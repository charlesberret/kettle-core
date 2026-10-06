# Changelog

Kettle Core follows semantic versioning for its Python distribution. The API
and Desk schema have their own integer contract versions.

## Unreleased

### Changed

- **Sweep is Finish batch on screen.** The button, its tooltip, the confirmation, the
  3-second undo (now catalog key `sweepUndoLabel`), the Behavior settings and the chat
  status lines all say what happens instead of naming an invented act. `sweep` joins the
  house words; `/api/sweep`, `sweepLabel` and `sweep.log` are unchanged.
- **The kit editor moved into the Agents tab.** Curators was a second tab about the same
  agent; its kit editor now sits under the provider and model choices as Agent Kits. A
  saved `adminTab: "curators"` opens Agents.
- The ritual row's gap narrows so four controls fit one line in the default meta pane,
  and its screen-reader label says "Actions on this file".

- **The agent is called the agent.** `curator` is retired from everything a user or
  the model reads: the sitting, the copy catalog, and all 10,294 words of the prompt
  corpus. The verb `curate`, the adjective `curatorial` and the `curated` queue field
  survive, and every identifier (`curator.provider`, `/api/curator`, `curatorProvider`)
  is unchanged — those are contract, not copy.
- **`Found Desk` is retired as a control label.** The ritual control reads **Approve**
  in both states; while a proposal is open, pressing it founds the project desk and
  the sitting promotes the control visually (`body.proposing #approve`) instead of
  renaming it. "Found" survives as the verb.
- **A project is "the project desk" on screen**; `desk` alone stays the term in code,
  prompts, docs and file names.
- Sitting copy rewritten end to end from a full editorial pass: 32 of 47 catalog
  strings, plus every `short` variant.

- **UI copy is one catalog in JSON.** `static/ui-copy.json` replaces
  `static/ui-copy.js`, which is deleted — `/ui-copy.js` is now rendered from the
  JSON per request, so no generated file can drift from it. Python viewports read
  the same catalog through `kettle.uicopy` or `GET /api/ui-copy`, which is what
  the TUI needed and a JavaScript file could never give it. Keys carry an optional
  `short` for narrow surfaces and a required `note`.
- The **Add Project** button reads **Start Interview**, matching the catalog and
  `docs/UI.md`; the web markup had it lowercase while the VS Code mirror did not.
- Bare `kettle` launches the Textual sitting (`kettle-tui` on PATH). The HTTP host
  is `kettle-web` (alias: `kettle --web`). Desktop sidecars that pass `--port` /
  `--no-open` are unchanged. The PyInstaller `kettle` binary still serves the
  sitting when `kettle-tui` is not on PATH.
- Add-project copy says **Draft Proposal ✓**, not the retired “finish ✓”.
- Agent chat paints GFM while the reply is still streaming.
- New desk files and lineage records are created mode `0600`. Existing files keep their bits.

### Added

- **The file-first journey.** Everything the agent offers reaches the user as a file, with why
  it is there and what is wanted. The handbook opens with that rule and a plain-word table
  generated from the lexicon, so the agent writes the way the screen reads.
  - The setup questions now name files the user can open; a commit count with no file attached
    no longer counts as an observation.
  - The proposal is about the user's files and what they want — *What You Want From It* and
    *The First Files* — instead of a charter for how the agent works.
  - `PROJECT.md` carries **What You Want From This Project**. The agent may change it only by
    quoting the change in that round's notes.
  - Each Sweep opens with one line saying what it is about to do, and ends by writing
    `.kettle/rounds/<stamp>.md` — what it did, what it now thinks you want, what's next —
    queued first in the next batch.
  - Summaries tie each file's reason to the user's own words.
- **Not this** — a fourth control on every file except the proposal. One click sets the file
  aside; Bring back undoes it. `POST /api/set-aside`.

- **State messages.** `ui-copy.json` gains a `states` section keyed by the flow states
  `docs/SITTING-FLOWS.md` names, each in three registers (`line` / `short` / `full`).
  Thirteen hand-written variants of "edit the proposal, then found the desk" — seven in
  `index.html`, four in the TUI, two catalog keys — collapse to one message. The spec
  now says *render `states.proposing`* where it used to say "tell the user", and
  `SITTING-FLOWS.md` §7 makes that a MUST.

- **UI debug mode** (Diagnostics → Inspect Interface Copy, or `?uidebug=1`).
  Outlines catalogued copy, names the key, the binding and the owning file, and
  copies a pasteable reference. Alt+click retypes a string; the inspector also
  lists and retunes the CSS tokens governing an element. Edits are overrides in
  `sitting-overrides.json` beside `settings.json` — `static/` and `index.html` are
  never written. New routes: `GET`/`POST /api/ui-copy` and
  `GET /api/ui-copy/promote`.

