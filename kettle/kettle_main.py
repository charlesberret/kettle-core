#!/usr/bin/env python3
"""kettle — unified entrypoint (the installed console script).

One command, two viewports onto the same desk:

  kettle                          browser / server mode       (default; stdlib only)
  kettle --web [--port N]         same as bare launch
  kettle projects                 list registered desks       ┐
  kettle add     <folder>         register a folder as a desk │
  kettle init                     register the current folder │  the CLI viewport
  kettle queue   <project>        show a desk's queue         │  (stdlib only)
  kettle open    <project> <id>   open the file in $EDITOR    │
  kettle chat    <project> [id]   talk to the resident curator│
  kettle sweep-status|close|archive   mechanical CLOSE helpers│
  kettle egress|egress-status         desk → ecosystem staging┘
  kettle doctor                   install health (PATH + package modules)
  kettle --help                   this message

The native macOS window lives in the separate kettle-desktop Electron shell.
Routing keeps web/server as the default; the CLI subcommands go through `cli.py`.
"""
import sys

CLI_CMDS = {"projects", "add", "init", "found", "queue", "open", "edit", "themes",
            "lineage", "bind", "chat",
            "doctor",
            "sweep-status", "sweep-close", "sweep-archive", "refresh-briefs",
            "egress", "egress-status"}


def main(argv=None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    cmd = args[0] if args else None

    if cmd in ("-h", "--help"):
        from kettle import __version__

        print((__doc__ or "").strip())
        print(f"\nversion {__version__}")
        return 0
    if cmd in CLI_CMDS:
        from . import cli
        return cli.main(args)
    if cmd in (None, "--web", "--app", "--replace"):
        from . import server          # server.main() reads sys.argv (--port/--no-open)
        return server.main() or 0
    print(f"kettle: unknown command {cmd!r} (try kettle --help)", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
