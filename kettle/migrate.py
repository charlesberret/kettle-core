"""Explicit migration from legacy Setsweep paths to Kettle.

Moves project desks ``.setsweep/`` → ``.kettle/`` and, when clearly supported,
the legacy user registry (``…/setsweep/projects.json`` → ``…/kettle/projects.json``,
plus a sibling ``settings.json`` when present).

**Dry-run is the default.** Pass ``apply=True`` / CLI ``--apply`` to write.
Never maintains two writable desks for one project: a root with both
``.kettle/`` and ``.setsweep/`` is refused (no rename, no copy).
"""
from __future__ import annotations

import json
import os
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

from . import server

DESK_LEGACY = ".setsweep"
DESK_CURRENT = ".kettle"


@dataclass
class Action:
    """One planned or executed migration step."""

    kind: str  # desk-rename | registry-move | path-rewrite | skip | refuse
    detail: str
    source: Path | None = None
    dest: Path | None = None
    project_id: str | None = None
    # path-rewrite only: which stale absolute-path field this repairs, and (for a
    # queue entry) which entry it belongs to — lets _apply_path_rewrite find and
    # update the exact field without re-deriving it from `detail`.
    rewrite_target: str | None = None  # "queue-entry" | "ledger"
    entry_id: str | None = None


@dataclass
class Plan:
    actions: list[Action] = field(default_factory=list)
    applied: bool = False

    @property
    def refusals(self) -> list[Action]:
        return [a for a in self.actions if a.kind == "refuse"]

    @property
    def pending(self) -> list[Action]:
        return [a for a in self.actions
                if a.kind in {"desk-rename", "registry-move", "path-rewrite"}]

    @property
    def ok(self) -> bool:
        return not self.refusals


def _desk_paths(root: Path) -> tuple[Path, Path]:
    return root / DESK_CURRENT, root / DESK_LEGACY


def plan_desk(proj: dict) -> Action:
    """Plan migration for one registered project root."""
    pid = str(proj.get("id") or "?")
    try:
        root = server.project_root(proj)
    except (OSError, TypeError, ValueError) as e:
        return Action(
            kind="refuse",
            detail=f"cannot resolve root ({e})",
            project_id=pid,
        )
    current, legacy = _desk_paths(root)
    if current.is_dir() and legacy.is_dir():
        return Action(
            kind="refuse",
            detail=(
                f"split desk: both {DESK_CURRENT}/ and {DESK_LEGACY}/ present "
                f"under {root} — resolve manually (never keep two writable desks)"
            ),
            source=legacy,
            dest=current,
            project_id=pid,
        )
    if legacy.is_dir() and not current.exists():
        return Action(
            kind="desk-rename",
            detail=f"rename {legacy} → {current}",
            source=legacy,
            dest=current,
            project_id=pid,
        )
    if current.is_dir():
        return Action(
            kind="skip",
            detail=f"already using {DESK_CURRENT}/",
            dest=current,
            project_id=pid,
        )
    if legacy.exists() and not legacy.is_dir():
        return Action(
            kind="refuse",
            detail=f"{legacy} exists but is not a directory",
            source=legacy,
            dest=current,
            project_id=pid,
        )
    return Action(
        kind="skip",
        detail="no desk directory yet",
        project_id=pid,
    )


def _rewrite_prefix(value: str, old: Path, new: Path) -> str | None:
    """`value` with an exact `<old>` (or `<old>/...`) prefix rewritten to `<new>`,
    or None if `value` does not start with that prefix. Only an exact directory-prefix
    match rewrites — a string that merely contains the old path as a substring
    elsewhere (a different project sharing a name fragment, say) is left alone."""
    old_s, new_s = str(old), str(new)
    if value == old_s:
        return new_s
    prefix = old_s + os.sep
    if value.startswith(prefix):
        return new_s + os.sep + value[len(prefix):]
    return None


