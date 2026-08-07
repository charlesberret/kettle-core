#!/usr/bin/env python3
"""Unit tests for gitmap layers: probe · history · grid · payload (no HTTP)."""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path

import kettle.gitmap as gitmap


def _git_available() -> bool:
    try:
        subprocess.run(["git", "--version"], capture_output=True, check=True)
        return True
    except (OSError, subprocess.CalledProcessError):
        return False


def _init_repo(root: Path) -> None:
    subprocess.run(["git", "init"], cwd=root, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=root, check=True, capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=root, check=True, capture_output=True,
    )


def _commit_on(root: Path, rel: str, body: str, day: date, msg: str = "c") -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body)
    subprocess.run(["git", "add", rel], cwd=root, check=True, capture_output=True)
    env = os.environ.copy()
    stamp = day.isoformat() + "T12:00:00"
    env["GIT_AUTHOR_DATE"] = stamp
    env["GIT_COMMITTER_DATE"] = stamp
    subprocess.run(
        ["git", "commit", "-m", msg],
        cwd=root, check=True, capture_output=True, env=env,
    )


class ClampAndCalendar(unittest.TestCase):
    def test_clamp_weeks(self):
        self.assertEqual(gitmap.clamp_weeks(26), 26)
        self.assertEqual(gitmap.clamp_weeks(1), gitmap.MIN_WEEKS)
        self.assertEqual(gitmap.clamp_weeks(99), gitmap.MAX_WEEKS)
        self.assertEqual(gitmap.clamp_weeks("nope"), gitmap.DEFAULT_WEEKS)
        self.assertEqual(gitmap.clamp_weeks(None), gitmap.DEFAULT_WEEKS)

    def test_sunday_on_or_before(self):
        self.assertEqual(
            gitmap.sunday_on_or_before(date(2026, 7, 28)),
            date(2026, 7, 26),
        )
        self.assertEqual(
            gitmap.sunday_on_or_before(date(2026, 7, 26)),
            date(2026, 7, 26),
        )

    def test_window_bounds(self):
        today = date(2026, 7, 28)
        first, last = gitmap.window_bounds(today, 4)
        self.assertEqual(last, today)
        self.assertEqual(first.weekday(), 6)  # Sunday
        self.assertEqual(first, date(2026, 7, 5))

    def test_weeks_for_repo_age(self):
        today = date(2026, 7, 28)
        # 3-day-old repo → min weeks
        self.assertEqual(
            gitmap.weeks_for_repo_age(today, date(2026, 7, 25)),
            gitmap.MIN_WEEKS,
        )
        # ~10 weeks of history
        first = date(2026, 5, 15)
        n = gitmap.weeks_for_repo_age(today, first)
        self.assertGreaterEqual(n, 10)
        self.assertLessEqual(n, gitmap.ADAPTIVE_CAP)
        # ancient → capped
        self.assertEqual(
            gitmap.weeks_for_repo_age(today, date(2020, 1, 1)),
            gitmap.ADAPTIVE_CAP,
        )
        # unknown → full cap
        self.assertEqual(gitmap.weeks_for_repo_age(today, None), gitmap.ADAPTIVE_CAP)


