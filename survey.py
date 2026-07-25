"""Deterministic founding survey — Phase A of the interview ritual.

Core maps the project tree without a curator CLI so the interview turn can be
tool-less (no shell / writes) under every provider. The model only rephrases the
snapshot into a plain opening and the confirmation card.

Pure: no server import, no network. Callers write the snapshot where they like
(typically ``.setsweep/runtime/survey.json``).
"""

from __future__ import annotations

import json
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
    ".turbo", "target", "vendor", ".setsweep", ".cache",
})

_MAX_TOP = 48
_MAX_SAMPLES = 8
_SAMPLE_CHARS = 2400


def build_survey(
    root: Path | str,
    *,
    max_top: int = _MAX_TOP,
    max_samples: int = _MAX_SAMPLES,
    sample_chars: int = _SAMPLE_CHARS,
) -> dict[str, Any]:
    """Walk *root* and return a JSON-serializable founding survey snapshot."""
    root_p = Path(root).expanduser().resolve()
    top: list[dict[str, str]] = []
    empty = True
    has_git = False
    has_setsweep = False
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
        if name in _SKIP_DIR_NAMES and name not in (".setsweep", ".git", ".cursor"):
            # Still record presence of key markers even if we skip listing their guts.
            pass
        try:
            is_dir = ent.is_dir()
        except OSError:
            continue
        empty = False
        kind = "dir" if is_dir else "file"
        if len(top) < max_top:
            top.append({"name": name, "kind": kind})
        if name == ".git" and is_dir:
            has_git = True
        elif name == ".setsweep" and is_dir:
            has_setsweep = True
        elif name == ".cursor" and is_dir:
            has_cursor = True
            agent_markers.append(".cursor/")
        elif name == ".claude" and is_dir:
            has_claude_dir = True
            agent_markers.append(".claude/")

    samples: dict[str, str] = {}
    for fname in _SAMPLE_NAMES:
        if len(samples) >= max_samples:
            break
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

    signals = {
        "git": has_git,
        "setsweep_desk": has_setsweep,
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
    """High-confidence stem option labels to pre-check on the confirmation card.

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
            lines.append(f"  - {ent.get('name', '')}{mark}")
        if len(top) > 40:
            lines.append(f"  … ({len(top) - 40} more)")
    else:
        lines.append("Top level: (nothing listed)")

    sig = survey.get("signals") or {}
    bits = []
    if sig.get("git"):
        bits.append("git repo")
    if sig.get("setsweep_desk"):
        bits.append("existing .setsweep desk")
    if sig.get("agent_markers"):
        bits.append("agent markers: " + ", ".join(sig["agent_markers"]))
    if bits:
        lines.append("Signals: " + "; ".join(bits))

    samples = survey.get("samples") or {}
    if samples:
        lines.append("Sampled files (truncated):")
        for name, text in samples.items():
            lines.append(f"--- {name} ---")
            lines.append(text.rstrip() or "(empty)")
            lines.append(f"--- end {name} ---")

    # Survey heuristics stay internal to the prose opening — never instruct pre-ticking
    # the confirmation card (blank card for the user).

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


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
