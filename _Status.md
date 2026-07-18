---
project: setsweep
kind: software
phase: active
canonical: ~/Repos/setsweep-core
deps: pip
test_cmd: pytest
test_signal: .pytest_cache/v/cache/lastfailed
healthbeacon: ~/.cache/setsweep/watch-health.json
---

## Status

The suite is 225 green on Python 3.14.6. Branch `codex/shore-up-system` now carries a
durable, committed baseline: the provider-neutral runtime, proposal-first founding flow,
viewport changes, mechanical sweep close, and tracked egress layer are all in history.
The empty root `package-lock.json` was unreferenced and removed; no experimental hunks
were held back. `ROADMAP.md`, the three companion plans, and eighteen agent briefs under
`docs/briefs/` are also committed. Brief 01 is complete; the overnight chain continues
with additive test depth before either remaining run-critical brief.

## Next action

- [ ] Brief 14 — deepen route, CLI, lifecycle, and CI coverage
- [ ] Brief 07 — add the curator idle watchdog and terminal-stream guarantees
- [ ] Brief 04 — externalize prompt constants without genericizing them
- [ ] After this core-only chain, brief 02 remains the separate plugin-repo Phase 0 task

## Known gaps

Full inventory now lives in `ROADMAP.md` ("Where it stands") and the briefs; still-true
highlights:

- No auth/Origin/Host checks on the HTTP surface — localhost bind is the only barrier
  (brief 05); Grok provider breaks the read-only interview tier (brief 06)
- A hung curator CLI pins a handler thread — no watchdog (brief 07)
- Frontend has zero tests and its error banner lives inside the script it guards — a JS
  error still produces a blank window (brief 08)
- Chat writes are always-on via `acceptEdits` (interim); a fuller permission UX may
  replace this later
- Settings shallow-merge clobber guard covers only `curator`/`agents` groups — other
  top-level groups can still be dropped by a bad patch
