# Installing Kettle

Kettle needs **Python 3.11+** and a curator CLI (default: **`claude`**, logged in). The
server and the CLI viewport are pure stdlib — no pip runtime dependencies.

Source: [github.com/charlesberret/kettle-core](https://github.com/charlesberret/kettle-core)

## Canonical install (editable)

**One install, one name on PATH.** Contributors and day-to-day use still prefer an
editable checkout so docs and kits edit in place.

| Piece | Location |
|---|---|
| Venv (canonical) | `~/.kettle-venv` |
| Editable source | clone of this repo |
| Console script | `~/.kettle-venv/bin/kettle` |
| PATH shim (exactly one) | e.g. `~/.local/bin/kettle` → `~/.kettle-venv/bin/kettle` |

`kettle doctor` reports which `kettle` wins on `PATH`, whether it resolves to the
canonical venv, whether every package module is importable, registry/desk integrity,
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
python3 -c "import kettle; print(kettle.__version__)"
```

Put **one** shim on your PATH pointing at the venv (not a second copy of the script):

```sh
ln -sf ~/.kettle-venv/bin/kettle ~/.local/bin/kettle   # dir must be on PATH
hash -r                                                    # clear shell command cache
which -a kettle                                          # expect one path
kettle doctor                                            # install health
```

### Reinstall rule (editable)

The installable unit is the `kettle/` package. New `.py` files under `kettle/` are
picked up by package discovery after reinstall when metadata is stale. If doctor
reports modules not importable, reinstall editable:

```sh
~/.kettle-venv/bin/pip install -e .
```

`kettle doctor` checks that the installed `top_level` includes `kettle` and that every
name in `kettle.PACKAGE_MODULES` is importable. It also prints Python/package version,
install mode (editable vs wheel), provider CLI readiness, registry/desk integrity
(including legacy `.setsweep/` hints), and server discovery status. Failing rows point
at this file or `ARCHITECTURE.md`. Exit status is nonzero when any check fails.

### PATH hygiene (you run these; agents never delete PATH entries)

If `which -a kettle` shows more than one winner, retire strays so a single shim points
at `~/.kettle-venv/bin/kettle`. Common extras: a Homebrew or pip-user console script,
and leftover shell shims from older installs. Keep only the symlink under a dir on PATH
(e.g. `~/.local/bin/kettle`), then `hash -r` and re-run `kettle doctor`.

## Wheel / pipx installs

The wheel ships the `kettle` package **plus** bundled `static/` (web UI) and `kits/`
(prompts and kind playbooks), so a non-editable install can serve the browser UI.

```sh
python3 -m pip install path/to/kettle-*.whl
# or, once published:  pipx install kettle
kettle --web --port 0          # use an ephemeral port in automation; never probe 4242
kettle doctor
python3 -c "import kettle; print(kettle.__version__)"
```

CI builds the wheel, audits package data, installs into a clean venv, and smokes
`kettle --help`, imports, doctor, and a short server boot (`GET /`, `/api/ping`,
`/api/kits`) on an ephemeral port.

Editable install remains the supported contributor path; wheel/pipx is for users who
want a self-contained install without a checkout.

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

Full help: `kettle --help` / `kettle <cmd> --help` (help prints `kettle.__version__`).

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

The project registry is `projects.json` (see `kettle/projects.example.json`). Override with
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
- **Layout is the `kettle/` package** with `static/` and `kits/` as package data.
  `APPDIR` resolves via `importlib.resources.files()` (PyInstaller still uses `_MEIPASS`).
- **Version** is single-sourced in `pyproject.toml`, exposed as `kettle.__version__`,
  and reported by `GET /api/ping` and `kettle --help`.
- **Editable and wheel installs are both supported** for serving the UI; editable remains
  the contributor path.
- **`kettle doctor` is read-only** — it never creates desks, rewrites settings, or probes
  port `4242`.
- **PyPI placeholder upload** (reserve the `kettle` name with a minimal 0.0.1) remains a
  follow-up until publish credentials are confirmed in this environment.
