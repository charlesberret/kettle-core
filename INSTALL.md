# Installing Setsweep

Setsweep needs **Python 3.11+** and the **`claude` CLI** (logged in). The server and the
CLI viewport are pure stdlib.

## Quick start — CLI + browser

```sh
git clone <repo> setsweep && cd setsweep      # or use the synced tree
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

The Electron shell at `~/Repos/setsweep-desktop/` wraps the server in a proper `.app`
(Dock icon, external-link interception, native folder picker). It bundles the Python
server via PyInstaller so the `.app` does not require a separate Python install.

See the setsweep-desktop README for dev/build commands. The built `.app` is at
`~/Repos/setsweep-desktop/out/Setsweep-darwin-arm64/Setsweep.app`.

## One command, two viewports

```
setsweep                          browser / server mode   (default; stdlib only)
setsweep --web [--port N]         same as bare launch
setsweep projects                 list registered desks   ┐
setsweep queue   <project>        show a desk's queue      │  CLI viewport
setsweep open    <project> <id>   open the file in $EDITOR │  (stdlib only)
setsweep chat    <project> [id]   talk to the curator     ┘
```

## Auth — Setsweep stores no key

It uses the `claude` CLI's own login. If `setsweep chat` can't reach the model, run
`claude` once to log in (or set `ANTHROPIC_API_KEY` in your environment). No API key is
ever entered into Setsweep.

## Registering a desk

The project registry is `projects.json` (override its location with `DESK_PROJECTS`; see
`projects.example.json` for the format). Each project points at a directory; its desk state lives
in `<root>/.setsweep/`. Add a project with `setsweep add <dir>`, by editing `projects.json` by
hand, or via the app's admin panel. The bundled Electron `.app` stores its registry at
`~/Library/Application Support/Setsweep/projects.json`.

## Notes for the maintainer

- **Editable install (`-e`) is the supported mode.** It keeps `static/` and the registry
  resolving from the source tree (`APPDIR = the repo`). A standalone wheel would need the
  flat modules restructured under a `setsweep/` package with `package-data` for `static/`
  — deferred (the flat layout is run-critical and well-tested as-is).
- **Isolated venv recommended:** the flat top-level module names (`server`, `cli`, `runtime`)
  are namespaced by the venv, so they can't collide with anything else on import. Install
  into a dedicated venv (or with `pipx`) for global isolation.
