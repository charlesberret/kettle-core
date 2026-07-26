---
id: 08
title: Frontend error bootstrap
repo: kettle-core
touches: [static/index.html, static/ (new small js file), test_server.py]
risk: run-critical
depends-on: [01]
status: done
---

## Context

The frontend is one 4,254-line file whose single inline script defines the error banner
and JS error logger (index.html:931–951) *inside the same script block they guard* — a
syntax error anywhere in the 3,300-line script prevents the error handler's own
registration, producing exactly the blank-window-with-no-repair-path CLAUDE.md warns
about. `init()` is only partially guarded: `/api/settings` is try/caught but the awaits
for `/api/projects` and `loadProject` are bare, and `unhandledrejection` only logs — so
a boot-time fetch failure yields a dead three-pane shell with no message. There is no
syntax gate anywhere: the current uncommitted ~1,000-line diff to this run-critical file
has zero automated verification.

## Task

1. Create a tiny first script (either `static/boot.js` or a separate small inline
   `<script>` placed before `themes.js`): registers `window.onerror` and
   `unhandledrejection` handlers that paint a visible banner ("Kettle hit a script
   error — [reload] [copy details]") using only DOM primitives it defines itself. It
   must not reference anything from the main script.
2. Make `unhandledrejection` show that banner, not just log.
3. Guard `init()`'s awaits so each boot phase failure paints the banner with the failing
   phase named.
4. Add the syntax gate: a Python test that extracts every `<script>` block from
   `index.html` (and any new .js files) and runs `node --check` on each — skipping with
   an honest message if node is absent, failing loudly in CI where node exists.

## Constraints

- No build step, no framework — plain files served as-is (roadmap decision).
- The boot script must stay tiny and dependency-free: it is the thing that must survive
  when everything else is broken.
- This file carries in-flight uncommitted work; land after brief 01, as its own commit.

## Done when

- Deliberately inserting `][` into the main script and reloading shows the banner (test
  this manually once; the automated proxy is the node --check gate).
- Killing the server after page load and reloading shows the named-phase banner, not a
  dead shell.
- The syntax-gate test exists and fails on an induced syntax error.

## Verify

Full suite; manual: boot a scratch server, break the script, reload, see the banner;
restore, verify normal boot.

## Afterwards

`status: done`; CLAUDE.md's blank-window warning gains a sentence noting the bootstrap
banner; brief 09 builds on the same file.
