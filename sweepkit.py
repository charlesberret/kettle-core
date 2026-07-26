"""Mechanical sweep close-kit — deterministic desk ops the curator should not re-derive.

The agent (or a thin sweep skill) leans on these for CLOSE; ACCRUE (familiarity + briefs)
stays judgment. Pure helpers: take a project dict, touch only that project's desk.
"""
from __future__ import annotations

import json
import shutil
from datetime import date, datetime
from pathlib import Path
from typing import Any

import server


def _entry_comment(e: dict) -> str:
    return str(e.get("comment") or "").strip()


def _has_file_change(proj: dict, e: dict) -> bool | None:
    """True/False when a snapshot exists; None if there is no baseline yet."""
    st = server.entry_diffstat(proj, e)
    if st is None:
        return None
    return bool(st.get("added") or st.get("removed"))


def assess_close(proj: dict) -> dict[str, Any]:
    """Summarize whether CLOSE needs judgment and what mechanical work is pending.

    Does not mutate the desk. Ledger contents are not parsed — if a ledger path is
    configured, auto mechanical-close is refused so the curator can apply rulings.
    Entries without snapshots cannot be certified quiet (blocks mechanical close).
    """
    q = server.load_queue(proj)
    entries = list(q.get("entries") or [])
    cl_path = server.comments_log_path(proj)
    comments_map = server.parse_comments_log(cl_path)

    changed: list[dict] = []
    unchanged: list[dict] = []
    unknown: list[dict] = []
    approved: list[str] = []
    pending: list[str] = []

    for e in entries:
        eid = str(e.get("id", ""))
        if not eid:
            continue
        log_notes = comments_map.get(eid) or []
        has_comment = bool(_entry_comment(e) or log_notes)
        diff = server.entry_diffstat(proj, e)
        file_changed = _has_file_change(proj, e)
        snap = server._snapshot_path(proj, eid)
        row = {
            "id": eid,
            "path": e.get("path"),
            "status": e.get("status", "pending"),
            "ask_type": e.get("ask_type"),
            "has_comment": has_comment,
            "file_changed": file_changed,
            "diff": diff,
            "has_snapshot": snap.exists(),
        }
        if has_comment or file_changed is True:
            changed.append(row)
        elif file_changed is None:
            unknown.append(row)
        else:
            unchanged.append(row)
        if e.get("status") == "approved":
            approved.append(eid)
        else:
            pending.append(eid)

    intake = server.intake_paths(proj)
    ledger = proj.get("ledger")
    has_ledger = bool(
        ledger and str(ledger).strip()
        and "no ledger configured" not in str(ledger)
    )

    quiet = len(changed) == 0 and len(unknown) == 0 and not has_ledger
    needs_accrue = not bool(intake)
    needs_judgment = not quiet
    all_approved = bool(entries) and len(approved) == len(entries)
    # Mechanical close only when the sitting is quiet AND ready to clear:
    # non-inbox — every entry approved; inbox — at least one approved to stage.
    can_mech = quiet and len(entries) > 0 and (
        all_approved or (bool(intake) and len(approved) > 0)
    )

    return {
        "project": proj.get("id"),
        "quiet": quiet,
        "needs_judgment": needs_judgment,
        "needs_accrue": needs_accrue,
        "is_inbox": bool(intake),
        "has_ledger": has_ledger,
        "entry_count": len(entries),
        "approved_ids": approved,
        "pending_ids": pending,
        "changed": changed,
        "unchanged": unchanged,
        "unknown": unknown,
        "curated": q.get("curated"),
        "all_approved": all_approved,
        "can_mechanical_close": can_mech,
        "fully_idle": quiet and len(entries) == 0,
    }


def stage_inbox_approved(proj: dict) -> dict[str, Any]:
    """Copy approved inbox drafts to outbound/. Never transmits. No-op if not inbox."""
    intake = server.intake_paths(proj)
    if not intake:
        return {"staged": [], "skipped": "not an inbox project"}
    _, _, outbound = intake
    outbound = Path(outbound)
    outbound.mkdir(parents=True, exist_ok=True)
    staged = []
    errors = []
    for e in server.load_queue(proj).get("entries") or []:
        if e.get("status") != "approved":
            continue
        try:
            src = server.safe_path(e["path"], server.project_root(proj))
            dest = outbound / src.name
            shutil.copy2(src, dest)
            staged.append({"id": e.get("id"), "from": str(src), "to": str(dest)})
        except (OSError, PermissionError, KeyError, RuntimeError) as err:
            errors.append({"id": e.get("id"), "error": str(err)})
    return {"staged": staged, "errors": errors, "outbound": str(outbound)}


