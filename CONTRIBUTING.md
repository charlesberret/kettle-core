# Contributing to Kettle

Thank you for taking an interest. This repository owns Kettle's Desk, API,
kits, CLI, and reference web UI. The product home and family navigator is
[charlesberret/kettle](https://github.com/charlesberret/kettle).

## Before you start

1. Read the pitch and quickstart in [`README.md`](./README.md).
2. Skim [`ARCHITECTURE.md`](./ARCHITECTURE.md) for invariants (desk files, localhost,
   approve ≠ apply, fenced I/O).
3. For multi-repo work (plugin or desktop), read [`docs/REPOSITORIES.md`](./docs/REPOSITORIES.md):
   **core lands first**, viewports follow the contract.

## Dev setup

```sh
git clone https://github.com/charlesberret/kettle-core.git
cd kettle-core
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
.venv/bin/kettle doctor
.venv/bin/python -m pytest
```

Runtime is **stdlib only**. Optional `dev` extras are for tests and coverage.

## What fits where

| Change | Repo |
|--------|------|
| Desk format, API, kits, web UI, CLI, core roadmap | **This repo** (`kettle-core`) |
| VS Code / Cursor extension | [kettle-vscode](https://github.com/charlesberret/kettle-vscode) |
| macOS Electron shell / packaging | [kettle-desktop](https://github.com/charlesberret/kettle-desktop) |

If a plugin change needs a new API, open the core PR first (or a linked pair), keep the
contract backward-compatible, and advance viewport compatibility manifests after.

## Pull requests

- Prefer small, reviewable diffs with a clear “why.”
- Add or extend tests when you touch contracts, founding, or ritual routes.
- Do not store API keys; do not broaden the network surface without a brief.
- Match existing tone in kits and UI copy (`static/ui-copy.js` is core-owned).

## Code of conduct

Participation across the Kettle repositories is governed by the
[project code of conduct](https://github.com/charlesberret/kettle/blob/main/CODE_OF_CONDUCT.md).

## License

By contributing, you agree your contributions are licensed under the MIT License
in this repository.
