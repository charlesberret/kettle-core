#!/usr/bin/env python3
"""desk — three-pane review server: agent-curated queue · plaintext editor · review agent.

Multi-project: the registry at projects.json maps project ids to a root (the agent's
working directory) and a queue file (<root>/.kettle/queue.json by convention). The
right-pane agent is the active curator CLI in headless mode (Claude: stream-json;
Grok Build CLI: streaming-json), run in the active project's root with
Read/Glob/Grep/Edit/Write under acceptEdits (project-fenced);
founding interview is tool-less (core survey snapshot) until finish drafts
DESK-PROPOSAL.md; approve of that entry runs the write-armed found. Each queue
entry's curatorial brief is injected as system-prompt context so the agent starts
aligned without re-reading the file.

Run standalone (web mode):  python3 server.py [--port 4242] [--no-open]
Bundled (Electron .app):     PyInstaller sidecar; set DESK_PROJECTS for the registry path.
"""

import base64
import difflib
import hashlib
import json
import math
import os
import hmac
import queue
import re
import secrets
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
import webbrowser
from datetime import date, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from . import kits     # curator kits: the per-kind playbook (lens · urgency · first-queue · sweep checks)
from . import lineage  # who-edited-what: agent edits self-record to the desk's working record
from . import runtime  # viewport-neutral agent adapter: spawn · usage normalizer · session ledger
from . import curator as curator_mod  # pluggable curator backends (claude CLI default)
from . import kettle_contract  # core/API/desk-schema identity for every viewport
from . import survey as survey_mod  # deterministic founding survey (tool-less interview Phase A)
from . import sweepkit  # mechanical sweep close-kit (status · archive · stage · thin log)
from . import theme_catalog  # bundled + user color theme packs (web, desktop, CLI)
from . import gitmap  # local git contribution heatmap (desk chrome; no network)

HOME = Path.home()


def _app_dir() -> Path:
    """Package data root (static/, kits/); PyInstaller extract dir when frozen.

    Uses importlib.resources.files() so wheel and editable installs resolve the
    same package tree. Callers still receive a concrete Path for read/glob APIs.
    """
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    package_dir = Path(__file__).resolve().parent
    try:
        from importlib.resources import files

        root = files(__package__ or "kettle")
        # On-disk packages (editable + extracted wheels): files() sees static/kits;
        # Path(__file__).parent is that same directory for Path-based callers.
        if root.joinpath("static").is_dir() or root.joinpath("kits").is_dir():
            return package_dir
    except (ModuleNotFoundError, TypeError, OSError, AttributeError):
        pass
    return package_dir


APPDIR = _app_dir()
STATIC = APPDIR / "static"


def user_projects_path() -> Path:
    """Platform user-data registry — same location desktop uses on macOS."""
    if sys.platform == "darwin":
        return HOME / "Library/Application Support/Kettle/projects.json"
    xdg = os.environ.get("XDG_CONFIG_HOME")
    base = Path(xdg).expanduser() if xdg else HOME / ".config"
    return base / "kettle" / "projects.json"


def legacy_user_projects_path() -> Path:
    """Pre-Kettle registry location, read during the rename transition."""
    if sys.platform == "darwin":
        return HOME / "Library/Application Support/Setsweep/projects.json"
    xdg = os.environ.get("XDG_CONFIG_HOME")
    base = Path(xdg).expanduser() if xdg else HOME / ".config"
    return base / "setsweep" / "projects.json"


def resolve_projects_path() -> Path:
    """Choose the live projects.json so CLI and desktop can share one desk.

    1. `$DESK_PROJECTS` — explicit override (tests, desktop sidecar, power users)
    2. User registry if it already exists (Application Support / XDG)
    3. Existing legacy Setsweep user registry (read/write in place; no split state)
    4. Repo-local `APPDIR/projects.json` if present (dev checkout)
    5. Otherwise the Kettle user path (first write creates the shared registry)
    """
    env = os.environ.get("DESK_PROJECTS")
    if env:
        return Path(env).expanduser()
    user = user_projects_path()
    if user.exists():
        return user
    legacy = legacy_user_projects_path()
    if legacy.exists():
        return legacy
    # Package dir (rare) or editable checkout repo root (parent of kettle/).
    for repo in (APPDIR / "projects.json", APPDIR.parent / "projects.json"):
        if repo.exists():
            return repo
    return user


PROJECTS_PATH = resolve_projects_path()
SETTINGS_PATH = PROJECTS_PATH.parent / "settings.json"
# Legacy constant — prefer current_curator().resolved_command() for new code.
CLAUDE = shutil.which("claude") or "claude"
_CLAUDE_AT_IMPORT = CLAUDE  # tests replace CLAUDE with a stub; agent_bin honors that
SERVER_PORT = None  # bound port, recorded at startup for the admin report
SERVER_STARTED = None  # ISO timestamp, set at bind
SERVER_TOKEN = None  # per-boot auth token; required on every /api/ request
DEFAULT_PORT = 4242  # one port for native app and web mode alike — a bookmarked
                     # tab always reaches the live server, never a stale orphan
RUNTIME_PATH = HOME / ".cache/kettle/server.json"  # discovery: port + token (mode 0600)
TOKEN_HEADER = "X-Kettle-Token"
_INLINE_SCRIPT_RE = re.compile(rb"<script(?![^>]*\bsrc=)[^>]*>(.*?)</script>", re.DOTALL | re.IGNORECASE)


def sitting_csp(body: bytes) -> str:
    """Content-Security-Policy for the served sitting.

    Scripts run only from this origin or as the exact inline blocks shipped in
    index.html (sha256-pinned per response, so editing the file needs no manual
    hash bump). Anything a rendered file or agent reply manages to inject — an
    <img onerror>, a <script>, a javascript: link — is refused by the browser even
    if the sanitizer misses it. Styles stay 'unsafe-inline' (the sitting uses style
    attributes); style injection cannot run code or read the token. Remote images are
    refused, so a document cannot beacon out when it is opened.
    """
    # Browsers normalize CRLF / lone CR to LF before hashing an inline script, so a
    # checkout with CRLF line endings must hash the normalized text or the sitting blanks.
    text = body.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    hashes = " ".join(
        "'sha256-" + base64.b64encode(hashlib.sha256(m.group(1)).digest()).decode() + "'"
        for m in _INLINE_SCRIPT_RE.finditer(text)
    )
    return "; ".join([
        "default-src 'self'",
        f"script-src 'self' {hashes}".rstrip(),
        "style-src 'self' 'unsafe-inline'",
        # No remote images: an <img> in a registered document would report the reader's
        # IP and the moment they opened it (a canary). Kettle never transmits.
        "img-src 'self' data:",
        "font-src 'self'",
        "connect-src 'self'",
        "object-src 'none'",
        "base-uri 'none'",
        "form-action 'none'",
        "frame-ancestors 'none'",
    ])
QUEUE_LOCK = threading.Lock()
SWEEPS_LOCK = threading.Lock()
SWEEPS_IN_FLIGHT: set[str] = set()  # project ids with a sweep stream open in this process
SETTINGS_LOCK = threading.Lock()
PROJECTS_LOCK = threading.Lock()
DEFAULT_CURATOR_IDLE_TIMEOUT_S = 300.0


def current_curator() -> curator_mod.CuratorConfig:
    return curator_mod.resolve_curator(load_settings())


def curator_idle_timeout_s() -> float:
    """Configured maximum silence between normalized curator events.

    Five minutes leaves ample room for ordinary provider-side tool work; every supported
    stream dialect emits model/text/tool/usage events when it is active. Tests shorten the
    setting. Invalid, non-positive, and non-finite values fall back safely.
    """
    settings = load_settings()
    block = settings.get("curator") if isinstance(settings.get("curator"), dict) else {}
    raw = block.get("idle_timeout_s", DEFAULT_CURATOR_IDLE_TIMEOUT_S)
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return DEFAULT_CURATOR_IDLE_TIMEOUT_S
    if not math.isfinite(value) or value <= 0:
        return DEFAULT_CURATOR_IDLE_TIMEOUT_S
    return max(0.05, min(value, 86_400.0))


def agent_bin() -> str:
    """Executable for the active curator provider (default: claude on PATH).

    When settings still name the bare `claude` command, honor the module-level
    `CLAUDE` path so tests can stub it and so the import-time `which()` result
    stays authoritative until the user sets a custom curator.command.
    """
    cfg = current_curator()
    fallback = curator_mod.DEFAULT_COMMAND.get(cfg.provider, "claude")
    cmd = (cfg.command or fallback).strip() or fallback
    if cmd == "claude" and CLAUDE != _CLAUDE_AT_IMPORT:
        return CLAUDE
    # Resolve on every turn, like /api/ping and `kettle doctor`: installing the CLI
    # after launch works without a restart, and a missing CLI is reported by its own
    # name rather than an invented ~/.local/bin path.
    return cfg.resolved_command()


def with_model(cmd: list, task: str, request_model=None) -> list:
    """Append --model from request override or settings.curator.models[task]."""
    m = current_curator().model_for(task, request_model)
    if m:
        cmd += ["--model", m]
    return cmd


def build_turn_cmd(
    prompt: str,
    *,
    task: str,
    request_model=None,
    session_id: str | None = None,
    system_append: str | None = None,
    name: str | None = None,
    tools_tier: str | None = None,
    extra: list | None = None,
) -> list:
    """Dialect-aware headless argv for Claude / Grok / ChatGPT(Codex) / Gemini."""
    cfg = current_curator()
    model = cfg.model_for(task, request_model)
    effort = cfg.effort_for(task)

    class _Bin:
        provider = cfg.provider
        effort = cfg.effort
        def resolved_command(self):
            return agent_bin()

    return runtime.build_argv(
        _Bin(), prompt,
        session_id=session_id,
        system_append=system_append,
        session_name=name,
        tools_tier=tools_tier,
        model=model,
        effort=effort,
        extra=extra,
    )


READ_ONLY_UNAVAILABLE = "read_only_unavailable"


def read_only_capability_error() -> dict | None:
    """Pre-stream guard for shell-bearing *read-only* tiers (legacy / optional callers).

    Founding interview is tool-less (core survey + empty allowlist) for every provider, so
    ``/api/interview`` no longer calls this. Kept for callers that still request a
    shell-bearing read-only posture: when the active provider cannot guarantee it, REFUSE
    unless ``curator.allow_unfenced_readonly: true``. Returns an error dict, or None to allow.
    """
    settings = load_settings()
    cfg = curator_mod.resolve_curator(settings)
    if runtime.guarantees_read_only(cfg.provider):
        return None
    block = settings.get("curator") if isinstance(settings.get("curator"), dict) else {}
    if bool(block.get("allow_unfenced_readonly")):
        return None
    label = curator_mod.PROVIDER_LABEL.get(cfg.provider, cfg.provider)
    return {
        "error": READ_ONLY_UNAVAILABLE,
        "provider": cfg.provider,
        "message": (
            f"This turn needs a read-only tool tier, but the active curator ({label}) "
            f"cannot guarantee one — its explore mode still permits shell and writes. "
            f"Switch to a provider that fences read-only (claude, chatgpt, or gemini), "
            f"or set curator.allow_unfenced_readonly: true to proceed anyway."
        ),
        "options": [
            "switch curator.provider to claude, chatgpt, or gemini",
            "set curator.allow_unfenced_readonly: true to acknowledge the downgrade",
        ],
    }


def read_only_downgrade_notice() -> str | None:
    """When a read-only turn proceeds only because allow_unfenced_readonly is set, the
    stream should say so. Returns the notice text, or None when no downgrade is in effect."""
    settings = load_settings()
    cfg = curator_mod.resolve_curator(settings)
    if runtime.guarantees_read_only(cfg.provider):
        return None
    block = settings.get("curator") if isinstance(settings.get("curator"), dict) else {}
    if not bool(block.get("allow_unfenced_readonly")):
        return None
    label = curator_mod.PROVIDER_LABEL.get(cfg.provider, cfg.provider)
    return (
        f"[read-only downgrade] {label} cannot fence this turn to read-only; proceeding "
        f"because curator.allow_unfenced_readonly is set. The curator may run shell/writes."
    )


CHATLOG_LOCK = threading.Lock()
CHATLOG_CAP = 500  # server-side cap: most recent N messages kept per project


