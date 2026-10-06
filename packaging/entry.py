#!/usr/bin/env python3
"""Entry point for the standalone `kettle` binary (PyInstaller).

Identical dispatch to the `kettle` console script: subcommands go to the CLI
viewport, a bare launch execs `kettle-tui` when it is on PATH, and `--web` /
missing TUI on a frozen binary serve the sitting. Keeping one entry means
the binary and the wheel cannot drift into two different products.
"""

from kettle.kettle_main import main

if __name__ == "__main__":
    raise SystemExit(main() or 0)
