"""Kettle curator kits — the per-kind playbook that arms a project's curator: a review
lens, an urgency rubric, a first-queue heuristic, founding-interview stems, sweep self-checks,
and an (optional) extra-tools list layered on the always-on builtins.

  kits/<kind>.json   shipped defaults (read-only baseline, synced via the repo)
  settings["kits"]   user edits / custom kits (local; fork-on-edit)
  proj["kit"]        a project's assignment (a kind or a custom kit name), set at founding

This module is pure: every function takes its inputs explicitly (no server import), so it
is trivially testable and never reaches the network or a fixed path.
"""

import json
from pathlib import Path

KINDS = ["writing", "code", "records", "knowledge", "inbox"]

# Shared founding stems — every desk asks these. Kit-specific stems merge in by id
# (kit wins on conflict). Sweep-actions is shared so inbox and non-inbox alike can opt in.
#
# Wording discipline: this card is the product's first impression, answered before the
# user has learned any Kettle vocabulary. Stems and options must be self-explanatory —
# no internal terms (sitting, sweep, egress, corpus), no slash piles, no example dumps.
# One axis per question; single-choice where the axis must be crisp; every option should
# change what the desk actually does. Card mechanics are stated once by the UI, never
# repeated per question.
BASE_INTERVIEW = [
    {
        "id": "status",
        "stem": "Where does this project stand?",
        "multi": False,
        "options": [
            "Brand new — starting from scratch",
            "In motion — active work under way",
            "Established — tend it and keep it coherent",
            "Backlogged — a pile to work through",
        ],
    },
    {
        "id": "horizon",
        "stem": "What would success look like?",
        "multi": False,
        "options": [
            "Something finished, out the door",
            "A living body of work that stays healthy",
            "A cleared queue that stays clear",
            "Too early to say — help me find out",
        ],
    },
    {
        "id": "direction",
        "stem": "What should our sessions focus on?",
        "multi": True,
        "options": [
            "Craft — make good work better",
            "Decisions — surface the calls only I can make",
            "Consistency — keep everything agreeing with itself",
            "Throughput — clear incoming work and draft replies",
            # Cowork is first-class: desk is not only a review gallery of others' work.
            "Build with me — propose next work, draft it together, then refine it in the queue",
        ],
    },
    {
        "id": "fences",
        "stem": "What should I never change without asking?",
        "multi": True,
        "options": [
            "Project files are fair game for agent editing",
            "Records and logs that only ever grow",
            "Wording that is already published or final",
            "Secrets, credentials, and personal data",
            "Anything that leaves the project — prepare it, let me send it",
        ],
    },
    {
        "id": "sweep_actions",
        "stem": "What else should happen when a session closes?",
        "multi": True,
        "options": [
            "Nothing else — tidy up and refill the queue",
            "Commit the session's changes to git",
            "Share approved work with the other agents here",
            "Queue approved drafts for sending — I do the sending",
            "Append a session summary to a running log",
            "Draft an outgoing update for another channel, held for review",
            "Update a tracking sheet",
        ],
    },
    {
        "id": "fleet",
        "stem": "Who else works on this project?",
        "multi": True,
        "options": [
            "Just me, for now",
            "Coding agents in this same repository",
            "Multiple agents that hand work to each other",
            "Automated jobs that depend on approved files",
        ],
    },
]


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


def interview_stems(kit) -> list:
    """Merged founding-interview stems: BASE_INTERVIEW, then kit.interview overrides by id."""
    by_id = {s["id"]: dict(s) for s in BASE_INTERVIEW if isinstance(s, dict) and s.get("id")}
    for s in (kit or {}).get("interview") or []:
        if isinstance(s, dict) and s.get("id"):
            by_id[s["id"]] = dict(s)
    base_ids = {s["id"] for s in BASE_INTERVIEW}
    order = [s["id"] for s in BASE_INTERVIEW] + [
        s["id"] for s in ((kit or {}).get("interview") or [])
        if isinstance(s, dict) and s.get("id") and s["id"] not in base_ids
    ]
    seen = set()
    out = []
    for i in order:
        if i in seen or i not in by_id:
            continue
        seen.add(i)
        stem = dict(by_id[i])
        # Drop legacy "Other (elaborate)" checkboxes — free response is the Elaborate field.
        if isinstance(stem.get("options"), list):
            stem["options"] = [
                o for o in stem["options"] if not _is_other_option(str(o))
            ]
        out.append(stem)
    return out


def _is_other_option(label: str) -> bool:
    """True for the old 'Other (elaborate…)' checkbox rows — free-response is the Elaborate field.

    Only matches labels that *are* the freeform Other row (start with Other and mention
    elaborate, or are exactly 'Other'). Does not match real options like
    'Other coding agents in this repo…'.
    """
    s = (label or "").strip().lower()
    if not s.startswith("other"):
        return False
    if s == "other" or s.startswith("other ("):
        return True
    return "elaborate" in s


def as_context(kit, mode: str) -> str:
    """Render a kit into an injectable context block for an agent mode:
      'review' → lens + urgency
      'sweep' → self-checks
      'found' → first-queue heuristic
    Returns '' for no kit, an empty section, or an unrecognized mode, so callers can
    inject unconditionally.

    Founding no longer asks a confirmation card (P4) — `interview_stems()` (base +
    kit, still merged) now feeds only the propose turn's *stated defaults*, not a
    Q&A form. There is deliberately no 'interview' mode here any more.
    """
    if not kit:
        return ""
    name = kit.get("name", "general")
    if mode == "review":
        if not kit:
            return ""
        parts = []
        if kit.get("lens"):
            parts.append("Review lens: " + kit["lens"])
        if kit.get("urgency"):
            parts.append("Urgency rubric: " + kit["urgency"])
        body = "\n".join(parts)
    elif mode == "sweep":
        if not kit:
            return ""
        checks = kit.get("sweepChecks") or []
        def _check_line(c):
            s = str(c or "").strip()
            if s.startswith("- "):
                s = s[2:].strip()
            return f"- {s}" if s else ""
        body = ("Sweep self-check (confirm each before closing):\n"
                + "\n".join(x for x in (_check_line(c) for c in checks) if x)) if checks else ""
    elif mode == "found":
        if not kit:
            return ""
        body = ("First-queue heuristic: " + kit["firstQueue"]) if kit.get("firstQueue") else ""
    else:
        body = ""
    return f"Curator kit — {name}:\n{body}" if body else ""


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
