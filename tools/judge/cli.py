"""``judge run`` and ``judge verify``."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .engine import RunError, execute, verify_scores, write_scores
from .rubric import RubricError, load_rubric
from .scenarios import JUDGE_ROOT, ScenarioError, load_scenarios


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="judge",
        description="Versioned sitting judge. Scores scenarios through a runner command.",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    run = sub.add_parser("run", help="score every scenario and write scores.json")
    run.add_argument("--rubric", required=True, help="rubric path or name under rubrics/")
    run.add_argument(
        "--scenarios", required=True, help="scenario file path or name under scenarios/",
    )
    run.add_argument(
        "--runner",
        required=True,
        help='command template; {scenario} is replaced with the scenario id',
    )
    run.add_argument(
        "--parallel", type=int, default=1, help="runner processes in flight (default 1)",
    )
    run.add_argument("--out", required=True, help="scores.json path")
    run.add_argument(
        "--timeout", type=float, default=60, help="per-scenario seconds (default 60)",
    )

    verify = sub.add_parser("verify", help="recompute the rubric hash and check a scores file")
    verify.add_argument("scores", help="scores.json to check")
    verify.add_argument("--rubric", required=True, help="rubric path or name under rubrics/")

    args = parser.parse_args(argv)
    try:
        if args.cmd == "run":
            return _cmd_run(args)
        return _cmd_verify(args)
    except (RubricError, ScenarioError, RunError) as exc:
        print(f"judge: {exc}", file=sys.stderr)
        return 2


def _cmd_run(args) -> int:
    rubric = load_rubric(resolve_rubric(args.rubric))
    _, scenarios = load_scenarios(resolve_scenarios(args.scenarios))
    rows = execute(
        rubric,
        scenarios,
        args.runner,
        parallel=args.parallel,
        timeout=args.timeout,
    )
    out = Path(args.out)
    write_scores(out, rows)
    errors = sum(1 for row in rows if row.get("error"))
    print(f"wrote {out} ({len(rows)} rows, {errors} errors)")
    return 1 if errors else 0


def _cmd_verify(args) -> int:
    rubric = load_rubric(resolve_rubric(args.rubric))
    problems = verify_scores(args.scores, rubric)
    if problems:
        print(f"{args.scores}: does not match {rubric.path.name}", file=sys.stderr)
        for problem in problems:
            print(f"  {problem}", file=sys.stderr)
        return 1
    print(
        f"{args.scores}: matches {rubric.path.name} "
        f"(version {rubric.version}, sha256 {rubric.sha256})"
    )
    return 0


def resolve_rubric(spec: str) -> Path:
    return _resolve(spec, JUDGE_ROOT / "rubrics", (".md",))


def resolve_scenarios(spec: str) -> Path:
    return _resolve(spec, JUDGE_ROOT / "scenarios", (".yaml", ".yml"))


def _resolve(spec: str, directory: Path, suffixes: tuple[str, ...]) -> Path:
    raw = Path(spec)
    candidates = []
    if raw.is_absolute():
        candidates.append(raw)
    else:
        candidates.append(Path.cwd() / raw)
        candidates.append(directory / raw)
        for suffix in suffixes:
            name = raw.name if raw.suffix else spec
            if not str(name).endswith(suffix):
                candidates.append(directory / f"{name}{suffix}")
    seen: set[Path] = set()
    for candidate in candidates:
        if candidate in seen:
            continue
        seen.add(candidate)
        if candidate.is_file():
            return candidate.resolve()
    raise RunError(f"not found: {spec}")