class LevelAndGrid(unittest.TestCase):
    def test_level_for_count_sevenths(self):
        self.assertEqual(gitmap.level_for_count(0, 10), 0)
        # Smallest unit = 1/7 of full (level 1…7)
        self.assertEqual(gitmap.level_for_count(1, 1, grain="day"), 1)
        self.assertEqual(gitmap.level_for_count(1, 7, grain="day"), 1)
        self.assertEqual(gitmap.level_for_count(3, 7, grain="day"), 3)
        self.assertEqual(gitmap.level_for_count(7, 7, grain="day"), 7)
        self.assertEqual(gitmap.level_for_count(100, 7, grain="day"), 7)
        # Week grain: active-days input (0–7)
        self.assertEqual(gitmap.level_for_count(1, 7, grain="week"), 1)
        self.assertEqual(gitmap.level_for_count(4, 7, grain="week"), 4)

    def test_scale_ceiling_min_floor(self):
        self.assertGreaterEqual(gitmap.scale_ceiling([1, 1, 1], grain="day"), gitmap._MIN_CEILING)
        self.assertGreaterEqual(
            gitmap.scale_ceiling([5, 6, 7, 8, 9, 10], grain="day"), 8
        )

    def test_should_use_week_grain(self):
        self.assertTrue(gitmap.should_use_week_grain(total=5, active_days=3))
        # high total alone → day grain (bursty but active project)
        self.assertFalse(gitmap.should_use_week_grain(total=100, active_days=5))
        self.assertFalse(gitmap.should_use_week_grain(total=50, active_days=20))

    def test_build_day_grid_column_major(self):
        first = date(2026, 7, 5)
        today = date(2026, 7, 28)
        counts = {
            "2026-07-05": 1,
            "2026-07-28": 4,
            "2026-07-20": 2,
        }
        cells, total, max_c, active = gitmap.build_day_grid(counts, first, today, 4)
        self.assertEqual(len(cells), 4 * 7)
        self.assertEqual(total, 1 + 4 + 2)
        self.assertEqual(max_c, 4)
        self.assertEqual(active, 3)
        self.assertEqual(cells[0]["date"], "2026-07-05")
        self.assertEqual(cells[0]["level"], 1)  # 1 commit = 1/7
        sun_today_week = date(2026, 7, 26)
        w = (sun_today_week.toordinal() - first.toordinal()) // 7
        dow = (today.weekday() + 1) % 7
        idx = w * 7 + dow
        self.assertEqual(cells[idx]["date"], "2026-07-28")
        self.assertEqual(cells[idx]["count"], 4)
        self.assertEqual(cells[idx]["level"], 4)  # 4 commits = 4/7

    def test_build_week_grid(self):
        first = date(2026, 7, 5)
        today = date(2026, 7, 28)
        counts = {
            "2026-07-05": 1,
            "2026-07-06": 1,
            "2026-07-28": 4,
        }
        cells, total, max_c = gitmap.build_week_grid(counts, first, today, 4)
        self.assertEqual(len(cells), 4)
        self.assertEqual(total, 6)
        # first week: 2 active days → level 2 (2/7)
        self.assertEqual(cells[0]["active_days"], 2)
        self.assertEqual(cells[0]["level"], 2)
        self.assertGreaterEqual(cells[0]["count"], 2)


