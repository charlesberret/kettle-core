# Kettle architecture

How the product is shaped today. Longer private design notes may exist outside the
published tree; **this file is the public source of truth** for clone readers and new
contributors.

## Thesis

Kettle is a **review instrument**. Agents prepare and propagate; the human reviewer
(the *user*) reads and rules. Context is paid for once by a per-project *curator* and
delivered pre-packed (the *brief*). Rulings are applied outward mechanically by a
*sweep*. Nothing asks the user to re-derive what an agent already knows; nothing lets
an agent rule on what is the user’s to rule.

## Desk-is-files; the app is a viewport

All durable desk state lives under `<project-root>/.kettle/` as ordinary files — no
hidden database. Any frontend (browser, CLI, desktop shell, editor plugin) is a
**viewport** over the same localhost API and the same desk files.

| Concern | Location |
|--------|----------|
| Charter, memory, review program, archive, outbound egress | `.kettle/` (durable; safe to sync) |
| Queue, chatlog, snapshots, session logs, comments | `.kettle/runtime/` (**exclude from file sync**) |
| Project registry | `projects.json` (user-local or Application Support for the `.app`) |
| Preferences / curator provider | `settings.json` |

**Sync rule:** if the project tree is synced (Dropbox, iCloud, git-annex, etc.), exclude
`.kettle/runtime/` so the sync daemon does not race high-churn rewrites. Durable desk
files may sync normally.

Multiple viewports may open one desk. Concurrency is file-level atomic writes, not a
long-lived state daemon.

## Process model

One Python server per machine, binds **`127.0.0.1` only**, default port **4242**. An
identity beacon (`GET /api/ping`) lets a new launch recognize and retire a previous
healthy Kettle instance — never by trusting a stale pidfile alone. Foreign occupants of
the port fall back to an ephemeral port.

## Viewports

| Viewport | Where |
|----------|--------|
| Browser / server | this repo — `kettle` / `kettle --web` |
| CLI | this repo — `kettle projects \| queue \| open \| edit \| chat \| …` (built-in TUI editor) |
| macOS `.app` | sibling **kettle-desktop** (loads core web UI + theme packs) |
| VS Code / Cursor | sibling **kettle-vscode** |

Theme packs (marquee **kettle** + bundled + user): [`docs/THEMES.md`](./docs/THEMES.md).

Wire contract: [`API.md`](./API.md).

## Tool tiers

| Tier | Used for | Grant |
|------|----------|--------|
| interview (tool-less) | founding interview (until Finish) | no tools — core survey snapshot only (`survey.py`) |
| project-write | review chat, sweep, found/finish | Edit / Write under `acceptEdits`, fenced to the project root |
| never | anyone | network beyond localhost; auto-mutation of append-only records; paths outside the fence |

Provider quirks for *write* tiers are single-sourced in `runtime.PROVIDER_CAPABILITIES`.
Founding no longer depends on per-provider read-only shell modes.

## Founding state machine

1. **Register** a folder (`kettle add` or in-app add) — **founding sentence
   required** (“what is this, and what do you want from a second reader here?”).
   Seeds an empty desk + queue “awaiting founding.”
2. **Survey** — core maps the folder deterministically (`survey.py`: tree, git
   activity, mtimes). No curator CLI.
3. **Interview** — tool-less **conversation** over that snapshot (one mission
   question in prose; no confirmation card). User’s words beat the files.
4. **Propose** — **Draft Proposal ✓** writes `.kettle/DESK-PROPOSAL.md` into the
   editor. The user edits that file.
5. **Found Desk** — curator digests *user-edited* text and writes the desk
   (charter opens with **Your Words** quoting the founding sentence). A desk is
   **founded** only when `PROJECT.md` exists **and** the queue has a content entry.
6. **Sitting** — user works the queue: read, comment, approve/rework.
7. **Sweep** — closes the sitting: apply rulings, assess diffs, restock queue, stage egress.

## Lineage

Edits are attributed as **agent**, **user**, or **unattributed** — never guessed. Agents
do not relabel user claims. CLI: `kettle lineage` / `kettle bind`. HTTP:
`/api/lineage` and related resolve endpoints. See also the desk’s own ledger files.

## Invariants (non-negotiable)

1. **Localhost only.** File I/O is fenced (resolve-then-`is_relative_to`); registered
   roots extend the fence and registration is gated (under `$HOME`, validated).
2. **Append-only records are never auto-mutated.** Rulings ledgers are applied exactly as
   written; launch-type rulings are logged as directives, never executed by the sweep.
3. **The curator never invents:** briefs are honest; memory records only what is attested
   (by files or by the user’s own words); empty queues say so.
4. **The user’s answers beat the files** where they disagree — and the charter records
   the user’s words, not a paraphrase, where they were exact.
5. **Memory is distillation, not log:** bounded (~80 lines), revisable, evidence-backed;
   the session log holds the particulars.
6. **Every background actor writes a healthbeacon;** silent failure is a bug by
   definition.
7. **No artifact attributes a choice to the user without lineage citation.** Default
   attribution is prototype/agent unless a dated user action says otherwise.

## Security surface (summary)

- No API keys stored — ambient curator-CLI login only.
- File fence on every route that touches the filesystem.
- Per-boot `X-Kettle-Token` (discovery file mode 0600) and Host/Origin gates on
  the localhost HTTP surface. See [`docs/AUTH-TOKEN.md`](./docs/AUTH-TOKEN.md).
- Rendered markdown is allowlist-sanitized (DOMPurify) before HTML (reading view
  and agent chat).
- Admin “fleet” diagnostics are opt-in (`settings.admin.fleet_panels`).
- Remote and multi-user serving are out of scope.

## Layout of this package

Python package under `kettle/` (`server.py`, `cli.py`, `runtime.py`, …), stdlib-only
runtime for server and CLI, with `static/` and `kits/` shipped as package data. Install
**editable** (`pip install -e .`) for contributors, or from a wheel for a self-contained
UI. Canonical install path: `~/.kettle-venv` (see [`INSTALL.md`](./INSTALL.md)).
`kettle doctor` checks PATH and package-module importability.

**Sitting UI** is only `kettle/static/index.html` (plus themes/fonts). Structure:
[`docs/UI-STRUCTURE.md`](./docs/UI-STRUCTURE.md). Type hierarchy, buttons, and
meta-pane rules: [`docs/UI.md`](./docs/UI.md). Desktop does not fork that file.

## Further reading

| Doc | Role |
|-----|------|
| [`README.md`](./README.md) | Product intro, glossary, quickstart |
| [`docs/REVIEW.md`](./docs/REVIEW.md) | Briefing for a full-tree review of current form |
| [`INSTALL.md`](./INSTALL.md) | Install, PATH, reinstall rule |
| [`API.md`](./API.md) | HTTP contract for viewports |
| [`ROADMAP.md`](./ROADMAP.md) | Phased plan and release ladder |
| [`docs/REPOSITORIES.md`](./docs/REPOSITORIES.md) | Repo ownership, compatibility, cross-repo changes |
| [`docs/RELEASE.md`](./docs/RELEASE.md) | Measurement and gates |
| [`kits/README.md`](./kits/README.md) | Curator playbooks |
