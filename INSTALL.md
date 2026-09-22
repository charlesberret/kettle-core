# Installing Kettle

Kettle needs **Python 3.11+** and a curator CLI (default: **`claude`**, logged in). The
server and the CLI viewport are pure stdlib — no pip runtime dependencies.

Source: [github.com/charlesberret/kettle-core](https://github.com/charlesberret/kettle-core)

## Install

Three ways in. Pick by what you are: a user, a stranger with no Python, or a contributor.

| You want | Do this | You get |
|---|---|---|
| To use Kettle | `uv tool install kettle` (or `pipx install kettle`) | `kettle` on PATH, its own isolated environment, upgrades with one command |
| No Python at all | Download the `kettle` binary from a release, `chmod +x`, put it on PATH | One 9 MB file; sitting, kits and interpreter are inside it |
| To work on Kettle | Clone, then `python3 -m venv .venv && .venv/bin/pip install -e .` | Editable checkout: docs, kits and prompts edit in place |

All three answer the same way:

```sh
kettle --version          # kettle X.Y.Z (api 0, desk schema 0)
kettle doctor             # install health, read-only
kettle projects           # the CLI viewport
kettle --web              # the sitting in a browser
```

`kettle doctor` never repairs, never deletes PATH entries, and never binds or probes port
`4242` — that is the live window's port.

### The rule that matters: one `kettle` on PATH

Two installs answering to the same name is the only install problem that actually bites.
`kettle doctor` fails when `which -a kettle` finds installs that resolve to genuinely
different targets; a single install anywhere is fine, canonical venv or not.

```sh
which -a kettle    # expect one path (or several symlinks to the same file)
hash -r            # after any change, clear the shell's command cache
kettle doctor
```

### Standalone binary

Build it yourself from a checkout — no Python needed on the machine that runs the result:

```sh
tools/build-binary.sh            # writes dist/kettle, then smoke-tests it
./dist/kettle --version
```

The script builds in a throwaway venv (PyInstaller is a build-time dependency only; the
shipped package stays stdlib-only), bundles `static/` and `kits/` inside the executable,
and then proves the bundle: `doctor`, an ephemeral-port server boot, `GET /api/ping` with
the discovery token, and `GET /` returning the real sitting. It never uses port 4242.

Use the binary for a machine without Python, a stranger trying Kettle once, or a hook
script that must not depend on which interpreter is on PATH.

### Contributor checkout

```sh
git clone https://github.com/charlesberret/kettle-core.git
cd kettle-core
python3 -m venv .venv
.venv/bin/pip install -e .
.venv/bin/kettle doctor
python3 -m pytest -q
```

**Reinstall rule.** The installable unit is the `kettle/` package. If `kettle doctor`
reports `package-import` red — the package does not import, or its bundled `static/` and
`kits/` are missing — reinstall editable:

```sh
.venv/bin/pip install -e .
```

`~/.kettle-venv` is still a perfectly good home for that venv, and the desktop build
script looks for it, but nothing requires it any more.

### Wheel

```sh
python3 -m build --wheel
python3 -m pip install dist/kettle-*.whl
```

The wheel ships the `kettle` package **plus** bundled `static/` (the sitting) and `kits/`
(prompts and kind playbooks), so a non-editable install serves the browser UI. CI builds
the wheel, audits that package data, installs into a clean venv, and smokes `kettle
--help`, imports, doctor, and a short server boot (`GET /`, `/api/ping`, `/api/kits`) on
an ephemeral port.

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
kettle themes                   list bundled and user color themes
kettle add     <folder>         register a folder as a desk
kettle init                      register the current folder
kettle found   <project>        curator founds the desk
kettle queue   <project>        show a desk's queue
kettle open    <project> <id>   edit the file in the built-in TUI (--external for $EDITOR)
kettle edit    <project> <id>   same as `open` (built-in syntax-colored TUI)
kettle chat    <project> [id]   talk to the curator
kettle lineage <project>        who edited what
kettle bind    <project>        add lineage directive to CLAUDE.md
kettle doctor                   install + runtime health
kettle migrate [--apply]        migrate .setsweep/ → .kettle/ (dry-run by default)
kettle sweep-status <project>   CLOSE readiness
kettle sweep-close  <project>   quiet mechanical CLOSE
kettle sweep-archive <project>  archive queue entries
kettle refresh-briefs <project> rewrite briefs on the current queue (no restock)
kettle egress <project> …       stage a desk egress memo
kettle egress-status <project>  list staged egress memos
```

Full help: `kettle --help` prints this list plus `kettle.__version__`. `kettle <cmd>
--help` prints that subcommand's own argparse help (usage/arguments) — it does not
print the version.

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

### Migrating from Setsweep

`kettle migrate` renames legacy desks and, when applicable, moves the legacy user
registry. **Dry-run is the default** (prints the plan, writes nothing). Pass
`--apply` to write.

```sh
kettle migrate              # dry-run: show what would change
kettle migrate --apply      # rename .setsweep/ → .kettle/ (and registry if needed)
kettle migrate --apply mydesk   # one project only (skips user-registry move)
```

Rules:

- One writable desk per project: if both `.kettle/` and `.setsweep/` already exist,
  migrate **refuses** (exit status 1) and changes nothing. Resolve the split by hand.
- Happy path is a rename of `.setsweep/` → `.kettle/` (not a copy that leaves both).
- When `DESK_PROJECTS` is unset and only the legacy Setsweep user registry exists,
  `--apply` moves `projects.json` (and a sibling `settings.json` when present) to the
  Kettle user path. If the Kettle registry already exists, the registry step is skipped.

`kettle doctor` reports legacy desks and split risk; its docs pointer names this
section and `kettle migrate --help`.

**Sync tip:** exclude `.kettle/runtime/` from file-sync tools so the queue/chatlog/snapshots
do not race. Durable charter/memory files under `.kettle/` may sync normally. See
[`ARCHITECTURE.md`](./ARCHITECTURE.md).

## Notes for the maintainer

- **One `kettle` on PATH** is the rule; `~/.kettle-venv` is conventional, not required — see above.
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
