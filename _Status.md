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

Roadmap refreshed 2026-07-22. Public docs, de-personalize, install determinism, UI type
hierarchy (`docs/UI.md`), plugin auto-start (0.6.4). **Open product debt:** founding UX
parity — plugin Desk is ahead; web/desktop share the older multi-field add path (brief
**22**). Desktop is not a separate frontend; it inherits web.

## Next action

- [ ] Brief **22** — viewport founding parity (web canonical → desktop free)
- [ ] Brief 05 — API hardening (Host/Origin; supervised)
- [ ] Brief 11 / 15 — package + desktop distribution when ready
- [ ] Live open-brief list: `grep -l "status: open" docs/briefs/*.md`
- [ ] Keep [`docs/PLATFORMS.md`](docs/PLATFORMS.md) ritual matrix honest when UI ships

## Known gaps

- No auth/Origin/Host checks beyond localhost bind (brief 05)
- Chat writes always-on via `acceptEdits` (interim)
- Full `setsweep doctor` expansion still in brief 18
- Desktop/plugin packaging separate from this core repo
