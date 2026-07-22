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

Roadmap + PLATFORMS living parity (2026-07-22). Brief **22** done: web add-project is
name+folder (more options collapsed); founding empty-states orient to the agent pane;
desktop inherits via the same `static/`. UI type hierarchy in `docs/UI.md`.

## Next action

- [ ] Brief 05 — API hardening (Host/Origin; supervised)
- [ ] Brief 11 / 15 — package + desktop distribution when ready
- [ ] Live open-brief list: `grep -l "status: open" docs/briefs/*.md`
- [ ] Keep [`docs/PLATFORMS.md`](docs/PLATFORMS.md) ritual matrix honest when UI ships
- [ ] Packaged desktop: `npm run build:sidecar` after core static changes

## Known gaps

- No auth/Origin/Host checks beyond localhost bind (brief 05)
- Chat writes always-on via `acceptEdits` (interim)
- Full `setsweep doctor` expansion still in brief 18
- Desktop/plugin packaging separate from this core repo
