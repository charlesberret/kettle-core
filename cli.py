#!/usr/bin/env python3
"""kettle — a command-line viewport over the same desk.

Proof of DESIGN.md §3 ("the desk is the application; the app is a viewport"): this driver
runs **no HTTP server**. It shares the web app's logic only through the desk helpers in
`server.py` (importing them is side-effect-free) and the agent adapter in `runtime.py`.
The desk is plain files in `<root>/.kettle/`; this renders and drives them from the
terminal — and edits go through your own `$EDITOR`, which is less to build and captures
your edits where the lineage reconciler can see them.

  kettle projects                list registered desks
  kettle add     <folder>        register a folder as a desk (first-run)
  kettle init                    register the current folder as a desk
  kettle found   <project>       curator founds the desk: charter, memory, first queue
  kettle queue   <project>       show a desk's queue
  kettle open    <project> <id>  show the brief, then open the file in $EDITOR
  kettle lineage <project>       who edited what: agent / user / unattributed
  kettle bind    <project>       add the lineage directive to the project's CLAUDE.md
  kettle chat    <project> [id]  converse with the resident curator — resumes the
                                    project session, shows the corrected token meter
                                    after each turn, records turns to the desk ledger
  kettle sweep-status <project>  mechanical CLOSE readiness (quiet / judgment / accrue)
  kettle sweep-close  <project>  quiet CLOSE: stage · archive · thin session log
  kettle sweep-archive <project>  archive queue entries (after judgment)
  kettle refresh-briefs <project> rewrite cold-re-entry briefs on the current queue
  kettle egress <project>        stage a desk egress memo (.kettle/outbound/)
  kettle egress-status <project> list staged egress memos
  kettle doctor                  install health (which kettle, py-modules mapping)

Run: python3 cli.py <command> …    (PROJECTS via DESK_PROJECTS env, same as the server)
"""
from __future__ import annotations

import argparse
import importlib.metadata
import importlib.util
import json
import os
import subprocess
import sys
import tomllib
from pathlib import Path

import egress
import lineage
import runtime
import server
import sweepkit

# Canonical install (brief 20). Doctor flags any other winner on PATH.
CANONICAL_VENV = Path.home() / ".kettle-venv"
CANONICAL_KETTLE = CANONICAL_VENV / "bin" / "kettle"
DIST_NAME = "kettle"


def _k(n) -> str:
    n = int(n or 0)
    return f"{n/1000:.0f}k" if n >= 1000 else str(n)


def _which_all(cmd: str = "kettle") -> list[Path]:
    """Every executable `cmd` on PATH, in resolution order (no duplicates)."""
    seen: set[str] = set()
    out: list[Path] = []
    for raw in os.environ.get("PATH", "").split(os.pathsep):
        if not raw:
            continue
        candidate = Path(raw).expanduser() / cmd
        try:
            if not candidate.is_file() or not os.access(candidate, os.X_OK):
                continue
            key = str(candidate.resolve()) if candidate.exists() else str(candidate)
        except OSError:
            key = str(candidate)
        if key in seen:
            continue
        seen.add(key)
        out.append(candidate)
    return out


def _py_modules_from_pyproject(path: Path | None = None) -> list[str]:
    """Read the setuptools py-modules list from pyproject.toml (source of truth)."""
    if path is None:
        # Prefer the live source tree next to this module (editable install).
        path = Path(__file__).resolve().parent / "pyproject.toml"
    if not path.is_file():
        return []
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    modules = data.get("tool", {}).get("setuptools", {}).get("py-modules") or []
    return [str(m) for m in modules]


def _installed_top_level(dist_name: str = DIST_NAME) -> list[str] | None:
    """Names recorded in the installed distribution's top_level.txt, or None if missing."""
    try:
        dist = importlib.metadata.distribution(dist_name)
    except importlib.metadata.PackageNotFoundError:
        return None
    text = dist.read_text("top_level.txt")
    if text is None:
        return None
    return [line.strip() for line in text.splitlines() if line.strip()]


