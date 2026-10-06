#!/usr/bin/env python3
"""The lexicon, and the linter that enforces it.

The linter's value is precision, not coverage: its first run produced 548 findings,
of which almost all were noise, and a tool people turn off enforces nothing. These
tests pin the exemptions that made it usable — they are the feature.
"""

from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LEXICON = ROOT / "kettle" / "kits" / "_lexicon.json"
DOC = ROOT / "docs" / "LEXICON.md"


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "tools" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


lint = _load("lint-lexicon")
render = _load("render-lexicon-doc")
TERMS = lint.load_lexicon()


def check(text: str):
    return lint.check_text(text, TERMS, where="t", line_no=1)


def checks(text: str):
    return {f["check"] for f in check(text)}


class LexiconShape(unittest.TestCase):
    def test_ids_unique_and_every_term_glossed(self):
        doc = json.loads(LEXICON.read_text(encoding="utf-8"))
        ids = [t["id"] for t in doc["terms"]]
        self.assertEqual(len(ids), len(set(ids)))
        for t in doc["terms"]:
            self.assertTrue(t.get("gloss"), f"{t['id']} has no gloss")
            self.assertIn(t["casing"], ("title", "sentence", "lower"))

    def test_retired_forms_are_literal_and_linted(self):
        """A replaced label is decidable by literal match, so it stays an error."""
        found = [f for f in check("press finish ✓ to continue") if f["check"] == "retired-form"]
        self.assertTrue(found, "a retired label must still be caught")

    def test_avoid_holds_only_spellings_of_its_own_term(self):
        """`avoid` is linted, so it must be decidable.

        A different word ("summary" for "brief") is only wrong when it *means* the
        term, which no regex can tell. Those belong in `not_synonyms`, which is
        guidance and never linted.
        """
        for t in json.loads(LEXICON.read_text(encoding="utf-8"))["terms"]:
            for bad in t.get("avoid", []):
                self.assertEqual(
                    bad["form"].lower().replace("-", " ").replace("✓", "").strip(),
                    t["term"].lower().replace("-", " ").replace("✓", "").strip(),
                    f"{t['id']}: {bad['form']!r} is a synonym, not a spelling — "
                    "move it to not_synonyms",
                )

    def test_single_word_controls_are_not_case_checked(self):
        """Sweep/Approve/Comment share a spelling with the concept."""
        for t in json.loads(LEXICON.read_text(encoding="utf-8"))["terms"]:
            if t["casing"] == "title" and " " not in t["term"]:
                self.assertIs(t.get("lint_case"), False, f"{t['id']} would flag the concept")

    def test_generated_doc_is_current(self):
        self.assertEqual(0, render.main.__wrapped__() if hasattr(render.main, "__wrapped__") else 0)
        body = render.render(json.loads(LEXICON.read_text(encoding="utf-8")))
        self.assertEqual(body, DOC.read_text(encoding="utf-8"),
                         "docs/LEXICON.md is stale — run tools/render-lexicon-doc.py")


class Catches(unittest.TestCase):
    def test_wrong_case_on_a_document_name(self):
        self.assertIn("wrong-case", checks("edit the desk proposal, then found"))

    def test_wrong_case_on_a_multiword_control(self):
        self.assertIn("wrong-case", checks("click start interview to begin"))

    def test_stray_capital_on_a_common_noun(self):
        self.assertIn("stray-capital", checks("the Sitting ends with a sweep"))

    def test_retired_role_name(self):
        """`curator` became `agent` in user-facing copy on 2026-10-01."""
        found = [f for f in check("the curator files a brief") if f["check"] == "retired-form"]
        self.assertTrue(found, "the retired role name must still be caught")
        self.assertIn("agent", found[0]["why"])

    def test_retired_control_name(self):
        """The control reads Approve in both states; `Found Desk` must not come back."""
        found = [f for f in check("press Found Desk when ready") if f["check"] == "retired-form"]
        self.assertTrue(found)

    def test_the_verb_survives_the_retired_control(self):
        """Only the label was retired. "found the project desk" is still correct."""
        self.assertEqual([], [f for f in check("Approve founds the project desk.")
                              if f["check"] == "retired-form"])

    def test_retired_forms_match_whole_words_only(self):
        """Retiring `curator` must not flag `curatorial`, `curated` or `curate`.

        It did, on the first run of the rename: 94 false warnings, every one of them
        a word that merely starts the same way.
        """
        for ok in ("real curatorial briefs", 'the "curated" field', "you curate a queue"):
            with self.subTest(text=ok):
                self.assertEqual([], [f for f in check(ok) if f["check"] == "retired-form"])


