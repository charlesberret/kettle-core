# Kettle-core — Agent Orientation

Core authority: [github.com/charlesberret/kettle-core](https://github.com/charlesberret/kettle-core).
Product home: [github.com/charlesberret/kettle](https://github.com/charlesberret/kettle).
Public architecture: [`ARCHITECTURE.md`](./ARCHITECTURE.md). Private design notes (if present)
live under `.local/` and are gitignored.

## Architecture

Python backend (`server.py`, `runtime.py`, `lineage.py`, `kits.py`, `cli.py`, `curator.py`,
`egress.py`, `sweepkit.py`) plus a folder-watcher entry point (`kettle_watch.py`) and a
launcher shim (`kettle_main.py`). No third-party *runtime* dependencies — the server and CLI
viewport are stdlib-only. Single-file frontend at `static/index.html` (plus vendored
`marked.min.js`, `purify.min.js`, `themes.js`, fonts). Three-pane layout: agent-curated queue ·
user's editor · project-aware review agent.

**Sitting UI conventions:** [`docs/UI.md`](./docs/UI.md) — type hierarchy (`--text-heading` /
`--text-label` / `--text-secondary` / `--text-primary`), buttons, urgency, meta pane. **Read
before editing `static/index.html`.** New panels must use those roles; do not ship body-white
copy next to gray chrome. Desktop loads the same file (no style fork).

**Viewport vs curator:** Desktop and VS Code are *viewports* onto the desk. A future
MCP bridge would be a narrow tool adapter, not a replacement for a sitting. Agentic
turns (interview, found, sweep, chat) run through the **curator provider** configured in
`settings.json` (`curator.provider` / `curator.command` / `curator.models`) — default is the
Claude Code CLI. `/api/ping` exposes the active curator so viewports can label it honestly.

**Sibling viewports** (separate repos; host-specific code stays out of this tree):

| Repo | Role |
|------|------|
| `kettle-desktop` | Electron macOS shell — bundles this server as a sidecar |
| `kettle-vscode` | VS Code and Cursor adapter (one VSIX) |

Changes to the Python layer do not require touching desktop or VS Code unless the HTTP API surface
changes. Wire contract: [`API.md`](./API.md).

**Chat write tools (interim):** `/api/chat` grants Edit/Write under `--permission-mode acceptEdits`,
fenced to the project root — same write tier as sweep for always-on implementation when the
user asks. Founding interview is tool-less (core survey) until Finish/Found.

Server listens on `http://127.0.0.1:4242/` (`DEFAULT_PORT = 4242` in `server.py`). A second launch
defers if the current instance is healthy; pass `--replace` or use `Kettle.app` to force a
restart.

Tests at repo root: `test_server.py`, `test_runtime.py`, `test_lineage.py`, `test_kits.py`,
`test_watch.py`, `test_cli.py`, `test_curator.py`, `test_egress.py`, `test_frontend.py`,
`test_kettle_main.py`, `test_sweepkit.py`. Run with `pytest`.

The `.kettle/` directory under each *project* holds that desk’s files. This repo’s own
`.kettle/` (if any) is gitignored.

## Invariants / Run-critical

These files, if broken, take the app offline while the user is in it. **Handoff only — never
edit from within Kettle itself.** Draft a handoff to an external agent with full context,
tests, and recovery steps.

| File | Why it's run-critical |
|---|---|
| `server.py` | Entire backend: routes, file-fence (`safe_path`), atomic writes, circuit-breaker |
| `static/index.html` | Entire single-file frontend — a JS error can blank the window |
| `kettle_main.py` | Launcher shim for desktop / console entry |
| `projects.json` | Live-read registry (user-local; gitignored in this tree) |
| `settings.json` | Live-read settings; deep-merge for `curator` / `agents` / `egress` / `admin` |

**Never bind or signal port 4242 from agent tooling** — that is the live window's port.

Safe to edit directly: `README.md`, `ARCHITECTURE.md`, `INSTALL.md`, `test_*.py`, kits, prompts,
`pyproject.toml`, `ROADMAP.md`, `docs/`, this file.

Planning: `ROADMAP.md` is current. `docs/briefs/` is historical design evidence
and must be checked against the live tree before reuse.

## Conventions

- Flat-layout package; install editable (`pip install -e .`) so `static/` resolves from the repo
  root. Canonical venv: `~/.kettle-venv` — see `INSTALL.md` and `kettle doctor`.
- Architecture invariants hold: localhost-only, file-fence on every route, append-only records
  never auto-mutated, user's words beat the files, memory is distillation, every automated
  actor beats a healthbeacon. Full list in [`ARCHITECTURE.md`](./ARCHITECTURE.md).
- Dominant workflow is drive-by: prefer fast, targeted, self-contained changes.
- Before touching `server.py` or `static/index.html`, check git status and coordinate with any
  in-flight branch work on those files.
