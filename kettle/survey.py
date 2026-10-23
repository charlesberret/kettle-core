"""Deterministic founding survey — Phase A of the interview ritual.

Core maps the project tree without a curator CLI so the interview turn can be
tool-less (no shell / writes) under every provider. The model only rephrases the
snapshot into a short conversation (dated observations + one mission question).

Pure: no server import, no network. Callers write the snapshot where they like
(typically ``.kettle/runtime/survey.json``).
"""

from __future__ import annotations

import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Orientation files worth sampling (first match per pattern family wins for "primary").
_SAMPLE_NAMES = (
    "README.md", "README.txt", "README", "Readme.md",
    "CLAUDE.md", "AGENTS.md", "PROJECT.md", "CONTRIBUTING.md",
    "package.json", "pyproject.toml", "Cargo.toml", "go.mod",
    "Gemfile", "composer.json", "Makefile", "CMakeLists.txt",
)

# Directories we never descend into while listing.
_SKIP_DIR_NAMES = frozenset({
    ".git", ".hg", ".svn", "node_modules", ".venv", "venv", "__pycache__",
    ".tox", ".mypy_cache", ".pytest_cache", "dist", "build", ".next",
    ".turbo", "target", "vendor", ".kettle", ".setsweep", ".cache",
})

# Kettle's own desk dirs — register_project() creates `.kettle/` (and a legacy `.setsweep/`
# may already exist) before the founding survey ever runs. Their bare presence is not user
# content: it must not defeat empty/greenfield detection, and it clutters top_level with
# something the user never made.
_DESK_DIR_NAMES = frozenset({".kettle", ".setsweep"})
# OS-generated noise that carries no project signal and shouldn't appear in top_level either.
_OS_NOISE_NAMES = frozenset({".DS_Store"})
# Hidden from the top-level listing entirely (Kettle-owned or OS noise, not user content).
_HIDDEN_TOP_LEVEL_NAMES = _DESK_DIR_NAMES | _OS_NOISE_NAMES
# Entries that never, by themselves, defeat "empty" detection: Kettle's own desk dirs, OS
# noise, and a bare `git init` with no commits/tracked files is just metadata, not content.
_NON_SUBSTANTIVE_NAMES = _DESK_DIR_NAMES | _OS_NOISE_NAMES | frozenset({".git"})

_MAX_TOP = 48
_MAX_SAMPLES = 8
_SAMPLE_CHARS = 2400

# git enrichment — bounded so a large repo's history never stalls a founding turn.
_GIT_TIMEOUT = 5.0
_GIT_LOG_TIMEOUT = 8.0
_GIT_LOG_SCAN_COMMITS = 500     # window for "most-changed paths" — recent history, not full log
_TOP_CHANGED_PATHS = 3

# mtime enrichment — bounded walk, same skip set as the top-level listing.
_MTIME_MAX_FILES = 12_000
_MTIME_BUCKETS = (
    ("last_24h", 1 * 86400),
    ("last_7d", 7 * 86400),
    ("last_30d", 30 * 86400),
)


