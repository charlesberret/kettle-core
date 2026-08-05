# Counsel — automation-safety seat (architect-codex)

Speaking only from the safety lens.

## Current conditions verified this session

- `kettle-core` is dirty, including run-critical `static/index.html`.
- `kettle-desktop` is dirty across its v2 implementation and tests.
- `kettle-vscode` has untracked token handoff files.
- The non-writing checks `tools/check_family.py`, `check-ui-copy`, and
  `check-palette` passed; a post-check status read showed no new sibling
  modifications.
- Every hosted workflow uses one checkout. Adding a private cross-repo checkout
  would introduce a credential and revision-selection problem that the plan
  must address explicitly.

## Risk tiers

| Tier | Scope | Ballot from this seat |
|---|---|---|
| Green | Read-only manifest/copy/palette drift checks against an exact core revision; native tests; report-only summaries; ephemeral-port integration tests | Safe to authorize after Tranche 0 names the contract |
| Yellow | Read-only cross-repo credential or public-repo checkout; `kettle doctor` code extension; release/version orchestration; installed hooks | Separate reviewed implementation with least privilege and human merge |
| Red | Cross-repo auto-commit/push; generator bots; dirty-source packaging; unattended run-critical edits; port 4242 interaction; cron/launchd/watchers | Not authorized |

The fastest safe automation is verification that shortens the feedback loop
without multiplying writes. A passing narrow drift check is not a release
attestation: clean provenance, native tests, packaging checks, and manual
product gates remain distinct.

## Preliminary ballots

| Gate | Ballot | Operative qualification |
|---|---|---|
| G3 | **concur-with-qualification** | Green detection only in the first engineering tranche. Use exact revisions, read-only credentials if required, ephemeral ports, and fail-closed inputs. |
| G5 | **concur-with-qualification** | Tranche 0 must reconcile topology and Desktop v2 contracts before CI encodes them. Tranche 1 may implement read-only checks only after explicit engineering authorization. |

## Walls

1. No unattended write to `server.py`, `static/index.html`,
   `kettle_main.py`, `projects.json`, or `settings.json`.
2. No bind, probe, or signal of port 4242 from this sitting or its proposed
   agent tooling.
3. No cross-repo write credential and no credential broader than read-only
   access to the exact dependency needed by a check.
4. No always-on job and no automation over a dirty or unresolved source tree.