- **Standalone binary.** `tools/build-binary.sh` + `packaging/kettle.spec` build a single
  `kettle` executable (~9 MB) with the sitting, kits and interpreter inside it: no Python on
  the target machine. The script builds in a throwaway venv (PyInstaller stays a build-time
  dependency; the package remains stdlib-only) and then proves the bundle — `doctor`, an
  ephemeral-port boot, `/api/ping` with the discovery token, and `GET /` returning the real
  sitting. A `standalone-binary` CI job runs it on Ubuntu and macOS. The same spec
  builds a directory bundle (`KETTLE_BUNDLE=onedir`) for hosts that launch the core as
  a sidecar, replacing kettle-desktop's own stale copy of the recipe.
- `kettle --version` / `-V` prints the version plus the API and desk-schema contract
  integers. The binary could not previously name itself.

- `kettle migrate`: dry-run-first migration of `.setsweep/` desks → `.kettle/` (and the
  legacy Setsweep user registry when clearly applicable). Default is dry-run; pass
  `--apply` to write. Refuses split desks (both directories present) so a project never
  keeps two writable desks. See `INSTALL.md` § Migrating from Setsweep.
- `kettle doctor` expands beyond PATH / package-module mapping: Python + package install
  mode, active curator CLI resolve (`curator.provider_readiness`), registry readability,
  desk integrity (`queue.json` parse + desk dirs), legacy `.setsweep/` migration hints
  (pointing at `kettle migrate`), runtime discovery (`~/.cache/kettle/server.json`), and
  a localhost `/api/ping` when discovery lists a non-conventional port (never binds or
  probes `4242`).
- CI `package-install` job: build wheel, audit bundled `static/` + `kits/` package data,
  clean-venv wheel install smoke, ephemeral-port server smoke, and pipx-style isolated
  install smoke on Python 3.11 and 3.14.
- `kettle.__version__` (via `importlib.metadata`) surfaced in `/api/ping` and
  `kettle --help`.

### Changed

- `kettle doctor` prints `hint` for a setsweep-only desk, with the migrate
  docs pointer, and the summary is no longer "all checks green". Exit stays 0.
  A split desk (both `.kettle/` and `.setsweep/`) is still `FAIL`.
- **Install is no longer a venv convention.** `INSTALL.md` leads with `uv tool install` /
  `pipx` for users, a standalone binary for machines without Python, and an editable
  checkout for contributors. `~/.kettle-venv` is conventional, not required; the rule that
  remains is one `kettle` on PATH.
- `kettle doctor`'s install section is five rows instead of seven: `python-version`,
  `package-version`, `kettle-on-path`, `kettle-path-extras`, and one `package-import` row
  that replaces `py-modules-list` / `install-mapping` / `py-modules-importable`. It asks the
  only question that matters — does the package import, and is its bundled `static/` +
  `kits/` data there — and reports a standalone binary as such instead of describing an
  interpreter the user never installed.

- Founding interview no longer passes a bare `--allowedTools` to Claude Code
  CLI (current CLIs require a value and exit 1). Claude's interview uses
  `--permission-mode plan --tools ""` (see Security); Grok uses plan mode.
- Founding interview is a conversation (one mission question), not a
  confirmation-card form. Agent chat renders GFM. See `docs/REVIEW.md`.

- Restructured the flat modules into the `kettle/` package; `static/`, `kits/`, and
  `projects.example.json` ship as package data so a wheel can serve the web UI.
  `APPDIR` resolves through `importlib.resources.files()` (PyInstaller `_MEIPASS` kept).
  Build floor pinned to `setuptools>=77`.
- Renamed the product and canonical commands from Setsweep to Kettle.
- New projects use `.kettle/` and the Kettle user registry.
- Public documentation and repository routing now describe the Kettle family.
- CLI `open` / `edit` use a built-in syntax-colored TUI editor by default
  (theme packs under `static/themes/`; marquee default `kettle`). Pass
  `--external` for `$EDITOR`. Search with `^F` / `^G` / `^D`; large files use
  plain mode.
- Web/desktop load theme packs from `GET /api/themes` and can install custom
  packs via Appearance or `POST /api/themes/install`.
- Sitting source view uses shared syntax role classes aligned with the CLI.

