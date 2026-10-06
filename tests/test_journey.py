#!/usr/bin/env python3
"""The agent's journey with the user, as the prompts encode it.

Two rules run through every stage, and these tests hold the prompts to them:

1. Everything the agent offers reaches the user as a file, with why it is here and
   what the agent wants from them.
2. What the agent believes the user wants is visible and correctable — it lives in
   the project notes and changes only when a round's notes quote the change.

Nothing pinned the old journey, which is how a proposal about "What Sittings Should
Do" and "Sweep Extras" survived as the first thing a user was asked to sign. These
tests are the reason the next drift will be noticed.
"""

from __future__ import annotations

import importlib.util
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
KITS = ROOT / "kettle" / "kits"
PROMPTS = KITS / "prompts"


def prompt(name: str) -> str:
    return (PROMPTS / f"{name}.md").read_text(encoding="utf-8")


def headings(text: str) -> list[str]:
    return re.findall(r"^\s*##\s+(.+?)\s+—", text, re.M)


# The fields server.py passes to .format(): a prompt that grows a new {placeholder}
# raises KeyError mid-turn, in front of the user.
FIELDS = {
    "propose": dict(desk_dir="D", name="N", proposal_path="P", queue_path="Q", root="R"),
    "found": dict(desk_dir="D", name="N", proposal_path="P", queue_path="Q", root="R"),
    "sweep": dict(desk_dir="D", ledger="L", name="N", queue_path="Q", root="R",
                  runtime_dir="RT", stamp="S", today="T"),
    "interview-role": dict(name="N", root="R"),
}


class PromptsStillFormat(unittest.TestCase):
    def test_each_prompt_formats_with_the_fields_the_server_passes(self):
        for name, fields in FIELDS.items():
            with self.subTest(prompt=name):
                prompt(name).format(**fields)


class Handbook(unittest.TestCase):
    def test_the_two_rules_come_first(self):
        base = (KITS / "_base.md").read_text(encoding="utf-8")
        rules = base.index("## Two rules that come before everything else")
        brief = base.index("## The brief standard")
        self.assertLess(rules, brief)
        self.assertIn("reaches the user as a file", base)
        self.assertIn("What You Want From This Project", base)

    def test_agent_files_live_in_dot_kettle(self):
        self.assertIn("`.kettle/` folder, never in theirs",
                      (KITS / "_base.md").read_text(encoding="utf-8"))

    def test_plain_word_table_is_generated_and_current(self):
        spec = importlib.util.spec_from_file_location(
            "render", ROOT / "tools" / "render-lexicon-doc.py")
        assert spec is not None and spec.loader is not None
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        doc = json.loads((KITS / "_lexicon.json").read_text(encoding="utf-8"))
        now = (KITS / "_base.md").read_text(encoding="utf-8")
        self.assertEqual(mod.splice_handbook(doc, now), now,
                         "run tools/render-lexicon-doc.py")
        self.assertIn("| desk | project |", now)


class FirstLook(unittest.TestCase):
    """The interview meets the user through files, not through how the agent works."""

    def test_every_observation_names_a_file(self):
        p = prompt("interview-role")
        self.assertIn("TALK ABOUT FILES", p)
        self.assertIn("each naming a file they can open", p)
        self.assertIn("A count with no file attached does not count", p)

    def test_no_longer_asks_about_the_agents_setup(self):
        p = prompt("interview-role")
        for gone in ("working posture this desk wants", "for this desk specifically",
                     "review lens, sweep extras"):
            self.assertNotIn(gone, p)


class Proposal(unittest.TestCase):
    """The one approval before work starts is about the user's files and intent."""

    def test_sections_are_about_files_and_intent(self):
        hs = headings(prompt("propose"))
        self.assertEqual(
            ["What This Project Is", "What You Want From It", "The First Files",
             "What I Won't Change", "Others Working Here", "When You Finish a Batch",
             "Questions I Still Have"], hs)

    def test_the_old_process_sections_are_gone(self):
        p = prompt("propose")
        for gone in ("What Sittings Should Do", "Sweep Extras", "Fences —",
                     "Other Agents / Fleet", "Document Families"):
            self.assertNotIn(gone, p)

    def test_the_first_files_are_the_heart_of_it(self):
        self.assertIn("The First Files — the heart of the proposal", prompt("propose"))


class Founding(unittest.TestCase):
    def test_project_notes_carry_what_the_user_wants(self):
        p = prompt("found")
        self.assertIn("## What You Want From This Project", p)
        self.assertIn("quoting the change in that round's note", p)

    def test_first_batch_starts_with_the_files_they_approved(self):
        self.assertIn("Start from the proposal's The First Files", prompt("found"))


class Rounds(unittest.TestCase):
    def test_says_what_it_will_do_before_any_tool_call(self):
        p = prompt("sweep")
        self.assertLess(p.index("SAY WHAT YOU ARE ABOUT TO DO"), p.index("=== CLOSE ==="))
        self.assertIn("before any tool call", p)

    def test_set_aside_is_read_as_this_file_or_this_kind(self):
        p = prompt("sweep")
        self.assertIn("4b. SET ASIDE", p)
        self.assertIn("**this file**", p)
        self.assertIn("**this kind of file**", p)
        self.assertIn("Never put a set-aside file back", p)

    def test_round_notes_are_written_to_dot_kettle_and_queued_first(self):
        p = prompt("sweep")
        self.assertIn("{desk_dir}/rounds/{stamp}.md", p)
        self.assertIn("put it FIRST in the new queue", p)
        for section in ("## What I Did", "## What I Now Think You Want", "## What's Next"):
            self.assertIn(section, p)

    def test_intent_never_changes_silently(self):
        p = prompt("sweep")
        self.assertIn("quoted, before and after, in this round's notes", p)
        self.assertIn("Never change it silently", p)


class Briefs(unittest.TestCase):
    def test_the_reason_is_tied_to_what_the_user_said(self):
        b = (KITS / "frameworks" / "brief.md").read_text(encoding="utf-8")
        self.assertIn("tied to what they said they want", b)
        self.assertIn("set it aside", b)


if __name__ == "__main__":
    unittest.main()
