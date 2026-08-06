"""Local git contribution heatmap for a project root.

Pinned decisions (desk chrome strip next to the project selector):
  - Root: the registered project root only (no walk-up to a parent monorepo).
  - Window: **adaptive** to repo age by default (min 2 … max 26 weeks), stretch
    full strip width; optional fixed ``weeks=`` still allowed via API.
  - Grain: **day** grid when dense enough; **week** bars when sparse / young
    (so new projects fill the slot instead of a sea of empty day cells).
  - Week start: Sunday (classic GitHub); day grain = columns weeks × rows Sun→Sat.
  - Scope: ``git log --all`` (every ref), all authors.
  - Levels: 0–7 in **sevenths** of full intensity (1 commit / 1 active day =
    1/7). Absolute and relative scales; quieter of the two wins.
  - Network: none — subprocess ``git`` against the on-disk work tree only.

Layers (build / test bottom-up):
  1. probe   — is this path a git work tree?
  2. history — commit counts by calendar day + first-commit date
  3. grid    — day or week cells with level 0–4
  4. payload — assemble the API/UI dict (``git_commit_activity``)
"""

from __future__ import annotations

import math
import subprocess
from datetime import date
from pathlib import Path
from typing import Any, Optional


DEFAULT_WEEKS = 26          # adaptive cap / fixed-window default
MIN_WEEKS = 2               # brand-new repos still get a couple of fat columns
MAX_WEEKS = 52              # hard clamp when caller forces weeks=
ADAPTIVE_CAP = 26
# Switch to week grain when the day grid would look empty.
SPARSE_ACTIVE_DAYS = 15
SPARSE_TOTAL_COMMITS = 20
# Sunday-first columns (GitHub classic). 0=Sun … 6=Sat.
DOW_START_SUNDAY = 0


def clamp_weeks(weeks: Any, default: int = DEFAULT_WEEKS) -> int:
    try:
        n = int(weeks)
    except (TypeError, ValueError):
        n = default
    return max(MIN_WEEKS, min(n, MAX_WEEKS))


def probe_git(root: Path, *, timeout: float = 5.0) -> bool:
    """True when *root* is inside a git work tree."""
    root = Path(root).expanduser()
    if not root.is_dir():
        return False
    try:
        probe = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "--is-inside-work-tree"],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return probe.returncode == 0 and (probe.stdout or "").strip() == "true"


def sunday_on_or_before(day: date) -> date:
    """Sunday of the week containing *day* (Python weekday: Mon=0 … Sun=6)."""
    days_since_sun = (day.weekday() + 1) % 7  # Mon→1 … Sun→0
    return date.fromordinal(day.toordinal() - days_since_sun)


def window_bounds(today: date, weeks: int) -> tuple[date, date]:
    """Inclusive window: first Sunday of the leftmost column → *today*."""
    weeks = clamp_weeks(weeks)
    week_sunday = sunday_on_or_before(today)
    first_sunday = date.fromordinal(week_sunday.toordinal() - 7 * (weeks - 1))
    return first_sunday, today