- Sweep crash-safety: every sweep that spawns a curator writes
  `runtime/sweep-health.json` (`running` → `done`/`failed`). An empty, quiet queue left
  by a sweep that closed and then died now restocks instead of reporting "Nothing to
  sweep" forever. A second sweep on the same desk is refused while one is streaming.
- Batch archives are one file per pass (`archive/<YYYY-MM-DD-HHMMSS>-batch.json`,
  suffixed on collision) and are never merged into or overwritten; entries are selected
  under the queue lock so a concurrent approve or intake entry is not dropped.
- `comments.log` stays append-only but comments are retired once consumed: a completed
  sweep or an archive appends `[kettle:closed through N]` markers, and clearing a note
  retracts its history. A file returning to the queue no longer replays settled direction.
- Founding has one prompt builder (`build_found_prompt`) for `POST /api/found`,
  `POST /api/bootstrap` and `kettle found`: the founding sentence, queue schema, kit context
  and scope note reach every entry point. `kettle found` refuses an already-founded desk,
  resumes only its own provider's session, and exits 1 when the desk did not found.
- Found Desk no longer strands a desk: the sitting announces "desk founded" only when
  `GET /api/interview` reports `founded: true` (new field, with `has_charter`); otherwise the
  proposal stays open, and a missing proposal entry is re-filed. A propose turn cannot found
  the desk. A chat session opened before the interview is not resumed as the interview.
- Founding prompts refer to the founding-sentence block as *above* (it leads the prompt).
- Refound keeps append-only records (`working-record.jsonl`, lineage baseline, `sessions/`,
  `archive/`, `outbound/`, `runtime/comments.log`, `runtime/approvals.log`) and clears only
  the charter, memory, proposal, queue, session and snapshots; it is refused (409 `busy`)
  while a curator turn is streaming on that desk.
- The founding survey honors the project's `max_depth` for git's most-changed paths and the
  filesystem recency walk, skips that walk when git history answers recency, and reports
  its recency counts cumulatively ("N in the last 7 days" now includes the last 24h).
- Curator orientation caps fit the files' line budgets (PROJECT/MEMORY 6000 characters,
  FAMILIARITY 9000) and mark any truncation, so the newest rulings are not silently cut.
- A desk whose `queue.json` does not parse is reported (409 `queue_corrupt`) and never
  overwritten; a project folder that was moved or deleted is reported (404) instead of being
  recreated by `mkdir -p`; one broken desk no longer fails the sitting's boot.
- `kettle chat` / `kettle found` / `kettle refresh-briefs` stop a curator that goes silent for
  `curator.idle_timeout_s` (default 300 s), as the server already did.
- The retired confirmation-card parser, renderer, CSS and tests are removed from the sitting
  (P4: founding is a conversation); the re-found offer keeps its own `refound-offer` styling.
  Founding copy in the sitting says "Draft Proposal ✓" instead of "finish ✓".
- Smaller fixes from the review: re-approving an entry keeps its first date and logs once;
  a project name with no ASCII letters gets a stable hashed id instead of `x`; two sweep
  session logs in the same second no longer overwrite each other; precomputed sweep diffs
  find snapshots for ids that need slugging; an intake folder outside the project that
  overlaps credential folders is ignored; `KETTLE_ALLOWED_ROOTS` entries pass the same
  gate as project roots; agent-chat task lists lose their stray bullets.
- `lineage_git` trusts only a `lineage.git` Kettle created, recorded outside every project
  in `~/.cache/kettle/lineage-trust.json`; any other one (including one from an older Kettle)
  is set aside untouched as `lineage.git.untrusted-<stamp>` and a fresh history starts. Its
  config is rewritten from a fixed template before each run, repo attributes are removed,
  and git runs with hooks, fsmonitor, pager, external diff and attributes files disabled.
- Desk writes never follow a planted symlink: every write or append under a registered
  project (queue, session, snapshots, archives, session logs, comments/approvals logs,
  working record, lineage baseline, EDITING.md, the CLAUDE.md directive, inbox staging)
  refuses a symlinked final component or a parent that leads outside the project
  (403 `unsafe_path`). Refound refuses a desk that leads outside its project. The root gate
  is case-insensitive on macOS and refuses `~/Library` apart from iCloud/CloudStorage.
- `kettle migrate --apply` also rewrites `<root>/.setsweep/` path prefixes in the desk's
  `runtime/queue.json` entries and the registry `ledger` field (listed in the dry run).
- Prompts and skills no longer hard-code `.kettle/outbound/` (a curator following it on a
  legacy `.setsweep` desk split the desk); the founding skill describes the P4
  conversation instead of the retired confirmation card; the interview role names the
  "Draft Proposal ✓" button.