class HouseWordsStayOffScreen(unittest.TestCase):
    """The check that earns this tool's keep.

    The first version of the linter enforced that we spell our own vocabulary
    consistently. That protected the vocabulary and did nothing for the person trying
    to use Kettle — and it hardened into CI the very entrenchment it should have
    caught. A user should not need a glossary; `house` terms stay off screen and the
    lexicon names the plain word instead.
    """

    def house(self, text):
        return {f["found"].lower() for f in lint.check_house_words(text, TERMS, where="t")}

    def test_catches_the_words_a_user_would_have_to_learn(self):
        for text, word in [("Found the desk from your proposal", "desk"),
                           ("Close the sitting", "sitting"),
                           ("Rule on each entry", "entry"),
                           ("read the brief first", "brief"),
                           ("the charter is written", "charter")]:
            with self.subTest(text=text):
                self.assertIn(word, self.house(text))

    def test_names_the_plain_word_as_the_fix(self):
        f = lint.check_house_words("found the desk", TERMS, where="t")
        fixes = " ".join(x["fix"] for x in f)
        self.assertIn("project", fixes)

    def test_leaves_plain_copy_alone(self):
        for ok in ["press Finish batch when you are done",
                   "Edit the proposal, then approve it to set up your project",
                   "Kettle lines up a batch of files for you to review",
                   "Chat with the agent about this file"]:
            with self.subTest(text=ok):
                self.assertEqual(set(), self.house(ok))

    def test_a_house_word_in_backticks_is_us_talking_about_it(self):
        """docs and notes discuss `desk` on purpose; that is not copy."""
        self.assertEqual(set(), self.house("the `desk` directory holds its records"))

    def test_the_shipped_catalog_is_clean(self):
        """Every string a user reads, checked against the whole house vocabulary."""
        doc = json.loads((ROOT / "kettle" / "static" / "ui-copy.json").read_text())
        bad = []
        for key, rec in doc["keys"].items():
            for field in ("text", "short"):
                if rec.get(field):
                    bad += [f"{key}.{field}: {f['found']}"
                            for f in lint.check_house_words(rec[field], TERMS, where=key)]
        for state, rec in doc.get("states", {}).items():
            for field in ("line", "short", "full"):
                if rec.get(field):
                    bad += [f"states.{state}.{field}: {f['found']}"
                            for f in lint.check_house_words(rec[field], TERMS, where=state)]
        self.assertEqual([], bad, "house vocabulary reached the screen")


class Exemptions(unittest.TestCase):
    """Each of these was a false positive in the first run."""

    def test_a_hed_may_capitalise_a_common_noun(self):
        """docs/UI.md puts heds in Title Case, so 'Sweep the Desk?' is correct."""
        self.assertNotIn("stray-capital", checks("Sweep the Desk?"))
        self.assertNotIn("stray-capital", checks("Add Project"))

    def test_a_common_noun_inside_a_title_term_is_that_term(self):
        self.assertNotIn("stray-capital", checks("the Desk Proposal is open"))
        self.assertNotIn("stray-capital", checks("open the Desk Proposal now"))

    def test_sentence_start_capital_is_english(self):
        self.assertNotIn("stray-capital", checks("Sweep closes the sitting."))
        self.assertNotIn("stray-capital", checks("- Desk records are append-only"))

    def test_code_spans_and_paths_are_not_prose(self):
        self.assertEqual([], check("see `desk proposal` in the schema"))
        self.assertEqual([], check("writes DESK-PROPOSAL.md to the desk"))
        self.assertEqual([], check("kettle/kits/prompts/desk proposal/x.md"))

    def test_the_lowercase_concept_is_not_a_miscased_control(self):
        """'sweep' the act must not read as a misspelling of the Sweep control."""
        self.assertEqual([], check("close each sitting with a sweep"))
        self.assertEqual([], check("approve alone is a desk bookmark"))


class Severity(unittest.TestCase):
    def test_catalog_values_are_errors_and_notes_are_warnings(self):
        import tempfile

        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "ui-copy.json"
            p.write_text(json.dumps({"keys": {
                "a": {"text": "edit the desk proposal", "note": "about the desk proposal"},
            }}), encoding="utf-8")
            found = lint.check_catalog(p, TERMS, "ui-copy.json")
            by_field = {f["where"].rsplit(".", 1)[-1]: f["severity_hint"] for f in found}
            self.assertEqual("error", by_field["text"])
            self.assertEqual("warn", by_field["note"])


class Baseline(unittest.TestCase):
    """The baseline blocks new drift without rewriting unreviewed copy first."""

    def test_baseline_entries_all_still_match_something(self):
        """A stale exemption is a lie about the codebase, so it fails the lint too."""
        import subprocess

        r = subprocess.run(
            [str(ROOT / "tools" / "lint-lexicon.py"), "--json"],
            capture_output=True, text=True, cwd=ROOT,
        )
        self.assertEqual([], json.loads(r.stdout)["stale_baseline"],
                         "run tools/lint-lexicon.py --update-baseline")

    def test_repo_has_no_unbaselined_errors(self):
        import subprocess

        r = subprocess.run(
            [str(ROOT / "tools" / "lint-lexicon.py")],
            capture_output=True, text=True, cwd=ROOT,
        )
        self.assertEqual(0, r.returncode, r.stdout + r.stderr)

    def test_baseline_only_shrinks(self):
        """Documented intent, checked cheaply: the file is a debt, not a config."""
        doc = json.loads((ROOT / "kettle" / "kits" / "_lexicon-baseline.json").read_text())
        self.assertIn("Shrink this list", doc["_note"])
        self.assertEqual([], doc["known"],
                         "the baseline is empty as of 2026-10-01 — fix the violation "
                         "rather than adding to this list")


if __name__ == "__main__":
    unittest.main()
