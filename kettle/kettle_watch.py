#!/usr/bin/env python3
"""kettle-watch — the live folder-watch that makes the inbox kind work.

Run on a schedule (e.g. cron every 15 min, or a launchd/systemd timer). For each registered
project that carries an `intake` block, scan its watched folder, diff against a per-project
seen-set, and fire a *curate* agent per new file: it drafts a response into `responses/` and
files a queue entry (with a brief and the `source` path) so the item appears in the app's queue.
Drop a file in the folder; next cycle a drafted reply is waiting for you to edit and approve.

Self-contained — standard library, the sibling core modules, and the `claude` CLI on PATH:
  - Registry:      same resolution as core (`$DESK_PROJECTS`, Kettle user path,
                   legacy user path, then a source-checkout registry).
  - State + health: ~/.cache/kettle/ (watch-state.json, watch-health.json).

Cron example (with an editable install of kettle):
  */15 * * * *  /path/to/venv/bin/python /path/to/kettle/kettle_watch.py
or, since it installs a console script:
  */15 * * * *  kettle-watch
"""

import json
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
try:
    from . import kits  # the per-kind curator playbook (lens · urgency · first-queue heuristic)
except ImportError:
    kits = None
from .server import resolve_projects_path

HOME = Path.home()
PROJECTS = resolve_projects_path()
CACHE = HOME / ".cache" / "kettle"
STATE = CACHE / "watch-state.json"
HEALTH = CACHE / "watch-health.json"
CLAUDE = shutil.which("claude") or "claude"

INTAKE_IGNORE = {".kettle", ".setsweep", ".git", ".DS_Store"}
INTAKE_MAX_PER_RUN = 10                               # cap a big dump; the rest curate next cycle

CURATE_PROMPT = """You are the Kettle inbox curator for the {name} project (root: {root}).
A new item has arrived in the intake folder and needs curating into the review queue.

SOURCE ITEM (read-only — never edit it):  {source}
DRAFT A RESPONSE TO:                       {responses}/{stem}.md
QUEUE FILE (append one entry):             {queue}
{kit_ctx}
Do exactly this, in order:
1. READ the source item in full.
2. DRAFT a response to it at {responses}/{stem}.md — a real first draft the reviewer will edit by
   hand, in their voice as best you can infer it from MEMORY.md (at {desk_dir}/MEMORY.md) if present.
   This draft is a starting point, never a fait accompli; the reviewer's hand is the only thing that
   sends anything.
3. FILE one queue entry by reading {queue}, appending exactly one entry to its "entries" array, and
   writing it back (preserve every existing entry; valid JSON). The entry's shape:
   {{
     "id": "{stem}",                       // unique; if taken, suffix -2, -3…
     "title": "<short label for the item>",
     "path": "{responses}/{stem}.md",      // ABSOLUTE path to the DRAFT (what the reviewer edits)
     "project": "{pid}",
     "project_root": "{root}",
     "source": "{source}",                 // ABSOLUTE path to the incoming item this answers
     "ask_type": "judgment",
     "ask": "<what you want the reviewer to decide about this reply>",
     "urgency": "high|medium|low",         // per the kit's urgency rubric
     "status": "pending",
     "brief": "<a triage summary: who it's from, what it asks, the deadline/stakes, and how you
                handled it in the draft — the reviewer reads THIS instead of re-reading the item>"
   }}
Do nothing else. Finish with a one-line summary naming the item and the urgency you assigned."""


def log_health(curated: int, status: str = "ok", error_msg: str | None = None) -> None:
    """Self-contained healthbeacon — a one-object JSON the operator (or a dashboard) can read to
    see the watcher is alive and what it did. No external logging library."""
    CACHE.mkdir(parents=True, exist_ok=True)
    rec = {"last_run": datetime.now().isoformat(timespec="seconds"),
           "curated": curated, "status": status}
    if error_msg:
        rec["error"] = error_msg
    try:
        HEALTH.write_text(json.dumps(rec, indent=2))
    except OSError:
        pass


def _load_settings() -> dict:
    try:
        return json.loads((SCRIPT_DIR / "settings.json").read_text())
    except (OSError, json.JSONDecodeError):
        return {}


def mtime(p: Path) -> float:
    try:
        return p.stat().st_mtime
    except FileNotFoundError:
        return 0.0


def _desk_dir(proj: dict) -> Path:
    root = Path(proj["root"]).expanduser().resolve()
    current = root / ".kettle"
    legacy = root / ".setsweep"
    if current.exists() or not legacy.exists():
        return current
    return legacy


def _runtime_dir(proj: dict) -> Path:
    """Mirrors server.runtime_dir(): volatile state lives at <root>/.kettle/runtime/ (inside
    the agent's project-root fence). If you sync the tree, exclude .kettle/runtime/."""
    d = _desk_dir(proj) / "runtime"
    d.mkdir(parents=True, exist_ok=True)
    return d


def resolve_intake(proj: dict):
    """(watch_dir, responses_dir, outbound_dir, ignore_names) for a project with an `intake`
    block, or None. `watch` may be a folder, "." (project root), or a subdir; relatives join to
    the root. responses/outbound default under the root and are always ignored by the scan."""
    cfg = proj.get("intake")
    if not isinstance(cfg, dict) or not cfg.get("watch"):
        return None
    root = Path(proj["root"]).expanduser().resolve()

    def _resolve(val, default):
        p = Path(val).expanduser() if val else Path(default)
        return (p if p.is_absolute() else (root / p)).resolve()

    watch = _resolve(cfg["watch"], ".")
    responses = _resolve(cfg.get("responses"), "responses")
    outbound = _resolve(cfg.get("outbound"), "outbox")
    ignore = set(INTAKE_IGNORE) | {responses.name, outbound.name}
    return watch, responses, outbound, ignore


