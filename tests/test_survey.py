"""Unit tests for the deterministic founding survey (Phase A)."""

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

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

    def test_register_project_seed_alone_still_reads_empty(self):
        """register_project() creates `.kettle/` (+ queue.json) before the first survey
        ever runs. That seed alone must not defeat empty/greenfield detection, nor show
        up as user content in top_level (regression: was reading 'Top level: .kettle/'
        and 'Empty / greenfield: no' for a folder nobody had put anything in yet)."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / ".kettle" / "runtime").mkdir(parents=True)
            (root / ".kettle" / "runtime" / "queue.json").write_text(
                json.dumps({"entries": [], "curated": "awaiting founding curation"}),
            )
            snap = survey.build_survey(root)
        self.assertTrue(snap["ok"])
        self.assertTrue(snap["empty"])
        self.assertEqual(snap["top_level"], [])
        self.assertFalse(snap["signals"]["kettle_desk"])
        block = survey.as_prompt_block(snap)
        self.assertIn("Empty / greenfield: yes", block)
        self.assertNotIn(".kettle", block)
        self.assertNotIn("existing .kettle desk", block)

    def test_kettle_dir_plus_bare_git_init_still_reads_empty(self):
        """`.kettle/` (register seed) alongside a freshly `git init`'d, commit-less repo
        (also common right after register_project) is still greenfield — git metadata
        with no tracked content is not user content either. `has_git` stays True."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / ".kettle").mkdir()
            _init_git_repo(root)
            snap = survey.build_survey(root)
        self.assertTrue(snap["ok"])
        self.assertTrue(snap["empty"])
        self.assertTrue(snap["signals"]["git"])
        self.assertNotIn(".kettle", [e["name"] for e in snap["top_level"]])

    def test_kettle_desk_signal_requires_founded_charter(self):
        """The 'existing .kettle desk' signal should fire only for a founded charter
        (.kettle/PROJECT.md), not for the bare register-seeded dir."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / ".kettle").mkdir()
            (root / ".kettle" / "PROJECT.md").write_text("# Some Project\n")
            (root / "README.md").write_text("# Some Project\n")
            snap = survey.build_survey(root)
        self.assertFalse(snap["empty"])
        self.assertTrue(snap["signals"]["kettle_desk"])
        self.assertIn("existing .kettle desk", survey.as_prompt_block(snap))

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


    def test_max_depth_bounds_the_dated_observations(self):
        """The scope note forbids deeper paths, so the survey must not cite them."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _init_git_repo(root)
            (root / "top.md").write_text("top\n")
            (root / "a" / "b").mkdir(parents=True)
            (root / "a" / "b" / "deep.md").write_text("deep\n")
            _git(root, "add", ".")
            _git(root, "commit", "-q", "-m", "files")
            snap = survey.build_survey(root, max_depth=1)
            paths = [p["path"] for p in snap["git_activity"]["top_changed_paths"]]
            self.assertEqual(paths, ["top.md"])
            self.assertIsNone(snap["mtime_buckets"])  # git history answers recency

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "top.md").write_text("top\n")
            (root / "a" / "b").mkdir(parents=True)
            (root / "a" / "mid.md").write_text("mid\n")
            (root / "a" / "b" / "deep.md").write_text("deep\n")
            self.assertEqual(sum(survey.build_survey(root, max_depth=1)["mtime_buckets"].values()), 1)
            self.assertEqual(sum(survey.build_survey(root, max_depth=2)["mtime_buckets"].values()), 2)
            self.assertEqual(sum(survey.build_survey(root)["mtime_buckets"].values()), 3)

    def test_recent_activity_counts_read_cumulatively(self):
        snap = {"top_level": [], "signals": {}, "samples": {}, "git_activity": None,
                "mtime_buckets": {"last_24h": 3, "last_7d": 2, "last_30d": 5, "older": 9}}
        block = survey.as_prompt_block(snap)
        self.assertIn("3 file(s) touched in the last 24h, 5 in the last 7 days, "
                      "10 in the last 30 days", block)

if __name__ == "__main__":
    unittest.main()