def archive_queue(
    proj: dict,
    *,
    only_approved: bool = False,
    entry_ids: list[str] | None = None,
) -> dict[str, Any]:
    """Move selected entries to archive/{today}-batch.json and delete their snapshots.

    Default: archive the entire current queue (normal desk close).
    Inbox mode: pass only_approved=True to leave pending entries in place.
    """
    q = server.load_queue(proj)
    entries = list(q.get("entries") or [])
    if entry_ids is not None:
        want = {str(i) for i in entry_ids}
        take = [e for e in entries if str(e.get("id")) in want]
        leave = [e for e in entries if str(e.get("id")) not in want]
    elif only_approved:
        take = [e for e in entries if e.get("status") == "approved"]
        leave = [e for e in entries if e.get("status") != "approved"]
    else:
        take, leave = entries, []

    if not take:
        return {"archived": [], "remaining": len(leave), "archive_path": None}

    today = date.today().isoformat()
    arch_dir = server.desk_dir(proj) / "archive"
    arch_dir.mkdir(parents=True, exist_ok=True)
    arch_path = arch_dir / f"{today}-batch.json"
    prior: list = []
    if arch_path.exists():
        try:
            prior = json.loads(arch_path.read_text()).get("entries") or []
        except (OSError, json.JSONDecodeError):
            prior = []
    batch = {
        "archived": today,
        "project": proj.get("id"),
        "entries": prior + take,
    }
    server.atomic_write(arch_path, json.dumps(batch, indent=2, ensure_ascii=False))

    deleted_snaps = []
    for e in take:
        snap = server._snapshot_path(proj, e.get("id"))
        if snap.exists():
            try:
                snap.unlink()
                deleted_snaps.append(str(snap))
            except OSError:
                pass

    new_q = dict(q)
    new_q["entries"] = leave
    if not leave:
        new_q["curated"] = f"swept {today}"

    def apply(_q):
        _q.clear()
        _q.update(new_q)

    server.mutate_queue(proj, apply)
    return {
        "archived": [e.get("id") for e in take],
        "remaining": len(leave),
        "archive_path": str(arch_path),
        "snapshots_deleted": deleted_snaps,
    }


def write_session_log_stub(
    proj: dict,
    status: dict,
    *,
    stamp: str | None = None,
    extra_lines: list[str] | None = None,
) -> Path:
    """Thin session log — one line per entry; expand only via extra_lines."""
    stamp = stamp or datetime.now().strftime("%Y-%m-%d-%H%M%S")
    sess_dir = server.runtime_dir(proj) / "sessions"
    sess_dir.mkdir(parents=True, exist_ok=True)
    path = sess_dir / f"{stamp}-session.md"
    lines = [
        f"# Sweep {stamp}",
        "",
        f"Project: {proj.get('id')} ({proj.get('name')})",
        f"Mode: {'quiet mechanical close' if status.get('quiet') else 'judgment pending'}",
        "",
        "## Entries",
    ]
    for row in status.get("changed") or []:
        bits = []
        if row.get("has_comment"):
            bits.append("comment")
        if row.get("file_changed"):
            bits.append("diff")
        lines.append(f"- {row['id']} — needs judgment ({', '.join(bits) or 'changed'})")
    for row in status.get("unchanged") or []:
        st = row.get("status") or "pending"
        lines.append(f"- {row['id']} — unchanged-{st}")
    if extra_lines:
        lines.append("")
        lines.extend(extra_lines)
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def publish_approval_egress(proj: dict, entries: list[dict] | None = None) -> dict[str, Any]:
    """Stage a kind:approval egress memo so fleet/other agents see user gates.

    Lists approved entries (cleared) and remaining pending entries (still blocked).
    No-op (returns published=False) when there is nothing useful to say.
    """
    import egress as _egress

    q = server.load_queue(proj)
    all_entries = list(entries if entries is not None else (q.get("entries") or []))
    approved = [e for e in all_entries if e.get("status") == "approved"]
    pending = [e for e in all_entries if e.get("status") != "approved"]
    if not approved and not pending:
        return {"published": False, "reason": "empty queue"}

    day = date.today().isoformat()
    lines = [
        f"User sitting closed via Kettle for project `{proj.get('id')}` ({proj.get('name')}).",
        "",
        "## Approved this sitting (peers may treat these as cleared)",
    ]
    if approved:
        for e in approved:
            lines.append(
                f"- **{e.get('id')}** · `{e.get('path')}` · "
                f"{e.get('ask') or '—'} · approved {e.get('approved') or day}"
            )
            if e.get("unblocks") and str(e.get("unblocks")).strip() not in ("", "—"):
                lines.append(f"  - unblocks: {e['unblocks']}")
    else:
        lines.append("- (none)")

    lines.extend(["", "## Still pending in queue (peers must not assume cleared)"])
    if pending:
        for e in pending:
            lines.append(
                f"- **{e.get('id')}** · `{e.get('path')}` · "
                f"{e.get('ask') or '—'} · status={e.get('status') or 'pending'}"
            )
            if e.get("unblocks") and str(e.get("unblocks")).strip() not in ("", "—"):
                lines.append(f"  - still blocks: {e['unblocks']}")
    else:
        lines.append("- (none — queue empty of pending work)")

    lines.extend([
        "",
        "Source of truth on the desk: `.kettle/runtime/queue.json` and "
        "`.kettle/runtime/approvals.log`. This memo is the fleet-readable summary "
        "after approve+sweep.",
    ])
    body = "\n".join(lines)
    result = _egress.stage_egress(
        proj,
        kind="approval",
        topic="sitting-approvals",
        body=body,
        day=day,
    )
    return {"published": True, **result}


