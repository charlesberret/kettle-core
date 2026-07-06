#!/usr/bin/env python3
"""Unit + integration tests for the Setsweep server.

Stdlib only (unittest + urllib). Run:  python3 test_server.py   (or python3 -m unittest)

The server uses module-level globals for its data paths and security fence; each test
redirects those into a tempdir so the real registry/queue/settings are never touched.
"""

import json
import os
import shutil
import tempfile
import unittest
import urllib.error
import urllib.request
from pathlib import Path

import server


def _http(method, url, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")


class Base(unittest.TestCase):
    """Redirect server globals into a tempdir under a fake HOME, with one project."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="dav-test-"))
        self.root = self.tmp / "proj"
        (self.root / ".setsweep").mkdir(parents=True)
        registry = self.tmp / "projects.json"
        registry.write_text(json.dumps({"projects": [{
            "id": "t", "name": "Test", "root": str(self.root),
            "ledger": None,
            "rework_agents": [{"id": "curator", "name": "the Test curator"}],
        }]}))

        self._saved = {k: getattr(server, k) for k in
                       ("PROJECTS_PATH", "SETTINGS_PATH", "BASE_ALLOWED_ROOTS", "HOME")}
        server.PROJECTS_PATH = registry
        server.SETTINGS_PATH = self.tmp / "settings.json"
        server.BASE_ALLOWED_ROOTS = [self.tmp]
        server.HOME = self.tmp  # so add_project's under-HOME gate accepts temp roots
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

    def test_slug(self):
        self.assertEqual(server.slug("Hello World!"), "Hello_World")
        self.assertEqual(server.slug("a/b:c"), "a_b_c")
        self.assertEqual(server.slug("!!!"), "x")  # empty-after-strip fallback

    def test_session_name(self):
        # one session per project now: setsweep-<project>, slugified, entry ignored
        n = server.session_name({"name": "CryptoHistory"})
        self.assertEqual(n, "setsweep-cryptohistory")
        self.assertEqual(n, n.lower())
        self.assertNotIn(" ", n)
        # the entry argument is accepted but ignored (call-site compatibility)
        self.assertEqual(
            server.session_name({"name": "CryptoHistory"}, {"title": "Chapter 3"}),
            "setsweep-cryptohistory")
        self.assertEqual(server.session_name({"name": "P"}), "setsweep-p")
        # length-capped (slug body <= 48 chars after the setsweep- prefix)
        long = server.session_name({"name": "x" * 80})
        self.assertLessEqual(len(long), len("setsweep-") + 48)

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
        (self.root / ".setsweep").mkdir(exist_ok=True)
        (self.root / ".setsweep" / "PROJECT.md").write_text("charter")
        got = server.safe_path(".setsweep/PROJECT.md", self.root)
        self.assertEqual(got, (self.root / ".setsweep" / "PROJECT.md").resolve())

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
        # the portable fence: base roots come from $SETSWEEP_ALLOWED_ROOTS, default empty
        a, b = self.tmp / "vaultA", self.tmp / "vaultB"
        a.mkdir(); b.mkdir()
        saved = os.environ.get("SETSWEEP_ALLOWED_ROOTS")
        try:
            os.environ["SETSWEEP_ALLOWED_ROOTS"] = f"{a}{os.pathsep}{b}"
            roots = server._env_allowed_roots()
            self.assertIn(a.resolve(), roots)
            self.assertIn(b.resolve(), roots)
            os.environ["SETSWEEP_ALLOWED_ROOTS"] = ""          # unset/empty → no base roots
            self.assertEqual(server._env_allowed_roots(), [])
        finally:
            if saved is None:
                os.environ.pop("SETSWEEP_ALLOWED_ROOTS", None)
            else:
                os.environ["SETSWEEP_ALLOWED_ROOTS"] = saved

    def test_settings_create_then_shallow_merge(self):
        self.assertEqual(server.load_settings(), {})           # creates {}
        self.assertTrue(server.SETTINGS_PATH.exists())
        server.save_settings({"model": "sonnet"})
        server.save_settings({"colWidths": {"left": 280}})     # disjoint key
        merged = server.load_settings()
        self.assertEqual(merged["model"], "sonnet")            # preserved
        self.assertEqual(merged["colWidths"], {"left": 280})

    def test_settings_survives_corrupt_file(self):
        server.SETTINGS_PATH.write_text("{not json")
        self.assertEqual(server.load_settings(), {})           # no crash

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
        f.write_text("edited later")                            # patron edits the file
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
        (self.root / ".setsweep" / "PROJECT.md").write_text("X" * 4000)
        out = server.project_orientation(self.proj())
        self.assertIn("PROJECT.md", out)                       # labeled
        self.assertEqual(out.count("X"), 2500)                 # body truncated
        self.assertNotIn("MEMORY.md", out)                     # absent file → section omitted

    def test_project_orientation_includes_curator_memory(self):
        desk = self.root / ".setsweep"
        (desk / "PROJECT.md").write_text("the charter")
        (desk / "MEMORY.md").write_text("- 2026-06-11: patron prefers serial commas")
        out = server.project_orientation(self.proj())
        self.assertIn("the charter", out)
        self.assertIn("prefers serial commas", out)
        self.assertLess(out.index("the charter"), out.index("prefers serial commas"))  # charter first
        (desk / "MEMORY.md").write_text("   \n")               # whitespace-only → omitted
        self.assertNotIn("MEMORY.md", server.project_orientation(self.proj()))

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
        # durable desk + seeded queue (awaiting founding)
        self.assertTrue((folder / ".setsweep").is_dir())
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

    def test_save_logs_user_edit_to_lineage(self):
        import lineage
        f = self.root / "alpha.md"
        s, _ = _http("POST", f"{self.base}/api/save",
                     {"path": str(f), "content": "patron's own edit\n"})
        self.assertEqual(s, 200)
        self.assertEqual(f.read_text(), "patron's own edit\n")
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
        self.assertIn("setsweep:lineage", (self.root / "CLAUDE.md").read_text())

    def test_queue_get_creates_snapshots(self):
        s, j = _http("GET", f"{self.base}/api/queue?project=t")
        self.assertEqual(s, 200)
        self.assertEqual(len(j["entries"]), 2)
        self.assertTrue((server.runtime_dir(self.proj()) / "snapshots" / "alpha.orig").exists())

    def test_file_get_fenced(self):
        s, j = _http("GET", f"{self.base}/api/file?path={self.root}/alpha.md")
        self.assertEqual((s, j["content"]), (200, "alpha body"))
        s2, _ = _http("GET", f"{self.base}/api/file?path=/etc/passwd")
        self.assertEqual(s2, 403)

    def test_save_fenced_and_atomic(self):
        s, _ = _http("POST", f"{self.base}/api/save",
                     {"path": str(self.root / "alpha.md"), "content": "rewritten"})
        self.assertEqual(s, 200)
        self.assertEqual((self.root / "alpha.md").read_text(), "rewritten")
        s2, _ = _http("POST", f"{self.base}/api/save",
                      {"path": "/tmp/evil.md", "content": "x"})
        self.assertEqual(s2, 403)

    def test_settings_roundtrip(self):
        self.assertEqual(_http("GET", f"{self.base}/api/settings"), (200, {}))
        _http("POST", f"{self.base}/api/settings", {"model": "opus"})
        _http("POST", f"{self.base}/api/settings", {"colors": {"--bg": "#000"}})
        s, j = _http("GET", f"{self.base}/api/settings")
        self.assertEqual(j["model"], "opus")
        self.assertEqual(j["colors"], {"--bg": "#000"})

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

    def test_sweep_injects_patron_comments_from_log(self):
        server.comments_log_path(self.proj()).write_text(
            "2026-06-29\talpha\tfix the TKs\n"
            "2026-06-29\talpha\talso check tone\n"
        )
        cmds = self._capture_cmds()
        self._post_stream("/api/sweep", {"project": "t"})
        prompt = cmds[-1][cmds[-1].index("-p") + 1]
        self.assertIn("PATRON COMMENTS", prompt)
        self.assertIn("Patron comment for this entry: fix the TKs", prompt)
        self.assertIn("Patron comment for this entry: also check tone", prompt)
        self.assertIn("comments.log", prompt)

    def test_approve_marks_and_logs(self):
        s, _ = _http("POST", f"{self.base}/api/approve", {"project": "t", "id": "beta"})
        self.assertEqual(s, 200)
        self.assertEqual(self._entry("beta")["status"], "approved")
        self.assertTrue((server.runtime_dir(self.proj()) / "approvals.log").exists())

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
        s, j = _http("POST", f"{self.base}/api/projects/add", {"name": "New One", "root": str(good)})
        self.assertEqual(s, 200)
        self.assertEqual(j["id"], "new_one")
        self.assertTrue((good / ".setsweep" / "runtime" / "queue.json").exists())
        # duplicate id
        s2, _ = _http("POST", f"{self.base}/api/projects/add", {"name": "New One", "root": str(good)})
        self.assertEqual(s2, 400)
        # nonexistent dir
        s3, _ = _http("POST", f"{self.base}/api/projects/add",
                      {"name": "Ghost", "root": str(self.tmp / "nope")})
        self.assertEqual(s3, 400)
        # outside HOME fence
        s4, _ = _http("POST", f"{self.base}/api/projects/add", {"name": "Evil", "root": "/etc"})
        self.assertEqual(s4, 400)

    def test_interview_status_lifecycle(self):
        # a desk with queue entries is founded on read even if session was never written
        s, j = _http("GET", f"{self.base}/api/interview?project=t")
        self.assertEqual((s, j["status"]), (200, "founded"))
        server.save_interview(self.proj(), {"session_id": "abc", "status": "interviewing"})
        _, j2 = _http("GET", f"{self.base}/api/interview?project=t")
        # queue entries on disk ⇒ founded (heals stale interviewing on read)
        self.assertEqual(j2["status"], "founded")
        iv = server.load_interview(self.proj())
        self.assertEqual(iv["session_id"], "abc")                    # roundtrip
        server.save_interview(self.proj(), {**iv, "status": "founded"})
        _, j3 = _http("GET", f"{self.base}/api/interview?project=t")
        self.assertEqual(j3["status"], "founded")

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
            with urllib.request.urlopen(req, timeout=10) as r:
                body = r.read().decode()
            self.assertIn("hello", body)
            iv = server.load_interview(self.proj())
            self.assertEqual((iv["session_id"], iv["status"]), ("sid-1", "interviewing"))
            # found: queue already has entries (setUp), so it must mark 'founded'
            req2 = urllib.request.Request(f"{self.base}/api/found",
                                          data=json.dumps({"project": "t"}).encode(),
                                          method="POST")
            with urllib.request.urlopen(req2, timeout=10) as r2:
                r2.read()
            self.assertEqual(server.load_interview(self.proj())["status"], "founded")
        finally:
            server.CLAUDE = saved

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
        saved = server.CLAUDE
        server.CLAUDE = str(stub)
        try:
            # queue already has entries (setUp), so bootstrap's mark_founded_if_filed must flip it
            req = urllib.request.Request(f"{self.base}/api/bootstrap",
                                         data=json.dumps({"project": "t"}).encode(), method="POST")
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
            self.assertFalse(j2["ok"])
        finally:
            server.subprocess.Popen = real

    def test_admin_report_shape(self):
        s, j = _http("GET", f"{self.base}/api/admin?project=t")
        self.assertEqual(s, 200)
        for key in ("server", "settings", "sentinel"):
            self.assertIn(key, j)

    def test_unknown_project_400(self):
        s, _ = _http("GET", f"{self.base}/api/queue?project=bogus")
        self.assertEqual(s, 400)

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
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, r.read().decode()

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

            def kill(self):
                pass

        def fake_popen(argv, *a, **k):
            cmds.append(list(argv))
            return _FakeProc(argv)

        server.subprocess.Popen = fake_popen
        self.addCleanup(lambda: setattr(server.subprocess, "Popen", real))
        return cmds

    def test_chat_uses_one_project_session_named_for_project(self):
        # first chat turn on a project CREATES the named project session (no --resume),
        # injects the file's context block, and names it setsweep-test
        cmds = self._capture_cmds()
        self._post_stream("/api/chat", {"project": "t", "id": "alpha", "message": "hi"})
        c1 = cmds[-1]
        self.assertIn("--name", c1)
        self.assertEqual(c1[c1.index("--name") + 1], "setsweep-test")
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
        server.save_session(self.proj(), session_id="sid-live", name="setsweep-test")
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
        server.save_session(self.proj(), session_id="sid-live", name="setsweep-test")
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

    def test_glance_streams_a_reaction(self):
        self._stub_claude(self._init(), self._say("a thought"), self._result())
        s, body = self._post_stream(
            "/api/glance", {"project": "t", "brief": "b", "path": str(self.root / "alpha.md")})
        self.assertEqual(s, 200)
        self.assertIn("a thought", body)

    def test_sweep_streams_with_null_ledger(self):
        # regression: a project whose `ledger` is None must not crash sweep()
        self._stub_claude(self._init(), self._say("swept"), self._result())
        s, body = self._post_stream("/api/sweep", {"project": "t"})
        self.assertEqual(s, 200)
        self.assertIn("swept", body)

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
        self.assertTrue(any(e.get("t") == "error" and "exited 3" in str(e.get("s"))
                            for e in self._events(body)))

    def test_missing_claude_binary_does_not_kill_server(self):
        saved = server.CLAUDE
        server.CLAUDE = str(self.tmp / "definitely-not-here")
        self.addCleanup(lambda: setattr(server, "CLAUDE", saved))
        try:
            self._post_stream("/api/chat", {"project": "t", "id": "alpha", "message": "x"})
        except Exception:
            pass  # the response may break mid-flight; we only assert the server survives
        s, _ = _http("GET", f"{self.base}/api/projects")
        self.assertEqual(s, 200)

    def test_ping_identity_beacon(self):
        import os
        s, j = _http("GET", f"{self.base}/api/ping")
        self.assertEqual(s, 200)
        self.assertEqual(j["app"], "setsweep")
        self.assertEqual(j["port"], self.port)
        self.assertEqual(j["pid"], os.getpid())   # server rides in-process here
        self.assertIn("started", j)

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


class LaunchTests(unittest.TestCase):
    """start_server_preferred circuit-breaker (2026-06-13): a bare launch must never
    kill a healthy, CURRENT predecessor. Stubs the ping/retire/bind/code-mtime seams
    so no real port is bound and no real process is signalled."""

    def setUp(self):
        self._saved = {k: getattr(server, k) for k in
                       ("_ping_setsweep", "_retire", "start_server", "_code_mtime")}
        self.retired, self.bound = [], []
        server._retire = lambda pid: self.retired.append(pid)
        server.start_server = lambda port=0: (
            self.bound.append(port) or ("SRV", port or server.DEFAULT_PORT))
        server._code_mtime = lambda: 1000.0  # fixed "code change" instant

    def tearDown(self):
        for k, v in self._saved.items():
            setattr(server, k, v)

    def _ping(self, result):
        server._ping_setsweep = lambda port, timeout=0.8: result

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
        self._ping(None)  # a non-setsweep occupant pings as "not ours" -> None
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


if __name__ == "__main__":
    unittest.main(verbosity=2)
