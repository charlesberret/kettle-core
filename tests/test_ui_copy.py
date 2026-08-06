#!/usr/bin/env python3
"""Shared UI copy must stay aligned across web (core) and VS Code Desk.

Canonical: static/ui-copy.js
Mirror:    ../kettle-vscode/src/uiCopy.ts (if present)
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORE_JS = ROOT / "kettle" / "static" / "ui-copy.js"
VSCODE_TS = ROOT.parent / "kettle-vscode" / "src" / "uiCopy.ts"

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
        self.assertIn("Kettle agent", keys.get("chatPlaceholder", ""))

    def test_vscode_mirror_matches_when_present(self):
        if not VSCODE_TS.is_file():
            self.skipTest("VS Code tree not checked out next to core")
        core = _keys_from_js(CORE_JS.read_text(encoding="utf-8"))
        vscode = _keys_from_ts(VSCODE_TS.read_text(encoding="utf-8"))
        self.assertEqual(
            set(core),
            set(vscode),
            "ui-copy key sets differ between core and VS Code - update both files",
        )
        for k in sorted(core):
            self.assertEqual(
                core[k],
                vscode[k],
                f"ui-copy mismatch for {k!r}:\n  core:   {core[k]!r}\n  vscode: {vscode[k]!r}",
            )


if __name__ == "__main__":
    unittest.main()