def build_survey(
    root: Path | str,
    *,
    max_top: int = _MAX_TOP,
    max_samples: int = _MAX_SAMPLES,
    sample_chars: int = _SAMPLE_CHARS,
    max_depth: int | None = None,
) -> dict[str, Any]:
    """Walk *root* and return a JSON-serializable founding survey snapshot.

    `max_depth` (the project's scope bound; None or < 1 = unbounded) limits the recency
    signals to files within that many directory levels, so the interview's dated
    observations never cite paths the desk's scope note puts out of bounds."""
    depth = max_depth if isinstance(max_depth, int) and max_depth >= 1 else None
    root_p = Path(root).expanduser().resolve()
    top: list[dict[str, str]] = []
    empty = True
    has_git = False
    has_kettle_dir = False
    has_legacy_desk = False
    has_cursor = False
    has_claude_dir = False
    agent_markers: list[str] = []

    try:
        entries = sorted(root_p.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
    except OSError as exc:
        return {
            "root": str(root_p),
            "ok": False,
            "error": f"unreadable: {exc}",
            "empty": True,
            "top_level": [],
            "signals": {},
            "samples": {},
            "suggested_prechecks": {},
            "generated_at": _now(),
        }

    for ent in entries:
        name = ent.name
        try:
            is_dir = ent.is_dir()
        except OSError:
            continue
        if name not in _NON_SUBSTANTIVE_NAMES:
            empty = False
        kind = "dir" if is_dir else "file"
        if name not in _HIDDEN_TOP_LEVEL_NAMES and len(top) < max_top:
            top.append({"name": name, "kind": kind})
        if name == ".git" and is_dir:
            has_git = True
        elif name == ".kettle" and is_dir:
            has_kettle_dir = True
        elif name == ".setsweep" and is_dir:
            has_legacy_desk = True
        elif name == ".cursor" and is_dir:
            has_cursor = True
            agent_markers.append(".cursor/")
        elif name == ".claude" and is_dir:
            has_claude_dir = True
            agent_markers.append(".claude/")

    # A `.kettle/` dir alone is just register_project()'s seed (queue.json etc). The
    # "existing desk" signal should mean a founded charter is actually there.
    has_kettle_charter = has_kettle_dir and (root_p / ".kettle" / "PROJECT.md").is_file()

    if depth != 1:
        listed_dirs = 0
        for ent in top:
            if listed_dirs >= 12:
                break
            if ent["kind"] != "dir" or ent["name"] in _SKIP_DIR_NAMES:
                continue  # never read inside a dir the survey would never descend
            listed_dirs += 1
            children = _dir_children(root_p / ent["name"])
            if children is not None:
                ent["children"], ent["child_count"] = children

    entry_names = {e.name for e in entries}
    samples: dict[str, str] = {}
    for fname in _SAMPLE_NAMES:
        if len(samples) >= max_samples:
            break
        if fname not in entry_names:
            continue  # exact name only — a case-insensitive disk must not double-sample
        p = root_p / fname
        if not p.is_file():
            continue
        text = _read_head(p, sample_chars)
        if text is not None:
            samples[fname] = text
        if fname in ("CLAUDE.md", "AGENTS.md") and fname not in agent_markers:
            agent_markers.append(fname)

    # Light descent one level for README under common subdirs only if none at root.
    if not any(k.upper().startswith("README") for k in samples):
        for sub in ("docs", "Doc", "Documentation"):
            if len(samples) >= max_samples:
                break
            cand = root_p / sub / "README.md"
            if cand.is_file():
                text = _read_head(cand, sample_chars)
                if text is not None:
                    samples[f"{sub}/README.md"] = text
                break

    git_activity = (_git_activity(root_p, max_depth=depth, sample_names=tuple(samples))
                    if has_git else None)
    mtime_buckets = recent_paths = oldest_path = None
    if not git_activity:
        mtime_buckets, recent_paths, oldest_path = _mtime_scan(root_p, max_depth=depth)
    signals = {
        "git": has_git,
        "kettle_desk": has_kettle_charter,
        "legacy_setsweep_desk": has_legacy_desk,
        "cursor": has_cursor,
        "claude_dir": has_claude_dir,
        "agent_markers": agent_markers,
        "has_readme": any(k.upper().startswith("README") for k in samples),
        "has_package_json": "package.json" in samples,
        "has_pyproject": "pyproject.toml" in samples,
        "file_count_top": len(top),
    }

    return {
        "root": str(root_p),
        "ok": True,
        "error": None,
        "empty": empty or (len(top) == 0),
        "top_level": top,
        "signals": signals,
        "samples": samples,
        "git_activity": git_activity,
        # the filesystem walk is only the fallback when git has no usable history
        "mtime_buckets": mtime_buckets,
        "recent_paths": recent_paths,
        "oldest_path": oldest_path,
        "suggested_prechecks": suggest_prechecks(empty=empty or not top, signals=signals,
                                                  samples=samples),
        "generated_at": _now(),
    }


def suggest_prechecks(
    *,
    empty: bool,
    signals: dict[str, Any],
    samples: dict[str, str],
) -> dict[str, list[str]]:
    """High-confidence stem option labels (legacy; P4 interview is not a card).

    Only include options the survey strongly supports — false pre-checks are worse
    than none. Labels must match BASE_INTERVIEW options verbatim.
    """
    out: dict[str, list[str]] = {}
    if empty:
        out["status"] = ["Brand new — starting from scratch"]
        out["horizon"] = ["Too early to say — help me find out"]
        out["fleet"] = ["Just me, for now"]
        return out

    # Status: prefer conservative "in motion" when there is substance + git.
    if signals.get("git") and signals.get("file_count_top", 0) >= 5:
        out["status"] = ["In motion — active work under way"]
    elif signals.get("file_count_top", 0) >= 3:
        out["status"] = ["In motion — active work under way"]

    markers = list(signals.get("agent_markers") or [])
    if markers:
        out["fleet"] = ["Coding agents in this same repository"]
    else:
        out["fleet"] = ["Just me, for now"]

    # Secrets fence is almost always right for real projects.
    if not empty:
        out.setdefault("fences", []).append("Secrets, credentials, and personal data")

    _ = samples  # reserved for kit-aware heuristics (inbox markers, etc.)
    return out


def as_prompt_block(survey: dict[str, Any]) -> str:
    """Render a survey snapshot for injection into the interview system / kickoff."""
    if not survey:
        return ""
    if not survey.get("ok", True):
        return (
            "CORE SURVEY (tool-less founding — do not re-walk the tree):\n"
            f"Survey failed: {survey.get('error') or 'unknown error'}. "
            "Ask whether this is the right folder or a new project."
        )

    lines = [
        "CORE SURVEY (authoritative — do not re-walk the tree with tools; you have none):",
        f"Root: {survey.get('root', '')}",
        f"Empty / greenfield: {'yes' if survey.get('empty') else 'no'}",
    ]
    top = survey.get("top_level") or []
    if top:
        lines.append("Top level:")
        for ent in top[:40]:
            mark = "/" if ent.get("kind") == "dir" else ""
            children = ent.get("children") or []
            if mark and children:
                count = ent.get("child_count", len(children))
                shown = ", ".join(children)
                if count > len(children):
                    shown += ", …"
                noun = "entry" if count == 1 else "entries"
                lines.append(f"  - {ent.get('name', '')}/ ({count} {noun}: {shown})")
            else:
                lines.append(f"  - {ent.get('name', '')}{mark}")
        if len(top) > 40:
            lines.append(f"  … ({len(top) - 40} more)")
    else:
        lines.append("Top level: (nothing listed)")

    sig = survey.get("signals") or {}
    bits = []
    if sig.get("git"):
        bits.append("git repo")
    if sig.get("kettle_desk"):
        bits.append("existing .kettle desk")
    elif sig.get("legacy_setsweep_desk"):
        bits.append("existing legacy .setsweep desk")
    if sig.get("agent_markers"):
        bits.append("agent markers: " + ", ".join(sig["agent_markers"]))
    if bits:
        lines.append("Signals: " + "; ".join(bits))

    git_activity = survey.get("git_activity")
    if git_activity:
        lines.append(
            f"Recent activity (git): last commit {git_activity['last_commit_date']} · "
            f"{git_activity['commits_last_30d']} commit(s) in the last 30 days · "
            f"{git_activity['author_count'] or 1} author(s)"
        )
        top_paths = git_activity.get("top_changed_paths") or []
        if top_paths:
            rendered = ", ".join(f"{p['path']} ({p['commits']})" for p in top_paths)
            lines.append(f"Most-changed paths (recent history): {rendered}")
        sample_dates = git_activity.get("sample_dates") or {}
        if sample_dates:
            rendered = ", ".join(f"{n} {d}" for n, d in sample_dates.items())
            lines.append(f"Orientation files last committed: {rendered}")
        recent_commits = git_activity.get("recent_commits") or []
        if recent_commits:
            rendered = "; ".join(f"{c['date']} {c['subject']}" for c in recent_commits)
            lines.append(f"Last commits: {rendered}")
    else:
        buckets = survey.get("mtime_buckets")
        if buckets:
            # buckets are exclusive (each file counted once); the prose reads cumulatively
            day = buckets["last_24h"]
            week = day + buckets["last_7d"]
            month = week + buckets["last_30d"]
            lines.append(
                "Recent activity (filesystem, no usable git history): "
                f"{day} file(s) touched in the last 24h, "
                f"{week} in the last 7 days, "
                f"{month} in the last 30 days."
            )
        recent = survey.get("recent_paths") or []
        if recent:
            lines.append(
                "Most recently touched: "
                + ", ".join(f"{r['path']} ({r['date']})" for r in recent)
                + "."
            )
        oldest = survey.get("oldest_path")
        if oldest:
            lines.append(
                f"Least recently touched: {oldest['path']} ({oldest['date']})."
            )

    samples = survey.get("samples") or {}
    if samples:
        lines.append("Sampled files (truncated):")
        for name, text in samples.items():
            lines.append(f"--- {name} ---")
            lines.append(text.rstrip() or "(empty)")
            lines.append(f"--- end {name} ---")

    # Survey heuristics stay internal to the prose opening — never instruct a form.

    lines.append(
        "If empty/greenfield: open with new-project vs wrong-folder; scaffold only if they want."
    )
    return "\n".join(lines)


def dump(survey: dict[str, Any]) -> str:
    return json.dumps(survey, indent=2, ensure_ascii=False)


def load(path: Path | str) -> dict[str, Any]:
    p = Path(path)
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _read_head(path: Path, n: int) -> str | None:
    try:
        raw = path.read_bytes()[: n * 4]  # rough cap for binary sniff
    except OSError:
        return None
    if b"\x00" in raw[:1024]:
        return "(binary file, not sampled)"
    try:
        text = raw.decode("utf-8", errors="replace")
    except Exception:
        return None
    text = text.replace("\r\n", "\n")
    if len(text) > n:
        text = text[:n].rstrip() + "\n… [truncated]"
    return text


def _git_run(root: Path, args: list[str], *, timeout: float) -> str | None:
    """Run one local, read-only ``git`` query. Never raises — a survey must not fail
    or hang the founding turn because a repo is huge, shallow, or the binary is
    missing."""
    try:
        proc = subprocess.run(
            ["git", "-C", str(root), *args],
            capture_output=True, text=True, timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout


def _within_depth(rel_path: str, max_depth: int | None) -> bool:
    """True when a root-relative path is at most `max_depth` levels deep (1 = root files)."""
    return max_depth is None or len(Path(rel_path).parts) <= max_depth


def _git_activity(root: Path, *, max_depth: int | None = None,
                  sample_names: tuple[str, ...] = ()) -> dict[str, Any] | None:
    """Deterministic git enrichment for the survey: last commit date, commit volume
    over the last 30 days, the most-changed paths in recent history, per-sample
    last-commit dates, the five most recent commit subjects, and a rough author
    count. Local ``git log`` only — no network, no curator CLI. Returns None
    when the query fails (not actually a work tree despite a ``.git`` entry, empty
    repo, git missing) so callers can omit the section rather than show zeros."""
    last = _git_run(root, ["log", "-1", "--format=%cs"], timeout=_GIT_TIMEOUT)
    if last is None:
        return None
    last = last.strip()
    if not last:
        return None  # a .git dir with no commits yet — nothing to report

    recent = _git_run(root, ["log", "--since=30.days", "--format=%h"], timeout=_GIT_TIMEOUT)
    commits_30d = len([l for l in (recent or "").splitlines() if l.strip()])

    changed = _git_run(
        root,
        ["log", f"-n{_GIT_LOG_SCAN_COMMITS}", "--name-only", "--format="],
        timeout=_GIT_LOG_TIMEOUT,
    )
    counts: dict[str, int] = {}
    for line in (changed or "").splitlines():
        path = line.strip()
        if path and _within_depth(path, max_depth):
            counts[path] = counts.get(path, 0) + 1
    top_paths = [
        {"path": p, "commits": n}
        for p, n in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[:_TOP_CHANGED_PATHS]
    ]

    authors = _git_run(root, ["log", "--format=%ae"], timeout=_GIT_LOG_TIMEOUT)
    author_count = len({a.strip() for a in (authors or "").splitlines() if a.strip()}) or None

    sample_dates: dict[str, str] = {}
    for name in sample_names:
        out = _git_run(root, ["log", "-1", "--format=%cs", "--", name],
                       timeout=_GIT_TIMEOUT)
        date = (out or "").strip()
        if date:
            sample_dates[name] = date

    recent_out = _git_run(root, ["log", "-5", "--format=%cs%x09%s"],
                          timeout=_GIT_TIMEOUT)
    recent_commits = []
    for line in (recent_out or "").splitlines():
        if not line.strip():
            continue
        date, _, subject = line.partition("\t")
        recent_commits.append({"date": date.strip(), "subject": subject[:72]})

    return {
        "last_commit_date": last,
        "commits_last_30d": commits_30d,
        "top_changed_paths": top_paths,
        "author_count": author_count,
        "sample_dates": sample_dates,
        "recent_commits": recent_commits,
    }


def _dir_children(path: Path, *, max_names: int = 8
                  ) -> tuple[list[str], int] | None:
    """Immediate entries of one top-level dir, filtered by the same skip sets as the
    rest of the survey. Returns (up to ``max_names`` display names — dirs marked
    with a trailing slash, case-insensitive sort — and the total count after
    filtering), or None when the dir can't be read."""
    try:
        kids = sorted(path.iterdir(), key=lambda p: p.name.lower())
    except OSError:
        return None
    names: list[str] = []
    for k in kids:
        if k.name in _HIDDEN_TOP_LEVEL_NAMES or k.name in _SKIP_DIR_NAMES:
            continue
        try:
            is_dir = k.is_dir()
        except OSError:
            is_dir = False
        names.append(k.name + "/" if is_dir else k.name)
    return names[:max_names], len(names)


def _mtime_scan(root: Path, *, max_files: int = _MTIME_MAX_FILES,
                max_depth: int | None = None
                ) -> tuple[dict[str, int] | None,
                           list[dict[str, str]] | None,
                           dict[str, str] | None]:
    """Filesystem-mtime recency in one walk: buckets (last 24h / 7d / 30d / older)
    plus the three most- and single least-recently modified files with their UTC
    dates. Skips the same noise directories as the top-level listing and the
    OS-noise file names, and honors the same depth bound and file cap. Works for
    git and non-git roots alike — the fallback signal when there is no usable
    history. Returns (None, None, None) when nothing was scanned."""
    buckets = {"last_24h": 0, "last_7d": 0, "last_30d": 0, "older": 0}
    now = datetime.now(timezone.utc).timestamp()
    scanned = 0
    mtimes: list[tuple[float, str]] = []
    capped = False
    try:
        for dirpath, dirnames, filenames in os.walk(root):
            level = len(Path(dirpath).relative_to(root).parts)  # 0 at the root
            if max_depth is not None and level + 1 >= max_depth:
                dirnames[:] = []            # files one level down would exceed the bound
            dirnames[:] = [d for d in dirnames if d not in _SKIP_DIR_NAMES]
            for fname in filenames:
                if fname in _OS_NOISE_NAMES:
                    continue                # .DS_Store et al carry no project signal
                if scanned >= max_files:
                    capped = True
                    break
                scanned += 1
                try:
                    fpath = Path(dirpath) / fname
                    mtime = fpath.stat().st_mtime
                except OSError:
                    continue
                age = now - mtime
                for label, span in _MTIME_BUCKETS:
                    if age < span:
                        buckets[label] += 1
                        break
                else:
                    buckets["older"] += 1
                mtimes.append((mtime, fpath.relative_to(root).as_posix()))
            if capped:
                break
    except OSError:
        return None, None, None
    if not scanned:
        return None, None, None
    recent_paths = oldest_path = None
    if mtimes:
        newest = sorted(mtimes, key=lambda t: (-t[0], t[1]))
        recent_paths = [
            {"path": p, "date": _day(m)} for m, p in newest[:3]
        ]
        o_mtime, o_path = min(mtimes)
        oldest_path = {"path": o_path, "date": _day(o_mtime)}
    return buckets, recent_paths, oldest_path


def _day(ts: float) -> str:
    return datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%d")


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