def _env_allowed_roots() -> list[Path]:
    """Extra base roots for the file fence.

    ``KETTLE_ALLOWED_ROOTS`` is authoritative. The former
    ``SETSWEEP_ALLOWED_ROOTS`` remains a read-side fallback during migration.
    Default (unset) = empty: the fence is exactly the registered project roots, each gated under
    $HOME at registration. Set this to widen it — e.g. a notes vault whose `[[wikilinks]]` cross
    project boundaries: `KETTLE_ALLOWED_ROOTS="$HOME/Notes:$HOME/Vault"`."""
    out: list[Path] = []
    raw = os.environ.get("KETTLE_ALLOWED_ROOTS")
    if raw is None:
        raw = os.environ.get("SETSWEEP_ALLOWED_ROOTS", "")
    for part in raw.split(os.pathsep):
        part = part.strip()
        if part:
            try:
                out.append(Path(part).expanduser().resolve())
            except (OSError, RuntimeError):
                continue
    return out


# The fence = these base roots + every registered project root (see allowed_roots()). Base
# defaults to empty for portability; the author can restore prior behavior with, e.g.,
# KETTLE_ALLOWED_ROOTS="$HOME/cloud/sync:$HOME/Library/Mobile Documents/com~apple~CloudDocs".
BASE_ALLOWED_ROOTS = _env_allowed_roots()

# Tool tiers (agent / chat / sweep / interview) are single-sourced in
# runtime.TOOL_TIERS and mapped to each provider's dialect by runtime.tools_argv.
# Every turn — HTTP routes and the CLI alike — resolves them through build_turn_cmd
# (→ runtime.build_argv). The old duplicate server-side flag constants were removed.

PROMPTS_DIR = APPDIR / "kits" / "prompts"


def _load_prompt(name: str, fallback: str) -> str:
    """Read one product prompt at import; missing files degrade to a short safe prompt."""
    path = PROMPTS_DIR / name
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        print(
            f"kettle: prompt file {path} unavailable ({exc}); using emergency fallback",
            file=sys.stderr,
        )
        return fallback
    # Prompt files carry one conventional final newline that is not part of the prompt.
    return text[:-1] if text.endswith("\n") else text


ACCRUE_PROMPT = _load_prompt(
    "accrue.md",
    "Accrue and restock {name} at {root}. Update {queue_path} and {desk_dir}; "
    "record the result in {session_log}.",
)
REFRESH_BRIEFS_PROMPT = _load_prompt(
    "refresh-briefs.md",
    "Rewrite cold-re-entry briefs and asks for every entry in {queue_path} "
    "for {name} at {root} (desk {desk_dir}). Do not restock or archive.",
)
SWEEP_PROMPT = _load_prompt(
    "sweep.md",
    "Review and sweep {name} at {root}. Use {ledger}; maintain {desk_dir}, "
    "{runtime_dir}, and {queue_path} for {today} ({stamp}).",
)

# Live stream narration during /api/sweep. Default is normal (more talkative than the
# historical quiet default). Stored in settings.json as sweepVerbosity.
SWEEP_VERBOSITY_LEVELS = ("quiet", "normal", "verbose")
DEFAULT_SWEEP_VERBOSITY = "normal"
SWEEP_VERBOSITY_INSTRUCTIONS = {
    level: _load_prompt(
        f"sweep-verbosity-{level}.md",
        f"LIVE REPORTING — {level}: report meaningful progress and finish with a recap.",
    )
    for level in SWEEP_VERBOSITY_LEVELS
}


def normalize_sweep_verbosity(raw) -> str:
    """quiet | normal | verbose — default normal (more talkative than the old terse sweep)."""
    v = str(raw or "").strip().lower()
    aliases = {
        "terse": "quiet",
        "minimal": "quiet",
        "min": "quiet",
        "standard": "normal",
        "default": "normal",
        "detailed": "verbose",
        "full": "verbose",
        "max": "verbose",
    }
    v = aliases.get(v, v)
    return v if v in SWEEP_VERBOSITY_LEVELS else DEFAULT_SWEEP_VERBOSITY


def sweep_verbosity_block(level: str | None = None) -> str:
    """Instruction block appended to the sweep / accrue prompt."""
    lvl = normalize_sweep_verbosity(level)
    return SWEEP_VERBOSITY_INSTRUCTIONS[lvl]


FOUNDING_LIVE_REPORTING = _load_prompt(
    "founding-live-reporting.md",
    "Report meaningful founding progress as you work and finish with a short recap.",
)
QUEUE_SCHEMA = _load_prompt(
    "queue-schema.md",
    "Queue entries need id, title, absolute path, project, ask_type, ask, urgency, "
    "status=pending, and an honest brief.",
)
BOOTSTRAP_PROMPT = _load_prompt(
    "bootstrap.md",
    "Found the {name} desk at {root}: write concise apparatus under {desk_dir} and "
    "populate {queue_path} with honest review entries.",
)

# ---- the founding interview (agent chat, multi-turn) ----
# Phase A (survey): core builds a deterministic snapshot (survey.py) — no curator tools.
# Phase B (interview): tool-less curator conversation (one mission question; no card).
# Phase C (finish → propose): write ONE DESK-PROPOSAL.md and queue it for the editor.
# Phase D (approve proposal → found): digest the *edited* proposal, write the desk, first batch.
PROPOSAL_ENTRY_ID = "desk-proposal"
PROPOSAL_FILENAME = "DESK-PROPOSAL.md"

INTERVIEW_ROLE = _load_prompt(
    "interview-role.md",
    "Interview the user to found the {name} desk at {root}. Survey read-only, ask only "
    "what the files cannot answer, and explain that approval is the founding gate.",
)
INTERVIEW_KICKOFF = _load_prompt(
    "interview-kickoff.md",
    "Survey the project, summarize it plainly, and begin the founding interview.",
)
PROPOSE_PROMPT = _load_prompt(
    "propose.md",
    "Draft only the editable desk proposal for {name} at {proposal_path}, then put one "
    "pending proposal entry in {queue_path}. Do not found the full desk yet.",
)
FOUND_PROMPT = _load_prompt(
    "found.md",
    "Read the approved proposal at {proposal_path}, then found the {name} desk at {root}: "
    "write apparatus under {desk_dir} and populate {queue_path}.",
)
FOUND_LEGACY_PROMPT = _load_prompt(
    "found-legacy.md",
    "Found the {name} desk at {root} from the interview and files; write apparatus under "
    "{desk_dir} and populate {queue_path}.",
)
DEFAULT_ROLE = _load_prompt(
    "default-role.md",
    "Help the user review {path} in {project}. Use this brief: {brief}. The ask is: {ask}.",
)
CONTEXT_BLOCK = _load_prompt(
    "context-block.md",
    "[Active file: {path}]\n[Curatorial brief] {brief}\n[The ask] {ask}\n\n",
)


EMPTY_QUEUE = {"curated": "empty — entries are filed by curating agents", "entries": []}


# ---------- projects ----------

def read_projects_registry() -> dict:
    """Load the on-disk registry; missing or invalid file → empty projects list."""
    try:
        if not PROJECTS_PATH.exists():
            return {"projects": []}
        data = json.loads(PROJECTS_PATH.read_text())
    except (OSError, json.JSONDecodeError):
        return {"projects": []}
    if not isinstance(data, dict):
        return {"projects": []}
    data.setdefault("projects", [])
    return data


def load_projects() -> list[dict]:
    data = read_projects_registry()
    # presented alphabetically by name (case-insensitive); write paths read raw JSON,
    # so the on-disk order/`note` are untouched. No project is pinned to the top.
    return sorted(data["projects"], key=lambda p: p.get("name", "").lower())


def get_project(pid: str | None) -> dict:
    """Resolve a registered project by id.

    `project` is required on project-scoped HTTP routes — omitting it used to
    silently target the first registry entry (dangerous for multi-project
    viewports). Pass an explicit id; raise KeyError if missing or unknown.
    """
    if not pid:
        raise KeyError("missing project")
    for pr in load_projects():
        if pr["id"] == pid:
            return pr
    raise KeyError(f"unknown project: {pid}")


def want_mutate(qs: dict) -> bool:
    """Whether a GET may run healing/snapshot side effects (default: yes).

    Pass `?mutate=0` (or false/no) for a pure read — useful for plugin polling.
    """
    raw = (qs.get("mutate", ["1"])[0] or "1").strip().lower()
    return raw not in ("0", "false", "no", "off")


def project_root(proj: dict) -> Path:
    return Path(proj["root"]).expanduser().resolve()


def git_commit_activity(root: Path, weeks: int = 26) -> dict:
    """Delegate to :mod:`gitmap` (kept as a server-facing name for tests/callers)."""
    return gitmap.git_commit_activity(root, weeks=weeks)


def desk_dir(proj: dict) -> Path:
    """Resolve one durable desk without creating parallel state.

    Prefer ``.kettle``. If it does not exist, keep using an existing
    ``.setsweep`` desk until the user runs an explicit migration. New projects
    always receive ``.kettle``.
    """
    root = project_root(proj)
    current = root / ".kettle"
    legacy = root / ".setsweep"
    if current.exists() or not legacy.exists():
        return current
    return legacy


def intake_paths(proj: dict):
    """(watch, responses, outbound) resolved for an inbox project's `intake` block, or None.
    Mirrors kettle-watch.resolve_intake: `watch` may be a folder, '.', or a subdir; relatives
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
    sessions) that must NOT sync. Kept INSIDE the project at <root>/.kettle/runtime/
    so they stay within the review agent's project-root fence (no out-of-sandbox
    --add-dir needed). If you sync the project tree (Dropbox/iCloud/etc.), exclude
    `.kettle/runtime/` at the sync layer (e.g. a `seafile-ignore.txt`) so the daemon
    doesn't race these rapid rewrites. The durable desk files stay in desk_dir() and sync
    normally. (A sync idiosyncrasy is fixed at the sync layer, not by moving state outside
    the sandbox.)"""
    desk = desk_dir(proj)
    d = desk / "runtime"
    root = project_root(proj).resolve()
    for candidate in (desk, d):
        if candidate.is_symlink() and not candidate.resolve().is_relative_to(root):
            # A registered folder that ships `.kettle -> ~/elsewhere` would move every
            # desk write (and the curator's) outside the project fence.
            raise ValueError(f"desk directory {candidate} is a symlink leading outside "
                             f"the project ({candidate.resolve()}) — refusing to use it")
    d.mkdir(parents=True, exist_ok=True)
    return d


def queue_path(proj: dict) -> Path:
    rd = runtime_dir(proj)
    return rd / "queue.json"


def comments_log_path(proj: dict) -> Path:
    return runtime_dir(proj) / "comments.log"


# A comments.log line whose text is `[kettle:closed through N]` retires that entry's
# comments on physical lines < N. The log stays append-only; a sweep that consumed the
# comments (or a user clearing a note) appends the marker instead of editing lines, so a
# file that returns to the queue later does not replay settled direction.
_COMMENTS_CLOSED_RE = re.compile(r"^\[kettle:closed through (\d+)\]$")


def parse_comments_log(path: Path) -> dict[str, list[dict[str, str]]]:
    """Parse runtime/comments.log → entry-id → [{date, text}, …] (append order preserved).

    Comments retired by a close marker are omitted."""
    out: dict[str, list[dict]] = {}
    if not path.is_file():
        return out
    for idx, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines()):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split("\t", 2)
        if len(parts) < 3:
            continue
        entry_id, text = parts[1].strip(), parts[2].strip()
        if not (entry_id and text):
            continue
        m = _COMMENTS_CLOSED_RE.match(text)
        if m:
            through = int(m.group(1))
            kept = [r for r in out.get(entry_id, []) if r["_line"] >= through]
            if kept:
                out[entry_id] = kept
            else:
                out.pop(entry_id, None)
            continue
        out.setdefault(entry_id, []).append({"date": parts[0].strip(), "text": text, "_line": idx})
    return {eid: [{"date": r["date"], "text": r["text"]} for r in rows]
            for eid, rows in out.items()}


def comments_log_line_count(proj: dict) -> int:
    """Physical line count of comments.log — the `through` bound for a close marker."""
    path = comments_log_path(proj)
    try:
        return len(path.read_text(encoding="utf-8", errors="replace").splitlines())
    except FileNotFoundError:
        return 0


