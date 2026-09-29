#!/usr/bin/env python3
"""Unit + integration tests for the Kettle server.

Stdlib only (unittest + urllib). Run:  python3 test_server.py   (or python3 -m unittest)

The server uses module-level globals for its data paths and security fence; each test
redirects those into a tempdir so the real registry/queue/settings are never touched.

SERIAL ONLY: this module temporarily replaces server globals and subprocess.Popen.
Do not run it under pytest-xdist until those seams become instance-scoped.
"""

import http.client
import io
import json
import os
import re
import signal
import socket
import shutil
import sys
import tempfile
import time
import unittest
import urllib.error
import urllib.request
from contextlib import redirect_stderr
from pathlib import Path

import kettle.server as server
import kettle.kettle_contract as kettle_contract
import kettle.sweepkit as sweepkit
from unittest import mock


def _auth_headers(extra=None):
    """Attach the live per-boot token (tests read it the same way clients do)."""
    h = {}
    if getattr(server, "SERVER_TOKEN", None):
        h[server.TOKEN_HEADER] = server.SERVER_TOKEN
    if extra:
        h.update(extra)
    return h


def _http(method, url, body=None, headers=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    for k, v in _auth_headers(headers).items():
        req.add_header(k, v)
    if data is not None and "Content-Type" not in (headers or {}):
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")


class Base(unittest.TestCase):
    """Redirect server globals into a tempdir under a fake HOME, with one project."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="kettle-test-"))
        self.root = self.tmp / "proj"
        (self.root / ".kettle").mkdir(parents=True)
        registry = self.tmp / "projects.json"
        registry.write_text(json.dumps({"projects": [{
            "id": "t", "name": "Test", "root": str(self.root),
            "ledger": None,
            "rework_agents": [{"id": "curator", "name": "the Test curator"}],
        }]}))

        self._saved = {k: getattr(server, k) for k in
                       ("PROJECTS_PATH", "SETTINGS_PATH", "BASE_ALLOWED_ROOTS", "HOME",
                        "RUNTIME_PATH", "SERVER_TOKEN")}
        server.PROJECTS_PATH = registry
        server.SETTINGS_PATH = self.tmp / "settings.json"
        server.BASE_ALLOWED_ROOTS = [self.tmp]
        server.HOME = self.tmp  # so add_project's under-HOME gate accepts temp roots
        server.RUNTIME_PATH = self.tmp / "cache" / "server.json"
        server.SERVER_TOKEN = None
        # the queue path is DERIVED by the server (runtime_dir/queue.json), never stored
        # in the registry — mirror that here so fixture writes land where the server reads
        self.queue = server.queue_path(server.get_project("t"))

    def tearDown(self):
        for k, v in self._saved.items():
            setattr(server, k, v)
        shutil.rmtree(self.tmp, ignore_errors=True)

    def proj(self):
        return server.get_project("t")

    def write_queue(self, entries):
        self.queue.write_text(json.dumps({"curated": "test", "entries": entries}))


class HelperTests(Base):

    def test_new_desk_file_is_owner_only(self):
        path = self.tmp / "fresh-desk.json"
        server.atomic_write(path, "{}")
        mode = path.stat().st_mode & 0o777
        self.assertEqual(mode, 0o600)
        log = self.tmp / "comments.log"
        server.append_line(log, "note\n")
        self.assertEqual(log.stat().st_mode & 0o777, 0o600)

    def test_get_project_requires_id(self):
        with self.assertRaises(KeyError) as cm:
            server.get_project(None)
        self.assertIn("missing project", str(cm.exception))
        with self.assertRaises(KeyError):
            server.get_project("")
        self.assertEqual(server.get_project("t")["id"], "t")

    def test_git_commit_activity_delegates(self):
        # Pure layers live in gitmap.py; server keeps a thin alias.
        act = server.git_commit_activity(self.root, weeks=8)
        self.assertTrue(act["ok"])
        self.assertFalse(act["git"])
        self.assertEqual(act["weeks"], 8)

    def test_resolve_projects_path_env_wins(self):
        explicit = self.tmp / "explicit-projects.json"
        prev = os.environ.get("DESK_PROJECTS")
        os.environ["DESK_PROJECTS"] = str(explicit)
        try:
            self.assertEqual(server.resolve_projects_path(), explicit)
        finally:
            if prev is None:
                os.environ.pop("DESK_PROJECTS", None)
            else:
                os.environ["DESK_PROJECTS"] = prev

    def test_resolve_projects_path_prefers_existing_user_registry(self):
        saved_home = server.HOME
        prev = os.environ.pop("DESK_PROJECTS", None)
        try:
            server.HOME = self.tmp
            user = server.user_projects_path()
            user.parent.mkdir(parents=True, exist_ok=True)
            user.write_text('{"projects":[]}')
            # Hide repo registry so user wins
            saved_appdir = server.APPDIR
            server.APPDIR = self.tmp / "empty-appdir"
            server.APPDIR.mkdir()
            self.assertEqual(server.resolve_projects_path(), user)
            server.APPDIR = saved_appdir
        finally:
            server.HOME = saved_home
            if prev is not None:
                os.environ["DESK_PROJECTS"] = prev

    def test_resolve_projects_path_falls_back_to_legacy_registry(self):
        saved_home = server.HOME
        saved_appdir = server.APPDIR
        prev = os.environ.pop("DESK_PROJECTS", None)
        try:
            server.HOME = self.tmp
            server.APPDIR = self.tmp / "empty-appdir"
            server.APPDIR.mkdir()
            legacy = server.legacy_user_projects_path()
            legacy.parent.mkdir(parents=True, exist_ok=True)
            legacy.write_text('{"projects":[]}')
            self.assertEqual(server.resolve_projects_path(), legacy)
        finally:
            server.HOME = saved_home
            server.APPDIR = saved_appdir
            if prev is not None:
                os.environ["DESK_PROJECTS"] = prev

    def test_desk_dir_prefers_kettle_and_falls_back_to_setsweep(self):
        proj = self.proj()
        current = self.root / ".kettle"
        legacy = self.root / ".setsweep"
        shutil.rmtree(current)
        legacy.mkdir()
        self.assertEqual(server.desk_dir(proj), legacy.resolve())
        current.mkdir()
        self.assertEqual(server.desk_dir(proj), current.resolve())

    def test_slug(self):
        self.assertEqual(server.slug("Hello World!"), "Hello_World")
        self.assertEqual(server.slug("a/b:c"), "a_b_c")
        self.assertEqual(server.slug("!!!"), "x")  # empty-after-strip fallback

    def test_session_name(self):
        # one session per project now: kettle-<project>, slugified, entry ignored
        n = server.session_name({"name": "CryptoHistory"})
        self.assertEqual(n, "kettle-cryptohistory")
        self.assertEqual(n, n.lower())
        self.assertNotIn(" ", n)
        # the entry argument is accepted but ignored (call-site compatibility)
        self.assertEqual(
            server.session_name({"name": "CryptoHistory"}, {"title": "Chapter 3"}),
            "kettle-cryptohistory")
        self.assertEqual(server.session_name({"name": "P"}), "kettle-p")
        # length-capped (slug body <= 48 chars after the kettle- prefix)
        long = server.session_name({"name": "x" * 80})
        self.assertLessEqual(len(long), len("kettle-") + 48)

    def test_safe_path_allows_under_root(self):
        p = self.root / "doc.md"
        p.write_text("hi")
        self.assertEqual(server.safe_path(str(p)), p.resolve())

    def test_safe_path_rejects_outside_fence(self):
        with self.assertRaises(PermissionError):
            server.safe_path("/etc/passwd")

    def test_safe_path_rejects_symlink_escape(self):
        # a symlink inside the fence pointing out must resolve-then-reject
        outside = self.tmp.parent / ("escape-" + self.tmp.name)
        outside.mkdir(exist_ok=True)
        try:
            link = self.root / "link"
            link.symlink_to(outside)
            with self.assertRaises(PermissionError):
                server.safe_path(str(link / "x"))
        finally:
            shutil.rmtree(outside, ignore_errors=True)

    def test_safe_path_dotdot_inside_ok_outside_rejected(self):
        # narrow the fence to the project root so `..` behaviour is meaningful:
        # a `..` that normalises back inside is fine; one that escapes is rejected.
        saved = server.BASE_ALLOWED_ROOTS
        server.BASE_ALLOWED_ROOTS = [self.root]
        try:
            inside = self.root / "a" / ".." / "b.md"            # -> self.root/b.md
            self.assertTrue(server.safe_path(str(inside)).is_relative_to(self.root.resolve()))
            with self.assertRaises(PermissionError):
                server.safe_path(str(self.root / ".." / "sibling.md"))  # escapes the root
        finally:
            server.BASE_ALLOWED_ROOTS = saved

    def test_safe_path_relative_without_base_rejected(self):
        # a relative path with no base must refuse outright — never resolve against CWD
        with self.assertRaises(PermissionError):
            server.safe_path("relative/x.md")

    def test_safe_path_relative_with_base_joins_to_root(self):
        # a relative path resolves against the supplied base (the project root), not CWD
        (self.root / ".kettle").mkdir(exist_ok=True)
        (self.root / ".kettle" / "PROJECT.md").write_text("charter")
        got = server.safe_path(".kettle/PROJECT.md", self.root)
        self.assertEqual(got, (self.root / ".kettle" / "PROJECT.md").resolve())

    def test_safe_path_relative_with_base_still_fences_traversal(self):
        # a relative path that climbs out of the fence via .. is still rejected post-join
        saved = server.BASE_ALLOWED_ROOTS
        server.BASE_ALLOWED_ROOTS = [self.root]
        try:
            with self.assertRaises(PermissionError):
                server.safe_path("../../etc/passwd", self.root)
        finally:
            server.BASE_ALLOWED_ROOTS = saved

    def test_safe_path_absolute_ignores_base(self):
        # an absolute path is unaffected by base (is_absolute short-circuits the join)
        p = self.root / "doc.md"
        p.write_text("hi")
        self.assertEqual(server.safe_path(str(p), self.tmp), p.resolve())

    def test_safe_path_null_byte_rejected(self):
        # an embedded NUL must never resolve into the fence — raise, never pass
        with self.assertRaises((ValueError, PermissionError)):
            server.safe_path(str(self.root) + "/a\x00b.md")

    def test_safe_path_honours_each_registered_project_root(self):
        # a file under a SECOND registered project root passes even though it is not
        # under the first root — the fence is the UNION of base + every project root.
        proj2 = self.tmp / "proj2"
        proj2.mkdir()
        saved_base = server.BASE_ALLOWED_ROOTS
        server.BASE_ALLOWED_ROOTS = [self.root]   # base no longer covers proj2 or tmp itself
        server.PROJECTS_PATH.write_text(json.dumps({"projects": [
            {"id": "t", "name": "T", "root": str(self.root),
             "queue": str(self.queue), "ledger": None, "rework_agents": []},
            {"id": "t2", "name": "T2", "root": str(proj2),
             "queue": str(proj2 / "q.json"), "ledger": None, "rework_agents": []},
        ]}))
        try:
            self.assertTrue(
                server.safe_path(str(proj2 / "x.md")).is_relative_to(proj2.resolve()))
            with self.assertRaises(PermissionError):
                server.safe_path(str(self.tmp / "loose.md"))   # under neither root
        finally:
            server.BASE_ALLOWED_ROOTS = saved_base

    def test_env_allowed_roots(self):
        # the portable fence: base roots come from $KETTLE_ALLOWED_ROOTS, default empty
        a, b = self.tmp / "vaultA", self.tmp / "vaultB"
        a.mkdir(); b.mkdir()
        saved = os.environ.get("KETTLE_ALLOWED_ROOTS")
        saved_legacy = os.environ.get("SETSWEEP_ALLOWED_ROOTS")
        try:
            os.environ["KETTLE_ALLOWED_ROOTS"] = f"{a}{os.pathsep}{b}"
            roots = server._env_allowed_roots()
            self.assertIn(a.resolve(), roots)
            self.assertIn(b.resolve(), roots)
            os.environ["KETTLE_ALLOWED_ROOTS"] = ""          # unset/empty → no base roots
            self.assertEqual(server._env_allowed_roots(), [])
            os.environ.pop("KETTLE_ALLOWED_ROOTS")
            os.environ["SETSWEEP_ALLOWED_ROOTS"] = str(a)
            self.assertEqual(server._env_allowed_roots(), [a.resolve()])
        finally:
            if saved is None:
                os.environ.pop("KETTLE_ALLOWED_ROOTS", None)
            else:
                os.environ["KETTLE_ALLOWED_ROOTS"] = saved
            if saved_legacy is None:
                os.environ.pop("SETSWEEP_ALLOWED_ROOTS", None)
            else:
                os.environ["SETSWEEP_ALLOWED_ROOTS"] = saved_legacy

    def test_settings_create_then_shallow_merge(self):
        # A missing file is seeded with a normalized curator block (provider/command/
        # models/menu) rather than {} — disk, core, and UI must share one pair.
        seeded = server.load_settings()
        self.assertTrue(server.SETTINGS_PATH.exists())
        self.assertEqual(seeded["curator"]["provider"], "claude")
        self.assertEqual(seeded["agents"], seeded["curator"]["models"])
        server.save_settings({"model": "sonnet"})
        server.save_settings({"colWidths": {"left": 280}})     # disjoint key
        merged = server.load_settings()
        self.assertEqual(merged["model"], "sonnet")            # preserved
        self.assertEqual(merged["colWidths"], {"left": 280})
        self.assertEqual(merged["curator"]["provider"], "claude")   # survives merges

    def test_settings_survives_corrupt_file(self):
        server.SETTINGS_PATH.write_text("{not json")
        loaded = server.load_settings()                        # no crash
        self.assertEqual(loaded["curator"]["provider"], "claude")   # reseeded
        self.assertTrue(server.SETTINGS_PATH.with_suffix(".json.corrupt").exists())

    def test_curator_block_preserves_unknown_keys(self):
        """The curator block is an extension point: normalizing it must not drop keys
        it does not own (idle_timeout_s, allow_unfenced_readonly, future groups)."""
        server.SETTINGS_PATH.write_text(json.dumps({"curator": {
            "provider": "claude", "allow_unfenced_readonly": True, "idle_timeout_s": 0.2,
        }}))
        block = server.load_settings()["curator"]
        self.assertIs(block["allow_unfenced_readonly"], True)
        self.assertEqual(block["idle_timeout_s"], 0.2)
        self.assertEqual(block["provider"], "claude")          # still normalized
        # and it survives a disjoint patch through save_settings
        after = server.save_settings({"colWidths": {"left": 280}})["curator"]
        self.assertIs(after["allow_unfenced_readonly"], True)

    def test_legacy_model_migrates(self):
        """A settings file predating the agents block resolves its top-level "model"
        into curator.models.chat on first load (back-compat, still supported)."""
        server.SETTINGS_PATH.write_text(json.dumps({"model": "opus"}))
        block = server.load_settings()["curator"]
        self.assertEqual(block["models"]["chat"], "opus")

    def test_curator_idle_timeout_setting(self):
        server.SETTINGS_PATH.write_text(json.dumps({
            "curator": {"idle_timeout_s": 0.2},
        }))
        self.assertEqual(server.curator_idle_timeout_s(), 0.2)
        server.SETTINGS_PATH.write_text(json.dumps({
            "curator": {"idle_timeout_s": "invalid"},
        }))
        self.assertEqual(server.curator_idle_timeout_s(),
                         server.DEFAULT_CURATOR_IDLE_TIMEOUT_S)

    def test_queue_creates_empty_when_missing(self):
        q = server.load_queue(self.proj())
        self.assertEqual(q["entries"], [])

    def test_mutate_queue_atomic_apply(self):
        self.write_queue([{"id": "a", "status": "pending"}])
        server.mutate_queue(self.proj(), lambda q: q["entries"][0].update(status="approved"))
        self.assertEqual(json.loads(self.queue.read_text())["entries"][0]["status"], "approved")

    def test_find_entry_raises_on_unknown(self):
        with self.assertRaises(KeyError):
            server.find_entry({"entries": [{"id": "a"}]}, "nope")

    def test_ensure_snapshots_caches_and_is_idempotent(self):
        f = self.root / "spine.md"
        f.write_text("original")
        self.write_queue([{"id": "e1", "status": "pending", "path": str(f)}])
        q = server.load_queue(self.proj())
        server.ensure_snapshots(self.proj(), q)
        snap = server.runtime_dir(self.proj()) / "snapshots" / "e1.orig"
        self.assertEqual(snap.read_text(), "original")
        f.write_text("edited later")                            # user edits the file
        server.ensure_snapshots(self.proj(), q)
        self.assertEqual(snap.read_text(), "original")          # first sight wins; not overwritten

    def test_ensure_snapshots_skips_missing_and_approved(self):
        self.write_queue([
            {"id": "gone", "status": "pending", "path": str(self.root / "absent.md")},
            {"id": "done", "status": "approved", "path": str(self.root / "x.md")},
        ])
        q = server.load_queue(self.proj())
        server.ensure_snapshots(self.proj(), q)                 # must not raise
        snapdir = server.runtime_dir(self.proj()) / "snapshots"
        self.assertFalse((snapdir / "gone.orig").exists())
        self.assertFalse((snapdir / "done.orig").exists())

    def test_session_store_shallow_merge(self):
        self.assertEqual(server.load_session(self.proj()), {})        # none yet
        server.save_session(self.proj(), session_id="s1", status="interviewing")
        server.save_session(self.proj(), last_entry="alpha")          # disjoint merge
        s = server.load_session(self.proj())
        self.assertEqual(s["session_id"], "s1")                       # preserved
        self.assertEqual(s["status"], "interviewing")
        self.assertEqual(s["last_entry"], "alpha")
        self.assertEqual(s.get("provider"), "claude")                 # stamped on sid write

    def test_session_id_for_curator_skips_foreign_provider(self):
        # Claude session under Grok must not --resume (Grok 404 → exit 1)
        server.save_settings({"curator": {"provider": "claude", "command": "claude",
                                          "models": {"setup": "sonnet", "chat": "sonnet",
                                                     "glance": "haiku"}}})
        server.save_session(self.proj(), session_id="claude-sid", status="founded")
        self.assertEqual(server.session_id_for_curator(proj=self.proj()), "claude-sid")

        server.save_settings({"curator": {"provider": "grok", "command": "grok",
                                          "models": {"setup": "grok-4.5", "chat": "grok-4.5",
                                                     "glance": "grok-composer-2.5-fast"}}})
        self.assertIsNone(server.session_id_for_curator(proj=self.proj()))

        # After a Grok turn lands a new sid, resume works again
        server.save_session(self.proj(), session_id="grok-sid", model="grok-4.5")
        self.assertEqual(
            server.session_id_for_curator(proj=self.proj(), model="grok-4.5"),
            "grok-sid",
        )
        self.assertEqual(server.load_session(self.proj())["provider"], "grok")

        # Different model on Grok → fresh session (agent-incompatible mid-session switch)
        self.assertIsNone(
            server.session_id_for_curator(proj=self.proj(), model="grok-composer-2.5-fast"),
        )
        # Untagged model under Grok + explicit want → also refuse (legacy chat→sweep case)
        server.save_session(self.proj(), session_id="grok-untagged")
        sess = server.load_session(self.proj())
        sess.pop("model", None)
        server.session_path(self.proj()).write_text(json.dumps(sess, indent=2))
        self.assertIsNone(
            server.session_id_for_curator(proj=self.proj(), model="grok-4.5"),
        )

    def test_session_migrates_legacy_interview_json(self):
        # an in-flight founding written under the old interview.json must survive: the
        # first load_session migrates it into session.json
        rd = server.runtime_dir(self.proj())
        (rd / "interview.json").write_text(json.dumps(
            {"session_id": "legacy-sid", "status": "interviewing"}))
        s = server.load_session(self.proj())
        self.assertEqual((s["session_id"], s["status"]), ("legacy-sid", "interviewing"))
        self.assertTrue((rd / "session.json").exists())               # promoted on first read

    def test_project_orientation_reads_and_truncates(self):
        self.assertEqual(server.project_orientation(self.proj()), "")  # missing → ""
        (self.root / ".kettle" / "PROJECT.md").write_text("X" * 9000)
        out = server.project_orientation(self.proj())
        self.assertIn("PROJECT.md", out)                       # labeled
        self.assertEqual(out.count("X"), 6000)                 # body truncated
        self.assertIn("truncated at 6000 of 9000 characters", out)  # visibly
        self.assertNotIn("MEMORY.md", out)                     # absent file → section omitted

    def test_project_orientation_includes_curator_memory(self):
        desk = self.root / ".kettle"
        (desk / "PROJECT.md").write_text("the charter")
        (desk / "MEMORY.md").write_text("- 2026-06-11: user prefers serial commas")
        out = server.project_orientation(self.proj())
        self.assertIn("the charter", out)
        self.assertIn("prefers serial commas", out)
        self.assertLess(out.index("the charter"), out.index("prefers serial commas"))  # charter first
        (desk / "MEMORY.md").write_text("   \n")               # whitespace-only → omitted
        self.assertNotIn("MEMORY.md", server.project_orientation(self.proj()))

    def test_project_orientation_includes_familiarity(self):
        desk = self.root / ".kettle"
        (desk / "PROJECT.md").write_text("charter")
        (desk / "FAMILIARITY.md").write_text("## Map\n- `src/content` is the content collections root")
        out = server.project_orientation(self.proj())
        self.assertIn("FAMILIARITY.md", out)
        self.assertIn("content collections", out)
        self.assertLess(out.index("charter"), out.index("content collections"))

    def test_project_orientation_includes_sweep_actions(self):
        desk = self.root / ".kettle"
        (desk / "SWEEP-ACTIONS.md").write_text(
            "- Stage approved drafts to outbound\n- Append sitting log to ~/Notes/rounds.md\n")
        out = server.project_orientation(self.proj())
        self.assertIn("SWEEP-ACTIONS.md", out)
        self.assertIn("rounds.md", out)
        self.assertIn("Never transmit", out)

    def test_build_refresh_briefs_prompt_empty_and_stocked(self):
        proj = self.proj()
        self.assertIsNone(server.build_refresh_briefs_prompt(proj))
        (self.root / "memo.md").write_text("decision memo\n")
        self.write_queue([{
            "id": "memo",
            "path": str(self.root / "memo.md"),
            "status": "pending",
            "ask": "Accept D10",
            "brief": "Round 2 founder decision on D10 and GREASE.",
        }])
        prompt = server.build_refresh_briefs_prompt(proj)
        self.assertIsNotNone(prompt)
        self.assertIn("cold re-entry", prompt.lower())
        self.assertIn("CURRENT QUEUE ENTRIES", prompt)
        self.assertIn("memo", prompt)
        self.assertIn("D10", prompt)  # old brief still listed for rewrite
        self.assertIn(str(server.queue_path(proj)), prompt)

    def test_project_orientation_marks_truncated_memory(self):
        proj = self.proj()
        rulings = "\n".join(f"- 2026-09-{i % 28 + 1:02d} ruling number {i}" for i in range(80))
        (server.desk_dir(proj) / "MEMORY.md").write_text(rulings)
        orientation = server.project_orientation(proj)
        self.assertIn("ruling number 79", orientation)  # an ~80-line memory fits whole
        (server.desk_dir(proj) / "MEMORY.md").write_text("x" * 20000)
        self.assertIn("truncated at 6000 of 20000 characters", server.project_orientation(proj))

    def test_project_orientation_carries_the_projects_claude_md_text(self):
        """Claude curator turns ignore project settings (and with them CLAUDE.md), so
        the conventions reach the curator as prompt text instead."""
        proj = self.proj()
        (server.project_root(proj) / "CLAUDE.md").write_text("Use Oxford commas.\n")
        orientation = server.project_orientation(proj)
        self.assertIn("Use Oxford commas.", orientation)
        self.assertIn("text only", orientation)

    def test_sweep_precomputed_context_includes_diffs(self):
        (self.root / "alpha.md").write_text("alpha body\n")
        (self.root / "beta.md").write_text("beta body\n")
        self.write_queue([
            {"id": "alpha", "path": str(self.root / "alpha.md"), "status": "pending"},
            {"id": "beta", "path": str(self.root / "beta.md"), "status": "pending"},
        ])
        proj = self.proj()
        q = server.load_queue(proj)
        server.ensure_snapshots(proj, q)
        (self.root / "alpha.md").write_text("alpha body\nchanged\n")
        block = server.sweep_precomputed_context(proj, q.get("entries", []))
        self.assertIn("### entry alpha", block)
        self.assertIn("diff:", block)
        self.assertIn("changed", block)
        self.assertIn("beta", block)

    # ---- register_project: shared by the HTTP handler and the CLI (first-run) ----

    def test_register_project_valid_seeds_desk(self):
        folder = self.tmp / "notes"
        folder.mkdir()
        proj = server.register_project("My Notes", str(folder))
        self.assertEqual(proj["id"], "my_notes")
        self.assertEqual(proj["name"], "My Notes")
        # appended to the registry
        ids = [p["id"] for p in json.loads(server.PROJECTS_PATH.read_text())["projects"]]
        self.assertIn("my_notes", ids)
        # durable desk + seeded queue (awaiting founding) + egress outbound
        self.assertTrue((folder / ".kettle").is_dir())
        self.assertTrue((folder / ".kettle" / "outbound" / "README.md").is_file())
        q = json.loads(server.queue_path(proj).read_text())
        self.assertEqual(q["curated"], "awaiting founding curation")

    def test_register_project_duplicate_raises(self):
        folder = self.tmp / "dup"; folder.mkdir()
        server.register_project("Dup", str(folder))
        with self.assertRaises(ValueError):
            server.register_project("Dup", str(folder))

    def test_project_for_path_finds_owning_desk(self):
        self.assertEqual(server.project_for_path(self.root / "x" / "y.md")["id"], "t")
        self.assertIsNone(server.project_for_path(self.tmp / "outside.md"))

    def test_register_project_nonexistent_raises(self):
        with self.assertRaises(ValueError):
            server.register_project("Ghost", str(self.tmp / "nope"))

    def test_register_project_outside_home_fence_raises(self):
        with self.assertRaises(ValueError):
            server.register_project("Evil", "/etc")        # HOME is self.tmp in the fixture

    def test_register_project_creates_registry_on_first_run(self):
        server.PROJECTS_PATH = self.tmp / "fresh" / "projects.json"   # does not exist yet
        folder = self.tmp / "first"; folder.mkdir()
        proj = server.register_project("First", str(folder))
        self.assertTrue(server.PROJECTS_PATH.exists())
        self.assertEqual([p["id"] for p in
                          json.loads(server.PROJECTS_PATH.read_text())["projects"]], [proj["id"]])

    def test_register_project_blank_name_raises(self):
        folder = self.tmp / "blank"; folder.mkdir()
        with self.assertRaises(ValueError):
            server.register_project("   ", str(folder))


class EndpointTests(Base):

    def setUp(self):
        super().setUp()
        self.write_queue([
            {"id": "alpha", "title": "Alpha — first", "path": str(self.root / "alpha.md"),
             "status": "pending", "urgency": "high", "ask_type": "tuning"},
            {"id": "beta", "title": "Beta — second", "path": str(self.root / "beta.md"),
             "status": "pending", "urgency": "low", "ask_type": "judgment"},
        ])
        (self.root / "alpha.md").write_text("alpha body")
        (self.root / "beta.md").write_text("beta body")
        self.srv, self.port = server.start_server(0)
        self.base = f"http://127.0.0.1:{self.port}"

    def tearDown(self):
        self.srv.shutdown()
        self.srv.server_close()
        super().tearDown()

    def test_projects_lists_registry(self):
        s, j = _http("GET", f"{self.base}/api/projects")
        self.assertEqual(s, 200)
        self.assertEqual([p["id"] for p in j["projects"]], ["t"])

    def test_missing_prompt_uses_fallback_and_ephemeral_server_stays_healthy(self):
        saved = server.PROMPTS_DIR
        server.PROMPTS_DIR = self.tmp / "missing-prompts"
        self.addCleanup(lambda: setattr(server, "PROMPTS_DIR", saved))
        warning = io.StringIO()
        with redirect_stderr(warning):
            prompt = server._load_prompt("absent.md", "Emergency {name}")
        self.assertEqual(prompt, "Emergency {name}")
        self.assertIn("using emergency fallback", warning.getvalue())

        extra_server, extra_port = server.start_server(0)
        try:
            status, payload = _http("GET", f"http://127.0.0.1:{extra_port}/api/ping")
            self.assertEqual(status, 200)
            self.assertEqual(payload["app"], "kettle")
            self.assertEqual(payload["port"], extra_port)
        finally:
            extra_server.shutdown()
            extra_server.server_close()

    def test_save_logs_user_edit_to_lineage(self):
        import kettle.lineage as lineage
        f = self.root / "alpha.md"
        s, _ = _http("POST", f"{self.base}/api/save",
                     {"path": str(f), "content": "user's own edit\n"})
        self.assertEqual(s, 200)
        self.assertEqual(f.read_text(), "user's own edit\n")
        recs = lineage.read_record(self.root)
        self.assertTrue(any(r["actor_kind"] == "user" and "alpha.md" in r["files"]
                            for r in recs), "editor save should log a user edit")

    def test_lineage_endpoints_status_resolve_accept(self):
        # baseline, out-of-band change → unattributed, resolve → user
        s, j = _http("POST", f"{self.base}/api/lineage/accept", {"project": "t"})
        self.assertEqual((s, j["ok"]), (200, True))
        (self.root / "alpha.md").write_text("changed out of band\n")
        _, st = _http("GET", f"{self.base}/api/lineage?project=t")
        self.assertEqual(st["counts"]["unattributed"], 1)
        s, _ = _http("POST", f"{self.base}/api/lineage/resolve",
                     {"project": "t", "path": "alpha.md", "as": "user"})
        self.assertEqual(s, 200)
        _, st = _http("GET", f"{self.base}/api/lineage?project=t")
        self.assertEqual(st["counts"], {"agent": 0, "user": 1, "unattributed": 0})

    def test_lineage_bind_writes_directive(self):
        s, j = _http("POST", f"{self.base}/api/lineage/bind", {"project": "t"})
        self.assertEqual((s, j["ok"]), (200, True))
        self.assertIn("kettle:lineage", (self.root / "CLAUDE.md").read_text())

    def test_queue_get_creates_snapshots(self):
        s, j = _http("GET", f"{self.base}/api/queue?project=t")
        self.assertEqual(s, 200)
        self.assertEqual(len(j["entries"]), 2)
        self.assertTrue((server.runtime_dir(self.proj()) / "snapshots" / "alpha.orig").exists())

    def test_queue_mutate_zero_skips_snapshots(self):
        snap = server.runtime_dir(self.proj()) / "snapshots" / "alpha.orig"
        self.assertFalse(snap.exists())
        s, j = _http("GET", f"{self.base}/api/queue?project=t&mutate=0")
        self.assertEqual(s, 200)
        self.assertEqual(len(j["entries"]), 2)
        self.assertFalse(snap.exists(), "pure read must not create snapshots")

    def test_file_get_fenced(self):
        s, j = _http("GET", f"{self.base}/api/file?path={self.root}/alpha.md&project=t")
        self.assertEqual((s, j["content"]), (200, "alpha body"))
        s2, _ = _http("GET", f"{self.base}/api/file?path=/etc/passwd&project=t")
        self.assertEqual(s2, 403)
        s3, j3 = _http("GET", f"{self.base}/api/file?path={self.root}/alpha.md")
        self.assertEqual(s3, 400)
        self.assertIn("missing project", j3["error"])

    def test_save_fenced_and_atomic(self):
        s, _ = _http("POST", f"{self.base}/api/save",
                     {"path": str(self.root / "alpha.md"), "content": "rewritten"})
        self.assertEqual(s, 200)
        self.assertEqual((self.root / "alpha.md").read_text(), "rewritten")
        s2, _ = _http("POST", f"{self.base}/api/save",
                      {"path": "/tmp/evil.md", "content": "x"})
        self.assertEqual(s2, 403)

    def test_settings_roundtrip(self):
        s0, j0 = _http("GET", f"{self.base}/api/settings")
        self.assertEqual(s0, 200)
        self.assertIn("curator", j0)  # normalized block even on empty settings
        self.assertEqual(j0["curator"]["provider"], "claude")
        _http("POST", f"{self.base}/api/settings", {"model": "opus"})
        _http("POST", f"{self.base}/api/settings", {"colors": {"--bg": "#000"}})
        s, j = _http("GET", f"{self.base}/api/settings")
        self.assertEqual(j["model"], "opus")                   # disjoint key kept
        self.assertEqual(j["colors"], {"--bg": "#000"})
        # The legacy top-level "model" does NOT override an established pair: settings
        # are seeded with an explicit agents.chat, and explicit beats legacy (see
        # curator.models_from_settings). Legacy migration is for files predating the
        # agents block — HelperTests.test_legacy_model_migrates covers that path.
        self.assertEqual(j["curator"]["models"]["chat"], "sonnet")
        # the modern path does change it, and the agents mirror stays in sync
        _http("POST", f"{self.base}/api/settings",
              {"curator": {"models": {"chat": "opus"}}})
        _, j2 = _http("GET", f"{self.base}/api/settings")
        self.assertEqual(j2["curator"]["models"]["chat"], "opus")
        self.assertEqual(j2["agents"]["chat"], "opus")

    def test_ping_exposes_curator(self):
        s, j = _http("GET", f"{self.base}/api/ping")
        self.assertEqual(s, 200)
        self.assertIn("curator", j)
        self.assertEqual(j["curator"]["provider"], "claude")
        self.assertIn("models", j["curator"])

    def test_curator_catalog(self):
        s, j = _http("GET", f"{self.base}/api/curator/catalog")
        self.assertEqual(s, 200)
        self.assertIn("providers", j)
        self.assertIn("models", j)
        self.assertIn("visible", j)
        self.assertIn("menu", j)
        self.assertEqual(j["menu"]["claude"], ["haiku", "sonnet", "opus"])
        # Seeded checkmarks — fable not in default menu
        visible_ids = {v["id"] for v in j["visible"] if v["provider"] == "claude"}
        self.assertNotIn("fable", visible_ids)
        # Persist custom menu
        _http("POST", f"{self.base}/api/settings", {
            "curator": {"menu": {"claude": ["opus"]}},
        })
        _, j2 = _http("GET", f"{self.base}/api/curator/catalog")
        self.assertEqual(j2["menu"]["claude"], ["opus"])

    def test_git_activity_route_nongit(self):
        s, j = _http("GET", f"{self.base}/api/git/activity?project=t&weeks=8")
        self.assertEqual(s, 200)
        self.assertTrue(j.get("ok"))
        self.assertFalse(j.get("git"))  # fixture root is not a git repo
        self.assertEqual(j.get("source"), "mtime")  # filesystem fallback
        self.assertEqual(j.get("weeks"), 8)
        self.assertIsInstance(j.get("cells"), list)
        self.assertEqual(j.get("dow_start"), 0)
        s2, _ = _http("GET", f"{self.base}/api/git/activity")
        self.assertEqual(s2, 400)  # project required

    def test_git_activity_route_with_commits_adaptive(self):
        """HTTP contract: temp git project → adaptive weeks + week grain when sparse."""
        import subprocess
        from datetime import date, timedelta
        try:
            subprocess.run(["git", "--version"], capture_output=True, check=True)
        except (OSError, subprocess.CalledProcessError):
            self.skipTest("git not on PATH")
        subprocess.run(["git", "init"], cwd=self.root, check=True, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"],
            cwd=self.root, check=True, capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test"],
            cwd=self.root, check=True, capture_output=True,
        )
        f = self.root / "note.txt"
        env = os.environ.copy()
        today = date.today()
        for i, offset in enumerate((5, 0)):
            f.write_text(f"line {i}\n")
            subprocess.run(["git", "add", "note.txt"], cwd=self.root, check=True, capture_output=True)
            d = today - timedelta(days=offset)
            stamp = d.isoformat() + "T12:00:00"
            env["GIT_AUTHOR_DATE"] = stamp
            env["GIT_COMMITTER_DATE"] = stamp
            subprocess.run(
                ["git", "commit", "-m", f"c{i}"],
                cwd=self.root, check=True, capture_output=True, env=env,
            )
        # adaptive (no weeks=)
        s, j = _http("GET", f"{self.base}/api/git/activity?project=t")
        self.assertEqual(s, 200)
        self.assertTrue(j["ok"])
        self.assertTrue(j["git"])
        self.assertTrue(j.get("adaptive"))
        self.assertIn(j.get("grain"), ("day", "week"))
        self.assertGreaterEqual(j["total"], 2)
        self.assertIn("first_date", j)
        self.assertIn("last_date", j)
        self.assertTrue(any(c.get("level", 0) >= 1 for c in j["cells"] if c.get("count")))
        # levels are sevenths (0–7); sparse history stays low
        lit = [c for c in j["cells"] if c.get("count")]
        self.assertTrue(all(1 <= c.get("level", 0) <= 7 for c in lit))
        self.assertTrue(all(c.get("level", 0) <= 3 for c in lit))
        # fixed weeks still works
        s2, j2 = _http("GET", f"{self.base}/api/git/activity?project=t&weeks=4")
        self.assertEqual(s2, 200)
        self.assertEqual(j2["weeks"], 4)
        self.assertFalse(j2.get("adaptive"))

    # ---- provider capability table + read-only enforcement (brief 06) ----

    def _write_settings(self, obj):
        server.SETTINGS_PATH.write_text(json.dumps(obj))
        self.addCleanup(lambda: server.SETTINGS_PATH.exists()
                        and server.SETTINGS_PATH.unlink())

    def test_ping_and_catalog_expose_capabilities(self):
        s, j = _http("GET", f"{self.base}/api/ping")
        self.assertEqual(s, 200)
        caps = j["curator"]["capabilities"]
        # default provider is claude — interview tool-less + fenced writes on chat/sweep
        self.assertTrue(caps["read_only_tier"])
        self.assertTrue(caps["fenced_writes"])

        s2, cat = _http("GET", f"{self.base}/api/curator/catalog")
        self.assertEqual(s2, 200)
        self.assertIn("capabilities", cat["active"])
        by_id = {p["id"]: p for p in cat["providers"]}
        self.assertTrue(by_id["claude"]["capabilities"]["read_only_tier"])
        # Grok interview is tool-less (core survey); write tiers still unfenced
        self.assertTrue(by_id["grok"]["capabilities"]["read_only_tier"])
        self.assertFalse(by_id["grok"]["capabilities"]["fenced_writes"])

    def test_interview_tool_less_proceeds_for_grok(self):
        # Founding interview is tool-less for every provider — no 409 refuse for Grok.
        stub = self.tmp / "grok-stub"
        stub.write_text(
            "#!/bin/sh\n"
            f"echo '{self._init(sid='sid-grok')}'\n"
            f"echo '{self._say('opening from survey')}'\n"
            f"echo '{self._result()}'\n"
        )
        stub.chmod(0o755)
        self._write_settings({"curator": {"provider": "grok", "command": str(stub)}})
        s, body = self._post_stream("/api/interview", {"project": "t", "message": "hi"})
        self.assertEqual(s, 200)
        ev = self._events(body)
        self.assertTrue(any(e.get("t") == "text" and "opening from survey" in (e.get("s") or "")
                            for e in ev), f"events={ev}")
        self.assertFalse(any("read-only downgrade" in (e.get("s") or "") for e in ev))
        # Phase A survey snapshot is written for the desk
        sp = server.survey_path(self.proj())
        self.assertTrue(sp.is_file(), f"expected survey at {sp}")
        snap = json.loads(sp.read_text())
        self.assertTrue(snap.get("ok"))
        self.assertIn("top_level", snap)

    def test_interview_tool_less_for_claude(self):
        # Default provider claude — tool-less interview, no downgrade notice.
        self._stub_claude(self._init(sid="sid-iv"), self._say("surveying"), self._result())
        s, body = self._post_stream("/api/interview", {"project": "t", "message": "hi"})
        self.assertEqual(s, 200)
        ev = self._events(body)
        self.assertTrue(any(e.get("t") == "text" and "surveying" in (e.get("s") or "")
                            for e in ev))
        self.assertFalse(any("read-only downgrade" in (e.get("s") or "") for e in ev))
        self.assertTrue(server.survey_path(self.proj()).is_file())

    def test_read_only_capability_error_still_names_options_when_weak(self):
        # Guard remains for non-interview callers when guarantees_read_only is false.
        from unittest.mock import patch
        self._write_settings({"curator": {"provider": "claude", "command": "claude"}})
        with patch.object(server.runtime, "guarantees_read_only", return_value=False):
            err = server.read_only_capability_error()
        self.assertIsNotNone(err)
        self.assertEqual(err["error"], "read_only_unavailable")
        self.assertTrue(err["options"])

    def test_kits_get_lists_defaults(self):
        s, j = _http("GET", f"{self.base}/api/kits")
        self.assertEqual(s, 200)
        self.assertEqual(j["kinds"], ["writing", "code", "records", "knowledge", "inbox"])
        self.assertTrue(any(k.get("_key") == "code" for k in j["kits"]))

    def test_kits_save_path_like_key_stays_in_settings_fence(self):
        # User kits are values inside the fixed SETTINGS_PATH, never filenames derived
        # from the client key. A traversal-shaped key therefore cannot select a path.
        key = "../../outside-kit"
        s, j = _http("POST", f"{self.base}/api/kits/save", {
            "key": key,
            "kit": {"name": "Traversal-shaped", "kind": "code", "lens": "stay fenced"},
        })
        self.assertEqual(s, 200)
        self.assertTrue(any(k.get("_key") == key for k in j["kits"]))
        self.assertEqual(server.load_settings()["kits"][key]["lens"], "stay fenced")
        self.assertFalse((self.tmp / "outside-kit.json").exists())
        self.assertFalse((self.root / "outside-kit.json").exists())

    def test_kits_delete_removes_only_user_override(self):
        _http("POST", f"{self.base}/api/kits/save", {
            "key": "code",
            "kit": {"name": "My Code", "kind": "code", "lens": "custom"},
        })
        s, j = _http("POST", f"{self.base}/api/kits/delete", {"key": "code"})
        self.assertEqual(s, 200)
        code = next(k for k in j["kits"] if k.get("_key") == "code")
        self.assertEqual(code["_source"], "default")
        self.assertNotIn("code", server.load_settings().get("kits", {}))

    def test_chatlog_post_then_get(self):
        messages = [
            {"role": "user", "text": "question"},
            {"role": "agent", "text": "answer"},
        ]
        s, saved = _http("POST", f"{self.base}/api/chatlog",
                         {"project": "t", "messages": messages})
        self.assertEqual((s, saved["count"]), (200, 2))
        s2, loaded = _http("GET", f"{self.base}/api/chatlog?project=t")
        self.assertEqual((s2, loaded["messages"]), (200, messages))

    def test_compact_without_session_is_terminal_noop(self):
        s, body = self._post_stream("/api/compact", {"project": "t"})
        self.assertEqual(s, 200)
        self.assertEqual(self._events(body)[-1]["t"], "done")
        ping, _ = _http("GET", f"{self.base}/api/ping")
        self.assertEqual(ping, 200)

    def test_refound_backs_up_and_reseeds_desk(self):
        desk = server.desk_dir(self.proj())
        (desk / "PROJECT.md").write_text("old charter")
        server.save_session(self.proj(), session_id="old", status="founded",
                            founding_note="keep this steer")
        s, j = _http("POST", f"{self.base}/api/projects/refound", {"id": "t"})
        self.assertEqual((s, j["ok"]), (200, True))
        self.assertTrue(Path(j["backup"]).is_dir())
        self.assertEqual(server.load_queue(self.proj())["entries"], [])
        sess = server.load_session(self.proj())
        self.assertEqual(sess, {"founding_note": "keep this steer"})
        self.assertFalse((desk / "PROJECT.md").exists())

    def test_refound_keeps_append_only_records(self):
        desk = server.desk_dir(self.proj())
        (desk / "PROJECT.md").write_text("old charter")
        (desk / "DESK-PROPOSAL.md").write_text("old proposal")
        (desk / "working-record.jsonl").write_text('{"actor": "user"}\n')
        (desk / "archive").mkdir(exist_ok=True)
        (desk / "archive" / "2026-01-01-000000-batch.json").write_text("{}")
        (desk / "outbound").mkdir(exist_ok=True)
        (desk / "outbound" / "memo.md").write_text("staged")
        server.comments_log_path(self.proj()).write_text("2026-01-01\talpha\tnote\n")
        s, j = _http("POST", f"{self.base}/api/projects/refound", {"id": "t"})
        self.assertEqual(s, 200)
        self.assertFalse((desk / "PROJECT.md").exists())
        self.assertFalse((desk / "DESK-PROPOSAL.md").exists())
        self.assertEqual((desk / "working-record.jsonl").read_text(), '{"actor": "user"}\n')
        self.assertTrue((desk / "archive" / "2026-01-01-000000-batch.json").exists())
        self.assertTrue((desk / "outbound" / "memo.md").exists())
        self.assertIn("note", server.comments_log_path(self.proj()).read_text())
        self.assertEqual(server.load_queue(self.proj())["entries"], [])
        self.assertIn("working-record.jsonl", j["kept"])

    def test_refound_is_refused_while_a_curator_turn_runs(self):
        key = server._stream_key(server.project_root(self.proj()))
        with server.SWEEPS_LOCK:
            server.CURATOR_STREAMS[key] = 1
        self.addCleanup(lambda: server.CURATOR_STREAMS.pop(key, None))
        s, j = _http("POST", f"{self.base}/api/projects/refound", {"id": "t"})
        self.assertEqual(s, 409)
        self.assertEqual(j["code"], "busy")

    def test_static_shell_scripts_fonts_and_font_traversal(self):
        def raw(path):
            conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
            try:
                conn.request("GET", path)
                res = conn.getresponse()
                return res.status, dict(res.getheaders()), res.read()
            finally:
                conn.close()

        s, headers, body = raw("/")
        self.assertEqual(s, 200)
        self.assertIn(b"<!DOCTYPE HTML", body[:100].upper())
        self.assertIn("no-store", headers.get("Cache-Control", ""))

        s2, headers2, body2 = raw("/themes.js")
        self.assertEqual(s2, 200)
        self.assertTrue(body2)
        self.assertIn("javascript", headers2.get("Content-Type", ""))

        font = "/fonts/IBMPlexMono-Regular.woff2"
        s3, headers3, body3 = raw(font)
        self.assertEqual(s3, 200)
        self.assertTrue(body3)
        self.assertEqual(headers3.get("Content-Type"), "font/woff2")

        # This resolves back to the same bundled font if traversal is normalized.
        # The route must reject it before opening the file.
        s4, _, _ = raw("/fonts/../fonts/IBMPlexMono-Regular.woff2")
        self.assertEqual(s4, 404)

    def test_comment_set_overwrite_clear(self):
        _http("POST", f"{self.base}/api/comment", {"project": "t", "id": "alpha", "text": "note one"})
        e = self._entry("alpha")
        self.assertEqual(e["comment"], "note one")
        _http("POST", f"{self.base}/api/comment", {"project": "t", "id": "alpha", "text": "note two"})
        self.assertEqual(self._entry("alpha")["comment"], "note two")   # overwrite, not append
        _http("POST", f"{self.base}/api/comment", {"project": "t", "id": "alpha", "text": "  "})
        self.assertNotIn("comment", self._entry("alpha"))               # empty clears

    def test_comment_is_per_entry(self):
        _http("POST", f"{self.base}/api/comment", {"project": "t", "id": "alpha", "text": "only alpha"})
        self.assertEqual(self._entry("alpha").get("comment"), "only alpha")
        self.assertIsNone(self._entry("beta").get("comment"))           # the bug we fixed

    def test_parse_comments_log(self):
        p = self.tmp / "comments.log"
        p.write_text(
            "2026-06-29\talpha\tnote one\n"
            "2026-06-29\talpha\tnote two\n"
            "2026-06-28\tbeta\tother note\n"
        )
        m = server.parse_comments_log(p)
        self.assertEqual(m["alpha"], [{"date": "2026-06-29", "text": "note one"},
                                       {"date": "2026-06-29", "text": "note two"}])
        self.assertEqual(m["beta"], [{"date": "2026-06-28", "text": "other note"}])

    def test_comments_close_marker_retires_only_earlier_lines(self):
        p = self.tmp / "comments.log"
        p.write_text(
            "2026-06-29\talpha\told note\n"
            "2026-06-29\tbeta\tbeta note\n"
            "2026-06-30\talpha\tlate note\n"
            "2026-06-30\talpha\t[kettle:closed through 2]\n"
        )
        m = server.parse_comments_log(p)
        self.assertEqual(m["alpha"], [{"date": "2026-06-30", "text": "late note"}])
        self.assertEqual(m["beta"], [{"date": "2026-06-29", "text": "beta note"}])

    def test_comment_appends_to_comments_log(self):
        _http("POST", f"{self.base}/api/comment", {"project": "t", "id": "alpha", "text": "fix TKs"})
        log = server.comments_log_path(self.proj())
        self.assertTrue(log.exists())
        self.assertIn("fix TKs", log.read_text())
        self.assertIn("\talpha\t", log.read_text())

    def test_queue_includes_comment_history(self):
        server.comments_log_path(self.proj()).write_text(
            "2026-06-29\talpha\tfix the TKs\n"
            "2026-06-29\talpha\talso check tone\n"
        )
        s, j = _http("GET", f"{self.base}/api/queue?project=t")
        self.assertEqual(s, 200)
        alpha = next(e for e in j["entries"] if e["id"] == "alpha")
        self.assertEqual(len(alpha["comment_history"]), 2)
        self.assertEqual(alpha["comment_history"][0]["text"], "fix the TKs")

    def test_sweep_injects_user_comments_from_log(self):
        server.comments_log_path(self.proj()).write_text(
            "2026-06-29\talpha\tfix the TKs\n"
            "2026-06-29\talpha\talso check tone\n"
        )
        cmds = self._capture_cmds()
        self._post_stream("/api/sweep", {"project": "t"})
        prompt = cmds[-1][cmds[-1].index("-p") + 1]
        self.assertIn("USER COMMENTS", prompt)
        self.assertIn("User comment for this entry: fix the TKs", prompt)
        self.assertIn("User comment for this entry: also check tone", prompt)
        self.assertIn("comments.log", prompt)

    def test_approve_marks_and_logs(self):
        s, _ = _http("POST", f"{self.base}/api/approve", {"project": "t", "id": "beta"})
        self.assertEqual(s, 200)
        self.assertEqual(self._entry("beta")["status"], "approved")
        self.assertTrue((server.runtime_dir(self.proj()) / "approvals.log").exists())

    def test_reapprove_keeps_the_first_date_and_logs_once(self):
        _http("POST", f"{self.base}/api/approve", {"project": "t", "id": "beta"})
        server.mutate_queue(self.proj(), lambda q: server.find_entry(q, "beta").__setitem__(
            "approved", "2026-01-01"))
        _http("POST", f"{self.base}/api/approve", {"project": "t", "id": "beta"})
        self.assertEqual(self._entry("beta")["approved"], "2026-01-01")
        log = (server.runtime_dir(self.proj()) / "approvals.log").read_text()
        self.assertEqual(log.count("\tbeta\t"), 1)

    def test_non_latin_project_names_get_distinct_ids(self):
        a, b = server.project_id_for("書簡"), server.project_id_for("Письма")
        self.assertNotEqual(a, b)
        self.assertTrue(a.startswith("p-"))
        self.assertEqual(server.project_id_for("My Notes"), "my_notes")

    def test_clear_session(self):
        # the project session is the unit: clear-session drops its id and active-file marker
        server.save_session(self.proj(), session_id="abc", last_entry="alpha")
        _http("POST", f"{self.base}/api/clear-session", {"project": "t"})
        sess = server.load_session(self.proj())
        self.assertNotIn("session_id", sess)
        self.assertNotIn("last_entry", sess)

    def test_add_project_valid_invalid_dup(self):
        good = self.tmp / "newproj"
        good.mkdir()
        note = "A notes folder for the reading group — flag anything half-finished."
        s, j = _http("POST", f"{self.base}/api/projects/add",
                     {"name": "New One", "root": str(good), "note": note})
        self.assertEqual(s, 200)
        self.assertEqual(j["id"], "new_one")
        self.assertTrue(j.get("ok"))
        self.assertEqual(j["project"]["id"], "new_one")
        self.assertTrue((good / ".kettle" / "runtime" / "queue.json").exists())
        self.assertEqual(server.load_session(j["project"])["founding_note"], note)
        # duplicate id
        s2, _ = _http("POST", f"{self.base}/api/projects/add",
                      {"name": "New One", "root": str(good), "note": note})
        self.assertEqual(s2, 400)
        # nonexistent dir
        s3, _ = _http("POST", f"{self.base}/api/projects/add",
                      {"name": "Ghost", "root": str(self.tmp / "nope"), "note": note})
        self.assertEqual(s3, 400)
        # outside HOME fence
        s4, _ = _http("POST", f"{self.base}/api/projects/add",
                      {"name": "Evil", "root": "/etc", "note": note})
        self.assertEqual(s4, 400)

    def test_add_project_requires_founding_sentence(self):
        # P3: the founding sentence is the one required field at add — a stranger
        # cannot skip past it into an empty-charter desk.
        good = self.tmp / "noteless"
        good.mkdir()
        s, j = _http("POST", f"{self.base}/api/projects/add",
                     {"name": "Noteless", "root": str(good)})
        self.assertEqual(s, 400)
        self.assertIn("founding sentence", j["error"])
        self.assertFalse((good / ".kettle").exists())  # nothing registered on rejection

        s2, blank = _http("POST", f"{self.base}/api/projects/add",
                          {"name": "Noteless", "root": str(good), "note": "   "})
        self.assertEqual(s2, 400)
        self.assertIn("founding sentence", blank["error"])

    def test_interview_status_lifecycle(self):
        # a desk with queue entries AND a charter is founded on read even if session
        # was never written; queue entries alone are not enough (P1).
        (server.desk_dir(self.proj()) / "PROJECT.md").write_text("# T\ncharter\n")
        s, j = _http("GET", f"{self.base}/api/interview?project=t")
        self.assertEqual((s, j["status"]), (200, "founded"))
        server.save_interview(self.proj(), {"session_id": "abc", "status": "interviewing"})
        _, j_pure = _http("GET", f"{self.base}/api/interview?project=t&mutate=0")
        self.assertEqual(j_pure["status"], "interviewing")  # pure read: no heal
        self.assertTrue(j_pure["has_entries"])
        self.assertGreaterEqual(j_pure["entry_count"], 1)
        _, j2 = _http("GET", f"{self.base}/api/interview?project=t")
        # queue entries + charter on disk ⇒ founded (heals stale interviewing on read)
        self.assertEqual(j2["status"], "founded")
        iv = server.load_interview(self.proj())
        self.assertEqual(iv["session_id"], "abc")                    # roundtrip
        server.save_interview(self.proj(), {**iv, "status": "founded"})
        _, j3 = _http("GET", f"{self.base}/api/interview?project=t")
        self.assertEqual(j3["status"], "founded")

    def test_charterless_queue_reports_awaiting_founding(self):
        # P1 regression: content entries alone must not read as founded, and a desk
        # that was incorrectly marked founded before this predicate existed (or whose
        # charter has since gone missing) heals back to interviewing on the next read
        # — the real-world shape of proteus/retinue/reuse-reasoner/incanter-core.
        self.assertFalse((server.desk_dir(self.proj()) / "PROJECT.md").exists())
        self.assertFalse(server.mark_founded_if_filed(self.proj()))
        _, j = _http("GET", f"{self.base}/api/interview?project=t")
        self.assertNotEqual(j["status"], "founded")
        self.assertTrue(j["has_entries"])  # entries are real; the desk still isn't founded

        # stale prior mark (the bug this predicate closes) demotes back to interviewing
        server.save_session(self.proj(), status="founded")
        self.assertFalse(server.mark_founded_if_filed(self.proj()))
        self.assertEqual(server.load_session(self.proj())["status"], "interviewing")

        # writing the charter (real founding) flips it for good
        (server.desk_dir(self.proj()) / "PROJECT.md").write_text("# T\ncharter\n")
        self.assertTrue(server.mark_founded_if_filed(self.proj()))
        self.assertEqual(server.load_session(self.proj())["status"], "founded")

    def test_founded_demotion_ignores_empty_queue(self):
        # a genuinely founded desk (charter on disk) must not be demoted just because
        # its queue is briefly empty between a sweep and its restock.
        (server.desk_dir(self.proj()) / "PROJECT.md").write_text("# T\ncharter\n")
        server.save_session(self.proj(), status="founded")
        self.write_queue([])
        self.assertFalse(server.mark_founded_if_filed(self.proj()))  # no content ⇒ not (re)confirmed
        self.assertEqual(server.load_session(self.proj())["status"], "founded")  # but not demoted

    def test_found_clears_orphan_proposal_entry_once_founded(self):
        # kits/prompts/found.md lets the curator leave the desk-proposal entry behind;
        # a real desk (reuse-reasoner) carries one pointing at a proposal file that no
        # longer exists. mark_founded_if_filed must clear it once the desk is truly
        # founded, regardless of whether the proposal file is still on disk.
        (server.desk_dir(self.proj()) / "PROJECT.md").write_text("# T\ncharter\n")
        entries = server.load_queue(self.proj())["entries"]
        self.write_queue(entries + [{
            "id": server.PROPOSAL_ENTRY_ID,
            "status": "pending",
            "path": str(self.tmp / "long-gone" / server.PROPOSAL_FILENAME),
            "founding_phase": "proposal",
            "title": "Desk Proposal",
        }])
        self.assertTrue(server.mark_founded_if_filed(self.proj()))
        ids = [e["id"] for e in server.load_queue(self.proj())["entries"]]
        self.assertNotIn(server.PROPOSAL_ENTRY_ID, ids)
        self.assertIn("alpha", ids)  # real content survives the strip

    def test_interviewing_persists_while_queue_empty(self):
        server.save_interview(self.proj(), {"session_id": "abc", "status": "interviewing"})
        json.dump({"curated": "awaiting founding curation", "entries": []},
                  open(server.queue_path(self.proj()), "w"))
        _, j = _http("GET", f"{self.base}/api/interview?project=t")
        self.assertEqual(j["status"], "interviewing")

    def test_load_interview_survives_corrupt_file(self):
        server.interview_path(self.proj()).parent.mkdir(parents=True, exist_ok=True)
        server.interview_path(self.proj()).write_text("{nope")
        self.assertEqual(server.load_interview(self.proj()), {})

    def test_interview_and_found_with_stub_claude(self):
        # a stub claude that emits a minimal stream-json conversation
        stub = self.tmp / "claude-stub"
        stub.write_text(
            "#!/bin/sh\n"
            'echo \'{"type":"system","subtype":"init","session_id":"sid-1","model":"stub"}\'\n'
            'echo \'{"type":"assistant","message":{"content":[{"type":"text","text":"hello"}]}}\'\n'
            'echo \'{"type":"result","usage":{"input_tokens":1}}\'\n')
        stub.chmod(0o755)
        saved = server.CLAUDE
        server.CLAUDE = str(stub)
        try:
            # interview turn: streams + persists the session as 'interviewing'
            req = urllib.request.Request(f"{self.base}/api/interview",
                                         data=json.dumps({"project": "t", "message": ""}).encode(),
                                         method="POST")
            for k, v in _auth_headers({"Content-Type": "application/json"}).items():
                req.add_header(k, v)
            with urllib.request.urlopen(req, timeout=10) as r:
                body = r.read().decode()
            self.assertIn("hello", body)
            iv = server.load_interview(self.proj())
            self.assertEqual((iv["session_id"], iv["status"]), ("sid-1", "interviewing"))
            # found: queue already has content entries (setUp) and the charter is on
            # disk (stubbed here — a real found turn would write it), so it must mark
            # 'founded'
            (server.desk_dir(self.proj()) / "PROJECT.md").write_text("# T\ncharter\n")
            req2 = urllib.request.Request(f"{self.base}/api/found",
                                          data=json.dumps({"project": "t"}).encode(),
                                          method="POST")
            for k, v in _auth_headers({"Content-Type": "application/json"}).items():
                req2.add_header(k, v)
            with urllib.request.urlopen(req2, timeout=10) as r2:
                r2.read()
            self.assertEqual(server.load_interview(self.proj())["status"], "founded")
        finally:
            server.CLAUDE = saved

    def test_proposal_entry_does_not_mark_founded(self):
        # desk-proposal alone must not heal to founded (propose phase ≠ founded)
        prop = server.proposal_path(self.proj())
        prop.parent.mkdir(parents=True, exist_ok=True)
        prop.write_text("# Desk Proposal\nidentity here\n")
        self.write_queue([{
            "id": server.PROPOSAL_ENTRY_ID,
            "status": "pending",
            "path": str(prop),
            "founding_phase": "proposal",
            "title": "Desk Proposal",
        }])
        server.save_session(self.proj(), status="proposing", session_id="s-prop")
        self.assertFalse(server.mark_founded_if_filed(self.proj()))
        self.assertEqual(server.load_session(self.proj())["status"], "proposing")
        self.assertTrue(server.desk_is_proposing(self.proj()))
        _, j = _http("GET", f"{self.base}/api/interview?project=t&mutate=0")
        self.assertEqual(j["status"], "proposing")
        self.assertFalse(j["has_entries"])
        self.assertTrue(j["has_proposal"])

    def test_propose_sets_proposing_status(self):
        # empty content queue + stub propose stream ⇒ status proposing
        json.dump({"curated": "awaiting founding curation", "entries": []},
                  open(server.queue_path(self.proj()), "w"))
        server.save_session(self.proj(), status="interviewing", session_id="sid-iv")
        stub = self.tmp / "claude-stub-propose"
        stub.write_text(
            "#!/bin/sh\n"
            'echo \'{"type":"system","subtype":"init","session_id":"sid-prop","model":"stub"}\'\n'
            'echo \'{"type":"assistant","message":{"content":[{"type":"text","text":"proposal draft"}]}}\'\n'
            'echo \'{"type":"result","usage":{"input_tokens":1}}\'\n')
        stub.chmod(0o755)
        # Pre-write proposal so propose() can stamp proposing even if the stub writes nothing
        prop = server.proposal_path(self.proj())
        prop.parent.mkdir(parents=True, exist_ok=True)
        prop.write_text("# Desk Proposal\n")
        saved = server.CLAUDE
        server.CLAUDE = str(stub)
        try:
            s, body = self._post_stream("/api/propose", {"project": "t"})
            self.assertEqual(s, 200)
            self.assertIn("proposal draft", body)
            self.assertEqual(server.load_session(self.proj())["status"], "proposing")
            self.assertFalse(server.desk_is_founded(self.proj()))
        finally:
            server.CLAUDE = saved

    def test_approve_proposal_returns_founding_flag(self):
        prop = server.proposal_path(self.proj())
        prop.parent.mkdir(parents=True, exist_ok=True)
        prop.write_text("# Desk Proposal\nedited by user\n")
        self.write_queue([{
            "id": server.PROPOSAL_ENTRY_ID,
            "status": "pending",
            "path": str(prop),
            "founding_phase": "proposal",
            "ask": "approve to found",
        }])
        server.save_session(self.proj(), status="proposing")
        s, j = _http("POST", f"{self.base}/api/approve",
                     {"project": "t", "id": server.PROPOSAL_ENTRY_ID})
        self.assertEqual(s, 200)
        self.assertTrue(j.get("founding"))
        self.assertEqual(self._entry(server.PROPOSAL_ENTRY_ID)["status"], "approved")

    def test_found_and_bootstrap_idempotent_when_already_founded(self):
        server.save_session(self.proj(), status="founded", session_id="done")
        s, body = self._post_stream("/api/found", {"project": "t"})
        self.assertEqual(s, 200)
        self.assertIn("already founded", body.lower())
        self.assertEqual(server.load_session(self.proj())["status"], "founded")
        s2, body2 = self._post_stream("/api/bootstrap", {"project": "t"})
        self.assertEqual(s2, 200)
        self.assertIn("already founded", body2.lower())
        s3, body3 = self._post_stream("/api/interview", {"project": "t", "message": "hi"})
        self.assertEqual(s3, 200)
        self.assertIn("already founded", body3.lower())

    def test_bootstrap_marks_founded_unsticking_interviewing(self):
        # regression: a desk stuck at 'interviewing' (interrupted founding) must become 'founded'
        # when /api/bootstrap (the quick-found escape hatch) files entries — else it stays trapped.
        stub = self.tmp / "claude-stub-bs"
        stub.write_text(
            "#!/bin/sh\n"
            'echo \'{"type":"system","subtype":"init","session_id":"sid-bs","model":"stub"}\'\n'
            'echo \'{"type":"assistant","message":{"content":[{"type":"text","text":"surveyed"}]}}\'\n'
            'echo \'{"type":"result","usage":{"input_tokens":1}}\'\n')
        stub.chmod(0o755)
        server.save_session(self.proj(), session_id="old-iv", status="interviewing")
        # queue already has entries (setUp); stand in for the charter a real bootstrap
        # turn would write, so mark_founded_if_filed's predicate can be satisfied
        (server.desk_dir(self.proj()) / "PROJECT.md").write_text("# T\ncharter\n")
        saved = server.CLAUDE
        server.CLAUDE = str(stub)
        try:
            # queue + charter on disk, so bootstrap's mark_founded_if_filed must flip it
            req = urllib.request.Request(f"{self.base}/api/bootstrap",
                                         data=json.dumps({"project": "t"}).encode(), method="POST")
            for k, v in _auth_headers({"Content-Type": "application/json"}).items():
                req.add_header(k, v)
            with urllib.request.urlopen(req, timeout=10) as r:
                r.read()
            self.assertEqual(server.load_interview(self.proj())["status"], "founded")
        finally:
            server.CLAUDE = saved

    def test_update_entry_whitelist(self):
        _http("POST", f"{self.base}/api/entry", {"project": "t", "id": "alpha",
              "fields": {"urgency": "low", "brief": "edited brief",
                         "path": "/etc/evil", "id": "hacked", "session_id": "x"}})
        e = self._entry("alpha")
        self.assertEqual(e["urgency"], "low")          # whitelisted field applied
        self.assertEqual(e["brief"], "edited brief")
        self.assertEqual(e["path"], str(self.root / "alpha.md"))  # path NOT clobbered
        self.assertEqual(e["id"], "alpha")             # id NOT clobbered
        self.assertNotIn("session_id", e)              # non-whitelisted ignored
        # empty value clears the field
        _http("POST", f"{self.base}/api/entry", {"project": "t", "id": "alpha",
              "fields": {"unblocks": ""}})
        self.assertNotIn("unblocks", self._entry("alpha"))

    def test_open_link_resolves_and_fences(self):
        (self.root / "modular-skiff-plan.md").write_text("# plan")
        opened = []
        real = server.subprocess.Popen
        server.subprocess.Popen = lambda *a, **k: opened.append(a[0]) or None
        try:
            s, j = _http("POST", f"{self.base}/api/open-link",
                         {"project": "t", "name": "modular-skiff-plan"})
            self.assertEqual(s, 200)
            self.assertTrue(j["ok"])
            self.assertTrue(j["path"].endswith("modular-skiff-plan.md"))
            self.assertEqual(opened[-1][:2], ["open", "-t"])   # default text editor
            s2, j2 = _http("POST", f"{self.base}/api/open-link",
                           {"project": "t", "name": "no-such-note"})
            self.assertEqual(s2, 404)
            self.assertIn("error", j2)
            self.assertNotIn("ok", j2)  # error envelope (no ok:false)
        finally:
            server.subprocess.Popen = real

    def test_admin_report_shape(self):
        s, j = _http("GET", f"{self.base}/api/admin?project=t")
        self.assertEqual(s, 200)
        for key in ("server", "settings", "fleet_panels", "sentinel", "projects"):
            self.assertIn(key, j)
        # Fleet panels default off (brief 10): sentinel/events/watcher are null.
        self.assertFalse(j["fleet_panels"])
        self.assertIsNone(j["sentinel"])
        self.assertIsNone(j.get("events"))
        self.assertIsNone(j.get("watcher"))

    def test_admin_fleet_panels_when_enabled(self):
        server.save_settings({"admin": {"fleet_panels": True}})
        s, j = _http("GET", f"{self.base}/api/admin?project=t")
        self.assertEqual(s, 200)
        self.assertTrue(j["fleet_panels"])
        self.assertIsInstance(j["sentinel"], dict)
        self.assertIn("state", j["sentinel"])
        self.assertIsInstance(j["events"], list)

    def test_unknown_project_400(self):
        s, _ = _http("GET", f"{self.base}/api/queue?project=bogus")
        self.assertEqual(s, 400)

    def test_missing_project_400(self):
        s, j = _http("GET", f"{self.base}/api/queue")
        self.assertEqual(s, 400)
        self.assertIn("missing project", j["error"])
        s2, j2 = _http("POST", f"{self.base}/api/approve", {"id": "alpha"})
        self.assertEqual(s2, 400)
        self.assertIn("missing project", j2["error"])

    def test_full_founding_review_and_close_lifecycle(self):
        life_root = self.tmp / "lifecycle"
        life_root.mkdir()
        s, added = _http("POST", f"{self.base}/api/projects/add", {
            "name": "Lifecycle", "root": str(life_root), "kit": "code",
            "note": "A lifecycle fixture — review drafts as they land.",
        })
        self.assertEqual((s, added["id"]), (200, "lifecycle"))
        proj = server.get_project("lifecycle")
        calls = []
        real_popen = server.subprocess.Popen

        class StubCurator:
            def __init__(self, argv):
                call = len(calls)
                calls.append(list(argv))
                if call == 1:  # finish interview -> proposal entry
                    proposal = server.proposal_path(proj)
                    proposal.write_text("# Desk Proposal\nUser intent.\n")
                    server.atomic_write(server.queue_path(proj), json.dumps({
                        "curated": "proposal ready",
                        "entries": [{
                            "id": server.PROPOSAL_ENTRY_ID,
                            "title": "Desk Proposal",
                            "path": str(proposal),
                            "status": "pending",
                            "founding_phase": "proposal",
                            "ask": "Approve to found",
                        }],
                    }, indent=2))
                elif call == 2:  # approved proposal -> durable desk + first content batch
                    desk = server.desk_dir(proj)
                    for name, text in {
                        "PROJECT.md": "# Lifecycle charter\n",
                        "MEMORY.md": "# Memory\n- User intent wins.\n",
                        "FAMILIARITY.md": "# Familiarity\n- draft.md is first.\n",
                        "SWEEP-ACTIONS.md": "# Sweep actions\n- Ordinary close.\n",
                    }.items():
                        (desk / name).write_text(text)
                    draft = life_root / "draft.md"
                    draft.write_text("first draft\n")
                    server.atomic_write(server.queue_path(proj), json.dumps({
                        "curated": "opening batch",
                        "entries": [{
                            "id": "first",
                            "title": "Review the first draft",
                            "path": str(draft),
                            "status": "pending",
                            "urgency": "high",
                            "ask": "Approve the opening draft",
                        }],
                    }, indent=2))
                lines = [
                    self._init("lifecycle-sid"),
                    self._say(f"stub turn {call}"),
                    self._result(),
                ]
                self.stdout = iter(line + "\n" for line in lines)
                self.returncode = 0

            @staticmethod
            def _init(sid):
                return EndpointTests._init(sid=sid)

            @staticmethod
            def _say(text):
                return EndpointTests._say(text)

            @staticmethod
            def _result():
                return EndpointTests._result()

            def wait(self, timeout=None):
                return self.returncode

            def poll(self):
                return self.returncode

            def kill(self):
                self.returncode = -9

        def fake_popen(argv, *args, **kwargs):
            return StubCurator(argv)

        server.subprocess.Popen = fake_popen
        self.addCleanup(lambda: setattr(server.subprocess, "Popen", real_popen))

        # register -> interview -> propose
        s1, interview = self._post_stream(
            "/api/interview", {"project": "lifecycle", "message": "Begin"})
        self.assertEqual(s1, 200)
        self.assertEqual(self._events(interview)[-1]["t"], "done")
        self.assertEqual(server.load_session(proj)["status"], "interviewing")

        s2, proposed = self._post_stream("/api/propose", {"project": "lifecycle"})
        self.assertEqual(s2, 200)
        self.assertEqual(self._events(proposed)[-1]["t"], "done")
        proposal_entry = server.find_entry(
            server.load_queue(proj), server.PROPOSAL_ENTRY_ID)
        self.assertEqual(proposal_entry["status"], "pending")
        self.assertEqual(server.load_session(proj)["status"], "proposing")

        # approve proposal -> found -> durable desk and content queue
        s3, approved_proposal = _http("POST", f"{self.base}/api/approve", {
            "project": "lifecycle", "id": server.PROPOSAL_ENTRY_ID,
        })
        self.assertEqual((s3, approved_proposal["founding"]), (200, True))
        s4, found = self._post_stream("/api/found", {"project": "lifecycle"})
        self.assertEqual(s4, 200)
        self.assertEqual(self._events(found)[-1]["t"], "done")
        self.assertEqual(server.load_session(proj)["status"], "founded")
        for name in ("PROJECT.md", "MEMORY.md", "FAMILIARITY.md", "SWEEP-ACTIONS.md"):
            self.assertTrue((server.desk_dir(proj) / name).is_file())

        # queue read snapshots the content -> chat -> approve -> sweep performs quiet CLOSE
        sq, queue = _http("GET", f"{self.base}/api/queue?project=lifecycle")
        self.assertEqual((sq, [e["id"] for e in queue["entries"]]), (200, ["first"]))
        sc, chat = self._post_stream("/api/chat", {
            "project": "lifecycle", "id": "first", "message": "Review it",
        })
        self.assertEqual(sc, 200)
        self.assertEqual(self._events(chat)[-1]["t"], "done")
        sa, _ = _http("POST", f"{self.base}/api/approve", {
            "project": "lifecycle", "id": "first",
        })
        self.assertEqual(sa, 200)
        ss, swept = self._post_stream("/api/sweep", {"project": "lifecycle"})
        self.assertEqual(ss, 200)
        self.assertEqual(self._events(swept)[-1]["t"], "done")
        self.assertEqual(server.load_queue(proj)["entries"], [])
        self.assertTrue(any((server.desk_dir(proj) / "archive").glob("*-batch.json")))
        self.assertTrue(any((server.runtime_dir(proj) / "sessions").glob("*-session.md")))
        self.assertEqual(len(calls), 5)

    # ---- streaming harness: a fake `claude` emitting stream-json ----
    def _stub_claude(self, *lines, exit_code=0):
        """Install a fake `claude` that echoes the given stream-json lines, then exits."""
        body = "#!/bin/sh\n"
        for ln in lines:
            body += "echo '" + ln.replace("'", "'\\''") + "'\n"
        body += f"exit {exit_code}\n"
        stub = self.tmp / "claude-stub"
        stub.write_text(body)
        stub.chmod(0o755)
        saved = server.CLAUDE
        server.CLAUDE = str(stub)
        self.addCleanup(lambda: setattr(server, "CLAUDE", saved))

    def _stub_curator_python(self, source, name="curator-python-stub"):
        """Install a Python curator stub for timing/process-lifecycle cases."""
        stub = self.tmp / name
        stub.write_text(f"#!{sys.executable}\n" + source)
        stub.chmod(0o755)
        saved = server.CLAUDE
        server.CLAUDE = str(stub)
        self.addCleanup(lambda: setattr(server, "CLAUDE", saved))
        return stub

    @staticmethod
    def _init(sid="sid-x", model="stub"):
        return json.dumps({"type": "system", "subtype": "init",
                           "session_id": sid, "model": model})

    @staticmethod
    def _say(text):
        return json.dumps({"type": "assistant",
                           "message": {"content": [{"type": "text", "text": text}]}})

    @staticmethod
    def _result():
        return json.dumps({"type": "result", "usage": {"input_tokens": 1}})

    def _post_stream(self, path, body):
        """POST and read the whole ndjson stream back as (status, text)."""
        req = urllib.request.Request(f"{self.base}{path}",
                                     data=json.dumps(body).encode(), method="POST")
        for k, v in _auth_headers({"Content-Type": "application/json"}).items():
            req.add_header(k, v)
        with urllib.request.urlopen(req, timeout=10) as r:
            status, text = r.status, r.read().decode()
        events = self._events(text)
        self.assertTrue(events, f"{path} returned an empty stream")
        self.assertEqual(events[-1].get("t"), "done",
                         f"{path} did not end with terminal done: {events[-1:]}")
        return status, text

    @staticmethod
    def _events(text):
        return [json.loads(l) for l in text.splitlines() if l.strip()]

    def test_chat_streams_text_and_persists_session(self):
        self._stub_claude(self._init(sid="sid-9"), self._say("howdy"), self._result())
        s, body = self._post_stream("/api/chat",
                                    {"project": "t", "id": "alpha", "message": "hi"})
        self.assertEqual(s, 200)
        ev = self._events(body)
        self.assertTrue(any(e.get("t") == "text" and e.get("s") == "howdy" for e in ev))
        self.assertTrue(any(e.get("t") == "done" for e in ev))
        sess = server.load_session(self.proj())
        self.assertEqual(sess["session_id"], "sid-9")   # persisted to the PROJECT session
        self.assertEqual(sess["last_entry"], "alpha")   # active-file marker recorded

    def test_chat_streams_with_stub_grok(self):
        """Grok provider: same NDJSON to the client; dialect differs only in argv."""
        stub = self.tmp / "grok-stub"
        stub.write_text(
            "#!/bin/sh\n"
            f"echo '{self._init(sid='sid-g')}'\n"
            f"echo '{self._say('from grok')}'\n"
            f"echo '{self._result()}'\n"
        )
        stub.chmod(0o755)
        server.save_settings({
            "curator": {
                "provider": "grok",
                "command": str(stub),
                "models": {
                    "setup": "grok-4.5",
                    "chat": "grok-4.5",
                    "glance": "grok-composer-2.5-fast",
                },
            },
        })
        s, body = self._post_stream("/api/chat",
                                    {"project": "t", "id": "alpha", "message": "hi"})
        self.assertEqual(s, 200)
        ev = self._events(body)
        self.assertTrue(any(e.get("t") == "text" and e.get("s") == "from grok" for e in ev))
        self.assertTrue(any(e.get("t") == "done" for e in ev))
        self.assertEqual(server.load_session(self.proj())["session_id"], "sid-g")

    def test_chat_skips_resume_when_provider_mismatches(self):
        # A Claude-tagged (or legacy) session must not be --resume'd under Grok —
        # that was the "curator exited 1" / session 404 failure mode.
        server.save_session(self.proj(), session_id="claude-only-sid", provider="claude",
                            status="founded", last_entry="alpha")
        stub = self.tmp / "grok-fresh"
        stub.write_text(
            "#!/bin/sh\n"
            f"echo '{self._init(sid='sid-fresh')}'\n"
            f"echo '{self._say('fresh')}'\n"
            f"echo '{self._result()}'\n"
        )
        stub.chmod(0o755)
        server.save_settings({
            "curator": {
                "provider": "grok",
                "command": str(stub),
                "models": {
                    "setup": "grok-4.5",
                    "chat": "grok-4.5",
                    "glance": "grok-composer-2.5-fast",
                },
            },
        })
        cmds = self._capture_cmds()
        # Prefer capture over stub file since _capture_cmds replaces Popen entirely
        s, body = self._post_stream("/api/chat",
                                    {"project": "t", "id": "alpha", "message": "hi"})
        self.assertEqual(s, 200)
        self.assertTrue(cmds)
        self.assertNotIn("--resume", cmds[-1])
        self.assertNotIn("claude-only-sid", cmds[-1])

    def test_sweep_skips_resume_when_grok_model_mismatches(self):
        # Chat left a composer/cursor session; sweep wants grok-4.5 → must not --resume
        # (MODEL_SWITCH_INCOMPATIBLE_AGENT).
        server.save_session(
            self.proj(), session_id="composer-sid", provider="grok",
            model="grok-composer-2.5-fast", status="founded",
        )
        server.save_settings({
            "curator": {
                "provider": "grok",
                "command": "grok",
                "models": {
                    "setup": "grok-4.5",
                    "chat": "grok-composer-2.5-fast",
                    "glance": "grok-composer-2.5-fast",
                },
            },
        })
        cmds = self._capture_cmds()
        self._post_stream("/api/sweep", {"project": "t"})
        self.assertTrue(cmds)
        self.assertNotIn("--resume", cmds[-1])
        self.assertNotIn("composer-sid", cmds[-1])
        self.assertIn("--model", cmds[-1])
        self.assertEqual(cmds[-1][cmds[-1].index("--model") + 1], "grok-4.5")

    def test_build_turn_cmd_grok_dialect(self):
        server.save_settings({
            "curator": {
                "provider": "grok",
                "command": "grok",
                "models": {"setup": "grok-4.5", "chat": "grok-4.5", "glance": "fast"},
            },
        })
        cmd = server.build_turn_cmd(
            "hello", task="chat", system_append="rules here",
            name="Desk", tools_tier="chat",
        )
        self.assertEqual(cmd[0], server.agent_bin())
        self.assertIn("streaming-json", cmd)
        self.assertNotIn("--verbose", cmd)
        self.assertIn("--rules", cmd)
        self.assertNotIn("--append-system-prompt", cmd)
        self.assertNotIn("--name", cmd)  # Grok has no session-name flag
        self.assertIn("--allow", cmd)
        self.assertNotIn("--allowedTools", cmd)

    def test_build_turn_cmd_gemini_dialect(self):
        server.save_settings({
            "curator": {
                "provider": "gemini",
                "command": "gemini",
                "models": {"setup": "gemini-2.5-pro", "chat": "gemini-2.5-pro",
                           "glance": "gemini-2.5-flash"},
            },
        })
        cmd = server.build_turn_cmd(
            "hello", task="chat", system_append="be brief",
            name="Desk", tools_tier="chat",
        )
        self.assertIn("stream-json", cmd)
        self.assertNotIn("--append-system-prompt", cmd)
        self.assertTrue(any("be brief" in str(a) for a in cmd))  # prompt-prefixed
        self.assertIn("--approval-mode", cmd)
        self.assertIn("auto_edit", cmd)
        self.assertNotIn("--name", cmd)

    def test_build_turn_cmd_chatgpt_dialect(self):
        server.save_settings({
            "curator": {
                "provider": "chatgpt",
                "command": "codex",
                "models": {"setup": "gpt-5.1", "chat": "gpt-5.1", "glance": "gpt-5-mini"},
            },
        })
        cmd = server.build_turn_cmd("hello", task="chat", tools_tier="chat")
        self.assertEqual(cmd[0], server.agent_bin())
        self.assertIn("exec", cmd)
        self.assertIn("--json", cmd)
        self.assertIn("--sandbox", cmd)
        self.assertIn("workspace-write", cmd)
        self.assertEqual(cmd[-1], "hello")

    def test_chat_streams_with_stub_gemini(self):
        stub = self.tmp / "gemini-stub"
        init = json.dumps({"type": "init", "session_id": "sid-gem", "model": "flash"})
        msg = json.dumps({"type": "message", "role": "assistant", "content": "gem hi"})
        done = json.dumps({"type": "result", "stats": {"input_tokens": 1}})
        stub.write_text(
            "#!/bin/sh\n"
            f"echo '{init}'\n"
            f"echo '{msg}'\n"
            f"echo '{done}'\n"
        )
        stub.chmod(0o755)
        server.save_settings({
            "curator": {
                "provider": "gemini",
                "command": str(stub),
                "models": {
                    "setup": "gemini-2.5-pro",
                    "chat": "gemini-2.5-pro",
                    "glance": "gemini-2.5-flash",
                },
            },
        })
        s, body = self._post_stream("/api/chat",
                                    {"project": "t", "id": "alpha", "message": "hi"})
        self.assertEqual(s, 200)
        ev = self._events(body)
        self.assertTrue(any(e.get("t") == "text" and e.get("s") == "gem hi" for e in ev))
        self.assertEqual(server.load_session(self.proj())["session_id"], "sid-gem")

    def _capture_cmds(self):
        """Patch subprocess.Popen so each spawned `claude` argv is recorded AND a minimal
        stream-json conversation is replayed back (so run_claude completes normally).
        Returns the list that collects argv lists."""
        cmds = []
        real = server.subprocess.Popen

        class _FakeProc:
            def __init__(self, argv):
                lines = [self._init(sid="sid-proj"), self._say("ok"), self._result()]
                self.stdout = iter([l + "\n" for l in lines])
                self.returncode = 0

            @staticmethod
            def _init(sid, model="stub"):
                return json.dumps({"type": "system", "subtype": "init",
                                   "session_id": sid, "model": model})

            @staticmethod
            def _say(t):
                return json.dumps({"type": "assistant",
                                   "message": {"content": [{"type": "text", "text": t}]}})

            @staticmethod
            def _result():
                return json.dumps({"type": "result", "usage": {"input_tokens": 1}})

            def wait(self, timeout=None):
                return 0

            def poll(self):
                return self.returncode

            def kill(self):
                self.returncode = -9

        def fake_popen(argv, *a, **k):
            cmds.append(list(argv))
            return _FakeProc(argv)

        server.subprocess.Popen = fake_popen
        self.addCleanup(lambda: setattr(server.subprocess, "Popen", real))
        return cmds

    def test_founding_prompt_loaded_from_product_prompt_file(self):
        cmds = self._capture_cmds()
        self._post_stream("/api/interview", {"project": "t", "message": "begin"})
        cmd = cmds[-1]
        role = cmd[cmd.index("--append-system-prompt") + 1]
        self.assertIn("a standing second reader, arriving for the first time", role)

    def test_founding_sentence_quoted_first_in_interview(self):
        # P3: the user's required founding sentence comes before the deterministic
        # survey dump, not tacked on at the end.
        sentence = "A batch of scanned letters — flag anything illegible or undated."
        server.save_session(self.proj(), founding_note=sentence)
        cmds = self._capture_cmds()
        self._post_stream("/api/interview", {"project": "t", "message": "begin"})
        role = cmds[-1][cmds[-1].index("--append-system-prompt") + 1]
        self.assertIn(sentence, role)
        # "CORE SURVEY" also appears in the role template's own opening line — anchor on
        # the survey block's actual heading (from survey.as_prompt_block), not that phrase.
        self.assertLess(role.index(sentence), role.index("CORE SURVEY (authoritative"))

    def test_founding_sentence_quoted_first_in_propose(self):
        sentence = "Slides for the fall course — check every claim against the syllabus."
        server.save_session(self.proj(), founding_note=sentence)
        cmds = self._capture_cmds()
        self._post_stream("/api/propose", {"project": "t"})
        prompt = cmds[-1][cmds[-1].index("-p") + 1]
        self.assertIn(sentence, prompt)
        self.assertIn("What This Project Is", prompt)
        self.assertLess(prompt.index(sentence), prompt.index("Write ONE file"))

    def test_founding_sentence_quoted_first_in_found(self):
        sentence = "Household finances — nothing leaves the desk without my say."
        server.save_session(self.proj(), founding_note=sentence)
        cmds = self._capture_cmds()
        self._post_stream("/api/found", {"project": "t"})
        prompt = cmds[-1][cmds[-1].index("-p") + 1]
        self.assertIn(sentence, prompt)
        self.assertIn("Your Words", prompt)
        self.assertLess(prompt.index(sentence), prompt.index("THE CHARTER"))

    def test_bootstrap_route_quotes_the_founding_sentence_first(self):
        """Every founding entry point shares build_found_prompt: /api/bootstrap used
        to drop the sentence the charter must open with."""
        sentence = "Field notes — keep my spelling of place names."
        server.save_session(self.proj(), founding_note=sentence)
        cmds = self._capture_cmds()
        self._post_stream("/api/bootstrap", {"project": "t"})
        prompt = cmds[-1][cmds[-1].index("-p") + 1]
        self.assertTrue(prompt.startswith("THE USER'S FOUNDING SENTENCE"))
        self.assertIn(sentence, prompt)
        self.assertIn("Your Words", prompt)
        self.assertIn("block above", prompt)

    def test_interview_does_not_resume_a_chat_session(self):
        """A chat before the interview opened a session with no founding role, survey
        or sentence; the interview must start fresh and carry all three."""
        server.save_session(self.proj(), session_id="sid-chat", founding_note="Why this.")
        cmds = self._capture_cmds()
        self._post_stream("/api/interview", {"project": "t", "message": "begin"})
        c = cmds[-1]
        self.assertNotIn("--resume", c)
        role = c[c.index("--append-system-prompt") + 1]
        self.assertIn("Why this.", role)

    def test_interview_resumes_its_own_session(self):
        server.save_session(self.proj(), session_id="sid-iv", status="interviewing")
        cmds = self._capture_cmds()
        self._post_stream("/api/interview", {"project": "t", "message": "more"})
        c = cmds[-1]
        self.assertEqual(c[c.index("--resume") + 1], "sid-iv")

    def test_propose_never_founds_the_desk(self):
        """Propose holds write tools; a curator that writes a charter and content
        entries anyway must not found the desk before the user approves."""
        server.save_session(self.proj(), status="proposing")
        (server.desk_dir(self.proj()) / "PROJECT.md").write_text("# charter\n")
        self.assertFalse(server.mark_founded_if_filed(self.proj()))
        self.assertTrue(server.mark_founded_if_filed(self.proj(), founding_step=True))

    def test_failed_found_keeps_the_proposal_openable(self):
        desk = server.desk_dir(self.proj())
        server.mutate_queue(self.proj(), lambda q: q.__setitem__("entries", []))
        (desk / "DESK-PROPOSAL.md").write_text("# Desk Proposal\n")
        server.save_session(self.proj(), status="proposing")
        self._stub_claude(self._init(), self._say("oops"), exit_code=1)
        self._post_stream("/api/found", {"project": "t"})
        entries = server.load_queue(self.proj())["entries"]
        self.assertEqual([e["id"] for e in entries], ["desk-proposal"])
        _, j = _http("GET", f"{self.base}/api/interview?project=t")
        self.assertFalse(j["founded"])
        self.assertTrue(j["has_proposal"])

    def test_chat_uses_one_project_session_named_for_project(self):
        # first chat turn on a project CREATES the named project session (no --resume),
        # injects the file's context block, and names it kettle-test
        cmds = self._capture_cmds()
        self._post_stream("/api/chat", {"project": "t", "id": "alpha", "message": "hi"})
        c1 = cmds[-1]
        self.assertIn("--name", c1)
        self.assertEqual(c1[c1.index("--name") + 1], "kettle-test")
        self.assertNotIn("--resume", c1)
        prompt = c1[c1.index("-p") + 1]
        self.assertIn("[Active file:", prompt)         # context injected on first turn
        self.assertEqual(server.load_session(self.proj())["session_id"], "sid-proj")

    def test_chat_reinjects_context_only_when_file_changes(self):
        cmds = self._capture_cmds()
        # turn 1 on alpha: context injected, session created
        self._post_stream("/api/chat", {"project": "t", "id": "alpha", "message": "one"})
        # turn 2 STILL on alpha: resumes, NO context re-injection
        self._post_stream("/api/chat", {"project": "t", "id": "alpha", "message": "two"})
        c2 = cmds[-1]
        self.assertIn("--resume", c2)                  # same project session resumed
        self.assertNotIn("[Active file:", c2[c2.index("-p") + 1])
        # turn 3 SWITCHES to beta: resumes the same session AND announces the new file
        self._post_stream("/api/chat", {"project": "t", "id": "beta", "message": "three"})
        c3 = cmds[-1]
        self.assertIn("--resume", c3)
        self.assertIn("[Active file:", c3[c3.index("-p") + 1])
        self.assertIn("beta.md", c3[c3.index("-p") + 1])
        self.assertEqual(server.load_session(self.proj())["last_entry"], "beta")

    def test_chat_works_without_an_entry(self):
        # the deadlock fix: a project-level turn (no file selected — e.g. answering a
        # question the sweep raised) must NOT crash; it resumes the project session and
        # injects no active-file context block.
        cmds = self._capture_cmds()
        server.save_session(self.proj(), session_id="sid-live", name="kettle-test")
        s, body = self._post_stream("/api/chat",
                                    {"project": "t", "message": "answering the sweep"})
        self.assertEqual(s, 200)
        c = cmds[-1]
        self.assertIn("--resume", c)                              # same project session
        self.assertEqual(c[c.index("--resume") + 1], "sid-live")
        self.assertNotIn("[Active file:", c[c.index("-p") + 1])   # no file-context block
        self.assertIsNone(server.load_session(self.proj()).get("last_entry"))  # untouched

    def test_chat_no_entry_bootstraps_when_no_session(self):
        # project-level first turn with no session yet: creates the named session with a
        # placeholder file, never raising on the missing entry.
        cmds = self._capture_cmds()
        s, _ = self._post_stream("/api/chat", {"project": "t", "id": None, "message": "hi"})
        self.assertEqual(s, 200)
        c = cmds[-1]
        self.assertIn("--name", c)
        self.assertNotIn("--resume", c)

    def test_sweep_resumes_the_project_session(self):
        cmds = self._capture_cmds()
        # seed a project session as if chat had run
        server.save_session(self.proj(), session_id="sid-live", name="kettle-test")
        self._post_stream("/api/sweep", {"project": "t"})
        c = cmds[-1]
        self.assertIn("--resume", c)
        self.assertEqual(c[c.index("--resume") + 1], "sid-live")  # continuity, not fresh

    def test_sweep_runs_fresh_when_no_session_yet(self):
        cmds = self._capture_cmds()
        self._post_stream("/api/sweep", {"project": "t"})
        c = cmds[-1]
        self.assertNotIn("--resume", c)
        self.assertIn("--name", c)                                # named, fresh
        self.assertEqual(server.load_session(self.proj())["session_id"], "sid-proj")  # persisted

    def test_glance_endpoint_removed(self):
        s, body = _http(
            "POST", f"{self.base}/api/glance",
            {"project": "t", "brief": "b", "path": str(self.root / "alpha.md")})
        self.assertEqual(s, 404)
        self.assertIn("error", body)

    def test_sweep_streams_with_null_ledger(self):
        # regression: a project whose `ledger` is None must not crash sweep()
        self._stub_claude(self._init(), self._say("swept"), self._result())
        s, body = self._post_stream("/api/sweep", {"project": "t"})
        self.assertEqual(s, 200)
        self.assertIn("swept", body)

    def test_failed_sweep_leaves_a_failed_beacon_and_keeps_comments_binding(self):
        server.comments_log_path(self.proj()).write_text("2026-06-29\talpha\trename Foo\n")
        self._stub_claude(self._init(), self._say("half done"), exit_code=1)
        s, body = self._post_stream("/api/sweep", {"project": "t"})
        self.assertEqual(s, 200)
        beacon = sweepkit.read_sweep_health(self.proj())
        self.assertEqual(beacon["state"], "failed")
        self.assertEqual(beacon["exit"], 1)
        self.assertTrue(beacon["error"])
        # the curator never finished, so the user's direction still stands
        self.assertIn("alpha", server.parse_comments_log(server.comments_log_path(self.proj())))

    def test_successful_sweep_retires_the_comments_it_carried(self):
        server.comments_log_path(self.proj()).write_text("2026-06-29\talpha\trename Foo\n")
        self._stub_claude(self._init(), self._say("swept"), self._result())
        self._post_stream("/api/sweep", {"project": "t"})
        self.assertEqual(sweepkit.read_sweep_health(self.proj())["state"], "done")
        log = server.comments_log_path(self.proj())
        self.assertNotIn("alpha", server.parse_comments_log(log))
        self.assertIn("rename Foo", log.read_text())  # append-only: the line is still there

    def test_empty_queue_after_a_failed_sweep_restocks_instead_of_idling(self):
        """A mechanical close archives before the accrue curator runs; if that curator
        dies, the empty quiet queue must not read as 'nothing to sweep' forever."""
        server.mutate_queue(self.proj(), lambda q: q.__setitem__("entries", []))
        sweepkit.write_sweep_health(self.proj(), state="failed", phase="accrue",
                                    error="client disconnected; curator stopped")
        cmds = self._capture_cmds()
        s, body = self._post_stream("/api/sweep", {"project": "t"})
        self.assertEqual(s, 200)
        self.assertNotIn("Nothing to sweep", body)
        self.assertTrue(cmds, "expected a restock curator turn")
        prompt = cmds[-1][cmds[-1].index("-p") + 1]
        self.assertIn("ACCRUE + RESTOCK only", prompt)
        self.assertIn("resume_interrupted_sweep", prompt)
        self.assertEqual(sweepkit.read_sweep_health(self.proj())["state"], "done")

    def test_empty_queue_after_a_clean_sweep_is_idle(self):
        server.mutate_queue(self.proj(), lambda q: q.__setitem__("entries", []))
        sweepkit.write_sweep_health(self.proj(), state="done", phase="accrue")
        cmds = self._capture_cmds()
        s, body = self._post_stream("/api/sweep", {"project": "t"})
        self.assertIn("Nothing to sweep", body)
        self.assertEqual(cmds, [])

    def test_stale_failure_on_an_idle_inbox_desk_is_reported_once(self):
        proj = self.proj()
        server.mutate_queue(proj, lambda q: q.__setitem__("entries", []))
        sweepkit.write_sweep_health(proj, state="failed", error="boom")
        with mock.patch.object(sweepkit, "assess_close", return_value={
                "fully_idle": True, "needs_accrue": False, "can_mechanical_close": False}):
            _, first = self._post_stream("/api/sweep", {"project": "t"})
            _, second = self._post_stream("/api/sweep", {"project": "t"})
        self.assertIn("last sweep did not finish: boom", first)
        self.assertNotIn("did not finish", second)
        self.assertEqual(sweepkit.read_sweep_health(proj)["state"], "idle")

    def test_comment_typed_while_the_sweep_prompt_builds_is_not_retired(self):
        proj = self.proj()
        log = server.comments_log_path(proj)
        log.write_text("2026-06-29\talpha\tseen note\n")
        real_orientation = server.project_orientation

        def orientation_with_late_comment(p):
            with log.open("a") as f:
                f.write("2026-06-29\talpha\tlate note\n")
            return real_orientation(p)

        self._stub_claude(self._init(), self._say("swept"), self._result())
        with mock.patch.object(server, "project_orientation", orientation_with_late_comment):
            self._post_stream("/api/sweep", {"project": "t"})
        left = server.parse_comments_log(log)
        self.assertEqual([r["text"] for r in left.get("alpha", [])], ["late note"])

    def test_second_sweep_on_the_same_desk_is_refused_while_one_runs(self):
        cmds = self._capture_cmds()
        with server.SWEEPS_LOCK:
            server.SWEEPS_IN_FLIGHT.add("t")
        self.addCleanup(lambda: server.SWEEPS_IN_FLIGHT.discard("t"))
        s, body = self._post_stream("/api/sweep", {"project": "t"})
        self.assertIn("already running", body)
        self.assertEqual(cmds, [])

    def test_clearing_a_comment_retracts_its_history(self):
        _http("POST", f"{self.base}/api/comment", {"project": "t", "id": "alpha", "text": "rename Foo"})
        _http("POST", f"{self.base}/api/comment", {"project": "t", "id": "alpha", "text": ""})
        log = server.comments_log_path(self.proj())
        self.assertNotIn("alpha", server.parse_comments_log(log))
        cmds = self._capture_cmds()
        self._post_stream("/api/sweep", {"project": "t"})
        prompt = cmds[-1][cmds[-1].index("-p") + 1]
        self.assertNotIn("rename Foo", prompt)

    def test_sweep_injects_intake_outbound_for_inbox_project(self):
        # an inbox project (intake block) gets the outbound-staging instruction with its path
        server.PROJECTS_PATH.write_text(json.dumps({"projects": [{
            "id": "t", "name": "Test", "root": str(self.root), "ledger": None,
            "kit": "inbox", "intake": {"watch": ".", "outbound": "outbox"},
            "rework_agents": [{"id": "curator", "name": "the Test curator"}],
        }]}))
        cmds = self._capture_cmds()
        self._post_stream("/api/sweep", {"project": "t"})
        prompt = cmds[-1][cmds[-1].index("-p") + 1]
        self.assertIn("INTAKE OUTBOUND", prompt)
        self.assertIn(str(self.root / "outbox"), prompt)        # the resolved outbound path
        self.assertIn("NEVER transmit", prompt)                 # staging only, localhost fence
        self.assertIn("review-program.md", prompt)              # restock override: intake refills, not the program
        self.assertIn("pending entries", prompt)     # pending entries survive the sweep

    def test_sweep_omits_intake_outbound_for_normal_project(self):
        # a project with no intake block must not carry the inbox-only instruction
        cmds = self._capture_cmds()
        self._post_stream("/api/sweep", {"project": "t"})
        self.assertNotIn("INTAKE OUTBOUND", cmds[-1][cmds[-1].index("-p") + 1])

    def test_sweep_prompt_precomputes_diffs_and_asks_for_familiarity(self):
        desk = self.root / ".kettle"
        (desk / "FAMILIARITY.md").write_text("## Map\n- alpha.md is the lead essay")
        server.ensure_snapshots(self.proj(), server.load_queue(self.proj()))
        cmds = self._capture_cmds()
        self._post_stream("/api/sweep", {"project": "t"})
        prompt = cmds[-1][cmds[-1].index("-p") + 1]
        self.assertIn("PRECOMPUTED DIFFS", prompt)
        self.assertIn("DESIGN OF THIS PASS", prompt)
        self.assertIn("ACCRUE", prompt)
        self.assertIn("FAMILIARITY.md", prompt)
        self.assertIn("alpha.md is the lead essay", prompt)  # orientation injects familiarity
        self.assertIn("(identical to snapshot)", prompt)

    def test_sweep_prompt_includes_default_verbosity(self):
        cmds = self._capture_cmds()
        self._post_stream("/api/sweep", {"project": "t"})
        prompt = cmds[-1][cmds[-1].index("-p") + 1]
        self.assertIn("LIVE REPORTING — normal", prompt)

    def test_sweep_verbosity_setting_and_request_override(self):
        server.save_settings({"sweepVerbosity": "quiet"})
        cmds = self._capture_cmds()
        self._post_stream("/api/sweep", {"project": "t"})
        prompt = cmds[-1][cmds[-1].index("-p") + 1]
        self.assertIn("LIVE REPORTING — quiet", prompt)
        self._post_stream("/api/sweep", {"project": "t", "verbosity": "verbose"})
        prompt2 = cmds[-1][cmds[-1].index("-p") + 1]
        self.assertIn("LIVE REPORTING — verbose", prompt2)

    def test_normalize_sweep_verbosity(self):
        self.assertEqual(server.normalize_sweep_verbosity(None), "normal")
        self.assertEqual(server.normalize_sweep_verbosity("terse"), "quiet")
        self.assertEqual(server.normalize_sweep_verbosity("VERBOSE"), "verbose")
        self.assertEqual(server.normalize_sweep_verbosity("nope"), "normal")

    def test_run_claude_skips_malformed_ndjson(self):
        self._stub_claude(self._init(), "this is not json",
                          self._say("survived"), self._result())
        s, body = self._post_stream("/api/chat",
                                    {"project": "t", "id": "alpha", "message": "x"})
        self.assertEqual(s, 200)
        self.assertIn("survived", body)           # stream continued past the garbage
        self.assertNotIn("not json", body)        # the bad line never became an event

    def test_run_claude_surfaces_nonzero_exit(self):
        self._stub_claude(self._init(), self._say("partial"), exit_code=3)
        s, body = self._post_stream("/api/chat",
                                    {"project": "t", "id": "alpha", "message": "x"})
        self.assertEqual(s, 200)
        self.assertIn("partial", body)            # what streamed before the failure survives
        events = self._events(body)
        self.assertEqual([e["t"] for e in events[-2:]], ["error", "done"])
        self.assertIn("curator exited 3", events[-2]["s"])

    def test_hung_curator_is_killed_after_idle_timeout(self):
        pidfile = self.tmp / "hung-curator.pid"
        # Headroom over interpreter cold-start: the stub writes its pidfile as
        # its first line, and the idle-timeout kill must not beat that write.
        # A 0.5s timeout raced the pidfile under a slow interpreter (anaconda
        # python in the full-suite run) — see LAB-61.
        server.save_settings({"curator": {"idle_timeout_s": 2.0}})
        self._stub_curator_python(
            "import os, time\n"
            f"open({str(pidfile)!r}, 'w').write(str(os.getpid()))\n"
            "time.sleep(5)\n"
            "print('late output', flush=True)\n",
            name="hung-curator",
        )
        s, body = self._post_stream(
            "/api/chat", {"project": "t", "id": "alpha", "message": "hang"})
        self.assertEqual(s, 200)
        events = self._events(body)
        self.assertEqual([e["t"] for e in events], ["error", "done"])
        self.assertIn("idle timeout", events[0]["s"])
        # Defensive: the pidfile is the stub's first write, but poll briefly so
        # a boundary race can never crash the read with FileNotFoundError.
        deadline = time.monotonic() + 2.0
        while not pidfile.exists() and time.monotonic() < deadline:
            time.sleep(0.02)
        pid = int(pidfile.read_text())
        with self.assertRaises(ProcessLookupError):
            os.kill(pid, 0)

    def test_client_disconnect_kills_curator_process(self):
        pidfile = self.tmp / "disconnect-curator.pid"
        self._stub_curator_python(
            "import json, os, time\n"
            f"open({str(pidfile)!r}, 'w').write(str(os.getpid()))\n"
            "print(json.dumps({'type':'system','subtype':'init','session_id':'sid-disconnect',"
            "'model':'stub'}), flush=True)\n"
            "time.sleep(0.15)\n"
            "while True:\n"
            "    print(json.dumps({'type':'assistant','message':{'content':[{'type':'text',"
            "'text':'tick'}]}}), flush=True)\n"
            "    time.sleep(0.03)\n",
            name="disconnect-curator",
        )
        payload = json.dumps({
            "project": "t", "id": "alpha", "message": "disconnect",
        }).encode()
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        conn.request("POST", "/api/chat", body=payload,
                     headers=_auth_headers({"Content-Type": "application/json",
                                           "Content-Length": str(len(payload))}))
        response = conn.getresponse()
        self.assertEqual(response.status, 200)
        first = json.loads(response.readline())
        self.assertEqual(first["t"], "model")
        stream_socket = conn.sock or response.fp.raw._sock
        stream_socket.shutdown(socket.SHUT_RDWR)
        stream_socket.close()
        response.close()
        conn.close()

        deadline = time.monotonic() + 3
        pid = int(pidfile.read_text())
        while time.monotonic() < deadline:
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                break
            time.sleep(0.03)
        else:
            os.kill(pid, signal.SIGKILL)
            self.fail("curator process survived client disconnect")

    def test_spawn_failure_returns_clean_json_and_does_not_kill_server(self):
        saved = server.CLAUDE
        server.CLAUDE = str(self.tmp / "definitely-not-here")
        self.addCleanup(lambda: setattr(server, "CLAUDE", saved))
        s0, failed = _http(
            "POST", f"{self.base}/api/chat",
            {"project": "t", "id": "alpha", "message": "x"})
        self.assertEqual(s0, 500)
        self.assertEqual(failed.get("error"), failed["error"])  # present
        self.assertIn("error", failed)
        self.assertEqual(failed["code"], "curator_unavailable")
        self.assertIn("curator CLI not found", failed["error"])
        self.assertIn("definitely-not-here", failed["error"])
        self.assertIn("kettle doctor", failed["error"])
        self.assertNotIn("repr(", json.dumps(failed))
        s, _ = _http("GET", f"{self.base}/api/projects")
        self.assertEqual(s, 200)

    def test_ping_identity_beacon(self):
        import os
        s, j = _http("GET", f"{self.base}/api/ping")
        self.assertEqual(s, 200)
        self.assertEqual(j["app"], "kettle")
        self.assertEqual(j["version"], kettle_contract.core_version())
        self.assertEqual(j["api_version"], kettle_contract.API_VERSION)
        self.assertEqual(
            j["desk_schema_version"],
            kettle_contract.DESK_SCHEMA_VERSION,
        )
        self.assertEqual(j["port"], self.port)
        self.assertEqual(j["pid"], os.getpid())   # server rides in-process here
        self.assertTrue(j.get("started"), "started must be set on every bind path")
        self.assertIn("curator", j)
        self.assertEqual(j["projects"], str(server.PROJECTS_PATH))
        self.assertEqual(j["settings"], str(server.SETTINGS_PATH))

    def test_diff_and_diffstat_canonical_keys(self):
        _http("GET", f"{self.base}/api/queue?project=t")  # create snapshots
        (self.root / "alpha.md").write_text("alpha body\nchanged\n")
        s, j = _http("GET", f"{self.base}/api/diffstat?project=t&id=alpha")
        self.assertEqual(s, 200)
        self.assertIn("stat", j)
        self.assertEqual(j["stat"], j["diff"])  # back-compat alias
        self.assertGreater((j["stat"] or {}).get("added", 0) + (j["stat"] or {}).get("removed", 0), 0)
        s2, j2 = _http("GET", f"{self.base}/api/diff?project=t&id=alpha")
        self.assertEqual(s2, 200)
        self.assertIn("text", j2)
        self.assertEqual(j2["text"], j2["diff"])
        self.assertTrue(j2["text"])

    def test_record_bind_writes_runtime(self):
        """main() and start_server() share _record_bind — cache file matches ping."""
        runtime = self.tmp / "cache" / "server.json"
        saved_path = server.RUNTIME_PATH
        saved_port, saved_started = server.SERVER_PORT, server.SERVER_STARTED
        saved_token = server.SERVER_TOKEN
        server.RUNTIME_PATH = runtime
        try:
            server._record_bind(4242)
            self.assertEqual(server.SERVER_PORT, 4242)
            self.assertTrue(server.SERVER_STARTED)
            data = json.loads(runtime.read_text())
            self.assertEqual(data["port"], 4242)
            self.assertEqual(data["started"], server.SERVER_STARTED)
            self.assertEqual(data["url"], "http://127.0.0.1:4242/")
            self.assertEqual(data["projects"], str(server.PROJECTS_PATH))
            self.assertTrue(data.get("token"))
            self.assertEqual(data["token"], server.SERVER_TOKEN)
            self.assertEqual(runtime.stat().st_mode & 0o777, 0o600)
        finally:
            server.RUNTIME_PATH = saved_path
            server.SERVER_PORT = saved_port
            server.SERVER_STARTED = saved_started
            server.SERVER_TOKEN = saved_token

    def test_settings_multi_group_no_clobber(self):
        for patch in ({"colors": {"--c-red": "#f00"}}, {"slots": {"agent": "--c-gray5"}},
                      {"iface": {"bg": "--c-black"}}, {"model": "opus"}):
            _http("POST", f"{self.base}/api/settings", patch)
        _, j = _http("GET", f"{self.base}/api/settings")
        self.assertEqual(j["colors"], {"--c-red": "#f00"})
        self.assertEqual(j["slots"], {"agent": "--c-gray5"})
        self.assertEqual(j["iface"], {"bg": "--c-black"})
        self.assertEqual(j["model"], "opus")
        # re-saving one group replaces only it; siblings untouched
        _http("POST", f"{self.base}/api/settings", {"colors": {"--c-blue": "#00f"}})
        _, j2 = _http("GET", f"{self.base}/api/settings")
        self.assertEqual(j2["colors"], {"--c-blue": "#00f"})
        self.assertEqual(j2["slots"], {"agent": "--c-gray5"})
        self.assertEqual(j2["model"], "opus")

    def test_edit_project_renames_and_repoints(self):
        moved = self.tmp / "moved"; moved.mkdir()
        s, j = _http("POST", f"{self.base}/api/projects/edit",
                     {"id": "t", "name": "Renamed", "root": str(moved)})
        self.assertEqual(s, 200)
        p = next(x for x in j["projects"] if x["id"] == "t")
        self.assertEqual(p["name"], "Renamed")
        self.assertEqual(p["root"], str(moved))
        # queue path is now derived at runtime, not stored in the registry
        self.assertNotIn("queue", p)
        s2, _ = _http("POST", f"{self.base}/api/projects/edit",
                      {"id": "t", "name": "X", "root": str(self.tmp / "nope")})
        self.assertEqual(s2, 400)                                        # non-existent folder rejected

    def test_delete_project_unregisters_but_keeps_files(self):
        s, j = _http("POST", f"{self.base}/api/projects/delete", {"id": "t"})
        self.assertEqual(s, 200)
        self.assertEqual(j["projects"], [])
        self.assertTrue(self.root.exists())                             # folder left on disk
        s2, _ = _http("POST", f"{self.base}/api/projects/delete", {"id": "ghost"})
        self.assertEqual(s2, 400)                                        # unknown id rejected

    def _entry(self, eid):
        return server.find_entry(server.load_queue(self.proj()), eid)


class LocalhostAuthTests(EndpointTests):
    """Per-boot token, Host/Origin gates, and error-envelope pins (brief 05)."""

    def _raw(self, method, path, *, headers=None, body=None):
        payload = None if body is None else json.dumps(body).encode()
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        try:
            hdrs = dict(headers or {})
            if payload is not None and "Content-Type" not in hdrs:
                hdrs["Content-Type"] = "application/json"
            if payload is not None:
                hdrs["Content-Length"] = str(len(payload))
            conn.request(method, path, body=payload, headers=hdrs)
            res = conn.getresponse()
            raw = res.read()
            try:
                data = json.loads(raw or b"{}")
            except json.JSONDecodeError:
                data = {"_raw": raw.decode("utf-8", "replace")}
            return res.status, data
        finally:
            conn.close()

    def test_api_post_without_token_forbidden(self):
        s, j = self._raw("POST", "/api/save",
                         body={"project": "t", "path": str(self.root / "alpha.md"),
                               "content": "x"})
        self.assertEqual(s, 403)
        self.assertEqual(j.get("code"), "auth")
        self.assertIn("X-Kettle-Token", j.get("error", ""))

    def test_foreign_origin_forbidden(self):
        s, j = self._raw(
            "POST", "/api/save",
            headers={
                server.TOKEN_HEADER: server.SERVER_TOKEN,
                "Origin": "https://evil.example",
            },
            body={"project": "t", "path": str(self.root / "alpha.md"), "content": "x"},
        )
        self.assertEqual(s, 403)
        self.assertEqual(j.get("code"), "bad_origin")

    def test_evil_host_forbidden(self):
        s, j = self._raw(
            "GET", "/api/ping",
            headers={
                server.TOKEN_HEADER: server.SERVER_TOKEN,
                "Host": "evil.tld",
            },
        )
        self.assertEqual(s, 403)
        self.assertEqual(j.get("code"), "bad_host")

    def test_malformed_json_is_400_envelope(self):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        try:
            payload = b"{not-json"
            conn.request(
                "POST", "/api/save", body=payload,
                headers=_auth_headers({
                    "Content-Type": "application/json",
                    "Content-Length": str(len(payload)),
                }),
            )
            res = conn.getresponse()
            j = json.loads(res.read() or b"{}")
            self.assertEqual(res.status, 400)
            self.assertEqual(j.get("code"), "bad_json")
            self.assertIn("error", j)
            self.assertNotIn("JSONDecodeError(", j["error"])  # str(e), not repr(e)
        finally:
            conn.close()

    def test_save_does_not_follow_a_planted_temp_symlink(self):
        """A folder that ships `draft.md.desk-tmp -> ~/.zshrc` (or any predictable
        temp name) must not redirect the user's save outside the fence."""
        target = self.root / "draft.md"
        target.write_text("old")
        outside = self.tmp / "outside-victim.txt"
        outside.write_text("untouched")
        for name in ("draft.md.desk-tmp", "draft.md.tmp"):
            (self.root / name).symlink_to(outside)
        s, _ = _http("POST", f"{self.base}/api/save",
                     {"project": "t", "path": str(target), "content": "new text"})
        self.assertEqual(s, 200)
        self.assertEqual(target.read_text(), "new text")
        self.assertEqual(outside.read_text(), "untouched")

    def test_save_creates_a_new_file_in_an_existing_folder(self):
        target = self.root / "fresh.md"
        s, _ = _http("POST", f"{self.base}/api/save",
                     {"project": "t", "path": str(target), "content": "hello"})
        self.assertEqual(s, 200)
        self.assertEqual(target.read_text(), "hello")

    def test_desk_logs_and_snapshots_do_not_follow_planted_symlinks(self):
        proj = self.proj()
        outside = self.tmp / "outside"
        outside.mkdir()
        victim = outside / "victim.txt"
        victim.write_text("untouched")
        log = server.runtime_dir(proj) / "approvals.log"
        log.unlink(missing_ok=True)
        log.symlink_to(victim)
        s, j = _http("POST", f"{self.base}/api/approve", {"project": "t", "id": "beta"})
        self.assertEqual((s, j["code"]), (403, "unsafe_path"))
        self.assertEqual(victim.read_text(), "untouched")
        snaps = server.runtime_dir(proj) / "snapshots"
        shutil.rmtree(snaps, ignore_errors=True)
        snaps.symlink_to(outside)
        with self.assertRaises(server.lineage.UnsafeDeskPath):
            server.atomic_write(snaps / "alpha.orig", b"x")
        self.assertFalse((outside / "alpha.orig").exists())

    def test_refound_refuses_a_desk_that_leads_outside_the_project(self):
        proj = self.proj()
        desk = server.project_root(proj) / ".kettle"
        elsewhere = self.tmp / "victim-desk"
        shutil.copytree(desk, elsewhere)
        (elsewhere / "note.md").write_text("keep me")
        shutil.rmtree(desk)
        desk.symlink_to(elsewhere)
        s, _ = _http("POST", f"{self.base}/api/projects/refound", {"id": "t"})
        self.assertEqual(s, 403)
        self.assertEqual((elsewhere / "note.md").read_text(), "keep me")

    def test_root_gate_is_case_insensitive_on_macos_and_covers_library(self):
        home = server.HOME.resolve()
        if sys.platform == "darwin":
            self.assertIn("overlaps", server.project_root_problem(home / ".SSH"))
        self.assertIn("Library", server.project_root_problem(home / "Library" / "Keychains"))
        self.assertIsNone(server.project_root_problem(
            home / "Library" / "Mobile Documents" / "com~apple~CloudDocs" / "proj"))

    def test_home_and_credential_folders_cannot_be_project_roots(self):
        home = server.HOME.resolve()
        self.assertIn("whole home folder", server.project_root_problem(home))
        self.assertIn("overlaps", server.project_root_problem(home / ".ssh"))
        self.assertIsNone(server.project_root_problem(self.root.resolve()))

    def test_symlinked_desk_leading_outside_the_project_is_refused(self):
        proj = self.proj()
        desk = server.project_root(proj) / ".kettle"
        elsewhere = self.tmp / "elsewhere-desk"
        shutil.copytree(desk, elsewhere)
        shutil.rmtree(desk)
        desk.symlink_to(elsewhere)
        with self.assertRaises(ValueError):
            server.runtime_dir(proj)

    def test_corrupt_queue_is_reported_and_never_overwritten(self):
        qp = server.queue_path(self.proj())
        qp.write_text("{not json")
        s, j = _http("GET", f"{self.base}/api/queue?project=t")
        self.assertEqual((s, j["code"]), (409, "queue_corrupt"))
        s2, j2 = _http("POST", f"{self.base}/api/approve", {"project": "t", "id": "alpha"})
        self.assertEqual(s2, 409)
        self.assertEqual(qp.read_text(), "{not json")

    def test_moved_project_folder_is_not_recreated(self):
        proj = self.proj()
        root = server.project_root(proj)
        moved = root.with_name(root.name + "-moved")
        root.rename(moved)
        self.addCleanup(lambda: moved.exists() and moved.rename(root))
        s, j = _http("GET", f"{self.base}/api/queue?project=t")
        self.assertEqual(s, 404)
        self.assertIn("project folder is missing", j["error"])
        self.assertFalse(root.exists())

    def test_save_missing_file_is_404(self):
        missing = self.root / "no-such-dir" / "missing.md"
        s, j = _http("POST", f"{self.base}/api/save",
                     {"project": "t", "path": str(missing), "content": "x"})
        self.assertEqual(s, 404)
        self.assertEqual(j.get("code"), "not_found")
        self.assertIn("error", j)

    def test_diff_unknown_entry_errors(self):
        s, j = _http("GET", f"{self.base}/api/diff?project=t&id=nope")
        self.assertEqual(s, 404)
        self.assertEqual(j.get("code"), "not_found")
        s2, j2 = _http("GET", f"{self.base}/api/diffstat?project=t&id=nope")
        self.assertEqual(s2, 404)
        self.assertEqual(j2.get("code"), "not_found")

    def test_index_injects_token_meta(self):
        s, headers, body = None, None, None
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        try:
            conn.request("GET", "/")
            res = conn.getresponse()
            s, body = res.status, res.read()
        finally:
            conn.close()
        self.assertEqual(s, 200)
        meta = f'meta name="kettle-token" content="{server.SERVER_TOKEN}"'.encode()
        self.assertIn(meta, body)

    def test_index_withholds_the_token_from_another_users_connection(self):
        """Anything on loopback can GET /; only this server's own user gets the token."""
        with mock.patch.object(server, "peer_is_own_user", return_value=False) as check:
            conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
            try:
                conn.request("GET", "/")
                body = conn.getresponse().read()
            finally:
                conn.close()
        self.assertTrue(check.called)
        self.assertNotIn(b'<meta name="kettle-token"', body)
        self.assertNotIn(server.SERVER_TOKEN.encode(), body)

    def test_peer_owner_parsers(self):
        lsof = ("p70500\nu501\nf4\nn127.0.0.1:50563->127.0.0.1:4242\n"
                "p999\nu0\nf5\nn127.0.0.1:4242->127.0.0.1:50563\n")
        self.assertEqual(server.parse_lsof_peer_uid(lsof, "127.0.0.1", 50563), 501)
        self.assertIsNone(server.parse_lsof_peer_uid(lsof, "127.0.0.1", 50999))
        # the server's own accepted socket (local = server port) must never answer
        self.assertIsNone(server.parse_lsof_peer_uid("p1\nu0\nf5\nn127.0.0.1:4242->127.0.0.1:50563\n",
                                                     "127.0.0.1", 50563))
        proc = ("  sl  local_address                         rem_address   st tx_queue rx_queue tr tm->when retrnsmt   uid  timeout inode\n"
                "   0: 0100007F:C583 0100007F:1092 01 00000000:00000000 00:00000000 00000000  1000        0 1\n"
                "   1: 0100007F:1092 0100007F:C583 01 00000000:00000000 00:00000000 00000000     0        0 2\n")
        self.assertEqual(server.parse_proc_net_tcp_uid(proc, "127.0.0.1", 0xC583), 1000)
        self.assertIsNone(server.parse_proc_net_tcp_uid(proc, "127.0.0.1", 1))

    def test_peer_check_can_be_skipped_explicitly(self):
        with mock.patch.dict(os.environ, {"KETTLE_SKIP_PEER_CHECK": "1"}):
            self.assertTrue(server.peer_is_own_user("127.0.0.1", 1))

    def test_index_sends_a_script_pinning_csp(self):
        """Injected markup must not run even if the sanitizer misses it: script-src
        admits only this origin plus the exact inline blocks shipped in index.html."""
        import base64
        import hashlib
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        try:
            conn.request("GET", "/")
            res = conn.getresponse()
            headers, body = dict(res.getheaders()), res.read()
        finally:
            conn.close()
        csp = headers.get("Content-Security-Policy", "")
        directives = {d.split()[0]: d.split()[1:] for d in csp.split("; ") if d}
        script_src = directives.get("script-src", [])
        self.assertIn("'self'", script_src)
        self.assertNotIn("'unsafe-inline'", script_src)
        self.assertNotIn("'unsafe-eval'", script_src)
        inline = re.findall(rb"<script(?![^>]*\bsrc=)[^>]*>(.*?)</script>", body, re.DOTALL)
        self.assertGreaterEqual(len(inline), 2)
        for block in inline:
            h = "'sha256-" + base64.b64encode(hashlib.sha256(block).digest()).decode() + "'"
            self.assertIn(h, script_src)
        self.assertEqual(directives.get("frame-ancestors"), ["'none'"])
        self.assertEqual(directives.get("object-src"), ["'none'"])
        self.assertEqual(headers.get("X-Frame-Options"), "DENY")
        self.assertEqual(headers.get("X-Content-Type-Options"), "nosniff")

    def test_csp_hashes_survive_crlf_line_endings(self):
        """Browsers hash inline scripts after normalizing CRLF; a CRLF checkout must
        not blank the sitting."""
        lf = b"<html><head><script>\nboot();\n</script></head><script>main()\n</script></html>"
        crlf = lf.replace(b"\n", b"\r\n")
        self.assertEqual(server.sitting_csp(lf), server.sitting_csp(crlf))

    def test_csp_refuses_remote_images(self):
        csp = server.sitting_csp(b"<script>x()</script>")
        img = next(d for d in csp.split("; ") if d.startswith("img-src"))
        self.assertNotIn("http", img)

    def test_same_origin_origin_allowed(self):
        s, j = self._raw(
            "GET", "/api/ping",
            headers={
                server.TOKEN_HEADER: server.SERVER_TOKEN,
                "Origin": f"http://127.0.0.1:{self.port}",
            },
        )
        self.assertEqual(s, 200)
        self.assertEqual(j.get("app"), "kettle")


class LaunchTests(unittest.TestCase):
    """start_server_preferred circuit-breaker (2026-06-13): a bare launch must never
    kill a healthy, CURRENT predecessor. Stubs the ping/retire/bind/code-mtime seams
    so no real port is bound and no real process is signalled."""

    def setUp(self):
        self._saved = {k: getattr(server, k) for k in
                       ("_ping_kettle", "_retire", "start_server", "_code_mtime")}
        self.retired, self.bound = [], []
        server._retire = lambda pid: self.retired.append(pid)
        server.start_server = lambda port=0: (
            self.bound.append(port) or ("SRV", port or server.DEFAULT_PORT))
        server._code_mtime = lambda: 1000.0  # fixed "code change" instant

    def tearDown(self):
        for k, v in self._saved.items():
            setattr(server, k, v)

    def _ping(self, result):
        server._ping_kettle = lambda port, timeout=0.8: result

    @staticmethod
    def _ts(epoch):
        from datetime import datetime, timezone
        return datetime.fromtimestamp(epoch, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%S%z")

    def test_no_predecessor_starts_normally(self):  # regression
        self._ping(None)
        self.assertIsNotNone(server.start_server_preferred())
        self.assertEqual(self.retired, [])
        self.assertEqual(self.bound, [server.DEFAULT_PORT])

    def test_healthy_current_predecessor_not_killed(self):  # the fix
        self._ping({"pid": 99999, "started": self._ts(1005)})  # started AFTER code mtime
        self.assertIsNone(server.start_server_preferred())     # defers
        self.assertEqual(self.retired, [])                     # nothing killed
        self.assertEqual(self.bound, [])                       # nothing bound

    def test_stale_predecessor_retired(self):  # intended retirement still works
        self._ping({"pid": 99999, "started": self._ts(995)})   # started BEFORE code mtime
        self.assertIsNotNone(server.start_server_preferred())
        self.assertEqual(self.retired, [99999])
        self.assertEqual(self.bound, [server.DEFAULT_PORT])

    def test_replace_retires_current_predecessor(self):
        self._ping({"pid": 99999, "started": self._ts(1005)})  # current, but --replace
        self.assertIsNotNone(server.start_server_preferred(replace=True))
        self.assertEqual(self.retired, [99999])

    def test_own_pid_never_killed(self):
        import os
        self._ping({"pid": os.getpid(), "started": self._ts(0)})
        self.assertIsNotNone(server.start_server_preferred())
        self.assertEqual(self.retired, [])
        self.assertEqual(self.bound, [server.DEFAULT_PORT])

    def test_foreign_occupant_ephemeral_fallback(self):  # regression
        self._ping(None)  # a non-kettle occupant pings as "not ours" -> None
        calls = []
        def fake_start(port=0):
            calls.append(port)
            if port == server.DEFAULT_PORT:
                raise OSError("address in use")
            return ("SRV", 54321)
        server.start_server = fake_start
        self.assertIsNotNone(server.start_server_preferred())
        self.assertEqual(calls, [server.DEFAULT_PORT, 0])  # tried fixed, fell back
        self.assertEqual(self.retired, [])


class GuardTests(Base):
    """LAB-23: Host / Origin (+ per-boot token) validation on the localhost surface.

    The guards live in Handler.check_request_guards / _host_allowed / _origin_allowed.
    Two layers of coverage: pure allowlist unit tests, plus live-server accept/reject
    cases driven through a raw http.client so the Host and token headers can be forged.
    """

    # ---- pure unit tests: the Host allowlist ----

    def test_host_allowed_accepts_loopback(self):
        for h in ("127.0.0.1", "localhost", "127.0.0.1:4242",
                  "localhost:8080", "LOCALHOST", "  localhost  "):
            self.assertTrue(server.Handler._host_allowed(h), f"should accept {h!r}")

    def test_host_allowed_rejects_foreign_and_malformed(self):
        # Foreign hosts (DNS-rebinding vectors), out-of-range ports, non-numeric
        # ports, empty Host, and IPv6 loopback (deliberately unlisted) all fail.
        for h in ("", "evil.com", "example.com:4242", "127.0.0.1.evil.com",
                  "localhost.evil.com", "127.0.0.1:", "localhost:0",
                  "localhost:99999", "127.0.0.1:abc", "[::1]", "0.0.0.0"):
            self.assertFalse(server.Handler._host_allowed(h), f"should reject {h!r}")

    # ---- live-server integration: accept + reject through the wire ----

    def setUp(self):
        super().setUp()
        self.srv, self.port = server.start_server(0)
        self.base = f"http://127.0.0.1:{self.port}"

    def tearDown(self):
        self.srv.shutdown()
        self.srv.server_close()
        super().tearDown()

    def _tok(self, extra=None):
        h = {server.TOKEN_HEADER: server.SERVER_TOKEN}
        if extra:
            h.update(extra)
        return h

    def _raw(self, method, path, host=None, headers=None):
        """Raw request with full control of the Host header (and no auto-token).

        `host=None` lets http.client set a valid loopback Host; pass a string to
        forge it. Returns (status, parsed_json_or_None).
        """
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        try:
            conn.putrequest(method, path, skip_host=(host is not None))
            if host is not None:
                conn.putheader("Host", host)
            for k, v in (headers or {}).items():
                conn.putheader(k, v)
            conn.endheaders()
            resp = conn.getresponse()
            raw = resp.read()
            try:
                return resp.status, json.loads(raw or b"{}")
            except json.JSONDecodeError:
                return resp.status, None
        finally:
            conn.close()

    def test_valid_host_no_origin_accepted(self):
        # CLI-style client: valid Host, valid token, NO Origin header — accepted.
        # This is the deliberate exception noted in LAB-23 for tools with no Origin.
        s, j = self._raw("GET", "/api/ping", headers=self._tok())
        self.assertEqual(s, 200)
        self.assertEqual(j["app"], "kettle")

    def test_same_origin_accepted(self):
        s, j = self._raw("GET", "/api/ping",
                         headers=self._tok({"Origin": self.base}))
        self.assertEqual(s, 200)

    def test_forged_host_rejected(self):
        s, j = self._raw("GET", "/api/ping", host="evil.com", headers=self._tok())
        self.assertEqual(s, 403)
        self.assertEqual(j["code"], "bad_host")

    def test_cross_origin_rejected(self):
        s, j = self._raw("GET", "/api/ping",
                         headers=self._tok({"Origin": "http://evil.com"}))
        self.assertEqual(s, 403)
        self.assertEqual(j["code"], "bad_origin")

    def test_api_path_requires_token(self):
        s, j = self._raw("GET", "/api/ping")  # valid Host, but no token
        self.assertEqual(s, 403)
        self.assertEqual(j["code"], "auth")

    def test_non_api_path_skips_token_but_enforces_host(self):
        # GET / carries no token requirement, yet a forged Host is still refused.
        s, j = self._raw("GET", "/", host="evil.com")
        self.assertEqual(s, 403)
        self.assertEqual(j["code"], "bad_host")


if __name__ == "__main__":
    unittest.main(verbosity=2)
