# Setsweep-core — Agent Orientation

Canonical product repo: [github.com/charlesberret/setsweep](https://github.com/charlesberret/setsweep).
Public architecture: [`ARCHITECTURE.md`](./ARCHITECTURE.md). Private design notes (if present)
live under `.local/` and are gitignored.

## Architecture

Python backend (`server.py`, `runtime.py`, `lineage.py`, `kits.py`, `cli.py`, `curator.py`,
`egress.py`, `sweepkit.py`) plus a folder-watcher entry point (`setsweep_watch.py`) and a
launcher shim (`setsweep_main.py`). No third-party *runtime* dependencies — the server and CLI
viewport are stdlib-only. Single-file frontend at `static/index.html` (plus vendored
`marked.min.js`, `purify.min.js`, `themes.js`, fonts). Three-pane layout: agent-curated queue ·
patron's editor · project-aware review agent.

**Viewport vs curator:** Desktop, VS Code, and MCP are *viewports* onto the desk. Agentic turns
(interview, found, sweep, chat) run through the **curator provider** configured in
`settings.json` (`curator.provider` / `curator.command` / `curator.models`) — default is the
Claude Code CLI. `/api/ping` exposes the active curator so viewports can label it honestly.

**Sibling viewports** (separate repos; host-specific code stays out of this tree):

| Repo | Role |
|------|------|
| `setsweep-desktop` | Electron macOS shell — bundles this server as a sidecar |
| `setsweep-plugin` | Host adapters; `packages/vscode` first (Cursor too); Obsidian/Sublime later |

Changes to the Python layer do not require touching desktop/plugin unless the HTTP API surface
changes. Wire contract: [`API.md`](./API.md).

**Chat write tools (interim):** `/api/chat` grants Edit/Write under `--permission-mode acceptEdits`,
fenced to the project root — same write tier as sweep for always-on implementation when the
patron asks. Founding interview stays read-only until Finish/Found.

Server listens on `http://127.0.0.1:4242/` (`DEFAULT_PORT = 4242` in `server.py`). A second launch
defers if the current instance is healthy; pass `--replace` or use `Setsweep.app` to force a
restart.

Tests at repo root: `test_server.py`, `test_runtime.py`, `test_lineage.py`, `test_kits.py`,
`test_watch.py`, `test_cli.py`, `test_curator.py`, `test_egress.py`, `test_frontend.py`,
`test_setsweep_main.py`, `test_sweepkit.py`. Run with `pytest`.

The `.setsweep/` directory under each *project* holds that desk’s files. This repo’s own
`.setsweep/` (if any) is gitignored.

## Invariants / Run-critical

These files, if broken, take the app offline while the patron is in it. **Handoff only — never
edit from within Setsweep itself.** Draft a handoff to an external agent with full context,
tests, and recovery steps.

| File | Why it's run-critical |
|---|---|
| `server.py` | Entire backend: routes, file-fence (`safe_path`), atomic writes, circuit-breaker |
| `static/index.html` | Entire single-file frontend — a JS error can blank the window |
| `setsweep_main.py` | Launcher shim for desktop / console entry |
| `projects.json` | Live-read registry (user-local; gitignored in this tree) |
| `settings.json` | Live-read settings; deep-merge for `curator` / `agents` / `egress` / `admin` |

**Never bind or signal port 4242 from agent tooling** — that is the live window's port.

Safe to edit directly: `README.md`, `ARCHITECTURE.md`, `INSTALL.md`, `test_*.py`, kits, prompts,
`pyproject.toml`, `_Status.md`, `ROADMAP.md`, `docs/`, this file.

Planning: `ROADMAP.md` + `docs/briefs/` — update a brief’s `status:` when you finish it.

## Conventions

- Flat-layout package; install editable (`pip install -e .`) so `static/` resolves from the repo
  root. Canonical venv: `~/.setsweep-venv` — see `INSTALL.md` and `setsweep doctor`.
- Architecture invariants hold: localhost-only, file-fence on every route, append-only records
  never auto-mutated, patron's words beat the files, memory is distillation, every automated
  actor beats a healthbeacon. Full list in [`ARCHITECTURE.md`](./ARCHITECTURE.md).
- Dominant workflow is drive-by: prefer fast, targeted, self-contained changes.
- Before touching `server.py` or `static/index.html`, check git status and coordinate with any
  in-flight branch work on those files.