def close_comments(proj: dict, entry_ids, through: int | None = None) -> None:
    """Retire comments for entry_ids written before line `through` (default: all so far)."""
    ids = [str(i) for i in entry_ids if str(i or "").strip()]
    if not ids:
        return
    bound = comments_log_line_count(proj) if through is None else int(through)
    ts = date.today().isoformat()
    with comments_log_path(proj).open("a", encoding="utf-8") as f:
        for eid in ids:
            f.write(f"{ts}\t{eid}\t[kettle:closed through {bound}]\n")


def enrich_queue_comments(proj: dict, q: dict) -> None:
    """Attach comment_history from comments.log to each queue entry (API response only)."""
    hist = parse_comments_log(comments_log_path(proj))
    for e in q.get("entries", []):
        eid = e.get("id")
        e["comment_history"] = list(hist.get(eid, [])) if eid else []


def sweep_user_comments_block(comments_map: dict[str, list[dict[str, str]]], entries: list[dict]) -> str:
    """Format user notes for queue entries — injected into the sweep prompt verbatim."""
    lines: list[str] = []
    for e in entries:
        eid = e.get("id")
        if not eid:
            continue
        texts = [r["text"] for r in comments_map.get(eid, [])]
        cur = str(e.get("comment") or "").strip()
        if cur and cur not in texts:
            texts.append(cur)
        if not texts:
            continue
        title = e.get("title") or Path(str(e.get("path") or eid)).name
        lines.append(f"Entry `{eid}` ({title}):")
        for t in texts:
            lines.append(f"- User comment for this entry: {t}")
        lines.append("")
    return "\n".join(lines).rstrip()


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
    """Read queue.json. Retries once on FileNotFoundError — the curator Write tool
    may briefly unlink/truncate the file while restocking after a sweep, and a
    concurrent /api/queue (viewport refresh) must not 404 the user for that race."""
    qp = queue_path(proj)
    with QUEUE_LOCK:
        for attempt in (0, 1):
            try:
                if not qp.exists():
                    qp.parent.mkdir(parents=True, exist_ok=True)
                    qp.write_text(json.dumps(EMPTY_QUEUE, indent=2))
                return json.loads(qp.read_text())
            except FileNotFoundError:
                if attempt == 0:
                    continue
                qp.parent.mkdir(parents=True, exist_ok=True)
                qp.write_text(json.dumps(EMPTY_QUEUE, indent=2))
                return json.loads(qp.read_text())
    return dict(EMPTY_QUEUE)


def mutate_queue(proj: dict, fn) -> dict:
    qp = queue_path(proj)
    with QUEUE_LOCK:
        try:
            q = json.loads(qp.read_text())
        except FileNotFoundError:
            qp.parent.mkdir(parents=True, exist_ok=True)
            q = dict(EMPTY_QUEUE)
        fn(q)
        atomic_write(qp, json.dumps(q, indent=2, ensure_ascii=False))
        return q


def project_orientation(proj: dict) -> str:
    """The curator's standing context, injected into every agent the app spawns:
    PROJECT.md (charter), MEMORY.md (user prefs / rulings), FAMILIARITY.md
    (project-centered expertise), SWEEP-ACTIONS.md (extra close-of-sitting work).
    Identity lives in these files, not in any one session: any fresh agent that reads
    them IS the curator."""
    desk = desk_dir(proj)
    sections = (
        ("PROJECT.md", 2500, "Project orientation (PROJECT.md, curator-maintained)"),
        ("MEMORY.md", 2000, "Curator memory (MEMORY.md — rulings already made and user "
                            "preferences already learned; honor these without re-asking)"),
        ("FAMILIARITY.md", 3000, "Project familiarity (FAMILIARITY.md — accrued map of this "
                                 "corpus: families, roles, paths, relationships, pitfalls; "
                                 "use it to write better briefs and deepen it when restocking)"),
        ("SWEEP-ACTIONS.md", 1500, "Sweep actions (SWEEP-ACTIONS.md — extra work after "
                                   "archive/restock: outbound stage, egress for dispatch, "
                                   "plaintext sitting logs, sheets, reporting. Never transmit "
                                   "mail/Slack/webhooks from the desk; stage or egress only)"),
    )
    parts = []
    for fname, cap, label in sections:
        try:
            text = (desk / fname).read_text(encoding="utf-8", errors="replace").strip()
        except OSError:
            continue
        if text:
            parts.append(f"{label}:\n{text[:cap]}")
    # Claude curator turns load settings from the user scope only (runtime.
    # CLAUDE_PROJECT_ISOLATION), which also stops the CLI reading the project's own
    # CLAUDE.md. Its conventions still matter to review, so carry the text — never its
    # hooks or settings — for every provider.
    try:
        conventions = (project_root(proj) / "CLAUDE.md").read_text(
            encoding="utf-8", errors="replace").strip()
    except OSError:
        conventions = ""
    if conventions:
        parts.append("Project instructions (the project's own CLAUDE.md — conventions for "
                     "agents working in this tree; text only):\n" + conventions[:4000])
    return "\n\n".join(parts)


def sweep_precomputed_context(proj: dict, entries: list) -> str:
    """Queue summary + unified diffs so the sweep curator skips N serial `diff -u` rounds."""
    if not entries:
        return "QUEUE + PRECOMPUTED DIFFS:\n(empty queue)\n"
    lines = ["QUEUE + PRECOMPUTED DIFFS (do not re-diff unless marked missing):\n"]
    for e in entries:
        eid = e.get("id", "?")
        path = e.get("path", "")
        status = e.get("status", "pending")
        ask = e.get("ask_type", "")
        comment = (e.get("comment") or "").strip()
        lines.append(f"### entry {eid}")
        lines.append(f"path: {path}")
        lines.append(f"status: {status}" + (f"  ask_type: {ask}" if ask else ""))
        if e.get("brief"):
            brief = str(e["brief"]).strip().replace("\n", " ")
            if len(brief) > 240:
                brief = brief[:237] + "…"
            lines.append(f"brief: {brief}")
        if comment:
            lines.append(f"queue.comment: {comment}")
        text = entry_diff_text(proj, e)
        if text:
            if len(text) > 4000:
                text = text[:4000] + "\n… [diff truncated]\n"
            lines.append("diff:")
            lines.append(text)
        else:
            sp = runtime_dir(proj) / "snapshots" / f"{eid}.orig"
            if sp.exists():
                lines.append("diff: (identical to snapshot)")
            else:
                lines.append("diff: (no snapshot — assess from file + brief if needed)")
        lines.append("")
    return "\n".join(lines)


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
    a deeper file the user points at can still be opened. '' when unbounded."""
    d = proj.get("max_depth")
    if not isinstance(d, int) or d < 1:
        return ""
    detail = ("only files directly in the root folder" if d == 1
              else f"the root folder plus {d - 1} level(s) of subdirectories")
    return (f"Project scope (max depth {d}): survey, queue, and attribute only files within {d} "
            f"director{'y level' if d == 1 else 'y levels'} of the root — {detail}. Deeper "
            "subtrees are out of scope; do not trawl them. If the user explicitly points you at a "
            "deeper file you may open that one file, but do not expand the desk's scope to its subtree.")


def founding_sentence_block(proj: dict, *, instruction: str) -> str:
    """The user's own founding sentence — required at add, before the interview ever
    starts (P3). Quoted first, ahead of survey/kit context: their words beat
    inference. '' when somehow missing (legacy desk added before this was required)."""
    note = (load_session(proj).get("founding_note") or "").strip()
    if not note:
        return ""
    return f"THE USER'S FOUNDING SENTENCE (typed at add, before anything else — {instruction}):\n{note}"


def build_refresh_briefs_prompt(proj: dict) -> str | None:
    """Prompt for rewriting brief+ask on the current queue only.

    Returns None when the queue is empty (caller should short-circuit). Shared by
    POST /api/refresh-briefs and `kettle refresh-briefs`.
    """
    entries = load_queue(proj).get("entries") or []
    if not entries:
        return None
    prompt = REFRESH_BRIEFS_PROMPT.format(
        name=proj["name"],
        root=str(project_root(proj)),
        desk_dir=str(desk_dir(proj)),
        queue_path=str(queue_path(proj)),
    )
    handbook = base_handbook()
    if handbook:
        prompt += "\n\n" + handbook
    orientation = project_orientation(proj)
    if orientation:
        prompt += "\n\n" + orientation
    try:
        brief_fw = (APPDIR / "kits" / "frameworks" / "brief.md").read_text(
            encoding="utf-8").strip()
    except OSError:
        brief_fw = ""
    if brief_fw:
        prompt += "\n\nBrief framework:\n" + brief_fw
    if QUEUE_SCHEMA:
        prompt += "\n\n" + QUEUE_SCHEMA
    inv = [{
        "id": e.get("id"),
        "title": e.get("title"),
        "path": e.get("path"),
        "status": e.get("status"),
        "ask": e.get("ask"),
        "brief": e.get("brief"),
    } for e in entries]
    prompt += (
        "\n\n---\nCURRENT QUEUE ENTRIES (rewrite brief+ask for each; preserve ids/paths):\n"
        + json.dumps(inv, indent=2, ensure_ascii=False)
        + "\n---\n"
    )
    sc = scope_note(proj)
    if sc:
        prompt += "\n\n" + sc
    return prompt


def session_path(proj: dict) -> Path:
    """The project's single persistent-session record (replaces the old per-file model
    and the founding interview.json). One Claude Code session per project — named
    kettle-<project> — runs interview → found → chat → sweep; this file is its
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


def session_id_for_curator(
    sess: dict | None = None,
    proj: dict | None = None,
    *,
    model: str | None = None,
) -> str | None:
    """Return session_id only when it is safe to --resume under the active curator.

    Claude / Grok / Codex / Gemini keep separate session stores — never resume a
    foreign provider's id (Grok 404 → failure).

    Grok (and other non-Claude providers) also bind a session to an agent/model:
    resuming a composer/`cursor` session with `--model grok-4.5` fails with
    MODEL_SWITCH_INCOMPATIBLE_AGENT. When `model` is given and does not match the
    tagged session model (or the tag is missing), start a fresh session.
    """
    if sess is None:
        if proj is None:
            return None
        sess = load_session(proj)
    sid = sess.get("session_id")
    if not sid:
        return None
    cur = current_curator().provider
    tagged = (sess.get("provider") or "").strip()
    if tagged:
        if tagged != cur:
            return None
    elif cur not in ("claude", "cli"):
        # Legacy records predate provider tagging — only Claude-family may resume.
        return None

    want = (model or "").strip()
    if want and cur not in ("claude", "cli"):
        have = (sess.get("model") or "").strip()
        if have != want:
            return None
    return sid


def save_session(proj: dict, **fields) -> dict:
    """Shallow-merge the given fields into the project session record; returns it.

    When a session_id is written, also stamp `provider` to the active curator so a
    later provider switch does not --resume a foreign session. Callers should pass
    `model=` when known so mid-session model switches can start fresh.
    """
    cur = load_session(proj)
    if "session_id" in fields:
        sid = fields.get("session_id")
        if sid:
            if "provider" not in fields:
                fields = {**fields, "provider": current_curator().provider}
        else:
            # Explicit clear — drop id, provider tag, and model binding
            cur.pop("session_id", None)
            cur.pop("provider", None)
            cur.pop("model", None)
            fields = {
                k: v for k, v in fields.items()
                if k not in ("session_id", "provider", "model")
            }
    cur.update(fields)
    session_path(proj).parent.mkdir(parents=True, exist_ok=True)
    atomic_write(session_path(proj), json.dumps(cur, indent=2))
    return cur


# back-compat shims: the interview is now just the project session's first phase
def interview_path(proj: dict) -> Path:
    return session_path(proj)


def survey_path(proj: dict) -> Path:
    """Durable founding survey snapshot (Phase A) under the project runtime dir."""
    return runtime_dir(proj) / "survey.json"


