# Installing Setsweep

Setsweep needs **Python 3.11+** and a curator CLI (default: **`claude`**, logged in). The
server and the CLI viewport are pure stdlib.

## Canonical install

**One install, one name on PATH.**

| Piece | Location |
|---|---|
| Venv (canonical) | `~/.setsweep-venv` |
| Editable source | `~/cloud/git-projects/setsweep-core` (also reachable via the `~/Repos` symlink) |
| Console script | `~/.setsweep-venv/bin/setsweep` |
| PATH shim (exactly one) | e.g. `~/.local/bin/setsweep` → `~/.setsweep-venv/bin/setsweep` |

`setsweep doctor` reports which `setsweep` wins on `PATH`, whether it resolves to the
canonical venv, and whether every `py-modules` entry is importable. It never repairs and
never deletes PATH entries.

### Quick start — CLI + browser

```sh
cd ~/cloud/git-projects/setsweep-core                     # canonical core repo
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
~/.setsweep-venv/bin/pip install -e ~/cloud/git-projects/setsweep-core
```

`setsweep doctor` checks that every name in `py-modules` is importable and present in the
installed distribution's top-level list.

### PATH retirement checklist (patron-run only)

Agents **propose** these; they do **not** remove anything from your PATH. On a machine that
has accumulated older installs, `which -a setsweep` may show several winners. Retire
strays so the single shim above is first:

```sh
# 1. Dead post-migration shell shim (if present)
rm -i ~/Seafile/Code/bin/setsweep          # pre-migration path
rm -i ~/cloud/sync/code/bin/setsweep       # fleet Code/bin copy, if not the intentional shim

# 2. Homebrew console script (shadows the venv when it sorts first on PATH)
brew uninstall setsweep 2>/dev/null || true
# or, if it was a plain pip --user / brew python install:
rm -i /opt/homebrew/bin/setsweep

# 3. Keep only one ~/.local/bin entry — must be a symlink to the venv, not a second script
ls -la ~/.local/bin/setsweep
# expected: … -> …/.setsweep-venv/bin/setsweep

hash -r
which -a setsweep
setsweep doctor
```

## The native window (macOS)

The Electron shell at `~/cloud/git-projects/setsweep-desktop/` wraps the server in a proper `.app`
(Dock icon, external-link interception, native folder picker). It bundles the Python
server via PyInstaller so the `.app` does not require a separate Python install.

See the setsweep-desktop README for dev/build commands. The built `.app` is at
`~/cloud/git-projects/setsweep-desktop/out/Setsweep-darwin-arm64/Setsweep.app`.

## Viewports

This repo ships the browser/server and CLI viewports. The macOS `.app` is
`~/cloud/git-projects/setsweep-desktop/`; editor plugins live in `~/cloud/git-projects/setsweep-plugin/`
(VS Code/Cursor first; Obsidian and Sublime planned).

```
setsweep                          browser / server mode   (default; stdlib only)
setsweep --web [--port N]         same as bare launch
setsweep projects                 list registered desks   ┐
setsweep queue   <project>        show a desk's queue      │  CLI viewport
setsweep open    <project> <id>   open the file in $EDITOR │  (stdlib only)
setsweep chat    <project> [id]   talk to the curator      │
setsweep doctor                   install health           ┘
```

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
bundled Electron `.app` always uses Application Support (sets `DESK_PROJECTS`). On first
launch the shell copies `projects.json` from your setsweep source tree if the userData
file does not exist yet (override the source with `SETSWEEP_PROJECTS_SRC`).

## Notes for the maintainer

- **Canonical install is `~/.setsweep-venv` with one PATH shim** — see above. Do not leave
  multiple `setsweep` console scripts on PATH; `doctor` flags extras.
- **Editable install (`-e`) is the supported mode.** It keeps `static/` and the registry
  resolving from the source tree (`APPDIR = the repo`). A standalone wheel would need the
  flat modules restructured under a `setsweep/` package with `package-data` for `static/`
  — deferred (the flat layout is run-critical and well-tested as-is).
- **Reinstall after every `py-modules` change** — the finder MAPPING is fixed at install
  time; see the reinstall rule above and the comment next to `py-modules` in
  `pyproject.toml`.
- **Isolated venv required for the flat layout:** top-level module names (`server`, `cli`,
  `runtime`) are namespaced by the venv so they cannot collide with anything else on
  import. The supported isolation is `~/.setsweep-venv` (or `pipx` if you accept that the
  doctor will report a non-canonical path until the shim points there).
