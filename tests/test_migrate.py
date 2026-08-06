#!/usr/bin/env python3
"""Tests for kettle migrate (.setsweep/ → .kettle/, dry-run vs apply)."""

from __future__ import annotations

import io
import json
import os
import shutil
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

import kettle.cli as cli
import kettle.migrate as migrate
import kettle.server as server


class MigrateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="kettle-migrate-"))
        self.registry = self.tmp / "projects.json"
        self.registry.write_text('{"projects": []}')
        self.settings = self.tmp / "settings.json"
        self._cwd = Path.cwd()
        self._saved = {name: getattr(server, name) for name in (
            "PROJECTS_PATH", "SETTINGS_PATH", "BASE_ALLOWED_ROOTS", "HOME",
        )}
        self._env = os.environ.get("DESK_PROJECTS")
        os.environ["DESK_PROJECTS"] = str(self.registry)
        server.PROJECTS_PATH = self.registry
        server.SETTINGS_PATH = self.settings
        server.BASE_ALLOWED_ROOTS = [self.tmp]
        server.HOME = self.tmp

    def tearDown(self):
        os.chdir(self._cwd)
        if self._env is None:
            os.environ.pop("DESK_PROJECTS", None)
        else:
            os.environ["DESK_PROJECTS"] = self._env
        for name, value in self._saved.items():
            setattr(server, name, value)
        shutil.rmtree(self.tmp, ignore_errors=True)

    def run_cli(self, argv):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = cli.main(argv)
        return code, out.getvalue(), err.getvalue()

    def _seed_legacy_desk(self, name="notes"):
        root = self.tmp / name
        desk = root / ".setsweep"
        (desk / "runtime").mkdir(parents=True)
        (desk / "CHARTER.md").write_text("# charter\n", encoding="utf-8")
        (desk / "runtime" / "queue.json").write_text(
            json.dumps({"entries": [{"id": "a", "title": "A", "status": "pending"}]}),
            encoding="utf-8",
        )
        proj = server.register_project(name.title(), str(root))
        # register_project seeds .kettle/ — remove it so only legacy remains
        kettle = root / ".kettle"
        if kettle.exists():
            shutil.rmtree(kettle)
        self.assertTrue(desk.is_dir())
        self.assertFalse(kettle.exists())
        return proj, root, desk

    def test_dry_run_default_does_not_write(self):
        proj, root, desk = self._seed_legacy_desk()
        code, out, err = self.run_cli(["migrate"])
        self.assertEqual((code, err), (0, ""))
        self.assertIn("dry-run", out)
        self.assertIn("pass --apply", out)
        self.assertIn(str(desk), out)
        self.assertIn(str(root / ".kettle"), out)
        self.assertTrue(desk.is_dir())
        self.assertFalse((root / ".kettle").exists())
        # desk_dir still resolves to legacy
        self.assertEqual(server.desk_dir(server.get_project(proj["id"])), desk.resolve())

    def test_apply_happy_path_renames_desk(self):
        proj, root, desk = self._seed_legacy_desk("happy")
        queue_body = (desk / "runtime" / "queue.json").read_text(encoding="utf-8")
        code, out, err = self.run_cli(["migrate", "--apply"])
        self.assertEqual((code, err), (0, ""))
        self.assertIn("applied", out)
        self.assertFalse(desk.exists())
        kettle = root / ".kettle"
        self.assertTrue(kettle.is_dir())
        self.assertTrue((kettle / "CHARTER.md").is_file())
        self.assertEqual(
            (kettle / "runtime" / "queue.json").read_text(encoding="utf-8"),
            queue_body,
        )
        live = server.get_project(proj["id"])
        self.assertEqual(server.desk_dir(live), kettle.resolve())
        self.assertFalse((root / ".setsweep").exists())

    def test_split_desk_refused_on_dry_run_and_apply(self):
        root = self.tmp / "split"
        root.mkdir()
        for name in (".kettle", ".setsweep"):
            d = root / name / "runtime"
            d.mkdir(parents=True)
            (d / "queue.json").write_text(
                json.dumps({"entries": []}), encoding="utf-8",
            )
        # Bypass register_project seeding: write registry directly
        proj = {"id": "split", "name": "Split", "root": str(root)}
        self.registry.write_text(json.dumps({"projects": [proj]}), encoding="utf-8")

        code, out, err = self.run_cli(["migrate"])
        self.assertEqual(code, 1)
        self.assertEqual(err, "")
        self.assertIn("REFUSE", out)
        self.assertIn("split", out.lower())
        self.assertTrue((root / ".kettle").is_dir())
        self.assertTrue((root / ".setsweep").is_dir())

        code2, out2, _ = self.run_cli(["migrate", "--apply"])
        self.assertEqual(code2, 1)
        self.assertIn("blocked", out2)
        self.assertTrue((root / ".kettle").is_dir())
        self.assertTrue((root / ".setsweep").is_dir())

    def test_project_filter_and_already_kettle_skip(self):
        legacy_proj, legacy_root, _ = self._seed_legacy_desk("legacy-one")
        kettle_root = self.tmp / "modern"
        kettle_root.mkdir()
        modern = server.register_project("Modern", str(kettle_root))
        self.assertTrue((kettle_root / ".kettle").is_dir())

        code, out, err = self.run_cli(["migrate", modern["id"]])
        self.assertEqual((code, err), (0, ""))
        self.assertIn("already using .kettle/", out)
        self.assertTrue((legacy_root / ".setsweep").is_dir())  # untouched

        code2, out2, err2 = self.run_cli(["migrate", "--apply", legacy_proj["id"]])
        self.assertEqual((code2, err2), (0, ""))
        self.assertTrue((legacy_root / ".kettle").is_dir())
        self.assertFalse((legacy_root / ".setsweep").exists())

    def test_registry_move_dry_run_and_apply(self):
        """Legacy user registry migrates when DESK_PROJECTS is unset."""
        home = self.tmp / "home"
        xdg = home / "xdg"
        legacy_dir = xdg / "setsweep"
        kettle_dir = xdg / "kettle"
        legacy_dir.mkdir(parents=True)
        legacy_reg = legacy_dir / "projects.json"
        legacy_settings = legacy_dir / "settings.json"
        legacy_reg.write_text('{"projects": []}', encoding="utf-8")
        legacy_settings.write_text('{"theme": "kettle"}', encoding="utf-8")

        # Clear override so plan_registry sees a real legacy path
        os.environ.pop("DESK_PROJECTS", None)
        with mock.patch.object(server, "HOME", home), \
             mock.patch.dict(os.environ, {"XDG_CONFIG_HOME": str(xdg)}, clear=False):
            # Re-point for clarity in assertions
            kettle_path = server.user_projects_path()
            legacy_path = server.legacy_user_projects_path()
            self.assertEqual(legacy_path, legacy_reg)
            self.assertEqual(kettle_path, kettle_dir / "projects.json")

            plan = migrate.run_migrate(
                apply=False,
                include_registry=True,
                kettle_registry=kettle_path,
                legacy_registry=legacy_path,
            )
            kinds = {a.kind for a in plan.actions}
            self.assertIn("registry-move", kinds)
            self.assertTrue(legacy_reg.is_file())
            self.assertFalse(kettle_path.exists())

            plan2 = migrate.run_migrate(
                apply=True,
                include_registry=True,
                kettle_registry=kettle_path,
                legacy_registry=legacy_path,
            )
            self.assertTrue(plan2.applied)
            self.assertTrue(kettle_path.is_file())
            self.assertFalse(legacy_reg.exists())
            self.assertTrue((kettle_dir / "settings.json").is_file())
            self.assertFalse(legacy_settings.exists())

    def test_help_lists_migrate(self):
        code, out, err = self.run_cli(["--help"])
        self.assertEqual((code, err), (0, ""))
        self.assertIn("migrate", out)
        code2, out2, err2 = self.run_cli(["migrate", "--help"])
        self.assertEqual((code2, err2), (0, ""))
        self.assertIn("--apply", out2)
        self.assertIn("dry-run", out2.lower())


if __name__ == "__main__":
    unittest.main()
