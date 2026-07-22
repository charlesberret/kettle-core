#!/usr/bin/env python3
"""Shared UI copy must stay aligned across web (core) and plugin Desk.

Canonical: static/ui-copy.js
Mirror:    ../setsweep-plugin/packages/vscode/src/uiCopy.ts (if present)
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CORE_JS = ROOT / "static" / "ui-copy.js"
PLUGIN_TS = (
    ROOT.parent / "setsweep-plugin" / "packages" / "vscode" / "src" / "uiCopy.ts"
)

# Keys every sitting surface must define
REQUIRED = {
    "streamIdle",
    "chatPlaceholder",
    "chatPlaceholderFounding",
    "chatPlaceholderProposing",
    "editorPlaceholder",
    "commentPlaceholder",
    "foundingQueueHintTitle",
    "foundingQueueHintBody",
    "addProjectStart",
}


def _keys_from_js(text: str) -> dict[str, str]:
    """Parse simple key: "value" pairs from the COPY object (not a full JS parser)."""
    out: dict[str, str] = {}
    for m in re.finditer(
        r"^\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*:\s*\"((?:\\.|[^\"\\])*)\"",
        text,
        re.M,
    ):
        out[m.group(1)] = m.group(2).encode("utf-8").decode("unicode_escape")
    # multi-line string concat: key: "a" + "b"
    for m in re.finditer(
        r"^\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*:\s*((?:\"(?:\\.|[^\"\\])*\"\s*\+\s*)+\"(?:\\.|[^\"\\])*\")",
        text,
        re.M,
    ):
        parts = re.findall(r"\"((?:\\.|[^\"\\])*)\"", m.group(2))
        out[m.group(1)] = "".join(
            p.encode("utf-8").decode("unicode_escape") for p in parts
        )
    return out


def _keys_from_ts(text: str) -> dict[str, str]:
    return _keys_from_js(text)


class UiCopyCatalog(unittest.TestCase):
    def test_core_ui_copy_exists_with_required_keys(self):
        self.assertTrue(CORE_JS.is_file(), f"missing {CORE_JS}")
        keys = _keys_from_js(CORE_JS.read_text(encoding="utf-8"))
        missing = REQUIRED - set(keys)
        self.assertFalse(missing, f"core ui-copy missing keys: {missing}")
        self.assertEqual(keys.get("streamIdle"), "Chat stream idle")
        self.assertIn("Setsweep agent", keys.get("chatPlaceholder", ""))

    def test_plugin_mirror_matches_when_present(self):
        if not PLUGIN_TS.is_file():
            self.skipTest("plugin tree not checked out next to core")
        core = _keys_from_js(CORE_JS.read_text(encoding="utf-8"))
        plugin = _keys_from_ts(PLUGIN_TS.read_text(encoding="utf-8"))
        self.assertEqual(
            set(core),
            set(plugin),
            "ui-copy key sets differ between core and plugin — update both files",
        )
        for k in sorted(core):
            self.assertEqual(
                core[k],
                plugin[k],
                f"ui-copy mismatch for {k!r}:\n  core:   {core[k]!r}\n  plugin: {plugin[k]!r}",
            )


if __name__ == "__main__":
    unittest.main()
