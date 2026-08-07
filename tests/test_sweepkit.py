#!/usr/bin/env python3
"""Tests for the mechanical sweep close-kit."""

from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

import kettle.server as server
import kettle.sweepkit as sweepkit


class SweepkitBase(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="kettle-sweepkit-"))
        self.root = self.tmp / "proj"
        (self.root / ".kettle").mkdir(parents=True)
        (self.root / "doc.md").write_text("hello\n", encoding="utf-8")
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
        server.HOME = self.tmp
        self.queue = server.queue_path(server.get_project("t"))

    def tearDown(self):
        for k, v in self._saved.items():
            setattr(server, k, v)
        shutil.rmtree(self.tmp, ignore_errors=True)

    def proj(self):
        return server.get_project("t")

    def write_queue(self, entries):
        self.queue.parent.mkdir(parents=True, exist_ok=True)
        self.queue.write_text(json.dumps({"curated": "test", "entries": entries}))

    def seed_quiet_approved(self, eid="e1", path="doc.md"):
        # Snapshots are taken only while pending (ensure_snapshots skips approved).
        self.write_queue([{
            "id": eid, "path": path, "brief": "b", "ask": "review",
            "status": "pending",
        }])
        q = server.load_queue(self.proj())
        server.ensure_snapshots(self.proj(), q)
        server.mutate_queue(self.proj(), lambda qq: qq["entries"][0].update(status="approved"))


class AssessTests(SweepkitBase):
    def test_quiet_approved_can_mechanical_close(self):
        self.seed_quiet_approved()
        st = sweepkit.assess_close(self.proj())
        self.assertTrue(st["quiet"])
        self.assertTrue(st["can_mechanical_close"])
        self.assertTrue(st["needs_accrue"])
        self.assertFalse(st["needs_judgment"])

    def test_missing_snapshot_blocks_quiet(self):
        self.write_queue([{
            "id": "e1", "path": "doc.md", "brief": "b", "ask": "review",
            "status": "approved",
        }])
        st = sweepkit.assess_close(self.proj())
        self.assertFalse(st["quiet"])
        self.assertTrue(st["unknown"])
        self.assertFalse(st["can_mechanical_close"])

    def test_file_change_needs_judgment(self):
        self.seed_quiet_approved()
        (self.root / "doc.md").write_text("hello\nchanged\n", encoding="utf-8")
        st = sweepkit.assess_close(self.proj())
        self.assertFalse(st["quiet"])
        self.assertTrue(st["needs_judgment"])
        self.assertFalse(st["can_mechanical_close"])
        self.assertEqual(st["changed"][0]["id"], "e1")

    def test_ledger_blocks_mechanical_close(self):
        self.seed_quiet_approved()
        proj = self.proj()
        proj["ledger"] = str(self.root / "rulings.md")
        st = sweepkit.assess_close(proj)
        self.assertFalse(st["quiet"])
        self.assertFalse(st["can_mechanical_close"])

    def test_pending_without_inbox_cannot_mech_close(self):
        self.write_queue([{
            "id": "e1", "path": "doc.md", "brief": "b", "ask": "review",
            "status": "pending",
        }])
        q = server.load_queue(self.proj())
        server.ensure_snapshots(self.proj(), q)
        st = sweepkit.assess_close(self.proj())
        self.assertTrue(st["quiet"])
        self.assertFalse(st["can_mechanical_close"])


class CloseTests(SweepkitBase):
    def test_mechanical_close_archives_and_logs(self):
        self.seed_quiet_approved()
        result = sweepkit.mechanical_close(self.proj())
        self.assertTrue(result["ok"])
        self.assertEqual(result["action"], "mechanical_close")
        self.assertTrue(result["needs_accrue"])
        self.assertEqual(result["archived"]["archived"], ["e1"])
        self.assertEqual(server.load_queue(self.proj()).get("entries"), [])
        self.assertTrue(Path(result["session_log"]).exists())
        snap = server._snapshot_path(self.proj(), "e1")
        self.assertFalse(snap.exists())
        # Peer-facing approval egress staged for fleet
        self.assertTrue(result.get("approval_egress", {}).get("published"))
        ap = Path(result["approval_egress"]["path"])
        self.assertTrue(ap.exists())
        text = ap.read_text(encoding="utf-8")
        self.assertIn("**Kind:** approval", text)
        self.assertIn("e1", text)
        self.assertIn("doc.md", text)

    def test_publish_approval_egress_lists_pending_blocks(self):
        self.write_queue([
            {"id": "ok", "path": "doc.md", "status": "approved", "ask": "done",
             "approved": "2026-07-16", "unblocks": "ship feature"},
            {"id": "wait", "path": "ROADMAP.md", "status": "pending", "ask": "gate",
             "unblocks": "agent-B may resume"},
        ])
        pub = sweepkit.publish_approval_egress(self.proj())
        self.assertTrue(pub["published"])
        body = Path(pub["path"]).read_text(encoding="utf-8")
        self.assertIn("ok", body)
        self.assertIn("ship feature", body)
        self.assertIn("ROADMAP.md", body)
        self.assertIn("agent-B may resume", body)
        self.assertIn("Still pending", body)

    def test_mechanical_close_refuses_when_dirty(self):
        self.seed_quiet_approved()
        (self.root / "doc.md").write_text("edited\n", encoding="utf-8")
        result = sweepkit.mechanical_close(self.proj())
        self.assertFalse(result["ok"])
        self.assertEqual(result["action"], "refused")
        self.assertEqual(len(server.load_queue(self.proj())["entries"]), 1)

    def test_inbox_stages_approved_only(self):
        (self.root / "responses").mkdir()
        (self.root / "responses" / "draft.md").write_text("reply\n", encoding="utf-8")
        registry = json.loads(server.PROJECTS_PATH.read_text())
        registry["projects"][0]["intake"] = {
            "watch": "incoming", "responses": "responses", "outbound": "outbox",
        }
        server.PROJECTS_PATH.write_text(json.dumps(registry))
        self.write_queue([
            {"id": "a1", "path": "responses/draft.md", "brief": "b", "ask": "review",
             "status": "pending"},
            {"id": "p1", "path": "responses/draft.md", "brief": "b", "ask": "review",
             "status": "pending"},
        ])
        q = server.load_queue(self.proj())
        server.ensure_snapshots(self.proj(), q)
        server.mutate_queue(
            self.proj(),
            lambda qq: next(e for e in qq["entries"] if e["id"] == "a1").update(status="approved"),
        )

        result = sweepkit.mechanical_close(self.proj())
        self.assertTrue(result["ok"])
        staged = result["staged"]["staged"]
        self.assertEqual(len(staged), 1)
        self.assertEqual(staged[0]["id"], "a1")
        self.assertTrue((self.root / "outbox" / "draft.md").exists())
        remaining = server.load_queue(self.proj())["entries"]
        self.assertEqual([e["id"] for e in remaining], ["p1"])
        self.assertFalse(result["needs_accrue"])  # inbox: no restock accrue


class ArchiveTests(SweepkitBase):
    def test_archive_by_ids(self):
        self.write_queue([
            {"id": "a", "path": "doc.md", "status": "approved"},
            {"id": "b", "path": "doc.md", "status": "pending"},
        ])
        out = sweepkit.archive_queue(self.proj(), entry_ids=["a"])
        self.assertEqual(out["archived"], ["a"])
        self.assertEqual(out["remaining"], 1)
        self.assertEqual(server.load_queue(self.proj())["entries"][0]["id"], "b")


if __name__ == "__main__":
    unittest.main()
