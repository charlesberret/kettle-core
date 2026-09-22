#!/usr/bin/env python3
"""kettle — unified entrypoint (the installed console script).

One command, two viewports onto the same desk:

  kettle                          browser / server mode       (default; stdlib only)
  kettle --web [--port N]         same as bare launch
  kettle projects                 list registered desks       ┐
  kettle themes                   list color themes            │
  kettle add     <folder>         register a folder as a desk │
  kettle init                     register the current folder │  the CLI viewport
  kettle found   <project>        curator founds the desk      │
  kettle queue   <project>        show a desk's queue         │  (stdlib only)
  kettle open|edit <project> <id> built-in TUI (--external for $EDITOR)
  kettle chat    <project> [id]   talk to the resident curator│
  kettle lineage <project>        who edited what              │
  kettle bind    <project>        add lineage directive to CLAUDE.md
  kettle migrate [--apply]        migrate .setsweep/ → .kettle/ (dry-run by default)
  kettle sweep-status|close|archive   mechanical CLOSE helpers│
  kettle refresh-briefs <project> rewrite briefs on the current queue
  kettle egress|egress-status         desk → ecosystem staging┘
  kettle doctor                   install health (PATH + package modules)
  kettle --help                   this message (plus kettle.__version__)

The native macOS window lives in the separate kettle-desktop Electron shell.
Routing keeps web/server as the default; the CLI subcommands go through `cli.py`.
`kettle <cmd> --help` prints that subcommand's own argparse help, not this message.
"""
import sys


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
    if cmd in (None, "--web", "--app", "--replace"):
        from . import server          # server.main() reads sys.argv (--port/--no-open)
        return server.main() or 0
    # Routing table is derived from cli.py's own subcommand table (cli.command_names())
    # so this router and the argparse tree it forwards to can never drift apart — a
    # subcommand added to cli.py (e.g. `migrate`) is reachable here automatically.
    # Imported lazily so a bare/--web launch never pulls in the CLI viewport module.
    from . import cli
    if cmd in cli.command_names():
        return cli.main(args)
    print(f"kettle: unknown command {cmd!r} (try kettle --help)", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