- Docs match the tree: API.md routes and tool tiers, broken links, INSTALL/CLI command
  lists, the AUTH-TOKEN conformance table, and `kettle-design-tokens.md` against
  `kettle-palette.json`.
- A missing or non-executable curator CLI is reported by name with a fix
  (`curator_unavailable`, 500, before any stream) instead of a traceback from `kettle chat` /
  `kettle found` or a made-up `~/.local/bin/claude` path; the CLI is resolved per turn, so
  installing it after launch works without a restart.
- The sitting surfaces refused API calls: a stale token after a core restart says to reload
  the window, instead of chat showing an empty turn and sweep printing "finished".
- `kettle-watch` exits 1 and keeps `status: error` in `watch-health.json` when any project
  failed (the final beacon used to overwrite errors with `ok`). The admin report exposes
  that beacon as `watch_health`.

### Compatibility

- Existing `.setsweep/` Desks are used in place when no `.kettle/` Desk exists.
- Existing Setsweep user registries remain discoverable without creating split
  state.
- `setsweep` and `setsweep-watch` remain console-script aliases that call the
  same `kettle_main` / `kettle_watch` entrypoints (no separate `setsweep_*`
  modules remain in the tree).
- Kettle adapters may attach to a legacy core identity during the migration
  window.
- The API and Desk-schema contract integers remain unchanged at `0`.

### Security

- Registered-root file fencing, loopback-only serving, deterministic founding
  survey, and staged egress remain release invariants.
- Localhost HTTP hardening: per-boot `X-Kettle-Token` (discovery file mode 0600),
  Host/Origin rejection, and normalized `{error, code}` envelopes (`str(e)` only).
- The served page carries the per-boot token only when the connecting socket belongs to
  the server's own Unix user (`lsof` on macOS, `/proc/net/tcp` on Linux). Any process on
  loopback — including another user's — could previously read the token from `GET /`.
  `KETTLE_SKIP_PEER_CHECK=1` disables the check where the owner cannot be determined.
- Rendered markdown (reading view, agent chat) is sanitized as a string before it
  reaches the DOM. Previously raw `marked` output was assigned to `innerHTML` and
  cleaned afterwards, which let `<img onerror>` in a project file or agent reply run
  script holding the page token. `id` attributes are no longer allowed (DOM
  clobbering of the sitting's own elements).
- The sitting is served with a Content-Security-Policy (script-src `'self'` plus
  per-response sha256 pins of the shipped inline blocks; `frame-ancestors 'none'`,
  `object-src 'none'`), `X-Frame-Options: DENY` and `nosniff`.
- A registered folder's own agent config no longer runs. Headless `claude -p` skips
  workspace trust, so a folder's `.claude/settings*.json` hooks and `.mcp.json` servers
  executed on the first curator turn, including the founding interview. Every Claude
  tier now passes `--setting-sources user --strict-mcp-config`; the interview also
  passes `--tools ""` (plan mode alone left 34 built-in tools and all user MCP
  connectors); write tiers name their built-ins with `--tools` (no WebFetch, WebSearch
  or Task) and deny the Write/Edit tools on `.gemini/**` and `.codex/**`. The folder
  watcher's curate turn gets the same isolation. Curator children never inherit
  `GEMINI_CLI_TRUST_WORKSPACE`. Custom `cli` providers are unchanged. The project's
  `CLAUDE.md` now reaches curators as prompt text in the orientation block.
- Shell allowlists no longer include commands that can run other programs (`rg`, `fd`,
  `find`, `awk`, `sed`, `sort`): `rg --pre ./script` executed under the chat tier. Use
  the built-in Grep/Glob/Edit tools. Shell-bearing tiers remain trusted, not fenced —
  Claude's `acceptEdits` also auto-approves ordinary filesystem commands.
- Writes no longer follow a symlink planted at a predictable temp name: `atomic_write`
  creates its temp file with O_EXCL under a random name (used by save, queue, snapshots
  and the watcher). A desk directory that is a symlink leading outside its project is
  refused. A project root may not be the whole home folder, overlap credential or agent
  config folders (`~/.ssh`, `~/.claude`, `~/.config`, …), or contain Kettle's settings.
- The sitting refuses remote images (`img-src 'self' data:`), so a registered
  document cannot report when it is opened. CSP hashes are computed on
  LF-normalized HTML, and `.gitattributes` pins `kettle/static/*.html` to LF.

## 0.2.0

This was the final pre-Kettle package version inherited from the Setsweep
development line. Git history preserves the detailed implementation record.
