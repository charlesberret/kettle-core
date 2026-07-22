---
id: 10
title: De-personalize the shipped surfaces
repo: setsweep-core
touches: [egress.py, server.py (or kits/prompts/ after brief 04), kits/_base.md, kits/frameworks/egress.md, _Status.md, settings handling]
risk: run-critical
depends-on: [01]
status: open
---

## Context

Charles's personal fleet is baked into surfaces every user would ship: `egress.py`'s
`_DEFAULT_ROUTES` (lines ~17–24) name avicenna, the majordomo inbox, and
`Characters/inbox`; the sweep prompt hardcodes Dramaturge/persona-recast doctrine
(currently server.py:281–289); `kits/_base.md` (lines ~80–92) instructs **every spawned
curator** about "Majordomo escalations" and "never write into ~/cloud/sync/system/";
`/api/admin` ships Xanadu persona scanning (server.py:1486–1502) and reads
`~/.cache/claude` sentinel files (1408–1456). A public user's curator would receive
instructions about a private infrastructure it cannot see — confusing at best,
behavior-distorting at worst — and the repo would leak personal topology.

## Task

1. **Egress routes → settings.** Move `_DEFAULT_ROUTES` into `settings.json` under an
   `egress` group (deep-merged like `curator` — extend `deep_merge_settings`), shipping
   neutral defaults (`handoff → .setsweep/outbound/`, no fleet names). Charles's routes
   become his local settings, not product code.
2. **Prompts and handbook.** Strip fleet doctrine from the sweep prompt; split
   `kits/_base.md` into the generic handbook plus an optional user overlay loaded from
   `settings.kits` (the fork-on-edit layer that already exists) — Charles's Majordomo
   material moves into his overlay.
3. **Admin panels.** Gate the Xanadu/sentinel panels behind a settings flag
   (`admin.fleet_panels: false` default); the code can stay, dormant, or move out —
   dormant-behind-flag is fine for now.
4. **The audit.** Run the grep list over every *tracked, shipped* file (exclude `.local/`,
   `.setsweep/`): `avicenna hesiod polytonic ficino relaytower majordomo Majordomo
   Seafile Xanadu Dramaturge charlesberret "/Users/charles"`. Fix every hit or justify
   it in the brief's closing note. `_Status.md` is included — it ships in the repo.

## Constraints

- Charles's own workflow must not break: his settings overlay carries what the defaults
  lose, and this brief includes writing that overlay into his local `settings.json`.
- Order with brief 04: if prompts have moved to files, edit files; if not, this brief
  edits `server.py` and re-runs the suite.

## Done when

- The grep list returns zero unjustified hits on tracked files.
- A fresh desk founded on a clean machine produces prompts/egress with no fleet
  vocabulary (stub-curator run, inspect assembled prompt).
- Charles's local sweep still stages egress to his configured routes (his settings, not
  defaults).

## Verify

Full suite; the grep audit; one stub founding + one stub sweep with default settings,
reading the assembled prompts for fleet terms.

## Afterwards

`status: done`; RELEASE.md's de-personalization checklist marks the code items done
(docs items live in brief 17); note the settings schema addition in API.md.
