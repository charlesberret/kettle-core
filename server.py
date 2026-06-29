#!/usr/bin/env python3
"""desk — three-pane review server: agent-curated queue · plaintext editor · review agent.

Multi-project: the registry at projects.json maps project ids to a root (the agent's
working directory) and a queue file (<root>/.setsweep/queue.json by convention). The
right-pane agent is Claude Code in headless mode (-p, stream-json), run in the active
project's root with project-write tools (Read/Glob/Grep/Edit/Write + a fenced shell
allowlist, acceptEdits); each queue entry's curatorial brief is injected
as system-prompt context so the agent starts aligned without re-reading the file.

Run standalone (web mode):  python3 server.py [--port 4242] [--no-open]
Bundled (Electron .app):     PyInstaller sidecar; set DESK_PROJECTS for the registry path.
"""

import difflib
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import threading
import time
import urllib.request
import webbrowser
from datetime import date, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import kits     # curator kits: the per-kind playbook (lens · urgency · first-queue · sweep checks)
import lineage  # who-edited-what: agent edits self-record to the desk's working record
import runtime  # viewport-neutral agent adapter: spawn · usage normalizer · session ledger

HOME = Path.home()


def _app_dir() -> Path:
    """Repo root in dev; PyInstaller extract dir when frozen as a bundled sidecar."""
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return Path(__file__).resolve().parent


APPDIR = _app_dir()
STATIC = APPDIR / "static"
PROJECTS_PATH = Path(os.environ.get("DESK_PROJECTS", APPDIR / "projects.json"))
SETTINGS_PATH = PROJECTS_PATH.parent / "settings.json"
CLAUDE = shutil.which("claude") or str(HOME / ".local/bin/claude")
SERVER_PORT = None  # bound port, recorded at startup for the admin report
SERVER_STARTED = None  # ISO timestamp, set at bind
DEFAULT_PORT = 4242  # one port for native app and web mode alike — a bookmarked
                     # tab always reaches the live server, never a stale orphan
RUNTIME_PATH = HOME / ".cache/setsweep/server.json"  # informational record of the bind
QUEUE_LOCK = threading.Lock()
SETTINGS_LOCK = threading.Lock()
PROJECTS_LOCK = threading.Lock()
CHATLOG_LOCK = threading.Lock()
CHATLOG_CAP = 500  # server-side cap: most recent N messages kept per project

def _env_allowed_roots() -> list[Path]:
    """Extra base roots for the file fence, from $SETSWEEP_ALLOWED_ROOTS (os.pathsep-separated).
    Default (unset) = empty: the fence is exactly the registered project roots, each gated under
    $HOME at registration. Set this to widen it — e.g. a notes vault whose `[[wikilinks]]` cross
    project boundaries: `SETSWEEP_ALLOWED_ROOTS="$HOME/Notes:$HOME/Vault"`."""
    out: list[Path] = []
    for part in os.environ.get("SETSWEEP_ALLOWED_ROOTS", "").split(os.pathsep):
        part = part.strip()
        if part:
            try:
                out.append(Path(part).expanduser().resolve())
            except (OSError, RuntimeError):
                continue
    return out


# The fence = these base roots + every registered project root (see allowed_roots()). Base
# defaults to empty for portability; the author can restore prior behavior with, e.g.,
# SETSWEEP_ALLOWED_ROOTS="$HOME/Seafile:$HOME/Library/Mobile Documents/com~apple~CloudDocs".
BASE_ALLOWED_ROOTS = _env_allowed_roots()

# the everyday shell kit — compound commands get split by the permission system,
# so every harmless part must be individually allowed or headless runs hit walls
SHELL_KIT = [
    "Bash(ls:*)", "Bash(cat:*)", "Bash(head:*)", "Bash(tail:*)", "Bash(echo:*)",
    "Bash(rg:*)", "Bash(grep:*)", "Bash(fd:*)", "Bash(find:*)", "Bash(wc:*)",
    "Bash(sed:*)", "Bash(awk:*)", "Bash(sort:*)", "Bash(uniq:*)", "Bash(diff:*)",
    "Bash(date:*)", "Bash(basename:*)", "Bash(dirname:*)", "Bash(mkdir:*)",
]

AGENT_TOOLS = [
    "--permission-mode", "acceptEdits",
    "--allowedTools",
    "Read", "Glob", "Grep", "Edit", "Write", *SHELL_KIT,
    "Bash(mv:*)", "Bash(cp:*)",
    "--disallowedTools", "NotebookEdit",
]

# the sweep applies rulings to canonical files, so it carries write tools —
# confined by cwd + acceptEdits to the project tree
SWEEP_TOOLS = [
    "--permission-mode", "acceptEdits",
    "--allowedTools",
    "Read", "Glob", "Grep", "Edit", "Write",
    "Bash(ls:*)", "Bash(cat:*)", "Bash(rg:*)", "Bash(fd:*)", "Bash(find:*)",
    "Bash(diff:*)",
    "--disallowedTools", "NotebookEdit",
]

# the founding interview is read-only: the curator surveys and converses; all
# writing waits for the found step (patron clicks finish), which carries SWEEP_TOOLS
INTERVIEW_TOOLS = [
    "--allowedTools",
    "Read", "Glob", "Grep",
    "Bash(ls:*)", "Bash(cat:*)", "Bash(head:*)", "Bash(tail:*)",
    "Bash(rg:*)", "Bash(fd:*)", "Bash(find:*)", "Bash(wc:*)",
    "--disallowedTools", "NotebookEdit",
]

SWEEP_PROMPT = (
    "You are reviewing a round of work on the {name} project (root: {root}) — the sweep is the "
    "iteration's turn: fired whenever a round of work reaches a review point (day's end is only "
    "the degenerate case). A sweep is NOT a daily event — it may fire several times in one day, and "
    "finding the queue already stocked or a session log already present from an earlier pass today "
    "is normal, not an error or a sign the work is done. Each sweep is its own pass over the current "
    "queue state. All of this happens in one pass, visibly:\n"
    "1. RULINGS — if a ruling ledger is configured ({ledger}): apply every ticked/filled/struck "
    "ruling to its canonical documents exactly as written; annotate each applied row "
    "'— swept {today}'; never infer rulings; launch-type rulings (a 'go', a grant, an "
    "acquisition, a schedule) are NOT executed — append 'LAUNCH DIRECTIVE: <what>' to "
    "{runtime_dir}/sweep.log.\n"
    "1b. BALLOTS — a persona's `QUESTIONS.md` (an `ask_type: fill` entry) carries the "
    "Dramaturge's casting questions as checkboxes; a ticked box is the patron's ruling. For each "
    "tick: if it CONFIRMS the persona's current chief/cast, mark it resolved, clear that question "
    "from the file, annotate '— swept {today}'. If it CHANGES the cast (a different chief, a figure "
    "kept/cut/re-weighted, a write-in), that is a RECAST that belongs to the Dramaturge, never the "
    "desk: raise it as a memo to {root}/Characters/inbox/ (and record it) — do NOT recast the "
    "persona BODY/SOURCES from the desk (the standing guardrail). Either way, learn the standing "
    "casting preference into MEMORY so the question is not re-asked.\n"
    "2. DIFF — for each entry in {queue_path} (approved and pending alike): diff the file "
    "against {runtime_dir}/snapshots/<id>.orig (the cached original; `diff -u` is available). "
    "Where no snapshot exists, say so and assess from the file and its brief. Also read each "
    "entry's `comment` (the note the patron left while reading) — they direct what follows.\n"
    "2a. NO-OP CHECK — if EVERY entry is byte-identical to its snapshot, carries no new comment, "
    "and the ledger shows no fresh ruling, then a prior sweep already processed this batch and "
    "nothing has changed since: report 'nothing to sweep since the last pass' in one line and STOP "
    "(do not re-archive, re-restock, or re-log). A re-fire over an unchanged state is a clean no-op, "
    "not a problem. Proceed through the steps below only when there is a real change to process.\n"
    "3. ASSESS — characterize each change in a sentence or two: what the patron (or their "
    "co-editing agent) did, and the apparent intent.\n"
    "4. RIPPLE — check the changes against the rest of the project for consistency and broader "
    "implications: stale cross-references, contradicted statements, renamed terms. FIX in place "
    "what is mechanical; FLAG in the log what needs judgment. A patron comment naming a renamed "
    "term or a change-that-needs-propagation makes that propagation a REQUIRED ripple: find "
    "every other file carrying the old form and fix it. Never touch append-only records.\n"
    "5. LEARN — update {desk_dir}/MEMORY.md (create on first use): compare what the briefs "
    "anticipated against what the patron actually did — the diffs, comments, and rulings are "
    "the evidence. Record ONLY what generalizes to future sittings: standing preferences, "
    "rulings that must never be re-asked, corrections to the curator's own predictions. Terse "
    "dated bullets; revise or strike entries today's evidence contradicts; keep the file under "
    "~80 lines — memory, not a log (the session log holds the particulars). If the evidence "
    "contradicts PROJECT.md itself, amend that file minimally and note the amendment here.\n"
    "6. LOG — write {runtime_dir}/sessions/{stamp}-session.md (create dir on first use; the {stamp} "
    "is unique per sweep — each sweep gets its OWN log, so several may sit under one date; never "
    "overwrite an earlier pass's log): entries "
    "reviewed, per-entry assessment, ripples fixed, ripples flagged, directives raised, AND each "
    "patron comment verbatim under its file with how you acted on it (propagated / recorded / "
    "deferred). The log is the sitting's record; MEMORY.md is its distillation.\n"
    "7. RESTOCK — archive the processed entries to {desk_dir}/archive/{today}-batch.json, "
    "delete their snapshots from {runtime_dir}/snapshots/, then load the NEXT batch into {queue_path} per "
    "{desk_dir}/review-program.md (entries with real curatorial briefs — read enough of each "
    "new document to write them; honor the entry schema already in the queue file). When a batch "
    "is persona pairs (BODY+SOURCES), also load any sibling `QUESTIONS.md` as a companion "
    "`ask_type: fill` entry (id `<persona>-questions`, a brief naming the open casting question) so "
    "the patron can tick the ballot in the same sitting. Mark the "
    "loaded batch in review-program.md. If the program is exhausted, leave the queue empty "
    "with a note saying so.\n"
    "8. Report tersely as you go — every step narrated in a line or two, since the patron "
    "watches this stream live."
)

