#!/usr/bin/env python3
"""The UI copy catalog is the one source of sitting strings, for every viewport.

Canonical: kettle/static/ui-copy.json
Consumers: the sitting (via the rendered /ui-copy.js), kettle.uicopy (CLI/TUI),
           kettle-vscode/src/uiCopy.ts (generated snapshot, checked when present)
"""

from __future__ import annotations

import html
import json
import re
import unittest
from pathlib import Path

from kettle import uicopy

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "kettle" / "static"
CATALOG = STATIC / "ui-copy.json"
INDEX = STATIC / "index.html"
VSCODE_TS = ROOT.parent / "kettle-vscode" / "src" / "uiCopy.ts"

# Keys every sitting surface must define.
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

TAG_TEXT_RE = re.compile(
    r'<(\w+)\b[^>]*\bdata-uic="([A-Za-z][A-Za-z0-9_]*)"[^>]*>(.*?)</\1>', re.S
)
TAG_ATTR_RE = re.compile(r'\bdata-uic-(title|ph|aria)="([A-Za-z][A-Za-z0-9_]*)"')
ATTR_PROP = {"title": "title", "ph": "placeholder", "aria": "aria-label"}


def markup() -> str:
    """Just the markup — the script below it mentions these attribute names too."""
    return INDEX.read_text(encoding="utf-8").split("<body>", 1)[1].split("<script>", 1)[0]


def tagged_sites() -> list[tuple[str, str, str | None]]:
    """(key, where, literal) for every data-uic* tag in the markup."""
    body = markup()
    out: list[tuple[str, str, str | None]] = []
    for m in TAG_TEXT_RE.finditer(body):
        out.append((m.group(2), "textContent", html.unescape(m.group(3).strip())))
    for m in TAG_ATTR_RE.finditer(body):
        prop = ATTR_PROP[m.group(1)]
        tag = body[body.rfind("<", 0, m.start()) : body.find(">", m.end())]
        am = re.search(r'\b' + prop + r'="([^"]*)"', tag)
        out.append((m.group(2), prop, html.unescape(am.group(1)) if am else None))
    return out


def keys_from_ts(text: str) -> dict[str, str]:
    """The generated mirror's UI_COPY map (not a full TS parser).

    Two traps, both of which bit this test when it was written:

    * `UI_COPY_SHORT` declares the *same key names* with terse values, so parsing
      the whole file merges the two maps and every key with a short variant
      compares unequal. Slice the UI_COPY block first.
    * The values are emitted by `JSON.stringify`, so they are JSON string literals.
      Decoding them with `unicode_escape` turns every em dash into mojibake
      (`\xe2\x80\x94`) and reports a mismatch that is not there. Parse them as JSON.
    """
    start = text.find("export const UI_COPY = {")
    if start < 0:
        return {}
    end = text.find("} as const;", start)
    block = text[start:end if end > 0 else len(text)]
    out: dict[str, str] = {}
    for m in re.finditer(
        r'^\s*"?([a-zA-Z_][a-zA-Z0-9_]*)"?\s*:\s*("(?:\\.|[^"\\])*")', block, re.M
    ):
        out[m.group(1)] = json.loads(m.group(2))
    return out


class Catalog(unittest.TestCase):
    def test_catalog_is_valid_and_complete(self):
        raw = json.loads(CATALOG.read_text(encoding="utf-8"))
        keys = raw["keys"]
        self.assertFalse(REQUIRED - set(keys), f"missing keys: {REQUIRED - set(keys)}")
        self.assertEqual(keys["streamIdle"]["text"], "Chat stream idle")
        self.assertIn("Kettle agent", keys["chatPlaceholder"]["text"])

    def test_every_key_carries_a_note(self):
        """The note is what lets an agent act on a key it has never seen before."""
        keys = json.loads(CATALOG.read_text(encoding="utf-8"))["keys"]
        missing = sorted(k for k, v in keys.items() if not v.get("note"))
        self.assertEqual([], missing, f"keys without a note: {missing}")

    def test_short_is_never_longer_than_text(self):
        """`short` exists for narrow surfaces; a longer one is a copy mistake."""
        keys = json.loads(CATALOG.read_text(encoding="utf-8"))["keys"]
        bad = [
            k
            for k, v in keys.items()
            if isinstance(v.get("short"), str) and len(v["short"]) > len(v["text"])
        ]
        self.assertEqual([], bad, f"short variant longer than text: {bad}")

    def test_no_generated_js_copy_is_committed(self):
        """/ui-copy.js is rendered per request. A file on disk would be a second source."""
        self.assertFalse(
            (STATIC / "ui-copy.js").exists(),
            "static/ui-copy.js is back — it must stay generated at request time",
        )


