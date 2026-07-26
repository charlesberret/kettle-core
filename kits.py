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


def _render_stems(stems: list) -> str:
    """Render stems as a blank GFM checklist for the user to answer."""
    lines = []
    for i, s in enumerate(stems, 1):
        # Ids stay in GFM for the desk parser; the UI hides the [id] chrome. Checkboxes
        # already read as multi, so only single-choice stems carry a tag — "(choose one)".
        one = "" if s.get("multi") else " (choose one)"
        sid = s.get("id", "")
        lines.append(f"{i}. [{sid}] {s.get('stem', '')}{one}")
        for opt in s.get("options") or []:
            if _is_other_option(str(opt)):
                continue
            lines.append(f"   - [ ] {opt}")
        lines.append("   Elaborate (optional):")  # leave blank — user only
    return "\n".join(lines)


def card_has_required_stems(text: str, kit=None) -> list[str]:
    """Return stem ids missing from *text* (soft validation of the confirmation card).

    Looks for ``[id]`` markers the UI/parser expect. Empty list means all base+kit
    stems appear. Used after interview turns; does not block the stream.
    """
    body = text or ""
    missing = []
    for s in interview_stems(kit):
        sid = s.get("id") or ""
        if not sid:
            continue
        if f"[{sid}]" not in body:
            missing.append(sid)
    return missing


def as_context(kit, mode: str) -> str:
    """Render a kit into an injectable context block for an agent mode:
      'review' → lens + urgency
      'sweep' → self-checks
      'found' → first-queue heuristic
      'interview' → MCQ stems (base + kit), for survey-then-confirm founding
    Returns '' for no kit or an empty section, so callers can inject unconditionally.
    Interview options always start unchecked. Survey heuristics shape the curator's
    opening prose; they never answer the user's confirmation card.
    """
    if not kit and mode != "interview":
        return ""
    name = (kit or {}).get("name", "general")
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
        body = ("Sweep self-check (confirm each before closing):\n"
                + "\n".join(f"- {c}" for c in checks)) if checks else ""
    elif mode == "found":
        if not kit:
            return ""
        body = ("First-queue heuristic: " + kit["firstQueue"]) if kit.get("firstQueue") else ""
    elif mode == "interview":
        stems = interview_stems(kit)
        body = (
            "Founding prompt list — emit these as a GFM markdown checklist in chat "
            "(### N. [id] stem, then - [ ] options, then `Elaborate (optional):` "
            "with the line left EMPTY). Copy stems and options VERBATIM, keeping the "
            "(choose one) tag on single-choice stems; add no other per-question "
            "instruction text — no '(pick all that apply)', no restating how checkboxes "
            "work. Never pre-fill Elaborate with survey commentary, coaching, or "
            "paraphrases — only the user writes free response. "
            "Do NOT add an 'Other (elaborate)' checkbox option — free response is the "
            "Elaborate field alone. "
            "The desk UI turns the checklist into interactive ticks. Emit every option "
            "as - [ ] unchecked — the user answers from a blank card (do not pre-check "
            "from the survey). You have NO tools; do not claim you will re-read files. "
            "Leave room for open discussion after the list. "
            "Finish ✓ later drafts one DESK-PROPOSAL.md for the user to edit and approve — "
            "do not write the full desk yet. Do not re-ask core themes the survey already "
            "answered.\n"
            + _render_stems(stems)
        )
        if kit and kit.get("lens"):
            body = ("Kit default lens (accept unless they delta it):\n" + kit["lens"]
                    + "\n\n" + body)
        if kit and kit.get("firstQueue"):
            body += "\n\nKit first-queue default (accept unless they delta it):\n" + kit["firstQueue"]
        return f"Curator kit — {name}:\n{body}"
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