# shared by the one-shot bootstrap and the interview's found step
QUEUE_SCHEMA = (
    "Queue entry schema (all fields): id (slug), title, path (absolute), project (name), "
    "project_root (absolute), ask_type (input|tuning|judgment), ask (one line: what is wanted "
    "from the patron), desk_item (null), urgency (high|medium|low), status (\"pending\"), "
    "unblocks (one line or \"—\"), brief (the curatorial brief — see the brief standard below).\n"
    "BRIEF STANDARD (both audiences, in order): the brief is shown to the patron the instant a "
    "file loads — seconds before any agent reply — so it must do real orienting work on its own. "
    "Write it in TWO movements: (1) a FIRST LINE that is plain, jargon-free, and immediately "
    "useful to a human — what this document is and what is wanted of them, in a sentence they "
    "can act on cold; (2) then 1–3 sentences of precise detail that also prime the review agent "
    "(specifics, terms of art, what to check). The two movements MUST NOT restate each other — "
    "movement 2 adds only precision movement 1 omitted (an exact quote, the fault's location, a "
    "concrete check); if you'd only be re-saying the lead in other words, stop at the lead. Spell "
    "out abbreviations on first use; no procedural agent-directed tails ('check file X first') — "
    "fold any sharpening cross-reference into the ask itself. 2–4 sentences total. Never make the "
    "patron decode shorthand to learn why a file is in front of them.\n"
)

BOOTSTRAP_PROMPT = (
    "You are the founding curator of the {name} project's desk (root: {root}). Setsweep — "
    "the patron's three-pane review app — has just registered this project; your work creates "
    "its review apparatus. Duties, in order:\n"
    "1. SURVEY — map the project briskly: top-level structure, any README/CLAUDE/index files, "
    "what kinds of documents live here and which carry the project's substance (as opposed to "
    "machinery, data dumps, or generated artifacts). Sample; do not read everything. "
    "Characterize, in your own words for the charter, what this project is and what 'review' "
    "means here — consistent with the type the patron selected (your kit, injected below; if "
    "none was chosen, judge it from the survey). Every apparatus you build must fit this "
    "project, not a generic template.\n"
    "2. THE CHARTER — write {desk_dir}/PROJECT.md: the standing profile every future "
    "agent receives on arrival (it is auto-injected into the review agent, the sweep, and "
    "pickups). Sections: what this project IS (identity and purpose, in the patron's terms, "
    "including the kind you named); the document families and their key paths; the review lens "
    "(what the patron cares about here — register, standards, sensitivities); conventions "
    "(formats, naming, what must never be auto-changed); key references (the project's own "
    "canonical indexes, if any). Keep it under ~80 lines — an orientation, not an archive.\n"
    "3. THE MEMORY — seed {desk_dir}/MEMORY.md: a short header naming its purpose (the "
    "curator's accrued judgment — rulings made and patron preferences learned, distilled by "
    "every sweep; honored by every agent without re-asking) plus any preference ALREADY IN "
    "EVIDENCE in the project's own files (a CLAUDE.md's stated conventions, style notes, an "
    "existing editorial standard). Record only what the files attest; never invent or assume "
    "preferences — an honest near-empty memory beats a speculative full one.\n"
    "4. THE TRACKING SYSTEM — write {desk_dir}/review-program.md: the project's review program. "
    "Name the document families you found, which need the patron's reading or judgment and why, "
    "a batch plan if volume warrants batching, and the desk conventions (one batch in the queue "
    "at a time; the patron's in-editor emendations are themselves the tuning; approve = done "
    "with this document; rework sends a memo to the curator). Create no speculative empty "
    "directories.\n"
    "5. THE FIRST QUEUE — populate {queue_path} (JSON; schema below) with the first batch: "
    "5–10 entries, the documents that most need the patron's attention first, urgency-ranked. "
    "Read enough of each chosen document to write an HONEST curatorial brief to the BRIEF "
    "STANDARD in the schema below (plain human-usable first line, then precise detail) — the "
    "brief is shown to the patron the instant the file loads AND given to the review agent, so "
    "it must orient a human on its own and prime the agent both. Set the top-level \"curated\" "
    "field to today + your role.\n"
    "6. If the folder does not look like a reviewable project at all (empty, pure data, etc.), do NOT "
    "invent entries — write a queue note saying what you found and what the patron should "
    "clarify, and say so in your report.\n"
    + QUEUE_SCHEMA +
    "Finish with a terse report: families found, entries filed, anything odd."
)

# ---- the founding interview (center-panel, multi-turn) ----
# Phase A: read-only survey + conversation with the patron in the middle pane.
# Phase B (patron clicks finish): FOUND_PROMPT resumes the same session with write
# tools; the curator founds the desk and "swings over" to the right chat pane.
INTERVIEW_ROLE = (
    "You are the founding curator of the {name} project (root: {root}), conducting the "
    "FOUNDING INTERVIEW in the center panel of the patron's review app. Nothing is written "
    "in this phase — your tools are read-only; the desk is founded only when the patron "
    "clicks finish ✓.\n"
    "WHAT THIS INTERVIEW IS FOR — hold this yourself, and put it to the patron plainly in your "
    "own words at the start: you are about to become this project's standing second reader. A "
    "short conversation now buys context you'd otherwise make them re-explain at every sitting "
    "— what this project is to THEM, what they want watched, what is off-limits. You are "
    "gathering just enough to found a desk that fits, NOT extracting a full specification. And "
    "the desk is amendable: every sweep refines the charter and memory, so this is a strong "
    "start, never a last word. The interview serves the patron — they can click finish ✓ the "
    "moment they're satisfied, and you should make that feel available throughout, not earned "
    "at the end.\n"
    "SURVEY — map the project briskly: top-level structure, README/CLAUDE/index files, what "
    "kinds of documents live here. Sample; do not read everything. Form a read of what this "
    "project is and what 'review' means here, consistent with the kind the patron selected "
    "(your kit, injected below; if none was chosen, judge it from the survey and the patron).\n"
    "INTERVIEW — your first reply: a 3–4 line read of what you found, then one or two lines "
    "framing what this interview is for and that they can finish whenever they like, then your "
    "opening questions. The strongest signal at founding is the patron themselves; the files "
    "only attest what they attest. THE CORE you want to come away with (ask in your own words, "
    "and skip what the survey already answers): what this project is TO THEM; what they want a "
    "second reader for; what must never be touched. Beyond the core, add only questions the "
    "survey left genuinely open — at most 3–4 per turn, numbered, so they can answer by number. "
    "Follow up; clarify; challenge gently where the files contradict them. Workmanlike and "
    "terse — no flattery, no ceremony.\n"
    "PACING — close each turn by orienting the patron: a light word on what you've still got in "
    "mind to cover, and the standing reminder that they can keep going or click finish ✓ now and "
    "let the desk improve from there. When the core is covered, say so plainly and RECOMMEND "
    "finishing — stop manufacturing questions. The patron decides when it ends; your job is to "
    "keep that choice easy and well-informed at every turn, never to interrogate them to "
    "exhaustion."
)

INTERVIEW_KICKOFF = (
    "(The patron has opened the founding interview. Survey the project now, then give your "
    "read and your opening questions.)"
)

FOUND_PROMPT = (
    "(The patron clicked finish — the interview is closed and you now hold write tools. "
    "Found the desk for {name} ({root}) in one pass. Everything the interview established "
    "governs; where their answers and the files disagree, THEIR ANSWERS WIN.\n"
    "1. THE CHARTER — write {desk_dir}/PROJECT.md: what this project IS in the patron's own "
    "terms (quote them where their words were exact), the kind you named, document families and "
    "key paths, the review lens they gave you, conventions and what must never be auto-changed, "
    "key references. Under ~80 lines.\n"
    "2. THE MEMORY — seed {desk_dir}/MEMORY.md: a short header naming its purpose (the "
    "curator's accrued judgment — rulings made and patron preferences learned, distilled by "
    "every sweep; honored by every agent without re-asking), then the preferences the patron "
    "STATED in this interview and any attested in the project's own files. Nothing invented.\n"
    "3. THE PROGRAM — write {desk_dir}/review-program.md: document families, what needs their "
    "reading or judgment and why, a batch plan if volume warrants, desk conventions (one "
    "batch at a time; in-editor emendations are the tuning; approve = done; rework sends a "
    "memo).\n"
    "4. THE FIRST QUEUE — populate {queue_path} (JSON; schema below): 5–10 entries, "
    "urgency-ranked by what the interview said matters most. Read enough of each document "
    "to write an HONEST brief to the BRIEF STANDARD in the schema below (plain human-usable "
    "first line, then precise detail). Set the top-level \"curated\" field to today + your role.\n"
    + QUEUE_SCHEMA +
    "5. Your final message is shown in the RIGHT chat pane, where you live from now on — "
    "address the patron directly: one line on the kind of desk now standing, the first "
    "batch they'll find in the queue at left, and that they should select the first entry to "
    "begin; questions and conversation continue in that pane.)"
)

DEFAULT_ROLE = (
    "You are the desk assistant in the patron's document-review sitting (project: {project}). "
    "Their first message opens with the active file's path and its curatorial brief — context "
    "prepared in advance so neither of you must re-derive it. Help them understand, "
    "troubleshoot, and revise that file; read any project files you need. You CAN edit files "
    "directly — do so when they ask for changes, with minimal, surgical diffs; their app reloads "
    "the open file after your turn. When DISCUSSING a passage rather than changing it, quote "
    "it in a fenced code block (their app turns those into jump-to-line buttons). Never touch "
    "append-only records or logs unless they explicitly direct it. Be concise and direct; they "
    "are mid-sitting and mental gear-shifts are the enemy."
)