def plan_queue_path_rewrites(proj: dict, legacy: Path, current: Path) -> list[Action]:
    """Queue entries whose `path` is an absolute path under the legacy desk directory,
    planned to move under the current desk directory in step with the desk rename that
    is moving the file itself. Read-only — inspects the legacy `runtime/queue.json` in
    place, before the rename physically relocates it. A project's own desk-rename
    action must run first (`build_plan` orders these together); `_apply_path_rewrite`
    then edits the file at its new (`current`) location."""
    pid = str(proj.get("id") or "?")
    qp = legacy / "runtime" / "queue.json"
    if not qp.is_file():
        return []
    try:
        data = json.loads(qp.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    entries = data.get("entries") if isinstance(data, dict) else None
    if not isinstance(entries, list):
        return []
    actions = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        old_path = entry.get("path")
        if not isinstance(old_path, str):
            continue
        new_path = _rewrite_prefix(old_path, legacy, current)
        if new_path is None:
            continue
        eid = str(entry.get("id") or "?")
        actions.append(Action(
            kind="path-rewrite",
            detail=f"queue entry '{eid}' path: {old_path} → {new_path}",
            source=Path(old_path),
            dest=Path(new_path),
            project_id=pid,
            rewrite_target="queue-entry",
            entry_id=eid,
        ))
    return actions


def plan_ledger_rewrite(proj: dict, legacy: Path, current: Path) -> Action | None:
    """The registry entry's `ledger` field, when it is a stale absolute path under the
    legacy desk directory — same prefix rewrite as queue entries, for the one other
    place a desk-relative absolute path is known to be stored."""
    ledger = proj.get("ledger")
    if not isinstance(ledger, str) or not ledger.strip():
        return None
    new_ledger = _rewrite_prefix(ledger, legacy, current)
    if new_ledger is None:
        return None
    return Action(
        kind="path-rewrite",
        detail=f"registry ledger: {ledger} → {new_ledger}",
        source=Path(ledger),
        dest=Path(new_ledger),
        project_id=str(proj.get("id") or "?"),
        rewrite_target="ledger",
    )


def plan_registry(
    *,
    kettle_path: Path | None = None,
    legacy_path: Path | None = None,
    desk_projects_env: str | None = ...,
) -> Action:
    """Plan moving the legacy Setsweep user registry to the Kettle path.

    Skipped when ``DESK_PROJECTS`` is set (explicit override owns the live path)
    or when the Kettle registry already exists (no split write target).
    """
    if desk_projects_env is ...:
        desk_projects_env = os.environ.get("DESK_PROJECTS")
    if desk_projects_env:
        return Action(
            kind="skip",
            detail="DESK_PROJECTS is set — registry path is an explicit override",
        )
    kettle = Path(kettle_path) if kettle_path is not None else server.user_projects_path()
    legacy = (
        Path(legacy_path) if legacy_path is not None else server.legacy_user_projects_path()
    )
    if kettle.exists():
        return Action(
            kind="skip",
            detail=f"Kettle registry already present ({kettle})",
            dest=kettle,
        )
    if not legacy.exists():
        return Action(
            kind="skip",
            detail="no legacy Setsweep user registry found",
            source=legacy,
            dest=kettle,
        )
    return Action(
        kind="registry-move",
        detail=f"move registry {legacy} → {kettle}",
        source=legacy,
        dest=kettle,
    )


def _apply_desk_rename(action: Action) -> None:
    assert action.source is not None and action.dest is not None
    if action.dest.exists():
        raise RuntimeError(f"destination already exists: {action.dest}")
    if not action.source.is_dir():
        raise RuntimeError(f"source desk missing: {action.source}")
    action.source.rename(action.dest)


def _apply_registry_move(action: Action) -> None:
    assert action.source is not None and action.dest is not None
    if action.dest.exists():
        raise RuntimeError(f"destination already exists: {action.dest}")
    if not action.source.is_file():
        raise RuntimeError(f"legacy registry missing: {action.source}")
    src_parent = action.source.parent
    try:
        was_live = server.PROJECTS_PATH.resolve() == action.source.resolve()
    except OSError:
        was_live = Path(server.PROJECTS_PATH) == action.source
    action.dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(action.source), str(action.dest))
    # Companion settings next to the registry (same layout resolve_projects_path uses).
    legacy_settings = src_parent / "settings.json"
    kettle_settings = action.dest.parent / "settings.json"
    if legacy_settings.is_file() and not kettle_settings.exists():
        shutil.move(str(legacy_settings), str(kettle_settings))
    if was_live:
        server.PROJECTS_PATH = action.dest
        server.SETTINGS_PATH = action.dest.parent / "settings.json"


