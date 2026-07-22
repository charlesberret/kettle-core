# Setsweep-core — Agent Orientation

Canonical path: `~/cloud/git-projects/setsweep-core` (moved from Seafile `Code/_archive/setsweep`).

## Architecture

Python backend (`server.py`, `runtime.py`, `lineage.py`, `kits.py`, `cli.py`, `curator.py`) plus a folder-watcher entry point (`setsweep_watch.py`) and a launcher shim (`setsweep_main.py`). No third-party runtime dependencies — the server and CLI viewport are stdlib-only. Single-file frontend at `static/index.html`. Three-pane layout: agent-curated queue · patron's editor · project-aware review agent.

**Viewport vs curator:** Desktop, VS Code, and MCP are *viewports* onto the desk. Agentic turns (interview, found, sweep, chat) run through the **curator provider** configured in `settings.json` (`curator.provider` / `curator.command` / `curator.models`) — default is the Claude Code CLI. `/api/ping` exposes the active curator so viewports can label it honestly.

**Sibling viewports** (separate repos; host-specific code stays out of this tree):

| Path | Role |
|------|------|
| `~/cloud/git-projects/setsweep-desktop` | Electron macOS shell — bundles this server as a sidecar |
| `~/cloud/git-projects/setsweep-plugin` | Host adapters; `packages/vscode` first (Cursor too); Obsidian/Sublime later |

Changes to the Python layer do not require touching desktop/plugin unless the HTTP API surface changes. Wire contract: [`API.md`](./API.md).

**Chat write tools (interim):** `/api/chat` grants Edit/Write under `--permission-mode acceptEdits`, fenced to the project root — same write tier as sweep for always-on implementation when the patron asks. Founding interview stays read-only until Finish/Found. A future reengineering of the chat/desk window may replace this with a fuller agent surface (permission UX, broader tools). → editor buttons remain useful for proposed fences.

Server listens on `http://127.0.0.1:4242/` (`DEFAULT_PORT = 4242` in `server.py`; moved from 8765 on 2026-06-13). A second launch defers if the current instance is healthy; pass `--replace` or use `Setsweep.app` to force a restart.

Five test files at root plus `test_curator.py`: `test_server.py`, `test_runtime.py`, `test_lineage.py`, `test_kits.py`, `test_watch.py`. Run with `pytest`.

The `.setsweep/` directory holds the curator's desk files (memos, handoffs, memory). It is gitignored and therefore invisible to dashboards — `_Status.md` and this file are the external face.

## Invariants / Run-critical

These files, if broken, take the app offline while the patron is in it. **Handoff only — never edit from within Setsweep itself.** Instead, draft a handoff memo to an external agent (a separate Claude Code session) carrying the full context needed to make the change, test it, and get Setsweep back online.

| File | Why it's run-critical |
|---|---|
| `server.py` | Entire backend: routes, file-fence (`safe_path`), atomic writes, circuit-breaker (`start_server_preferred`) |
| `static/index.html` | Entire single-file frontend — a JS error produces a blank window on reload with no app left to repair it. A tiny boot bootstrap (first inline `<script>`, before themes.js) paints a survival banner ("Setsweep hit a script error — [reload] [copy details]") on any parse/boot failure and `init()` names the failing phase, but this is a safety net, not a license to edit the file live. |
| `setsweep_main.py` | Launcher shim — the entry point the desktop shell / `Setsweep.app` invoke |
| `projects.json` | Live-read registry; sentinel and cron re-read it on every cycle |
| `settings.json` | Live-read settings; a shallow-merge clobber silently drops key groups. Prefer deep-merge for `curator` / `agents` via `curator.deep_merge_settings` |

**Never bind or signal port 4242 from agent tooling** — that is the live window's port.

Safe to review and edit directly: `README.md`, `.local/DESIGN.md`, `test_*.py` files, `.setsweep/` desk files, `kits/` (including product prompts under `kits/prompts/`), `pyproject.toml`, `_Status.md`, `ROADMAP.md`, `docs/` (including the agent briefs in `docs/briefs/`), this file.

Planning surface: `ROADMAP.md` is the master plan (phases with exit tests); `docs/briefs/` holds ready-to-run work packages — read the relevant brief before starting roadmap work, and update its `status:` frontmatter when you finish.

## Conventions

- Flat-layout package; install editable (`pip install -e .`) so `static/` and `projects.json` resolve from the repo root. A non-editable wheel would require restructuring under a package with `package-data` — deferred, see `INSTALL.md`.
- DESIGN §5 invariants hold: localhost-only, file-fence enforced on every route, append-only records never auto-mutated, patron's words beat the files, memory is distillation, every automated actor beats a healthbeacon.
- Dominant workflow is drive-by: prefer fast, targeted, self-contained changes over long sit-downs.
- Before touching `server.py` or `static/index.html` check git status first — branch `codex/shore-up-system` carries Charles's in-flight uncommitted work on both files. Coordinate rather than overwrite.
