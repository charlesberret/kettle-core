"""Fan scenario runs out through a runner command and write ``scores.json``.

Rows are emitted in scenario-file order. ``--parallel`` changes how many runner
processes are in flight, not the order of the file. A runner that exits non-zero
becomes one ``error`` row; the remaining scenarios still run.
"""

from __future__ import annotations

import hashlib
import json
import os
import shlex
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from .rubric import Rubric
from .scenarios import Scenario
from .schema import SchemaError, validate

NOTES_LIMIT = 4000
ERROR_LIMIT = 500


class RunError(ValueError):
    pass


def run_id_for(rubric_sha256: str, scenario_id: str) -> str:
    digest = hashlib.sha256(f"{rubric_sha256}\n{scenario_id}".encode("utf-8")).hexdigest()
    return digest[:16]


def runner_argv(template: str, scenario_id: str) -> list[str]:
    if "{scenario}" not in template:
        raise RunError("runner command must include {scenario}")
    if "\x00" in template or "\x00" in scenario_id:
        raise RunError("runner command cannot contain NUL")
    marked = template.replace("{scenario}", "\x00")
    try:
        parts = shlex.split(marked, posix=True)
    except ValueError as exc:
        raise RunError(f"runner command is not a valid command: {exc}") from exc
    return [part.replace("\x00", scenario_id) for part in parts]


def execute(
    rubric: Rubric,
    scenarios: list[Scenario],
    runner: str,
    *,
    parallel: int = 1,
    timeout: float = 60,
    cwd: Path | None = None,
) -> list[dict]:
    if parallel < 1:
        raise RunError("--parallel must be at least 1")
    if timeout <= 0:
        raise RunError("--timeout must be positive")
    # Fail the batch before any scenario starts when the template itself is unusable.
    runner_argv(runner, "scenario")
    cwd = cwd or Path(__file__).resolve().parent
    workers = min(parallel, len(scenarios))

    def one(scenario: Scenario) -> dict:
        return _run_one(
            rubric, scenario, runner, timeout=timeout, cwd=cwd
        )

    if workers == 1:
        rows = [one(scenario) for scenario in scenarios]
    else:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = [pool.submit(one, scenario) for scenario in scenarios]
            rows = [future.result() for future in futures]
    validate(rows)
    return rows


def canonical_scores(rows: list[dict]) -> str:
    """Byte-stable JSON. Key order matches the score-file contract."""
    payload = []
    for row in rows:
        item = {
            "scenario": row["scenario"],
            "run_id": row["run_id"],
            "rubric_version": row["rubric_version"],
            "rubric_sha256": row["rubric_sha256"],
            "scores": row["scores"],
            "notes": row["notes"],
        }
        if row.get("error"):
            item["error"] = row["error"]
        payload.append(item)
    return json.dumps(payload, indent=2, ensure_ascii=False) + "\n"


def write_scores(path: Path | str, rows: list[dict]) -> None:
    path = Path(path)
    text = canonical_scores(rows)
    try:
        validate(json.loads(text))
    except SchemaError as exc:
        raise RunError(f"refusing to write scores that fail the schema: {exc}") from exc
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text, encoding="utf-8", newline="\n")
    os.replace(tmp, path)


def verify_scores(path: Path | str, rubric: Rubric) -> list[str]:
    """Return human-readable problems. An empty list means the hash matches."""
    path = Path(path)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [f"cannot read scores: {exc}"]
    try:
        validate(data)
    except SchemaError as exc:
        return [f"scores do not match the schema: {exc}"]
    problems = []
    for index, row in enumerate(data):
        recorded = row.get("rubric_sha256")
        if recorded != rubric.sha256:
            problems.append(
                f"{row.get('scenario', index)}: recorded {recorded} "
                f"but {rubric.path.name} is {rubric.sha256}"
            )
    return problems


