"""Kettle lineage — who edited what: agent vs. user vs. unattributed.

Implements the model in `LINEAGE.md` (Revision 1; user ruling 2026-06-18): track agent
edits against user edits over a desk's files, with an honest `unattributed` residual for
changes that happened outside the app and can't be confirmed. Two plain files in the desk:

  .kettle/working-record.jsonl  — append-only; agents (and the app, for the user's
                                      own saves) log each edit-batch as it happens
  .kettle/lineage-baseline.json  — the last reconciled state: {ts, files: {rel: hash}}

The reconciler compares the tree against the baseline. A change a working-record entry
claims (since the baseline) is attributed to that entry's actor; an **unclaimed** change is
`unattributed` and surfaced for the user to resolve at the desk — trust-by-default
("unlogged ⇒ user") is rejected, because it would manufacture the false authorship this
exists to prevent. Content hashes are the dependency-free v1 change-detector; git can back
it later behind the same interface.

Stdlib only. The reconcile logic is pure and unit-tested; file-walking is plumbing.
"""
from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Iterable, Iterator, Optional

RECORD_NAME = "working-record.jsonl"
BASELINE_NAME = "lineage-baseline.json"

# names skipped wholesale while walking a desk (desk machinery + VCS + heavy noise)
SKIP_DIRS = {".kettle", ".setsweep", ".git", "node_modules", "__pycache__", ".venv",
             "venv", ".mypy_cache", ".pytest_cache", "dist", "build", ".cache"}
MAX_BYTES = 1_000_000          # skip files larger than this (likely data/media, not prose/source)


class UnsafeDeskPath(ValueError):
    """A desk write whose path escapes the project through a symlink."""


def confine(path: Path | str, root: Path | str) -> Path:
    """Refuse to write `path` when its final component is a symlink (dangling or not), or
    when the deepest existing ancestor resolves outside `root`. A registered folder is
    not trusted: a planted `.kettle/working-record.jsonl -> ~/.zshrc`, or a symlinked
    `runtime/snapshots`, must not turn a desk write into a write elsewhere."""
    root_r = Path(root).resolve()
    p = Path(path)
    if not p.is_absolute():
        p = Path(root) / p
    if p.is_symlink():
        raise UnsafeDeskPath(f"{p} is a symlink — Kettle does not write through links in a project")
    anc = p.parent
    while not os.path.lexists(anc) and anc != anc.parent:
        anc = anc.parent
    if not anc.resolve().is_relative_to(root_r):
        raise UnsafeDeskPath(f"{p} leads outside the project ({anc.resolve()}) through a symlink")
    return p


def write_confined(path: Path | str, root: Path | str, text: str, *, append: bool = False) -> None:
    """Write or append text without following a symlink at the final component (O_NOFOLLOW
    closes the gap between the check and the open)."""
    p = confine(path, root)
    flags = os.O_WRONLY | os.O_CREAT | (os.O_APPEND if append else os.O_TRUNC)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(str(p), flags, 0o600)
    with os.fdopen(fd, "a" if append else "w", encoding="utf-8") as f:
        f.write(text)


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def desk_dir(root: Path | str) -> Path:
    root = Path(root)
    current = root / ".kettle"
    legacy = root / ".setsweep"
    if current.exists() or not legacy.exists():
        return current
    return legacy


# ---------- change detection: content-hash snapshot ----------

