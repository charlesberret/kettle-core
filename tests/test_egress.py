#!/usr/bin/env python3
"""Tests for desk egress (.kettle/outbound/)."""

from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

import kettle.egress as egress
import kettle.server as server


class EgressTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="kettle-egress-"))
        self.root = self.tmp / "proj"
        (self.root / ".kettle").mkdir(parents=True)
        registry = self.tmp / "projects.json"
        registry.write_text(json.dumps({"projects": [{
            "id": "t", "name": "Test", "root": str(self.root),
        }]}))
        self._saved = {k: getattr(server, k) for k in
                       ("PROJECTS_PATH", "SETTINGS_PATH", "BASE_ALLOWED_ROOTS", "HOME")}
        server.PROJECTS_PATH = registry
        server.SETTINGS_PATH = self.tmp / "settings.json"
        server.BASE_ALLOWED_ROOTS = [self.tmp]
        server.HOME = self.tmp

    def tearDown(self):
        for k, v in self._saved.items():
            setattr(server, k, v)
        shutil.rmtree(self.tmp, ignore_errors=True)

    def proj(self):
        return server.get_project("t")

    def test_ensure_seeds_readme(self):
        d = egress.ensure_egress(self.proj())
        self.assertTrue(d.is_dir())
        readme = d / "README.md"
        self.assertTrue(readme.exists())
        text = readme.read_text()
        self.assertIn("outbound", text)
        self.assertIn("outbox", text.lower())  # disambiguates mail outbox

    def test_stage_egress_writes_header(self):
        result = egress.stage_egress(
            self.proj(),
            kind="launch",
            topic="Ship the beta",
            body="Approve go for beta release.",
        )
        path = Path(result["path"])
        self.assertTrue(path.exists())
        self.assertRegex(path.name, r"^\d{4}-\d{2}-\d{2}-launch-ship-the-beta\.md$")
        body = path.read_text()
        self.assertIn("# Egress: Ship the beta", body)
        self.assertIn("**From:** kettle/t", body)
        self.assertIn("**Kind:** launch", body)
        self.assertIn("**Route:** launch", body)  # neutral product default
        self.assertIn("**Status:** staged", body)
        self.assertIn("Approve go for beta release.", body)

    def test_list_staged_skips_readme_and_routed(self):
        egress.stage_egress(
            self.proj(), kind="handoff", topic="note", body="hello", route="peers")
        d = egress.egress_dir(self.proj())
        (d / "old-done.md").write_text(
            "# Egress: done\n**Kind:** handoff\n**Route:** x\n**Status:** routed\n\nok\n")
        staged = egress.list_staged(self.proj())
        self.assertEqual(len(staged), 1)
        self.assertEqual(staged[0]["kind"], "handoff")
        self.assertEqual(staged[0]["topic"], "note")

    def test_invalid_kind_raises(self):
        with self.assertRaises(ValueError):
            egress.stage_egress(self.proj(), kind="mail", topic="x", body="y")

    def test_approval_kind_routes_to_peers_by_default(self):
        result = egress.stage_egress(
            self.proj(),
            kind="approval",
            topic="sitting-approvals",
            body="User approved ROADMAP.md.",
        )
        body = Path(result["path"]).read_text()
        self.assertIn("**Kind:** approval", body)
        self.assertIn("**Route:** peers", body)

    def test_settings_egress_routes_override_defaults(self):
        server.SETTINGS_PATH.write_text(json.dumps({
            "egress": {"routes": {
                "launch": "release-coordinator",
                "handoff": "peer-review",
            }},
        }))
        result = egress.stage_egress(
            self.proj(), kind="launch", topic="Go", body="Ship it.")
        self.assertIn("**Route:** release-coordinator",
                      Path(result["path"]).read_text())
        result2 = egress.stage_egress(
            self.proj(), kind="handoff", topic="Note", body="hi")
        self.assertIn("**Route:** peer-review", Path(result2["path"]).read_text())

    def test_register_project_seeds_outbound(self):
        folder = self.tmp / "notes"
        folder.mkdir()
        proj = server.register_project("My Notes", str(folder))
        readme = folder / ".kettle" / "outbound" / "README.md"
        self.assertTrue(readme.is_file())
        self.assertEqual(proj["id"], "my_notes")


if __name__ == "__main__":
    unittest.main()
