---
id: 10
title: De-personalize the shipped surfaces
repo: kettle-core
touches: [egress.py, server.py (or kits/prompts/ after brief 04), kits/_base.md, kits/frameworks/egress.md, _Status.md, settings handling]
risk: run-critical
depends-on: [01]
status: done
---

## Context

The original internal build carried maintainer-specific egress routes, agent
nicknames, absolute paths, and fleet panels into surfaces every user would
ship. A public user's curator would receive instructions about private
infrastructure it cannot see, confusing behavior and leaking personal topology.

## Task

1. **Egress routes → settings.** Move `_DEFAULT_ROUTES` into `settings.json` under an
   `egress` group (deep-merged like `curator` — extend `deep_merge_settings`), shipping
   neutral defaults (`handoff → .kettle/outbound/`, no fleet names). Maintainer routes
   become local settings, not product code.
2. **Prompts and handbook.** Strip fleet doctrine from the sweep prompt; split
   `kits/_base.md` into the generic handbook plus an optional user overlay loaded from
   `settings.kits` (the fork-on-edit layer that already exists). Private fleet
   material moves into the local overlay.
3. **Admin panels.** Gate private fleet and sentinel panels behind a settings flag
   (`admin.fleet_panels: false` default); the code can stay, dormant, or move out —
   dormant-behind-flag is fine for now.
4. **The audit.** Run the grep list over every *tracked, shipped* file (exclude `.local/`,
   `.kettle/`): absolute home paths, private hostnames, agent nicknames, and
   maintainer-only sync roots. Fix every hit or justify it in the closing note.

## Constraints

- Existing workflows must not break: a local settings overlay carries what the
  defaults lose.
- Order with brief 04: if prompts have moved to files, edit files; if not, this brief
  edits `server.py` and re-runs the suite.

## Done when

- The grep list returns zero unjustified hits on tracked files.
- A fresh desk founded on a clean machine produces prompts/egress with no fleet
  vocabulary (stub-curator run, inspect assembled prompt).
- A local sweep still stages egress to configured routes from settings, not defaults.

## Verify

Full suite; the grep audit; one stub founding + one stub sweep with default settings,
reading the assembled prompts for fleet terms.

## Afterwards

`status: done`; RELEASE.md's de-personalization checklist marks the code items done
(docs items live in brief 17); note the settings schema addition in API.md.

## Closing note (2026-07-22)

Shipped product surfaces are clean of fleet names. Remaining audit hits are justified:

| Hit | Why it stays |
|---|---|
| `test_egress` custom route strings | Asserts that settings overlays still work |
| `docs/briefs/10`, `docs/RELEASE.md` audit prose | Describes the historical problem |

Local `settings.json` overlays (gitignored) carry custom `egress.routes` and
maintainer-only admin settings.