def install_doctor_checks(
    *,
    path_hits: list[Path] | None = None,
    py_modules: list[str] | None = None,
    top_level: list[str] | None | object = ...,
    canonical: Path = CANONICAL_KETTLE,
) -> list[dict]:
    """Read-only install health rows for `kettle doctor` (brief 20; expanded by brief 18).

    Each row: {name, ok, detail, docs}. `ok` False means doctor should exit nonzero.
    """
    rows: list[dict] = []
    hits = path_hits if path_hits is not None else _which_all("kettle")
    modules = py_modules if py_modules is not None else _py_modules_from_pyproject()
    if top_level is ...:
        top_level = _installed_top_level()

    # --- which kettle ---
    if not hits:
        rows.append({
            "name": "kettle-on-path",
            "ok": False,
            "detail": "no `kettle` on PATH",
            "docs": "INSTALL.md § Canonical install",
        })
    else:
        first = hits[0]
        try:
            resolved = first.resolve()
            canon = canonical.expanduser().resolve()
            is_canon = resolved == canon
        except OSError:
            resolved = first
            is_canon = False
        rows.append({
            "name": "kettle-on-path",
            "ok": is_canon,
            "detail": (
                f"resolves to {first}"
                + (f" → {resolved}" if resolved != first else "")
                + ("" if is_canon else f" (canonical is {canonical})")
            ),
            "docs": "INSTALL.md § Canonical install",
        })
        extras = hits[1:]
        if extras:
            rows.append({
                "name": "kettle-path-extras",
                "ok": False,
                "detail": f"{len(extras)} extra on PATH: "
                          + ", ".join(str(p) for p in extras),
                "docs": "INSTALL.md § PATH retirement checklist",
            })
        else:
            rows.append({
                "name": "kettle-path-extras",
                "ok": True,
                "detail": "single kettle on PATH",
                "docs": "INSTALL.md § Canonical install",
            })

    # --- py-modules importable + present in installed top_level ---
    if not modules:
        rows.append({
            "name": "py-modules-list",
            "ok": False,
            "detail": "could not read tool.setuptools.py-modules from pyproject.toml",
            "docs": "INSTALL.md § Reinstall rule",
        })
        return rows

    rows.append({
        "name": "py-modules-list",
        "ok": True,
        "detail": f"{len(modules)} modules in pyproject.toml",
        "docs": "pyproject.toml py-modules",
    })

    if top_level is None:
        rows.append({
            "name": "install-mapping",
            "ok": False,
            "detail": f"distribution {DIST_NAME!r} not installed in this interpreter "
                      f"({sys.executable})",
            "docs": "INSTALL.md § Reinstall rule",
        })
    else:
        missing_map = [m for m in modules if m not in top_level]
        if missing_map:
            rows.append({
                "name": "install-mapping",
                "ok": False,
                "detail": "py-modules missing from installed top_level (reinstall editable): "
                          + ", ".join(missing_map),
                "docs": "INSTALL.md § Reinstall rule",
            })
        else:
            rows.append({
                "name": "install-mapping",
                "ok": True,
                "detail": "installed top_level covers py-modules",
                "docs": "INSTALL.md § Reinstall rule",
            })

    missing_import = []
    for name in modules:
        try:
            spec = importlib.util.find_spec(name)
        except (ImportError, ModuleNotFoundError, ValueError):
            spec = None
        if spec is None:
            missing_import.append(name)
    if missing_import:
        rows.append({
            "name": "py-modules-importable",
            "ok": False,
            "detail": "not importable (stale editable MAPPING?): "
                      + ", ".join(missing_import),
            "docs": "INSTALL.md § Reinstall rule",
        })
    else:
        rows.append({
            "name": "py-modules-importable",
            "ok": True,
            "detail": f"all {len(modules)} py-modules importable",
            "docs": "INSTALL.md § Reinstall rule",
        })

    return rows


def _resolve(proj: dict, path: str) -> Path:
    p = Path(path)
    return p if p.is_absolute() else server.project_root(proj) / p


# ---------- read-only views ----------

