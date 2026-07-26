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

    def test_catalog_payload_full(self):
        cat = theme_catalog.catalog_payload(full=True)
        self.assertEqual(cat["default"], "kettle")
        self.assertIn("kettle", cat["packs"])
        self.assertIn("--ansi-0", cat["packs"]["kettle"]["dark"]["colors"])

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
