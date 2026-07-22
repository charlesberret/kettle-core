"""Frontend syntax gate.

static/index.html is run-critical: a syntax error anywhere in its single 3,300-line
inline script prevents even the error handler's own registration, producing the
blank-window-with-no-repair-path CLAUDE.md warns about (brief 08). There is no build
step, so nothing else parses the JS before a patron loads it.

This gate extracts every inline <script> block from index.html plus every .js file
shipped under static/ and runs `node --check` (syntax only) on each. Where node is on
PATH it fails loudly on a syntax error; where node is absent it skips with an honest
message rather than passing silently.
"""

import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

STATIC = Path(__file__).resolve().parent / "static"
INDEX = STATIC / "index.html"

# Inline scripts only: a <script ...> with no src= attribute, capturing its body.
_INLINE_SCRIPT = re.compile(
    r"<script(?![^>]*\bsrc=)[^>]*>(.*?)</script>", re.DOTALL | re.IGNORECASE
)

NODE = shutil.which("node")


def inline_scripts(html: str):
    """(index, source) for each non-empty inline <script> block in the HTML."""
    blocks = []
    for i, m in enumerate(_INLINE_SCRIPT.finditer(html)):
        body = m.group(1)
        if body.strip():
            blocks.append((i, body))
    return blocks


def node_check(source: str) -> subprocess.CompletedProcess:
    """Run `node --check` over source; returns the completed process."""
    with tempfile.NamedTemporaryFile(
        "w", suffix=".js", delete=False, encoding="utf-8"
    ) as fh:
        fh.write(source)
        tmp = fh.name
    try:
        return subprocess.run(
            [NODE, "--check", tmp], capture_output=True, text=True
        )
    finally:
        Path(tmp).unlink(missing_ok=True)


class SittingUiConventions(unittest.TestCase):
    """docs/UI.md type hierarchy must stay wired in static/index.html.

    Guards against new panes defaulting to body-white while chrome is gray.
    """

    def test_type_role_tokens_defined(self):
        css = INDEX.read_text(encoding="utf-8")
        for token in (
            "--text-heading",
            "--text-label",
            "--text-secondary",
            "--text-primary",
            "--text-muted",
            "--text-link",
        ):
            self.assertIn(token, css, f"missing type token {token} (see docs/UI.md)")

    def test_brief_pane_uses_secondary_not_primary_ink(self):
        css = INDEX.read_text(encoding="utf-8")
        # Brief values must not reintroduce pure --fg as their color.
        self.assertRegex(
            css,
            r"\.brief-ask[^{]*\{[^}]*color:\s*var\(--text-secondary\)",
            "brief-ask must use --text-secondary (docs/UI.md)",
        )
        self.assertRegex(
            css,
            r"\.brief-body[^{]*\{[^}]*color:\s*var\(--text-secondary\)",
            "brief-body must use --text-secondary (docs/UI.md)",
        )
        self.assertNotRegex(
            css,
            r"\.brief-ask\s*\{[^}]*color:\s*var\(--fg\)",
            "brief-ask must not use raw --fg",
        )


@unittest.skipIf(NODE is None, "node not on PATH — frontend syntax gate skipped")
class FrontendSyntaxGate(unittest.TestCase):

    def test_index_html_has_inline_scripts(self):
        blocks = inline_scripts(INDEX.read_text(encoding="utf-8"))
        # The boot bootstrap + the main script are both inline; guard against a
        # regex that silently matches nothing (which would make the gate a no-op).
        self.assertGreaterEqual(len(blocks), 2, "expected inline <script> blocks")

    def test_inline_scripts_parse(self):
        html = INDEX.read_text(encoding="utf-8")
        for idx, source in inline_scripts(html):
            with self.subTest(script=idx):
                proc = node_check(source)
                self.assertEqual(
                    proc.returncode,
                    0,
                    f"inline <script> #{idx} in index.html failed node --check:\n"
                    f"{proc.stderr}",
                )

    def test_static_js_files_parse(self):
        js_files = sorted(STATIC.glob("*.js"))
        self.assertTrue(js_files, "expected at least one .js file under static/")
        for path in js_files:
            with self.subTest(js=path.name):
                proc = subprocess.run(
                    [NODE, "--check", str(path)], capture_output=True, text=True
                )
                self.assertEqual(
                    proc.returncode,
                    0,
                    f"{path.name} failed node --check:\n{proc.stderr}",
                )


if __name__ == "__main__":
    unittest.main()
