"""Core and compatibility identity published to every Kettle viewport.

The product version remains single-sourced in ``pyproject.toml``. The two
integer contract versions advance only when their public surfaces change
incompatibly:

* ``API_VERSION`` covers the localhost HTTP and NDJSON contract.
* ``DESK_SCHEMA_VERSION`` covers durable files under ``<project>/.kettle/``.

Version 0 is deliberately pre-stable. Clients can still make explicit
compatibility decisions against it; moving to 1 is the compatibility promise.
"""

from __future__ import annotations

import importlib.metadata
import tomllib
from pathlib import Path


DIST_NAME = "kettle"
API_VERSION = 0
DESK_SCHEMA_VERSION = 0


def core_version() -> str:
    """Return the source version, falling back to installed distribution metadata."""
    pyproject = Path(__file__).with_name("pyproject.toml")
    if pyproject.is_file():
        try:
            with pyproject.open("rb") as fp:
                return str(tomllib.load(fp)["project"]["version"])
        except (OSError, KeyError, TypeError, tomllib.TOMLDecodeError):
            pass
    try:
        return importlib.metadata.version(DIST_NAME)
    except importlib.metadata.PackageNotFoundError:
        return "unknown"


def identity() -> dict[str, str | int]:
    """Return the public identity embedded in ``GET /api/ping`` and bundles."""
    return {
        "version": core_version(),
        "api_version": API_VERSION,
        "desk_schema_version": DESK_SCHEMA_VERSION,
    }
