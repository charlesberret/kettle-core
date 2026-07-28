"""Theme catalog and pack validation."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import theme_catalog


class ThemeCatalog(unittest.TestCase):
    def test_default_is_kettle_marquee(self):
        self.assertEqual(theme_catalog.default_theme_id(), "kettle")
        pack = theme_catalog.load_theme("kettle")
        self.assertTrue(pack.get("marquee"))
        self.assertEqual(len(pack["dark"]["ansi"]), 16)

    def test_list_includes_bundled(self):
        ids = theme_catalog.list_theme_ids()
        self.assertIn("kettle", ids)
        self.assertIn("nord", ids)
        self.assertIn("tokyo-night", ids)

    def test_resolve_role_hex(self):
        pack = theme_catalog.load_theme("kettle")
        bg = theme_catalog.resolve_role_hex(pack, "bg", dark=True)
        fg = theme_catalog.resolve_role_hex(pack, "fg", dark=True)
        self.assertTrue(bg.startswith("#"))
        self.assertNotEqual(bg, fg)
        # syntax aliases
        comment = theme_catalog.resolve_role_hex(pack, "comment", dark=True)
        self.assertTrue(comment.startswith("#"))

    def test_user_theme_overrides_bundled_id(self):
        pack = theme_catalog.load_theme("kettle")
        with tempfile.TemporaryDirectory() as td:
            udir = Path(td)
            custom = {
                "schema_version": 1,
                "id": "kettle",
                "label": "Custom Kettle",
                "marquee": False,
                "dark": pack["dark"],
                "light": pack["light"],
            }
            (udir / "kettle.json").write_text(json.dumps(custom), encoding="utf-8")
            with mock.patch.object(theme_catalog, "user_themes_dir", return_value=udir):
                loaded = theme_catalog.load_theme("kettle")
            self.assertEqual(loaded["label"], "Custom Kettle")
            self.assertEqual(loaded["_source"], "user")

    def test_invalid_pack_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            bad = Path(td) / "bad.json"
            bad.write_text(json.dumps({"id": "x"}), encoding="utf-8")
            with self.assertRaises(ValueError):
                theme_catalog.load_pack_file(bad)

    def test_pack_to_web_shape(self):
        pack = theme_catalog.load_theme("kettle")
        web = theme_catalog.pack_to_web(pack)
        self.assertEqual(web["id"], "kettle")
        self.assertIn("--ansi-0", web["dark"]["colors"])
        self.assertTrue(web["dark"]["iface"]["bg"].startswith("--ansi-"))
        self.assertTrue(web["dark"]["slots"]["mdhead"].startswith("--ansi-"))
        # Catalog merge must retain sitting opacity defaults (packs omit them).
        self.assertEqual(web["dark"]["ifaceOpacity"]["muted"], 58)
        self.assertEqual(web["light"]["ifaceOpacity"]["muted"], 52)
        self.assertEqual(web["light"]["slotOpacity"]["agent"], 48)
        self.assertEqual(web["light"]["slots"]["agent"], "--ansi-7")
        self.assertEqual(web["light"]["iface"]["bg"], "--ansi-0")
        self.assertEqual(web["light"]["iface"]["fg"], "--ansi-7")

    @staticmethod
    def _rel_luminance(hexv: str) -> float:
        h = hexv.lstrip("#")
        rgb = [int(h[i : i + 2], 16) / 255.0 for i in (0, 2, 4)]

        def f(c: float) -> float:
            return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

        r, g, b = (f(c) for c in rgb)
        return 0.2126 * r + 0.7152 * g + 0.0722 * b

    def test_every_bundled_pack_has_working_light_and_dark(self):
        """Standard packs ship both modes; light text uses ink; light panels stay light."""
        ids = theme_catalog.list_theme_ids()
        # kettle + classic + gruvbox + material + nord + solarized + tokyo-night
        self.assertGreaterEqual(len(ids), 7)
        self.assertNotIn("one-dark", ids)
        for tid in ids:
            pack = theme_catalog.load_theme(tid)
            if pack.get("_source") != "bundled":
                continue
            for which in ("dark", "light"):
                self.assertIn(which, pack, f"{tid} missing {which}")
                block = pack[which]
                self.assertEqual(len(block["ansi"]), 16, tid)
                iface = block.get("iface") or {}
                slots = block.get("slots") or {}
                bg_i = int(iface.get("bg", 0))
                fg_i = int(iface.get("fg", 7))
                self.assertNotEqual(
                    block["ansi"][bg_i],
                    block["ansi"][fg_i],
                    f"{tid}.{which}: bg and fg must differ",
                )
                if which == "light":
                    # Paper-in-0 / ink-in-7 convention used by themes.js and sittings.
                    self.assertEqual(bg_i, 0, f"{tid}.light.iface.bg")
                    self.assertEqual(fg_i, 7, f"{tid}.light.iface.fg")
                    for role in theme_catalog.TEXT_SLOT_KEYS:
                        idx = int(slots[role])
                        self.assertNotEqual(
                            idx, bg_i,
                            f"{tid}.light.slots.{role}={idx} is paper (invisible text)",
                        )
                        self.assertEqual(
                            idx, 7,
                            f"{tid}.light.slots.{role} should be ink (7), got {idx}",
                        )
                    # Surfaces must stay light (panel→ansi-15 breaks when 15 is dark ink).
                    for role in ("bg", "panel", "panel2"):
                        idx = int(iface[role])
                        lum = self._rel_luminance(block["ansi"][idx])
                        self.assertGreater(
                            lum, 0.45,
                            f"{tid}.light.iface.{role}→ansi-{idx} is too dark "
                            f"({block['ansi'][idx]}, L={lum:.2f})",
                        )

    def test_catalog_payload_full(self):
        cat = theme_catalog.catalog_payload(full=True)
        self.assertEqual(cat["default"], "kettle")
        self.assertIn("kettle", cat["packs"])
        self.assertIn("--ansi-0", cat["packs"]["kettle"]["dark"]["colors"])
        # Every bundled pack exposes a light side through the web catalog.
        for meta in cat["themes"]:
            if meta.get("source") != "bundled":
                continue
            tid = meta["id"]
            self.assertIn(tid, cat["packs"])
            web = cat["packs"][tid]
            self.assertIn("light", web)
            self.assertIn("--ansi-0", web["light"]["colors"])
            self.assertEqual(web["light"]["slots"]["agent"], "--ansi-7")

    def test_install_user_pack(self):
        base = theme_catalog.load_theme("kettle")
        payload = {
            "schema_version": 1,
            "id": "unit-test-theme",
            "label": "Unit Test Theme",
            "marquee": False,
            "dark": base["dark"],
            "light": base["light"],
        }
        with tempfile.TemporaryDirectory() as td:
            udir = Path(td)
            with mock.patch.object(theme_catalog, "user_themes_dir", return_value=udir):
                installed = theme_catalog.install_user_pack(payload)
                self.assertEqual(installed["id"], "unit-test-theme")
                self.assertEqual(installed["_source"], "user")
                self.assertTrue((udir / "unit-test-theme.json").is_file())
                ids = theme_catalog.list_theme_ids()
                self.assertIn("unit-test-theme", ids)


if __name__ == "__main__":
    unittest.main(verbosity=2)