def _apply_path_rewrite(action: Action) -> None:
    """Apply one queue-entry or registry-ledger prefix rewrite. Runs after the desk
    rename it is paired with, so `server.queue_path` / the live registry already
    resolve to the new (`.kettle`) location."""
    assert action.source is not None and action.dest is not None
    assert action.project_id is not None
    if action.rewrite_target == "ledger":
        data = server.read_projects_registry()
        projects = data.get("projects")
        if not isinstance(projects, list):
            raise RuntimeError("projects registry is malformed")
        matched = False
        for p in projects:
            if (isinstance(p, dict) and str(p.get("id")) == action.project_id
                    and p.get("ledger") == str(action.source)):
                p["ledger"] = str(action.dest)
                matched = True
        if not matched:
            raise RuntimeError(
                f"registry ledger {action.source} for project "
                f"'{action.project_id}' not found — already rewritten or changed"
            )
        server.atomic_write(server.PROJECTS_PATH, json.dumps(data, indent=2, ensure_ascii=False))
        return

    assert action.entry_id is not None
    proj = server.get_project(action.project_id)
    qp = server.queue_path(proj)
    try:
        data = json.loads(qp.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise RuntimeError(f"cannot read queue for rewrite: {qp} ({e})") from e
    entries = data.get("entries")
    if not isinstance(entries, list):
        raise RuntimeError(f"queue.json has no entries list: {qp}")
    matched = False
    for entry in entries:
        if (isinstance(entry, dict) and str(entry.get("id")) == action.entry_id
                and entry.get("path") == str(action.source)):
            entry["path"] = str(action.dest)
            matched = True
    if not matched:
        raise RuntimeError(
            f"queue entry '{action.entry_id}' with path {action.source} not found in "
            f"{qp} — already rewritten or changed"
        )
    server.atomic_write(qp, json.dumps(data, indent=2, ensure_ascii=False))


def build_plan(
    *,
    project_ids: Iterable[str] | None = None,
    include_registry: bool = True,
    kettle_registry: Path | None = None,
    legacy_registry: Path | None = None,
) -> Plan:
    """Assemble a migration plan without writing."""
    plan = Plan()
    projects = server.load_projects()
    if project_ids is not None:
        wanted = list(project_ids)
        by_id = {str(p.get("id")): p for p in projects if isinstance(p, dict)}
        missing = [pid for pid in wanted if pid not in by_id]
        for pid in missing:
            plan.actions.append(Action(
                kind="refuse",
                detail=f"unknown project id: {pid}",
                project_id=pid,
            ))
        selected = [by_id[pid] for pid in wanted if pid in by_id]
    else:
        selected = [p for p in projects if isinstance(p, dict)]

    for proj in selected:
        desk_action = plan_desk(proj)
        plan.actions.append(desk_action)
        if desk_action.kind == "desk-rename":
            # Same move as the rename above: queue-entry paths and the registry
            # ledger field can carry an absolute `<root>/.setsweep/...` string that
            # the rename alone does not touch (the file moves; the text inside a
            # JSON value does not). Plan those rewrites in the same breath so they
            # land — and are reported — together with the rename that requires them.
            legacy, current = desk_action.source, desk_action.dest
            plan.actions.extend(plan_queue_path_rewrites(proj, legacy, current))
            ledger_action = plan_ledger_rewrite(proj, legacy, current)
            if ledger_action is not None:
                plan.actions.append(ledger_action)

    if include_registry and project_ids is None:
        plan.actions.append(plan_registry(
            kettle_path=kettle_registry,
            legacy_path=legacy_registry,
        ))
    return plan


def apply_plan(plan: Plan) -> Plan:
    """Execute pending actions. Refuses the whole apply if any refuse is present."""
    if plan.refusals:
        raise RuntimeError(
            "refusing to apply while refusals remain — resolve split desks first"
        )
    for action in plan.pending:
        if action.kind == "desk-rename":
            _apply_desk_rename(action)
            action.detail = f"renamed {action.source} → {action.dest}"
        elif action.kind == "registry-move":
            _apply_registry_move(action)
            action.detail = f"moved registry {action.source} → {action.dest}"
        elif action.kind == "path-rewrite":
            _apply_path_rewrite(action)
            what = "registry ledger" if action.rewrite_target == "ledger" \
                else f"queue entry '{action.entry_id}' path"
            action.detail = f"rewrote {what}: {action.source} → {action.dest}"
    plan.applied = True
    return plan


def run_migrate(
    *,
    apply: bool = False,
    project_ids: Iterable[str] | None = None,
    include_registry: bool = True,
    kettle_registry: Path | None = None,
    legacy_registry: Path | None = None,
) -> Plan:
    """Plan (and optionally apply) migration. Dry-run when ``apply`` is False."""
    plan = build_plan(
        project_ids=project_ids,
        include_registry=include_registry,
        kettle_registry=kettle_registry,
        legacy_registry=legacy_registry,
    )
    if apply:
        if plan.refusals:
            return plan  # caller prints refusals; nothing written
        apply_plan(plan)
    return plan


def format_report(plan: Plan, *, apply_requested: bool) -> str:
    """Human-readable CLI report."""
    lines: list[str] = []
    if apply_requested and plan.applied:
        lines.append("migrate: applied")
    elif apply_requested and plan.refusals:
        lines.append("migrate: apply blocked (refusals present) — nothing written")
    else:
        lines.append("migrate: dry-run (pass --apply to write)")
    lines.append("")

    if not plan.actions:
        lines.append("  (nothing to inspect)")
    for action in plan.actions:
        label = (action.project_id or "registry").ljust(12)
        if action.kind == "desk-rename":
            verb = "renamed" if plan.applied else "rename "
            lines.append(f"  {label}  {verb}  {action.source}  →  {action.dest}")
        elif action.kind == "registry-move":
            verb = "moved  " if plan.applied else "move   "
            lines.append(f"  {label}  {verb}  {action.source}  →  {action.dest}")
        elif action.kind == "path-rewrite":
            verb = "rewrote" if plan.applied else "rewrite"
            what = "ledger" if action.rewrite_target == "ledger" else f"queue[{action.entry_id}]"
            lines.append(f"  {label}  {verb}  {what}  {action.source}  →  {action.dest}")
        elif action.kind == "refuse":
            lines.append(f"  {label}  REFUSE  {action.detail}")
        else:
            lines.append(f"  {label}  skip    {action.detail}")

    lines.append("")
    n_pending = len(plan.pending)
    n_refuse = len(plan.refusals)
    if plan.applied:
        lines.append(f"migrate: {n_pending} change(s) applied")
    elif apply_requested and n_refuse:
        lines.append(
            f"migrate: {n_refuse} refusal(s), {n_pending} change(s) not applied"
        )
    elif n_pending or n_refuse:
        lines.append(
            f"migrate: {n_pending} change(s) planned"
            + (f", {n_refuse} refused" if n_refuse else "")
            + " — not applied"
        )
    else:
        lines.append("migrate: nothing to do")
    return "\n".join(lines) + "\n"
