"""Unit tests for the deterministic founding survey (Phase A)."""

import json
import os
import subprocess
import tempfile
import unittest
from datetime import datetime, timezone
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

    def test_readme_sampled_once_under_exact_name_matching(self):
        """_SAMPLE_NAMES lists both README.md and Readme.md; on a case-insensitive
        disk both resolve to the one file and the prompt block used to print the
        README twice. Sampling must key off the names actually in the root
        listing, so only the name that exists is sampled."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "README.md").write_text("# Once only\n")
            snap = survey.build_survey(root)
            block = survey.as_prompt_block(snap)
        readme_samples = [k for k in snap["samples"] if k.upper().startswith("README")]
        self.assertEqual(readme_samples, ["README.md"])
        self.assertEqual(block.count("--- README.md ---"), 1)

    def test_mtime_buckets_skip_os_noise(self):
        """.DS_Store carries no project signal: alone it must not count as a
        touched file, and next to real files it must not inflate the count."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / ".DS_Store").write_text("noise")
            snap = survey.build_survey(root)
            self.assertIsNone(snap["mtime_buckets"])
            self.assertIsNone(snap["recent_paths"])
            self.assertIsNone(snap["oldest_path"])
            self.assertNotIn("Recent activity", survey.as_prompt_block(snap))
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / ".DS_Store").write_text("noise")
            (root / "notes.md").write_text("hi\n")
            snap = survey.build_survey(root)
            self.assertEqual(sum(snap["mtime_buckets"].values()), 1)

    def test_non_git_recency_names_files_with_dates(self):
        """Without git history the survey still lets the interview make a dated,
        file-naming observation: the three newest files and the single oldest."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "chapters").mkdir()
            (root / "notes").mkdir()
            for rel, day in (
                ("chapters/09.md", "2026-03-02"),
                ("notes/timeline.md", "2026-09-30"),
                ("chapters/01.md", "2026-10-03"),
                ("chapters/04.md", "2026-10-12"),
            ):
                p = root / rel
                p.write_text("x\n")
                ts = datetime.strptime(day, "%Y-%m-%d").replace(
                    tzinfo=timezone.utc).timestamp()
                os.utime(p, (ts, ts))
            snap = survey.build_survey(root)
        self.assertIsNone(snap["git_activity"])
        self.assertEqual(snap["recent_paths"], [
            {"path": "chapters/04.md", "date": "2026-10-12"},
            {"path": "chapters/01.md", "date": "2026-10-03"},
            {"path": "notes/timeline.md", "date": "2026-09-30"},
        ])
        self.assertEqual(snap["oldest_path"],
                         {"path": "chapters/09.md", "date": "2026-03-02"})
        block = survey.as_prompt_block(snap)
        self.assertIn(
            "Most recently touched: chapters/04.md (2026-10-12), "
            "chapters/01.md (2026-10-03), notes/timeline.md (2026-09-30).",
            block,
        )
        self.assertIn("Least recently touched: chapters/09.md (2026-03-02).", block)

    def test_recent_paths_respect_max_depth(self):
        """The scope bound applies to per-file recency too: a file deeper than
        max_depth must never be named."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "top.md").write_text("top\n")
            (root / "sub").mkdir()
            (root / "sub" / "deep.md").write_text("deep\n")
            snap = survey.build_survey(root, max_depth=1)
        self.assertEqual([r["path"] for r in snap["recent_paths"]], ["top.md"])
        self.assertEqual(snap["oldest_path"]["path"], "top.md")
        self.assertNotIn("deep.md", survey.as_prompt_block(snap))

    def test_top_level_dirs_list_their_children(self):
        """Each top-level dir shows up to 8 immediate entry names plus the true
        count, so the reader can name what a folder holds without tools."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            d = root / "chapters"
            d.mkdir()
            for i in range(10):
                (d / f"{i:02d}-file.md").write_text("x\n")
            (d / ".DS_Store").write_text("noise")  # filtered, not counted
            (d / ".git").mkdir()                   # skip-set dir, filtered
            snap = survey.build_survey(root)
            ent = next(e for e in snap["top_level"] if e["name"] == "chapters")
            block = survey.as_prompt_block(snap)
        self.assertEqual(ent["child_count"], 10)
        self.assertEqual(len(ent["children"]), 8)
        self.assertEqual(ent["children"][0], "00-file.md")
        self.assertIn("chapters/ (10 entries:", block)
        self.assertIn("00-file.md, 01-file.md", block)
        self.assertIn("…", block)
        self.assertNotIn(".DS_Store", block)

    def test_top_level_children_mark_dirs_and_hide_noise(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            d = root / "proj"
            d.mkdir()
            (d / "sub").mkdir()
            (d / ".kettle").mkdir()
            (d / "a.md").write_text("x\n")
            snap = survey.build_survey(root)
            ent = next(e for e in snap["top_level"] if e["name"] == "proj")
        self.assertEqual(ent["child_count"], 2)
        self.assertEqual(ent["children"], ["a.md", "sub/"])
        self.assertIn("proj/ (2 entries: a.md, sub/)",
                      survey.as_prompt_block(snap))

    def test_top_level_children_skip_skip_set_dirs(self):
        """A top-level dir the walk would never descend into (node_modules,
        .venv, dist, target …) must not have its entries read or rendered —
        it keeps the bare 'name/' line."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            nm = root / "node_modules"
            nm.mkdir()
            for i in range(3):
                (nm / f"pkg{i}.js").write_text("x\n")
            src = root / "src"
            src.mkdir()
            (src / "main.py").write_text("x\n")
            snap = survey.build_survey(root)
            block = survey.as_prompt_block(snap)
        nm_ent = next(e for e in snap["top_level"] if e["name"] == "node_modules")
        src_ent = next(e for e in snap["top_level"] if e["name"] == "src")
        self.assertNotIn("children", nm_ent)
        self.assertNotIn("child_count", nm_ent)
        self.assertEqual(src_ent["children"], ["main.py"])
        self.assertIn("  - node_modules/\n", block)
        self.assertNotIn("pkg0", block)
        self.assertIn("src/ (1 entry: main.py)", block)

    def test_top_level_children_omitted_at_depth_one(self):
        """max_depth=1 forbids citing anything below the root — including the
        children listing, so dirs render in the old bare form."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "chapters").mkdir()
            (root / "chapters" / "01.md").write_text("x\n")
            snap = survey.build_survey(root, max_depth=1)
            ent = next(e for e in snap["top_level"] if e["name"] == "chapters")
            block = survey.as_prompt_block(snap)
        self.assertNotIn("children", ent)
        self.assertIn("  - chapters/\n", block)
        self.assertNotIn("entries:", block)

    def test_git_activity_reports_sample_dates_and_recent_subjects(self):
        """Git roots get the same dated observation power: the last commit date
        per sampled orientation file and the newest commit subjects."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _init_git_repo(root)
            (root / "README.md").write_text("# One\n")
            (root / "CLAUDE.md").write_text("notes\n")
            (root / "uncommitted.txt").write_text("never added\n")
            _git(root, "add", "README.md", "CLAUDE.md")
            _git(root, "commit", "-q", "-m", "Add readme and agent notes")
            (root / "README.md").write_text("# Two\n")
            _git(root, "add", "README.md")
            _git(root, "commit", "-q", "-m", "Revise the readme")
            snap = survey.build_survey(root)
            activity = snap["git_activity"]
            block = survey.as_prompt_block(snap)
        self.assertIn("sample_dates", activity)
        self.assertIn("recent_commits", activity)
        # two commits touched README.md, one touched CLAUDE.md; uncommitted.txt
        # was never sampled and never committed
        self.assertEqual(set(activity["sample_dates"]), {"README.md", "CLAUDE.md"})
        for d in activity["sample_dates"].values():
            self.assertRegex(d, r"^\d{4}-\d{2}-\d{2}$")
        subjects = [c["subject"] for c in activity["recent_commits"]]
        self.assertEqual(subjects, ["Revise the readme", "Add readme and agent notes"])
        for c in activity["recent_commits"]:
            self.assertRegex(c["date"], r"^\d{4}-\d{2}-\d{2}$")
        self.assertIn("Orientation files last committed: README.md "
                      f"{activity['sample_dates']['README.md']}, CLAUDE.md "
                      f"{activity['sample_dates']['CLAUDE.md']}", block)
        self.assertIn("Last commits:", block)
        self.assertIn("Revise the readme", block)

    def test_recent_activity_counts_read_cumulatively(self):
        snap = {"top_level": [], "signals": {}, "samples": {}, "git_activity": None,
                "mtime_buckets": {"last_24h": 3, "last_7d": 2, "last_30d": 5, "older": 9}}
        block = survey.as_prompt_block(snap)
        self.assertIn("3 file(s) touched in the last 24h, 5 in the last 7 days, "
                      "10 in the last 30 days", block)

if __name__ == "__main__":
    unittest.main()