def _projects_or_empty() -> list:
    try:
        return server.load_projects()
    except Exception:  # noqa: BLE001 — missing/empty/corrupt registry ⇒ first-run empty
        return []


def cmd_projects(_args) -> int:
    projs = _projects_or_empty()
    if not projs:
        print("no desks registered yet.")
        print("  register one:        kettle add <folder>")
        print("  or, inside a folder: kettle init")
        return 0
    for p in projs:
        root = server.project_root(p)
        mark = "" if root.exists() else "   (root missing)"
        print(f"{p['id']:<14} {p.get('name', p['id'])}{mark}")
        print(f"{'':<14} {root}")
    return 0


def _default_name(path: str) -> str:
    base = Path(path).expanduser().resolve().name
    return base.replace("-", " ").replace("_", " ").title() or "Project"


def cmd_add(args) -> int:
    """Register a folder as a desk (shares the server's validation + fence gate)."""
    name = args.name or _default_name(args.path)
    try:
        proj = server.register_project(name, args.path)
    except ValueError as e:
        print(f"could not register: {e}", file=sys.stderr)
        return 2
    print(f"registered [{proj['id']}] {proj['name']}")
    print(f"  root: {server.project_root(proj)}")
    print(f"  desk: {server.desk_dir(proj)}  (queue seeded — awaiting founding)")
    print(f"\nnext:  kettle chat  {proj['id']}     # talk to the curator, found the desk")
    print(f"       kettle queue {proj['id']}     # see what's been filed")
    return 0


def cmd_init(args) -> int:
    """Register the current directory as a desk."""
    args.path = "."
    return cmd_add(args)


def cmd_lineage(args) -> int:
    """Show who edited what since the baseline — agent / user / unattributed — or
    re-baseline (--accept) to mark the current tree as seen."""
    proj = server.get_project(args.project)
    root = server.project_root(proj)
    if args.accept:
        giton = bool(server.load_settings().get("lineage_git"))
        m = lineage.accept_baseline(root, git=giton)
        print(f"baseline set — {len(m['files'])} files marked as seen ({m['ts']})"
              + (" · git history updated" if giton else "") + ".")
        return 0
    st = lineage.status(root)
    if st["baseline_ts"] is None:
        print(f"{proj['id']}: no lineage baseline yet.")
        print(f"  set one:  kettle lineage {proj['id']} --accept")
        return 0
    c = st["counts"]
    print(f"lineage — {proj['id']}   (baseline {st['baseline_ts']})")
    print(f"  agent {c['agent']}  ·  user {c['user']}  ·  unattributed {c['unattributed']}")
    if not st["changes"]:
        print("  clean — nothing changed since the baseline.")
        return 0
    print()
    for ch in st["changes"]:
        by = f"  by {ch['by']}" if ch.get("by") else ""
        print(f"  {ch['status']:<13} {ch['change']:<9} {ch['path']}{by}")
    if c["unattributed"]:
        print(f"\n{c['unattributed']} unattributed — changed outside the app, source unconfirmed.")
        print(f"  review, then re-baseline:  kettle lineage {proj['id']} --accept")
    return 0


def cmd_bind(args) -> int:
    """Add the fenced lineage directive to the project's CLAUDE.md (transparent + idempotent)
    so any agent working in the tree self-records its edits."""
    proj = server.get_project(args.project)
    r = lineage.ensure_directive(server.project_root(proj))
    print(f"lineage directive {r['action']} in {r['file']}")
    if r["editing_created"]:
        print(f"  wrote {server.desk_dir(proj)}/EDITING.md (the protocol)")
    print("  agents in this tree now carry the attribution directive + the .kettle pointer.")
    return 0


