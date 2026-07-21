---
id: 21
title: First-run design pass (web)
repo: setsweep-core
touches: [static/index.html (modal styles, #setupmodal, #addmodal), server.py (launch hint only)]
risk: run-critical
depends-on: [08]
status: open
---

## Context

Bare `setsweep` launches the web client, and the first thing a new user meets is the
**"set up Setsweep"** modal (`#setupmodal`). From the 2026-07-21 plugin-sitting handoff,
with the patron's own read: it is *functionally* right — provider selection, per-role
models, and an honest "Setsweep never stores API keys" line — but it **looks like a
debugging form**: dense layout, label column crowding the controls ("curatorial setup",
"session chat"), stock unstyled selects, and a heavy block of prose above it.

This is the same argument as the founding interview, applied one screen earlier. The setup
modal is the product's actual first impression, and right now it undersells a tool whose
whole thesis is careful, deliberate work. Before this goes on GitHub for strangers, the
first screen has to read as a product.

## Task

Scope is **the modals and their shared styles only**. Do not redesign the 4,254-line
sitting; this is a contained visual pass.

1. **Shared modal styles** — one set of rules serving `#setupmodal`, `#addmodal`, and the
   sweep confirm: consistent padding, a real label/control rhythm (labels stop crowding
   selects), styled selects that match the app's chrome rather than the browser default.
2. **`#setupmodal` copy** — shorter. Keep the "never stores API keys" line verbatim; it is
   the most trust-bearing sentence in the app. Cut the prose block down to what a first-time
   user needs to make the one decision in front of them.
3. **The gate** — verify the setup modal does not reappear once settings are valid. The
   handoff flags this as a possible bug; confirm before changing, then fix if real.
4. **Launch hint** (P2, `server.py`, one line) — after a bare launch, print the CLI viewport
   alongside the URL: `CLI: setsweep projects | add | queue …`. Discoverability for the
   half of the product that has no window.
5. **Accessibility** — focus trap, `aria-modal`, Esc-to-close on every modal touched.

## Constraints

- `static/index.html` is run-critical. Brief 08's boot bootstrap and `node --check` gate now
  protect this file — run the suite and the gate before and after.
- **Coordinate with brief 09** (sanitizer + a11y), which also touches these modals for focus
  traps. Do them in one sitting or sequence them deliberately; do not run both in parallel
  worktrees against this file.
- No build step, no framework, no CSS dependency — plain styles in the file, consistent with
  the no-build property.
- Do not touch the three-pane sitting layout, the editor, or the chat pane in this pass.

## Done when

- The setup modal reads as a product screen: a screenshot before/after shows obvious
  improvement in spacing, alignment, and density.
- Every touched modal is keyboard-navigable and focus-trapped.
- A valid-settings launch goes straight to the sitting with no setup modal.
- Suite green; `node --check` gate green.

## Verify

Fresh-install simulation: move `settings.json` aside, launch on an ephemeral port (never
4242), walk the first-run flow end to end by keyboard only, then relaunch and confirm the
modal does not return.

## Afterwards

`status: done`; note the launch-hint line in `README.md`'s CLI section; if the gate bug was
real, record it in `_Status.md`.
