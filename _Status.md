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

The suite is 269 green (was 36 in mid-June). On 2026-07-17 a full-system survey (eleven
subsystem audits across core, desktop, and plugin) produced `ROADMAP.md`, the
`docs/PLATFORMS.md` / `ENGINEERING.md` / `RELEASE.md` companions, and eighteen agent
briefs under `docs/briefs/`. Seven briefs have since landed on `codex/shore-up-system`:
01 (the working tree is now committed — the roadmap's first act), 04 (product prompts
externalized to `kits/prompts/`), 07 (curator stream watchdog), 14 (deeper suite + CI),
03 (tool tiers single-sourced on `runtime.TOOL_TIERS`; CLI de-hardcoded from Claude), 06
(per-provider capability table with pre-stream read-only enforcement), and 08 (frontend
error bootstrap that survives a script parse failure, plus a `node --check` gate). The
branch is committed and green; promotion to `main` is still pending patron review.

## Next action

- [ ] Brief 02 — reconcile the two divergent plugin implementations (plugin repo)
- [ ] Brief 11 — package restructure + version (the packaging pivot; unblocks 13/15/17/18
      — do it alone, it moves every module)
- [ ] Newly unblocked and safe: brief 09 (sanitizer + a11y, needs 08 ✓), brief 12 (unify
      the folder-watchers, needs 03 ✓)
- [ ] Held for a supervised session: brief 05 (API hardening — three-repo blast radius),
      brief 10 (de-personalization — rewrites private egress config)
- [ ] Live open-brief list: `grep -l "status: open" docs/briefs/*.md`

## Known gaps

Full inventory lives in `ROADMAP.md` ("Where it stands") and the briefs; still-open
highlights:

- No auth/Origin/Host checks on the HTTP surface — localhost bind is the only barrier
  (brief 05, held for supervised)
- Chat writes are always-on via `acceptEdits` (interim); a fuller permission UX may
  replace this later
- Settings shallow-merge clobber guard covers only `curator`/`agents` groups — other
  top-level groups can still be dropped by a bad patch
- Personal-fleet vocabulary still baked into shipped egress routes / prompts / admin
  panels (brief 10, held for supervised)
