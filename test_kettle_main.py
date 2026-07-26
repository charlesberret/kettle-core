#!/usr/bin/env python3
"""Routing tests for the installed `kettle` entrypoint."""

import io
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest import mock

import cli
import server
import kettle_main


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


if __name__ == "__main__":
    unittest.main(verbosity=2)
