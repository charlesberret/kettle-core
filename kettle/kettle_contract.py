"""Core and compatibility identity published to every Kettle viewport.

The product version remains single-sourced in ``pyproject.toml`` and surfaced as
``kettle.__version__`` via ``importlib.metadata``. The two integer contract
versions advance only when their public surfaces change incompatibly:

* ``API_VERSION`` covers the localhost HTTP and NDJSON contract.
* ``DESK_SCHEMA_VERSION`` covers durable files under ``<project>/.kettle/``.

Version 0 is deliberately pre-stable. Clients can still make explicit
compatibility decisions against it; moving to 1 is the compatibility promise.
"""

from __future__ import annotations

DIST_NAME = "kettle"
API_VERSION = 0
DESK_SCHEMA_VERSION = 0


def core_version() -> str:
    """Return ``kettle.__version__`` (importlib.metadata / pyproject fallback)."""
    # Local import avoids import cycles during package bootstrap.
    from kettle import __version__

    return __version__


def identity() -> dict[str, str | int]:
    """Return the public identity embedded in ``GET /api/ping`` and bundles."""
    return {
        "version": core_version(),
        "api_version": API_VERSION,
        "desk_schema_version": DESK_SCHEMA_VERSION,
    }
