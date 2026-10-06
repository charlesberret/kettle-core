#!/usr/bin/env python3
"""kettle — unified entrypoint (the installed console script).

One command, several viewports onto the same desk:

  kettle                          Textual TUI (requires kettle-tui on PATH)
  kettle-web                      HTTP sitting host (browser + desktop sidecar)
  kettle --web [--port N]         same as kettle-web
  kettle projects                 list registered desks       ┐
  kettle themes                   list color themes            │
  kettle add     <folder>         add a folder as a project   │
  kettle init                     register the current folder │  the CLI viewport
  kettle found   <project>        agent sets up the project   │
  kettle queue   <project>        show a project's files      │  (stdlib only)
  kettle open|edit <project> <id> built-in TUI (--external for $EDITOR)
  kettle chat    <project> [id]   talk to the project's agent │
  kettle lineage <project>        who edited what              │
  kettle bind    <project>        add lineage directive to CLAUDE.md
  kettle migrate [--apply]        migrate .setsweep/ → .kettle/ (dry-run by default)
  kettle sweep-status|close|archive   mechanical CLOSE helpers│
  kettle refresh-briefs <project> rewrite briefs on the current queue
  kettle egress|egress-status         desk → ecosystem staging┘
  kettle doctor                   install health (PATH + package modules)
  kettle --help                   this message (plus kettle.__version__)

The native macOS window lives in the separate kettle-desktop Electron shell.
It still spawns this process as `kettle --web --port N --no-open` (or `kettle-web`
with the same flags). Routing sends those flags to the HTTP host; a bare `kettle`
execs `kettle-tui`. `kettle <cmd> --help` prints that subcommand's own argparse
help, not this message.
"""
from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

# Flags that mean "start the HTTP sitting host", including the desktop sidecar
# form `kettle --port <n> --no-open` and the explicit `kettle --web`.
SERVER_FLAGS = frozenset({
    "--web",
    "--app",
    "--replace",
    "--port",
    "--no-open",
})


def _prog_name() -> str:
    return Path(sys.argv[0]).name.lower()


def _invoked_as_web() -> bool:
    return _prog_name() in {"kettle-web", "kettle-web.exe"}


def _looks_like_server(args: list[str]) -> bool:
    for a in args:
        if a in SERVER_FLAGS or a.startswith("--port="):
            return True
    return False


def launch_web() -> int:
    from . import server          # server.main() reads sys.argv (--port/--no-open)
    return server.main() or 0


def _tui_executable() -> str | None:
    """PATH, then the directory of this script / interpreter (same venv, no PATH entry)."""
    found = shutil.which("kettle-tui")
    if found:
        return found
    names = ("kettle-tui", "kettle-tui.exe")
    parents = []
    try:
        parents.append(Path(sys.argv[0]).resolve().parent)
    except OSError:
        pass
    try:
        parents.append(Path(sys.executable).resolve().parent)
    except OSError:
        pass
    seen: set[Path] = set()
    for parent in parents:
        if parent in seen:
            continue
        seen.add(parent)
        for name in names:
            candidate = parent / name
            if candidate.is_file() and os.access(candidate, os.X_OK):
                return str(candidate)
    return None


def launch_tui(tui_argv: list[str]) -> int:
    """Replace this process with kettle-tui. Frozen binaries fall back to the HTTP host."""
    exe = _tui_executable()
    if exe:
        try:
            os.execvp(exe, [exe, *tui_argv])
        except OSError as exc:
            print(f"kettle: failed to launch kettle-tui ({exe}): {exc}", file=sys.stderr)
            return 1
        return 0
    if getattr(sys, "frozen", False):
        return launch_web()
    print(
        "kettle: kettle-tui is not on PATH.\n"
        "  pip install kettle-tui    # Textual sitting\n"
        "  kettle-web                # browser / desktop HTTP host\n"
        "  kettle --web              # same",
        file=sys.stderr,
    )
    return 1


def web_main(argv=None) -> int:
    """Installed as kettle-web: always the HTTP sitting host.

    server.main() reads process argv; the console script already has it.
    --help / --version share the kettle entrypoint text.
    """
    args = list(sys.argv[1:] if argv is None else argv)
    cmd = args[0] if args else None
    if cmd in ("-h", "--help", "-V", "--version"):
        return main(args)
    return launch_web()


def main(argv=None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    cmd = args[0] if args else None

    if cmd in ("-h", "--help"):
        from kettle import __version__

        print((__doc__ or "").strip())
        print(f"\nversion {__version__}")
        return 0
    if cmd in ("-V", "--version"):
        # A standalone binary must be able to name itself; the console script
        # answers the same way.
        from kettle import __version__
        from kettle import kettle_contract

        print(f"kettle {__version__} (api {kettle_contract.API_VERSION}, "
              f"desk schema {kettle_contract.DESK_SCHEMA_VERSION})")
        return 0
    if _invoked_as_web():
        return launch_web()
    if cmd is None:
        return launch_tui([])
    if _looks_like_server(args):
        return launch_web()
    if cmd.startswith("-"):
        return launch_tui(args)
    # Routing table is derived from cli.py's own subcommand table (cli.command_names())
    # so this router and the argparse tree it forwards to can never drift apart — a
    # subcommand added to cli.py (e.g. `migrate`) is reachable here automatically.
    # Imported lazily so a TUI / --web launch never pulls in the CLI viewport module.
    from . import cli
    if cmd in cli.command_names():
        return cli.main(args)
    print(f"kettle: unknown command {cmd!r} (try kettle --help)", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
