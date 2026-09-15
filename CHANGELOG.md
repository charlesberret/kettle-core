# Changelog

Kettle Core follows semantic versioning for its Python distribution. The API
and Desk schema have their own integer contract versions.

## Unreleased

### Added

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
- The sitting refuses remote images (`img-src 'self' data:`), so a registered
  document cannot report when it is opened. CSP hashes are computed on
  LF-normalized HTML, and `.gitattributes` pins `kettle/static/*.html` to LF.

## 0.2.0

This was the final pre-Kettle package version inherited from the Setsweep
development line. Git history preserves the detailed implementation record.
