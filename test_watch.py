#!/usr/bin/env python3
"""Unit tests for kettle_watch — the inbox folder-watch.

Stdlib only. Covers the pure, agent-free helpers (path resolution, the scan/seen-set, the
deterministic queue repair, the healthbeacon). The agent-firing intake_pass itself is not
exercised here (it spawns the `claude` CLI); its logic is the thin loop around these helpers.
"""

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import kettle_watch as w


class ResolveIntakeTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="sw-test-"))
        (self.tmp / "intake").mkdir()

    def test_none_without_intake_block(self):
        self.assertIsNone(w.resolve_intake({"id": "x", "root": str(self.tmp)}))
        self.assertIsNone(w.resolve_intake({"id": "x", "root": str(self.tmp), "intake": {}}))

    def test_subdir_watch_with_defaults(self):
        proj = {"id": "x", "root": str(self.tmp), "intake": {"watch": "intake"}}
        watch, responses, outbound, ignore = w.resolve_intake(proj)
        self.assertEqual(watch, (self.tmp / "intake").resolve())
        self.assertEqual(responses, (self.tmp / "responses").resolve())   # default
        self.assertEqual(outbound, (self.tmp / "outbox").resolve())       # default
        # responses/outbound dir names are always ignored by the scan
        self.assertIn("responses", ignore)
        self.assertIn("outbox", ignore)
        self.assertIn(".kettle", ignore)
        self.assertIn(".setsweep", ignore)

    def test_runtime_falls_back_to_legacy_desk(self):
        (self.tmp / ".setsweep").mkdir()
        runtime = w._runtime_dir({"id": "x", "root": str(self.tmp)})
        self.assertEqual(runtime, (self.tmp / ".setsweep" / "runtime").resolve())
        self.assertFalse((self.tmp / ".kettle").exists())

    def test_root_watch_and_absolute(self):
        proj = {"id": "x", "root": str(self.tmp),
                "intake": {"watch": ".", "responses": "drafts", "outbound": "/tmp/out"}}
        watch, responses, outbound, _ = w.resolve_intake(proj)
        self.assertEqual(watch, self.tmp.resolve())
        self.assertEqual(responses, (self.tmp / "drafts").resolve())
        self.assertEqual(outbound, Path("/tmp/out").resolve())


class ScanNewTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="sw-scan-"))

    def test_filters_dotfiles_dirs_ignore_and_seen(self):
        (self.tmp / "a.eml").write_text("1")
        (self.tmp / "b.txt").write_text("2")
        (self.tmp / ".hidden").write_text("x")          # dotfile → skipped
        (self.tmp / "responses").mkdir()                # dir + in ignore → skipped
        ignore = {"responses", ".kettle"}
        names = [p.name for p in w.scan_new(self.tmp, ignore, set())]
        self.assertEqual(sorted(names), ["a.eml", "b.txt"])
        # a seen path is excluded
        seen = {str((self.tmp / "a.eml").resolve()), str(self.tmp / "a.eml")}
        names2 = [p.name for p in w.scan_new(self.tmp, ignore, seen)]
        self.assertEqual(names2, ["b.txt"])

    def test_cap_per_run(self):
        for i in range(w.INTAKE_MAX_PER_RUN + 5):
            (self.tmp / f"item{i:02d}.txt").write_text("x")
        self.assertEqual(len(w.scan_new(self.tmp, set(), set())), w.INTAKE_MAX_PER_RUN)


class NormalizeQueueTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="sw-norm-"))
        self.qf = self.tmp / "queue.json"

    def test_defaults_status_and_backfills(self):
        self.qf.write_text(json.dumps({"entries": [
            {"id": "a"},                                  # missing status/project/project_root
            {"id": "b", "status": "approved"},            # real status must be preserved
        ]}))
        w.normalize_queue(self.qf, {"id": "proj", "root": str(self.tmp)})
        q = json.loads(self.qf.read_text())
        self.assertEqual(q["entries"][0]["status"], "pending")
        self.assertEqual(q["entries"][0]["project"], "proj")
        self.assertEqual(q["entries"][0]["project_root"], str(self.tmp.resolve()))
        self.assertEqual(q["entries"][1]["status"], "approved")   # not clobbered

    def test_malformed_is_silent(self):
        self.qf.write_text("{not json")
        w.normalize_queue(self.qf, {"id": "p", "root": str(self.tmp)})   # must not raise
        self.assertEqual(self.qf.read_text(), "{not json")               # left untouched


class HealthTest(unittest.TestCase):
    def test_writes_a_beacon(self):
        tmp = Path(tempfile.mkdtemp(prefix="sw-health-"))
        saved = w.CACHE, w.HEALTH
        w.CACHE = tmp
        w.HEALTH = tmp / "watch-health.json"
        try:
            w.log_health(3, status="ok")
            rec = json.loads(w.HEALTH.read_text())
            self.assertEqual(rec["curated"], 3)
            self.assertEqual(rec["status"], "ok")
            self.assertIn("last_run", rec)
        finally:
            w.CACHE, w.HEALTH = saved


class IntakePassTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="sw-pass-"))
        self.root = self.tmp / "project"
        self.watch = self.root / "incoming"
        self.watch.mkdir(parents=True)
        self.source = self.watch / "Request One.eml"
        self.source.write_text("Please reply")
        self.proj = {
            "id": "inbox", "name": "Inbox", "root": str(self.root),
            "intake": {"watch": "incoming", "responses": "responses"},
        }
        runtime = self.root / ".kettle" / "runtime"
        runtime.mkdir(parents=True)
        self.queue = runtime / "queue.json"
        self.queue.write_text(json.dumps({"entries": [{"id": "request-one"}]}))

    def test_success_builds_curator_command_marks_seen_and_normalizes(self):
        state = {}
        calls = []

        def run(cmd, **kwargs):
            calls.append((cmd, kwargs))
            return SimpleNamespace(returncode=0, stderr="")

        with mock.patch.object(w.subprocess, "run", side_effect=run):
            count = w.intake_pass(self.proj, state, {})
        self.assertEqual(count, 1)
        self.assertEqual(state["intake_seen"], [str(self.source.resolve())])
        entry = json.loads(self.queue.read_text())["entries"][0]
        self.assertEqual(entry["status"], "pending")
        self.assertEqual(entry["project"], "inbox")
        cmd, kwargs = calls[0]
        self.assertEqual(cmd[0], w.CLAUDE)
        self.assertIn("--add-dir", cmd)
        self.assertIn(str(self.source.resolve()), cmd[cmd.index("-p") + 1])
        self.assertEqual(kwargs["cwd"], str(self.root))
        self.assertEqual(kwargs["timeout"], 900)

    def test_timeout_reports_error_and_leaves_item_unseen(self):
        state = {}
        health = []
        with mock.patch.object(
            w.subprocess, "run",
            side_effect=w.subprocess.TimeoutExpired(["claude"], 900),
        ), mock.patch.object(w, "log_health", side_effect=lambda *a, **k: health.append((a, k))):
            count = w.intake_pass(self.proj, state, {})
        self.assertEqual(count, 0)
        self.assertEqual(state["intake_seen"], [])
        self.assertEqual(health[0][1]["status"], "error")
        self.assertIn("timed out", health[0][1]["error_msg"])

    def test_nonzero_curator_exit_is_retried_next_cycle(self):
        state = {}
        health = []
        result = SimpleNamespace(returncode=7, stderr="bad credentials")
        with mock.patch.object(w.subprocess, "run", return_value=result), \
                mock.patch.object(w, "log_health",
                                  side_effect=lambda *a, **k: health.append((a, k))):
            count = w.intake_pass(self.proj, state, {})
        self.assertEqual(count, 0)
        self.assertEqual(state["intake_seen"], [])
        self.assertIn("bad credentials", health[0][1]["error_msg"])


class MainTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="sw-main-"))
        self._saved = {name: getattr(w, name) for name in (
            "CLAUDE", "PROJECTS", "CACHE", "STATE", "HEALTH", "SCRIPT_DIR",
        )}
        w.CACHE = self.tmp / "cache"
        w.STATE = w.CACHE / "watch-state.json"
        w.HEALTH = w.CACHE / "watch-health.json"
        w.SCRIPT_DIR = self.tmp
        w.PROJECTS = self.tmp / "projects.json"
        curator = self.tmp / "claude-stub"
        curator.write_text("#!/bin/sh\nexit 0\n")
        curator.chmod(0o755)
        w.CLAUDE = str(curator)

    def tearDown(self):
        for name, value in self._saved.items():
            setattr(w, name, value)

    def test_main_runs_projects_persists_state_and_health(self):
        w.PROJECTS.write_text(json.dumps({"projects": [
            {"id": "one", "name": "One", "root": str(self.tmp)},
            {"id": "two", "name": "Two", "root": str(self.tmp)},
        ]}))
        with mock.patch.object(w, "intake_pass", side_effect=[2, 1]):
            code = w.main()
        self.assertEqual(code, 0)
        self.assertEqual(set(json.loads(w.STATE.read_text())), {"one", "two"})
        health = json.loads(w.HEALTH.read_text())
        self.assertEqual((health["status"], health["curated"]), ("ok", 3))

    def test_main_missing_curator_fails_with_healthbeacon(self):
        w.CLAUDE = str(self.tmp / "missing-curator")
        code = w.main()
        self.assertEqual(code, 1)
        health = json.loads(w.HEALTH.read_text())
        self.assertEqual(health["status"], "error")
        self.assertIn("not found", health["error"])

    def test_main_bad_registry_fails_with_healthbeacon(self):
        w.PROJECTS.write_text("{broken")
        code = w.main()
        self.assertEqual(code, 1)
        health = json.loads(w.HEALTH.read_text())
        self.assertIn("cannot read registry", health["error"])


if __name__ == "__main__":
    unittest.main()