def mechanical_close(proj: dict) -> dict[str, Any]:
    """Run quiet CLOSE when safe: stage inbox, archive, thin log.

    Refuses (without mutating) when judgment is needed or a ledger is configured.
    """
    status = assess_close(proj)
    if status.get("fully_idle"):
        return {"ok": True, "action": "idle", "status": status}
    if not status.get("can_mechanical_close"):
        return {
            "ok": False,
            "action": "refused",
            "reason": "judgment or ledger required — run curator accrue/close with judgment",
            "status": status,
        }

    # Capture entries before archive so the approval memo can list them.
    pre_entries = list(server.load_queue(proj).get("entries") or [])
    staged = stage_inbox_approved(proj) if status.get("is_inbox") else {"staged": []}
    approval_pub: dict[str, Any] = {"published": False}
    try:
        approval_pub = publish_approval_egress(proj, pre_entries)
    except Exception as exc:  # noqa: BLE001 — never fail close on egress
        approval_pub = {"published": False, "error": str(exc)}

    archived = archive_queue(
        proj,
        only_approved=True if status.get("is_inbox") else False,
    )
    extra = []
    if staged.get("staged"):
        extra.extend(f"- staged: {s['id']} → {s['to']}" for s in staged["staged"])
    if approval_pub.get("published") and approval_pub.get("path"):
        extra.append(f"- approval egress: {approval_pub['path']}")
    log_path = write_session_log_stub(
        proj,
        status,
        extra_lines=extra or None,
    )
    return {
        "ok": True,
        "action": "mechanical_close",
        "status": status,
        "staged": staged,
        "approval_egress": approval_pub,
        "archived": archived,
        "session_log": str(log_path),
        "needs_accrue": status.get("needs_accrue") and not status.get("is_inbox"),
    }


def status_for_prompt(proj: dict) -> str:
    """Compact JSON block injected into the sweep prompt."""
    st = assess_close(proj)
    # Drop bulky unchanged detail for prompt size; keep ids
    slim = {
        "quiet": st["quiet"],
        "needs_judgment": st["needs_judgment"],
        "needs_accrue": st["needs_accrue"],
        "is_inbox": st["is_inbox"],
        "has_ledger": st["has_ledger"],
        "can_mechanical_close": st["can_mechanical_close"],
        "fully_idle": st["fully_idle"],
        "approved_ids": st["approved_ids"],
        "pending_ids": st["pending_ids"],
        "changed_ids": [c["id"] for c in st["changed"]],
        "unchanged_ids": [u["id"] for u in st["unchanged"]],
    }
    return (
        "CLOSE KIT STATUS (from kettle sweepkit — trust this; do not re-diff to discover it):\n"
        + json.dumps(slim, indent=2)
    )
