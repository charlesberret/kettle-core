"""Syntax highlighters for the built-in CLI editor."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import syntax
import tui_editor


class LanguageDetection(unittest.TestCase):
    def test_common_suffixes(self):
        cases = {
            "a.py": "python",
            "a.pyi": "python",
            "a.ts": "typescript",
            "a.tsx": "typescript",
            "a.js": "javascript",
            "a.jsx": "javascript",
            "a.md": "markdown",
            "a.yml": "yaml",
            "a.yaml": "yaml",
            "a.json": "json",
            "a.toml": "toml",
            "a.ini": "ini",
            "a.css": "css",
            "a.html": "html",
            "a.sh": "shell",
            "a.rs": "rust",
            "a.go": "go",
            "a.rb": "ruby",
            "a.java": "java",
            "a.c": "c",
            "a.cpp": "cpp",
            "a.sql": "sql",
            "a.swift": "swift",
            "a.lua": "lua",
            "a.r": "r",
            "a.unknown": "text",
            None: "text",
            "": "text",
        }
        for path, lang in cases.items():
            with self.subTest(path=path):
                self.assertEqual(syntax.language_for_path(path), lang)

    def test_special_filenames(self):
        self.assertEqual(syntax.language_for_path("Dockerfile"), "dockerfile")
        self.assertEqual(syntax.language_for_path("Makefile"), "shell")
        self.assertEqual(syntax.language_for_path("Gemfile"), "ruby")


class Tokenizers(unittest.TestCase):
    def _kinds(self, src: str, language: str) -> set[str]:
        return {k for k, _ in syntax.tokenize(src, language=language)}

    def test_python_keywords_and_strings(self):
        toks = syntax.tokenize("def foo():\n    return 'x'  # hi\n", language="python")
        kinds = {k for k, _ in toks}
        self.assertIn("keyword", kinds)
        self.assertIn("string", kinds)
        self.assertIn("comment", kinds)
        self.assertIn("function", kinds)

    def test_python_triple_string_and_self(self):
        src = 'class A:\n    """doc"""\n    def m(self):\n        return None\n'
        kinds = self._kinds(src, "python")
        self.assertIn("string", kinds)
        self.assertIn("constant", kinds)  # self
        self.assertIn("type", kinds)  # A / CapWords

    def test_python_unclosed_string(self):
        toks = syntax.tokenize("x = 'unterminated", language="python")
        self.assertTrue(any(k == "string" for k, _ in toks))

    def test_json_property_vs_string(self):
        toks = syntax.tokenize('{"a": "b", "n": 1, "t": true, "z": null}', language="json")
        quoted = [(k, t) for k, t in toks if t.startswith('"')]
        self.assertGreaterEqual(len(quoted), 2)
        self.assertEqual(quoted[0][0], "property")
        kinds = {k for k, _ in toks}
        self.assertIn("number", kinds)
        self.assertIn("constant", kinds)
        self.assertIn("punctuation", kinds)

    def test_javascript_comment_and_template(self):
        kinds = self._kinds("const x = `hi`; // c\n/* b */", "javascript")
        self.assertIn("keyword", kinds)
        self.assertIn("string", kinds)
        self.assertIn("comment", kinds)

    def test_markdown_heading_and_fence(self):
        src = "# Title\n\npara **bold** and `code`\n\n```\ncode\n```\n> quote\n- item\n"
        kinds = self._kinds(src, "markdown")
        self.assertIn("heading", kinds)
        self.assertIn("string", kinds)
        self.assertIn("comment", kinds)
        self.assertIn("operator", kinds)

    def test_yaml_key_and_comment(self):
        src = "# head\n---\nname: value\nlist:\n  - one\nflag: true\ncount: 3\n"
        kinds = self._kinds(src, "yaml")
        self.assertIn("comment", kinds)
        self.assertIn("heading", kinds)
        self.assertIn("property", kinds)
        self.assertIn("operator", kinds)

    def test_shell(self):
        kinds = self._kinds("#!/bin/sh\nif true; then echo hi; fi\n# c\n", "shell")
        self.assertIn("keyword", kinds)
        self.assertIn("comment", kinds)

    def test_css_block_comment(self):
        kinds = self._kinds("/* c */\n.a { color: red; }\n", "css")
        self.assertIn("comment", kinds)

    def test_html_tag_and_comment(self):
        kinds = self._kinds("<!-- c --><div class='x'>hi</div>", "html")
        self.assertIn("comment", kinds)
        self.assertIn("keyword", kinds)

    def test_toml(self):
        kinds = self._kinds("# c\n[section]\nkey = \"v\"\n", "toml")
        self.assertIn("comment", kinds)
        self.assertIn("heading", kinds)
        self.assertIn("property", kinds)
        self.assertIn("string", kinds)

    def test_c_like_and_go_rust(self):
        for lang, src in (
            ("c", "int main() { return 0; // c\n}"),
            ("go", "package main\nfunc main() {}\n"),
            ("rust", "fn main() { let x = 1; }\n"),
            ("sql", "SELECT * FROM t WHERE id = 1;"),
            ("ruby", "def hello\n  puts 'hi'\nend\n"),
            ("dockerfile", "FROM alpine\nRUN echo hi\n"),
        ):
            with self.subTest(lang=lang):
                kinds = self._kinds(src, lang)
                self.assertTrue(kinds)

    def test_tokenize_default_path(self):
        toks = syntax.tokenize("x = 1", path="mod.py")
        self.assertTrue(any(k == "number" or k == "text" for k, _ in toks))

    def test_tokenize_lines_split(self):
        lines = syntax.tokenize_lines("a\nb", language="text")
        self.assertEqual(len(lines), 2)
        lines2 = syntax.tokenize_lines("a\nb\n", language="text")
        self.assertEqual(len(lines2), 3)
        self.assertEqual(lines2[-1], [])

    def test_roundtrip_text_coverage(self):
        src = "hello world"
        toks = syntax.tokenize(src, language="text")
        self.assertEqual("".join(t for _, t in toks), src)

    def test_generic_operators_and_numbers(self):
        kinds = self._kinds("x += 0x10 && y != 3.14", "javascript")
        self.assertIn("operator", kinds)
        self.assertIn("number", kinds)


class BufferHelpers(unittest.TestCase):
    def test_find_next_wraps(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "a.py"
            p.write_text("alpha\nbeta alpha\ngamma\n", encoding="utf-8")
            buf = tui_editor.Buffer.load(p)
            buf.find_query = "alpha"
            buf.row, buf.col = 0, 0
            buf.find_next(backward=False, from_cursor=False)
            self.assertEqual((buf.row, buf.col), (0, 0))
            buf.find_next(backward=False, from_cursor=True)
            self.assertEqual((buf.row, buf.col), (1, 5))

    def test_find_backward_and_missing(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "b.txt"
            p.write_text("one\ntwo\none\n", encoding="utf-8")
            buf = tui_editor.Buffer.load(p)
            buf.find_query = "one"
            # Start after the last match; step backward to the first.
            buf.row, buf.col = 2, 3
            buf.find_next(backward=True, from_cursor=True)
            self.assertEqual((buf.row, buf.col), (2, 0))
            buf.find_next(backward=True, from_cursor=True)
            self.assertEqual((buf.row, buf.col), (0, 0))
            buf.find_query = "missing"
            buf.find_next()
            self.assertIn("not found", buf.message)

    def test_find_empty_query(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "c.txt"
            p.write_text("x\n", encoding="utf-8")
            buf = tui_editor.Buffer.load(p)
            buf.find_query = ""
            buf.find_next()
            self.assertIn("no search", buf.message)

    def test_save_touch_token_lines(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "d.py"
            p.write_text("def x():\n    return 1\n", encoding="utf-8")
            buf = tui_editor.Buffer.load(p)
            self.assertEqual(buf.language, "python")
            lines = buf.token_lines()
            self.assertGreaterEqual(len(lines), 2)
            buf.lines[0] = "def y():"
            buf.touch()
            self.assertTrue(buf.dirty)
            buf.save()
            self.assertFalse(buf.dirty)
            self.assertIn("def y", p.read_text(encoding="utf-8"))

    def test_plain_mode_for_large_files(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "big.py"
            # Force plain mode via line count threshold.
            old = tui_editor.HIGHLIGHT_MAX_LINES
            try:
                tui_editor.HIGHLIGHT_MAX_LINES = 3
                p.write_text("a\nb\nc\nd\n", encoding="utf-8")
                buf = tui_editor.Buffer.load(p)
                self.assertTrue(buf.plain_highlight)
                self.assertEqual(buf.language, "text")
                self.assertIn("large file", buf.message)
            finally:
                tui_editor.HIGHLIGHT_MAX_LINES = old

    def test_new_file_and_clamp(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "missing.md"
            buf = tui_editor.Buffer.load(p)
            self.assertEqual(buf.lines, [""])
            buf.row = 99
            buf.col = 99
            buf.clamp()
            self.assertEqual(buf.row, 0)
            self.assertEqual(buf.col, 0)

    def test_hex_helpers(self):
        r, g, b = tui_editor._hex_to_curses_rgb("#ff8000")
        self.assertEqual((r, g, b), (1000, 501, 0))  # 128/255*1000 ≈ 501
        ansi = ["#000000", "#ffffff", "#808080"]
        self.assertEqual(tui_editor._nearest_ansi16("#f0f0f0", ansi), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
