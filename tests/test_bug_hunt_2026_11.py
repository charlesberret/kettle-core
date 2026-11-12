"""Strict expected failures.

- relative path under the supplied base:
  https://github.com/charlesberret/kettle-core/issues/45
- one bad working-record line aborts the read:
  https://github.com/charlesberret/kettle-core/issues/44
- a corrupt session file is read as empty:
  https://github.com/charlesberret/kettle-core/issues/48
- saving over corrupt settings drops the unread bytes:
  https://github.com/charlesberret/kettle-core/issues/47
- string and numeric queue ids do not match:
  https://github.com/charlesberret/kettle-core/issues/46

Each test states a contract. While the code does not meet it, pytest reports
a strict expected failure.
"""

from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path

import pytest

import kettle.lineage as lineage
import kettle.server as server


@pytest.fixture
def twin_desks(monkeypatch):
    """Two sibling project roots in one registry."""
    tmp = Path(tempfile.mkdtemp(prefix="kettle-bughunt-"))
    proj_a = tmp / "alpha"
    proj_b = tmp / "beta"
    proj_a.mkdir()
    proj_b.mkdir()
    (proj_b / "secret.md").write_text("other desk", encoding="utf-8")

    registry = tmp / "projects.json"
    registry.write_text(
        json.dumps(
            {
                "projects": [
                    {
                        "id": "alpha",
                        "name": "Alpha",
                        "root": str(proj_a),
                        "ledger": None,
                        "rework_agents": [],
                    },
                    {
                        "id": "beta",
                        "name": "Beta",
                        "root": str(proj_b),
                        "ledger": None,
                        "rework_agents": [],
                    },
                ]
            }
        ),
        encoding="utf-8",
    )

    saved = {k: getattr(server, k) for k in ("PROJECTS_PATH", "BASE_ALLOWED_ROOTS")}
    server.PROJECTS_PATH = registry
    server.BASE_ALLOWED_ROOTS = [proj_a]

    yield {"tmp": tmp, "alpha": proj_a, "beta": proj_b}

    for k, v in saved.items():
        setattr(server, k, v)
    shutil.rmtree(tmp, ignore_errors=True)


@pytest.fixture
def settings_sandbox(monkeypatch):
    tmp = Path(tempfile.mkdtemp(prefix="kettle-bughunt-settings-"))
    saved = server.SETTINGS_PATH
    server.SETTINGS_PATH = tmp / "settings.json"
    yield server.SETTINGS_PATH
    server.SETTINGS_PATH = saved
    shutil.rmtree(tmp, ignore_errors=True)


@pytest.mark.xfail(
    strict=True,
    reason="a relative path must stay under the supplied base",
)
def test_safe_path_relative_must_stay_under_base(twin_desks):
    proj_a = twin_desks["alpha"]
    with pytest.raises(PermissionError):
        server.safe_path("../beta/secret.md", base=proj_a)


@pytest.mark.xfail(
    strict=True,
    reason="read_record should skip or surface bad JSONL lines, not abort the whole read",
)
def test_read_record_skips_corrupt_jsonl_line(twin_desks):
    root = twin_desks["alpha"]
    path = lineage.record_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    good = json.dumps(
        {
            "ts": "2026-01-01T00:00:00+00:00",
            "actor": "agent",
            "actor_kind": "agent",
            "files": ["a.md"],
        }
    )
    path.write_text(f"{good}\nNOT JSON\n", encoding="utf-8")
    records = lineage.read_record(root)
    assert len(records) == 1
    assert records[0]["actor"] == "agent"


@pytest.mark.xfail(
    strict=True,
    reason="corrupt session.json must surface JSONDecodeError, not be read as an empty session",
)
def test_load_session_corrupt_json_surfaces_error(twin_desks):
    proj = {"id": "alpha", "root": str(twin_desks["alpha"])}
    sp = server.session_path(proj)
    sp.parent.mkdir(parents=True, exist_ok=True)
    sp.write_text('{"session_id": "keep-me", "status": "founded"', encoding="utf-8")
    with pytest.raises(json.JSONDecodeError):
        server.load_session(proj)


@pytest.mark.xfail(
    strict=True,
    reason="save_settings on corrupt disk should snapshot like load_settings, not merge {}",
)
def test_save_settings_corrupt_disk_preserves_backup(settings_sandbox):
    settings_sandbox.write_text("{not-json", encoding="utf-8")
    server.save_settings({"curator": {"models": {"chat": "example-model"}}})
    backup = settings_sandbox.with_suffix(".json.corrupt")
    assert backup.exists(), "unreadable settings should be backed up before merge-write"


@pytest.mark.xfail(
    strict=True,
    reason="find_entry should match numeric ids when the lookup key is a string",
)
def test_find_entry_coerces_string_and_int_ids():
    queue = {"entries": [{"id": 42, "path": "doc.md", "status": "pending"}]}
    entry = server.find_entry(queue, "42")
    assert entry["path"] == "doc.md"
