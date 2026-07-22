---
project: setsweep
kind: software
phase: active
canonical: ~/cloud/git-projects/setsweep-core
deps: pip
test_cmd: pytest
test_signal: .pytest_cache/v/cache/lastfailed
healthbeacon: ~/.cache/setsweep/watch-health.json
---

## Status

The suite is 279+ green. Roadmap + briefs live; landed on `codex/shore-up-system` include
01, 03, 04, 06, 07, 08, 10 (de-personalize), 14, 20 (install determinism), 21 (first-run
modals). Personal fleet routes and admin panels moved to local `settings.json` overlays.

## Next action

- [ ] Public GitHub path (web + CLI): brief 09 (sanitizer + a11y), brief 17 (docs for
      strangers — clone URL, glossary, de-personalize remaining docs), brief 05 (API
      hardening) when supervised
- [ ] Brief 11 — package restructure (unblocks 13/15/18) — larger sitting
- [ ] Brief 12 — unify folder-watchers
- [ ] Live open-brief list: `grep -l "status: open" docs/briefs/*.md`

## Known gaps

Full inventory lives in `ROADMAP.md` ("Where it stands") and the briefs; still-open
highlights:

- No auth/Origin/Host checks on the HTTP surface — localhost bind is the only barrier
  (brief 05, held for supervised)
- Chat writes are always-on via `acceptEdits` (interim); a fuller permission UX may
  replace this later
- Docs still name local paths (`~/cloud/git-projects/…`) — brief 17
- XSS sanitizer is still a blocklist; keyboard a11y incomplete — brief 09
