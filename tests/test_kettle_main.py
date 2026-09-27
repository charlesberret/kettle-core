#!/usr/bin/env python3
"""Routing tests for the installed `kettle` entrypoint."""

import io
import sys
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest import mock

import kettle.cli as cli
import kettle.server as server
import kettle.kettle_main as kettle_main


class EntrypointTest(unittest.TestCase):
    def test_help_is_side_effect_free(self):
        out = io.StringIO()
        with redirect_stdout(out):
            code = kettle_main.main(["--help"])
        self.assertEqual(code, 0)
        self.assertIn("unified entrypoint", out.getvalue())

    def test_cli_commands_dispatch_without_starting_server(self):
        with mock.patch.object(cli, "main", return_value=7) as call, \
                mock.patch.object(server, "main") as web:
            code = kettle_main.main(["queue", "desk"])
        self.assertEqual(code, 7)
        call.assert_called_once_with(["queue", "desk"])
        web.assert_not_called()

    def test_doctor_dispatches_to_cli(self):
        with mock.patch.object(cli, "main", return_value=0) as call, \
                mock.patch.object(server, "main") as web:
            code = kettle_main.main(["doctor"])
        self.assertEqual(code, 0)
        call.assert_called_once_with(["doctor"])
        web.assert_not_called()

    def test_refresh_briefs_dispatches_to_cli(self):
        with mock.patch.object(cli, "main", return_value=0) as call:
            code = kettle_main.main(["refresh-briefs", "desk"])
        self.assertEqual(code, 0)
        call.assert_called_once_with(["refresh-briefs", "desk"])

    def test_migrate_dispatches_to_cli(self):
        """Regression: kettle_main.CLI_CMDS used to be a hand-written literal that
        forgot `migrate`, so `kettle migrate` exited 2 "unknown command" even though
        INSTALL.md / ROADMAP / doctor's legacy-migration hint all point users there."""
        with mock.patch.object(cli, "main", return_value=0) as call, \
                mock.patch.object(server, "main") as web:
            code = kettle_main.main(["migrate", "--apply"])
        self.assertEqual(code, 0)
        call.assert_called_once_with(["migrate", "--apply"])
        web.assert_not_called()

    def test_every_cli_subcommand_routes_through_the_cli_not_the_server(self):
        """Single-source guarantee: every name cli.py's own argparse tree dispatches
        is reachable here — kettle_main's routing table cannot drift from cli.py's."""
        names = cli.command_names()
        self.assertIn("migrate", names)
        for name in names:
            with mock.patch.object(cli, "main", return_value=0) as call, \
                    mock.patch.object(server, "main") as web:
                code = kettle_main.main([name])
            self.assertEqual(code, 0, name)
            call.assert_called_once_with([name])
            web.assert_not_called()

    def test_web_flags_dispatch_to_server(self):
        with mock.patch.object(server, "main", return_value=None) as web:
            code = kettle_main.main(["--web"])
        self.assertEqual(code, 0)
        web.assert_called_once_with()

    def test_unknown_command_is_an_error(self):
        err = io.StringIO()
        with redirect_stderr(err):
            code = kettle_main.main(["mystery"])
        self.assertEqual(code, 2)
        self.assertIn("unknown command", err.getvalue())


class ServerFlagRouting(unittest.TestCase):
    """A sidecar host (kettle-desktop) launches `kettle --port <n> --no-open` with no
    subcommand; the standalone binary is launched the same way. Leading flags belong
    to the server, not to the unknown-command path."""

    def _routes_to_server(self, argv):
        called = {}

        def fake_main():
            called["server"] = True
            return 0

        buf = io.StringIO()
        with mock.patch.object(server, "main", fake_main), redirect_stdout(buf), \
                redirect_stderr(buf):
            code = kettle_main.main(argv)
        return code, called.get("server", False)

    def test_port_and_no_open_reach_the_server(self):
        for argv in (["--port", "0"], ["--no-open"], ["--web", "--port", "0"], []):
            with self.subTest(argv=argv):
                code, hit = self._routes_to_server(argv)
                self.assertEqual(code, 0)
                self.assertTrue(hit, f"{argv} did not reach server.main()")

    def test_version_and_help_do_not_start_a_server(self):
        for argv in (["--version"], ["-V"], ["--help"]):
            with self.subTest(argv=argv):
                code, hit = self._routes_to_server(argv)
                self.assertEqual(code, 0)
                self.assertFalse(hit, f"{argv} started a server")

    def test_an_unknown_word_is_still_an_error(self):
        code, hit = self._routes_to_server(["definitely-not-a-command"])
        self.assertEqual(code, 2)
        self.assertFalse(hit)


if __name__ == "__main__":
    unittest.main(verbosity=2)
