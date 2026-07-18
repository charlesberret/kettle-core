---
id: 02
title: Reconcile the two plugin trees
repo: setsweep-plugin
touches: [packages/vscode/**, git worktrees]
risk: normal
depends-on: []
status: open
---

## Context

Two divergent implementations of the VS Code extension coexist. The committed branch
`feat/vscode-explorer-sitting` (worktree, ~8,223 lines, version 0.5.113) has sidecar
auto-start, an Explorer TreeView (`queueView.ts`), a settings panel, a setup wizard, and
a `src/test/` directory. Main's working tree holds a leaner ~3,293-line rewrite (version
0.2.0, edited 2026-07-17) with the Desk webview panel, `debug.ts`, chat participant and
LM tools — and almost all of it is **untracked** (`deskPanel.ts`, `confirmCard.ts`,
`debug.ts`, `paths.ts`, `state.ts`, `chat/` are `??` in git status). Installed VSIXes in
the wild are 0.5.113-lineage, so packaging from main as-is would silently *downgrade*
version numbers. No document says which tree is canonical.

## Task

1. Commit main's rewrite first — it is the current product and it is one `git clean`
   from oblivion. Commit message states it is the canonical line going forward.
2. Cherry-pick from the branch the three things the rewrite lacks and the plugin spec
   promises: `sidecar.ts` (auto-start core when no server found), `queueView.ts` (the
   Explorer TreeView), and `src/test/` (confirmCard, project, activation tests — adapt paths
   to the rewrite's module layout).
3. Bump the version **above** the branch lineage (0.6.0) so no installed extension ever
   sees a downgrade. Derive `DESK_UI_BUILD` and `debug.ts BUILD_ID` from one source
   (package.json version at compile time) while you are in there.
4. Retire the branch worktree: merge or archive-tag it (`archive/explorer-sitting`),
   remove the worktree, record the decision in the repo README or `_Status.md`.

## Constraints

- Nothing from the branch overwrites a rewrite file wholesale — port, don't paste; the
  two `api.ts` variants (393 vs 325 lines) must be diffed and reconciled deliberately.
- The extension must keep working attach-only (sidecar auto-start is additive and off by
  default until `setsweep.autoStartServer` — a new setting — enables it).
- Respect the settings work landed 2026-07-17 (`serverUrl`/`project`/`confirmSweep` with
  fallback reads of the pre-0.3 keys).

## Done when

- One implementation, on main, fully tracked; `npm run compile` clean; tests pass via
  `npm test` (wire `@vscode/test-electron` if the ported tests need it).
- `vsce package` produces a VSIX whose version exceeds 0.5.113.
- The worktree is gone; the branch is tagged or merged; a line in the repo README states
  main is canonical.

## Verify

Install the packaged VSIX into VS Code, attach to a running core, open the Desk panel,
run a founding card round-trip and one approve; confirm the TreeView lists the queue.

## Afterwards

Set `status: done`; update plugin `_Status.md`; note in core's `docs/briefs/16` that its
dependency is satisfied.
