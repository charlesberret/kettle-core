# Installing Kettle

Kettle needs **Python 3.11+** and a curator CLI (default: **`claude`**, logged in). The
server and the CLI viewport are pure stdlib — no pip runtime dependencies.

Source: [github.com/charlesberret/kettle-core](https://github.com/charlesberret/kettle-core)

## Canonical install

**One install, one name on PATH.**

| Piece | Location |
|---|---|
| Venv (canonical) | `~/.kettle-venv` |
| Editable source | clone of this repo |
| Console script | `~/.kettle-venv/bin/kettle` |
| PATH shim (exactly one) | e.g. `~/.local/bin/kettle` → `~/.kettle-venv/bin/kettle` |

`kettle doctor` reports which `kettle` wins on `PATH`, whether it resolves to the
canonical venv, whether every `py-modules` entry is importable, registry/desk integrity,
active curator CLI resolve, runtime discovery, and a localhost ping when discovery lists
a non-conventional port. It never repairs, never deletes PATH entries, and never binds
or probes port `4242`.

### Quick start — CLI + browser

```sh
git clone https://github.com/charlesberret/kettle-core.git
cd kettle-core
python3 -m venv ~/.kettle-venv
~/.kettle-venv/bin/pip install -e .
~/.kettle-venv/bin/kettle projects        # the CLI viewport
~/.kettle-venv/bin/kettle --web           # browser mode
```

Put **one** shim on your PATH pointing at the venv (not a second copy of the script):

```sh
ln -sf ~/.kettle-venv/bin/kettle ~/.local/bin/kettle   # dir must be on PATH
hash -r                                                    # clear shell command cache
which -a kettle                                          # expect one path
kettle doctor                                            # install health
```

### Reinstall rule (editable)

This package is **flat** (`py-modules` in `pyproject.toml`). An editable install records
that list in the finder MAPPING at install time. **Adding a module to `py-modules`
requires reinstalling editable**, or the CLI dies with `ModuleNotFoundError` for the new
name even though the file is in the tree:

```sh
~/.kettle-venv/bin/pip install -e .
```

`kettle doctor` checks that every name in `py-modules` is importable and present in the
installed distribution's top-level list. It also prints Python/package version, install
mode (editable vs wheel), provider CLI readiness, registry/desk integrity (including
legacy `.setsweep/` hints), and server discovery status. Failing rows point at this file
or `ARCHITECTURE.md`. Exit status is nonzero when any check fails.

### PATH hygiene (you run these; agents never delete PATH entries)

If `which -a kettle` shows more than one winner, retire strays so a single shim points
at `~/.kettle-venv/bin/kettle`. Common extras: a Homebrew or pip-user console script,
and leftover shell shims from older installs. Keep only the symlink under a dir on PATH
(e.g. `~/.local/bin/kettle`), then `hash -r` and re-run `kettle doctor`.

## Other ways to open Kettle

The public **product home** is
[charlesberret/kettle](https://github.com/charlesberret/kettle). This repository
is the runnable core. Other hosts are adapters over it:

| Host | Repo | Notes |
|------|------|--------|
| macOS `.app` | [kettle-desktop](https://github.com/charlesberret/kettle-desktop) | Electron shell; general public install later |
| VS Code / Cursor | [kettle-vscode](https://github.com/charlesberret/kettle-vscode) | One VSIX for both hosts |

Neither is required for CLI or browser use of this core.

## Viewports

This repo ships the browser/server and CLI viewports.

```
kettle                          browser / server mode   (default; stdlib only)
kettle --web [--port N]         same as bare launch
kettle projects                 list registered desks
kettle add     <folder>         register a folder as a desk
kettle init                      register the current folder
kettle found   <project>        curator founds the desk
kettle queue   <project>        show a desk's queue
kettle open    <project> <id>   open the file in $EDITOR
kettle chat    <project> [id]   talk to the curator
kettle lineage <project>        who edited what
kettle bind    <project>        add lineage directive to CLAUDE.md
kettle doctor                   install + runtime health
kettle sweep-status <project>   CLOSE readiness
kettle sweep-close  <project>   quiet mechanical CLOSE
kettle sweep-archive <project>  archive queue entries
kettle egress <project> …       stage a desk egress memo
kettle egress-status <project>  list staged egress memos
```

Full help: `kettle --help` / `kettle <cmd> --help`.

## Wheel / pipx installs (CI-verified; limited)

CI builds a wheel and installs it into a clean venv (and a pipx-style isolated venv) on
supported Python versions. That proves console scripts and flat `py-modules` import
cleanly. **Editable install remains the supported path for real use** — the current flat
layout does **not** ship `static/` or `kits/` inside the wheel, so a non-editable install
cannot serve the browser UI or load kit prompts from package data.

Follow-up (package restructure under `kettle/` with bundled resources): see
[`docs/briefs/11-package-restructure.md`](./docs/briefs/11-package-restructure.md) and
the Installation section of [`ROADMAP.md`](./ROADMAP.md).

## Auth — Kettle stores no key

It uses the active curator CLI’s own login:

| Provider | CLI | Typical ambient auth |
|----------|-----|----------------------|
| Claude (default) | `claude` | Claude login / `ANTHROPIC_API_KEY` |
| Grok | `grok` | Grok login / `XAI_API_KEY` |
| ChatGPT | `codex` | ChatGPT login / `OPENAI_API_KEY` or `CODEX_API_KEY` |
| Gemini | `gemini` | Gemini login / `GEMINI_API_KEY` |

No API key is ever entered into Kettle.

## Registering a desk

The project registry is `projects.json` (see `projects.example.json`). Override with
`DESK_PROJECTS`. Resolution without an override prefers the shared Kettle user registry
when it exists (`~/Library/Application Support/Kettle/projects.json` on macOS), then an
existing legacy Setsweep registry, then a repo-local `projects.json` in a source checkout.
See [`API.md`](./API.md).

Each project points at a directory; new desk state lives in `<root>/.kettle/`.
An existing `<root>/.setsweep/` desk remains active in place until explicitly
migrated, preventing split state. Add a project with `kettle add <dir>`, by editing
the registry, or via the app's admin panel. The
bundled Electron `.app` always uses Application Support (sets `DESK_PROJECTS`).

**Sync tip:** exclude `.kettle/runtime/` from file-sync tools so the queue/chatlog/snapshots
do not race. Durable charter/memory files under `.kettle/` may sync normally. See
[`ARCHITECTURE.md`](./ARCHITECTURE.md).

## Notes for the maintainer

- **Canonical install is `~/.kettle-venv` with one PATH shim** — see above.
- **Editable install (`-e`) is the supported mode.** It keeps `static/` resolving from the
  source tree. Wheel/pipx CI verifies import + console-script smoke only until the
  package restructure lands.
- **Reinstall after every `py-modules` change** — see the reinstall rule and the comment
  next to `py-modules` in `pyproject.toml`.
- **`kettle doctor` is read-only** — it never creates desks, rewrites settings, or probes
  port `4242`.
