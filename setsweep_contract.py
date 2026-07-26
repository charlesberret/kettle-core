"""Compatibility import for integrations that still load ``setsweep_contract``."""

from kettle_contract import (  # noqa: F401
    API_VERSION,
    DESK_SCHEMA_VERSION,
    DIST_NAME,
    core_version,
    identity,
)

__all__ = [
    "API_VERSION",
    "DESK_SCHEMA_VERSION",
    "DIST_NAME",
    "core_version",
    "identity",
]