CONTEXT_BLOCK = (
    "[Active file: {path}]\n[Curatorial brief] {brief}\n[The ask] {ask}\n\n"
)

# the glance: a one-breath reaction fired automatically when a file is opened,
# reading ONLY the brief (not the file). Terse by construction — it keeps the
# conversation warm and surfaces anything unclear, nothing more.
GLANCE_PROMPT = (
    "You are the desk assistant in the patron's review sitting (project: {project}). "
    "They have just opened a document; they have ALREADY read its brief (shown to them on load), "
    "so do NOT restate or summarize it. In ONE or TWO sentences — no preamble, no greeting — "
    "ADD something: a question worth asking, a tension or risk the brief implies, what you'd "
    "check first, or a connection worth noting. If the brief raises nothing to add, say so in "
    "a few words rather than padding. Terse and concrete; they read or edit the document "
    "next.\n\n[Document: {path}]\n[Brief they just read] {brief}"
)

EMPTY_QUEUE = {"curated": "empty — entries are filed by curating agents", "entries": []}


# ---------- projects ----------

def load_projects() -> list[dict]:
    data = json.loads(PROJECTS_PATH.read_text())
    # presented alphabetically by name (case-insensitive); write paths read raw JSON,
    # so the on-disk order/`note` are untouched. No project is pinned to the top.
    return sorted(data["projects"], key=lambda p: p.get("name", "").lower())


def get_project(pid: str | None) -> dict:
    projects = load_projects()
    if pid:
        for pr in projects:
            if pr["id"] == pid:
                return pr
        raise KeyError(f"unknown project: {pid}")
    return projects[0]


def project_root(proj: dict) -> Path:
    return Path(proj["root"]).expanduser().resolve()


def desk_dir(proj: dict) -> Path:
    """Durable desk — always at <project_root>/.setsweep (syncs with the project)."""
    return project_root(proj) / ".setsweep"


def intake_paths(proj: dict):
    """(watch, responses, outbound) resolved for an inbox project's `intake` block, or None.
    Mirrors setsweep-watch.resolve_intake: `watch` may be a folder, '.', or a subdir; relatives
    join to the root; responses/outbound default under the root. Used to thread the outbound
    folder into the sweep so approved drafts are staged outward (never transmitted)."""
    cfg = proj.get("intake")
    if not isinstance(cfg, dict) or not cfg.get("watch"):
        return None
    root = project_root(proj)

    def _resolve(val, default):
        p = Path(val).expanduser() if val else Path(default)
        return (p if p.is_absolute() else (root / p)).resolve()

    return (_resolve(cfg["watch"], "."),
            _resolve(cfg.get("responses"), "responses"),
            _resolve(cfg.get("outbound"), "outbox"))


def runtime_dir(proj: dict) -> Path:
    """Volatile runtime state — the high-churn files (queue, chatlog, logs, snapshots,
    sessions) that must NOT sync. Kept INSIDE the project at <root>/.setsweep/runtime/
    so they stay within the review agent's project-root fence (no out-of-sandbox
    --add-dir needed). If you sync the project tree (Seafile/Dropbox/etc.), exclude
    `.setsweep/runtime/` at the sync layer (e.g. a `seafile-ignore.txt`) so the daemon
    doesn't race these rapid rewrites. The durable desk files stay in desk_dir() and sync
    normally. (A sync idiosyncrasy is fixed at the sync layer, not by moving state outside
    the sandbox.)"""
    d = desk_dir(proj) / "runtime"
    d.mkdir(parents=True, exist_ok=True)
    return d


def queue_path(proj: dict) -> Path:
    rd = runtime_dir(proj)
    return rd / "queue.json"


def allowed_roots() -> list[Path]:
    roots = list(BASE_ALLOWED_ROOTS)
    try:
        roots += [project_root(p) for p in load_projects()]
    except Exception:  # noqa: BLE001 — registry problems surface elsewhere
        pass
    return roots


def safe_path(p: str, base: Path | None = None) -> Path:
    raw = Path(p).expanduser()
    if not raw.is_absolute():
        # relative inputs resolve against the project root, never the server CWD
        # (the server serves many projects from one process, so CWD is meaningless here)
        if base is None:
            raise PermissionError(f"refusing CWD-relative path: {p}")
        raw = Path(base) / raw
    rp = raw.resolve()
    for root in allowed_roots():
        try:
            if rp.is_relative_to(root.resolve()):
                return rp
        except (OSError, ValueError):
            continue
    raise PermissionError(f"path outside allowed roots: {p}")


# ---------- queue io ----------

def load_queue(proj: dict) -> dict:
    qp = queue_path(proj)
    with QUEUE_LOCK:
        if not qp.exists():
            qp.parent.mkdir(parents=True, exist_ok=True)
            qp.write_text(json.dumps(EMPTY_QUEUE, indent=2))
        return json.loads(qp.read_text())


def mutate_queue(proj: dict, fn) -> dict:
    qp = queue_path(proj)
    with QUEUE_LOCK:
        q = json.loads(qp.read_text())
        fn(q)
        tmp = qp.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(q, indent=2, ensure_ascii=False))
        tmp.replace(qp)
        return q


def project_orientation(proj: dict) -> str:
    """The curator's standing context, injected into every agent the app spawns:
    PROJECT.md (the charter — what this project is and how the patron reads it) and
    MEMORY.md (accrued judgment — rulings made, preferences learned across sittings).
    Identity lives in these files, not in any one session: any fresh agent that reads
    them IS the curator."""
    desk = desk_dir(proj)
    sections = (
        ("PROJECT.md", 2500, "Project orientation (PROJECT.md, curator-maintained)"),
        ("MEMORY.md", 2000, "Curator memory (MEMORY.md — rulings already made and patron "
                            "preferences already learned; honor these without re-asking)"),
    )
    parts = []
    for fname, cap, label in sections:
        try:
            text = (desk / fname).read_text(encoding="utf-8", errors="replace").strip()
        except OSError:
            continue
        if text:
            parts.append(f"{label}:\n{text[:cap]}")
    return "\n\n".join(parts)


def base_handbook() -> str:
    """The shared curator handbook (kits/_base.md) — cross-cutting conduct injected into
    every spawned agent, BENEATH the per-project charter (which is more specific and wins).
    Returns "" if the file is absent, so the desk runs with or without a kits/ directory."""
    try:
        text = (APPDIR / "kits" / "_base.md").read_text(encoding="utf-8", errors="replace").strip()
    except OSError:
        return ""
    return f"Curator handbook (how every desk here is worked):\n{text[:4000]}" if text else ""


def scope_note(proj: dict) -> str:
    """A soft scope bound injected into the curator's prompts when a project sets max_depth.
    It shapes what the curator surveys / queues / attributes; it is not a hard read-fence —
    a deeper file the patron points at can still be opened. '' when unbounded."""
    d = proj.get("max_depth")
    if not isinstance(d, int) or d < 1:
        return ""
    detail = ("only files directly in the root folder" if d == 1
              else f"the root folder plus {d - 1} level(s) of subdirectories")
    return (f"Project scope (max depth {d}): survey, queue, and attribute only files within {d} "
            f"director{'y level' if d == 1 else 'y levels'} of the root — {detail}. Deeper "
            "subtrees are out of scope; do not trawl them. If the patron explicitly points you at a "
            "deeper file you may open that one file, but do not expand the desk's scope to its subtree.")


def session_path(proj: dict) -> Path:
    """The project's single persistent-session record (replaces the old per-file model
    and the founding interview.json). One Claude Code session per project — named
    setsweep-<project> — runs interview → found → chat → sweep; this file is its
    source of truth: {session_id, status, last_entry, name}."""
    return runtime_dir(proj) / "session.json"


def load_session(proj: dict) -> dict:
    """Project session state. Empty {} means no session yet. On first read it migrates
    a legacy interview.json (the prior per-project interview record) into session.json,
    so an in-flight founding survives the refactor."""
    sp = session_path(proj)
    try:
        return json.loads(sp.read_text())
    except (OSError, json.JSONDecodeError):
        pass
    # one-time migration of the legacy interview record
    legacy = runtime_dir(proj) / "interview.json"
    try:
        data = json.loads(legacy.read_text())
    except (OSError, json.JSONDecodeError):
        return {}
    if data:
        atomic_write(sp, json.dumps(data, indent=2))
    return data


def save_session(proj: dict, **fields) -> dict:
    """Shallow-merge the given fields into the project session record; returns it."""
    cur = load_session(proj)
    cur.update(fields)
    session_path(proj).parent.mkdir(parents=True, exist_ok=True)
    atomic_write(session_path(proj), json.dumps(cur, indent=2))
    return cur


# back-compat shims: the interview is now just the project session's first phase
def interview_path(proj: dict) -> Path:
    return session_path(proj)


def load_interview(proj: dict) -> dict:
    """Founding state lives in the project session now: {} (never started) |
    status 'interviewing' | 'founded'. Reads through to load_session."""
    return load_session(proj)


def save_interview(proj: dict, data: dict):
    session_path(proj).parent.mkdir(parents=True, exist_ok=True)
    atomic_write(session_path(proj), json.dumps(data, indent=2))


def find_entry(q: dict, entry_id: str) -> dict:
    for e in q["entries"]:
        if e["id"] == entry_id:
            return e
    raise KeyError(entry_id)


def session_name(proj: dict, entry: dict | None = None) -> str:
    """Display name set on the project's single Claude session via `--name`, so it is
    legible in the `/resume` picker and terminal title. One session per project now, so
    the name is project-level: setsweep-<project>, slugified and length-capped. The
    `entry` argument is accepted but ignored (kept for call-site compatibility)."""
    base = proj.get("name") or "desk"
    body = re.sub(r"[^a-z0-9]+", "-", base.lower()).strip("-")[:48]
    return f"setsweep-{body}" if body else "setsweep"


