#!/usr/bin/env python3
"""setsweep — unified entrypoint (the installed console script).

One command, two viewports onto the same desk:

  setsweep                          browser / server mode       (default; stdlib only)
  setsweep --web [--port N]         same as bare launch
  setsweep projects                 list registered desks       ┐
  setsweep add     <folder>         register a folder as a desk │
  setsweep init                     register the current folder │  the CLI viewport
  setsweep queue   <project>        show a desk's queue         │  (stdlib only)
  setsweep open    <project> <id>   open the file in $EDITOR    │
  setsweep chat    <project> [id]   talk to the resident curator┘
  setsweep --help                   this message

The native macOS window lives in the separate setsweep-desktop Electron shell.
Routing keeps web/server as the default; the CLI subcommands go through `cli.py`.
"""
import sys

CLI_CMDS = {"projects", "add", "init", "found", "queue", "open", "lineage", "bind", "chat"}


def main(argv=None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    cmd = args[0] if args else None

    if cmd in ("-h", "--help"):
        print((__doc__ or "").strip())
        return 0
    if cmd in CLI_CMDS:
        import cli
        return cli.main(args)
    if cmd in (None, "--web", "--app", "--replace"):
        import server          # server.main() reads sys.argv (--port/--no-open)
        return server.main() or 0
    print(f"setsweep: unknown command {cmd!r} (try setsweep --help)", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
