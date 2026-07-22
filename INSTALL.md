# Installing Setsweep

Setsweep needs **Python 3.11+** and a curator CLI (default: **`claude`**, logged in). The
server and the CLI viewport are pure stdlib — no pip runtime dependencies.

Source: [github.com/charlesberret/setsweep](https://github.com/charlesberret/setsweep)

## Canonical install

**One install, one name on PATH.**

| Piece | Location |
|---|---|
| Venv (canonical) | `~/.setsweep-venv` |
| Editable source | clone of this repo |
| Console script | `~/.setsweep-venv/bin/setsweep` |
| PATH shim (exactly one) | e.g. `~/.local/bin/setsweep` → `~/.setsweep-venv/bin/setsweep` |

`setsweep doctor` reports which `setsweep` wins on `PATH`, whether it resolves to the
canonical venv, and whether every `py-modules` entry is importable. It never repairs and
never deletes PATH entries.

### Quick start — CLI + browser

```sh
git clone https://github.com/charlesberret/setsweep.git
cd setsweep
python3 -m venv ~/.setsweep-venv
~/.setsweep-venv/bin/pip install -e .
~/.setsweep-venv/bin/setsweep projects        # the CLI viewport
~/.setsweep-venv/bin/setsweep --web           # browser mode
```

Put **one** shim on your PATH pointing at the venv (not a second copy of the script):

```sh
ln -sf ~/.setsweep-venv/bin/setsweep ~/.local/bin/setsweep   # dir must be on PATH
hash -r                                                    # clear shell command cache
which -a setsweep                                          # expect one path
setsweep doctor                                            # install health
```

### Reinstall rule (editable)

This package is **flat** (`py-modules` in `pyproject.toml`). An editable install records
that list in the finder MAPPING at install time. **Adding a module to `py-modules`
requires reinstalling editable**, or the CLI dies with `ModuleNotFoundError` for the new
name even though the file is in the tree:

```sh
~/.setsweep-venv/bin/pip install -e .
```

`setsweep doctor` checks that every name in `py-modules` is importable and present in the
installed distribution's top-level list.

### PATH hygiene (you run these; agents never delete PATH entries)

If `which -a setsweep` shows more than one winner, retire strays so a single shim points
at `~/.setsweep-venv/bin/setsweep`. Common extras: a Homebrew or pip-user console script,
and leftover shell shims from older installs. Keep only the symlink under a dir on PATH
(e.g. `~/.local/bin/setsweep`), then `hash -r` and re-run `setsweep doctor`.

## The native window (macOS)

The Electron shell lives in the sibling **[setsweep-desktop](https://github.com/charlesberret/setsweep-desktop)**
repo (if published). It wraps the server in a proper `.app` (Dock icon, external-link
interception, native folder picker) and may bundle the Python server via PyInstaller.

Editor plugins live in **setsweep-plugin** (VS Code/Cursor first; Obsidian and Sublime
planned). Neither is required for CLI or browser use of this core.

## Viewports

This repo ships the browser/server and CLI viewports.

```
setsweep                          browser / server mode   (default; stdlib only)
setsweep --web [--port N]         same as bare launch
setsweep projects                 list registered desks
setsweep add     <folder>         register a folder as a desk
setsweep init                      register the current folder
setsweep found   <project>        curator founds the desk
setsweep queue   <project>        show a desk's queue
setsweep open    <project> <id>   open the file in $EDITOR
setsweep chat    <project> [id]   talk to the curator
setsweep lineage <project>        who edited what
setsweep bind    <project>        add lineage directive to CLAUDE.md
setsweep doctor                   install health
setsweep sweep-status <project>   CLOSE readiness
setsweep sweep-close  <project>   quiet mechanical CLOSE
setsweep sweep-archive <project>  archive queue entries
setsweep egress <project> …       stage a desk egress memo
setsweep egress-status <project>  list staged egress memos
```

Full help: `setsweep --help` / `setsweep <cmd> --help`.

## Auth — Setsweep stores no key

It uses the active curator CLI’s own login:

| Provider | CLI | Typical ambient auth |
|----------|-----|----------------------|
| Claude (default) | `claude` | Claude login / `ANTHROPIC_API_KEY` |
| Grok | `grok` | Grok login / `XAI_API_KEY` |
| ChatGPT | `codex` | ChatGPT login / `OPENAI_API_KEY` or `CODEX_API_KEY` |
| Gemini | `gemini` | Gemini login / `GEMINI_API_KEY` |

No API key is ever entered into Setsweep.

## Registering a desk

The project registry is `projects.json` (see `projects.example.json`). Override with
`DESK_PROJECTS`. Resolution without an override prefers the shared user registry when it
exists (`~/Library/Application Support/Setsweep/projects.json` on macOS), else a
repo-local `projects.json` in a source checkout — see [`API.md`](./API.md).

Each project points at a directory; desk state lives in `<root>/.setsweep/`. Add a project
with `setsweep add <dir>`, by editing the registry, or via the app's admin panel. The
bundled Electron `.app` always uses Application Support (sets `DESK_PROJECTS`).

**Sync tip:** exclude `.setsweep/runtime/` from file-sync tools so the queue/chatlog/snapshots
do not race. Durable charter/memory files under `.setsweep/` may sync normally. See
[`ARCHITECTURE.md`](./ARCHITECTURE.md).

## Notes for the maintainer

- **Canonical install is `~/.setsweep-venv` with one PATH shim** — see above.
- **Editable install (`-e`) is the supported mode.** It keeps `static/` resolving from the
  source tree. A non-editable wheel would need a package restructure — deferred.
- **Reinstall after every `py-modules` change** — see the reinstall rule and the comment
  next to `py-modules` in `pyproject.toml`.
