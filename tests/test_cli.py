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

import cli
import server


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
        """Brief 20: doctor catches PATH strays and py-modules missing from top_level."""
        canon = Path("/tmp/fake-venv/bin/kettle")
        rows = cli.install_doctor_checks(
            path_hits=[
                Path("/opt/homebrew/bin/kettle"),
                Path("/Users/me/.local/bin/kettle"),
            ],
            py_modules=["cli", "server", "egress", "sweepkit"],
            top_level=["cli", "server"],  # egress + sweepkit missing → stale MAPPING
            canonical=canon,
        )
        by_name = {r["name"]: r for r in rows}
        self.assertFalse(by_name["kettle-on-path"]["ok"])
        self.assertFalse(by_name["kettle-path-extras"]["ok"])
        self.assertIn("extra on PATH", by_name["kettle-path-extras"]["detail"])
        self.assertFalse(by_name["install-mapping"]["ok"])
        self.assertIn("egress", by_name["install-mapping"]["detail"])
        self.assertIn("sweepkit", by_name["install-mapping"]["detail"])
        # Real modules remain importable in this process even when top_level is stale.
        self.assertTrue(by_name["py-modules-importable"]["ok"])

    def test_install_doctor_green_when_canonical_and_mapped(self):
        modules = cli._py_modules_from_pyproject()
        self.assertIn("egress", modules)
        rows = cli.install_doctor_checks(
            path_hits=[cli.CANONICAL_KETTLE],
            py_modules=modules,
            top_level=list(modules),
            canonical=cli.CANONICAL_KETTLE,
        )
        self.assertTrue(all(r["ok"] for r in rows), rows)
        code, out, err = self.run_cli(["doctor"])
        # Live PATH may have strays — command must run and print a table either way.
        self.assertIn(code, (0, 1))
        self.assertEqual(err, "")
        self.assertIn("kettle-on-path", out)
        self.assertIn("py-modules-importable", out)


if __name__ == "__main__":
    unittest.main(verbosity=2)