def cmd_found(args) -> int:
    """Found the desk: digests DESK-PROPOSAL.md when present, else one-shot from files /
    interview session. Mirrors the server's found()."""
    proj = server.get_project(args.project)
    sid = server.load_session(proj).get("session_id")
    fields = dict(
        name=proj["name"], root=str(server.project_root(proj)),
        desk_dir=str(server.desk_dir(proj)), queue_path=str(server.queue_path(proj)),
        proposal_path=str(server.proposal_path(proj)),
    )
    if server.proposal_on_disk(proj):
        prompt = server.FOUND_PROMPT.format(**fields)
    elif sid:
        prompt = server.FOUND_LEGACY_PROMPT.format(**fields)
    else:
        prompt = server.BOOTSTRAP_PROMPT.format(
            name=proj["name"], root=str(server.project_root(proj)),
            desk_dir=str(server.desk_dir(proj)), queue_path=str(server.queue_path(proj)),
        )
    # Resolve the provider from settings exactly as the HTTP routes do, and let
    # build_turn_cmd → runtime.build_argv single-source the sweep tier (write powers,
    # confined by cwd + acceptEdits) and the dialect flags — no Claude hardcoding.
    cfg = server.current_curator()
    cmd = server.build_turn_cmd(
        prompt, task="setup", request_model=args.model,
        session_id=sid, name=server.session_name(proj), tools_tier="sweep",
    )
    rt = runtime.Runtime(server.agent_bin(), server.desk_dir(proj) / "sessions",
                         provider=cfg.provider)
    print(f"· founding {proj['id']} — the curator surveys {server.project_root(proj)} …\n")
    for ev in rt.spawn(prompt, cwd=str(server.project_root(proj)), session_id=sid,
                       role="found", cmd=cmd):
        t = ev["t"]
        if t == "text":
            sys.stdout.write(ev["s"]); sys.stdout.flush()
        elif t == "tool":
            sys.stdout.write(f"\n  ⚙ {ev['s']}\n"); sys.stdout.flush()
        elif t == "model":
            new = ev.get("session")
            if new and new != sid:
                sid = new
                server.save_session(proj, session_id=sid, status="interviewing",
                                    name=server.session_name(proj))
        elif t == "done":
            u = ev.get("usage") or {}
            print(f"\n  [ctx {_k(u.get('context'))}/{_k(u.get('window'))} · ${ev.get('cost') or 0:.3f}]")
            if ev.get("error"):
                print(f"  [agent error: {ev['error']}]")
        elif t == "error":
            print(f"\n  [error: {ev['s']}]")
    founded = server.mark_founded_if_filed(proj)
    n = len(server.load_queue(proj).get("entries", []))
    print(f"\n{'✓ founded' if founded else '✗ not yet founded'} — "
          f"{n} entr{'y' if n == 1 else 'ies'} in the queue.")
    if founded:
        print(f"next:  kettle queue {proj['id']}   ·   "
              f"kettle chat {proj['id']} <entry-id>")
    else:
        print("(no entries filed — run `kettle found` again, or read the survey above.)")
    return 0


def cmd_queue(args) -> int:
    proj = server.get_project(args.project)
    entries = server.load_queue(proj).get("entries", [])
    if not entries:
        print(f"{proj['id']}: queue empty")
        return 0
    print(f"{proj['id']} — {len(entries)} in queue\n")
    for e in entries:
        title = e.get("title") or Path(e["path"]).name
        print(f"  [{e['id']}] {title}   <{e.get('status', '?')}>")
        print(f"        {e['path']}")
        if e.get("ask"):
            print(f"        ask:   {e['ask']}")
        if e.get("brief"):
            brief = " ".join(str(e["brief"]).split())
            print(f"        brief: {brief[:200]}")
        print()
    return 0


