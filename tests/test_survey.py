"""Unit tests for the deterministic founding survey (Phase A)."""

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

import kettle.kits as kits
import kettle.survey as survey


def _git(root, *args):
    subprocess.run(["git", "-C", str(root), *args], check=True,
                    capture_output=True, text=True)


def _init_git_repo(root: Path) -> None:
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "reader@example.test")
    _git(root, "config", "user.name", "Reader")


class TestBuildSurvey(unittest.TestCase):
    def test_empty_folder(self):
        with tempfile.TemporaryDirectory() as td:
            snap = survey.build_survey(td)
        self.assertTrue(snap["ok"])
        self.assertTrue(snap["empty"])
        self.assertEqual(snap["suggested_prechecks"].get("status"),
                         ["Brand new — starting from scratch"])

    def test_samples_readme_and_markers(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "README.md").write_text("# Hello project\n\nA demo.\n")
            (root / "CLAUDE.md").write_text("Agent notes.\n")
            (root / "src").mkdir()
            (root / ".git").mkdir()
            snap = survey.build_survey(root)
        self.assertTrue(snap["ok"])
        self.assertFalse(snap["empty"])
        self.assertIn("README.md", snap["samples"])
        self.assertIn("Hello project", snap["samples"]["README.md"])
        self.assertTrue(snap["signals"]["git"])
        self.assertIn("CLAUDE.md", snap["signals"]["agent_markers"])
        fleet = snap["suggested_prechecks"].get("fleet") or []
        self.assertTrue(any("Coding agents" in o for o in fleet))

    def test_as_prompt_block_includes_core_survey(self):
        with tempfile.TemporaryDirectory() as td:
            (Path(td) / "README.md").write_text("Title\n")
            snap = survey.build_survey(td)
        block = survey.as_prompt_block(snap)
        self.assertIn("CORE SURVEY", block)
        self.assertIn("README.md", block)

    def test_reports_legacy_setsweep_desk_without_treating_it_as_kettle(self):
        with tempfile.TemporaryDirectory() as td:
            (Path(td) / ".setsweep").mkdir()
            snap = survey.build_survey(td)
        self.assertFalse(snap["signals"]["kettle_desk"])
        self.assertTrue(snap["signals"]["legacy_setsweep_desk"])
        self.assertIn("legacy .setsweep desk", survey.as_prompt_block(snap))

    def test_dump_roundtrip(self):
        with tempfile.TemporaryDirectory() as td:
            snap = survey.build_survey(td)
            p = Path(td) / "survey.json"
            p.write_text(survey.dump(snap))
            loaded = survey.load(p)
        self.assertEqual(loaded["root"], snap["root"])
        self.assertEqual(loaded["empty"], snap["empty"])

    def test_git_activity_cites_a_real_date_and_path(self):
        # P2: the interview opening must cite real git activity, not just presence.
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _init_git_repo(root)
            (root / "README.md").write_text("# Hello\n")
            _git(root, "add", "README.md")
            _git(root, "commit", "-q", "-m", "first commit")
            (root / "README.md").write_text("# Hello\n\nmore\n")
            _git(root, "add", "README.md")
            _git(root, "commit", "-q", "-m", "second commit")
            snap = survey.build_survey(root)

        self.assertTrue(snap["signals"]["git"])
        activity = snap["git_activity"]
        self.assertIsNotNone(activity)
        self.assertRegex(activity["last_commit_date"], r"^\d{4}-\d{2}-\d{2}$")
        self.assertEqual(activity["commits_last_30d"], 2)
        self.assertEqual(activity["author_count"], 1)
        paths = [p["path"] for p in activity["top_changed_paths"]]
        self.assertIn("README.md", paths)

        block = survey.as_prompt_block(snap)
        self.assertIn(activity["last_commit_date"], block)
        self.assertIn("README.md", block)

    def test_git_activity_none_for_dot_git_dir_that_is_not_a_repo(self):
        # A bare .git/ marker (no actual repository) must not crash or fabricate dates.
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / ".git").mkdir()
            (root / "README.md").write_text("# Hi\n")
            snap = survey.build_survey(root)
        self.assertTrue(snap["signals"]["git"])
        self.assertIsNone(snap["git_activity"])
        # falls back to mtime buckets instead of fabricating git history
        self.assertIsNotNone(snap["mtime_buckets"])

    def test_mtime_buckets_present_for_non_git_root(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "notes.md").write_text("hi\n")
            snap = survey.build_survey(root)
        self.assertIsNone(snap["git_activity"])
        buckets = snap["mtime_buckets"]
        self.assertIsNotNone(buckets)
        self.assertEqual(sum(buckets.values()), 1)  # the one file just written
        self.assertIn(
            "Recent activity (filesystem, no usable git history)",
            survey.as_prompt_block(snap),
        )


class TestCardStems(unittest.TestCase):
    def test_card_starts_blank(self):
        text = kits._render_stems(kits.BASE_INTERVIEW[:1])
        self.assertNotIn("- [x]", text)
        self.assertIn("- [ ] Brand new — starting from scratch", text)
        self.assertIn("- [ ] In motion — active work under way", text)

    def test_card_has_required_stems(self):
        stems = kits.interview_stems(None)
        body = "\n".join(f"### {i}. [{s['id']}] {s['stem']}" for i, s in enumerate(stems, 1))
        self.assertEqual(kits.card_has_required_stems(body), [])
        self.assertIn("status", kits.card_has_required_stems("no card here"))


if __name__ == "__main__":
    unittest.main()
