---
project: setsweep
kind: software
phase: active
canonical: https://github.com/charlesberret/setsweep
deps: pip
test_cmd: pytest
test_signal: .pytest_cache/v/cache/lastfailed
healthbeacon: ~/.cache/setsweep/watch-health.json
---

## Status

Public-facing docs and de-personalized shipped surfaces are in place for a GitHub-ready
web + CLI product. Recent landings include briefs 09 (DOMPurify + keyboard floor), 10
(de-personalize), 20 (install determinism / doctor seed), 21 (first-run modals).

## Next action

- [ ] Brief 05 — API hardening (Host/Origin; supervised)
- [ ] Brief 11 — package restructure (when ready for packaging pivot)
- [ ] Brief 12 — unify folder-watchers
- [ ] Live open-brief list: `grep -l "status: open" docs/briefs/*.md`

## Known gaps

- No auth/Origin/Host checks beyond localhost bind (brief 05)
- Chat writes always-on via `acceptEdits` (interim)
- Full `setsweep doctor` expansion still in brief 18
- Desktop/plugin packaging separate from this core repo