def cmd_refresh_briefs(args) -> int:
    """Rewrite brief + ask on every entry currently in the queue (no archive/restock)."""
    proj = server.get_project(args.project)
    prompt = server.build_refresh_briefs_prompt(proj)
    if prompt is None:
        print(f"{proj['id']}: queue empty — nothing to refresh")
        return 0
    n = len(server.load_queue(proj).get("entries") or [])
    sid = server.load_session(proj).get("session_id")
    cfg = server.current_curator()
    cmd = server.build_turn_cmd(
        prompt, task="setup", request_model=args.model,
        session_id=sid, name=server.session_name(proj), tools_tier="sweep",
    )
    rt = runtime.Runtime(server.agent_bin(), server.desk_dir(proj) / "sessions",
                         provider=cfg.provider)
    print(f"· refreshing briefs on {proj['id']} — {n} entr"
          f"{'y' if n == 1 else 'ies'} …\n")
    for ev in rt.spawn(prompt, cwd=str(server.project_root(proj)), session_id=sid,
                       role="refresh-briefs", cmd=cmd):
        t = ev["t"]
        if t == "text":
            sys.stdout.write(ev["s"]); sys.stdout.flush()
        elif t == "tool":
            sys.stdout.write(f"\n  ⚙ {ev['s']}\n"); sys.stdout.flush()
        elif t == "model":
            new = ev.get("session")
            if new and new != sid:
                sid = new
                server.save_session(proj, session_id=sid, name=server.session_name(proj))
        elif t == "done":
            u = ev.get("usage") or {}
            print(f"\n  [ctx {_k(u.get('context'))}/{_k(u.get('window'))} · ${ev.get('cost') or 0:.3f}]")
            if ev.get("error"):
                print(f"  [agent error: {ev['error']}]")
        elif t == "error":
            print(f"\n  [error: {ev['s']}]")
    print(f"\nnext:  kettle queue {proj['id']}")
    return 0


def cmd_open(args) -> int:
    proj = server.get_project(args.project)
    entry = server.find_entry(server.load_queue(proj), args.id)
    print(f"[{entry['id']}] {entry.get('title') or Path(entry['path']).name}")
    if entry.get("ask"):
        print(f"ask:   {entry['ask']}")
    if entry.get("brief"):
        print(f"brief: {' '.join(str(entry['brief']).split())}")
    path = _resolve(proj, entry["path"])
    editor = os.environ.get("EDITOR") or "vi"
    print(f"\nopening {path} in {editor} …")
    return subprocess.call([editor, str(path)])


# ---------- the curator conversation ----------

def cmd_chat(args) -> int:
    proj = server.get_project(args.project)
    sess = server.load_session(proj)
    sid = sess.get("session_id")
    last_entry = sess.get("last_entry")
    entry = server.find_entry(server.load_queue(proj), args.id) if args.id else None
    cfg = server.current_curator()
    rt = runtime.Runtime(server.agent_bin(), server.desk_dir(proj) / "sessions",
                         provider=cfg.provider)
    root = str(server.project_root(proj))

    where = f"file [{entry['id']}]" if entry else "project-level"
    print(f"· {proj['id']} — {where} — "
          f"{'resuming session' if sid else 'new session'} · :q to quit")

    while True:
        try:
            msg = input("\nyou> ").strip()
        except EOFError:
            break
        if not msg:
            continue
        if msg in (":q", ":quit", "exit"):
            break

        message = msg
        # announce the active file only on the first turn or a file switch (the session
        # carries it thereafter) — the same rule the web chat uses
        if entry and (not sid or entry["id"] != last_entry):
            message = server.CONTEXT_BLOCK.format(
                path=entry["path"], brief=entry.get("brief", "(none prepared)"),
                ask=entry.get("ask", "general review")) + msg

        sysprompt = None
        if not sid:  # first turn: orient the curator, name the session
            role = proj.get("role") or server.DEFAULT_ROLE
            sysprompt = role.format(
                path=(entry["path"] if entry else "(no file selected)"),
                project=proj["name"],
                brief=(entry.get("brief", "(none prepared)") if entry else "(none prepared)"),
                ask=(entry.get("ask", "general review") if entry else "general review"))
            orient = server.project_orientation(proj)
            if orient:
                sysprompt += "\n\n" + orient

        # Same single source as the HTTP routes: build_turn_cmd resolves the provider
        # from settings and maps the "agent" tier + dialect flags. The CLI review chat
        # keeps its established (agent-tier) write powers, now provider-correct.
        cmd = server.build_turn_cmd(
            message, task="chat", request_model=args.model,
            session_id=sid, system_append=sysprompt,
            name=server.session_name(proj), tools_tier="agent",
        )

        server.save_session(proj, **({"last_entry": entry["id"]} if entry else {}),
                            name=server.session_name(proj))

        sys.stdout.write("\ncurator> ")
        sys.stdout.flush()
        for ev in rt.spawn(message, cwd=root, session_id=sid, role="chat", cmd=cmd):
            t = ev["t"]
            if t == "text":
                sys.stdout.write(ev["s"])
                sys.stdout.flush()
            elif t == "tool":
                sys.stdout.write(f"\n  ⚙ {ev['s']}\n")
                sys.stdout.flush()
            elif t == "model":
                new = ev.get("session")
                if new and new != sid:
                    sid = new
                    server.save_session(proj, session_id=sid, name=server.session_name(proj))
            elif t == "done":
                u = ev.get("usage") or {}
                pct = int((u.get("fraction") or 0) * 100)
                print(f"\n  [ctx {_k(u.get('context'))}/{_k(u.get('window'))} · {pct}%"
                      f" · ${ev.get('cost') or 0:.3f}]")
                if ev.get("error"):
                    print(f"  [agent error: {ev['error']}]")
            elif t == "error":
                print(f"\n  [error: {ev['s']}]")
        last_entry = entry["id"] if entry else last_entry
    return 0


