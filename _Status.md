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

Core alignment checkpoint (2026-07-25): package/API/desk-schema identity is
core-owned and published on `/api/ping`; the reference web ritual has a structural
CI bar; blank founding cards and provider activity chrome are integrated. Desktop
inherits the same `static/`. Brief **23** remains in progress until the packaged
plugin and manual provider/browser ritual matrix are recorded.

## Next action

- [ ] Brief 05 — API hardening (Host/Origin; supervised)
- [ ] Brief 11 / 15 — package + desktop distribution when ready
- [ ] Brief 23 — finish packaged VSIX + manual provider/viewport ritual walk
- [ ] `python3 tools/check_family.py` — identity/compatibility across sibling repos
- [ ] Live open-brief list: `grep -l "status: open" docs/briefs/*.md`
- [ ] Keep [`docs/PLATFORMS.md`](docs/PLATFORMS.md) ritual matrix honest when UI ships
- [ ] Packaged desktop: `npm run build:sidecar` after core static changes

## Known gaps

- No auth/Origin/Host checks beyond localhost bind (brief 05)
- Chat writes always-on via `acceptEdits` (interim)
- Full `setsweep doctor` expansion still in brief 18
- Desktop/plugin packaging separate from this core repo
- Structural ritual tests do not prove browser focus, installed-extension freshness,
  or real Claude/Grok provider behavior; those remain brief 23 release gates