def ensure_founding_survey(proj: dict) -> dict:
    """Build and persist a deterministic survey for the founding interview."""
    snap = survey_mod.build_survey(project_root(proj))
    sp = survey_path(proj)
    sp.parent.mkdir(parents=True, exist_ok=True)
    atomic_write(sp, survey_mod.dump(snap))
    return snap


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
    the name is project-level: kettle-<project>, slugified and length-capped. The
    `entry` argument is accepted but ignored (kept for call-site compatibility)."""
    base = proj.get("name") or "desk"
    body = re.sub(r"[^a-z0-9]+", "-", base.lower()).strip("-")[:48]
    return f"kettle-{body}" if body else "kettle"


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
        atomic_write(dest, data)


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
    """Load settings.json, normalize curator block, reseeding empty/corrupt files.

    Empty ``{}`` used to resolve as silent Claude defaults while the desk still
    held a cached Grok model id. We now persist a normalized curator block so
    disk, core, and UI share one pair.
    """
    with SETTINGS_LOCK:
        raw: dict = {}
        existed = SETTINGS_PATH.exists()
        corrupt = False
        if not existed:
            raw = {}
        else:
            try:
                loaded = json.loads(SETTINGS_PATH.read_text() or "{}")
                raw = loaded if isinstance(loaded, dict) else {}
            except json.JSONDecodeError:
                corrupt = True
                # Keep a backup of the unreadable file once.
                try:
                    bak = SETTINGS_PATH.with_suffix(".json.corrupt")
                    bak.write_bytes(SETTINGS_PATH.read_bytes())
                except OSError:
                    pass
                raw = {}
        normalized = curator_mod.ensure_curator_settings(raw)
        # Persist when missing, corrupt, empty, or models/provider were illegal.
        if (not existed) or corrupt or raw != normalized:
            atomic_write(
                SETTINGS_PATH,
                json.dumps(normalized, indent=2, ensure_ascii=False),
            )
        return normalized


def save_settings(patch: dict) -> dict:
    """Merge patch into settings.json (deep-merge for curator/agents); returns merged dict.

    Always sanitizes provider↔model pairs so half-patches cannot leave
    ``provider=claude`` with ``chat=grok-4.5``.
    """
    with SETTINGS_LOCK:
        try:
            cur = json.loads(SETTINGS_PATH.read_text()) if SETTINGS_PATH.exists() else {}
            if not isinstance(cur, dict):
                cur = {}
        except json.JSONDecodeError:
            cur = {}
        cur = curator_mod.deep_merge_settings(cur, patch)
        cur = curator_mod.ensure_curator_settings(cur)
        # Final coerce: illegal model ids for the active provider → defaults.
        block = cur.get("curator") if isinstance(cur.get("curator"), dict) else {}
        prov = str(block.get("provider") or "claude")
        block = dict(block)
        block["models"] = curator_mod.sanitize_models_for_provider(prov, block.get("models"))
        cur["curator"] = block
        cur["agents"] = dict(block.get("models") or {})
        atomic_write(SETTINGS_PATH, json.dumps(cur, indent=2, ensure_ascii=False))
        return cur


def atomic_write(path: Path, data: str | bytes) -> None:
    """Write via a fresh temp file in the same directory, then rename over `path`.

    The temp file is created with O_EXCL under a random name, so a symlink planted at a
    predictable `<name>.tmp` cannot redirect the write outside the fence. An existing
    file keeps its permission bits; a new one gets 0644."""
    path = Path(path)
    try:
        mode = stat.S_IMODE(path.stat().st_mode)
    except OSError:
        mode = 0o644
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix="." + path.name + ".", suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data.encode("utf-8") if isinstance(data, str) else data)
        os.chmod(tmp, mode)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def slug(s: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", s).strip("_") or "x"


def project_root_problem(rp: Path) -> str | None:
    """Why a resolved folder cannot be a project root, or None. Roots extend the file
    fence: every file under one becomes readable, writable and visible to curators."""
    home = HOME.resolve()
    if not rp.is_relative_to(home):
        return f"folder must be under {HOME}"
    if rp == home:
        return f"folder cannot be your whole home folder ({HOME}) — choose the project's own folder"
    for sp in (home / n for n in (".ssh", ".gnupg", ".aws", ".claude", ".config", ".cache",
                                  ".kube", ".docker")):
        if rp.is_relative_to(sp) or sp.is_relative_to(rp):
            return (f"folder {rp} overlaps {sp}, which holds credentials or agent "
                    "configuration — choose the project's own folder")
    registry_dir = PROJECTS_PATH.parent.resolve()
    if registry_dir.is_relative_to(rp):
        # a curator with write tools in this root could rewrite settings.json
        # (curator.command) or the project registry
        return (f"folder {rp} contains Kettle's own settings ({registry_dir}) — "
                "choose the project's own folder")
    return None


def register_project(name: str, root: str, kit: str | None = None,
                     max_depth=None, note: str | None = None) -> dict:
    """Register a project: validate, append to the registry, seed its desk. The single
    source of truth for 'add a project', shared by the HTTP handler and the CLI so the
    fence gate (project roots must be under $HOME — registered roots extend the file-API
    fence) is enforced one way. Raises ValueError(message) on any validation failure;
    returns the project dict on success. Creates the registry if it does not exist yet
    (first run), so a fresh install can register its first desk.

    `note` (the founding sentence) is optional *here* — this is the low-level
    primitive other callers (migration, tests) may use without a human at the
    keyboard. The human-facing entry points (`add_project` HTTP handler, `kettle add`
    CLI) require it before they ever call this."""
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
    problem = project_root_problem(rp)
    if problem:
        raise ValueError(problem)
    pid = slug(name).lower()
    proj = {
        "id": pid,
        "name": name,
        "root": root_raw.rstrip("/") or root_raw,  # ~-form preserved as given
    }
    if kit in kits.KINDS:                          # the user's pick (no auto-detection)
        proj["kit"] = kit
    try:
        depth = int(max_depth)
    except (TypeError, ValueError):
        depth = 0
    if depth >= 1:                                  # 0 / blank → unlimited (no field stored)
        proj["max_depth"] = depth
    with PROJECTS_LOCK:
        data = read_projects_registry()
        if any(p["id"] == pid for p in data["projects"]):
            raise ValueError(f"duplicate project id: {pid}")
        data["projects"].append(proj)
        PROJECTS_PATH.parent.mkdir(parents=True, exist_ok=True)
        atomic_write(PROJECTS_PATH, json.dumps(data, indent=2, ensure_ascii=False))
    (rp / ".kettle").mkdir(parents=True, exist_ok=True)   # new durable desk dir
    qp = queue_path(proj)
    if not qp.exists():
        atomic_write(qp, json.dumps(
            dict(EMPTY_QUEUE, curated="awaiting founding curation"),
            indent=2, ensure_ascii=False))
    from . import egress as _egress
    _egress.ensure_egress(proj)
    note = str(note or "").strip()
    if note:                       # the user's founding sentence → quoted first at every turn
        save_session(proj, founding_note=note)
    return proj


def refound_desk(proj: dict) -> dict:
    """Reset a project's desk to the pristine UNFOUNDED seed so its founding interview runs
    again on next selection. The whole old desk (charter, memory, runtime, queue, transcript)
    is copied to a machine-local backup first; the user's founding note is carried into the
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
    bk = HOME / ".cache" / "kettle-refound-backups" / f"{proj['id']}-{stamp}"
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


def is_proposal_entry(e: dict | None) -> bool:
    """True for the founding desk-proposal queue entry (not content work)."""
    if not isinstance(e, dict):
        return False
    if e.get("id") == PROPOSAL_ENTRY_ID or e.get("founding_phase") == "proposal":
        return True
    path = str(e.get("path") or "").replace("\\", "/")
    return path.endswith("/" + PROPOSAL_FILENAME) or path.endswith(PROPOSAL_FILENAME)


def content_entries(q: dict | None) -> list:
    """Queue entries that count as real work (excludes the desk proposal)."""
    return [e for e in ((q or {}).get("entries") or []) if not is_proposal_entry(e)]


def proposal_path(proj: dict) -> Path:
    return desk_dir(proj) / PROPOSAL_FILENAME


def proposal_on_disk(proj: dict) -> bool:
    try:
        return proposal_path(proj).is_file() and proposal_path(proj).stat().st_size > 0
    except OSError:
        return False


def clear_proposal_entry(proj: dict) -> None:
    """Remove the desk-proposal placeholder from the queue once real founding has
    landed. `kits/prompts/found.md` lets the curator leave it behind, and a stale one
    can go on pointing at a proposal file long since archived, renamed, or migrated
    away (the pre-Kettle `.setsweep/DESK-PROPOSAL.md` path is a live example)."""
    def strip(q):
        q["entries"] = [e for e in (q.get("entries") or []) if not is_proposal_entry(e)]
    mutate_queue(proj, strip)


def mark_founded_if_filed(proj: dict, *, founding_step: bool = False) -> bool:
    """A desk is founded once it has a charter (`PROJECT.md`) on disk AND the curator
    has filed at least one *content* queue entry (not the desk-proposal placeholder).
    Heals both directions: promotes to founded once charter and content both land
    (clearing any leftover desk-proposal entry), and demotes a desk stuck at
    'founded' with no charter — a stale mark from before this predicate existed, or a
    charter that has since gone missing — back to interviewing. Never demotes for an
    empty *queue* alone: a genuinely founded desk's queue legitimately empties between
    a sweep and its restock. Shared by founding handlers and the CLI.

    While a Desk Proposal awaits approval (status proposing) only a founding step —
    Found Desk, bootstrap, `kettle found` — may promote. A propose turn that ignores its
    prompt and writes a charter plus entries must not found the desk behind the user's
    approval, and neither may the next queue read."""
    try:
        has_charter = (desk_dir(proj) / "PROJECT.md").is_file()
        q = load_queue(proj)
        founded_now = has_charter and bool(content_entries(q))
        status = load_session(proj).get("status")
        was_founded = status == "founded"
        if founded_now and not was_founded and not founding_step and status == "proposing":
            return False
        if founded_now:
            if not was_founded:
                save_session(proj, status="founded")
            if any(is_proposal_entry(e) for e in (q.get("entries") or [])):
                clear_proposal_entry(proj)
            return True
        if was_founded and not has_charter:
            save_session(proj, status="interviewing")
    except Exception:  # noqa: BLE001
        pass
    return False


def ensure_proposal_entry(proj: dict) -> bool:
    """Re-file the desk-proposal queue entry when DESK-PROPOSAL.md exists on an unfounded
    desk but the queue lost it (a propose turn that wrote the file and no entry, or an
    approve whose Found Desk never finished). Without it the sitting has nothing to open
    and the desk is stuck until refound. Returns True when an entry was added."""
    if not proposal_on_disk(proj) or desk_is_founded(proj):
        return False
    added = []

    def add(q):
        entries = q.get("entries") or []
        if content_entries(q) or any(is_proposal_entry(e) for e in entries):
            return
        entries.append({
            "id": PROPOSAL_ENTRY_ID,
            "title": "Desk Proposal",
            "path": str(proposal_path(proj)),
            "project": proj.get("name"),
            "project_root": str(project_root(proj)),
            "ask_type": "judgment",
            "ask": "Edit this proposal until it matches your intent, then approve to found the desk",
            "urgency": "high",
            "status": "pending",
            "founding_phase": "proposal",
            "brief": "This is the Kettle Desk Proposal. Approving it founds the desk from this text.",
        })
        q["entries"] = entries
        added.append(True)

    mutate_queue(proj, add)
    return bool(added)


def build_found_prompt(proj: dict, *, session_id: str | None, bootstrap: bool = False) -> str:
    """The one founding prompt, shared by POST /api/found, POST /api/bootstrap and
    `kettle found` so no entry point drops the user's founding sentence, the queue
    schema, the kit context or the scope note.

    Digests DESK-PROPOSAL.md when present; otherwise resumes the interview session
    (legacy found) or, with no session or when `bootstrap` is set, founds one-shot from
    the files. The founding-sentence block leads the prompt (P3: the user's words come
    before any instructions or inference); the prompts refer to it as 'above'."""
    fields = dict(
        name=proj["name"], root=str(project_root(proj)),
        desk_dir=str(desk_dir(proj)), queue_path=str(queue_path(proj)),
        proposal_path=str(proposal_path(proj)),
    )
    has_proposal = not bootstrap and proposal_on_disk(proj)
    if has_proposal:
        prompt = FOUND_PROMPT.format(**fields)
    elif session_id and not bootstrap:
        prompt = FOUND_LEGACY_PROMPT.format(**fields)
    else:
        prompt = BOOTSTRAP_PROMPT.format(
            name=fields["name"], root=fields["root"],
            desk_dir=fields["desk_dir"], queue_path=fields["queue_path"],
        )
    fs = founding_sentence_block(
        proj, instruction="PROJECT.md must open with it under a 'Your Words' heading")
    if fs:
        prompt = fs + "\n\n" + prompt
    # Single-source schema + cold-re-entry brief standard (kits/prompts/queue-schema.md).
    if QUEUE_SCHEMA:
        prompt += "\n\n" + QUEUE_SCHEMA
    kit_ctx = kits.as_context(
        kits.for_project(proj, APPDIR / "kits", load_settings()), "found")
    if kit_ctx:
        prompt += "\n\n" + kit_ctx
    if has_proposal:
        prompt += (
            "\n\nCRITICAL: Re-read the proposal file on disk immediately before writing "
            "desk files — the user may have edited it in the center pane after you "
            "drafted it. Their on-disk text is authoritative."
        )
    sc = scope_note(proj)
    if sc:
        prompt += "\n\n" + sc
    return prompt


