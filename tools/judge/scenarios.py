"""Load a scenario file. Each scenario names a fixture directory."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from .yamlio import YAMLError, loads

JUDGE_ROOT = Path(__file__).resolve().parent
_ID = re.compile(r"^[a-z][a-z0-9-]{0,63}$")


class ScenarioError(ValueError):
    pass


@dataclass(frozen=True)
class Scenario:
    id: str
    title: str
    fixture: Path
    raw: dict


def load_scenarios(path: Path | str) -> tuple[dict, list[Scenario]]:
    path = Path(path)
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ScenarioError(f"cannot read scenarios {path}: {exc}") from exc
    try:
        data = loads(text)
    except YAMLError as exc:
        raise ScenarioError(f"{path}: {exc}") from exc
    if not isinstance(data, dict) or not isinstance(data.get("scenarios"), list):
        raise ScenarioError(f"{path}: needs a top-level scenarios list")
    items = data["scenarios"]
    if not items:
        raise ScenarioError(f"{path}: scenarios list is empty")
    seen: set[str] = set()
    scenarios: list[Scenario] = []
    for index, item in enumerate(items, 1):
        if not isinstance(item, dict):
            raise ScenarioError(f"{path}: scenario {index} is not a mapping")
        sid = item.get("id")
        fixture_spec = item.get("fixture")
        if not isinstance(sid, str) or not _ID.fullmatch(sid):
            raise ScenarioError(f"{path}: scenario {index} needs an id like empty-folder")
        if sid in seen:
            raise ScenarioError(f"{path}: duplicate scenario id {sid}")
        seen.add(sid)
        if not isinstance(fixture_spec, str) or not fixture_spec.strip():
            raise ScenarioError(f"{path}: scenario {sid} needs a fixture folder")
        fixture = resolve_fixture(fixture_spec, path)
        if not fixture.is_dir():
            raise ScenarioError(f"{path}: fixture for {sid} is not a directory: {fixture}")
        title = item.get("title") or sid
        if not isinstance(title, str):
            raise ScenarioError(f"{path}: scenario {sid} title must be a string")
        scenarios.append(Scenario(id=sid, title=title, fixture=fixture, raw=item))
    return data, scenarios


def resolve_fixture(spec: str, scenario_file: Path) -> Path:
    raw = Path(spec)
    if raw.is_absolute():
        return raw
    candidates = [
        scenario_file.parent / spec,
        JUDGE_ROOT / spec,
        Path.cwd() / spec,
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate.resolve()
    return (JUDGE_ROOT / spec).resolve()
