"""Syntax highlighters for the built-in CLI editor."""

from __future__ import annotations

import unittest

import syntax


class LanguageDetection(unittest.TestCase):
    def test_common_suffixes(self):
        self.assertEqual(syntax.language_for_path("a.py"), "python")
        self.assertEqual(syntax.language_for_path("a.ts"), "typescript")
        self.assertEqual(syntax.language_for_path("a.md"), "markdown")
        self.assertEqual(syntax.language_for_path("a.yml"), "yaml")
        self.assertEqual(syntax.language_for_path("a.unknown"), "text")


class Tokenizers(unittest.TestCase):
    def test_python_keywords_and_strings(self):
        toks = syntax.tokenize("def foo():\n    return 'x'  # hi\n", language="python")
        kinds = {k for k, _ in toks}
        self.assertIn("keyword", kinds)
        self.assertIn("string", kinds)
        self.assertIn("comment", kinds)
        self.assertIn("function", kinds)

    def test_json_property_vs_string(self):
        toks = syntax.tokenize('{"a": "b"}', language="json")
        # first quoted span is property, second is string value
        quoted = [(k, t) for k, t in toks if t.startswith('"')]
        self.assertGreaterEqual(len(quoted), 2)
        self.assertEqual(quoted[0][0], "property")
        self.assertEqual(quoted[1][0], "string")

    def test_markdown_heading(self):
        toks = syntax.tokenize("# Title\n\npara\n", language="markdown")
        self.assertTrue(any(k == "heading" for k, _ in toks))

    def test_tokenize_lines_split(self):
        lines = syntax.tokenize_lines("a\nb", language="text")
        self.assertEqual(len(lines), 2)
        # trailing newline yields an empty final line
        lines2 = syntax.tokenize_lines("a\nb\n", language="text")
        self.assertEqual(len(lines2), 3)
        self.assertEqual(lines2[-1], [])

    def test_roundtrip_text_coverage(self):
        src = "hello world"
        toks = syntax.tokenize(src, language="text")
        self.assertEqual("".join(t for _, t in toks), src)


class BufferFind(unittest.TestCase):
    def test_find_next_wraps(self):
        from tui_editor import Buffer
        from pathlib import Path
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "a.py"
            p.write_text("alpha\nbeta alpha\ngamma\n", encoding="utf-8")
            buf = Buffer.load(p)
            buf.find_query = "alpha"
            buf.row, buf.col = 0, 0
            buf.find_next(backward=False, from_cursor=False)
            self.assertEqual((buf.row, buf.col), (0, 0))
            buf.find_next(backward=False, from_cursor=True)
            self.assertEqual((buf.row, buf.col), (1, 5))


if __name__ == "__main__":
    unittest.main(verbosity=2)
