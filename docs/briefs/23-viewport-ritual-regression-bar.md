---
id: 23
title: Viewport ritual regression bar
repo: kettle-core
touches: [test_frontend.py, static/index.html, docs/PLATFORMS.md, tools/check_family.py; corresponding checks in kettle-vscode]
risk: run-critical
depends-on: [22]
status: in-progress
---

## Context

Brief 22 aligned the visible founding entry, but the plugin later regressed parts
of the canonical state machine while the parity matrix still said `same`. A
rendered similarity claim is not enough. Core needs an executable reference-web
baseline, consumers need adapter checks, and releases still need a manual walk
through real providers and packaged artifacts.

The canonical ritual is:

```text
register → interview → confirm card → propose → open proposal
→ approve proposal → found → first queue → chat activity → compact
→ approve/comment/sweep
```

## Task

1. Add a structural core test that connects the reference web functions to
   `/api/interview`, `/api/propose`, `/api/approve`, `/api/found`, and
   `/api/compact`; confirms proposal chrome retains a visible found action; and
   confirms activity events and blank confirmation cards are handled.
2. Add corresponding plugin adapter tests for its host messages and client
   routes. These tests may permit a host-specific layout, not a second state
   machine.
3. Publish core, API, and desk-schema identity on `/api/ping`; require viewports
   to declare compatible integer contracts.
4. Provide one read-only family check for versions, revisions, dirty state, and
   contract compatibility across sibling checkouts.
5. Re-run the manual ritual on a scratch folder under each supported provider
   and each shipping graphical viewport. Record the core/plugin build and
   packaged install under test.

## Constraints

- Never bind, curl, replace, or signal port 4242 from the automated bar.
- Structural tests are a regression floor, not proof that browser focus,
  extension installation, or a third-party provider worked end to end.
- Desktop keeps loading core `static/`; do not create an Electron frontend.
- Ordinary plugin builds remain independently reproducible and do not read a
  sibling checkout implicitly.

## Done when

- The ordinary core and plugin suites fail if any ritual hop above is removed.
- `python3 tools/check_family.py` reports compatible known contracts across the
  three sibling repos.
- A dated manual record covers fresh founding, proposal editing/founding, visible
  activity, compact, and one sitting under the supported providers and packaged
  viewports.
- `docs/PLATFORMS.md` distinguishes automated coverage from manual/package
  validation and no longer calls an unverified adapter `same`.

## Verify

```sh
python3 -m pytest
python3 tools/check_family.py
```

For the manual matrix, use an ephemeral test server or a user-approved live
restart. Never make port 4242 lifecycle changes from an autonomous agent.

## Current checkpoint (2026-07-25)

Core identity, family-check plumbing, and the reference-web structural bar are
implemented in the working tree. Provider/browser/package walkthroughs remain
an explicit release gate; this brief stays `in-progress` until they are recorded.