def ensure_snapshots(proj: dict, q: dict):
    """Cache each pending entry's file bytes at <desk>/snapshots/<id>.orig — the sweep's
    diff baseline. Runs on every queue read, so the moment any batch lands (bootstrap,
    pickup, sweep restock, hand-filed) and the app sees it, originals are cached.
    Never overwrites an existing snapshot: first sight = the original."""
    snap_dir = runtime_dir(proj) / "snapshots"
    for e in q.get("entries", []):
        if e.get("status") != "pending" or not e.get("id"):
            continue
        dest = snap_dir / (slug(str(e["id"])) + ".orig")
        if dest.exists():
            continue
        try:
            data = safe_path(e["path"], project_root(proj)).read_bytes()
        except (PermissionError, KeyError, OSError, RuntimeError):
            continue  # source missing or outside safe roots: skip cleanly
        snap_dir.mkdir(parents=True, exist_ok=True)
        tmp = dest.with_name(dest.name + ".tmp")
        tmp.write_bytes(data)
        tmp.replace(dest)


def _snapshot_path(proj: dict, entry_id) -> Path:
    return runtime_dir(proj) / "snapshots" / (slug(str(entry_id)) + ".orig")


def _read_pair(proj: dict, e: dict):
    """(original_lines, live_lines) for an entry, or (None, None) if either side is
    unavailable (no snapshot yet, or the source is missing/outside the fence)."""
    snap = _snapshot_path(proj, e.get("id"))
    if not snap.exists():
        return None, None
    try:
        orig = snap.read_text(errors="replace").splitlines()
        live = safe_path(e["path"], project_root(proj)).read_text(errors="replace").splitlines()
    except (PermissionError, KeyError, OSError, RuntimeError):
        return None, None
    return orig, live


def entry_diffstat(proj: dict, e: dict) -> dict | None:
    """Lines added/removed vs. the entry's snapshot — the change made THIS sitting.
    None when there is no baseline to compare against (so the UI can stay silent)."""
    orig, live = _read_pair(proj, e)
    if orig is None:
        return None
    added = removed = 0
    for ln in difflib.unified_diff(orig, live, lineterm=""):
        if ln[:1] == "+" and not ln.startswith("+++"):
            added += 1
        elif ln[:1] == "-" and not ln.startswith("---"):
            removed += 1
    return {"added": added, "removed": removed}


def entry_diff_text(proj: dict, e: dict) -> str:
    """Unified diff (snapshot → live) for the Info panel's view-diff toggle."""
    orig, live = _read_pair(proj, e)
    if orig is None:
        return ""
    return "\n".join(difflib.unified_diff(
        orig, live, fromfile="original", tofile="current", lineterm=""))


# ---------- chatlog (persistent per-project transcript) ----------

def chatlog_path(proj: dict) -> Path:
    # derived from the registry's queue path, never from client input
    return queue_path(proj).parent / "chatlog.json"


def load_chatlog(proj: dict) -> list:
    with CHATLOG_LOCK:
        try:
            msgs = json.loads(chatlog_path(proj).read_text()).get("messages", [])
            return msgs if isinstance(msgs, list) else []
        except (OSError, json.JSONDecodeError):
            return []


def save_chatlog(proj: dict, messages: list) -> int:
    messages = messages[-CHATLOG_CAP:]
    with CHATLOG_LOCK:
        cp = chatlog_path(proj)
        cp.parent.mkdir(parents=True, exist_ok=True)
        atomic_write(cp, json.dumps({"messages": messages}, ensure_ascii=False))
    return len(messages)


# ---------- settings ----------

def load_settings() -> dict:
    with SETTINGS_LOCK:
        if not SETTINGS_PATH.exists():
            atomic_write(SETTINGS_PATH, "{}")
            return {}
        try:
            return json.loads(SETTINGS_PATH.read_text())
        except json.JSONDecodeError:
            return {}


def save_settings(patch: dict) -> dict:
    """Shallow-merge patch into settings.json; returns the merged dict."""
    with SETTINGS_LOCK:
        try:
            cur = json.loads(SETTINGS_PATH.read_text()) if SETTINGS_PATH.exists() else {}
        except json.JSONDecodeError:
            cur = {}
        cur.update(patch)
        atomic_write(SETTINGS_PATH, json.dumps(cur, indent=2, ensure_ascii=False))
        return cur


def atomic_write(path: Path, text: str):
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


