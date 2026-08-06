"""Theme catalog and pack validation."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import kettle.theme_catalog as theme_catalog


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

    def test_install_user_pack_rejects_bad_payloads(self):
        with self.assertRaises(ValueError):
            theme_catalog.install_user_pack(["not", "an", "object"])
        base = theme_catalog.load_theme("kettle")
        bad_id = {
            "schema_version": 1,
            "id": "bad id!",
            "label": "Nope",
            "dark": base["dark"],
            "light": base["light"],
        }
        with self.assertRaises(ValueError):
            theme_catalog.install_user_pack(bad_id)

    def test_validate_pack_mode_errors(self):
        base = theme_catalog.load_theme("kettle")
        cases = [
            ({"schema_version": 2, "id": "x", "label": "x",
              "dark": base["dark"], "light": base["light"]},
             "unsupported schema_version"),
            ({"schema_version": 1, "id": "", "label": "x",
              "dark": base["dark"], "light": base["light"]},
             "id and label"),
            ({"schema_version": 1, "id": "x", "label": "x",
              "dark": base["dark"]},
             "missing light"),
            ({"schema_version": 1, "id": "x", "label": "x",
              "dark": {**base["dark"], "ansi": ["#000000"] * 15},
              "light": base["light"]},
             "ansi must be 16"),
            ({"schema_version": 1, "id": "x", "label": "x",
              "dark": {**base["dark"], "ansi": ["red"] + ["#000000"] * 15},
              "light": base["light"]},
             "#RRGGBB"),
            ({"schema_version": 1, "id": "x", "label": "x",
              "dark": {**base["dark"], "iface": "nope"},
              "light": base["light"]},
             "iface must be an object"),
            ({"schema_version": 1, "id": "x", "label": "x",
              "dark": {**base["dark"], "iface": {"bg": 99}},
              "light": base["light"]},
             "must be 0–15"),
        ]
        for pack, needle in cases:
            with self.subTest(needle=needle):
                with self.assertRaises(ValueError) as ctx:
                    theme_catalog.validate_pack(pack)
                self.assertIn(needle, str(ctx.exception))

    def test_read_json_rejects_non_object(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "arr.json"
            path.write_text("[1, 2]", encoding="utf-8")
            with self.assertRaises(ValueError):
                theme_catalog._read_json(path)

    def test_active_theme_id_from_settings(self):
        self.assertEqual(
            theme_catalog.active_theme_id_from_settings(None),
            "kettle",
        )
        self.assertEqual(
            theme_catalog.active_theme_id_from_settings({"builtinTheme": "nord"}),
            "nord",
        )
        self.assertEqual(
            theme_catalog.active_theme_id_from_settings({"theme": "tokyo-night"}),
            "tokyo-night",
        )

    def test_prefer_dark_mode_env(self):
        with mock.patch.dict("os.environ", {"KETTLE_THEME_MODE": "light"}):
            self.assertFalse(theme_catalog.prefer_dark_mode())
        with mock.patch.dict("os.environ", {"KETTLE_THEME_MODE": "day"}):
            self.assertFalse(theme_catalog.prefer_dark_mode())
        with mock.patch.dict("os.environ", {"KETTLE_THEME_MODE": "dark"}):
            self.assertTrue(theme_catalog.prefer_dark_mode())
        with mock.patch.dict("os.environ", {}, clear=False):
            # Without env override, non-darwin defaults to dark.
            env = {k: v for k, v in __import__("os").environ.items()
                   if k != "KETTLE_THEME_MODE"}
            with mock.patch.dict("os.environ", env, clear=True):
                with mock.patch.object(theme_catalog.sys, "platform", "linux"):
                    self.assertTrue(theme_catalog.prefer_dark_mode())

    def test_user_themes_dir_env_and_platforms(self):
        with tempfile.TemporaryDirectory() as td:
            custom = Path(td) / "themes"
            with mock.patch.dict("os.environ", {"KETTLE_THEMES_DIR": str(custom)}):
                self.assertEqual(theme_catalog.user_themes_dir(), custom)
        with mock.patch.dict("os.environ", {}, clear=False):
            env = {k: v for k, v in __import__("os").environ.items()
                   if k not in {"KETTLE_THEMES_DIR", "XDG_CONFIG_HOME", "APPDATA"}}
            with mock.patch.dict("os.environ", env, clear=True):
                with mock.patch.object(theme_catalog.sys, "platform", "linux"):
                    path = theme_catalog.user_themes_dir()
                    self.assertTrue(str(path).endswith("kettle/themes"))
                with mock.patch.object(theme_catalog.sys, "platform", "darwin"):
                    path = theme_catalog.user_themes_dir()
                    self.assertIn("Application Support", str(path))
                with mock.patch.object(theme_catalog.sys, "platform", "win32"):
                    with mock.patch.dict("os.environ", {"APPDATA": "/appdata"}):
                        path = theme_catalog.user_themes_dir()
                        self.assertEqual(path, Path("/appdata/Kettle/themes"))

    def test_load_theme_falls_back_to_default(self):
        with tempfile.TemporaryDirectory() as td:
            with mock.patch.object(theme_catalog, "user_themes_dir",
                                   return_value=Path(td)):
                pack = theme_catalog.load_theme("does-not-exist-xyz")
        self.assertEqual(pack["id"], "kettle")

    def test_ansi_colors_and_syntax_table(self):
        pack = theme_catalog.load_theme("kettle")
        dark = theme_catalog.ansi_colors(pack, dark=True)
        light = theme_catalog.ansi_colors(pack, dark=False)
        self.assertEqual(len(dark), 16)
        self.assertNotEqual(dark[0], light[7])  # paper vs ink typically differ
        table = theme_catalog.syntax_color_table(pack, dark=True)
        self.assertIn("keyword", table)
        self.assertTrue(table["keyword"].startswith("#"))
        # Unknown role falls back through SYNTAX_ROLE_DEFAULTS → fg.
        self.assertEqual(
            theme_catalog.resolve_role_hex(pack, "not-a-real-role", dark=True),
            theme_catalog.resolve_role_hex(pack, "fg", dark=True),
        )

    def test_catalog_skips_broken_user_packs(self):
        with tempfile.TemporaryDirectory() as td:
            udir = Path(td)
            (udir / "broken.json").write_text('{"id": "broken"}', encoding="utf-8")
            with mock.patch.object(theme_catalog, "user_themes_dir", return_value=udir):
                cat = theme_catalog.catalog_payload(full=False)
            ids = [t["id"] for t in cat["themes"]]
            self.assertNotIn("broken", ids)
            self.assertIn("kettle", ids)

    def test_list_theme_ids_falls_back_when_index_corrupt(self):
        with tempfile.TemporaryDirectory() as td:
            bdir = Path(td) / "bundled"
            bdir.mkdir()
            (bdir / "index.json").write_text("{not json", encoding="utf-8")
            # Minimal valid pack so glob fallback has something to list.
            base = theme_catalog.load_theme("kettle")
            (bdir / "solo.json").write_text(json.dumps({
                "schema_version": 1, "id": "solo", "label": "Solo",
                "dark": base["dark"], "light": base["light"],
            }), encoding="utf-8")
            with mock.patch.object(theme_catalog, "bundled_themes_dir",
                                   return_value=bdir):
                with mock.patch.object(theme_catalog, "user_themes_dir",
                                       return_value=Path(td) / "empty-user"):
                    ids = theme_catalog.list_theme_ids()
            self.assertEqual(ids, ["solo"])

    def test_default_theme_id_falls_back_on_bad_index(self):
        with tempfile.TemporaryDirectory() as td:
            bdir = Path(td)
            (bdir / "index.json").write_text("{", encoding="utf-8")
            with mock.patch.object(theme_catalog, "bundled_themes_dir",
                                   return_value=bdir):
                self.assertEqual(theme_catalog.default_theme_id(), "kettle")

    def test_pack_to_web_merges_custom_opacity(self):
        pack = theme_catalog.load_theme("kettle")
        pack["dark"] = {
            **pack["dark"],
            "ifaceOpacity": {"muted": 40},
            "slotOpacity": {"agent": 33},
        }
        web = theme_catalog.pack_to_web(pack)
        self.assertEqual(web["dark"]["ifaceOpacity"]["muted"], 40)
        self.assertEqual(web["dark"]["slotOpacity"]["agent"], 33)
        # Untouched defaults remain.
        self.assertEqual(web["dark"]["ifaceOpacity"]["panel"], 92)


if __name__ == "__main__":
    unittest.main(verbosity=2)
