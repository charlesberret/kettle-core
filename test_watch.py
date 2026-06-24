#!/usr/bin/env python3
"""Unit tests for setsweep_watch — the inbox folder-watch.

Stdlib only. Covers the pure, agent-free helpers (path resolution, the scan/seen-set, the
deterministic queue repair, the healthbeacon). The agent-firing intake_pass itself is not
exercised here (it spawns the `claude` CLI); its logic is the thin loop around these helpers.
"""

import json
import tempfile
import unittest
from pathlib import Path

import setsweep_watch as w


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
        self.assertIn(".setsweep", ignore)

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
        ignore = {"responses", ".setsweep"}
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


if __name__ == "__main__":
    unittest.main()
