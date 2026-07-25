# Agent briefs — ready-to-run work packages

A brief is a self-contained work order for an autonomous agent session (or a focused
human sitting): enough context to start cold, a precise task, the constraints that keep
the work safe, and a verifiable definition of done. Briefs exist so drive-by sessions can
push the [roadmap](../../ROADMAP.md) forward without re-deriving the state of the world.

## How to run one

Paste the brief body into a fresh agent session started in the named repo, or point the
session at the file. The agent reads `CLAUDE.md` first (it always should), then the brief.
One brief per session; finish or hand off — never leave a brief half-applied and silent.

## Format

Frontmatter: `id`, `title`, `repo`, `touches` (files), `risk` (`normal` | `run-critical`
— the latter means the file list includes something whose breakage takes the live app
down; re-read the Invariants section of `CLAUDE.md` before editing), `depends-on` (brief
ids that must land first), `status` (`open` | `in-progress` | `done`).

Body: **Context** (why; what the surveys found), **Task** (what to do), **Constraints**
(what must not happen), **Done when** (checkable), **Verify** (the commands/actions that
prove it), **Afterwards** (what to update: `_Status.md`, `API.md`, this index, the brief's
own `status`).

## The rules that bind every brief

- Never bind, signal, or curl port 4242 — that is the live window's port. Tests boot on
  ephemeral ports (`start_server(0)`), as `test_server.py` already does.
- Run-critical files (`server.py`, `static/index.html`, `setsweep_main.py`,
  `projects.json`, `settings.json`) get edited only by an external session that runs the
  tests before and after — never from inside Setsweep itself.
- DESIGN §5 invariants are non-negotiable: localhost-only, file-fence on every route,
  append-only records never auto-mutated, user's words beat files, memory is
  distillation, every automated actor beats a healthbeacon.
- A brief that discovers its premise is stale updates the brief (and this index), then
  proceeds or stops — it never forces a stale plan onto fresh code.

## Index

| # | Brief | Repo | Phase | Depends on |
|---|-------|------|-------|-----------|
| 01 | [Commit the working tree](01-commit-the-working-tree.md) | core | 0 | — |
| 02 | [Reconcile the two plugin trees](02-reconcile-plugin-trees.md) | plugin | 0 | — |
| 03 | [Single-source the tool tiers](03-single-source-tool-tiers.md) | core | 1 | 01 |
| 04 | [Externalize the prompts](04-externalize-prompts.md) | core | 1 | 01 |
| 05 | [Harden the HTTP surface](05-api-hardening.md) | core | 2 | 01 |
| 06 | [Provider capability table](06-provider-capability-table.md) | core | 2 | 03 |
| 07 | [Curator watchdog](07-curator-watchdog.md) | core | 2 | 01 |
| 08 | [Frontend error bootstrap](08-frontend-error-bootstrap.md) | core | 2 | 01 |
| 09 | [Allowlist sanitizer + keyboard access](09-sanitize-and-a11y.md) | core | 2 | 08 |
| 10 | [De-personalize the shipped surfaces](10-de-personalize.md) | core | 2 | 01 |
| 11 | [Package restructure + version](11-package-restructure.md) | core | 3 | 01, 04 |
| 12 | [Unify the folder-watchers](12-unify-watchers.md) | core | 1 | 03 |
| 13 | [API contract v1](13-api-contract-v1.md) | core | 3 | 05, 07, 11 |
| 14 | [Test depth](14-test-depth.md) | core | 2–3 | 01 |
| 15 | [Desktop distribution](15-desktop-distribution.md) | desktop | 3 | 01, 11 |
| 16 | [Extract the shared core-client](16-extract-core-client.md) | plugin | 3 | 02 |
| 17 | [Docs for strangers](17-docs-for-strangers.md) | core | 4 | 10, 11 |
| 18 | [Metrics beacons + setsweep doctor](18-metrics-and-doctor.md) | core | 5 | 11 |
| 19 | [Enforce the agent fence](19-enforce-the-fence.md) | core | 6 | 03, 06 |
| 20 | [One setsweep — install determinism](20-install-determinism.md) | core | 3 | — |
| 21 | [First-run design pass (web)](21-first-run-design.md) | core | 4 | 08 |
| 22 | [Viewport founding parity](22-viewport-founding-parity.md) | core | 4 | 08, 21 |
| 23 | [Viewport ritual regression bar](23-viewport-ritual-regression-bar.md) | core + plugin | 4 | 22 |

Status board: a brief's `status` frontmatter is the truth; this table stays status-free
so it never lies. `grep -l "status: open" docs/briefs/*.md` is the live to-do list.

**Parity rule:** founding and sitting chrome changes update
[`docs/PLATFORMS.md`](../PLATFORMS.md) ritual matrix the same day. Type/color chrome:
[`docs/UI.md`](../UI.md).
