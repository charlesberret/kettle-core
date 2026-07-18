#!/usr/bin/env python3
"""setsweep — a command-line viewport over the same desk.

Proof of DESIGN.md §3 ("the desk is the application; the app is a viewport"): this driver
runs **no HTTP server**. It shares the web app's logic only through the desk helpers in
`server.py` (importing them is side-effect-free) and the agent adapter in `runtime.py`.
The desk is plain files in `<root>/.setsweep/`; this renders and drives them from the
terminal — and edits go through your own `$EDITOR`, which is less to build and captures
your edits where the lineage reconciler can see them.

  setsweep projects                list registered desks
  setsweep add     <folder>        register a folder as a desk (first-run)
  setsweep init                    register the current folder as a desk
  setsweep found   <project>       curator founds the desk: charter, memory, first queue
  setsweep queue   <project>       show a desk's queue
  setsweep open    <project> <id>  show the brief, then open the file in $EDITOR
  setsweep lineage <project>       who edited what: agent / user / unattributed
  setsweep bind    <project>       add the lineage directive to the project's CLAUDE.md
  setsweep chat    <project> [id]  converse with the resident curator — resumes the
                                    project session, shows the corrected token meter
                                    after each turn, records turns to the desk ledger
  setsweep sweep-status <project>  mechanical CLOSE readiness (quiet / judgment / accrue)
  setsweep sweep-close  <project>  quiet CLOSE: stage · archive · thin session log
  setsweep sweep-archive <project>  archive queue entries (after judgment)
  setsweep egress <project>        stage a desk egress memo (.setsweep/outbound/)
  setsweep egress-status <project> list staged egress memos

Run: python3 cli.py <command> …    (PROJECTS via DESK_PROJECTS env, same as the server)
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

import egress
import lineage
import runtime
import server
import sweepkit


def _k(n) -> str:
    n = int(n or 0)
    return f"{n/1000:.0f}k" if n >= 1000 else str(n)


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
        print("  register one:        setsweep add <folder>")
        print("  or, inside a folder: setsweep init")
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
    print(f"\nnext:  setsweep chat  {proj['id']}     # talk to the curator, found the desk")
    print(f"       setsweep queue {proj['id']}     # see what's been filed")
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
        print(f"  set one:  setsweep lineage {proj['id']} --accept")
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
        print(f"  review, then re-baseline:  setsweep lineage {proj['id']} --accept")
    return 0


def cmd_bind(args) -> int:
    """Add the fenced lineage directive to the project's CLAUDE.md (transparent + idempotent)
    so any agent working in the tree self-records its edits."""
    proj = server.get_project(args.project)
    r = lineage.ensure_directive(server.project_root(proj))
    print(f"lineage directive {r['action']} in {r['file']}")
    if r["editing_created"]:
        print(f"  wrote {server.desk_dir(proj)}/EDITING.md (the protocol)")
    print("  agents in this tree now carry the attribution directive + the .setsweep pointer.")
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
    extra = list(server.SWEEP_TOOLS)            # write powers, confined by cwd + acceptEdits
    if args.model:
        extra += ["--model", args.model]
    if not sid:
        extra += ["--name", server.session_name(proj)]
    rt = runtime.Runtime(server.CLAUDE, server.desk_dir(proj) / "sessions")
    print(f"· founding {proj['id']} — the curator surveys {server.project_root(proj)} …\n")
    for ev in rt.spawn(prompt, cwd=str(server.project_root(proj)), session_id=sid,
                       role="found", extra=extra):
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
        print(f"next:  setsweep queue {proj['id']}   ·   "
              f"setsweep chat {proj['id']} <entry-id>")
    else:
        print("(no entries filed — run `setsweep found` again, or read the survey above.)")
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
    rt = runtime.Runtime(server.CLAUDE, server.desk_dir(proj) / "sessions")
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

        extra = list(server.AGENT_TOOLS)
        if args.model:
            extra += ["--model", args.model]
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
            extra += ["--append-system-prompt", sysprompt, "--name", server.session_name(proj)]

        server.save_session(proj, **({"last_entry": entry["id"]} if entry else {}),
                            name=server.session_name(proj))

        sys.stdout.write("\ncurator> ")
        sys.stdout.flush()
        for ev in rt.spawn(message, cwd=root, session_id=sid, role="chat", extra=extra):
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
            print("setsweep egress: pass --body or pipe the memo body on stdin", file=sys.stderr)
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


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        prog="setsweep", description="CLI viewport over the desk.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="examples:\n"
               "  setsweep projects\n"
               "  setsweep add     ~/work/notes        # register a folder\n"
               "  setsweep init                        # register the current folder\n"
               "  setsweep queue   setsweep\n"
               "  setsweep open    setsweep refounding-merge\n"
               "  setsweep chat    setsweep               # talk to the desk\n"
               "  setsweep chat    setsweep <entry-id>    # about one file\n"
               "  setsweep sweep-status setsweep\n"
               "  setsweep sweep-close  setsweep\n"
               "  setsweep egress setsweep --kind launch --topic go-ahead --body '…'\n"
               "  setsweep egress-status setsweep\n")
    # not required: a bare `setsweep` should greet with the menu, not error out
    sub = ap.add_subparsers(
        dest="cmd",
        metavar="{projects,add,init,found,queue,open,lineage,bind,chat,"
                "sweep-status,sweep-close,sweep-archive,egress,egress-status}")
    sub.add_parser("projects", help="list registered desks").set_defaults(fn=cmd_projects)
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
    eg = sub.add_parser("egress", help="stage a desk egress memo under .setsweep/outbound/")
    eg.add_argument("project")
    eg.add_argument("--kind", required=True, choices=sorted(egress.KINDS))
    eg.add_argument("--topic", required=True)
    eg.add_argument("--route", default=None, help="routing hint (defaults by kind)")
    eg.add_argument("--body", default=None, help="memo body; else read stdin")
    eg.set_defaults(fn=cmd_egress)
    es = sub.add_parser("egress-status", help="list staged desk egress memos")
    es.add_argument("project"); es.set_defaults(fn=cmd_egress_status)
    args = ap.parse_args(argv)
    if not getattr(args, "fn", None):   # bare `setsweep` → show the menu, exit clean
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
