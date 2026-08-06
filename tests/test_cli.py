#!/usr/bin/env python3
"""Tests for the serverless CLI viewport.

Stdlib unittest fixtures only. Like test_server.py, this module redirects server globals
into a tempdir and must run serially.
"""

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
import kettle.server as server


class CliTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="kettle-cli-"))
        self.registry = self.tmp / "projects.json"
        self.registry.write_text('{"projects": []}')
        self.settings = self.tmp / "settings.json"
        self._cwd = Path.cwd()
        self._saved = {name: getattr(server, name) for name in (
            "PROJECTS_PATH", "SETTINGS_PATH", "BASE_ALLOWED_ROOTS", "HOME", "CLAUDE",
        )}
        server.PROJECTS_PATH = self.registry
        server.SETTINGS_PATH = self.settings
        server.BASE_ALLOWED_ROOTS = [self.tmp]
        server.HOME = self.tmp
        server.CLAUDE = "claude-test"

    def tearDown(self):
        os.chdir(self._cwd)
        for name, value in self._saved.items():
            setattr(server, name, value)
        shutil.rmtree(self.tmp, ignore_errors=True)

    def run_cli(self, argv):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = cli.main(argv)
        return code, out.getvalue(), err.getvalue()

    def register(self, name="Desk"):
        root = self.tmp / name.lower().replace(" ", "-")
        root.mkdir()
        return server.register_project(name, str(root))

    def test_projects_add_and_list(self):
        code0, out0, _ = self.run_cli(["projects"])
        self.assertEqual(code0, 0)
        self.assertIn("no desks registered", out0)

        root = self.tmp / "notes"
        root.mkdir()
        code1, out1, err1 = self.run_cli(["add", str(root), "--name", "My Notes"])
        self.assertEqual((code1, err1), (0, ""))
        self.assertIn("registered [my_notes]", out1)
        self.assertTrue((root / ".kettle" / "runtime" / "queue.json").is_file())

        code2, out2, _ = self.run_cli(["projects"])
        self.assertEqual(code2, 0)
        self.assertIn("my_notes", out2)
        self.assertIn(str(root), out2)

    def test_init_registers_current_directory(self):
        root = self.tmp / "current-project"
        root.mkdir()
        os.chdir(root)
        code, out, err = self.run_cli(["init", "--name", "Current Project"])
        self.assertEqual((code, err), (0, ""))
        self.assertIn("registered [current_project]", out)
        self.assertEqual(server.project_root(server.get_project("current_project")).resolve(),
                         root.resolve())

    def test_queue_renders_entries(self):
        proj = self.register()
        target = Path(proj["root"]) / "draft.md"
        target.write_text("draft")
        server.atomic_write(server.queue_path(proj), json.dumps({
            "curated": "test",
            "entries": [{
                "id": "draft", "title": "Read draft", "path": str(target),
                "status": "pending", "ask": "Approve it", "brief": "Read closely.",
            }],
        }))
        code, out, _ = self.run_cli(["queue", proj["id"]])
        self.assertEqual(code, 0)
        self.assertIn("[draft] Read draft", out)
        self.assertIn("ask:   Approve it", out)
        self.assertIn("brief: Read closely.", out)

    def test_themes_lists_marquee_kettle(self):
        code, out, err = self.run_cli(["themes"])
        self.assertEqual((code, err), (0, ""))
        self.assertIn("kettle", out)
        self.assertIn("marquee", out.lower() + out)  # header or marker
        self.assertIn("default", out)

    def test_open_uses_builtin_editor(self):
        proj = self.register()
        target = Path(proj["root"]) / "draft.md"
        target.write_text("hello")
        server.atomic_write(server.queue_path(proj), json.dumps({
            "curated": "test",
            "entries": [{
                "id": "draft", "title": "Draft", "path": str(target),
                "status": "pending", "brief": "Check it", "ask": "ok?",
            }],
        }))
        with mock.patch("tui_editor.edit_file", return_value=0) as edit:
            code, out, err = self.run_cli(["open", proj["id"], "draft"])
        self.assertEqual((code, err), (0, ""))
        self.assertIn("built-in editor", out)
        edit.assert_called_once()
        self.assertEqual(Path(edit.call_args.args[0]), target)

    def test_open_external_uses_editor_env(self):
        proj = self.register()
        target = Path(proj["root"]) / "draft.md"
        target.write_text("hello")
        server.atomic_write(server.queue_path(proj), json.dumps({
            "curated": "test",
            "entries": [{"id": "draft", "path": str(target), "status": "pending"}],
        }))
        with mock.patch.dict(os.environ, {"EDITOR": "true"}), \
                mock.patch("cli.subprocess.call", return_value=0) as call:
            code, out, _ = self.run_cli(["open", proj["id"], "draft", "--external"])
        self.assertEqual(code, 0)
        self.assertIn("opening", out)
        call.assert_called_once()
        self.assertEqual(call.call_args.args[0][0], "true")

    def test_edit_alias_and_tty_fallback(self):
        proj = self.register()
        target = Path(proj["root"]) / "draft.md"
        target.write_text("hello")
        server.atomic_write(server.queue_path(proj), json.dumps({
            "curated": "test",
            "entries": [{"id": "draft", "path": str(target), "status": "pending"}],
        }))
        # edit_file returns 3 → no tty → external fallback
        with mock.patch("tui_editor.edit_file", return_value=3), \
                mock.patch("cli.subprocess.call", return_value=0) as call:
            code, out, err = self.run_cli(["edit", proj["id"], "draft"])
        self.assertEqual(code, 0)
        self.assertIn("no tty", err)
        call.assert_called_once()

    def test_egress_and_status(self):
        proj = self.register()
        code, out, err = self.run_cli([
            "egress", proj["id"], "--kind", "handoff", "--topic", "Next desk",
            "--body", "Carry this context.",
        ])
        self.assertEqual((code, err), (0, ""))
        staged = json.loads(out)
        self.assertEqual(staged["status"], "staged")
        self.assertTrue(Path(staged["path"]).is_file())

        code2, out2, _ = self.run_cli(["egress-status", proj["id"]])
        self.assertEqual(code2, 0)
        status = json.loads(out2)
        self.assertEqual(status["project"], proj["id"])
        self.assertEqual(len(status["staged"]), 1)

    def test_found_hands_provider_built_cmd_to_runtime(self):
        proj = self.register()
        captured = []

        class FakeRuntime:
            def __init__(self, command, sessions_dir, provider="claude"):
                captured.append({"command": command, "sessions_dir": Path(sessions_dir),
                                 "provider": provider})

            def spawn(self, prompt, **kwargs):
                captured[-1].update(prompt=prompt, **kwargs)
                yield {"t": "model", "session": "sid-cli"}
                yield {"t": "done", "usage": {}, "cost": 0}

        with mock.patch.object(cli.runtime, "Runtime", FakeRuntime):
            code, _, _ = self.run_cli(["found", proj["id"], "--model", "opus"])
        self.assertEqual(code, 0)
        call = captured[0]
        # Provider resolved from settings (default claude); the full argv is single-sourced
        # through build_turn_cmd and handed to spawn as cmd=, not extra=.
        self.assertEqual(call["provider"], "claude")
        self.assertEqual(call["role"], "found")
        self.assertEqual(Path(call["cwd"]).resolve(), Path(proj["root"]).resolve())
        cmd = call["cmd"]
        self.assertEqual(cmd[0], server.agent_bin())
        self.assertIn("--model", cmd)
        self.assertEqual(cmd[cmd.index("--model") + 1], "opus")
        self.assertIn("--name", cmd)                      # first turn names the session
        self.assertIn("--permission-mode", cmd)           # sweep tier is write-armed
        self.assertIn("acceptEdits", cmd)

    def test_chat_hands_context_and_tool_tier_to_runtime(self):
        proj = self.register()
        target = Path(proj["root"]) / "draft.md"
        target.write_text("draft")
        server.atomic_write(server.queue_path(proj), json.dumps({
            "curated": "test",
            "entries": [{
                "id": "draft", "path": str(target), "status": "pending",
                "brief": "Assess structure", "ask": "Recommend edits",
            }],
        }))
        captured = []

        class FakeRuntime:
            def __init__(self, command, sessions_dir, provider="claude"):
                captured.append({"command": command, "sessions_dir": Path(sessions_dir),
                                 "provider": provider})

            def spawn(self, prompt, **kwargs):
                captured[-1].update(prompt=prompt, **kwargs)
                yield {"t": "model", "session": "sid-chat"}
                yield {"t": "done", "usage": {}, "cost": 0}

        answers = iter(["hello", ":q"])
        with mock.patch.object(cli.runtime, "Runtime", FakeRuntime), \
                mock.patch("builtins.input", side_effect=lambda _prompt="": next(answers)):
            code, _, _ = self.run_cli(["chat", proj["id"], "draft", "--model", "sonnet"])
        self.assertEqual(code, 0)
        call = captured[0]
        self.assertEqual(call["role"], "chat")
        self.assertEqual(call["provider"], "claude")
        self.assertIn("[Active file:", call["prompt"])
        self.assertIn("Assess structure", call["prompt"])
        cmd = call["cmd"]
        self.assertIn("--append-system-prompt", cmd)
        self.assertIn("--name", cmd)
        self.assertIn("--model", cmd)
        self.assertEqual(cmd[cmd.index("--model") + 1], "sonnet")

    def test_chat_builds_grok_argv_when_provider_is_grok(self):
        """Gate for brief 03: a grok curator config makes `kettle chat` build Grok
        dialect argv (no Claude hardcoding), single-sourced through build_turn_cmd."""
        self.settings.write_text(json.dumps({
            "curator": {
                "provider": "grok",
                "command": "grok",
                "models": {"setup": "grok-4.5", "chat": "grok-4.5"},
            },
        }))
        proj = self.register()
        target = Path(proj["root"]) / "draft.md"
        target.write_text("draft")
        server.atomic_write(server.queue_path(proj), json.dumps({
            "curated": "test",
            "entries": [{
                "id": "draft", "path": str(target), "status": "pending",
                "brief": "Assess structure", "ask": "Recommend edits",
            }],
        }))
        captured = []

        class FakeRuntime:
            def __init__(self, command, sessions_dir, provider="claude"):
                captured.append({"command": command, "sessions_dir": Path(sessions_dir),
                                 "provider": provider})

            def spawn(self, prompt, **kwargs):
                captured[-1].update(prompt=prompt, **kwargs)
                yield {"t": "model", "session": "sid-grok"}
                yield {"t": "done", "usage": {}, "cost": 0}

        answers = iter(["hello", ":q"])
        with mock.patch.object(cli.runtime, "Runtime", FakeRuntime), \
                mock.patch("builtins.input", side_effect=lambda _prompt="": next(answers)):
            code, _, _ = self.run_cli(["chat", proj["id"], "draft"])
        self.assertEqual(code, 0)
        call = captured[0]
        self.assertEqual(call["provider"], "grok")
        cmd = call["cmd"]
        # Grok dialect: streaming-json, --rules (not --append-system-prompt), --allow
        # Bash (not Claude's --allowedTools), no --name, and the grok model.
        self.assertIn("streaming-json", cmd)
        self.assertNotIn("--verbose", cmd)
        self.assertIn("--rules", cmd)
        self.assertNotIn("--append-system-prompt", cmd)
        self.assertIn("--allow", cmd)
        self.assertNotIn("--allowedTools", cmd)
        self.assertNotIn("--name", cmd)
        self.assertIn("grok-4.5", cmd)

    def test_install_doctor_flags_stale_mapping_and_path_extras(self):
        """Brief 20: doctor catches PATH strays and top_level missing the kettle package."""
        canon = Path("/tmp/fake-venv/bin/kettle")
        rows = cli.install_doctor_checks(
            path_hits=[
                Path("/opt/homebrew/bin/kettle"),
                Path("/Users/me/.local/bin/kettle"),
            ],
            package_modules=["kettle", "kettle.cli", "kettle.server"],
            top_level=["cli", "server"],  # flat leftovers — missing kettle package
            canonical=canon,
        )
        by_name = {r["name"]: r for r in rows}
        self.assertIn("python-version", by_name)
        self.assertIn("package-version", by_name)
        self.assertFalse(by_name["kettle-on-path"]["ok"])
        self.assertFalse(by_name["kettle-path-extras"]["ok"])
        self.assertIn("extra on PATH", by_name["kettle-path-extras"]["detail"])
        self.assertFalse(by_name["install-mapping"]["ok"])
        self.assertIn("kettle", by_name["install-mapping"]["detail"])
        # Real modules remain importable in this process even when top_level is stale.
        self.assertTrue(by_name["py-modules-importable"]["ok"])

    def test_install_doctor_accepts_package_top_level(self):
        """Wheel/editable installs list only the kettle package in top_level.txt."""
        rows = cli.install_doctor_checks(
            path_hits=[cli.CANONICAL_KETTLE],
            package_modules=["kettle", "kettle.cli", "kettle.server"],
            top_level=["kettle"],
            canonical=cli.CANONICAL_KETTLE,
        )
        by_name = {r["name"]: r for r in rows}
        self.assertTrue(by_name["py-modules-list"]["ok"])
        self.assertIn("PACKAGE_MODULES", by_name["py-modules-list"]["detail"])
        self.assertTrue(by_name["install-mapping"]["ok"])

    def test_install_doctor_green_when_canonical_and_mapped(self):
        modules = cli._package_modules()
        self.assertIn("kettle.egress", modules)
        rows = cli.install_doctor_checks(
            path_hits=[cli.CANONICAL_KETTLE],
            package_modules=modules,
            top_level=["kettle"],
            canonical=cli.CANONICAL_KETTLE,
        )
        self.assertTrue(all(r["ok"] for r in rows), rows)
        code, out, err = self.run_cli(["doctor"])
        # Live PATH may have strays — command must run and print a table either way.
        self.assertIn(code, (0, 1))
        self.assertEqual(err, "")
        self.assertIn("kettle-on-path", out)
        self.assertIn("py-modules-importable", out)
        self.assertIn("provider-cli", out)
        self.assertIn("registry", out)
        self.assertIn("desk-integrity", out)
        self.assertIn("server-reachable", out)

    def test_desk_doctor_flags_corrupt_registry_and_queue(self):
        """Broken scratch registry / queue.json turn the matching doctor rows red."""
        bad_reg = self.tmp / "broken-projects.json"
        bad_reg.write_text("{not-json", encoding="utf-8")
        rows = cli.desk_doctor_checks(
            registry_path=bad_reg,
            registry_data=None,
            registry_error="invalid JSON: Expecting property name",
        )
        by_name = {r["name"]: r for r in rows}
        self.assertFalse(by_name["registry"]["ok"])
        self.assertIn("INSTALL.md", by_name["registry"]["docs"])

        root = self.tmp / "scratch-desk"
        root.mkdir()
        desk = root / ".kettle"
        (desk / "runtime").mkdir(parents=True)
        (desk / "runtime" / "queue.json").write_text("not-json", encoding="utf-8")
        proj = {"id": "scratch", "name": "Scratch", "root": str(root)}
        rows2 = cli.desk_doctor_checks(
            projects=[proj],
            registry_path=self.registry,
            registry_data={"projects": [proj]},
            registry_error=None,
        )
        by2 = {r["name"]: r for r in rows2}
        self.assertTrue(by2["registry"]["ok"])
        self.assertFalse(by2["desk-integrity"]["ok"])
        self.assertIn("queue.json", by2["desk-integrity"]["detail"])
        self.assertIn("ARCHITECTURE.md", by2["desk-integrity"]["docs"])

    def test_desk_doctor_legacy_hint_and_split_failure(self):
        legacy_root = self.tmp / "legacy-only"
        legacy_root.mkdir()
        (legacy_root / ".setsweep" / "runtime").mkdir(parents=True)
        (legacy_root / ".setsweep" / "runtime" / "queue.json").write_text(
            json.dumps({"entries": []}), encoding="utf-8",
        )
        legacy_proj = {"id": "legacy", "name": "Legacy", "root": str(legacy_root)}
        rows = cli.desk_doctor_checks(
            projects=[legacy_proj],
            registry_path=self.registry,
            registry_data={"projects": [legacy_proj]},
            registry_error=None,
        )
        by_name = {r["name"]: r for r in rows}
        self.assertTrue(by_name["desk-integrity"]["ok"])
        self.assertTrue(by_name["legacy-migration"]["ok"])
        self.assertIn(".setsweep", by_name["legacy-migration"]["detail"])

        split_root = self.tmp / "split-desk"
        split_root.mkdir()
        for name in (".kettle", ".setsweep"):
            (split_root / name / "runtime").mkdir(parents=True)
            (split_root / name / "runtime" / "queue.json").write_text(
                json.dumps({"entries": []}), encoding="utf-8",
            )
        split_proj = {"id": "split", "name": "Split", "root": str(split_root)}
        rows2 = cli.desk_doctor_checks(
            projects=[split_proj],
            registry_path=self.registry,
            registry_data={"projects": [split_proj]},
            registry_error=None,
        )
        by2 = {r["name"]: r for r in rows2}
        self.assertFalse(by2["legacy-migration"]["ok"])
        self.assertIn("split risk", by2["legacy-migration"]["detail"])

    def test_runtime_doctor_flags_missing_provider_and_dead_server(self):
        """Missing curator CLI and stale discovery both fail with docs pointers."""
        rows = cli.runtime_doctor_checks(
            settings={"curator": {"provider": "grok", "command": "grok-not-installed-xyz"}},
            provider_ready={
                "id": "grok",
                "label": "Grok Build CLI",
                "command": "grok-not-installed-xyz",
                "command_resolved": "grok-not-installed-xyz",
                "command_exists": False,
            },
            discovery=None,
            discovery_error=None,
            ping=None,
        )
        by_name = {r["name"]: r for r in rows}
        self.assertFalse(by_name["provider-cli"]["ok"])
        self.assertIn("not on PATH", by_name["provider-cli"]["detail"])
        self.assertIn("INSTALL.md", by_name["provider-cli"]["docs"])
        self.assertTrue(by_name["server-reachable"]["ok"])  # no discovery → CLI-only ok

        rows2 = cli.runtime_doctor_checks(
            settings={"curator": {"provider": "claude", "command": "claude"}},
            provider_ready={
                "id": "claude",
                "label": "Claude Code",
                "command": "claude",
                "command_resolved": "/bin/claude",
                "command_exists": True,
            },
            discovery={"port": 59999, "pid": 1, "url": "http://127.0.0.1:59999/"},
            discovery_error=None,
            ping=None,  # injected dead ping
        )
        by2 = {r["name"]: r for r in rows2}
        self.assertTrue(by2["provider-cli"]["ok"])
        self.assertTrue(by2["runtime-discovery"]["ok"])
        self.assertFalse(by2["server-reachable"]["ok"])
        self.assertIn("stale discovery", by2["server-reachable"]["detail"])
        self.assertIn("ENGINEERING.md", by2["server-reachable"]["docs"])

    def test_doctor_checks_combines_layers_and_exits_nonzero(self):
        modules = cli._py_modules_from_pyproject()
        rows = cli.doctor_checks(
            path_hits=[cli.CANONICAL_KETTLE],
            py_modules=modules,
            top_level=list(modules),
            canonical=cli.CANONICAL_KETTLE,
            projects=[],
            registry_path=self.registry,
            registry_data={"projects": []},
            registry_error=None,
            settings={"curator": {"provider": "claude", "command": "missing-cli-zzz"}},
            provider_ready={
                "id": "claude",
                "label": "Claude Code",
                "command": "missing-cli-zzz",
                "command_resolved": "missing-cli-zzz",
                "command_exists": False,
            },
            discovery={"port": 58888, "pid": 9},
            discovery_error=None,
            ping=None,
        )
        names = [r["name"] for r in rows]
        for expected in (
            "python-version", "package-version", "kettle-on-path",
            "registry", "desk-integrity", "legacy-migration",
            "provider-cli", "runtime-discovery", "server-reachable",
        ):
            self.assertIn(expected, names)
        self.assertTrue(any(not r["ok"] for r in rows))
        with mock.patch.object(cli, "doctor_checks", return_value=rows):
            code, out, err = self.run_cli(["doctor"])
        self.assertEqual(code, 1)
        self.assertEqual(err, "")
        self.assertIn("FAIL", out)
        self.assertIn("provider-cli", out)
        self.assertIn("→", out)


if __name__ == "__main__":
    unittest.main(verbosity=2)