def slug(s: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", s).strip("_") or "x"


def register_project(name: str, root: str, kit: str | None = None,
                     max_depth=None) -> dict:
    """Register a project: validate, append to the registry, seed its desk. The single
    source of truth for 'add a project', shared by the HTTP handler and the CLI so the
    fence gate (project roots must be under $HOME — registered roots extend the file-API
    fence) is enforced one way. Raises ValueError(message) on any validation failure;
    returns the project dict on success. Creates the registry if it does not exist yet
    (first run), so a fresh install can register its first desk."""
    name = str(name or "").strip()
    root_raw = str(root or "").strip()
    if not name:
        raise ValueError("name required")
    if not root_raw:
        raise ValueError("folder required")
    try:
        rp = Path(root_raw).expanduser().resolve()
    except (OSError, RuntimeError):
        raise ValueError(f"cannot resolve folder: {root_raw}")
    if not rp.is_dir():
        raise ValueError(f"folder does not exist (or is not a directory): {rp}")
    if not rp.is_relative_to(HOME.resolve()):
        raise ValueError(f"folder must be under {HOME}")
    pid = slug(name).lower()
    proj = {
        "id": pid,
        "name": name,
        "root": root_raw.rstrip("/") or root_raw,  # ~-form preserved as given
        "rework_agents": [{"id": "curator", "name": f"the {name} curator — queue & sweep"}],
    }
    if kit in kits.KINDS:                          # the patron's pick (no auto-detection)
        proj["kit"] = kit
    try:
        depth = int(max_depth)
    except (TypeError, ValueError):
        depth = 0
    if depth >= 1:                                  # 0 / blank → unlimited (no field stored)
        proj["max_depth"] = depth
    with PROJECTS_LOCK:
        try:
            data = json.loads(PROJECTS_PATH.read_text())
        except (OSError, json.JSONDecodeError):
            data = {"projects": []}            # first run: no registry yet
        data.setdefault("projects", [])
        if any(p["id"] == pid for p in data["projects"]):
            raise ValueError(f"duplicate project id: {pid}")
        data["projects"].append(proj)
        PROJECTS_PATH.parent.mkdir(parents=True, exist_ok=True)
        atomic_write(PROJECTS_PATH, json.dumps(data, indent=2, ensure_ascii=False))
    (rp / ".setsweep").mkdir(parents=True, exist_ok=True)   # durable desk dir
    qp = queue_path(proj)
    if not qp.exists():
        atomic_write(qp, json.dumps(
            dict(EMPTY_QUEUE, curated="awaiting founding curation"),
            indent=2, ensure_ascii=False))
    return proj


def refound_desk(proj: dict) -> dict:
    """Reset a project's desk to the pristine UNFOUNDED seed so its founding interview runs
    again on next selection. The whole old desk (charter, memory, runtime, queue, transcript)
    is copied to a machine-local backup first; the patron's founding note is carried into the
    fresh seed so the rerun keeps their steer."""
    desk = desk_dir(proj)
    note = ""
    sj = desk / "runtime" / "session.json"
    try:
        if sj.exists():
            note = json.loads(sj.read_text()).get("founding_note", "")
    except (OSError, json.JSONDecodeError):
        pass
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    bk = HOME / ".cache" / "setsweep-refound-backups" / f"{proj['id']}-{stamp}"
    if desk.exists():
        bk.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(desk, bk)
        shutil.rmtree(desk)
    rt = desk / "runtime"
    rt.mkdir(parents=True, exist_ok=True)
    atomic_write(rt / "queue.json",
                 json.dumps(dict(EMPTY_QUEUE, curated="awaiting founding curation"), indent=2))
    atomic_write(rt / "session.json", json.dumps({"founding_note": note}, indent=2))
    return {"ok": True, "backup": str(bk), "note_preserved": bool(note)}


def project_for_path(p: Path) -> dict | None:
    """The registered project whose root contains p (the most specific, for nested roots).
    Used to attribute an editor save to the right desk's working record."""
    p = Path(p).resolve()
    best = None
    best_len = -1
    for proj in load_projects():
        try:
            root = project_root(proj).resolve()
        except (OSError, ValueError):
            continue
        if (p == root or root in p.parents) and len(str(root)) > best_len:
            best, best_len = proj, len(str(root))
    return best


def mark_founded_if_filed(proj: dict) -> bool:
    """A desk is founded once the curator has filed at least one queue entry; otherwise
    the session stays resumable and founding can be run again. Returns True if it flipped
    to founded. Shared by the founding handler and the CLI so both judge 'done' the same."""
    try:
        if load_queue(proj).get("entries"):
            save_session(proj, status="founded")
            return True
    except Exception:  # noqa: BLE001
        pass
    return False


# ---------- admin / debug ----------

CACHE = HOME / ".cache" / "claude"


def _read_json(path: Path):
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return None


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except (OSError, ProcessLookupError):
        return False


def _sentinel_status() -> dict:
    """desk-sentinel liveness: heartbeat age + whether the pid names a live process."""
    out = {"heartbeat_age": None, "pid": None, "pid_alive": None, "state": "down"}
    state = _read_json(CACHE / "desk-sentinel-state.json")
    if isinstance(state, dict) and isinstance(state.get("_heartbeat"), (int, float)):
        import time
        out["heartbeat_age"] = round(time.time() - state["_heartbeat"], 1)
    host = os.uname().nodename.split(".")[0]
    pidfile = CACHE / f"desk-sentinel-{host}.pid"
    try:
        pid = int(pidfile.read_text().strip())
        out["pid"] = pid
        out["pid_alive"] = _pid_alive(pid)
    except (OSError, ValueError):
        pass
    age = out["heartbeat_age"]
    if out["pid_alive"] and age is not None and age < 300:
        out["state"] = "live"
    elif out["pid_alive"] or (age is not None and age < 1800):
        out["state"] = "stale"
    else:
        out["state"] = "down"
    return out


def _events_tail(n: int = 20) -> list[str]:
    try:
        lines = (CACHE / "desk-events.log").read_text(errors="replace").splitlines()
        return lines[-n:]
    except OSError:
        return []


def _project_debug(proj: dict) -> dict:
    """Per-project counts, read defensively — a broken project never 500s the report."""
    info = {
        "id": proj.get("id"), "name": proj.get("name"), "root": proj.get("root"),
        "entries": None, "status": {}, "comments": 0,
        "snapshots": None, "chatlog": False, "sessions": False, "error": None,
        "persona_family": None,
    }
    try:
        q = load_queue(proj)
        entries = q.get("entries", [])
        info["entries"] = len(entries)
        for e in entries:
            st = e.get("status", "?")
            info["status"][st] = info["status"].get(st, 0) + 1
            if e.get("comment"):
                info["comments"] += 1
        rd = runtime_dir(proj)
        snap = rd / "snapshots"
        info["snapshots"] = len(list(snap.glob("*.orig"))) if snap.is_dir() else 0
        info["chatlog"] = (rd / "chatlog.json").exists()
        info["sessions"] = (rd / "sessions").is_dir()
    except Exception as e:  # noqa: BLE001 — report, never raise
        info["error"] = repr(e)
    # Persona-rebuild family status — a whole-family progress read (the queue only
    # tracks the active batch). Surfaced only where a Xanadu personas dir exists;
    # never lets its own failure break the report.
    try:
        pdir = Path(proj.get("root", "")) / "Worlds/Xanadu/personas"
        if pdir.is_dir():
            fam = {"total": 0, "rebuilt": 0, "pending": 0, "curiosity": 0}
            for d in sorted(pdir.iterdir()):
                if not d.is_dir() or d.name.startswith("_"):
                    continue
                if not (d / "BODY.md").is_file():
                    continue
                fam["total"] += 1
                if (d / "SOURCES.md").is_file():
                    fam["rebuilt"] += 1
                else:
                    fam["pending"] += 1
                if (d / "CURIOSITY.md").is_file():
                    fam["curiosity"] += 1
            info["persona_family"] = fam
    except Exception:  # noqa: BLE001 — the family scan must never 500 the report
        pass
    return info


def admin_report(active_pid: str | None) -> dict:
    """Read-only debug snapshot for the Admin overlay. All reads home-fenced and
    defensive: missing files surface as null, never a 500."""
    try:
        projects = load_projects()
    except Exception:  # noqa: BLE001
        projects = []
    health = _read_json(CACHE / "inventory-health.json")
    watch = health.get("setsweep-watch") if isinstance(health, dict) else None
    return {
        "server": {
            "port": SERVER_PORT,
            "claude_path": CLAUDE,
            "claude_exists": Path(CLAUDE).exists() if CLAUDE else False,
            "project_count": len(projects),
            "active": active_pid,
        },
        "settings": load_settings(),
        "projects": [_project_debug(p) for p in projects],
        "sentinel": _sentinel_status(),
        "events": _events_tail(20),
        "watcher": watch,
    }


# ---------- http ----------

class Handler(BaseHTTPRequestHandler):
    # HTTP/1.0 (default): close-delimited responses make chat streaming trivial.

    def log_message(self, format, *args):  # noqa: A002 — quiet
        pass

    def send_json(self, obj, code=200):
        body = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def read_body(self) -> dict:
        n = min(int(self.headers.get("Content-Length", 0)), 10_000_000)
        return json.loads(self.rfile.read(n) or b"{}")

    def stream_line(self, obj) -> bool:
        try:
            self.wfile.write((json.dumps(obj, ensure_ascii=False) + "\n").encode())
            self.wfile.flush()
            return True
        except (BrokenPipeError, ConnectionResetError):
            return False

    def do_GET(self):
        url = urlparse(self.path)
        qs = parse_qs(url.query)
        try:
            if url.path in ("/", "/index.html"):
                body = (STATIC / "index.html").read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            elif url.path == "/marked.min.js":
                body = (STATIC / "marked.min.js").read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "application/javascript")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            elif url.path.startswith("/fonts/") and url.path.endswith(".woff2"):
                # bundled fonts only: a single basename under STATIC/fonts, no traversal
                name = url.path[len("/fonts/"):]
                fonts_dir = (STATIC / "fonts").resolve()
                fp = (fonts_dir / name).resolve()
                if "/" in name or ".." in name or fp.parent != fonts_dir or not fp.is_file():
                    self.send_json({"error": "not found"}, 404)
                    return
                body = fp.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "font/woff2")
                self.send_header("Cache-Control", "max-age=31536000, immutable")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            elif url.path == "/api/ping":
                # identity beacon: lets a new instance recognize (and retire) an
                # old setsweep holding the port — and lets anyone tell us apart
                # from a foreign service
                self.send_json({"app": "setsweep", "pid": os.getpid(),
                                "port": SERVER_PORT, "started": SERVER_STARTED})
            elif url.path == "/api/projects":
                self.send_json({"projects": load_projects(), "home": str(HOME)})
            elif url.path == "/api/kits":
                self.send_json({"kits": kits.list_kits(APPDIR / "kits", load_settings()),
                                "kinds": kits.KINDS})
            elif url.path == "/api/settings":
                self.send_json(load_settings())
            elif url.path == "/api/admin":
                self.send_json(admin_report(qs.get("project", [None])[0]))
            elif url.path == "/api/lineage":
                proj = get_project(qs.get("project", [None])[0])
                self.send_json(lineage.status(project_root(proj), max_depth=proj.get("max_depth")))
            elif url.path == "/api/queue":
                proj = get_project(qs.get("project", [None])[0])
                q = load_queue(proj)
                ensure_snapshots(proj, q)
                for e in q.get("entries", []):
                    e["diff"] = entry_diffstat(proj, e)   # {added, removed} vs snapshot, or None
                self.send_json(q)
            elif url.path == "/api/diff":
                proj = get_project(qs.get("project", [None])[0])
                eid = qs.get("id", [None])[0]
                ent = next((x for x in load_queue(proj).get("entries", [])
                            if str(x.get("id")) == str(eid)), None)
                self.send_json({"diff": entry_diff_text(proj, ent) if ent else ""})
            elif url.path == "/api/diffstat":
                proj = get_project(qs.get("project", [None])[0])
                eid = qs.get("id", [None])[0]
                ent = next((x for x in load_queue(proj).get("entries", [])
                            if str(x.get("id")) == str(eid)), None)
                self.send_json({"diff": entry_diffstat(proj, ent) if ent else None})
            elif url.path == "/api/chatlog":
                proj = get_project(qs.get("project", [None])[0])
                self.send_json({"messages": load_chatlog(proj)})
            elif url.path == "/api/interview":
                proj = get_project(qs.get("project", [None])[0])
                iv = load_interview(proj)
                self.send_json({"status": iv.get("status", "none"),
                                "has_session": bool(iv.get("session_id"))})
            elif url.path == "/api/file":
                proj = get_project(qs.get("project", [None])[0])
                p = safe_path(qs["path"][0], project_root(proj) if proj else None)
                self.send_json({"path": str(p),
                                "content": p.read_text(encoding="utf-8", errors="replace")})
            else:
                self.send_json({"error": "not found"}, 404)
        except PermissionError as e:
            self.send_json({"error": str(e)}, 403)
        except FileNotFoundError:
            self.send_json({"error": "file not found"}, 404)
        except KeyError as e:
            self.send_json({"error": f"missing/unknown: {e}"}, 400)
        except Exception as e:  # noqa: BLE001
            self.send_json({"error": repr(e)}, 500)

    def do_POST(self):
        url = urlparse(self.path)
        try:
            d = self.read_body()
            if url.path == "/api/save":
                sp = get_project(d.get("project")) if d.get("project") else None
                p = safe_path(d["path"], project_root(sp) if sp else None)
                tmp = p.with_name(p.name + ".desk-tmp")
                tmp.write_text(d["content"], encoding="utf-8")
                tmp.replace(p)  # atomic write; rely on your VCS/sync layer for version history
                proj = project_for_path(p)            # the patron's own edit → user lineage
                if proj:
                    try:
                        lineage.log_user_edit(project_root(proj), [str(p)])
                    except OSError:
                        pass
                self.send_json({"ok": True})
            elif url.path == "/api/approve":
                proj = get_project(d.get("project"))

                def approve(q):
                    e = find_entry(q, d["id"])
                    e["status"] = "approved"
                    e["approved"] = date.today().isoformat()

                q = mutate_queue(proj, approve)
                e = find_entry(q, d["id"])
                log = runtime_dir(proj) / "approvals.log"
                with log.open("a") as f:
                    f.write(f"{e['approved']}\t{e['id']}\t{e['path']}\t{e.get('ask','')}\n")
                self.send_json({"ok": True})
            elif url.path == "/api/settings":
                self.send_json(save_settings(d))
            elif url.path == "/api/chatlog":
                proj = get_project(d.get("project"))
                msgs = d.get("messages")
                if not isinstance(msgs, list):
                    self.send_json({"error": "messages must be a list"}, 400)
                else:
                    self.send_json({"ok": True, "count": save_chatlog(proj, msgs)})
            elif url.path == "/api/rework":
                self.rework(d)
            elif url.path == "/api/comment":
                proj = get_project(d.get("project"))
                text = str(d.get("text", "")).strip()
                ts = date.today().isoformat()

                def setc(q):
                    e = find_entry(q, d["id"])
                    if text:
                        e["comment"] = text
                    else:
                        e.pop("comment", None)  # empty = clear the note

                mutate_queue(proj, setc)
                if text:
                    with (runtime_dir(proj) / "comments.log").open("a") as f:
                        f.write(f"{ts}\t{d['id']}\t{text.replace(chr(10), ' / ')}\n")
                self.send_json({"ok": True, "comment": text})
            elif url.path == "/api/clear-session":
                proj = get_project(d.get("project"))
                # the project session is the unit now: drop its id + active-file marker
                # so the next chat turn opens a fresh thread and re-injects file context
                sess = load_session(proj)
                sess.pop("session_id", None)
                sess.pop("last_entry", None)
                atomic_write(session_path(proj), json.dumps(sess, indent=2))
                self.send_json({"ok": True})
            elif url.path == "/api/lineage/resolve":
                proj = get_project(d.get("project"))
                giton = bool(load_settings().get("lineage_git"))
                lineage.resolve(project_root(proj), d["path"],
                                actor_kind=d.get("as", "user"), git=giton)
                self.send_json({"ok": True})
            elif url.path == "/api/lineage/accept":
                proj = get_project(d.get("project"))
                giton = bool(load_settings().get("lineage_git"))
                m = lineage.accept_baseline(project_root(proj), git=giton,
                                            max_depth=proj.get("max_depth"))
                self.send_json({"ok": True, "ts": m["ts"], "files": len(m["files"])})
            elif url.path == "/api/lineage/bind":
                proj = get_project(d.get("project"))
                self.send_json({"ok": True, **lineage.ensure_directive(project_root(proj))})
            elif url.path == "/api/chat":
                self.chat(d)
            elif url.path == "/api/compact":
                self.compact(d)
            elif url.path == "/api/sweep":
                self.sweep(d)
            elif url.path == "/api/projects/add":
                self.add_project(d)
            elif url.path == "/api/projects/delete":
                self.delete_project(d)
            elif url.path == "/api/projects/edit":
                self.edit_project(d)
            elif url.path == "/api/projects/refound":
                self.refound_project(d)
            elif url.path == "/api/kits/save":
                self.save_kit(d)
            elif url.path == "/api/kits/delete":
                self.delete_kit(d)
            elif url.path == "/api/bootstrap":
                self.bootstrap(d)
            elif url.path == "/api/interview":
                self.interview(d)
            elif url.path == "/api/found":
                self.found(d)
            elif url.path == "/api/entry":
                self.update_entry(d)
            elif url.path == "/api/open-link":
                self.open_link(d)
            elif url.path == "/api/glance":
                self.glance(d)
            else:
                self.send_json({"error": "not found"}, 404)
        except PermissionError as e:
            self.send_json({"error": str(e)}, 403)
        except KeyError as e:
            self.send_json({"error": f"missing/unknown: {e}"}, 400)
        except Exception as e:  # noqa: BLE001
            self.send_json({"error": repr(e)}, 500)

    # ---- rework: send an entry back with a memo ----
    def rework(self, d):
        proj = get_project(d.get("project"))
        agent_id = str(d["agent"])
        memo = str(d.get("memo", "")).strip()
        agent_name = next(
            (a["name"] for a in proj.get("rework_agents", []) if a["id"] == agent_id),
            agent_id,
        )
        today = date.today().isoformat()

        def mark(q):
            e = find_entry(q, d["id"])
            e["status"] = "rework"
            e["rework"] = today

        q = mutate_queue(proj, mark)
        e = find_entry(q, d["id"])
        rd = runtime_dir(proj)
        rework_dir = rd / "rework"
        rework_dir.mkdir(parents=True, exist_ok=True)
        memo_path = rework_dir / f"{today}-{slug(e['id'])}-to-{slug(agent_id)}.md"
        atomic_write(memo_path, (
            f"# Rework memo — {e.get('title', e['id'])}\n\n"
            f"- recipient: {agent_name} (`{agent_id}`)\n"
            f"- entry: {e['id']}\n"
            f"- title: {e.get('title', '—')}\n"
            f"- path: {e['path']}\n"
            f"- filed: {today}\n\n"
            f"## Memo from the patron\n\n{memo}\n\n"
            f"---\nFiled from setsweep (rework), project {proj['name']}.\n"
        ))
        log = rd / "approvals.log"
        with log.open("a") as f:
            f.write(f"{today}\trework\t{e['id']}\t{e['path']}\tto={agent_id}\n")
        self.send_json({"ok": True, "memo_file": str(memo_path)})

    # ---- the right-pane agent ----
    # ---- info-pane field edits (whitelist; never touches path/id/session) ----
    ENTRY_FIELDS = {"title", "status", "urgency", "ask_type", "ask", "unblocks", "brief", "source"}

    def update_entry(self, d):
        proj = get_project(d.get("project"))
        fields = d.get("fields") or {}
        clean = {k: v for k, v in fields.items() if k in self.ENTRY_FIELDS}

        def apply(q):
            e = find_entry(q, d["id"])
            for k, v in clean.items():
                if v is None or v == "":
                    e.pop(k, None)
                else:
                    e[k] = v

        q = mutate_queue(proj, apply)
        self.send_json({"ok": True, "entry": find_entry(q, d["id"])})

    # ---- open an Obsidian-style [[wikilink]] in the OS default text editor ----
    def open_link(self, d):
        proj = get_project(d.get("project"))
        name = str(d.get("name", "")).strip()
        if not name:
            self.send_json({"error": "empty link"}, 400)
            return
        root = project_root(proj)
        target = None
        # an explicit relative path/extension is resolved directly; a bare name
        # is matched by file stem (prefer .md/.markdown/.txt) anywhere under root
        if "/" in name or name.lower().endswith((".md", ".markdown", ".txt")):
            cand = (root / name)
            target = cand if cand.exists() else None
        if target is None:
            stem = re.sub(r"\.(md|markdown|txt)$", "", name, flags=re.I).lower()
            best = None
            for ext in (".md", ".markdown", ".txt", ""):
                for p in root.rglob("*"):
                    if "/." in str(p):  # skip dotdirs (.setsweep, .git)
                        continue
                    if p.is_file() and p.stem.lower() == stem and (
                            ext == "" or p.suffix.lower() == ext):
                        best = p
                        break
                if best:
                    break
            target = best
        if target is None:
            self.send_json({"ok": False, "error": f"no file matching [[{name}]]"}, 404)
            return
        try:
            safe = safe_path(str(target))  # fence to allowed roots
        except PermissionError as e:
            self.send_json({"error": str(e)}, 403)
            return
        subprocess.Popen(["open", "-t", str(safe)])  # macOS: default text editor
        self.send_json({"ok": True, "path": str(safe)})

    # ---- glance: a fast, terse reaction to a just-loaded brief (no tools, no session) ----
    def glance(self, d):
        proj = get_project(d.get("project"))
        brief = str(d.get("brief", "")).strip() or "(no brief prepared)"
        path = str(d.get("path", ""))
        prompt = GLANCE_PROMPT.format(path=path, brief=brief, project=proj["name"])
        cmd = [CLAUDE, "-p", prompt, "--output-format", "stream-json", "--verbose",
               "--model", d.get("model") or "haiku"]
        # no tools, no resume: a throwaway reaction read only from the brief
        self.run_claude(cmd, str(project_root(proj)))

    def chat(self, d):
        proj = get_project(d.get("project"))
        sess = load_session(proj)
        sid = sess.get("session_id")
        message = d["message"]

        # The entry is OPTIONAL: a project-level turn (no file selected — e.g. answering a
        # question the sweep raised) carries no active-file context block, but still resumes
        # the project session. Only look up an entry when an id is supplied. This is what
        # lets the patron reply when nothing is open (the sweep leaves no current file).
        entry = None
        eid = d.get("id")
        if eid:
            q = load_queue(proj)
            entry = find_entry(q, eid)
            # tell the agent "now looking at <path>" only when the active file changed —
            # not re-told on every turn within the same file (the session carries it once
            # announced)
            switched = entry["id"] != sess.get("last_entry")
            if not sid or switched:
                message = CONTEXT_BLOCK.format(
                    path=entry["path"],
                    brief=entry.get("brief", "(none prepared)"),
                    ask=entry.get("ask", "general review"),
                ) + message

        cmd = [CLAUDE, "-p", message, "--output-format", "stream-json", "--verbose"]
        model = d.get("model")
        if model and model != "default":
            cmd += ["--model", model]
        if sid:
            cmd += ["--resume", sid]
        else:  # first-ever turn on this project: create the named project session
            role = proj.get("role") or DEFAULT_ROLE
            sysprompt = role.format(
                path=(entry["path"] if entry else "(no file selected)"),
                project=proj["name"],
                brief=(entry.get("brief", "(none prepared)") if entry else "(none prepared)"),
                ask=(entry.get("ask", "general review") if entry else "general review"),
            )
            handbook = base_handbook()
            if handbook:
                sysprompt += "\n\n" + handbook
            orientation = project_orientation(proj)
            if orientation:
                sysprompt += "\n\n" + orientation
            kit_ctx = kits.as_context(
                kits.for_project(proj, APPDIR / "kits", load_settings()), "review")
            if kit_ctx:
                sysprompt += "\n\n" + kit_ctx
            sc = scope_note(proj)
            if sc:
                sysprompt += "\n\n" + sc
            cmd += ["--append-system-prompt", sysprompt, "--name", session_name(proj)]
        cmd += AGENT_TOOLS

        # record the active file (only when an entry is in play) so a same-file follow-up
        # won't re-inject context; the session_id is persisted by run_claude's init hook below
        if entry:
            save_session(proj, last_entry=entry["id"], name=session_name(proj))
        else:
            save_session(proj, name=session_name(proj))

        def persist(new_sid):
            save_session(proj, session_id=new_sid)

        self.run_claude(cmd, str(project_root(proj)), prior_sid=sid, persist=persist,
                        record_user_message=d["message"], role="review-agent")

    def compact(self, d):
        """Run /compact on the project session: summarize-and-continue in place. The
        session_id is unchanged, so the thread survives — only its context shrinks. The
        compact turn's own usage reflects the pre-compaction size, so the client does not
        drive the context bar from it; the bar refreshes on the next real chat turn."""
        proj = get_project(d.get("project"))
        sid = load_session(proj).get("session_id")
        if not sid:
            self.run_claude(["true"], str(project_root(proj)))  # no session: emit clean stream, no-op
            return
        cmd = [CLAUDE, "-p", "/compact", "--output-format", "stream-json", "--verbose",
               "--resume", sid]
        model = d.get("model")
        if model and model != "default":
            cmd += ["--model", model]
        cmd += AGENT_TOOLS
        self.run_claude(cmd, str(project_root(proj)), prior_sid=sid)

    def sweep(self, d):
        proj = get_project(d.get("project"))
        ledger = proj.get("ledger") or "(no ledger configured — queue/approvals only)"
        prompt = SWEEP_PROMPT.format(
            name=proj["name"], root=str(project_root(proj)),
            ledger=str(Path(ledger).expanduser()) if ledger.startswith("~") or ledger.startswith("/") else ledger,
            desk_dir=str(desk_dir(proj)), runtime_dir=str(runtime_dir(proj)),
            today=date.today().isoformat(),
            stamp=datetime.now().strftime("%Y-%m-%d-%H%M%S"),
            queue_path=str(queue_path(proj)),
        )
        handbook = base_handbook()
        if handbook:
            prompt += "\n\n" + handbook
        orientation = project_orientation(proj)
        if orientation:
            prompt += "\n\n" + orientation
        kit_ctx = kits.as_context(
            kits.for_project(proj, APPDIR / "kits", load_settings()), "sweep")
        if kit_ctx:
            prompt += "\n\n" + kit_ctx
        intake = intake_paths(proj)
        if intake:
            _, _, outbound = intake
            prompt += (
                "\n\nINTAKE OUTBOUND — this is an inbox project; its queue is refilled by the live "
                "intake pass (a folder-watch), NOT by review-program.md. An APPROVED entry is itself "
                "a reason to sweep: do NOT apply the step-2a no-op stop while any approved entry still "
                "awaits staging, even if its draft is byte-identical to its snapshot (the patron may "
                "approve a draft as written). Override step 7 RESTOCK "
                "accordingly: do NOT load any next batch and do NOT treat a missing review program as "
                "'exhausted' or empty the queue. Instead, for each APPROVED entry: STAGE its draft "
                f"(the entry's `path`) to the outbound folder {outbound} (create it on first use) by "
                "copying the file there so an out-of-band tool can pick it up to send, then archive "
                "that entry to the batch file and delete its snapshot. LEAVE all pending and rework "
                "entries in the queue untouched — intake keeps refilling around them. NEVER transmit "
                "anything yourself — staging only (localhost is the fence). Record in the session log "
                "which drafts you staged. The `source` items are read-only and never moved.")
        sc = scope_note(proj)
        if sc:
            prompt += "\n\n" + sc
        # the curator's steer: the last thing they entered before starting the sweep, so the
        # thing most on their mind. It leads the prompt — the first thing the agent reads —
        # and sets the emphasis of the whole pass.
        thrust = str(d.get("thrust") or "").strip()
        if thrust:
            quoted = "\n".join("> " + ln for ln in thrust.splitlines())
            prompt = ("The curator's steer for this sitting — read it first; let it shape where "
                      "you press hardest as you close the desk:\n\n" + quoted + "\n\n— · —\n\n" + prompt)
        cmd = [CLAUDE, "-p", prompt, "--output-format", "stream-json", "--verbose"]
        model = d.get("model")
        if model and model != "default":
            cmd += ["--model", model]
        # resume the project session for continuity across the sitting; if none exists
        # yet, run fresh under the project name and persist the session it creates
        sid = load_session(proj).get("session_id")
        if sid:
            cmd += ["--resume", sid]
        else:
            cmd += ["--name", session_name(proj)]
        cmd += SWEEP_TOOLS

        def persist(new_sid):
            save_session(proj, session_id=new_sid, name=session_name(proj))

        self.run_claude(cmd, str(project_root(proj)), prior_sid=sid, persist=persist,
                        role="sweep")

    # ---- add project: registry append + desk seed ----
    def add_project(self, d):
        # registration logic (validation, fence gate, registry append, desk seed) lives in
        # the module-level register_project so the CLI shares it; here we only translate.
        try:
            proj = register_project(d.get("name", ""), d.get("root", ""),
                                    d.get("kit"), d.get("max_depth"))
        except ValueError as e:
            self.send_json({"error": str(e)}, 400)
            return
        note = str(d.get("note") or "").strip()
        if note:                       # the patron's founding steer → woven into the charter at found
            save_session(proj, founding_note=note)
        self.send_json({**proj, "home": str(HOME)})

    # ---- reset a desk to its founding seed so the interview reruns ----
    def refound_project(self, d):
        try:
            proj = get_project(str(d.get("id", "")).strip())
        except KeyError:
            self.send_json({"error": f"no such project: {d.get('id')}"}, 400)
            return
        self.send_json(refound_desk(proj))

    # ---- curator kits: save (fork-on-edit / create) and delete a user kit ----
    def save_kit(self, d):
        key = str(d.get("key") or "").strip()
        kit = d.get("kit")
        if not key or not isinstance(kit, dict):
            self.send_json({"error": "key and kit object required"}, 400)
            return
        ks = dict(load_settings().get("kits") or {})
        ks[key] = kit                            # user layer; shipped kits/*.json stay pristine
        save_settings({"kits": ks})
        self.send_json({"kits": kits.list_kits(APPDIR / "kits", load_settings()),
                        "kinds": kits.KINDS})

    def delete_kit(self, d):
        key = str(d.get("key") or "").strip()
        ks = dict(load_settings().get("kits") or {})
        ks.pop(key, None)                        # only the user override/custom; default returns
        save_settings({"kits": ks})
        self.send_json({"kits": kits.list_kits(APPDIR / "kits", load_settings()),
                        "kinds": kits.KINDS})

    # ---- remove a project from the registry (unregister only — files left on disk) ----
    def delete_project(self, d):
        pid = str(d.get("id", "")).strip()
        with PROJECTS_LOCK:
            data = json.loads(PROJECTS_PATH.read_text())
            before = len(data["projects"])
            data["projects"] = [p for p in data["projects"] if p["id"] != pid]
            if len(data["projects"]) == before:
                self.send_json({"error": f"no such project: {pid}"}, 400)
                return
            atomic_write(PROJECTS_PATH, json.dumps(data, indent=2, ensure_ascii=False))
        # the project's files and its .setsweep desk are intentionally left untouched
        self.send_json({"projects": load_projects(), "home": str(HOME)})

    # ---- edit a project's name / root (id stays fixed; a moved root repoints the queue) ----
    def edit_project(self, d):
        pid = str(d.get("id", "")).strip()
        name = str(d.get("name", "")).strip()
        root_raw = str(d.get("root", "")).strip()
        if not name:
            self.send_json({"error": "name required"}, 400)
            return
        if not root_raw:
            self.send_json({"error": "folder required"}, 400)
            return
        try:
            rp = Path(root_raw).expanduser().resolve()
        except (OSError, RuntimeError):
            self.send_json({"error": f"cannot resolve folder: {root_raw}"}, 400)
            return
        if not rp.is_dir():
            self.send_json({"error": f"folder does not exist (or is not a directory): {rp}"}, 400)
            return
        if not rp.is_relative_to(HOME.resolve()):
            self.send_json({"error": f"folder must be under {HOME}"}, 400)
            return
        root_clean = root_raw.rstrip("/") or root_raw
        with PROJECTS_LOCK:
            data = json.loads(PROJECTS_PATH.read_text())
            proj = next((p for p in data["projects"] if p["id"] == pid), None)
            if not proj:
                self.send_json({"error": f"no such project: {pid}"}, 400)
                return
            proj["name"] = name
            proj["root"] = root_clean
            if "kit" in d:                       # assign/reassign (empty string → unassign)
                kit = str(d.get("kit") or "").strip()
                if kit:
                    proj["kit"] = kit
                else:
                    proj.pop("kit", None)
            if "max_depth" in d:                 # set scope bound (0 / blank → unbounded)
                try:
                    depth = int(d.get("max_depth") or 0)
                except (TypeError, ValueError):
                    depth = 0
                if depth >= 1:
                    proj["max_depth"] = depth
                else:
                    proj.pop("max_depth", None)
            # queue path is derived at runtime; do not store it in the registry
            proj.pop("queue", None)
            atomic_write(PROJECTS_PATH, json.dumps(data, indent=2, ensure_ascii=False))
        self.send_json({"projects": load_projects(), "home": str(HOME)})

    # ---- bootstrap: the founding curator surveys, programs, and fills the first queue ----
    def bootstrap(self, d):
        proj = get_project(d.get("project"))
        prompt = BOOTSTRAP_PROMPT.format(
            name=proj["name"], root=str(project_root(proj)),
            desk_dir=str(desk_dir(proj)), queue_path=str(queue_path(proj)),
        )
        cmd = [CLAUDE, "-p", prompt, "--output-format", "stream-json", "--verbose"]
        model = d.get("model")
        if model and model != "default":
            cmd += ["--model", model]
        cmd += SWEEP_TOOLS  # write powers, confined by cwd + acceptEdits to the project tree
        self.run_claude(cmd, str(project_root(proj)))
        mark_founded_if_filed(proj)  # founded iff the curator filed entries (shared rule, as in found())

    # ---- the founding interview: read-only survey + conversation (center panel) ----
    def interview(self, d):
        proj = get_project(d.get("project"))
        sid = load_session(proj).get("session_id")
        message = str(d.get("message") or "").strip() or INTERVIEW_KICKOFF
        cmd = [CLAUDE, "-p", message, "--output-format", "stream-json", "--verbose"]
        model = d.get("model")
        if model and model != "default":
            cmd += ["--model", model]
        if sid:
            cmd += ["--resume", sid]
        else:  # first turn creates the named project session (read-only this phase)
            role = INTERVIEW_ROLE.format(name=proj["name"], root=str(project_root(proj)))
            note = (load_session(proj).get("founding_note") or "").strip()
            if note:
                role += ("\n\nThe patron left a founding note — project-specific quirks and needs "
                         "to honor; weave them into your questions and into the charter:\n" + note)
            sc = scope_note(proj)
            if sc:
                role += "\n\n" + sc
            cmd += ["--append-system-prompt", role, "--name", session_name(proj)]
        cmd += INTERVIEW_TOOLS

        def persist(new_sid):
            save_session(proj, session_id=new_sid, status="interviewing",
                         name=session_name(proj))

        self.run_claude(cmd, str(project_root(proj)), prior_sid=sid, persist=persist)

    # ---- finish: the curator founds the desk with write tools, in the same session ----
    def found(self, d):
        proj = get_project(d.get("project"))
        sid = load_session(proj).get("session_id")
        if sid:  # continue the SAME interview session, now with write tools
            prompt = FOUND_PROMPT.format(
                name=proj["name"], root=str(project_root(proj)),
                desk_dir=str(desk_dir(proj)), queue_path=str(queue_path(proj)))
        else:  # no interview happened (API caller / skipped): one-shot founding
            prompt = BOOTSTRAP_PROMPT.format(
                name=proj["name"], root=str(project_root(proj)),
                desk_dir=str(desk_dir(proj)), queue_path=str(queue_path(proj)))
        kit_ctx = kits.as_context(
            kits.for_project(proj, APPDIR / "kits", load_settings()), "found")
        if kit_ctx:
            prompt += "\n\n" + kit_ctx
        note = (load_session(proj).get("founding_note") or "").strip()
        if note:
            prompt += ("\n\nPatron's founding note (project-specific quirks and needs to honor in "
                       "the charter and the first queue):\n" + note)
        sc = scope_note(proj)
        if sc:
            prompt += "\n\n" + sc
        cmd = [CLAUDE, "-p", prompt, "--output-format", "stream-json", "--verbose"]
        model = d.get("model")
        if model and model != "default":
            cmd += ["--model", model]
        if sid:
            cmd += ["--resume", sid]
        else:
            cmd += ["--name", session_name(proj)]
        cmd += SWEEP_TOOLS  # write powers, confined by cwd + acceptEdits

        def persist(new_sid):
            save_session(proj, session_id=new_sid, status="interviewing",
                         name=session_name(proj))

        self.run_claude(cmd, str(project_root(proj)), prior_sid=sid, persist=persist,
                        role="founding-curator")
        mark_founded_if_filed(proj)  # founded iff the curator filed entries (shared rule)

    def run_claude(self, cmd, cwd, prior_sid=None, persist=None, record_user_message=None,
                   role="agent"):
        """Spawn claude headless; forward normalized events as ndjson to the client.

        Stream parsing, usage accounting, and transcript capture live in `runtime.py` —
        the viewport-neutral adapter any future CLI viewport drives too. This method is the
        HTTP/process glue: own the response, forward each normalized event, map the init
        session-id to the caller's `persist` hook, and (when `record_user_message` is set)
        append the turn to the desk's own ledger at `<root>/.setsweep/sessions/<id>.jsonl`
        — so continuity is the desk's, not the agent process's. Event shapes are unchanged
        (model/text/tool/done/error); `usage` is additive and ignored by older frontends;
        `done.ctx` is now true single-call occupancy, not the turn's summed aggregate."""
        self.send_response(200)
        self.send_header("Content-Type", "application/x-ndjson; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()

        # stderr merged into stdout: a second unread pipe can deadlock claude mid-stream
        proc = subprocess.Popen(
            cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
        )
        assert proc.stdout is not None
        meter = runtime.UsageMeter()
        cap = {"sid": prior_sid, "text": [], "tools": [], "edits": []}

        def on_session(new_sid):
            cap["sid"] = new_sid
            if persist and new_sid and new_sid != prior_sid:
                persist(new_sid)  # immediately, so a fast next turn finds the session

        try:
            for evt in runtime.normalize(proc.stdout, meter, on_session):
                if evt["t"] == "text":
                    cap["text"].append(evt["s"])
                elif evt["t"] == "tool":
                    cap["tools"].append(evt["s"])
                    if evt.get("tool") in lineage.WRITE_TOOLS and evt.get("path"):
                        cap["edits"].append(evt["path"])
                if not self.stream_line(evt):  # client gone
                    proc.kill()
                    break
            proc.wait(timeout=10)
            if proc.returncode not in (0, None, -9):
                self.stream_line({"t": "error", "s": f"claude exited {proc.returncode}"})
        except Exception as e:  # noqa: BLE001
            proc.kill()
            self.stream_line({"t": "error", "s": repr(e)})
        finally:
            if record_user_message is not None and cap["sid"]:
                try:
                    runtime.SessionLedger(Path(cwd) / ".setsweep" / "sessions").append_turn(
                        cap["sid"], "user", record_user_message,
                        agent_text="".join(cap["text"]), tools=cap["tools"],
                        usage=meter.snapshot())
                except OSError:
                    pass
            if cap["edits"]:                          # the agent's file edits self-record
                try:
                    lineage.log_agent_edits(cwd, cap["edits"], actor=role,
                                            session=cap["sid"] or "")
                except OSError:
                    pass
            if proc.poll() is None:
                proc.kill()


# ---------- entry points ----------

def start_server(port: int = 0) -> tuple[ThreadingHTTPServer, int]:
    """Start in a daemon thread; returns (server, bound_port)."""
    global SERVER_PORT, SERVER_STARTED
    srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    SERVER_PORT = srv.server_address[1]
    SERVER_STARTED = subprocess.run(["date", "+%Y-%m-%dT%H:%M:%S%z"],
                                    capture_output=True, text=True).stdout.strip()
    try:  # informational record of the bind (the ping is the authority)
        RUNTIME_PATH.parent.mkdir(parents=True, exist_ok=True)
        RUNTIME_PATH.write_text(json.dumps(
            {"pid": os.getpid(), "port": SERVER_PORT, "started": SERVER_STARTED}))
    except OSError:
        pass
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, SERVER_PORT


def _ping_setsweep(port: int, timeout: float = 0.8) -> dict | None:
    """Answer of /api/ping on the port iff it identifies as setsweep, else None."""
    try:
        with urllib.request.urlopen(
                f"http://127.0.0.1:{port}/api/ping", timeout=timeout) as r:
            j = json.loads(r.read())
            return j if j.get("app") == "setsweep" else None
    except Exception:  # noqa: BLE001 — closed port, timeout, non-JSON: all mean "not ours"
        return None


def _code_mtime() -> float:
    """Newest mtime among the files a running instance could be serving stale."""
    paths = [Path(__file__), Path(__file__).parent / "static" / "index.html"]
    return max((p.stat().st_mtime for p in paths if p.exists()), default=0.0)


def _predecessor_is_stale(info: dict) -> bool:
    """True iff the responding predecessor started BEFORE the current code — i.e. it
    is serving stale code/tab and may be retired. Missing/unparseable timestamp →
    treat as CURRENT (return False): the safe default is to defer, never to kill a
    live window we can't prove stale."""
    started = info.get("started")
    if not started:
        return False
    from datetime import datetime
    try:
        ts = datetime.fromisoformat(started).timestamp()      # py3.11+: handles -0400
    except (ValueError, TypeError):
        try:
            ts = datetime.strptime(started, "%Y-%m-%dT%H:%M:%S%z").timestamp()
        except (ValueError, TypeError):
            return False
    return ts < _code_mtime()


def _retire(pid: int) -> None:
    """SIGTERM with up to 2s grace, then SIGKILL."""
    try:
        os.kill(pid, signal.SIGTERM)
        for _ in range(20):
            time.sleep(0.1)
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                break
        else:
            os.kill(pid, signal.SIGKILL)
            time.sleep(0.2)
    except (ProcessLookupError, PermissionError):
        pass


def start_server_preferred(port: int = DEFAULT_PORT,
                           replace: bool = False) -> tuple[ThreadingHTTPServer, int] | None:
    """Claim the fixed port.

    Circuit-breaker (2026-06-13): a bare launch must NEVER kill a healthy, CURRENT
    predecessor — that turned every stray relaunch into the patron's window vanishing
    mid-sitting. We retire a responding setsweep predecessor ONLY if it is stale
    (started before the current code) or the launch is explicit (`--replace`).

    Returns:
      (server, port) — this process bound the port and is now serving.
      None           — a healthy current setsweep already holds the port; the caller
                       should defer (do not open a second window; do not kill anything).
    A foreign (non-setsweep) occupant → fall back to an ephemeral port (returns a tuple).
    We kill only a pid that ANSWERED our ping — never on the say-so of a stale state file.
    """
    info = _ping_setsweep(port)
    pid = info.get("pid") if info else None
    if pid and pid != os.getpid():
        if replace or _predecessor_is_stale(info or {}):
            _retire(pid)
        else:
            return None  # healthy current instance — defer, leave the live window alone
    try:
        return start_server(port)
    except OSError:
        return start_server(0)


def main():
    global SERVER_PORT
    port = DEFAULT_PORT
    args = sys.argv[1:]
    if "--port" in args:
        port = int(args[args.index("--port") + 1])
    srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    SERVER_PORT = srv.server_address[1]
    url = f"http://127.0.0.1:{port}/"
    print(f"desk · {url}\nprojects: {PROJECTS_PATH}")
    if "--no-open" not in args:
        threading.Timer(0.4, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nbye")


if __name__ == "__main__":
    main()