class Markup(unittest.TestCase):
    def test_every_tagged_key_exists(self):
        keys = json.loads(CATALOG.read_text(encoding="utf-8"))["keys"]
        unknown = sorted({k for k, _, _ in tagged_sites() if k not in keys})
        self.assertEqual([], unknown, f"index.html tags unknown keys: {unknown}")

    def test_tagged_literals_match_the_catalog_exactly(self):
        """The literal in index.html is the fallback when /ui-copy.js fails to load.

        If it disagrees with the catalog, the sitting reads one way with the catalog
        and another way without it — the drift this whole mechanism exists to remove.
        Fix the literal, or fix the catalog; do not leave them different.
        """
        keys = json.loads(CATALOG.read_text(encoding="utf-8"))["keys"]
        bad = []
        for key, where, literal in tagged_sites():
            want = keys.get(key, {}).get("text")
            if want != literal:
                bad.append(f"{key} ({where}): catalog {want!r} != markup {literal!r}")
        self.assertEqual([], bad, "\n".join(bad))

    def test_tagged_text_elements_have_no_child_elements(self):
        """data-uic sets textContent, which would delete children. Tag the leaf."""
        body = markup()
        bad = []
        for m in TAG_TEXT_RE.finditer(body):
            if "<" in m.group(3):
                bad.append(m.group(2))
        self.assertEqual([], bad, f"data-uic on a wrapper element: {bad}")


class Rendered(unittest.TestCase):
    def test_render_js_is_script_safe(self):
        js = uicopy.render_js(uicopy.payload(STATIC))
        self.assertIn("KETTLE_UI_COPY", js)
        # An unescaped "</script>" inside a string literal would close the element.
        self.assertNotIn("<", js.split("*/", 1)[1])

    def test_render_js_exposes_flat_text_and_meta(self):
        js = uicopy.render_js(uicopy.payload(STATIC))
        flat = re.search(r"root\.KETTLE_UI_COPY = (\{.*?\});\n", js, re.S).group(1)
        self.assertEqual("Chat stream idle", json.loads(flat)["streamIdle"])
        meta = re.search(r"root\.KETTLE_UI_COPY_META = (\{.*?\});\n", js, re.S).group(1)
        self.assertEqual("Agent idle", json.loads(meta)["streamIdle"]["short"])


class Overrides(unittest.TestCase):
    def payload_with(self, tmp: Path, doc: dict) -> dict:
        tmp.write_text(json.dumps(doc), encoding="utf-8")
        return uicopy.payload(STATIC, tmp)

    def test_key_override_wins_and_is_reported(self):
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            over = Path(td) / uicopy.OVERRIDES_NAME
            pay = self.payload_with(over, {"keys": {"queueTitle": {"text": "Stack"}}})
            self.assertEqual("Stack", uicopy.text(pay, "queueTitle"))
            self.assertIn("queueTitle", pay["overridden"])
            # the shipped note survives, so the badge can still explain the key
            self.assertTrue(pay["keys"]["queueTitle"]["note"])

    def test_short_falls_back_to_text(self):
        pay = uicopy.payload(STATIC)
        # queueTitle has no short of its own, so the resolver falls back to its text
        self.assertEqual("Queue", uicopy.text(pay, "queueTitle", short=True))
        self.assertEqual("Info", uicopy.text(pay, "metaTitle", short=True))

    def test_corrupt_overrides_do_not_break_the_sitting(self):
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            over = Path(td) / uicopy.OVERRIDES_NAME
            over.write_text("{not json", encoding="utf-8")
            pay = uicopy.payload(STATIC, over)
            self.assertEqual("Queue", uicopy.text(pay, "queueTitle"))

    def test_missing_catalog_yields_empty_not_an_exception(self):
        pay = uicopy.payload(Path("/nonexistent-static"))
        self.assertEqual({}, pay["keys"])
        self.assertEqual("fallback", uicopy.text(pay, "queueTitle", default="fallback"))


