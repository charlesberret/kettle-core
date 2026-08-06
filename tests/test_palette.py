"""Product palette stays aligned with the builtin kettle theme in themes.js."""

from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PALETTE_PATH = ROOT / "kettle" / "static" / "kettle-palette.json"
THEMES_PATH = ROOT / "kettle" / "static" / "themes.js"


def _extract_kettle_pack_arrays(themes_src: str) -> tuple[list[str], list[str]]:
    """Return (dark_ansi16, light_ansi16) hex lists from BUILTIN_THEMES.kettle."""
    m = re.search(
        r"kettle:\s*\{\s*label:\s*'Kettle',\s*"
        r"dark:\s*pack\(\s*\[([^\]]+)\]\s*,[\s\S]*?"
        r"light:\s*pack\(\s*\[([^\]]+)\]",
        themes_src,
    )
    if not m:
        raise AssertionError("could not find kettle dark/light pack arrays in themes.js")

    def parse_hexes(blob: str) -> list[str]:
        return [h.lower() for h in re.findall(r"'*(#[0-9a-fA-F]{6})'*", blob)]

    dark = parse_hexes(m.group(1))
    light = parse_hexes(m.group(2))
    if len(dark) != 16 or len(light) != 16:
        raise AssertionError(f"expected 16 hexes each; got dark={len(dark)} light={len(light)}")
    return dark, light


class KettlePalette(unittest.TestCase):
    def test_palette_schema(self):
        data = json.loads(PALETTE_PATH.read_text(encoding="utf-8"))
        self.assertEqual(data["id"], "kettle")
        self.assertEqual(data["schema_version"], 1)
        self.assertEqual(len(data["ansi_labels"]), 16)
        for mode in ("dark", "light"):
            block = data[mode]
            self.assertEqual(len(block["ansi"]), 16)
            for key, idx in block["iface"].items():
                self.assertIsInstance(idx, int, key)
                self.assertGreaterEqual(idx, 0)
                self.assertLessEqual(idx, 15)
            for key, idx in block["slots"].items():
                self.assertIsInstance(idx, int, key)
                self.assertGreaterEqual(idx, 0)
                self.assertLessEqual(idx, 15)
            # Readable sitting: bg and fg must differ.
            self.assertNotEqual(block["ansi"][block["iface"]["bg"]], block["ansi"][block["iface"]["fg"]])

    def test_themes_js_kettle_matches_palette(self):
        data = json.loads(PALETTE_PATH.read_text(encoding="utf-8"))
        themes_src = THEMES_PATH.read_text(encoding="utf-8")
        dark, light = _extract_kettle_pack_arrays(themes_src)
        self.assertEqual(dark, [h.lower() for h in data["dark"]["ansi"]])
        self.assertEqual(light, [h.lower() for h in data["light"]["ansi"]])

    def test_light_iface_uses_ink_on_paper(self):
        """Light mode must map bg→paper (ansi-0) and fg→ink (ansi-7), not the inverse."""
        themes_src = THEMES_PATH.read_text(encoding="utf-8")
        m = re.search(r"const IFACE_LIGHT = \{([^}]+)\}", themes_src)
        self.assertIsNotNone(m)
        body = m.group(1)
        self.assertIn("bg: '--ansi-0'", body)
        self.assertIn("fg: '--ansi-7'", body)

    def test_light_slots_use_ink_not_paper(self):
        """Text slots in light mode must use ink (ansi-7), not paper (ansi-0).

        A prior bug mapped agent/ctx* to --ansi-0, making prose invisible on light canvases.
        """
        themes_src = THEMES_PATH.read_text(encoding="utf-8")
        m = re.search(r"const SLOTS_LIGHT = \{([^}]+)\}", themes_src)
        self.assertIsNotNone(m, "SLOTS_LIGHT missing from themes.js")
        body = m.group(1)
        for role in ("ctxhead", "ctxbody", "cmthead", "agent"):
            # role: '--ansi-N' — must not be paper
            rm = re.search(rf"{role}:\s*'--ansi-(\d+)'", body)
            self.assertIsNotNone(rm, f"SLOTS_LIGHT missing {role}")
            idx = int(rm.group(1))
            self.assertNotEqual(
                idx, 0,
                f"SLOTS_LIGHT.{role} maps to paper (ansi-0); use ink (ansi-7)",
            )
            self.assertEqual(idx, 7, f"SLOTS_LIGHT.{role} should be ink (ansi-7), got {idx}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
