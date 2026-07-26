#!/usr/bin/env python3
"""Compatibility entrypoint for the former ``setsweep-watch`` command."""

from kettle_watch import main


if __name__ == "__main__":
    raise SystemExit(main())