class PatchValidation(unittest.TestCase):
    def test_accepts_a_key_and_a_selector(self):
        out = uicopy.validate_patch(
            {"keys": {"queueTitle": {"text": "Stack"}},
             "selectors": {"#approve": {"title": "hm"}}}
        )
        self.assertEqual("Stack", out["keys"]["queueTitle"]["text"])
        self.assertEqual("hm", out["selectors"]["#approve"]["title"])

    def test_refuses_a_broad_selector(self):
        """A selector override relabels one element; it is not a licence to restyle."""
        for sel in ("*", "body", "div", ".btn", "#a b", "#a,#b"):
            with self.subTest(sel=sel), self.assertRaises(uicopy.CopyError):
                uicopy.validate_patch({"selectors": {sel: {"text": "x"}}})

    def test_refuses_unknown_fields_and_web_attrs_on_keys(self):
        with self.assertRaises(uicopy.CopyError):
            uicopy.validate_patch({"keys": {"queueTitle": {"onclick": "x"}}})
        with self.assertRaises(uicopy.CopyError):
            # a catalog key is cross-platform text; "title" is a web element attribute
            uicopy.validate_patch({"keys": {"queueTitle": {"title": "x"}}})

    def test_refuses_overlong_text_and_empty_patches(self):
        with self.assertRaises(uicopy.CopyError):
            uicopy.validate_patch({"keys": {"queueTitle": {"text": "x" * 2001}}})
        with self.assertRaises(uicopy.CopyError):
            uicopy.validate_patch({})

    def test_null_entry_clears_an_override(self):
        patch = uicopy.validate_patch({"keys": {"queueTitle": None}})
        merged = uicopy.apply_patch({"keys": {"queueTitle": {"text": "Stack"}}}, patch)
        self.assertNotIn("queueTitle", merged["keys"])

    def test_empty_string_clears_one_field_only(self):
        patch = uicopy.validate_patch({"keys": {"queueTitle": {"short": ""}}})
        merged = uicopy.apply_patch(
            {"keys": {"queueTitle": {"text": "Stack", "short": "S"}}}, patch
        )
        self.assertEqual({"text": "Stack"}, merged["keys"]["queueTitle"])

    def test_entry_cap(self):
        many = {"keys": {f"k{i}": {"text": "x"} for i in range(uicopy.MAX_ENTRIES + 1)}}
        with self.assertRaises(uicopy.CopyError):
            uicopy.apply_patch({}, uicopy.validate_patch(many))


class Promote(unittest.TestCase):
    def test_plan_separates_ready_keys_from_selectors_needing_one(self):
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            over = Path(td) / uicopy.OVERRIDES_NAME
            over.write_text(
                json.dumps(
                    {"keys": {"queueTitle": {"text": "Stack"}},
                     "selectors": {"#addgo": {"text": "go"}}}
                ),
                encoding="utf-8",
            )
            plan = uicopy.promote_plan(STATIC, over)
            self.assertEqual(["queueTitle"], [r["key"] for r in plan["ready"]])
            self.assertEqual("Queue", plan["ready"][0]["from"]["text"])
            self.assertTrue(plan["ready"][0]["known"])
            self.assertEqual(["#addgo"], [n["selector"] for n in plan["needs_key"]])


class VsCodeMirror(unittest.TestCase):
    def test_mirror_matches_when_the_tree_is_present(self):
        if not VSCODE_TS.is_file():
            self.skipTest("VS Code tree not checked out next to core")
        core = {
            k: v["text"]
            for k, v in json.loads(CATALOG.read_text(encoding="utf-8"))["keys"].items()
        }
        mirror = keys_from_ts(VSCODE_TS.read_text(encoding="utf-8"))
        missing = sorted(set(core) - set(mirror))
        self.assertEqual(
            [], missing, f"run `npm run sync-ui-copy` in kettle-vscode: {missing}"
        )
        for k in sorted(set(core) & set(mirror)):
            self.assertEqual(
                core[k], mirror[k], f"ui-copy mismatch for {k!r} — re-run sync-ui-copy"
            )


if __name__ == "__main__":
    unittest.main()
