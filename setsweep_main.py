#!/usr/bin/env python3
"""Compatibility entrypoint for the former ``setsweep`` command.

New installs should use ``kettle``. This alias intentionally shares the exact
same implementation and contracts during the rename transition.
"""

from kettle_main import main


if __name__ == "__main__":
    raise SystemExit(main())
