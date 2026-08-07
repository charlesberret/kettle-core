"""Kettle — review instrument core (server, CLI, kits, static UI)."""

from __future__ import annotations

import importlib.metadata
import tomllib
from pathlib import Path

DIST_NAME = "kettle"

# Submodules the install must be able to import (doctor + packaging smoke).
# Adding a new top-level module under kettle/? Append it here and reinstall editable
# only if the distribution metadata is stale — package discovery picks up new .py files.
PACKAGE_MODULES = (
    "cli",
    "curator",
    "egress",
    "gitmap",
    "kettle_contract",
    "kettle_main",
    "kettle_watch",
    "kits",
    "lineage",
    "migrate",
    "runtime",
    "server",
    "survey",
    "sweepkit",
    "syntax",
    "theme_catalog",
    "tui_editor",
)


def _read_version() -> str:
    """Single-source version: installed dist metadata, else pyproject.toml."""
    try:
        return importlib.metadata.version(DIST_NAME)
    except importlib.metadata.PackageNotFoundError:
        pass
    # Editable / source checkout before metadata is available: repo-root pyproject.
    pyproject = Path(__file__).resolve().parent.parent / "pyproject.toml"
    if pyproject.is_file():
        try:
            with pyproject.open("rb") as fp:
                return str(tomllib.load(fp)["project"]["version"])
        except (OSError, KeyError, TypeError, tomllib.TOMLDecodeError):
            pass
    return "unknown"


__version__ = _read_version()

__all__ = ["DIST_NAME", "PACKAGE_MODULES", "__version__"]
