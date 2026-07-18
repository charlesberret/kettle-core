---
id: 16
title: Extract the shared core-client
repo: setsweep-plugin
touches: [packages/core-client (new), packages/vscode/src/**, esbuild config (new)]
risk: normal
depends-on: [02]
status: open
---

## Context

About 800 lines of the VS Code extension are already host-agnostic with zero `vscode`
imports (survey-verified): `api.ts` (393 — typed client for every core route the plugin
uses), `discover.ts` (80 — configured URL → `~/.cache/setsweep/server.json` → :4242,
each ping-validated), `confirmCard.ts` (173 — the founding-card GFM parser/serializer),
`state.ts` (113), `paths.ts` (35), plus a small `renderMarkdown`. This is the seed of
`packages/core-client` — the package an Obsidian adapter (Electron/TS) would consume
directly, and the forcing function to reconcile the two `api.ts` variants the two-tree
era produced. Meanwhile the desk webview is ~680 lines of untyped inline JS in a
template string (outside tsc entirely), the webview CSP allows `unsafe-inline` with no
nonce, and `DESK_UI_BUILD` must manually match `debug.ts`'s `BUILD_ID`.

## Task

1. Create `packages/core-client`: move the five modules + renderMarkdown; no `vscode`
   import may ever enter it (enforce with an eslint rule or a grep test in CI). Public
   API: client, discovery, confirm-card codec, the NDJSON stream reducer as a pure
   state machine.
2. `packages/vscode` consumes it via the workspace; the extension shrinks to host
   glue + webview.
3. Move the webview to a real `.ts` file bundled by esbuild into the panel HTML; add a
   CSP nonce and drop `unsafe-inline`.
4. Unit tests in core-client (plain vitest or node:test — no VS Code harness needed):
   confirmCard round-trip (including the single-choice `(choose one)` tag), stream
   reducer event sequences (text/tool/usage/done, error-without-done pre-brief-07
   servers), discovery fallback order.
5. Derive `DESK_UI_BUILD` and `BUILD_ID` from package.json version at build time —
   delete the manual must-match invariant.
6. Wire chatlog rehydration (api.chatlog/saveChatlog exist unused) so a window reload
   restores the sitting's conversation.

## Constraints

- Behavior-neutral extraction first, improvements second — two commit series.
- The core-client's README states its contract: it tracks `setsweep-core/API.md` tier
  A/B and declares which core version range it speaks (consume brief 11's ping
  version).

## Done when

- `npm test` runs core-client units without launching VS Code; the extension compiles
  against the package; the webview is tsc-checked and nonce'd.
- A scratch Node script (no VS Code) can list a queue and parse a confirm card using
  only core-client — the Obsidian-readiness proof.

## Verify

Package the VSIX, install, run a sitting end-to-end against a live core; reload the
window mid-sitting and see the chat restored.

## Afterwards

`status: done`; docs/PLATFORMS.md's adapter section notes core-client is real; an
Obsidian spike brief can now be written against it.
