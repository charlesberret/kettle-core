#!/usr/bin/env python3
"""kettle — a command-line viewport over the same desk.

Proof of DESIGN.md §3 ("the desk is the application; the app is a viewport"): this driver
runs **no HTTP server**. It shares the web app's logic only through the desk helpers in
`server.py` (importing them is side-effect-free) and the agent adapter in `runtime.py`.
The desk is plain files in `<root>/.kettle/`; this renders and drives them from the
terminal. Edits use the **built-in TUI editor** (syntax-colored from the active Kettle
theme pack) so a sitting does not depend on an external `$EDITOR`. Pass ``--external``
to open ``$EDITOR`` instead when you want your own tools.

  kettle projects                list registered desks
  kettle add     <folder>        register a folder as a desk (first-run)
  kettle init                    register the current folder as a desk
  kettle found   <project>       curator founds the desk: charter, memory, first queue
  kettle queue   <project>       show a desk's queue
  kettle open    <project> <id>  show the brief, then edit the file (built-in TUI)
  kettle edit    <project> <id>  same as open (explicit name for the built-in editor)
  kettle themes                  list bundled + user color themes (marquee: kettle)
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
  kettle doctor                  install + runtime health (PATH, desks, provider, server)

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
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from . import curator
from . import egress
from . import kettle_contract
from . import lineage
from . import runtime
from . import server
from . import sweepkit

# Canonical install (brief 20). Doctor flags any other winner on PATH.
CANONICAL_VENV = Path.home() / ".kettle-venv"
CANONICAL_KETTLE = CANONICAL_VENV / "bin" / "kettle"
DIST_NAME = "kettle"
# Never probe the conventional live port (docs/ENGINEERING.md). Discovery only.
_DOCTOR_PING_TIMEOUT_S = 0.8


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


def _package_modules() -> list[str]:
    """Importable dotted names under the kettle package (doctor source of truth)."""
    from kettle import PACKAGE_MODULES

    return ["kettle", *[f"kettle.{name}" for name in PACKAGE_MODULES]]


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


# Back-compat alias used by older tests / callers.
def _py_modules_from_pyproject(path: Path | None = None) -> list[str]:
    """Return package submodule short names (not flat py-modules).

    ``path`` is accepted for call-site compatibility and ignored — the module
    list lives in ``kettle.PACKAGE_MODULES`` after the package restructure.
    """
    del path  # unused; kept so monkeypatches/tests keep a stable signature
    from kettle import PACKAGE_MODULES

    return list(PACKAGE_MODULES)


def _package_install_info(dist_name: str = DIST_NAME) -> tuple[str, str]:
    """Return (version, install_mode) for the installed distribution."""
    try:
        dist = importlib.metadata.distribution(dist_name)
    except importlib.metadata.PackageNotFoundError:
        return "unknown", "not-installed"
    version = dist.version or "unknown"
    # PEP 610 direct_url.json distinguishes editable checkouts from wheels.
    try:
        text = dist.read_text("direct_url.json")
    except (FileNotFoundError, OSError):
        text = None
    if text:
        try:
            meta = json.loads(text)
        except json.JSONDecodeError:
            meta = {}
        dir_info = meta.get("dir_info") if isinstance(meta, dict) else None
        if isinstance(dir_info, dict) and dir_info.get("editable"):
            return version, "editable"
        if isinstance(meta, dict) and meta.get("url", "").startswith("file:"):
            return version, "local-path"
    return version, "wheel-or-sdist"


def _read_settings_readonly() -> dict:
    """Load settings.json without healing or rewriting (doctor is read-only)."""
    path = server.SETTINGS_PATH
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8") or "{}")
    except (OSError, json.JSONDecodeError, UnicodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _registry_raw() -> tuple[Path, object | None, str | None]:
    """Return (path, parsed_json_or_None, error_detail_or_None). Never creates files."""
    path = server.PROJECTS_PATH
    if not path.exists():
        return path, {"projects": []}, None
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as e:
        return path, None, f"unreadable: {e}"
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        return path, None, f"invalid JSON: {e}"
    return path, data, None


def _read_discovery(path: Path | None = None) -> tuple[dict | None, str | None]:
    """Parse ~/.cache/kettle/server.json. Returns (info, error). Missing → (None, None)."""
    p = path if path is not None else server.RUNTIME_PATH
    if not p.is_file():
        return None, None
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeError) as e:
        return None, f"unreadable discovery: {e}"
    if not isinstance(data, dict):
        return None, "discovery is not a JSON object"
    return data, None


def _ping_localhost(port: int, timeout: float = _DOCTOR_PING_TIMEOUT_S) -> dict | None:
    """GET /api/ping on loopback only. Never binds; never probes port 4242."""
    if not isinstance(port, int) or port <= 0 or port == server.DEFAULT_PORT:
        # Refuse the conventional live port so tools never disturb a bookmarked desk.
        return None
    try:
        with urllib.request.urlopen(
            f"http://127.0.0.1:{port}/api/ping", timeout=timeout,
        ) as resp:
            payload = json.loads(resp.read())
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError, ValueError):
        return None
    if not isinstance(payload, dict):
        return None
    if payload.get("app") not in {"kettle", "setsweep"}:
        return None
    return payload


def install_doctor_checks(
    *,
    path_hits: list[Path] | None = None,
    py_modules: list[str] | None = None,
    package_modules: list[str] | None = None,
    top_level: Any = ...,
    canonical: Path = CANONICAL_KETTLE,
) -> list[dict]:
    """Read-only install health rows for `kettle doctor` (brief 20; expanded by brief 18).

    Each row: {name, ok, detail, docs}. `ok` False means doctor should exit nonzero.

    ``py_modules`` is a legacy alias for short submodule names (without the
    ``kettle.`` prefix). Prefer ``package_modules`` with dotted import names.
    """
    rows: list[dict] = []
    hits = path_hits if path_hits is not None else _which_all("kettle")
    if top_level is ...:
        top_level = _installed_top_level()
    if package_modules is not None:
        modules = list(package_modules)
        modules_source = "caller"
    elif py_modules is not None:
        # Legacy short names → dotted package imports.
        modules = [
            n if n == "kettle" or n.startswith("kettle.") else f"kettle.{n}"
            for n in py_modules
        ]
        modules_source = "caller"
    else:
        modules = _package_modules()
        modules_source = "kettle.PACKAGE_MODULES"

    # --- python + package ---
    py_ok = sys.version_info >= (3, 11)
    rows.append({
        "name": "python-version",
        "ok": py_ok,
        "detail": f"{sys.version.split()[0]} ({sys.executable})",
        "docs": "INSTALL.md § Canonical install",
    })
    pkg_version, install_mode = _package_install_info()
    rows.append({
        "name": "package-version",
        "ok": install_mode != "not-installed",
        "detail": f"{DIST_NAME} {pkg_version} ({install_mode})",
        "docs": "INSTALL.md § Canonical install",
    })

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
                "docs": "INSTALL.md § PATH hygiene",
            })
        else:
            rows.append({
                "name": "kettle-path-extras",
                "ok": True,
                "detail": "single kettle on PATH",
                "docs": "INSTALL.md § Canonical install",
            })

    # --- package modules importable + kettle present in installed top_level ---
    if not modules:
        rows.append({
            "name": "py-modules-list",
            "ok": False,
            "detail": "could not resolve kettle.PACKAGE_MODULES",
            "docs": "INSTALL.md § Reinstall rule",
        })
        return rows

    # Row name kept as py-modules-list for doctor output stability.
    rows.append({
        "name": "py-modules-list",
        "ok": True,
        "detail": f"{len(modules)} modules from {modules_source}",
        "docs": "kettle/__init__.py PACKAGE_MODULES",
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
        # Package layout: top_level.txt lists the distribution package name only.
        if "kettle" not in top_level:
            listed = ", ".join(top_level) if top_level else "(empty)"
            rows.append({
                "name": "install-mapping",
                "ok": False,
                "detail": "installed top_level missing 'kettle' (reinstall): " + listed,
                "docs": "INSTALL.md § Reinstall rule",
            })
        else:
            rows.append({
                "name": "install-mapping",
                "ok": True,
                "detail": "installed top_level includes kettle package",
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
            "detail": "not importable (reinstall editable?): "
                      + ", ".join(missing_import),
            "docs": "INSTALL.md § Reinstall rule",
        })
    else:
        rows.append({
            "name": "py-modules-importable",
            "ok": True,
            "detail": f"all {len(modules)} package modules importable",
            "docs": "INSTALL.md § Reinstall rule",
        })

    return rows


def desk_doctor_checks(
    *,
    projects: list[dict] | None = None,
    registry_path: Path | None = None,
    registry_data: Any = ...,
    registry_error: Any = ...,
) -> list[dict]:
    """Read-only registry + desk integrity + legacy migration hints (brief 18)."""
    rows: list[dict] = []
    if registry_data is ... or registry_error is ...:
        path, data, err = _registry_raw()
        if registry_path is None:
            registry_path = path
        if registry_data is ...:
            registry_data = data
        if registry_error is ...:
            registry_error = err
    elif registry_path is None:
        registry_path = server.PROJECTS_PATH

    if registry_error:
        rows.append({
            "name": "registry",
            "ok": False,
            "detail": f"{registry_path}: {registry_error}",
            "docs": "INSTALL.md § Registering a desk",
        })
        return rows

    if not isinstance(registry_data, dict) or not isinstance(
        registry_data.get("projects"), list,
    ):
        rows.append({
            "name": "registry",
            "ok": False,
            "detail": f"{registry_path}: expected object with projects[]",
            "docs": "INSTALL.md § Registering a desk",
        })
        return rows

    proj_list = projects if projects is not None else list(registry_data.get("projects") or [])
    rows.append({
        "name": "registry",
        "ok": True,
        "detail": f"{registry_path} ({len(proj_list)} project(s))",
        "docs": "INSTALL.md § Registering a desk",
    })

    problems: list[str] = []
    legacy_only: list[str] = []
    both_desks: list[str] = []
    for proj in proj_list:
        if not isinstance(proj, dict):
            problems.append("non-object project entry")
            continue
        pid = str(proj.get("id") or "?")
        root_raw = proj.get("root")
        if not root_raw:
            problems.append(f"{pid}: missing root")
            continue
        try:
            root = Path(str(root_raw)).expanduser().resolve()
        except OSError as e:
            problems.append(f"{pid}: bad root ({e})")
            continue
        if not root.is_dir():
            problems.append(f"{pid}: root missing ({root})")
            continue
        kettle_desk = root / ".kettle"
        setsweep_desk = root / ".setsweep"
        if kettle_desk.is_dir() and setsweep_desk.is_dir():
            both_desks.append(pid)
        elif setsweep_desk.is_dir() and not kettle_desk.exists():
            legacy_only.append(pid)
        desk = kettle_desk if kettle_desk.exists() or not setsweep_desk.exists() else setsweep_desk
        if not desk.is_dir():
            # Unfounded / never-opened desk: registry entry alone is fine.
            continue
        queue = desk / "runtime" / "queue.json"
        if not queue.is_file():
            problems.append(f"{pid}: desk present but queue.json missing ({queue})")
            continue
        try:
            qdata = json.loads(queue.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, UnicodeError) as e:
            problems.append(f"{pid}: queue.json unreadable ({e})")
            continue
        if not isinstance(qdata, dict) or "entries" not in qdata:
            problems.append(f"{pid}: queue.json missing entries[]")

    if problems:
        rows.append({
            "name": "desk-integrity",
            "ok": False,
            "detail": "; ".join(problems[:5])
                      + (f" (+{len(problems) - 5} more)" if len(problems) > 5 else ""),
            "docs": "ARCHITECTURE.md · INSTALL.md § Registering a desk",
        })
    else:
        rows.append({
            "name": "desk-integrity",
            "ok": True,
            "detail": (
                f"{len(proj_list)} desk(s) ok"
                if proj_list else "no desks registered"
            ),
            "docs": "ARCHITECTURE.md · INSTALL.md § Registering a desk",
        })

    # Split state is a real failure; legacy-only is an informational hint (still ok).
    if both_desks:
        rows.append({
            "name": "legacy-migration",
            "ok": False,
            "detail": "both .kettle/ and .setsweep/ present (split risk): "
                      + ", ".join(both_desks[:5]),
            "docs": "INSTALL.md § Registering a desk · ROADMAP Migration",
        })
    elif legacy_only:
        rows.append({
            "name": "legacy-migration",
            "ok": True,
            "detail": "legacy .setsweep/ desk(s) in use (migrate when ready): "
                      + ", ".join(legacy_only[:5]),
            "docs": "INSTALL.md § Registering a desk · ROADMAP Migration",
        })
    else:
        rows.append({
            "name": "legacy-migration",
            "ok": True,
            "detail": "no legacy .setsweep/ desks in registry",
            "docs": "INSTALL.md § Registering a desk",
        })

    return rows


def runtime_doctor_checks(
    *,
    settings: dict | None = None,
    provider_ready: dict | None = None,
    discovery: Any = ...,
    discovery_error: Any = ...,
    ping: Any = ...,
) -> list[dict]:
    """Read-only provider + discovery + server reachability rows (brief 18).

    Auth-token enforcement is owned elsewhere; doctor only reports CLI resolve and
    an optional localhost ping from the discovery record (never binds, never probes
    the conventional live port 4242).
    """
    rows: list[dict] = []
    settings = settings if settings is not None else _read_settings_readonly()
    try:
        cfg = curator.resolve_curator(settings)
    except Exception as e:  # noqa: BLE001 — doctor must keep going
        rows.append({
            "name": "provider-cli",
            "ok": False,
            "detail": f"curator resolve failed: {e}",
            "docs": "INSTALL.md § Auth",
        })
        cfg = None

    if cfg is not None:
        if provider_ready is None:
            provider_ready = curator.provider_readiness(
                cfg.provider,
                active_provider=cfg.provider,
                active_command=cfg.command,
            )
        exists = bool(provider_ready.get("command_exists"))
        cmd = provider_ready.get("command_resolved") or provider_ready.get("command") or "?"
        label = provider_ready.get("label") or cfg.provider
        rows.append({
            "name": "provider-cli",
            "ok": exists,
            "detail": (
                f"{label}: {cmd}"
                if exists else
                f"{label}: `{provider_ready.get('command') or cmd}` not on PATH"
            ),
            "docs": "INSTALL.md § Auth",
        })

    if discovery is ... or discovery_error is ...:
        info, err = _read_discovery()
        if discovery is ...:
            discovery = info
        if discovery_error is ...:
            discovery_error = err

    if discovery_error:
        rows.append({
            "name": "runtime-discovery",
            "ok": False,
            "detail": discovery_error,
            "docs": "ARCHITECTURE.md · docs/ENGINEERING.md",
        })
        rows.append({
            "name": "server-reachable",
            "ok": False,
            "detail": "skipped (discovery unreadable)",
            "docs": "ARCHITECTURE.md · docs/ENGINEERING.md",
        })
        return rows

    if discovery is None:
        rows.append({
            "name": "runtime-discovery",
            "ok": True,
            "detail": f"no discovery record at {server.RUNTIME_PATH} (server not running)",
            "docs": "ARCHITECTURE.md · docs/ENGINEERING.md",
        })
        rows.append({
            "name": "server-reachable",
            "ok": True,
            "detail": "server not running (CLI-only is fine)",
            "docs": "INSTALL.md § Viewports",
        })
        return rows

    port = discovery.get("port")
    pid = discovery.get("pid")
    url = discovery.get("url") or (f"http://127.0.0.1:{port}/" if port else "?")
    rows.append({
        "name": "runtime-discovery",
        "ok": isinstance(port, int) and port > 0,
        "detail": f"port={port} pid={pid} url={url}",
        "docs": "ARCHITECTURE.md · docs/ENGINEERING.md",
    })

    if not (isinstance(port, int) and port > 0):
        rows.append({
            "name": "server-reachable",
            "ok": False,
            "detail": "discovery missing a usable port",
            "docs": "ARCHITECTURE.md · docs/ENGINEERING.md",
        })
        return rows

    if port == server.DEFAULT_PORT:
        # Policy: tooling must not probe 4242. Report discovery only.
        rows.append({
            "name": "server-reachable",
            "ok": True,
            "detail": (
                f"discovery lists conventional port {port}; "
                "skipping probe (see docs/ENGINEERING.md)"
            ),
            "docs": "docs/ENGINEERING.md",
        })
        return rows

    if ping is ...:
        ping = _ping_localhost(port)

    if ping is None:
        rows.append({
            "name": "server-reachable",
            "ok": False,
            "detail": f"no kettle /api/ping on 127.0.0.1:{port} (stale discovery?)",
            "docs": "ARCHITECTURE.md · docs/ENGINEERING.md",
        })
        return rows

    local_ver = kettle_contract.core_version()
    remote_ver = ping.get("version")
    ver_note = (
        f"version={remote_ver}"
        if remote_ver == local_ver
        else f"version={remote_ver} (local {local_ver})"
    )
    # Version skew is a warning detail; reachability itself is the hard check.
    # Auth token presence is owned by the security workstream — not reported here.
    rows.append({
        "name": "server-reachable",
        "ok": True,
        "detail": f"GET /api/ping ok on :{port} ({ver_note})",
        "docs": "ARCHITECTURE.md · API.md",
    })
    return rows


def doctor_checks(
    *,
    path_hits: list[Path] | None = None,
    py_modules: list[str] | None = None,
    top_level: Any = ...,
    canonical: Path = CANONICAL_KETTLE,
    projects: list[dict] | None = None,
    registry_path: Path | None = None,
    registry_data: Any = ...,
    registry_error: Any = ...,
    settings: dict | None = None,
    provider_ready: dict | None = None,
    discovery: Any = ...,
    discovery_error: Any = ...,
    ping: Any = ...,
) -> list[dict]:
    """Full read-only doctor table: install + desks + provider/runtime."""
    rows = install_doctor_checks(
        path_hits=path_hits,
        py_modules=py_modules,
        top_level=top_level,
        canonical=canonical,
    )
    rows.extend(desk_doctor_checks(
        projects=projects,
        registry_path=registry_path,
        registry_data=registry_data,
        registry_error=registry_error,
    ))
    rows.extend(runtime_doctor_checks(
        settings=settings,
        provider_ready=provider_ready,
        discovery=discovery,
        discovery_error=discovery_error,
        ping=ping,
    ))
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


def _entry_header(entry: dict) -> str:
    title = entry.get("title") or Path(entry.get("path", "")).name
    return f"[{entry.get('id')}] {title}"


def _open_external(path: Path) -> int:
    editor = os.environ.get("EDITOR") or "vi"
    print(f"opening {path} in {editor} …")
    return subprocess.call([editor, str(path)])


def cmd_open(args) -> int:
    """Show brief context, then edit the entry file (built-in TUI by default)."""
    proj = server.get_project(args.project)
    entry = server.find_entry(server.load_queue(proj), args.id)
    print(f"[{entry['id']}] {entry.get('title') or Path(entry['path']).name}")
    if entry.get("ask"):
        print(f"ask:   {entry['ask']}")
    if entry.get("brief"):
        print(f"brief: {' '.join(str(entry['brief']).split())}")
    path = _resolve(proj, entry["path"])
    if getattr(args, "external", False):
        return _open_external(path)

    from . import theme_catalog
    from . import tui_editor

    try:
        settings = server.load_settings()
    except Exception:
        settings = {}
    if not isinstance(settings, dict):
        settings = {}
    theme_id = getattr(args, "theme", None) or theme_catalog.active_theme_id_from_settings(settings)
    header = _entry_header(entry)
    print(f"\nbuilt-in editor · theme {theme_id} · ^S save · ^Q quit · ^W $EDITOR\n")
    code = tui_editor.edit_file(path, theme_id=theme_id, header=header)
    if code == 2:
        return _open_external(path)
    if code == 3:
        print("no tty for built-in editor — falling back to $EDITOR", file=sys.stderr)
        return _open_external(path)
    return 0 if code in (0, 1) else code


def cmd_edit(args) -> int:
    """Alias for open — explicit name for the built-in review editor."""
    return cmd_open(args)


def cmd_themes(args) -> int:
    """List bundled and user theme packs; mark the marquee default."""
    from . import theme_catalog

    default = theme_catalog.default_theme_id()
    print(f"default (marquee): {default}")
    print(f"bundled dir:       {theme_catalog.bundled_themes_dir()}")
    print(f"user dir:          {theme_catalog.user_themes_dir()}")
    print()
    for tid in theme_catalog.list_theme_ids():
        try:
            pack = theme_catalog.load_theme(tid)
        except (OSError, ValueError) as e:
            print(f"  {tid:16}  (error: {e})")
            continue
        mark = "*" if tid == default or pack.get("marquee") else " "
        src = pack.get("_source", "?")
        print(f" {mark} {tid:16}  {pack.get('label', tid):20}  [{src}]")
    print("\n* marquee / default    place custom packs as <id>.json in the user dir")
    return 0


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
    """Install + runtime health (brief 20 install seed; brief 18 expansion). Read-only."""
    rows = doctor_checks()
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
        print(f"doctor: {failed} check(s) failed — see INSTALL.md / ARCHITECTURE.md")
        return 1
    print("doctor: all checks green")
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
               "  kettle edit    kettle refounding-merge\n"
               "  kettle themes\n"
               "  kettle chat    kettle               # talk to the desk\n"
               "  kettle chat    kettle <entry-id>    # about one file\n"
               "  kettle doctor                      # install + runtime health\n"
               "  kettle sweep-status kettle\n"
               "  kettle sweep-close  kettle\n"
               "  kettle refresh-briefs kettle\n"
               "  kettle egress kettle --kind launch --topic go-ahead --body '…'\n"
               "  kettle egress-status kettle\n")
    # not required: a bare `kettle` should greet with the menu, not error out
    sub = ap.add_subparsers(
        dest="cmd",
        metavar="{projects,add,init,found,queue,open,edit,themes,lineage,bind,chat,doctor,"
                "sweep-status,sweep-close,sweep-archive,refresh-briefs,egress,egress-status}")
    sub.add_parser("projects", help="list registered desks").set_defaults(fn=cmd_projects)
    sub.add_parser("themes", help="list bundled and user color themes").set_defaults(fn=cmd_themes)
    sub.add_parser(
        "doctor",
        help="install + runtime health (PATH, desks, provider CLI, server discovery)",
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
    o = sub.add_parser("open", help="edit an entry's file (built-in TUI; --external for $EDITOR)")
    o.add_argument("project"); o.add_argument("id")
    o.add_argument("--external", action="store_true", help="open in $EDITOR instead of the built-in TUI")
    o.add_argument("--theme", default=None, help="theme pack id (default: kettle / settings)")
    o.set_defaults(fn=cmd_open)
    e = sub.add_parser("edit", help="edit an entry's file in the built-in syntax-colored TUI")
    e.add_argument("project"); e.add_argument("id")
    e.add_argument("--external", action="store_true", help="open in $EDITOR instead")
    e.add_argument("--theme", default=None, help="theme pack id (default: kettle / settings)")
    e.set_defaults(fn=cmd_edit)
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
