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
        self.tmp = Path(tempfile.mkdtemp(prefix="setsweep-cli-"))
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
        self.assertTrue((root / ".setsweep" / "runtime" / "queue.json").is_file())

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

    def test_found_hands_current_argv_inputs_to_runtime(self):
        proj = self.register()
        captured = []

        class FakeRuntime:
            def __init__(self, command, sessions_dir):
                captured.append({"command": command, "sessions_dir": Path(sessions_dir)})

            def spawn(self, prompt, **kwargs):
                captured[-1].update(prompt=prompt, **kwargs)
                yield {"t": "model", "session": "sid-cli"}
                yield {"t": "done", "usage": {}, "cost": 0}

        with mock.patch.object(cli.runtime, "Runtime", FakeRuntime):
            code, _, _ = self.run_cli(["found", proj["id"], "--model", "opus"])
        self.assertEqual(code, 0)
        call = captured[0]
        self.assertEqual(call["command"], "claude-test")
        self.assertEqual(call["role"], "found")
        self.assertEqual(Path(call["cwd"]).resolve(), Path(proj["root"]).resolve())
        self.assertIn("--model", call["extra"])
        self.assertEqual(call["extra"][call["extra"].index("--model") + 1], "opus")
        self.assertIn("--name", call["extra"])

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
            def __init__(self, command, sessions_dir):
                captured.append({"command": command, "sessions_dir": Path(sessions_dir)})

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
        self.assertIn("[Active file:", call["prompt"])
        self.assertIn("Assess structure", call["prompt"])
        self.assertIn("--append-system-prompt", call["extra"])
        self.assertIn("--name", call["extra"])
        self.assertIn("--model", call["extra"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
