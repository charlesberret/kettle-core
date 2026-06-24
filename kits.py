"""Setsweep curator kits — the per-kind playbook that arms a project's curator: a review
lens, an urgency rubric, a first-queue heuristic, sweep self-checks, and an (optional)
extra-tools list layered on the always-on builtins.

  kits/<kind>.json   shipped defaults (read-only baseline, synced via the repo)
  settings["kits"]   user edits / custom kits (local; fork-on-edit)
  proj["kit"]        a project's assignment (a kind or a custom kit name), set at founding

This module is pure: every function takes its inputs explicitly (no server import), so it
is trivially testable and never reaches the network or a fixed path.
"""

import json
from pathlib import Path

KINDS = ["writing", "code", "records", "knowledge", "inbox"]


def load_defaults(kits_dir) -> dict:
    """{kind: kit} from kits/*.json. Files beginning with '_' (the handbook) are skipped;
    malformed or unreadable files are dropped, never raised."""
    out = {}
    try:
        files = sorted(Path(kits_dir).glob("*.json"))
    except OSError:
        return out
    for f in files:
        if f.name.startswith("_"):
            continue
        try:
            kit = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        out[kit.get("kind") or f.stem] = kit
    return out


def resolve(ref, kits_dir, settings=None) -> dict | None:
    """A kit reference (a kind or a custom kit name) → its kit dict, or None.
    A user kit in settings['kits'] of the same key wins over the shipped default."""
    if not ref:
        return None
    user = (settings or {}).get("kits") or {}
    if ref in user:
        return user[ref]
    return load_defaults(kits_dir).get(ref)


def for_project(proj, kits_dir, settings=None) -> dict | None:
    """The kit assigned to a project via its 'kit' field, or None if unassigned."""
    return resolve((proj or {}).get("kit"), kits_dir, settings)


def as_context(kit, mode: str) -> str:
    """Render a kit into an injectable context block for an agent mode:
      'review' → lens + urgency · 'sweep' → self-checks · 'found' → first-queue heuristic.
    Returns '' for no kit or an empty section, so callers can inject unconditionally."""
    if not kit:
        return ""
    if mode == "review":
        parts = []
        if kit.get("lens"):
            parts.append("Review lens: " + kit["lens"])
        if kit.get("urgency"):
            parts.append("Urgency rubric: " + kit["urgency"])
        body = "\n".join(parts)
    elif mode == "sweep":
        checks = kit.get("sweepChecks") or []
        body = ("Sweep self-check (confirm each before closing):\n"
                + "\n".join(f"- {c}" for c in checks)) if checks else ""
    elif mode == "found":
        body = ("First-queue heuristic: " + kit["firstQueue"]) if kit.get("firstQueue") else ""
    else:
        body = ""
    return f"Curator kit — {kit.get('name', 'kit')}:\n{body}" if body else ""


def list_kits(kits_dir, settings=None) -> list:
    """Every kit the editor should show: each kind's *effective* kit (a user override if
    one exists, else the shipped default), then any custom user kits. Each is tagged with
    `_source` ('default' | 'user') and `_key` (its settings.kits key / kind) so the editor
    knows whether it is editing a pristine default (fork on save) or an existing user kit."""
    user = (settings or {}).get("kits") or {}
    defaults = load_defaults(kits_dir)
    out = []
    for kind in KINDS:
        if kind in user:
            out.append({**user[kind], "_source": "user", "_key": kind})
        elif kind in defaults:
            out.append({**defaults[kind], "_source": "default", "_key": kind})
    for key, kit in user.items():
        if key not in KINDS:                       # custom kits (keyed by their own name)
            out.append({**kit, "_source": "user", "_key": key})
    return out


def extra_tools(kit) -> list:
    """Tool entries beyond the always-on builtins (skill/mcp/rag/corpus). [] for shipped
    defaults. Each entry is a {type, ref} dict; 'builtin' entries are dropped (always granted)."""
    if not kit:
        return []
    return [t for t in (kit.get("tools") or [])
            if isinstance(t, dict) and t.get("type") != "builtin"]
