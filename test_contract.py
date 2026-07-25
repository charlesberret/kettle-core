"""Contract identity and family-check metadata tests."""

from __future__ import annotations

import json
import sys
import tempfile
import tomllib
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import setsweep_contract

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "tools"))
import check_family  # noqa: E402


class ContractIdentity(unittest.TestCase):
    def test_core_version_is_single_sourced_from_pyproject(self):
        with (ROOT / "pyproject.toml").open("rb") as fp:
            expected = str(tomllib.load(fp)["project"]["version"])
        self.assertEqual(setsweep_contract.core_version(), expected)
        self.assertEqual(setsweep_contract.identity()["version"], expected)

    def test_contract_versions_are_nonnegative_integers(self):
        identity = setsweep_contract.identity()
        for key in ("api_version", "desk_schema_version"):
            self.assertIs(type(identity[key]), int)
            self.assertGreaterEqual(identity[key], 0)

    def test_family_parser_accepts_both_manifest_key_styles(self):
        with tempfile.TemporaryDirectory() as tmp:
            snake = Path(tmp) / "snake.json"
            snake.write_text(
                json.dumps({"api_versions": [0], "desk_schema_versions": [0]}),
                encoding="utf-8",
            )
            camel = Path(tmp) / "camel.json"
            camel.write_text(
                json.dumps({"apiVersions": [0], "deskSchemaVersions": [0]}),
                encoding="utf-8",
            )
            self.assertEqual(check_family.compatibility_support(snake), ({0}, {0}))
            self.assertEqual(check_family.compatibility_support(camel), ({0}, {0}))

    def test_family_parser_rejects_coerced_or_boolean_versions(self):
        with tempfile.TemporaryDirectory() as tmp:
            for value in ("0", True, -1):
                path = Path(tmp) / f"invalid-{value!s}.json"
                path.write_text(
                    json.dumps(
                        {"api_versions": [value], "desk_schema_versions": [0]}
                    ),
                    encoding="utf-8",
                )
                with self.subTest(value=value), self.assertRaises(ValueError):
                    check_family.compatibility_support(path)

    def test_family_parser_reads_literal_core_contracts(self):
        repo = check_family.Repo("core", ROOT, (sys.executable, "-m", "pytest"))
        self.assertEqual(
            check_family.contract_versions(repo),
            (
                setsweep_contract.API_VERSION,
                setsweep_contract.DESK_SCHEMA_VERSION,
            ),
        )


class FamilyCheckCommand(unittest.TestCase):
    def make_family(self, root: Path, *, plugin_api=0):
        core = root / "setsweep-core"
        desktop = root / "setsweep-desktop"
        plugin = root / "setsweep-plugin"
        (plugin / "packages" / "vscode").mkdir(parents=True)
        desktop.mkdir()
        core.mkdir()
        (core / "pyproject.toml").write_text(
            '[project]\nname = "setsweep"\nversion = "0.2.0"\n',
            encoding="utf-8",
        )
        (core / "setsweep_contract.py").write_text(
            "API_VERSION = 0\nDESK_SCHEMA_VERSION = 0\n",
            encoding="utf-8",
        )
        (desktop / "package.json").write_text(
            json.dumps({"version": "0.1.0"}), encoding="utf-8"
        )
        (desktop / "setsweep-compatibility.json").write_text(
            json.dumps({"apiVersions": [0], "deskSchemaVersions": [0]}),
            encoding="utf-8",
        )
        (plugin / "packages" / "vscode" / "package.json").write_text(
            json.dumps({"version": "0.6.65"}), encoding="utf-8"
        )
        (plugin / "packages" / "vscode" / "setsweep-compatibility.json").write_text(
            json.dumps(
                {
                    "api_versions": [plugin_api],
                    "desk_schema_versions": [0],
                }
            ),
            encoding="utf-8",
        )
        return SimpleNamespace(
            core=core,
            desktop=desktop,
            plugin=plugin,
            require_clean=False,
            run_tests=False,
        )

    def run_main(self, args, *, dirty=False):
        out, err = StringIO(), StringIO()
        with (
            mock.patch.object(check_family, "parse_args", return_value=args),
            mock.patch.object(check_family, "is_checkout", return_value=True),
            mock.patch.object(
                check_family,
                "status_line",
                side_effect=lambda repo, version: f"{repo.name} {version}",
            ),
            mock.patch.object(check_family, "dirty", return_value=dirty),
            redirect_stdout(out),
            redirect_stderr(err),
        ):
            code = check_family.main()
        return code, out.getvalue(), err.getvalue()

    def test_family_main_reports_both_viewports_compatible(self):
        with tempfile.TemporaryDirectory() as tmp:
            args = self.make_family(Path(tmp))
            code, out, err = self.run_main(args)
        self.assertEqual(code, 0, err)
        self.assertIn("desktop  api=[0], desk=[0] => compatible", out)
        self.assertIn("plugin   api=[0], desk=[0] => compatible", out)

    def test_family_main_rejects_incompatible_or_dirty_release(self):
        with tempfile.TemporaryDirectory() as tmp:
            args = self.make_family(Path(tmp), plugin_api=1)
            code, out, _ = self.run_main(args)
            self.assertEqual(code, 1)
            self.assertIn("INCOMPATIBLE", out)

            args.require_clean = True
            code, _, err = self.run_main(args, dirty=True)
            self.assertEqual(code, 1)
            self.assertIn("clean-tree gate failed", err)

    def test_family_main_reports_missing_checkout(self):
        with tempfile.TemporaryDirectory() as tmp:
            args = self.make_family(Path(tmp))
            out, err = StringIO(), StringIO()
            with (
                mock.patch.object(check_family, "parse_args", return_value=args),
                mock.patch.object(check_family, "is_checkout", return_value=False),
                redirect_stdout(out),
                redirect_stderr(err),
            ):
                code = check_family.main()
        self.assertEqual(code, 2)
        self.assertIn("missing Setsweep Git checkouts", err.getvalue())


if __name__ == "__main__":
    unittest.main()