def scan_new(watch: Path, ignore: set, seen: set) -> list:
    """Top-level files in the watch dir not yet seen — oldest first, capped. Non-recursive (the
    drop-a-file model); skips dirs, dotfiles, the ignore-set, and prior-seen paths."""
    try:
        entries = sorted(watch.iterdir(), key=mtime)
    except OSError:
        return []
    out = []
    for p in entries:
        if p.name.startswith(".") or p.name in ignore or not p.is_file():
            continue
        if str(p) in seen:
            continue
        out.append(p)
    return out[:INTAKE_MAX_PER_RUN]


def normalize_queue(queue_file: Path, proj: dict) -> None:
    """Deterministically repair what the curate agent may have dropped: a missing/empty `status`
    defaults to 'pending' (so the app caches a diff baseline and approve has something to toggle),
    and `project`/`project_root` are backfilled. Never overwrites a real status. Atomic write."""
    try:
        q = json.loads(queue_file.read_text())
    except (OSError, json.JSONDecodeError):
        return
    root = str(Path(proj["root"]).expanduser().resolve())
    changed = False
    for e in q.get("entries", []):
        if not e.get("status"):
            e["status"] = "pending"; changed = True
        if not e.get("project"):
            e["project"] = proj["id"]; changed = True
        if not e.get("project_root"):
            e["project_root"] = root; changed = True
    if changed:
        tmp = queue_file.with_name(queue_file.name + ".intake-tmp")
        tmp.write_text(json.dumps(q, indent=2))
        tmp.replace(queue_file)


def intake_pass(proj: dict, st: dict, settings: dict) -> int:
    """Curate each new intake file into the queue. Returns the count curated this run."""
    resolved = resolve_intake(proj)
    if not resolved:
        return 0
    watch, responses, outbound, ignore = resolved
    seen = set(st.get("intake_seen", []))
    new_files = scan_new(watch, ignore, seen)
    if not new_files:
        return 0

    responses.mkdir(parents=True, exist_ok=True)
    root = Path(proj["root"]).expanduser()
    runtime_dir = _runtime_dir(proj)
    desk_dir = _desk_dir(proj)
    kit_ctx = ""
    if kits is not None:
        kit = kits.for_project(proj, SCRIPT_DIR / "kits", settings)
        lens = kits.as_context(kit, "review")
        firstq = kits.as_context(kit, "found")
        kit_ctx = ("\n" + "\n".join(c for c in (lens, firstq) if c) + "\n") if (lens or firstq) else ""

    curated = 0
    for src in new_files:                         # sequential: one queue.json writer at a time
        stem = "".join(c if (c.isalnum() or c in "-_") else "-" for c in src.stem).strip("-") or "item"
        prompt = CURATE_PROMPT.format(
            name=proj["name"], root=str(root), pid=proj["id"], source=str(src),
            responses=str(responses), stem=stem, queue=str(runtime_dir / "queue.json"),
            desk_dir=str(desk_dir), kit_ctx=kit_ctx,
        )
        cmd = [CLAUDE, "-p", prompt, "--output-format", "json",
               "--permission-mode", "acceptEdits",
               "--add-dir", str(watch),           # the source item may sit outside the project fence
               "--allowedTools", "Read", "Glob", "Grep", "Edit", "Write",
               "Bash(ls:*)", "Bash(cat:*)", "Bash(rg:*)", "Bash(fd:*)",
               "--disallowedTools", "NotebookEdit"]
        try:
            r = subprocess.run(cmd, cwd=str(root), capture_output=True, text=True, timeout=900)
        except subprocess.TimeoutExpired:
            log_health(curated, status="error", error_msg=f"{proj['id']}: curate timed out on {src.name}")
            break
        if r.returncode != 0:
            log_health(curated, status="error",
                       error_msg=f"{proj['id']}: curate failed on {src.name}: {r.stderr[-200:]}")
            break                                  # leave src unseen → retried next cycle
        seen.add(str(src))                         # mark seen only on success
        normalize_queue(runtime_dir / "queue.json", proj)   # repair agent omissions deterministically
        curated += 1
    st["intake_seen"] = sorted(seen)
    return curated


def main() -> int:
    if not CLAUDE or shutil.which(CLAUDE) is None and not Path(CLAUDE).exists():
        log_health(0, status="error", error_msg="`claude` CLI not found on PATH")
        sys.stderr.write("kettle-watch: `claude` CLI not found on PATH\n")
        return 1
    try:
        projects = json.loads(PROJECTS.read_text()).get("projects", [])
    except (OSError, json.JSONDecodeError) as e:
        log_health(0, status="error", error_msg=f"cannot read registry at {PROJECTS}: {e}")
        sys.stderr.write(f"kettle-watch: cannot read registry at {PROJECTS}: {e}\n")
        return 1

    settings = _load_settings()
    state = json.loads(STATE.read_text()) if STATE.exists() else {}
    curated = 0
    for proj in projects:
        st = state.setdefault(proj["id"], {})
        try:
            curated += intake_pass(proj, st, settings)
        except Exception as e:  # noqa: BLE001 — one bad project must not sink the run
            log_health(curated, status="error", error_msg=f"{proj.get('id')}: {e}")

    CACHE.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(state, indent=2))
    log_health(curated)
    sys.stderr.write(f"kettle-watch: curated {curated} new item(s)\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
