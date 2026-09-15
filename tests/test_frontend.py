"""Frontend syntax gate.

static/index.html is run-critical: a syntax error anywhere in its single 3,300-line
inline script prevents even the error handler's own registration, producing the
blank-window-with-no-repair-path CLAUDE.md warns about (brief 08). There is no build
step, so nothing else parses the JS before a user loads it.

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

STATIC = Path(__file__).resolve().parents[1] / "kettle" / "static"
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


def function_source(html: str, name: str) -> str:
    """Return one top-level JS function through the next function declaration."""
    match = re.search(
        rf"(?:^|\n)(?:async\s+)?function\s+{re.escape(name)}\s*\([^)]*\)\s*\{{"
        rf".*?(?=\n(?:async\s+)?function\s+[A-Za-z_$]|\Z)",
        html,
        re.DOTALL,
    )
    if not match:
        raise AssertionError(f"missing top-level JavaScript function {name}()")
    return match.group(0)


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

    def test_type_labels_mix_toward_bg_not_alias_dim(self):
        """Labels must stay gray even when --muted equals --fg (theme defaults)."""
        css = INDEX.read_text(encoding="utf-8")
        # Extract :root block roughly
        self.assertIn("color-mix(in srgb, var(--fg)", css)
        self.assertRegex(
            css,
            r"--text-label:\s*color-mix\(in srgb,\s*var\(--fg\)",
            "--text-label must color-mix toward bg, not alias --dim",
        )
        self.assertNotRegex(
            css,
            r"--text-label:\s*var\(--dim\)",
            "--text-label must not be a bare --dim alias",
        )

    def test_desk_brief_ask_blockquote_and_body(self):
        """Right-pane brief: ask as block-quote lead; body as secondary brief text."""
        css = INDEX.read_text(encoding="utf-8")
        self.assertIn("id=\"desk-brief\"", INDEX.read_text(encoding="utf-8"))
        self.assertIn("id=\"takeaway\"", INDEX.read_text(encoding="utf-8"))
        self.assertIn("id=\"ritual\"", INDEX.read_text(encoding="utf-8"))
        self.assertRegex(
            css,
            r"\.brief-ask[^{]*\{[^}]*border-left",
            "brief-ask must be block-quote styled (plugin Desk)",
        )
        # Ritual is framed by drag bars above (#divBrief) and below (#divDesk)
        html = INDEX.read_text(encoding="utf-8")
        self.assertIn('id="divBrief"', html)
        self.assertIn('id="divDesk"', html)
        self.assertLess(html.index('id="divBrief"'), html.index('id="ritual"'))
        self.assertLess(html.index('id="ritual"'), html.index('id="divDesk"'))
        # Reload button stays removed; agent bar sits under chat entry
        html = INDEX.read_text(encoding="utf-8")
        self.assertNotIn("id=\"reloadbtn\"", html)
        self.assertIn("id=\"agentbar\"", html)
        self.assertIn("id=\"ctxbar\"", html)
        self.assertLess(html.index("id=\"chatin\""), html.index("id=\"agentbar\""))
        self.assertLess(html.index("id=\"model\""), html.index("id=\"ctxbar\""))
        self.assertLess(html.index("id=\"ctxbar\""), html.index("id=\"agentsettings\""))
        # model/ctx/settings live inside agentbar (bottom of right pane)
        self.assertLess(html.index("id=\"agentbar\""), html.index("id=\"model\""))
        # Project selector lives in the right desk pane; git heatmap fills the row gap
        self.assertIn("id=\"desk-proj\"", html)
        self.assertIn("id=\"gitmap\"", html)
        self.assertLess(html.index("id=\"proj\""), html.index("id=\"gitmap\""))
        # Renderer + lifecycle layers present (methodical git strip)
        self.assertIn("function renderGitMap", html)
        self.assertIn("function refreshGitMap", html)
        self.assertIn("function gitMapEmptyGrid", html)
        self.assertIn("/api/git/activity", html)
        self.assertLess(html.index("id=\"desk-proj\""), html.index("id=\"desk-brief\""))
        self.assertLess(html.index("id=\"approve\""), html.index("id=\"comment\""))
        self.assertLess(html.index("id=\"comment\""), html.index("id=\"sweepbtn\""))

    def test_left_file_info_box(self):
        """Bottom-left info pane: status/path/changes under the queue."""
        html = INDEX.read_text(encoding="utf-8")
        self.assertIn('id="meta"', html)
        self.assertIn('id="metadl"', html)
        self.assertIn('id="metaedit"', html)
        self.assertIn('id="divQ"', html)
        # Info sits after the queue in the left column
        self.assertLess(html.index('id="queue"'), html.index('id="meta"'))
        self.assertLess(html.index('id="meta"'), html.index('id="mid"'))
        css = html
        self.assertRegex(css, r"#meta\s*\{[^}]*border-top")
        # Field names: gray body text (not all-caps header labels)
        self.assertRegex(css, r"\.meta-k[^{]*\{[^}]*--text-secondary")
        self.assertIn("metaRow('status'", html)
        self.assertIn("metaRow('needs'", html)

    def test_diff_badges_colored_globally(self):
        css = INDEX.read_text(encoding="utf-8")
        self.assertRegex(css, r"\.qdiff\s+\.add[^{]*\{[^}]*--good")
        self.assertRegex(css, r"\.qdiff\s+\.del[^{]*\{[^}]*--warn")


class ViewportRitualRegressionBar(unittest.TestCase):
    """Structural CI bar for the canonical reference-web sitting state machine.

    These checks do not claim a manual provider/browser walkthrough. They make
    accidental deletion or disconnection of a founding/sitting step fail the
    ordinary core suite, giving every adapted viewport a stable baseline.
    """

    @classmethod
    def setUpClass(cls):
        cls.html = INDEX.read_text(encoding="utf-8")

    def function(self, name: str) -> str:
        return function_source(self.html, name)

    def test_founding_routes_form_one_reference_web_chain(self):
        self.assertIn("'/api/interview'", self.function("ivTurn"))

        propose = self.function("finishInterview")
        self.assertIn("'/api/propose'", propose)
        self.assertIn("enterProposing(pid)", propose)

        approve = self.function("approve")
        self.assertIn("'/api/approve'", approve)
        self.assertIn("isProposalEntry(cur)", approve)
        self.assertIn("foundFromProposal()", approve)

        found = self.function("foundFromProposal")
        self.assertIn("'/api/found'", found)
        self.assertIn("revealQueue(pid", found)

    def test_proposal_phase_keeps_the_found_action_visible(self):
        self.assertRegex(
            self.html,
            r"body\.proposing\s+#approve\s*\{",
            "proposal phase must visibly promote the action that founds the desk",
        )
        proposing = self.function("setProposingChrome")
        self.assertIn("classList.toggle('proposing'", proposing)
        self.assertNotIn("pointerEvents = 'none'", proposing)
        self.assertIn("ab.textContent = 'Found Desk'", self.function("showProposalGuide"))

    def test_agent_chat_renders_gfm(self):
        """Agent bubbles must paint GFM (headings, lists, task ticks), not raw markdown."""
        html = INDEX.read_text(encoding="utf-8")
        fill = function_source(html, "fillAgentMarkdown")
        self.assertIn("_mdHtml", fill)
        self.assertIn("purifyHtml", fill)
        self.assertIn("marked.parse", function_source(html, "_mdHtml"))
        add = function_source(html, "addMsg")
        self.assertIn("fillAgentMarkdown", add)
        stream = function_source(html, "pipeStream")
        self.assertIn("fillAgentMarkdown", stream)
        self.assertRegex(html, r"\.msg\.agent\.md\s*\{")
        self.assertIn("ui-2026-09-15f", html)

    def test_markdown_is_sanitized_as_a_string_before_it_reaches_the_dom(self):
        """Assigning marked output to innerHTML and cleaning the node afterwards is
        too late: parsing already queued <img onerror> handlers. Every markdown
        sink must assign a purifyHtml() result, and DOMPurify must never be fed a
        live node's innerHTML."""
        html = self.html
        self.assertNotRegex(html, r"innerHTML\s*=\s*(?:marked\.parse|_mdHtml)\(")
        self.assertNotRegex(html, r"DOMPurify\.sanitize\(\s*\w+\.innerHTML")
        self.assertNotIn("sanitizeRender", html)
        purify = self.function("purifyHtml")
        self.assertIn("DOMPurify.sanitize(", purify)
        self.assertIn("return null", purify)  # no blocklist fallback
        for name in ("fillAgentMarkdown", "renderMd"):
            src = self.function(name)
            with self.subTest(sink=name):
                self.assertIn("purifyHtml(_mdHtml(", src)
                for m in re.finditer(r"(\w+)\.innerHTML\s*=\s*([^;]+);", src):
                    self.assertNotIn("marked", m.group(2))
                    self.assertNotIn("_mdHtml", m.group(2))

    def test_markdown_sanitizer_drops_id_attributes(self):
        """$() is getElementById; a file's <div id="chat"> must not capture the sitting."""
        m = re.search(r"const MD_PURIFY = \{(.*?)\n\};", self.html, re.DOTALL)
        self.assertIsNotNone(m)
        attrs = re.search(r"ALLOWED_ATTR:\s*\[(.*?)\]", m.group(1), re.DOTALL).group(1)
        self.assertNotIn("'id'", attrs)
        self.assertIn("SANITIZE_NAMED_PROPS: true", m.group(1))

    def test_found_desk_announces_founded_only_when_the_core_says_so(self):
        found = self.function("foundFromProposal")
        self.assertIn("st.founded === true", found)
        self.assertLess(found.index("st.founded === true"), found.index("'— desk founded —'"))
        self.assertIn("enterProposing(pid)", found)          # failure keeps the proposal open
        self.assertIn("$('approve').disabled = true", found)  # no double Found Desk
        proposing = self.function("enterProposing")
        self.assertNotIn("isProposalEntry(e) && e.status !== 'approved')", proposing)

    def test_sitting_uses_the_cores_founded_predicate(self):
        load = self.function("loadProject")
        self.assertIn("ivst.founded", load)
        self.assertNotIn("const proposing = !hasContent", load)
        self.assertNotIn("const unfounded = !hasContent", load)

    def test_refused_api_calls_surface_instead_of_streaming_nothing(self):
        """After a core restart every call 403s with code auth; chat used to show an
        empty turn and sweep printed started/finished having done nothing."""
        stream = self.function("pipeStream")
        self.assertLess(stream.index("if(!r.ok) throw await apiErrorText(r)"),
                        stream.index("r.body.getReader()"))
        err = self.function("apiErrorText")
        self.assertIn("j.code === 'auth'", err)
        self.assertIn("reload", err)
        for name in ("jget", "jpost"):
            self.assertIn("apiErrorText(r)", self.function(name))

    def test_one_broken_desk_does_not_fail_the_sitting_boot(self):
        load = self.function("loadProject")
        i = load.index("jget('/api/queue?project='")
        self.assertIn("try {", load[max(0, i - 80):i])
        self.assertIn("this desk could not load", load)

    def test_founding_does_not_upgrade_gfm_into_a_card(self):
        """P4: interview is a conversation. The confirmation-card machinery is gone,
        not merely disconnected, and agent turns always paint display-only GFM."""
        for name in ("parseConfirmCard", "renderConfirmCard", "serializeConfirmCard",
                     "maybeUpgradeConfirmCard", "looksLikeConfirmCard", "growElaborate",
                     "ensureInterviewStartAnchor", "confirm-card", "cc-elab", "finish ✓"):
            with self.subTest(identifier=name):
                self.assertNotIn(name, self.html)
        self.assertIn("fillAgentMarkdown(agentNode, agentAcc)", self.function("pipeStream"))

    def test_activity_updates_chrome_and_compact_stays_connected(self):
        stream = self.function("pipeStream")
        self.assertIn("ev.t === 'activity'", stream)
        self.assertIn("setSpinLabel", stream)
        self.assertIn("'/api/compact'", self.function("runCompact"))


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