class MtimeFallback(unittest.TestCase):
    """Filesystem mtime path — no git required."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="kettle-mtime-"))
        self.root = self.tmp / "desk"
        self.root.mkdir()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_mtime_counts_and_skips_noise(self):
        today = date(2026, 7, 28)
        (self.root / "note.md").write_text("hi\n")
        noise = self.root / "node_modules" / "pkg"
        noise.mkdir(parents=True)
        (noise / "index.js").write_text("x\n")
        t = datetime(2026, 7, 15, 10, 0, 0).timestamp()
        os.utime(self.root / "note.md", (t, t))
        counts, oldest, seen, trunc = gitmap.mtime_counts_by_day(
            self.root, today=today,
        )
        self.assertFalse(trunc)
        self.assertEqual(seen, 1)
        self.assertEqual(counts.get("2026-07-15"), 1)
        self.assertEqual(oldest, date(2026, 7, 15))

    def test_mtime_payload_adaptive(self):
        today = date(2026, 7, 28)
        p = self.root / "only.md"
        p.write_text("body\n")
        t = datetime(2026, 7, 10, 9, 0, 0).timestamp()
        os.utime(p, (t, t))
        act = gitmap.mtime_file_activity(self.root, weeks=None, today=today)
        self.assertEqual(act["source"], "mtime")
        self.assertFalse(act["git"])
        self.assertTrue(act["adaptive"])
        self.assertGreaterEqual(act["total"], 1)
        self.assertTrue(act["cells"])


@unittest.skipUnless(_git_available(), "git not on PATH")
class ProbeAndHistory(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="kettle-gitmap-"))
        self.root = self.tmp / "repo"
        self.root.mkdir()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_probe_nongit(self):
        self.assertFalse(gitmap.probe_git(self.root))
        self.assertFalse(gitmap.probe_git(self.tmp / "missing"))

    def test_probe_and_counts(self):
        _init_repo(self.root)
        self.assertTrue(gitmap.probe_git(self.root))
        today = date.today()
        _commit_on(self.root, "a.txt", "one\n", today - timedelta(days=2), "a")
        _commit_on(self.root, "a.txt", "two\n", today, "b")
        first, _ = gitmap.window_bounds(today, 4)
        counts, err = gitmap.commit_counts_by_day(self.root, first)
        self.assertIsNone(err)
        self.assertGreaterEqual(counts.get(today.isoformat(), 0), 1)

    def test_payload_nongit_uses_mtime(self):
        """Non-git roots get a filesystem mtime heatmap (not an empty strip)."""
        today = date(2026, 7, 28)
        # Two files with distinct mtimes inside the fixed window
        a = self.root / "a.md"
        b = self.root / "b.md"
        a.write_text("alpha\n")
        b.write_text("beta\n")
        t_a = datetime(2026, 7, 20, 12, 0, 0).timestamp()
        t_b = datetime(2026, 7, 27, 12, 0, 0).timestamp()
        os.utime(a, (t_a, t_a))
        os.utime(b, (t_b, t_b))
        act = gitmap.git_commit_activity(self.root, weeks=8, today=today)
        self.assertTrue(act["ok"])
        self.assertFalse(act["git"])
        self.assertEqual(act["source"], "mtime")
        self.assertEqual(act["weeks"], 8)
        self.assertGreaterEqual(act["total"], 2)
        self.assertTrue(act["cells"])
        lit = [c for c in act["cells"] if c.get("count")]
        self.assertTrue(lit)
        self.assertTrue(all(1 <= c["level"] <= 7 for c in lit))

    def test_payload_sparse_uses_week_grain_and_adaptive(self):
        _init_repo(self.root)
        today = date(2026, 7, 28)
        for i, offset in enumerate((10, 3, 0)):
            _commit_on(
                self.root, "note.txt", f"line {i}\n",
                today - timedelta(days=offset), f"c{i}",
            )
        # adaptive (weeks=None)
        act = gitmap.git_commit_activity(self.root, weeks=None, today=today)
        self.assertTrue(act["ok"])
        self.assertTrue(act["git"])
        self.assertTrue(act["adaptive"])
        self.assertLessEqual(act["weeks"], gitmap.ADAPTIVE_CAP)
        self.assertGreaterEqual(act["weeks"], gitmap.MIN_WEEKS)
        # 3 commits → sparse → week grain
        self.assertEqual(act["grain"], "week")
        self.assertEqual(act["rows"], 1)
        self.assertEqual(len(act["cells"]), act["weeks"])
        self.assertGreaterEqual(act["total"], 3)
        # sparse: each lit week is a few sevenths, not full
        lit = [c for c in act["cells"] if c["count"]]
        self.assertTrue(lit)
        self.assertTrue(all(1 <= c["level"] <= 7 for c in lit))
        self.assertTrue(all(c["level"] <= 3 for c in lit))

    def test_payload_fixed_weeks_day_grain_when_dense(self):
        _init_repo(self.root)
        today = date(2026, 7, 28)
        # Many commits on many days so day grain wins
        for i in range(25):
            _commit_on(
                self.root, "note.txt", f"line {i}\n",
                today - timedelta(days=i), f"c{i}",
            )
        act = gitmap.git_commit_activity(self.root, weeks=8, today=today)
        self.assertFalse(act["adaptive"])
        self.assertEqual(act["weeks"], 8)
        self.assertEqual(act["grain"], "day")
        self.assertEqual(len(act["cells"]), 8 * 7)


if __name__ == "__main__":
    unittest.main()