def first_commit_date(root: Path, *, timeout: float = 15.0) -> Optional[date]:
    """Author date of the oldest root commit on any ref, or None.

    Note: ``git log --reverse -n 1`` is *not* reliable (``-n`` applies before
    ``--reverse`` on many git builds). Use root commits via ``rev-list``.
    """
    root = Path(root).expanduser().resolve()
    try:
        roots = subprocess.run(
            ["git", "-C", str(root), "rev-list", "--max-parents=0", "--all"],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if roots.returncode != 0:
        return None
    shas = [s.strip() for s in (roots.stdout or "").splitlines() if s.strip()]
    if not shas:
        return None
    oldest: Optional[date] = None
    for sha in shas:
        try:
            log = subprocess.run(
                [
                    "git", "-C", str(root), "log", "-1",
                    "--pretty=format:%cs", "--no-show-signature", sha,
                ],
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        except (OSError, subprocess.TimeoutExpired):
            continue
        if log.returncode != 0:
            continue
        line = (log.stdout or "").strip()
        if not line:
            continue
        try:
            y, m, d = (int(x) for x in line.split("-", 2))
            dt = date(y, m, d)
        except (TypeError, ValueError):
            continue
        if oldest is None or dt < oldest:
            oldest = dt
    return oldest


def weeks_for_repo_age(
    today: date,
    first: Optional[date],
    *,
    min_weeks: int = MIN_WEEKS,
    max_weeks: int = ADAPTIVE_CAP,
) -> int:
    """How many Sunday-columns to show given repo birth date (or full cap if unknown)."""
    max_weeks = max(min_weeks, max_weeks)
    if first is None:
        return max_weeks
    if first > today:
        first = today
    first_sun = sunday_on_or_before(first)
    last_sun = sunday_on_or_before(today)
    span = ((last_sun.toordinal() - first_sun.toordinal()) // 7) + 1
    return max(min_weeks, min(int(span), max_weeks))


def commit_counts_by_day(
    root: Path,
    since: date,
    *,
    timeout: float = 20.0,
) -> tuple[dict[str, int], Optional[str]]:
    """Return ({YYYY-MM-DD: count}, error_or_None) from local ``git log --all``."""
    root = Path(root).expanduser().resolve()
    counts: dict[str, int] = {}
    try:
        log = subprocess.run(
            [
                "git",
                "-C",
                str(root),
                "log",
                "--all",
                f"--since={since.isoformat()}",
                "--pretty=format:%cs",
                "--no-show-signature",
            ],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {}, str(exc)[:200]
    if log.returncode != 0:
        err = ((log.stderr or "git log failed").strip() or "git log failed")[:200]
        return {}, err
    for line in (log.stdout or "").splitlines():
        d = line.strip()
        if d:
            counts[d] = counts.get(d, 0) + 1
    return counts, None


# Intensity is measured in **sevenths** of full (level 0–7). One unit = 1/7.
# Absolute: 1 commit (day) or 1 active day (week) → level 1; 7+ → full.
# Relative: same sevenths of *ceiling*, with ceiling floored at 7 so a single
# sample never becomes “full scale”.
MAX_LEVEL = 7
_MIN_CEILING = MAX_LEVEL  # at least seven units of headroom


def scale_ceiling(positive_counts: list[int], *, grain: str = "day") -> int:
    """~p90 of positive bucket counts, floored at 7 so 1 unit ≠ full scale."""
    del grain  # same floor for day/week; kept for call-site symmetry
    if not positive_counts:
        return _MIN_CEILING
    xs = sorted(positive_counts)
    idx = min(len(xs) - 1, max(0, math.ceil(0.9 * len(xs)) - 1))
    return max(_MIN_CEILING, int(xs[idx]))


def level_for_count(count: int, ceiling: int, *, grain: str = "day") -> int:
    """Map a bucket count to intensity 0–7 (each step = 1/7 of full).

    *count* is commits (day grain) or active days in the week (week grain).
    Absolute sevenths: ``min(7, count)``. Relative: sevenths of *ceiling*.
    Returns the quieter of the two.
    """
    del grain
    if count <= 0:
        return 0
    n = int(count)
    abs_lv = min(MAX_LEVEL, n)  # 1 → 1/7, 7 → full
    ceiling = max(_MIN_CEILING, int(ceiling))
    # How many sevenths of the ceiling does this count fill?
    rel_lv = min(MAX_LEVEL, math.ceil(MAX_LEVEL * n / ceiling))
    return min(abs_lv, rel_lv)


def should_use_week_grain(*, total: int, active_days: int) -> bool:
    """Young / sparse histories look better as week bars than a hollow day grid.

    Require *both* low active-day count and low total so a busy repo with
    commits piled on a few days still gets the day calendar.
    """
    return active_days < SPARSE_ACTIVE_DAYS and total < SPARSE_TOTAL_COMMITS


def build_day_grid(
    counts: dict[str, int],
    first_sunday: date,
    today: date,
    weeks: int,
) -> tuple[list[dict[str, Any]], int, int, int]:
    """Column-major day cells (week × weekday Sun→Sat).

    Returns (cells, total, max_bucket, active_days).
    """
    weeks = clamp_weeks(weeks)
    raw: list[dict[str, Any]] = []
    positives: list[int] = []
    total = 0
    active_days = 0
    for w in range(weeks):
        for dow in range(7):
            d = date.fromordinal(first_sunday.toordinal() + w * 7 + dow)
            if d > today:
                c = 0
            else:
                c = int(counts.get(d.isoformat(), 0))
            raw.append({"date": d.isoformat(), "count": c})
            if d <= today and c:
                positives.append(c)
                total += c
                active_days += 1
    ceiling = scale_ceiling(positives, grain="day")
    max_c = max(positives) if positives else 0
    cells = [
        {
            "date": cell["date"],
            "count": int(cell["count"]),
            "level": level_for_count(int(cell["count"]), ceiling, grain="day"),
        }
        for cell in raw
    ]
    return cells, total, max_c, active_days


def build_week_grid(
    counts: dict[str, int],
    first_sunday: date,
    today: date,
    weeks: int,
) -> tuple[list[dict[str, Any]], int, int]:
    """One cell per week (fat bar). Returns (cells, total_commits, max_week_commits).

    Level uses **active days in the week** (0–7) so each day is exactly 1/7 of
    the bar; ``count`` remains total commits for tooltips.
    """
    weeks = clamp_weeks(weeks)
    raw: list[dict[str, Any]] = []
    active_list: list[int] = []
    total = 0
    max_c = 0
    for w in range(weeks):
        week_start = date.fromordinal(first_sunday.toordinal() + w * 7)
        week_end = date.fromordinal(week_start.toordinal() + 6)
        c = 0
        active_days = 0
        for i in range(7):
            d = date.fromordinal(week_start.toordinal() + i)
            if d > today:
                continue
            day_c = int(counts.get(d.isoformat(), 0))
            if day_c:
                c += day_c
                active_days += 1
        label_end = min(week_end, today)
        raw.append({
            "date": week_start.isoformat(),
            "date_end": label_end.isoformat(),
            "count": c,
            "active_days": active_days,
        })
        if c:
            active_list.append(active_days)
            total += c
            max_c = max(max_c, c)
    ceiling = scale_ceiling(active_list, grain="week")
    cells = [
        {
            "date": cell["date"],
            "date_end": cell["date_end"],
            "count": int(cell["count"]),
            "active_days": int(cell["active_days"]),
            # 1 active day = 1/7 of the week bar
            "level": level_for_count(
                int(cell["active_days"]), ceiling, grain="week",
            ),
        }
        for cell in raw
    ]
    return cells, total, max_c


# Back-compat name used by older tests
def build_grid(
    counts: dict[str, int],
    first_sunday: date,
    today: date,
    weeks: int,
) -> tuple[list[dict[str, Any]], int, int]:
    cells, total, max_c, _active = build_day_grid(counts, first_sunday, today, weeks)
    return cells, total, max_c


def empty_payload(weeks: int = DEFAULT_WEEKS, *, git: bool = False) -> dict[str, Any]:
    weeks = clamp_weeks(weeks)
    return {
        "ok": True,
        "git": git,
        "weeks": weeks,
        "grain": "day",
        "rows": 7,
        "adaptive": False,
        "dow_start": DOW_START_SUNDAY,
        "cells": [],
        "total": 0,
        "max": 0,
    }


def git_commit_activity(
    root: Path,
    weeks: Optional[int] = None,
    *,
    today: Optional[date] = None,
    adaptive: Optional[bool] = None,
) -> dict[str, Any]:
    """Full payload for UIs / ``GET /api/git/activity``.

    *weeks*:
      - ``None`` → adaptive window from first commit (default).
      - int → fixed window (clamped).
    *today* is injectable for deterministic tests.
    """
    root = Path(root).expanduser().resolve()
    day = today or date.today()
    use_adaptive = adaptive if adaptive is not None else (weeks is None)
    repo_first = first_commit_date(root) if (root.is_dir() and probe_git(root)) else None

    if use_adaptive:
        n_weeks = weeks_for_repo_age(day, repo_first)
    else:
        n_weeks = clamp_weeks(weeks if weeks is not None else DEFAULT_WEEKS)

    base = empty_payload(n_weeks, git=False)
    base["adaptive"] = use_adaptive
    if repo_first:
        base["repo_first"] = repo_first.isoformat()

    if not root.is_dir() or not probe_git(root):
        return base

    # Adaptive: left edge is the Sunday of the first commit (not "today − N weeks"),
    # so young repos don't lose their earliest days to min-week padding.
    if use_adaptive and repo_first is not None:
        first_sunday = sunday_on_or_before(repo_first)
        last = day
        # Recompute column count from that left edge (still clamped).
        n_weeks = weeks_for_repo_age(day, repo_first)
    else:
        first_sunday, last = window_bounds(day, n_weeks)
    counts, err = commit_counts_by_day(root, first_sunday)
    if err:
        out = empty_payload(n_weeks, git=True)
        out["adaptive"] = use_adaptive
        out["error"] = err
        out["first_date"] = first_sunday.isoformat()
        out["last_date"] = last.isoformat()
        if repo_first:
            out["repo_first"] = repo_first.isoformat()
        return out

    day_cells, total, max_c, active_days = build_day_grid(
        counts, first_sunday, last, n_weeks,
    )
    if should_use_week_grain(total=total, active_days=active_days):
        cells, total, max_c = build_week_grid(counts, first_sunday, last, n_weeks)
        grain, rows = "week", 1
    else:
        cells, grain, rows = day_cells, "day", 7

    return {
        "ok": True,
        "git": True,
        "weeks": n_weeks,
        "grain": grain,
        "rows": rows,
        "adaptive": use_adaptive,
        "dow_start": DOW_START_SUNDAY,
        "first_date": first_sunday.isoformat(),
        "last_date": last.isoformat(),
        "repo_first": repo_first.isoformat() if repo_first else None,
        "cells": cells,
        "total": total,
        "max": max_c,
        "active_days": active_days,
    }
