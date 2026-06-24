#!/usr/bin/env python3
"""setsweep — unified entrypoint (the installed console script).

One command, three viewports onto the same desk:

  setsweep                          the native window           (default; needs `gui` extra)
  setsweep --web [--port N]         browser mode                (stdlib only)
  setsweep projects                 list registered desks       ┐
  setsweep add     <folder>         register a folder as a desk │
  setsweep init                     register the current folder │  the CLI viewport
  setsweep queue   <project>        show a desk's queue         │  (stdlib only)
  setsweep open    <project> <id>   open the file in $EDITOR    │
  setsweep chat    <project> [id]   talk to the resident curator┘
  setsweep --help                   this message

Routing keeps the GUI as the default — the same behavior as the prior bash launcher —
and folds the terminal viewport in under the same name. GUI/web go through `server.py`;
the CLI subcommands go through `cli.py`; nothing starts a server unless you ask for one.
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
    if cmd == "--web":
        import server          # server.main() reads sys.argv (--port/--no-open); --web is ignored
        return server.main()
    # default (bare), --app, --replace → the native window
    import app
    return app.main() or 0


if __name__ == "__main__":
    sys.exit(main())