def _run_one(
    rubric: Rubric,
    scenario: Scenario,
    runner: str,
    *,
    timeout: float,
    cwd: Path,
) -> dict:
    base = {
        "scenario": scenario.id,
        "run_id": run_id_for(rubric.sha256, scenario.id),
        "rubric_version": rubric.version,
        "rubric_sha256": rubric.sha256,
    }
    try:
        argv = runner_argv(runner, scenario.id)
    except RunError as exc:
        return _error(base, str(exc))
    payload = _stdin_payload(rubric, scenario)
    env = os.environ.copy()
    env.update(
        {
            "JUDGE_SCENARIO": scenario.id,
            "JUDGE_FIXTURE": str(scenario.fixture),
            "JUDGE_RUBRIC": str(rubric.path),
            "JUDGE_RUBRIC_VERSION": rubric.version,
            "JUDGE_RUBRIC_SHA256": rubric.sha256,
        }
    )
    try:
        completed = subprocess.run(
            argv,
            input=json.dumps(payload, ensure_ascii=False),
            text=True,
            capture_output=True,
            timeout=timeout,
            cwd=str(cwd),
            env=env,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return _error(base, f"runner timed out after {timeout:g}s")
    except OSError as exc:
        detail = exc.strerror or str(exc)
        return _error(base, f"runner failed to start: {detail}")
    parsed, parse_error = _parse_runner_stdout(completed.stdout, rubric)
    if completed.returncode != 0:
        detail = _collapse(completed.stderr) or _collapse(completed.stdout)
        message = f"runner exited {completed.returncode}"
        if detail:
            message = f"{message}: {detail}"
        if parsed is None:
            return _error(base, message)
        return _finish(base, parsed[0], parsed[1], rubric, error=message)
    if parsed is None:
        return _error(base, parse_error or "runner stdout is not a JSON object")
    return _finish(base, parsed[0], parsed[1], rubric)


def _stdin_payload(rubric: Rubric, scenario: Scenario) -> dict:
    raw = dict(scenario.raw)
    raw["fixture"] = str(scenario.fixture)
    return {
        "id": scenario.id,
        "title": scenario.title,
        "fixture": str(scenario.fixture),
        "rubric": {
            "version": rubric.version,
            "sha256": rubric.sha256,
            "dimensions": list(rubric.dimensions),
            "path": str(rubric.path),
        },
        "scenario": raw,
    }


def _parse_runner_stdout(stdout: str, rubric: Rubric) -> tuple[tuple[dict, str] | None, str | None]:
    text = stdout.lstrip("\ufeff").strip()
    if not text:
        return None, "runner stdout is empty"
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return None, "runner stdout is not JSON"
    if not isinstance(data, dict):
        return None, "runner stdout is not a JSON object"
    scores = data.get("scores", {})
    notes = data.get("notes", "")
    if not isinstance(scores, dict):
        return None, "scores is not an object"
    clean: dict[str, int] = {}
    for key, value in scores.items():
        if not isinstance(key, str) or not key:
            return None, "a score name is empty"
        if isinstance(value, bool) or not isinstance(value, int):
            return None, f"score {key} is not an integer"
        clean[key] = value
    if not isinstance(notes, str):
        return None, "notes is not a string"
    notes = notes.strip()
    if len(notes) > NOTES_LIMIT:
        notes = notes[:NOTES_LIMIT] + "…"
    return (_order_scores(clean, rubric.dimensions), notes), None


def _order_scores(scores: dict[str, int], dimensions: tuple[str, ...]) -> dict[str, int]:
    ordered: dict[str, int] = {}
    for dim in dimensions:
        if dim in scores:
            ordered[dim] = scores[dim]
    for key in sorted(scores):
        if key not in ordered:
            ordered[key] = scores[key]
    return ordered


def _finish(base: dict, scores: dict, notes: str, rubric: Rubric, error: str | None = None) -> dict:
    row = {
        **base,
        "scores": _order_scores(scores, rubric.dimensions),
        "notes": notes,
    }
    if error:
        row["error"] = _limit(error, ERROR_LIMIT)
    return row


def _error(base: dict, message: str) -> dict:
    return {**base, "scores": {}, "notes": "", "error": _limit(message, ERROR_LIMIT)}


def _collapse(text: str) -> str:
    return " ".join(text.split())


def _limit(text: str, limit: int) -> str:
    text = text.strip()
    if len(text) <= limit:
        return text
    return text[:limit] + "…"