# ---------- sweep close-kit ----------

def cmd_sweep_status(args) -> int:
    st = sweepkit.assess_close(server.get_project(args.project))
    print(json.dumps(st, indent=2, default=str))
    return 0


def cmd_sweep_close(args) -> int:
    result = sweepkit.mechanical_close(server.get_project(args.project))
    print(json.dumps(result, indent=2, default=str))
    return 0 if result.get("ok") else 1


def cmd_sweep_archive(args) -> int:
    proj = server.get_project(args.project)
    ids = list(args.id) if args.id else None
    result = sweepkit.archive_queue(
        proj, only_approved=bool(args.approved_only), entry_ids=ids)
    print(json.dumps(result, indent=2, default=str))
    return 0


# ---------- desk egress ----------

def cmd_egress(args) -> int:
    body = args.body
    if body is None:
        if sys.stdin.isatty():
            print("kettle egress: pass --body or pipe the memo body on stdin", file=sys.stderr)
            return 2
        body = sys.stdin.read()
    try:
        result = egress.stage_egress(
            server.get_project(args.project),
            kind=args.kind,
            topic=args.topic,
            body=body,
            route=args.route,
        )
    except ValueError as e:
        print(f"egress: {e}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2))
    return 0


def cmd_egress_status(args) -> int:
    proj = server.get_project(args.project)
    egress.ensure_egress(proj)
    print(json.dumps({
        "project": proj.get("id"),
        "dir": str(egress.egress_dir(proj)),
        "staged": egress.list_staged(proj),
    }, indent=2))
    return 0


def cmd_doctor(_args) -> int:
    """Install health (brief 20). Brief 18 expands with server/curator/beacon rows."""
    rows = install_doctor_checks()
    width = max((len(r["name"]) for r in rows), default=8)
    failed = 0
    for r in rows:
        mark = "ok" if r["ok"] else "FAIL"
        if not r["ok"]:
            failed += 1
        print(f"  {mark:4}  {r['name']:<{width}}  {r['detail']}")
        if not r["ok"] and r.get("docs"):
            print(f"        → {r['docs']}")
    print()
    if failed:
        print(f"doctor: {failed} check(s) failed — see INSTALL.md")
        return 1
    print("doctor: all install checks green")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        prog="kettle", description="CLI viewport over the desk.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="examples:\n"
               "  kettle projects\n"
               "  kettle add     ~/work/notes        # register a folder\n"
               "  kettle init                        # register the current folder\n"
               "  kettle queue   kettle\n"
               "  kettle open    kettle refounding-merge\n"
               "  kettle chat    kettle               # talk to the desk\n"
               "  kettle chat    kettle <entry-id>    # about one file\n"
               "  kettle doctor                      # install health\n"
               "  kettle sweep-status kettle\n"
               "  kettle sweep-close  kettle\n"
               "  kettle refresh-briefs kettle\n"
               "  kettle egress kettle --kind launch --topic go-ahead --body '…'\n"
               "  kettle egress-status kettle\n")
    # not required: a bare `kettle` should greet with the menu, not error out
    sub = ap.add_subparsers(
        dest="cmd",
        metavar="{projects,add,init,found,queue,open,lineage,bind,chat,doctor,"
                "sweep-status,sweep-close,sweep-archive,refresh-briefs,egress,egress-status}")
    sub.add_parser("projects", help="list registered desks").set_defaults(fn=cmd_projects)
    sub.add_parser(
        "doctor",
        help="install health: which kettle, py-modules mapping (brief 20; brief 18 expands)",
    ).set_defaults(fn=cmd_doctor)
    a = sub.add_parser("add", help="register a folder as a desk")
    a.add_argument("path"); a.add_argument("--name", default=None); a.set_defaults(fn=cmd_add)
    i = sub.add_parser("init", help="register the current folder as a desk")
    i.add_argument("--name", default=None); i.set_defaults(fn=cmd_init)
    f = sub.add_parser("found", help="curator founds the desk (charter, memory, first queue)")
    f.add_argument("project"); f.add_argument("--model", default=None); f.set_defaults(fn=cmd_found)
    g = sub.add_parser("lineage", help="who edited what: agent / user / unattributed")
    g.add_argument("project"); g.add_argument("--accept", action="store_true",
                   help="re-baseline: mark the current tree as seen")
    g.set_defaults(fn=cmd_lineage)
    b2 = sub.add_parser("bind", help="add the lineage directive to the project's CLAUDE.md")
    b2.add_argument("project"); b2.set_defaults(fn=cmd_bind)
    q = sub.add_parser("queue", help="show a desk's queue"); q.add_argument("project"); q.set_defaults(fn=cmd_queue)
    o = sub.add_parser("open", help="open an entry's file in $EDITOR")
    o.add_argument("project"); o.add_argument("id"); o.set_defaults(fn=cmd_open)
    c = sub.add_parser("chat", help="converse with the resident curator")
    c.add_argument("project"); c.add_argument("id", nargs="?")
    c.add_argument("--model", default=None); c.set_defaults(fn=cmd_chat)
    ss = sub.add_parser("sweep-status", help="CLOSE readiness (quiet / judgment / accrue)")
    ss.add_argument("project"); ss.set_defaults(fn=cmd_sweep_status)
    sc = sub.add_parser("sweep-close", help="quiet mechanical CLOSE when safe")
    sc.add_argument("project"); sc.set_defaults(fn=cmd_sweep_close)
    sa = sub.add_parser("sweep-archive", help="archive queue entries (after judgment)")
    sa.add_argument("project")
    sa.add_argument("id", nargs="*", help="optional entry ids; default: whole queue")
    sa.add_argument("--approved-only", action="store_true",
                    help="archive approved entries only (inbox close)")
    sa.set_defaults(fn=cmd_sweep_archive)
    rb = sub.add_parser(
        "refresh-briefs",
        help="rewrite cold-re-entry briefs on the current queue (no restock)",
    )
    rb.add_argument("project")
    rb.add_argument("--model", default=None)
    rb.set_defaults(fn=cmd_refresh_briefs)
    eg = sub.add_parser("egress", help="stage a desk egress memo under .kettle/outbound/")
    eg.add_argument("project")
    eg.add_argument("--kind", required=True, choices=sorted(egress.KINDS))
    eg.add_argument("--topic", required=True)
    eg.add_argument("--route", default=None, help="routing hint (defaults by kind)")
    eg.add_argument("--body", default=None, help="memo body; else read stdin")
    eg.set_defaults(fn=cmd_egress)
    es = sub.add_parser("egress-status", help="list staged desk egress memos")
    es.add_argument("project"); es.set_defaults(fn=cmd_egress_status)
    args = ap.parse_args(argv)
    if not getattr(args, "fn", None):   # bare `kettle` → show the menu, exit clean
        ap.print_help()
        return 0
    try:
        return args.fn(args)
    except KeyError as e:
        print(f"not found: {e}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print()
        return 130


if __name__ == "__main__":
    sys.exit(main())
