# Installing Setsweep

Setsweep needs **Python 3.11+** and the **`claude` CLI** (logged in). The server and the
CLI viewport are pure stdlib.

## Quick start — CLI + browser

```sh
cd ~/cloud/git-projects/setsweep-core                     # canonical core repo
python3 -m venv ~/.setsweep-venv
~/.setsweep-venv/bin/pip install -e .
~/.setsweep-venv/bin/setsweep projects        # the CLI viewport
~/.setsweep-venv/bin/setsweep --web           # browser mode
```

Put the command on your PATH:

```sh
ln -s ~/.setsweep-venv/bin/setsweep ~/.local/bin/setsweep   # any dir on your PATH
setsweep                                                       # then just `setsweep`
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
setsweep chat    <project> [id]   talk to the curator     ┘
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

- **Editable install (`-e`) is the supported mode.** It keeps `static/` and the registry
  resolving from the source tree (`APPDIR = the repo`). A standalone wheel would need the
  flat modules restructured under a `setsweep/` package with `package-data` for `static/`
  — deferred (the flat layout is run-critical and well-tested as-is).
- **Isolated venv recommended:** the flat top-level module names (`server`, `cli`, `runtime`)
  are namespaced by the venv, so they can't collide with anything else on import. Install
  into a dedicated venv (or with `pipx`) for global isolation.
