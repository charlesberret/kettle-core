#!/usr/bin/env python3
"""Unit tests for lineage.py — agent / user / unattributed reconciliation.

Stdlib only (unittest). Run:  python3 test_lineage.py

The load-bearing rule, pinned in test_unclaimed_change_is_unattributed_not_user: a change
no working-record entry claims is UNATTRIBUTED, never silently 'user' — the user's
2026-06-18 ruling against trust-by-default.
"""
import tempfile
import unittest
from pathlib import Path

import kettle.lineage as lineage


class LineageTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="lin-test-"))
        (self.tmp / "a.md").write_text("alpha\n")
        (self.tmp / "b.md").write_text("beta\n")
        lineage.accept_baseline(self.tmp)        # baseline = current state

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    # ---- change detection ----

    def test_clean_tree_has_no_changes(self):
        self.assertEqual(lineage.status(self.tmp)["changed"], 0)

    def test_detects_added_modified_deleted(self):
        (self.tmp / "a.md").write_text("alpha edited\n")     # modified
        (self.tmp / "c.md").write_text("gamma\n")            # added
        (self.tmp / "b.md").unlink()                         # deleted
        chg = {c["path"]: c["change"] for c in lineage.status(self.tmp)["changes"]}
        self.assertEqual(chg, {"a.md": "modified", "c.md": "added", "b.md": "deleted"})

    # ---- attribution ----

    def test_unclaimed_change_is_unattributed_not_user(self):
        """THE RULING: an unlogged change is unattributed, never auto-'user'."""
        (self.tmp / "a.md").write_text("changed out of band\n")
        st = lineage.status(self.tmp)
        self.assertEqual(st["counts"]["unattributed"], 1)
        self.assertEqual(st["counts"]["user"], 0)
        self.assertEqual(st["changes"][0]["status"], "unattributed")

    def test_agent_claim_attributes_to_agent(self):
        (self.tmp / "a.md").write_text("rewritten by an agent\n")
        lineage.log_edit(self.tmp, actor="dramaturge", actor_kind="agent",
                         files=["a.md"], summary="rebuilt")
        st = lineage.status(self.tmp)
        self.assertEqual(st["counts"], {"agent": 1, "user": 0, "unattributed": 0})
        self.assertEqual(st["changes"][0]["by"], "dramaturge")

    def test_user_claim_attributes_to_user(self):
        (self.tmp / "b.md").write_text("the user edited this in the desk\n")
        lineage.log_edit(self.tmp, actor="user", actor_kind="user", files=["b.md"])
        st = lineage.status(self.tmp)
        self.assertEqual(st["counts"], {"agent": 0, "user": 1, "unattributed": 0})

    def test_stale_claim_before_baseline_is_ignored(self):
        # a claim that predates the baseline can't explain a change made after it
        lineage.log_edit(self.tmp, actor="old-agent", actor_kind="agent",
                         files=["a.md"], summary="long ago", ts="2000-01-01T00:00:00+00:00")
        (self.tmp / "a.md").write_text("changed now, by nobody logged\n")
        st = lineage.status(self.tmp)
        self.assertEqual(st["changes"][0]["status"], "unattributed")

    def test_latest_claim_wins(self):
        # the record is append-ordered, so a later entry overwrites an earlier claim
        (self.tmp / "a.md").write_text("v2\n")
        lineage.log_edit(self.tmp, actor="agent-x", actor_kind="agent", files=["a.md"])
        lineage.log_edit(self.tmp, actor="user", actor_kind="user", files=["a.md"])
        self.assertEqual(lineage.status(self.tmp)["changes"][0]["status"], "user")

    # ---- resolve + re-baseline ----

    def test_resolve_then_attributed_then_accept_clears(self):
        (self.tmp / "a.md").write_text("out-of-band\n")
        self.assertEqual(lineage.status(self.tmp)["changes"][0]["status"], "unattributed")
        lineage.resolve(self.tmp, "a.md", actor_kind="user")      # user resolves
        self.assertEqual(lineage.status(self.tmp)["changes"][0]["status"], "user")
        lineage.accept_baseline(self.tmp)                          # mark seen
        self.assertEqual(lineage.status(self.tmp)["changed"], 0)

    # ---- agent auto-logging ----

    def test_log_agent_edits_relativizes_and_filters(self):
        rec = lineage.log_agent_edits(self.tmp, [
            str(self.tmp / "a.md"),
            str(self.tmp / ".kettle" / "PROJECT.md"),   # machinery → dropped
            "/etc/passwd",                                  # outside the desk → dropped
            str(self.tmp / "a.md"),                         # duplicate → once
        ], actor="curator")
        self.assertEqual(rec["files"], ["a.md"])
        self.assertEqual(rec["actor_kind"], "agent")
        self.assertEqual(rec["actor"], "curator")

    def test_log_agent_edits_none_when_nothing_trackable(self):
        self.assertIsNone(lineage.log_agent_edits(
            self.tmp, ["/etc/x", str(self.tmp / ".kettle" / "q.json")]))

    def test_agent_edit_auto_logged_reconciles_as_agent(self):
        (self.tmp / "a.md").write_text("changed by the sweep\n")
        lineage.log_agent_edits(self.tmp, [str(self.tmp / "a.md")], actor="sweep")
        st = lineage.status(self.tmp)
        self.assertEqual(st["changes"][0]["status"], "agent")
        self.assertEqual(st["changes"][0]["by"], "sweep")

    def test_user_edit_auto_logged_reconciles_as_user(self):
        (self.tmp / "a.md").write_text("the user typed this in the editor\n")
        lineage.log_user_edit(self.tmp, [str(self.tmp / "a.md")])
        st = lineage.status(self.tmp)
        self.assertEqual(st["changes"][0]["status"], "user")
        self.assertEqual(st["changes"][0]["by"], "user")

    # ---- the binding directive ----

    def test_ensure_directive_creates_and_is_idempotent(self):
        r1 = lineage.ensure_directive(self.tmp)
        self.assertEqual(r1["action"], "created")
        self.assertTrue(r1["editing_created"])
        body = (self.tmp / "CLAUDE.md").read_text()
        self.assertIn("kettle:lineage", body)
        self.assertIn(".kettle/EDITING.md", body)
        self.assertTrue((self.tmp / ".kettle" / "EDITING.md").exists())
        r2 = lineage.ensure_directive(self.tmp)               # re-bind
        self.assertEqual(r2["action"], "updated")
        self.assertFalse(r2["editing_created"])
        # exactly one fenced block (open + close marker), no duplication
        self.assertEqual((self.tmp / "CLAUDE.md").read_text().count("kettle:lineage"), 2)

    def test_ensure_directive_appends_to_existing_claude(self):
        (self.tmp / "CLAUDE.md").write_text("# My project\n\nexisting instructions.\n")
        r = lineage.ensure_directive(self.tmp)
        self.assertEqual(r["action"], "appended")
        body = (self.tmp / "CLAUDE.md").read_text()
        self.assertIn("existing instructions", body)
        self.assertIn("kettle:lineage", body)

    def test_ensure_directive_updates_legacy_desk_without_splitting_state(self):
        (self.tmp / ".kettle").rename(self.tmp / ".setsweep")
        (self.tmp / "CLAUDE.md").write_text(
            "<!-- setsweep:lineage (old) -->\nold\n"
            "<!-- /setsweep:lineage -->\n"
        )
        result = lineage.ensure_directive(self.tmp)
        body = (self.tmp / "CLAUDE.md").read_text()
        self.assertEqual(result["action"], "updated")
        self.assertIn("kettle:lineage", body)
        self.assertIn(".setsweep/EDITING.md", body)
        self.assertNotIn("setsweep:lineage", body)
        self.assertTrue((self.tmp / ".setsweep" / "EDITING.md").exists())
        self.assertFalse((self.tmp / ".kettle").exists())

    # ---- optional git substrate ----

    def test_git_snapshot_uses_separate_history_leaving_project_git_untouched(self):
        import shutil, subprocess
        if not shutil.which("git"):
            self.skipTest("git not available")
        run = lambda *a: subprocess.run(["git", "-C", str(self.tmp), *a],
                                        capture_output=True, text=True, check=True)
        run("init", "-q"); run("config", "user.email", "u@x"); run("config", "user.name", "u")
        run("add", "-A"); run("commit", "-q", "-m", "the user's own commit")
        before = run("rev-list", "--count", "HEAD").stdout.strip()
        (self.tmp / "a.md").write_text("changed\n")
        h = lineage.git_snapshot(self.tmp, "lineage: test")
        self.assertIsNotNone(h)                                       # lineage committed
        self.assertTrue((self.tmp / ".kettle" / "lineage.git").exists())
        after = run("rev-list", "--count", "HEAD").stdout.strip()
        self.assertEqual(before, after)                              # project git UNTOUCHED

    # ---- walking ----

    def test_kettle_dir_and_dotfiles_not_tracked(self):
        lineage.accept_baseline(self.tmp)
        (self.tmp / ".kettle" / "queue.json").parent.mkdir(exist_ok=True)
        (self.tmp / ".kettle" / "queue.json").write_text("{}")
        (self.tmp / ".hidden").write_text("secret\n")
        self.assertEqual(lineage.status(self.tmp)["changed"], 0)   # neither is tracked

    def test_binary_and_oversized_skipped(self):
        (self.tmp / "img.bin").write_bytes(b"\x00\x01\x02\x00")
        snap = lineage.snapshot(self.tmp)
        self.assertNotIn("img.bin", snap)


class MaxDepthTest(unittest.TestCase):
    def test_snapshot_respects_and_prunes_depth(self):
        from pathlib import Path
        root = Path(tempfile.mkdtemp())
        (root / "a.md").write_text("1")
        (root / "sub").mkdir(); (root / "sub" / "b.md").write_text("2")
        (root / "sub" / "deep").mkdir(); (root / "sub" / "deep" / "c.md").write_text("3")
        keys = lambda md: set(lineage.snapshot(root, max_depth=md).keys())
        self.assertEqual(keys(1), {"a.md"})                                 # root files only
        self.assertEqual(keys(2), {"a.md", "sub/b.md"})                     # + one subdir level
        self.assertEqual(keys(None), {"a.md", "sub/b.md", "sub/deep/c.md"})  # unbounded
        self.assertEqual(keys(0), keys(None))                              # 0 == unbounded


if __name__ == "__main__":
    unittest.main()