def desk_is_founded(proj: dict) -> bool:
    """True when session status is founded (content entries heal via mark_founded_if_filed)."""
    return load_session(proj).get("status") == "founded"


def desk_is_proposing(proj: dict) -> bool:
    """Proposal phase: session says proposing, or proposal file is the only work on the queue."""
    st = load_session(proj).get("status")
    if st == "founded":
        return False
    if st == "proposing":
        return True
    try:
        q = load_queue(proj)
    except Exception:  # noqa: BLE001
        return False
    ents = q.get("entries") or []
    return bool(ents) and not content_entries(q) and any(is_proposal_entry(e) for e in ents)


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


def _admin_fleet_panels_enabled(settings: dict | None = None) -> bool:
    """Personal-fleet admin panels (sentinel, desk-events, persona family). Default off."""
    s = settings if settings is not None else load_settings()
    admin = s.get("admin") if isinstance(s, dict) else None
    return bool(isinstance(admin, dict) and admin.get("fleet_panels"))


def _project_debug(proj: dict, *, fleet_panels: bool = False) -> dict:
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
        info["error"] = str(e)
    # Optional persona-family progress: only when fleet_panels is on *and*
    # settings.admin.persona_family_relpath is set (no product-default personal path).
    if fleet_panels:
        try:
            settings = load_settings()
            admin = settings.get("admin") if isinstance(settings, dict) else {}
            rel = (admin or {}).get("persona_family_relpath")
            if isinstance(rel, str) and rel.strip():
                pdir = Path(proj.get("root", "")) / rel.strip()
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
    settings = load_settings()
    fleet = _admin_fleet_panels_enabled(settings)
    cfg = current_curator()
    report = {
        "server": {
            "port": SERVER_PORT,
            "claude_path": cfg.resolved_command(),  # back-compat alias
            "claude_exists": cfg.command_exists(),
            "curator_path": cfg.resolved_command(),
            "curator_exists": cfg.command_exists(),
            "curator": cfg.as_public_dict(),
            "project_count": len(projects),
            "active": active_pid,
        },
        "settings": settings,
        "projects": [_project_debug(p, fleet_panels=fleet) for p in projects],
        "fleet_panels": fleet,
        "sentinel": None,
        "events": None,
        "watcher": None,
        # Kettle's own folder-watcher beacon (kettle_watch.py) — always reported.
        "watch_health": _read_json(HOME / ".cache" / "kettle" / "watch-health.json") or None,
    }
    if fleet:
        health = _read_json(CACHE / "inventory-health.json")
        watch = health.get("kettle-watch") if isinstance(health, dict) else None
        report["sentinel"] = _sentinel_status()
        report["events"] = _events_tail(20)
        report["watcher"] = watch
    return report


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

    def send_err(self, status: int, error: str, code: str):
        """Uniform error envelope: {error, code} with str messages (never repr)."""
        self.send_json({"error": error, "code": code}, status)

    @staticmethod
    def _host_allowed(host: str) -> bool:
        h = (host or "").strip().lower()
        if h in ("127.0.0.1", "localhost"):
            return True
        if h.startswith("127.0.0.1:") or h.startswith("localhost:"):
            _, _, port_s = h.partition(":")
            return port_s.isdigit() and 1 <= int(port_s) <= 65535
        return False

    def _origin_allowed(self, origin: str) -> bool:
        port = SERVER_PORT or DEFAULT_PORT
        allowed = {
            f"http://127.0.0.1:{port}",
            f"http://localhost:{port}",
        }
        return origin.strip() in allowed

    def check_request_guards(self, *, require_token: bool) -> bool:
        """Host + Origin (+ optional token) gates. False ⇒ response already sent."""
        if not self._host_allowed(self.headers.get("Host", "")):
            self.send_err(403, "invalid Host header", "bad_host")
            return False
        origin = self.headers.get("Origin")
        if origin is not None and origin != "" and not self._origin_allowed(origin):
            self.send_err(403, "cross-origin request blocked", "bad_origin")
            return False
        if require_token:
            got = self.headers.get(TOKEN_HEADER)
            if (
                not SERVER_TOKEN
                or not isinstance(got, str)
                or not hmac.compare_digest(got, SERVER_TOKEN)
            ):
                self.send_err(
                    403,
                    "missing or invalid X-Kettle-Token "
                    "(read token from ~/.cache/kettle/server.json)",
                    "auth",
                )
                return False
        return True

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

    def stream_idle(self, message: str) -> None:
        """NDJSON notice without spawning a curator (idempotent short-circuit)."""
        self.send_response(200)
        self.send_header("Content-Type", "application/x-ndjson; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.stream_line({"t": "text", "s": message})
        self.stream_line({"t": "done"})

    def do_GET(self):
        url = urlparse(self.path)
        qs = parse_qs(url.query)
        api = url.path.startswith("/api/")
        if not self.check_request_guards(require_token=api):
            return
        try:
            if url.path in ("/", "/index.html"):
                body = (STATIC / "index.html").read_bytes()
                # Inject per-boot token so same-origin UI can authorize /api/ calls.
                if SERVER_TOKEN:
                    meta = (
                        f'<meta name="kettle-token" content="{SERVER_TOKEN}">'
                    ).encode()
                    if b'<meta name="kettle-token"' not in body:
                        body = body.replace(b"<head>", b"<head>\n" + meta, 1)
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Security-Policy", sitting_csp(body))
                self.send_header("X-Frame-Options", "DENY")
                self.send_header("X-Content-Type-Options", "nosniff")
                self.send_header("Referrer-Policy", "no-referrer")
                # Sitting UI iterates quickly — never let Electron/browser keep a stale shell.
                self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
                self.send_header("Pragma", "no-cache")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            elif url.path in ("/marked.min.js", "/themes.js", "/purify.min.js", "/ui-copy.js"):
                body = (STATIC / url.path.lstrip("/")).read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "application/javascript")
                self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
                self.send_header("Pragma", "no-cache")
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
                # old kettle holding the port — and lets anyone tell us apart
                # from a foreign service
                cfg = current_curator()
                self.send_json({
                    "app": "kettle",
                    **kettle_contract.identity(),
                    "pid": os.getpid(),
                    "port": SERVER_PORT,
                    "started": SERVER_STARTED,
                    "projects": str(PROJECTS_PATH),
                    "settings": str(SETTINGS_PATH),
                    "curator": cfg.as_public_dict(),
                })
            elif url.path == "/api/projects":
                self.send_json({
                    "projects": load_projects(),
                    "home": str(HOME),
                    "registry": str(PROJECTS_PATH),
                })
            elif url.path == "/api/kits":
                self.send_json({"kits": kits.list_kits(APPDIR / "kits", load_settings()),
                                "kinds": kits.KINDS})
            elif url.path == "/api/settings":
                # Always surface a normalized curator block (migration is read-side)
                self.send_json(curator_mod.ensure_curator_settings(load_settings()))
            elif url.path == "/api/themes":
                # Color theme catalog for web/desktop Appearance and CLI parity.
                full = (qs.get("full", ["0"])[0] or "0").lower() in ("1", "true", "yes")
                self.send_json(theme_catalog.catalog_payload(full=full))
            elif url.path.startswith("/api/themes/"):
                tid = url.path[len("/api/themes/"):].strip("/")
                if not tid or "/" in tid or ".." in tid or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", tid):
                    self.send_json({"error": "invalid theme id"}, 400)
                    return
                try:
                    pack = theme_catalog.load_theme(tid)
                except FileNotFoundError:
                    self.send_json({"error": "theme not found"}, 404)
                    return
                except ValueError as e:
                    self.send_json({"error": str(e)}, 400)
                    return
                self.send_json(theme_catalog.pack_to_web(pack))
            elif url.path == "/api/curator/catalog":
                self.send_json(curator_mod.build_catalog(load_settings()))
            elif url.path == "/api/admin":
                self.send_json(admin_report(qs.get("project", [None])[0]))
            elif url.path == "/api/lineage":
                proj = get_project(qs.get("project", [None])[0])
                self.send_json(lineage.status(project_root(proj), max_depth=proj.get("max_depth")))
            elif url.path == "/api/queue":
                proj = get_project(qs.get("project", [None])[0])
                if want_mutate(qs):
                    mark_founded_if_filed(proj)   # queue entries ⇒ founded (heals stale interviewing)
                    q = load_queue(proj)
                    ensure_snapshots(proj, q)
                else:
                    q = load_queue(proj)
                enrich_queue_comments(proj, q)
                for e in q.get("entries", []):
                    e["diff"] = entry_diffstat(proj, e)   # {added, removed} vs snapshot, or None
                self.send_json(q)
            elif url.path == "/api/diff":
                proj = get_project(qs.get("project", [None])[0])
                eid = qs.get("id", [None])[0]
                ent = next((x for x in load_queue(proj).get("entries", [])
                            if str(x.get("id")) == str(eid)), None)
                if ent is None:
                    self.send_err(404, f"unknown entry id: {eid}", "not_found")
                    return
                text = entry_diff_text(proj, ent)
                # `text` is canonical; `diff` kept for older clients
                self.send_json({"text": text, "diff": text})
            elif url.path == "/api/diffstat":
                proj = get_project(qs.get("project", [None])[0])
                eid = qs.get("id", [None])[0]
                ent = next((x for x in load_queue(proj).get("entries", [])
                            if str(x.get("id")) == str(eid)), None)
                if ent is None:
                    self.send_err(404, f"unknown entry id: {eid}", "not_found")
                    return
                stat = entry_diffstat(proj, ent)
                # `stat` is canonical; `diff` kept for older clients (same key, different type — avoid)
                self.send_json({"stat": stat, "diff": stat})
            elif url.path == "/api/git/activity":
                # Local git contribution heatmap (gitmap.py) for the project root.
                # Omit weeks / weeks=auto → adaptive window from first commit.
                proj = get_project(qs.get("project", [None])[0])
                raw_w = (qs.get("weeks", [None])[0] or "").strip().lower()
                if raw_w in ("", "auto", "0", "none"):
                    weeks_arg = None  # adaptive
                else:
                    weeks_arg = gitmap.clamp_weeks(raw_w)
                self.send_json(
                    gitmap.git_commit_activity(project_root(proj), weeks=weeks_arg)
                )
            elif url.path == "/api/chatlog":
                proj = get_project(qs.get("project", [None])[0])
                self.send_json({"messages": load_chatlog(proj)})
            elif url.path == "/api/interview":
                proj = get_project(qs.get("project", [None])[0])
                q = load_queue(proj)
                entries = q.get("entries") or []
                content = content_entries(q)
                if want_mutate(qs):
                    mark_founded_if_filed(proj)
                    # proposal-only queue ⇒ proposing (not founded)
                    if not content_entries(load_queue(proj)) and (
                        proposal_on_disk(proj)
                        or any(is_proposal_entry(e) for e in entries)
                    ):
                        st = load_session(proj).get("status")
                        if st not in ("founded", "proposing"):
                            save_session(proj, status="proposing")
                    ensure_proposal_entry(proj)
                    entries = load_queue(proj).get("entries") or []
                iv = load_interview(proj)
                # has_entries = content work (viewport founded signal); proposal alone is not.
                self.send_json({
                    "status": iv.get("status", "none"),
                    "has_session": bool(iv.get("session_id")),
                    "has_entries": bool(content),
                    "entry_count": len(content),
                    "has_proposal": proposal_on_disk(proj) or any(
                        is_proposal_entry(e) for e in entries),
                    "proposal_path": str(proposal_path(proj)),
                    # The founded predicate (charter AND content entries) — viewports
                    # use this, not has_entries, to decide founded.
                    "founded": iv.get("status") == "founded",
                    "has_charter": (desk_dir(proj) / "PROJECT.md").is_file(),
                })
            elif url.path == "/api/file":
                proj = get_project(qs.get("project", [None])[0])
                p = safe_path(qs["path"][0], project_root(proj) if proj else None)
                self.send_json({"path": str(p),
                                "content": p.read_text(encoding="utf-8", errors="replace")})
            else:
                self.send_json({"error": "not found"}, 404)
        except PermissionError as e:
            self.send_err(403, str(e), "forbidden")
        except FileNotFoundError as e:
            self.send_err(404, str(e) or "file not found", "not_found")
        except KeyError as e:
            self.send_err(400, f"missing/unknown: {e}", "bad_request")
        except Exception as e:  # noqa: BLE001
            self.send_err(500, str(e), "internal")

    def do_POST(self):
        url = urlparse(self.path)
        if not self.check_request_guards(require_token=url.path.startswith("/api/")):
            return
        try:
            d = self.read_body()
            if url.path == "/api/save":
                sp = get_project(d.get("project")) if d.get("project") else None
                p = safe_path(d["path"], project_root(sp) if sp else None)
                atomic_write(p, d["content"])  # rely on your VCS/sync layer for version history
                proj = project_for_path(p)            # the user's own edit → user lineage
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
                # Proposal approve is only a bookmark here; the client streams POST /api/found
                # so the curator digests on-disk edits and files the first content batch.
                self.send_json({
                    "ok": True,
                    "founding": is_proposal_entry(e) and not desk_is_founded(proj),
                })
            elif url.path == "/api/settings":
                self.send_json(save_settings(d))
            elif url.path == "/api/themes/install":
                # Write a host-neutral pack into the user themes directory.
                try:
                    pack = theme_catalog.install_user_pack(d if isinstance(d, dict) else {})
                except ValueError as e:
                    self.send_json({"error": str(e)}, 400)
                    return
                except OSError as e:
                    self.send_json({"error": f"could not write theme: {e}"}, 500)
                    return
                self.send_json({
                    "ok": True,
                    "id": pack.get("id"),
                    "label": pack.get("label"),
                    "path": pack.get("_path"),
                    "pack": theme_catalog.pack_to_web(pack),
                    "catalog": theme_catalog.catalog_payload(full=False),
                })
            elif url.path == "/api/curator":
                # Atomic curator selection: provider + model (+ optional effort) in one write.
                # Preferred over partial PATCH /api/settings for the desk model menu.
                try:
                    next_settings = curator_mod.apply_curator_selection(
                        load_settings(),
                        provider=d.get("provider"),
                        model=d.get("model"),
                        task=str(d.get("task") or "chat"),
                        effort=d.get("effort"),
                        command=d.get("command"),
                        models=d.get("models") if isinstance(d.get("models"), dict) else None,
                    )
                except ValueError as e:
                    self.send_json({"error": str(e)}, 400)
                    return
                # apply_curator_selection returns a full settings dict — write via merge of
                # the curator block so we don't drop unrelated top-level keys unexpectedly.
                saved = save_settings({"curator": next_settings.get("curator") or {}})
                self.send_json({
                    "ok": True,
                    "settings": saved,
                    "active": curator_mod.resolved_active(saved),
                })
            elif url.path == "/api/chatlog":
                proj = get_project(d.get("project"))
                msgs = d.get("messages")
                if not isinstance(msgs, list):
                    self.send_json({"error": "messages must be a list"}, 400)
                else:
                    self.send_json({"ok": True, "count": save_chatlog(proj, msgs)})
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
                else:
                    close_comments(proj, [d["id"]])  # a cleared note is retracted, not replayed
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
            elif url.path == "/api/refresh-briefs":
                self.refresh_briefs(d)
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
            elif url.path == "/api/propose":
                self.propose(d)
            elif url.path == "/api/found":
                self.found(d)
            elif url.path == "/api/entry":
                self.update_entry(d)
            elif url.path == "/api/open-link":
                self.open_link(d)
            else:
                self.send_json({"error": "not found"}, 404)
        except json.JSONDecodeError as e:
            self.send_err(400, str(e), "bad_json")
        except PermissionError as e:
            self.send_err(403, str(e), "forbidden")
        except FileNotFoundError as e:
            self.send_err(404, str(e) or "file not found", "not_found")
        except KeyError as e:
            self.send_err(400, f"missing/unknown: {e}", "bad_request")
        except Exception as e:  # noqa: BLE001
            self.send_err(500, str(e), "internal")

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
                    if "/." in str(p):  # skip dotdirs (.kettle, .git)
                        continue
                    if p.is_file() and p.stem.lower() == stem and (
                            ext == "" or p.suffix.lower() == ext):
                        best = p
                        break
                if best:
                    break
            target = best
        if target is None:
            self.send_json({"error": f"no file matching [[{name}]]"}, 404)
            return
        try:
            safe = safe_path(str(target))  # fence to allowed roots
        except PermissionError as e:
            self.send_json({"error": str(e)}, 403)
            return
        subprocess.Popen(["open", "-t", str(safe)])  # macOS: default text editor
        self.send_json({"ok": True, "path": str(safe)})

    def chat(self, d):
        proj = get_project(d.get("project"))
        sess = load_session(proj)
        turn_model = current_curator().model_for("chat", d.get("model"))
        sid = session_id_for_curator(sess, model=turn_model)
        message = d["message"]

        # The entry is OPTIONAL: a project-level turn (no file selected — e.g. answering a
        # question the sweep raised) carries no active-file context block, but still resumes
        # the project session. Only look up an entry when an id is supplied. This is what
        # lets the user reply when nothing is open (the sweep leaves no current file).
        entry = None
        eid = d.get("id")
        proposing = desk_is_proposing(proj)
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
            if proposing and is_proposal_entry(entry) and (not sid or switched):
                message = (
                    "[Founding proposal phase] The user is editing the desk proposal. "
                    "Revise that file with Edit/Write when they ask. Do NOT write PROJECT.md, "
                    "MEMORY.md, or found the full desk until they click approve.\n\n"
                ) + message

        sysprompt = None
        if not sid:  # first-ever turn on this project: create the named project session
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
            if proposing:
                sysprompt += (
                    "\n\nFounding proposal phase: help refine DESK-PROPOSAL.md only until "
                    "the user approves it."
                )

        cmd = build_turn_cmd(
            message, task="chat", request_model=d.get("model"),
            session_id=sid, system_append=sysprompt,
            name=session_name(proj), tools_tier="chat",
        )

        # record the active file (only when an entry is in play) so a same-file follow-up
        # won't re-inject context; the session_id is persisted by run_curator's init hook below
        if entry:
            save_session(proj, last_entry=entry["id"], name=session_name(proj))
        else:
            save_session(proj, name=session_name(proj))

        def persist(new_sid):
            kw = {"session_id": new_sid}
            if turn_model:
                kw["model"] = turn_model
            save_session(proj, **kw)

        self.run_curator(cmd, str(project_root(proj)), prior_sid=sid, persist=persist,
                         record_user_message=d["message"], role="review-agent")

    def compact(self, d):
        """Run /compact on the project session: summarize-and-continue in place. The
        session_id is unchanged, so the thread survives — only its context shrinks. The
        compact turn's own usage reflects the pre-compaction size, so the client does not
        drive the context bar from it; the bar refreshes on the next real chat turn."""
        proj = get_project(d.get("project"))
        turn_model = current_curator().model_for("chat", d.get("model"))
        sid = session_id_for_curator(proj=proj, model=turn_model)
        if not sid:
            self.run_curator(["true"], str(project_root(proj)))  # no session: emit clean stream, no-op
            return
        cmd = build_turn_cmd(
            "/compact", task="chat", request_model=d.get("model"),
            session_id=sid, tools_tier="chat",
        )
        self.run_curator(cmd, str(project_root(proj)), prior_sid=sid)

    def refresh_briefs(self, d):
        """Rewrite brief + ask on the current queue only (no close, archive, or restock)."""
        proj = get_project(d.get("project"))
        built = build_refresh_briefs_prompt(proj)
        if built is None:
            self.stream_idle("Queue is empty — nothing to refresh.")
            return
        prompt = built
        sid = session_id_for_curator(
            proj=proj, model=current_curator().model_for("setup", d.get("model")),
        )
        cmd = build_turn_cmd(
            prompt, task="setup", request_model=d.get("model"),
            session_id=sid, name=session_name(proj), tools_tier="sweep",
        )

        def persist(new_sid):
            kw = {"session_id": new_sid, "name": session_name(proj)}
            m = current_curator().model_for("setup", d.get("model"))
            if m:
                kw["model"] = m
            save_session(proj, **kw)

        self.run_curator(cmd, str(project_root(proj)), prior_sid=sid, persist=persist,
                         role="curator")

    def sweep(self, d):
        proj = get_project(d.get("project"))
        with SWEEPS_LOCK:
            if proj["id"] in SWEEPS_IN_FLIGHT:
                self.stream_idle("A sweep is already running for this desk — wait for it to finish.")
                return
            SWEEPS_IN_FLIGHT.add(proj["id"])
        try:
            self._sweep(proj, d)
        finally:
            with SWEEPS_LOCK:
                SWEEPS_IN_FLIGHT.discard(proj["id"])

    def _sweep(self, proj, d):
        ledger = proj.get("ledger") or "(no ledger configured — queue/approvals only)"
        rd = runtime_dir(proj)
        cl_path = comments_log_path(proj)
        stamp = datetime.now().strftime("%Y-%m-%d-%H%M%S")
        last = sweepkit.read_sweep_health(proj)
        interrupted = last.get("state") in ("running", "failed")
        status = sweepkit.assess_close(proj)
        close: dict = {"ok": False, "action": "skipped", "status": status}
        if status.get("can_mechanical_close"):
            close = sweepkit.mechanical_close(proj)

        # Fully idle, or quiet inbox close with nothing left to accrue → no curator spawn
        st = close.get("status") or status
        if st.get("fully_idle"):
            if interrupted and st.get("needs_accrue"):
                # The previous sweep closed the queue and then died before restocking.
                # An empty quiet queue is its wreckage, not an idle desk: restock now.
                close = {
                    "ok": True, "action": "resume_interrupted_sweep",
                    "needs_accrue": True, "interrupted_sweep": last,
                    "session_log": last.get("session_log") or "",
                }
            else:
                note = ""
                if interrupted:
                    note = (f" (last sweep did not finish: {last.get('error') or last.get('state')}"
                            f" at {last.get('updated', '?')})")
                    # Reported once; a quiet desk with nothing to restock is not still failing.
                    sweepkit.write_sweep_health(proj, state="idle", phase="close", stamp=stamp,
                                                previous=last)
                self.stream_idle("Nothing to sweep — queue empty and quiet." + note)
                return
        if close.get("ok") and close.get("action") == "mechanical_close" and not close.get("needs_accrue"):
            n = len((close.get("archived") or {}).get("archived") or [])
            sweepkit.write_sweep_health(proj, state="done", phase="close", stamp=stamp,
                                        session_log=close.get("session_log") or "")
            self.stream_idle(
                f"Quiet close complete ({n} entr{'y' if n == 1 else 'ies'} archived"
                + ("; inbox drafts staged" if (close.get("staged") or {}).get("staged") else "")
                + "). No accrue/restock for this desk kind."
            )
            return

        accrue_only = bool(close.get("ok") and close.get("needs_accrue"))
        queue_entries = load_queue(proj).get("entries", [])
        # Bound the comments this prompt shows in the same breath as reading them: a note
        # typed while the rest of the prompt is assembled must not be retired unread.
        comments_through = comments_log_line_count(proj)
        user_comments = sweep_user_comments_block(parse_comments_log(cl_path), queue_entries)

        if accrue_only:
            prompt = ACCRUE_PROMPT.format(
                name=proj["name"], root=str(project_root(proj)),
                desk_dir=str(desk_dir(proj)), runtime_dir=str(rd),
                stamp=stamp, queue_path=str(queue_path(proj)),
                session_log=close.get("session_log") or "",
            )
            prompt += "\n\n---\nCLOSE KIT RESULT:\n" + json.dumps(
                {k: close[k] for k in ("action", "archived", "staged", "session_log", "needs_accrue",
                                       "interrupted_sweep")
                 if k in close}, indent=2)
            prompt += "\n---\n"
        else:
            prompt = SWEEP_PROMPT.format(
                name=proj["name"], root=str(project_root(proj)),
                ledger=str(Path(ledger).expanduser()) if str(ledger).startswith(("~", "/")) else ledger,
                desk_dir=str(desk_dir(proj)), runtime_dir=str(rd),
                today=date.today().isoformat(),
                stamp=stamp,
                queue_path=str(queue_path(proj)),
                comments_log_path=str(cl_path),
            )
            prompt += (
                "\n\n---\nUSER COMMENTS (from "
                + str(cl_path)
                + " — treat each line as mandatory review input for that entry):\n\n"
            )
            prompt += user_comments if user_comments else "(no comments on file for current queue entries)"
            prompt += "\n---\n"
            prompt += "\n" + sweep_precomputed_context(proj, queue_entries)
            prompt += "\n" + sweepkit.status_for_prompt(proj)
            prompt += (
                "\n\nCLOSE KIT: prefer `kettle sweep-close <project>` / mechanical helpers when "
                "quiet; after judgment, archive via the close-kit rather than hand-rolled mv/rm.\n"
            )
            intake = intake_paths(proj)
            if intake:
                _, _, outbound = intake
                prompt += (
                    "\n\nINTAKE OUTBOUND — inbox project: stage approved drafts to "
                    f"{outbound}, archive approved only, leave pending entries. "
                    "NEVER transmit.\n"
                )

        handbook = base_handbook()
        if handbook:
            prompt += "\n\n" + handbook
        orientation = project_orientation(proj)
        if orientation:
            prompt += "\n\n" + orientation
        # Accrue / egress frameworks (full text — brief.md's worked rewrite is load-bearing
        # for cold-re-entry quality; do not truncate mid-example).
        for fname, label in (
            ("frameworks/brief.md", "Brief framework"),
            ("frameworks/familiarity.md", "Familiarity framework"),
            ("frameworks/egress.md", "Egress framework"),
        ):
            try:
                text = (APPDIR / "kits" / fname).read_text(encoding="utf-8").strip()
            except OSError:
                text = ""
            if text:
                prompt += f"\n\n{label}:\n{text}"
        if QUEUE_SCHEMA:
            prompt += "\n\n" + QUEUE_SCHEMA
        from . import egress as _egress
        try:
            prompt += "\n\n" + _egress.status_for_prompt(proj)
        except OSError:
            pass
        kit_ctx = kits.as_context(
            kits.for_project(proj, APPDIR / "kits", load_settings()), "sweep")
        if kit_ctx:
            prompt += "\n\n" + kit_ctx
        sc = scope_note(proj)
        if sc:
            prompt += "\n\n" + sc
        thrust = str(d.get("thrust") or "").strip()
        if thrust:
            quoted = "\n".join("> " + ln for ln in thrust.splitlines())
            prompt = ("The curator's steer for this sitting — read it first; let it shape where "
                      "you press hardest as you close the desk:\n\n" + quoted + "\n\n— · —\n\n" + prompt)
        # Live-stream verbosity (settings.sweepVerbosity; request may override for one-shot)
        verb = d.get("verbosity") if d.get("verbosity") not in (None, "") else \
            load_settings().get("sweepVerbosity")
        prompt += "\n\n" + sweep_verbosity_block(verb)
        sid = session_id_for_curator(
            proj=proj, model=current_curator().model_for("setup", d.get("model")),
        )
        cmd = build_turn_cmd(
            prompt, task="setup", request_model=d.get("model"),
            session_id=sid, name=session_name(proj), tools_tier="sweep",
        )

        def persist(new_sid):
            kw = {"session_id": new_sid, "name": session_name(proj)}
            m = current_curator().model_for("setup", d.get("model"))
            if m:
                kw["model"] = m
            save_session(proj, **kw)

        # The comments this prompt carried are consumed only if the curator finishes.
        shown_ids = [e.get("id") for e in queue_entries if e.get("id")]
        phase = "accrue" if accrue_only else "sweep"
        started = sweepkit.write_sweep_health(
            proj, state="running", phase=phase, stamp=stamp, pid=os.getpid(),
            session_log=close.get("session_log") or "",
        )

        def on_finish(outcome):
            sweepkit.write_sweep_health(
                proj, state="done" if outcome["ok"] else "failed", phase=phase,
                stamp=stamp, started=started["updated"], exit=outcome.get("exit"),
                error=outcome.get("error"), session_log=close.get("session_log") or "",
            )
            if outcome["ok"] and shown_ids:
                close_comments(proj, shown_ids, through=comments_through)

        self.run_curator(cmd, str(project_root(proj)), prior_sid=sid, persist=persist,
                         role="sweep", on_finish=on_finish)

    # ---- add project: registry append + desk seed ----
    def add_project(self, d):
        # registration logic (validation, fence gate, registry append, desk seed) lives in
        # the module-level register_project so the CLI shares it; here we only translate.
        note = str(d.get("note") or "").strip()
        if not note:
            self.send_json({
                "error": "founding sentence required: in a sentence or two, what is this "
                         "and what do you want from a second reader here?",
            }, 400)
            return
        try:
            proj = register_project(d.get("name", ""), d.get("root", ""),
                                    d.get("kit"), d.get("max_depth"), note)
        except ValueError as e:
            self.send_json({"error": str(e)}, 400)
            return
        # Flat fields kept for the web UI (`added.id`); `project` + `ok` for typed clients.
        self.send_json({"ok": True, "project": proj, "home": str(HOME), **proj})

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
            data = read_projects_registry()
            before = len(data["projects"])
            data["projects"] = [p for p in data["projects"] if p["id"] != pid]
            if len(data["projects"]) == before:
                self.send_json({"error": f"no such project: {pid}"}, 400)
                return
            atomic_write(PROJECTS_PATH, json.dumps(data, indent=2, ensure_ascii=False))
        # the project's files and its .kettle desk are intentionally left untouched
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
        problem = project_root_problem(rp)
        if problem:
            self.send_json({"error": problem}, 400)
            return
        root_clean = root_raw.rstrip("/") or root_raw
        with PROJECTS_LOCK:
            data = read_projects_registry()
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

    # ---- bootstrap: one-shot found from files (CLI / legacy; UI demotes this) ----
    def bootstrap(self, d):
        proj = get_project(d.get("project"))
        if desk_is_founded(proj):
            self.stream_idle("Desk already founded. Use refound to start over.")
            return
        if mark_founded_if_filed(proj, founding_step=True):
            self.stream_idle("Queue already has content entries — marked founded.")
            return
        prompt = build_found_prompt(proj, session_id=None, bootstrap=True)
        cmd = build_turn_cmd(
            prompt, task="setup", request_model=d.get("model"), tools_tier="sweep",
        )
        self.run_curator(cmd, str(project_root(proj)))
        mark_founded_if_filed(proj, founding_step=True)

    # ---- the founding interview: core survey + tool-less conversation ----
    def interview(self, d):
        proj = get_project(d.get("project"))
        if desk_is_founded(proj):
            self.stream_idle("Desk already founded. Use refound to interview again.")
            return
        if desk_is_proposing(proj):
            self.stream_idle(
                "Desk Proposal is ready — edit it in the center pane, talk here to revise, "
                "approve when it matches your intent.")
            return
        # Tool-less interview: no provider read_only refuse — survey is core-side.
        sid = session_id_for_curator(
            proj=proj, model=current_curator().model_for("chat", d.get("model")),
        )
        if sid and load_session(proj).get("status") != "interviewing":
            # A chat (or `kettle chat`) before the interview opened this session without
            # the founding role, survey or founding sentence. Resuming it would leave the
            # kickoff pointing at a survey the curator never received: start fresh.
            sid = None
        message = str(d.get("message") or "").strip() or INTERVIEW_KICKOFF
        role = None
        if not sid:  # first turn: build survey, open named project session (no tools)
            snap = ensure_founding_survey(proj)
            role = INTERVIEW_ROLE.format(name=proj["name"], root=str(project_root(proj)))
            fs = founding_sentence_block(
                proj, instruction="quote it in your opening line, don't paraphrase it")
            if fs:
                role += "\n\n" + fs
            role += "\n\n" + survey_mod.as_prompt_block(snap)
            # No confirmation card (P4) — kit stems now feed only the propose turn's
            # stated defaults, not a founding Q&A form.
            sc = scope_note(proj)
            if sc:
                role += "\n\n" + sc
        cmd = build_turn_cmd(
            message, task="chat", request_model=d.get("model"),
            session_id=sid, system_append=role,
            name=session_name(proj), tools_tier="interview",
        )

        def persist(new_sid):
            kw = {
                "session_id": new_sid,
                "status": "interviewing",
                "name": session_name(proj),
            }
            m = current_curator().model_for("chat", d.get("model"))
            if m:
                kw["model"] = m
            save_session(proj, **kw)

        self.run_curator(cmd, str(project_root(proj)), prior_sid=sid, persist=persist)

    # ---- finish interview: write DESK-PROPOSAL.md + single queue entry (not full found) ----
    def propose(self, d):
        proj = get_project(d.get("project"))
        if desk_is_founded(proj):
            self.stream_idle("Desk already founded. Use refound to start over.")
            return
        if mark_founded_if_filed(proj):
            self.stream_idle("Queue already has content entries — marked founded.")
            return
        turn_model = current_curator().model_for("setup", d.get("model"))
        # Prefer setup model, but resume chat-tagged interview session when compatible
        sid = session_id_for_curator(proj=proj, model=turn_model)
        if not sid:
            sid = session_id_for_curator(
                proj=proj, model=current_curator().model_for("chat", d.get("model")))
        prop = proposal_path(proj)
        prop.parent.mkdir(parents=True, exist_ok=True)
        fields = dict(
            name=proj["name"], root=str(project_root(proj)),
            desk_dir=str(desk_dir(proj)), queue_path=str(queue_path(proj)),
            proposal_path=str(prop),
        )
        fs = founding_sentence_block(
            proj, instruction="open 'What This Project Is' with it, quoted")
        prompt = (fs + "\n\n" if fs else "") + PROPOSE_PROMPT.format(**fields)
        # Single-source schema + cold-re-entry brief standard (kits/prompts/queue-schema.md).
        if QUEUE_SCHEMA:
            prompt += "\n\n" + QUEUE_SCHEMA
        kit_ctx = kits.as_context(
            kits.for_project(proj, APPDIR / "kits", load_settings()), "found")
        if kit_ctx:
            prompt += "\n\n" + kit_ctx
        sc = scope_note(proj)
        if sc:
            prompt += "\n\n" + sc
        cmd = build_turn_cmd(
            prompt, task="setup", request_model=d.get("model"),
            session_id=sid, name=session_name(proj), tools_tier="sweep",
        )

        def persist(new_sid):
            kw = {
                "session_id": new_sid,
                "status": "proposing",
                "name": session_name(proj),
            }
            if turn_model:
                kw["model"] = turn_model
            save_session(proj, **kw)

        self.run_curator(cmd, str(project_root(proj)), prior_sid=sid, persist=persist,
                         role="founding-curator")
        # Ensure proposing even if the agent forgot to set status mid-stream. Propose
        # never founds the desk: that is Found Desk's job, after the user approves.
        if proposal_on_disk(proj) or desk_is_proposing(proj) or any(
                is_proposal_entry(e) for e in (load_queue(proj).get("entries") or [])):
            save_session(proj, status="proposing")
            ensure_proposal_entry(proj)

    # ---- approve proposal (or legacy): digest proposal / found desk + first content batch ----
    def found(self, d):
        proj = get_project(d.get("project"))
        if desk_is_founded(proj):
            self.stream_idle("Desk already founded. Use refound to start over.")
            return
        if mark_founded_if_filed(proj, founding_step=True):
            self.stream_idle("Queue already has content entries — marked founded.")
            return
        turn_model = current_curator().model_for("setup", d.get("model"))
        sid = session_id_for_curator(proj=proj, model=turn_model)
        if not sid:
            sid = session_id_for_curator(
                proj=proj, model=current_curator().model_for("chat", d.get("model")))
        has_proposal = proposal_on_disk(proj)
        prompt = build_found_prompt(proj, session_id=sid)
        cmd = build_turn_cmd(
            prompt, task="setup", request_model=d.get("model"),
            session_id=sid, name=session_name(proj), tools_tier="sweep",
        )

        def persist(new_sid):
            kw = {
                "session_id": new_sid,
                "status": "proposing" if has_proposal else "interviewing",
                "name": session_name(proj),
            }
            if turn_model:
                kw["model"] = turn_model
            save_session(proj, **kw)

        self.run_curator(cmd, str(project_root(proj)), prior_sid=sid, persist=persist,
                         role="founding-curator")
        if not mark_founded_if_filed(proj, founding_step=True):
            ensure_proposal_entry(proj)  # keep the proposal openable after a failed Found

    def run_curator(self, cmd, cwd, prior_sid=None, persist=None, record_user_message=None,
                    role="agent", notice=None, on_finish=None):
        """Spawn the active curator CLI; forward normalized events as ndjson to the client.

        Stream parsing, usage accounting, and transcript capture live in `runtime.py` —
        the viewport-neutral adapter any future CLI viewport drives too. This method is the
        HTTP/process glue: own the response, forward each normalized event, map the init
        session-id to the caller's `persist` hook, and (when `record_user_message` is set)
        append the turn to the desk's own ledger at `<root>/.kettle/sessions/<id>.jsonl`
        — so continuity is the desk's, not the agent process's. Event shapes are unchanged
        (model/text/tool/done/error); `usage` is additive and ignored by older frontends;
        `done.ctx` is now true single-call occupancy, not the turn's summed aggregate.

        `on_finish(outcome)` (optional) is called exactly once with
        `{"ok": bool, "exit": int | None, "error": str | None}` — ok only when the CLI
        exited cleanly, reported no error event, and the client stayed to the end."""
        proc = None
        has_streamed = False

        def finish(ok: bool, error: str | None) -> None:
            if on_finish is None:
                return
            try:
                on_finish({"ok": ok, "error": error,
                           "exit": proc.returncode if proc is not None else None})
            except Exception:  # noqa: BLE001 — bookkeeping must not break the stream
                pass

        try:
            # stderr merged into stdout: a second unread pipe can deadlock the CLI mid-stream
            proc = subprocess.Popen(
                cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                env=runtime.curator_env(),
            )
        except Exception as exc:  # noqa: BLE001 — executable missing / spawn refused
            msg = runtime.spawn_error_text(cmd, exc, current_curator().provider)
            finish(False, msg)
            self.send_err(500, msg, "curator_unavailable")
            return

        # From this point the response belongs to the NDJSON stream. Any later failure is
        # represented as stream events; never attempt a second HTTP response.
        has_streamed = True
        self.send_response(200)
        self.send_header("Content-Type", "application/x-ndjson; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()

        if notice:  # e.g. a read-only downgrade acknowledgement, before curator output
            self.stream_line({"t": "text", "s": str(notice) + "\n\n"})

        assert proc.stdout is not None
        meter = runtime.UsageMeter()
        cap = {"sid": prior_sid, "text": [], "tools": [], "edits": []}
        noise: list[str] = []  # non-JSON CLI chatter (e.g. Grok resume 404)
        saw_error_evt = False
        failure: list[str] = []  # first reason this turn did not complete cleanly
        done_sent = False
        pending_done = None
        client_gone = False
        idle_timeout = curator_idle_timeout_s()

        def emit(evt) -> bool:
            nonlocal done_sent
            if done_sent:
                return False
            if evt.get("t") == "done":
                done_sent = True
            return self.stream_line(evt)

        def stop_process() -> None:
            if proc.poll() is None:
                proc.kill()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=10)

        def on_session(new_sid):
            cap["sid"] = new_sid
            if persist and new_sid and new_sid != prior_sid:
                persist(new_sid)  # immediately, so a fast next turn finds the session

        line_queue: queue.Queue = queue.Queue()
        eof = object()

        def read_stdout() -> None:
            try:
                for line in proc.stdout:
                    line_queue.put(line)
            except Exception as exc:  # noqa: BLE001 — surface reader failures in handler thread
                line_queue.put(exc)
            finally:
                line_queue.put(eof)

        threading.Thread(target=read_stdout, daemon=True,
                         name="kettle-curator-stdout").start()
        last_event_at = [time.monotonic()]

        def iter_lines():
            while True:
                remaining = idle_timeout - (time.monotonic() - last_event_at[0])
                if remaining <= 0:
                    raise TimeoutError(
                        f"curator idle timeout after {idle_timeout:g}s without an event")
                try:
                    item = line_queue.get(timeout=remaining)
                except queue.Empty as exc:
                    raise TimeoutError(
                        f"curator idle timeout after {idle_timeout:g}s without an event") from exc
                if item is eof:
                    return
                if isinstance(item, Exception):
                    raise item
                raw = item.rstrip("\n")
                stripped = raw.strip()
                if stripped and not stripped.startswith("{"):
                    noise.append(stripped)
                yield item

        try:
            for evt in runtime.normalize(iter_lines(), meter, on_session):
                last_event_at[0] = time.monotonic()
                if evt["t"] == "text":
                    cap["text"].append(evt["s"])
                elif evt["t"] == "tool":
                    cap["tools"].append(evt["s"])
                    if evt.get("tool") in lineage.WRITE_TOOLS and evt.get("path"):
                        cap["edits"].append(evt["path"])
                elif evt["t"] == "error":
                    saw_error_evt = True
                    failure.append(str(evt.get("s") or "curator reported an error"))
                if evt["t"] == "done":
                    pending_done = evt
                    break
                if not emit(evt):  # client gone
                    client_gone = True
                    failure.append("client disconnected; curator stopped")
                    stop_process()
                    break
            if not client_gone:
                proc.wait(timeout=10)
            if proc.returncode not in (0, None, -9) and not saw_error_evt:
                detail = next(
                    (n for n in reversed(noise)
                     if n.lower().startswith("error") or "not found" in n.lower()),
                    noise[-1] if noise else None,
                )
                msg = (f"{detail} (exit {proc.returncode})" if detail
                       else f"curator exited {proc.returncode}")
                failure.append(msg)
                emit({"t": "error", "s": msg})
            elif proc.returncode not in (0, None):
                failure.append(f"curator exited {proc.returncode}")
            emit(pending_done or {"t": "done"})
        except TimeoutError as exc:
            failure.append(str(exc))
            stop_process()
            if has_streamed:
                emit({"t": "error", "s": str(exc)})
                emit({"t": "done"})
        except Exception as e:  # noqa: BLE001
            failure.append(str(e) or type(e).__name__)
            stop_process()
            if has_streamed:
                emit({"t": "error", "s": str(e)})
                emit({"t": "done"})
        finally:
            if record_user_message is not None and cap["sid"]:
                try:
                    runtime.SessionLedger(
                        desk_dir({"root": cwd}) / "sessions"
                    ).append_turn(
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
                failure.append("curator still running at stream end; stopped")
                stop_process()
            if has_streamed and not done_sent:
                emit({"t": "done"})
            finish(not failure, failure[0] if failure else None)

    # Back-compat alias for tests / older call sites
    run_claude = run_curator


# ---------- entry points ----------

def _record_bind(port: int) -> None:
    """Stamp identity globals + ~/.cache/kettle/server.json after a successful bind.

    Shared by `start_server` (tests / daemon) and `main` (blocking sidecar / CLI web).
    Generates a per-boot token (mode 0600 discovery file). `/api/ping` remains the
    identity authority; the cache also carries the token viewports must send.
    """
    global SERVER_PORT, SERVER_STARTED, SERVER_TOKEN
    SERVER_PORT = port
    SERVER_STARTED = subprocess.run(
        ["date", "+%Y-%m-%dT%H:%M:%S%z"],
        capture_output=True, text=True,
    ).stdout.strip()
    SERVER_TOKEN = secrets.token_urlsafe(32)
    try:
        RUNTIME_PATH.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "pid": os.getpid(),
            "port": SERVER_PORT,
            "started": SERVER_STARTED,
            "url": f"http://127.0.0.1:{SERVER_PORT}/",
            "projects": str(PROJECTS_PATH),
            "settings": str(SETTINGS_PATH),
            "token": SERVER_TOKEN,
        }
        # Atomic write at mode 0600 so the token is not world-readable.
        tmp = RUNTIME_PATH.with_name(RUNTIME_PATH.name + ".tmp")
        fd = os.open(str(tmp), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(json.dumps(payload))
        os.replace(tmp, RUNTIME_PATH)
        try:
            os.chmod(RUNTIME_PATH, 0o600)
        except OSError:
            pass
    except OSError:
        pass


def _discovery_token() -> str | None:
    """Token from the discovery file (for circuit-breaker ping of a live predecessor)."""
    try:
        data = json.loads(RUNTIME_PATH.read_text(encoding="utf-8"))
        tok = data.get("token")
        return tok if isinstance(tok, str) and tok else None
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        return None


def start_server(port: int = 0) -> tuple[ThreadingHTTPServer, int]:
    """Start in a daemon thread; returns (server, bound_port)."""
    srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    _record_bind(srv.server_address[1])
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, SERVER_PORT


def _ping_kettle(port: int, timeout: float = 0.8) -> dict | None:
    """Answer of /api/ping for Kettle or its transitional Setsweep predecessor."""
    try:
        req = urllib.request.Request(f"http://127.0.0.1:{port}/api/ping")
        tok = _discovery_token()
        if tok:
            req.add_header(TOKEN_HEADER, tok)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            j = json.loads(r.read())
            return j if j.get("app") in {"kettle", "setsweep"} else None
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


def prepare_bind(port: int = DEFAULT_PORT, replace: bool = False) -> int | None:
    """Decide which port to bind under the circuit-breaker.

    Returns:
      port to bind (may equal the preferred port), or
      None if a healthy current kettle already holds the port (caller should defer).

    Retires a predecessor only when stale or `replace` is True. Does not fall back to
    an ephemeral port — callers that hit OSError on bind may try port 0 themselves.
    """
    info = _ping_kettle(port)
    pid = info.get("pid") if info else None
    if pid and pid != os.getpid():
        if replace or _predecessor_is_stale(info or {}):
            _retire(pid)
        else:
            return None
    return port


def start_server_preferred(port: int = DEFAULT_PORT,
                           replace: bool = False) -> tuple[ThreadingHTTPServer, int] | None:
    """Claim the fixed port (daemon thread).

    Circuit-breaker (2026-06-13): a bare launch must NEVER kill a healthy, CURRENT
    predecessor — that turned every stray relaunch into the user's window vanishing
    mid-sitting. We retire a responding kettle predecessor ONLY if it is stale
    (started before the current code) or the launch is explicit (`--replace`).

    Returns:
      (server, port) — this process bound the port and is now serving.
      None           — a healthy current kettle already holds the port; the caller
                       should defer (do not open a second window; do not kill anything).
    A foreign (non-kettle) occupant → fall back to an ephemeral port (returns a tuple).
    We kill only a pid that ANSWERED our ping — never on the say-so of a stale state file.
    """
    claimed = prepare_bind(port, replace=replace)
    if claimed is None:
        return None
    try:
        return start_server(claimed)
    except OSError:
        return start_server(0)


def main():
    """Blocking web entry (CLI `kettle --web`, desktop sidecar).

    Same identity recording as `start_server`. On the default port (no `--port`),
    applies the circuit-breaker via `prepare_bind` so `--replace` actually works
    and a healthy live window is not killed by a stray relaunch.
    """
    args = sys.argv[1:]
    replace = "--replace" in args
    explicit_port = "--port" in args
    port = DEFAULT_PORT
    if explicit_port:
        port = int(args[args.index("--port") + 1])
    # Always run the circuit-breaker — including with explicit --port — so
    # `kettle --web --port 4242 --replace` (plugin Restart Core) actually
    # retires the predecessor. Previously --port skipped prepare_bind and
    # hit "Address already in use" while the stale process kept serving.
    claimed = prepare_bind(port, replace=replace)
    if claimed is None:
        url = f"http://127.0.0.1:{port}/"
        print(f"kettle already running at {url} — deferring (pass --replace to restart)")
        return 0
    port = claimed

    try:
        srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    except OSError:
        if explicit_port:
            raise
        # Foreign occupant or race on the default port → ephemeral fallback
        srv = ThreadingHTTPServer(("127.0.0.1", 0), Handler)

    _record_bind(srv.server_address[1])
    url = f"http://127.0.0.1:{SERVER_PORT}/"
    print(f"desk · {url}\nprojects: {PROJECTS_PATH}")
    print("CLI: kettle projects | add | queue | chat …")
    if "--no-open" not in args:
        threading.Timer(0.4, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nbye")
    return 0


if __name__ == "__main__":
    raise SystemExit(main() or 0)
