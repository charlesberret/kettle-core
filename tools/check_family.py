#!/usr/bin/env python3
"""Status/compatibility checker with an optional serial Kettle family test run."""

from __future__ import annotations

import argparse
import ast
import json
import subprocess
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Repo:
    name: str
    path: Path
    test_command: tuple[str, ...]


def run(repo: Repo, *args: str, capture: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        cwd=repo.path,
        check=False,
        text=True,
        capture_output=capture,
    )


def git_value(repo: Repo, *args: str) -> str:
    result = run(repo, "git", *args)
    return result.stdout.strip() if result.returncode == 0 else "unknown"


def is_checkout(repo: Repo) -> bool:
    return git_value(repo, "rev-parse", "--is-inside-work-tree") == "true"


def dirty(repo: Repo) -> bool:
    return bool(git_value(repo, "status", "--porcelain"))


def json_object(path: Path) -> dict:
    with path.open(encoding="utf-8") as fp:
        value = json.load(fp)
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def core_version(core: Repo) -> str:
    with (core.path / "pyproject.toml").open("rb") as fp:
        return str(tomllib.load(fp)["project"]["version"])


def contract_versions(core: Repo) -> tuple[int, int]:
    path = core.path / "kettle" / "kettle_contract.py"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found: dict[str, int] = {}
    for node in tree.body:
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        if (
            isinstance(target, ast.Name)
            and target.id in {"API_VERSION", "DESK_SCHEMA_VERSION"}
            and isinstance(node.value, ast.Constant)
            and type(node.value.value) is int
        ):
            found[target.id] = node.value.value
    missing = {"API_VERSION", "DESK_SCHEMA_VERSION"} - found.keys()
    if missing:
        raise ValueError(f"{path} lacks literal integer values for {sorted(missing)}")
    if any(value < 0 for value in found.values()):
        raise ValueError(f"{path} contract versions must be nonnegative integers")
    return found["API_VERSION"], found["DESK_SCHEMA_VERSION"]


def package_version(repo: Repo, relative: str) -> str:
    return str(json_object(repo.path / relative)["version"])


def compatibility_support(path: Path) -> tuple[set[int], set[int]]:
    data = json_object(path)
    api_values = data.get("api_versions", data.get("apiVersions"))
    desk_values = data.get("desk_schema_versions", data.get("deskSchemaVersions"))
    if api_values is None or desk_values is None:
        raise ValueError(
            f"{path} must declare api_versions/apiVersions and "
            "desk_schema_versions/deskSchemaVersions"
        )
    for label, values in (("API", api_values), ("desk-schema", desk_values)):
        if (
            not isinstance(values, list)
            or any(type(value) is not int or value < 0 for value in values)
        ):
            raise ValueError(
                f"{path} {label} versions must be a JSON array of nonnegative integers"
            )
    api = set(api_values)
    desk = set(desk_values)
    if not api or not desk:
        raise ValueError(f"{path} must declare at least one API and desk-schema version")
    return api, desk


def status_line(repo: Repo, version: str) -> str:
    branch = git_value(repo, "branch", "--show-current") or "(detached)"
    head = git_value(repo, "rev-parse", "--short=12", "HEAD")
    state = "DIRTY" if dirty(repo) else "clean"
    return f"{repo.name:8} {version:10} {branch:28} {head}  {state}\n         {repo.path}"


def parse_args() -> argparse.Namespace:
    core_default = Path(__file__).resolve().parents[1]
    siblings = core_default.parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--core", type=Path, default=core_default)
    parser.add_argument("--desktop", type=Path, default=siblings / "kettle-desktop")
    parser.add_argument(
        "--vscode",
        "--plugin",
        dest="vscode",
        type=Path,
        default=siblings / "kettle-vscode",
        help="VS Code/Cursor adapter checkout (the --plugin spelling is deprecated)",
    )
    parser.add_argument("--require-clean", action="store_true")
    parser.add_argument(
        "--run-tests",
        action="store_true",
        help="run core, desktop, and VS Code tests serially after compatibility checks",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repos = [
        Repo("core", args.core.resolve(), (sys.executable, "-m", "pytest")),
        Repo("desktop", args.desktop.resolve(), ("npm", "test")),
        Repo("vscode", args.vscode.resolve(), ("npm", "test")),
    ]
    missing = [repo for repo in repos if not repo.path.is_dir() or not is_checkout(repo)]
    if missing:
        print("missing Kettle Git checkouts:", file=sys.stderr)
        for repo in missing:
            print(f"  {repo.name}: {repo.path}", file=sys.stderr)
        return 2

    core, desktop, vscode = repos
    try:
        versions = {
            "core": core_version(core),
            "desktop": package_version(desktop, "package.json"),
            "vscode": package_version(vscode, "package.json"),
        }
        api_version, desk_version = contract_versions(core)
    except (KeyError, OSError, TypeError, ValueError, json.JSONDecodeError, tomllib.TOMLDecodeError) as exc:
        print(f"family metadata error: {exc}", file=sys.stderr)
        return 2

    print("Kettle repository family")
    for repo in repos:
        print(status_line(repo, versions[repo.name]))

    print()
    compatibility_specs = (
        ("desktop", desktop.path / "kettle-compatibility.json"),
        ("vscode", vscode.path / "kettle-compatibility.json"),
    )
    compatible = True
    print(f"contracts core(api={api_version}, desk={desk_version})")
    for name, path in compatibility_specs:
        try:
            supported_api, supported_desk = compatibility_support(path)
        except (KeyError, OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
            compatible = False
            print(f"  {name:8} UNDECLARED => INCOMPATIBLE")
            print(f"{name} compatibility metadata error: {exc}", file=sys.stderr)
            continue
        viewport_ok = api_version in supported_api and desk_version in supported_desk
        compatible = compatible and viewport_ok
        print(
            f"  {name:8} api={sorted(supported_api)}, desk={sorted(supported_desk)} "
            f"=> {'compatible' if viewport_ok else 'INCOMPATIBLE'}"
        )
    print("desktop release builds must also stamp the exact bundled core provenance")

    failed = not compatible
    if args.require_clean and any(dirty(repo) for repo in repos):
        print("clean-tree gate failed", file=sys.stderr)
        failed = True

    if args.run_tests:
        print()
        for repo in repos:
            print(f"==> {repo.name}: {' '.join(repo.test_command)}", flush=True)
            result = run(repo, *repo.test_command, capture=False)
            if result.returncode:
                print(f"{repo.name} tests failed ({result.returncode})", file=sys.stderr)
                failed = True

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