def file_hash(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _is_texty(path: Path) -> bool:
    try:
        with open(path, "rb") as f:
            return b"\x00" not in f.read(8192)      # crude but effective binary sniff
    except OSError:
        return False


def iter_tracked(root: Path | str, excludes: Optional[set] = None,
                 max_depth: Optional[int] = None) -> Iterator[Path]:
    """Walk the desk's tracked working files: text files under root, skipping dotdirs /
    machinery / oversized / binary. The desk's own `.kettle/` is never tracked.

    max_depth (>=1) bounds the walk by directory level — 1 = only files in the root folder,
    2 = root + one level of subdirs — and PRUNES the descent, so a shallow desk over a huge
    tree (e.g. ~) never enumerates the deep subtrees. 0/None = the whole tree."""
    root = Path(root)
    skip = SKIP_DIRS | (excludes or set())
    bound = max_depth if (isinstance(max_depth, int) and max_depth >= 1) else None
    for dirpath, dirnames, filenames in os.walk(root):
        rel = Path(dirpath).relative_to(root)
        depth = 0 if str(rel) == "." else len(rel.parts)
        dirnames[:] = [d for d in dirnames if d not in skip and not d.startswith(".")]
        if bound is not None and depth + 1 >= bound:
            dirnames[:] = []                       # children would exceed the bound — don't descend
        if bound is not None and depth >= bound:
            continue                               # this dir's own files are already out of scope
        for fn in sorted(filenames):
            if fn.startswith("."):
                continue
            p = Path(dirpath) / fn
            try:
                if p.stat().st_size > MAX_BYTES or not _is_texty(p):
                    continue
            except OSError:
                continue
            yield p


def snapshot(root: Path | str, excludes: Optional[set] = None,
             max_depth: Optional[int] = None) -> dict:
    """{relpath: content-hash} over the desk's tracked files (bounded by max_depth)."""
    root = Path(root)
    return {str(p.relative_to(root)): file_hash(p)
            for p in iter_tracked(root, excludes, max_depth)}


def load_baseline(root: Path | str) -> dict:
    try:
        return json.loads((desk_dir(root) / BASELINE_NAME).read_text())
    except (OSError, json.JSONDecodeError):
        return {"ts": None, "files": {}}


def save_baseline(root: Path | str, manifest: dict) -> dict:
    d = desk_dir(root)
    confine(d / BASELINE_NAME, root)
    d.mkdir(parents=True, exist_ok=True)
    write_confined(d / BASELINE_NAME, root, json.dumps(manifest, indent=1, ensure_ascii=False))
    return manifest


def accept_baseline(root: Path | str, excludes: Optional[set] = None,
                    git: bool = False, max_depth: Optional[int] = None) -> dict:
    """Mark the current tree as the reconciled baseline (the user has seen it). When
    `git` is on, also commit a watermarked snapshot to the separate lineage history."""
    m = save_baseline(root, {"ts": _now(), "files": snapshot(root, excludes, max_depth)})
    if git:
        git_snapshot(root, f"lineage: baseline {m['ts']}")
    return m


# ---------- the working record (agent/app self-logging) ----------

def record_path(root: Path | str) -> Path:
    return desk_dir(root) / RECORD_NAME


def read_record(root: Path | str) -> list:
    try:
        text = record_path(root).read_text(encoding="utf-8")
    except OSError:
        return []
    return [json.loads(ln) for ln in text.splitlines() if ln.strip()]


def log_edit(root: Path | str, actor: str, actor_kind: str, files: Iterable[str],
             summary: str = "", session: str = "", ts: Optional[str] = None) -> dict:
    """Append one edit-batch to the desk's working record. `files` are paths relative to
    the desk root. `actor_kind` is 'agent' or 'user'. The single way edits get attributed
    as they happen; everything not logged becomes the reconciler's `unattributed`."""
    rec = {"ts": ts or _now(), "actor": actor, "actor_kind": actor_kind,
           "session": session, "files": list(files), "summary": summary}
    d = desk_dir(root)
    confine(d / RECORD_NAME, root)
    d.mkdir(parents=True, exist_ok=True)
    write_confined(d / RECORD_NAME, root, json.dumps(rec, ensure_ascii=False) + "\n", append=True)
    return rec


def _parse_ts(s) -> Optional[datetime]:
    try:
        return datetime.fromisoformat(s) if s else None
    except (ValueError, TypeError):
        return None


def claims_since(records: list, baseline_ts: Optional[str]) -> dict:
    """Latest claim per file from records at/after the baseline. {relpath: entry}. A claim
    older than the baseline can't explain a change made since, so it is excluded. The
    record is append-ordered (chronological), so last-write-wins is the latest claim."""
    floor = _parse_ts(baseline_ts)
    latest: dict = {}
    for e in records:
        ets = _parse_ts(e.get("ts"))
        if floor and ets and ets < floor:
            continue
        for rel in e.get("files", []):
            latest[rel] = e          # later entry overwrites → newest claim wins
    return latest


# ---------- the reconciler ----------

def _attribute(rel: str, change: str, claims: dict) -> dict:
    e = claims.get(rel)
    if e is None:
        return {"path": rel, "change": change, "status": "unattributed", "by": None, "at": None}
    kind = e.get("actor_kind")
    status = kind if kind in ("agent", "user") else "unattributed"
    return {"path": rel, "change": change, "status": status,
            "by": e.get("actor"), "at": e.get("ts")}


def reconcile(root: Path | str, baseline: dict, records: list,
              excludes: Optional[set] = None, max_depth: Optional[int] = None) -> list:
    """Compare the tree against the baseline; attribute each change via the working record.
    Returns [{path, change: added|modified|deleted, status: agent|user|unattributed, by, at}]."""
    cur = snapshot(root, excludes, max_depth)
    base = baseline.get("files", {})
    claims = claims_since(records, baseline.get("ts"))
    out = []
    for rel, h in cur.items():
        old = base.get(rel)
        if old == h:
            continue
        out.append(_attribute(rel, "added" if old is None else "modified", claims))
    for rel in base:
        if rel not in cur:
            out.append(_attribute(rel, "deleted", claims))
    return sorted(out, key=lambda c: (c["status"], c["path"]))


def status(root: Path | str, excludes: Optional[set] = None,
           max_depth: Optional[int] = None) -> dict:
    """Full lineage picture for a desk: counts + the attributed change list (bounded by max_depth)."""
    baseline = load_baseline(root)
    changes = reconcile(root, baseline, read_record(root), excludes, max_depth)
    counts = {"agent": 0, "user": 0, "unattributed": 0}
    for c in changes:
        counts[c["status"]] = counts.get(c["status"], 0) + 1
    return {"baseline_ts": baseline.get("ts"), "counts": counts,
            "changed": len(changes), "changes": changes}


WRITE_TOOLS = {"Edit", "Write", "MultiEdit", "NotebookEdit"}


def _relativize(root: Path | str, paths: Iterable[str]) -> list:
    """Absolute/relative edit paths → unique desk-relative paths. Paths outside the desk
    root, and desk machinery under a dot-dir (`.kettle/`, `.git/`), are dropped — the
    record tracks the desk's *working* files, the same set the reconciler walks."""
    root = Path(root).resolve()
    rels: list = []
    seen = set()
    for p in paths:
        try:
            rp = Path(p)
            if not rp.is_absolute():
                rp = root / rp                          # the editing cwd is the desk root
            rel = rp.resolve().relative_to(root)
        except (ValueError, OSError):
            continue
        if rel.parts and rel.parts[0].startswith("."):
            continue
        s = str(rel)
        if s not in seen:
            seen.add(s)
            rels.append(s)
    return rels


def log_agent_edits(root: Path | str, abs_paths: Iterable[str], actor: str = "agent",
                    session: str = "", summary: str = "") -> Optional[dict]:
    """Log a turn's file edits as one agent batch, so Kettle's own agents self-record
    without the honor system. Returns the record, or None if nothing trackable was edited."""
    rels = _relativize(root, abs_paths)
    if not rels:
        return None
    return log_edit(root, actor=actor, actor_kind="agent", files=rels, session=session,
                    summary=summary or f"{actor}: edited {len(rels)} file(s)")


def log_user_edit(root: Path | str, abs_paths: Iterable[str], actor: str = "user",
                  session: str = "", summary: str = "user save (editor)") -> Optional[dict]:
    """Log the user's own in-app edits (a middle-pane save) as a user batch — the other
    half of in-app attribution, the counterpart to log_agent_edits."""
    rels = _relativize(root, abs_paths)
    if not rels:
        return None
    return log_edit(root, actor=actor, actor_kind="user", files=rels, session=session,
                    summary=summary)


def resolve(root: Path | str, path: str, actor_kind: str = "user",
            actor: str = "user", summary: str = "desk-resolve", git: bool = False) -> dict:
    """Record the user's resolution of an unattributed change (a user action — the
    authoritative attribution). Appends a claim so the next reconcile attributes it; the
    user then accepts the baseline to clear it from 'changed since'."""
    rec = log_edit(root, actor=actor, actor_kind=actor_kind, files=[path], summary=summary)
    if git:
        git_snapshot(root, f"lineage: {path} resolved as {actor_kind} by {actor}")
    return rec


# ---------- the binding directive (transparent, fenced, opt-in) ----------

DIRECTIVE_TAG = "kettle:lineage"
LEGACY_DIRECTIVE_TAG = "setsweep:lineage"
EDITING_MD = """# Editing this project — the lineage protocol

Any agent that edits files in this project records its work, so Kettle can tell agent
edits from the user's. The rule:

- When you edit files here, append one entry per edit-batch to `working-record.jsonl`:
  `{"ts": …, "actor": …, "actor_kind": "agent", "files": [<paths relative to the project
  root>], "summary": …}`.
- **Attribute honestly. An agent edit is an agent edit — never recorded as the user's.**
  If you are proposing rather than enacting the user's decision, say "proposal".
- Kettle's own agents do this automatically; this rule is for any *other* agent working
  in the tree (e.g. a separate CLI session).

Changes nobody logs are reconciled as `unattributed` and surfaced for the user to resolve —
nothing is ever silently attributed to them. Kettle desk config lives in this
`{desk_name}/` directory.
"""


def _directive_block(desk_name: str) -> str:
    return (
        "<!-- {tag} (added by `kettle bind`; safe to delete this whole block) -->\n"
        "**Editing this project:** record each edit to `{desk_name}/working-record.jsonl` and "
        "attribute honestly — an agent edit is an agent edit, never the user's. "
        "Protocol: `{desk_name}/EDITING.md`. Desk config: `{desk_name}/`.\n"
        "<!-- /{tag} -->"
    ).format(tag=DIRECTIVE_TAG, desk_name=desk_name)


def ensure_directive(root: Path | str, agent_file: str = "CLAUDE.md") -> dict:
    """Add (or refresh) the fenced lineage directive in the project's agent-instructions
    file, and write a standard desk-local `EDITING.md` if absent. Idempotent and visible:
    the block is marker-fenced so it is identifiable and removable. Returns what it did."""
    import re
    root = Path(root)
    d = desk_dir(root)
    desk_name = d.name
    directive = _directive_block(desk_name)
    confine(d / "EDITING.md", root)
    d.mkdir(parents=True, exist_ok=True)
    editing_created = False
    if not (d / "EDITING.md").exists():
        write_confined(d / "EDITING.md", root, EDITING_MD.replace("{desk_name}", desk_name))
        editing_created = True

    f = confine(root / agent_file, root)
    existing = f.read_text(encoding="utf-8") if f.exists() else ""
    present_tag = next(
        (
            tag for tag in (DIRECTIVE_TAG, LEGACY_DIRECTIVE_TAG)
            if f"<!-- {tag}" in existing
        ),
        None,
    )
    if present_tag:
        new = re.sub(
            rf"<!-- {re.escape(present_tag)}.*?<!-- /{re.escape(present_tag)} -->",
            directive,
            existing,
            flags=re.S,
        )
        action = "updated"
    elif existing.strip():
        new = existing.rstrip() + "\n\n" + directive + "\n"
        action = "appended"
    else:
        new = directive + "\n"
        action = "created"
    write_confined(f, root, new)
    return {"file": str(f), "action": action, "editing_created": editing_created}


# ---------- optional git substrate (separate history; never the project's own repo) ----------

GIT_DIR = ".kettle/lineage.git"          # a history apart from any user .git in the tree


def _git_dir(root: Path | str) -> Path:
    return desk_dir(root) / "lineage.git"


# Never let the lineage repo's own config run code: hooks, fsmonitor, a pager, an
# external diff or attributes-driven filters are all ways a folder that ships
# `.kettle/lineage.git` could execute something on the next snapshot.
_GIT_HARDENING = ["-c", "core.hooksPath=/dev/null", "-c", "core.fsmonitor=false",
                  "-c", "core.pager=cat", "-c", "diff.external=", "-c", "core.sshCommand=false",
                  "-c", "core.attributesFile=/dev/null"]

_LINEAGE_CONFIG = """[core]
\trepositoryformatversion = 0
\tfilemode = true
\tbare = false
[user]
\temail = desk@kettle.local
\tname = Kettle
"""

# Which lineage.git directories Kettle itself created. Kept OUTSIDE every project tree
# (anything inside a registered folder can be forged by whoever made the folder).
TRUST_PATH = Path.home() / ".cache" / "kettle" / "lineage-trust.json"


def _git(root: Path, *args, check: bool = True):
    import subprocess
    return subprocess.run(
        ["git", *_GIT_HARDENING, "--git-dir", str(_git_dir(root)), "--work-tree", str(root),
         *args],
        capture_output=True, text=True, check=check)


def _trust_key(gd: Path) -> str:
    st = gd.stat()
    return f"{gd.resolve()}|{st.st_dev}|{st.st_ino}"


def _load_trust() -> set:
    try:
        return set(json.loads(TRUST_PATH.read_text()).get("repos") or [])
    except (OSError, json.JSONDecodeError, AttributeError):
        return set()


def _record_trust(gd: Path) -> None:
    repos = _load_trust() | {_trust_key(gd)}
    TRUST_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = TRUST_PATH.with_name(TRUST_PATH.name + f".{os.getpid()}.tmp")
    tmp.write_text(json.dumps({"repos": sorted(repos)}, indent=1))
    os.replace(tmp, TRUST_PATH)


def _lineage_git_is_ours(gd: Path) -> bool:
    try:
        return _trust_key(gd) in _load_trust()
    except OSError:
        return False


def _reset_lineage_config(gd: Path) -> None:
    """Rewrite what Kettle controls before every run: a fixed config (no filters,
    includes or aliases) and no repo-level attributes file."""
    (gd / "config").write_text(_LINEAGE_CONFIG)
    for name in ("commondir", "info/attributes"):
        try:
            (gd / name).unlink()
        except FileNotFoundError:
            pass


def git_snapshot(root: Path | str, message: str) -> Optional[str]:
    """Commit the desk's working files to a SEPARATE lineage git history (init if needed)
    with a watermarked message — never the project's own repo, so a user's git is untouched.
    Returns the short commit hash, or None (nothing to commit / git unavailable). Toggled by
    the `lineage_git` setting; the hash baseline is the dependency-free default."""
    import subprocess
    root = Path(root)
    gd = _git_dir(root)
    try:
        if gd.is_symlink() or (gd.exists() and not _lineage_git_is_ours(gd)):
            # Not created by Kettle (or created before trust was recorded): never run it.
            # Set it aside, untouched, and start a fresh history Kettle does trust.
            aside = gd.with_name(f"lineage.git.untrusted-{datetime.now():%Y%m%d-%H%M%S}")
            os.replace(gd, aside)
        confine(gd / "config", root)
        if not gd.exists():
            _git(root, "init", "-q")
            _record_trust(gd)
            # keep the user's .git, desk machinery, and heavy noise out of the lineage history
            (gd / "info").mkdir(parents=True, exist_ok=True)
            (gd / "info" / "exclude").write_text(
                "\n".join([".git", ".kettle", ".setsweep", "node_modules", "__pycache__",
                           ".venv", "venv", "dist", "build", ".cache", ""]))
        _reset_lineage_config(gd)
        _git(root, "add", "-A")
        if _git(root, "diff", "--cached", "--quiet", check=False).returncode == 0:
            return None                                    # nothing changed
        _git(root, "commit", "-q", "-m", message)
        return _git(root, "rev-parse", "--short", "HEAD").stdout.strip() or None
    except (subprocess.CalledProcessError, OSError, UnsafeDeskPath):
        return None
