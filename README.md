# Kettle Core

**The local-first review desk for agent work.**

[![Tests](https://github.com/charlesberret/kettle-core/actions/workflows/test.yml/badge.svg)](https://github.com/charlesberret/kettle-core/actions/workflows/test.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-3776AB.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-yellow.svg)](./LICENSE)

Kettle helps you review work prepared by coding and writing agents. A curator
packs a short brief for each queue item; you read, edit, comment, and approve;
a sweep closes the sitting and restocks the queue.

This repository owns the Python core, first-class CLI, localhost API, desk
format, curator kits, and reference web UI. The public project home is
**[charlesberret/kettle](https://github.com/charlesberret/kettle)**. Reviewing
the tree: [`docs/REVIEW.md`](./docs/REVIEW.md).

```text
queue  →  editor  →  ruling
          ↕
   project/.kettle/
```

## Install

```sh
uv tool install --upgrade git+https://github.com/charlesberret/kettle-core.git
```

That puts `kettle` on your PATH. [`tools/install.sh`](./tools/install.sh) runs the
same install with uv, or with pipx if that is what you have. The name `kettle`
on PyPI, Homebrew, and npm already belongs to other projects, so the install
uses this git URL. Checkout, wheel, and a binary you build yourself:
[INSTALL.md](./INSTALL.md).

## Try it

Kettle requires Python 3.11 or newer and a supported agent CLI with its own
authentication already configured. The default curator is
[Claude Code](https://docs.anthropic.com/en/docs/claude-code); Kettle never asks
for or stores the provider API key.

```sh
kettle doctor
kettle --web
```

From a checkout of this repository, the same check is the venv binary:

```sh
git clone https://github.com/charlesberret/kettle-core.git
cd kettle-core
python3 -m venv .venv
.venv/bin/pip install -e .
.venv/bin/kettle doctor
.venv/bin/kettle-web
```

`doctor` accepts that `.venv/bin/kettle` even when `kettle` is not on PATH.
Activate the venv before the bare commands below (`source .venv/bin/activate`),
or keep the `.venv/bin/` prefix.

Open [http://127.0.0.1:4242](http://127.0.0.1:4242), add a project folder (a
founding sentence is required), and complete the founding interview. You can
also stay in the terminal:

```sh
kettle projects
kettle add ~/path/to/project
kettle queue <project>
kettle open <project> <entry>
kettle chat <project> <entry>
kettle sweep-status <project>
```

Run `kettle --help` and `kettle <command> --help` for the installed command
surface. See [INSTALL.md](./INSTALL.md) for a durable user installation and PATH
hygiene.

## What is a desk?

The desk is ordinary, inspectable project state:

```text
project/
  .kettle/
    PROJECT.md
    MEMORY.md
    FAMILIARITY.md
    SWEEP-ACTIONS.md
    outbound/
    runtime/        # high-churn state; exclude from file sync
```

Every viewport attaches to the same desk and API:

- `kettle-web` / `kettle --web` (HTTP sitting) and the CLI subcommands ship here.
  Bare `kettle` execs [kettle-tui](https://github.com/charlesberret/kettle-tui).
- [kettle-vscode](https://github.com/charlesberret/kettle-vscode) serves VS Code
  and Cursor.
- [kettle-desktop](https://github.com/charlesberret/kettle-desktop) is a thin
  macOS shell over this repository's web UI.

Adapters never own desk migrations or product semantics. The versioned contract
is published by `GET /api/ping`; current API and desk-schema versions live in
[kettle_contract.py](./kettle/kettle_contract.py).

## Setsweep migration

Kettle is the continuation of Setsweep. The transition is intentionally
non-destructive:

- New projects use `.kettle/`.
- Existing `.setsweep/` desks are used in place when no `.kettle/` desk exists.
- `kettle` and `kettle-watch` are canonical; the old `setsweep` command names
  remain compatibility aliases for now.
- The core recognizes both `app: "kettle"` and legacy `app: "setsweep"` peers
  on port 4242.
- Branding alone does not change the API or desk-schema contract integers.

Kettle never creates two live desks for the same project. `kettle migrate` (dry-run by
default; `--apply` to write) handles the final on-disk rename — see
[INSTALL.md § Migrating from Setsweep](./INSTALL.md#migrating-from-setsweep).

## Development

The runtime is Python standard library only. Development and test dependencies
are optional:

```sh
python3 -m venv .venv
.venv/bin/pip install -e '.[dev]'
.venv/bin/python -m pytest
python3 tools/check_family.py
```

The test suite is serial because several integration tests replace module-level
server state and bind ephemeral localhost ports. Cross-repository validation is
documented in [docs/REPOSITORIES.md](./docs/REPOSITORIES.md).

## Security and privacy

- The server binds to `127.0.0.1`.
- File access is resolved and fenced to registered project roots, plus any
  explicitly configured `KETTLE_ALLOWED_ROOTS`.
- Founding interviews use a deterministic, tool-less survey snapshot.
- Outbound email, Slack, webhooks, and launch actions are staged as desk egress;
  Kettle does not transmit them.
- There is no telemetry or analytics endpoint.

Please report vulnerabilities privately as described in
[SECURITY.md](./SECURITY.md).

## Documentation

- [Architecture and invariants](./ARCHITECTURE.md)
- [HTTP and NDJSON API](./API.md)
- [Install guide](./INSTALL.md)
- [Repository ownership and compatibility](./docs/REPOSITORIES.md)
- [Viewport capability matrix](./docs/PLATFORMS.md)
- [Curator kits](./kettle/kits/README.md)
- [Roadmap](./ROADMAP.md)
- [Changelog](./CHANGELOG.md)
- [Contributing](./CONTRIBUTING.md)

## Status

Kettle is pre-1.0 and already used for real review sittings. Interfaces may
change while the product is shaped, but changes to the desk and API are tracked
explicitly through their contract versions.

## License

Kettle Core is MIT licensed. Bundled web assets retain their own licenses; see
[THIRD_PARTY_NOTICES.md](./THIRD_PARTY_NOTICES.md).
