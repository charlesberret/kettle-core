# Counsel — contract/API seat (architect-opus)

Speaking only from the contract lens: what crosses a repo boundary, who owns it, and
whether the boundary is enforced or merely described.

## The four contracts that cross a boundary

| # | Contract | Owner (verified) | Consumers | Enforcement |
|---|---|---|---|---|
| C1 | **HTTP API** (`/api/*`, port 4242) | kettle-core — `API.md`, 387 lines | vscode, desktop | **manifest-declared, not tested cross-repo** |
| C2 | **Desk schema** (`.kettle/`) | kettle-core | vscode, desktop, CLI | same |
| C3 | **UI copy catalog** (`static/ui-copy.js`) | kettle-core | vscode (`src/uiCopy.ts` snapshot) | **generator script, run by hand** |
| C4 | **Core source for bundling** | kettle-core tree | desktop sidecar | `check-core-source.sh`, local only |

## How the coupling actually works (verified by reading the scripts)

`kettle-vscode/scripts/sync-ui-copy.mjs` resolves core in this order: `KETTLE_UI_COPY`
env → `KETTLE_SRC` env → **sibling filesystem paths** `../kettle-core/static/ui-copy.js`,
then legacy `../setsweep-core/...`, then `../../`. `kettle-desktop/scripts/check-core-source.sh`
takes the core path as `$1` and refuses to bundle a dirty core tree unless
`KETTLE_ALLOW_UNVERIFIED_CORE=1`.

Both are **good scripts**. `check-core-source.sh` in particular already does the right
thing — it records the core commit, detects a dirty tree, and fails closed. That is a
real provenance gate, and it is better than most multi-repo setups have.

## The structural gap

**Every cross-repo contract is enforced only on Charles's laptop.**

- `kettle-vscode/.github/workflows/ci.yml` runs exactly three steps — `npm ci`,
  `npm test`, `npm run package` (verified). It performs a single `actions/checkout` of
  its own repo. There is no second checkout of kettle-core anywhere in any workflow.
- Therefore C3 drift is caught **only** when a human runs `sync-ui-copy.mjs` in a
  sibling checkout. In CI, the committed `uiCopy.ts` snapshot is simply accepted as truth.
- `kettle-compatibility.json` declares `{"api_versions":[0],"desk_schema_versions":[0],
  "allow_legacy_identity":false}`. Nothing in kettle-core's `test.yml` reads any
  consumer's manifest, and nothing in a consumer's CI reads core's actual API version.
  The manifest is an **assertion**, not a check. (Honesty rail: I verified the file's
  content and the absence of cross-repo checkout; I did **not** exhaustively prove no
  test anywhere reads it — `AUDIT_DEPTH: bounded`.)

**Right now the snapshot is in sync** — `sync-ui-copy` reports "up to date" against
`../kettle-core/static/ui-copy.js`. So this is a latent risk, not a live break. But it
is in sync *by luck and diligence*, not by machine.

## Live evidence of the gap

Uncommitted design-token work is spanning two repos by hand this week:
`kettle-core/static/kettle-design-tokens.md` (untracked) and
`kettle-vscode/themes/kettle-design-tokens.{json,md}` (untracked). That is a **fifth
contract being born** — a shared token/palette vocabulary — with no owner declared and
no sync path except `sync-palette.mjs` sitting beside it. This is exactly the moment a
contract either gets a home or becomes drift.

## Ballot from this seat

- **G2 — concur with correction**: core owns C1–C4 unambiguously. The correction is
  that *ownership is documented but unenforced*; the plan must not describe these as
  "contracts" without saying they are honor-system across the repo line.
- **G3 — qualified**: the highest-value automation here is *verification*, not
  generation — a CI job that checks out core beside a consumer and fails on drift.
  That is additive, reversible, and touches no run-critical file.
- **New gate proposed (G6): who owns the design-token vocabulary?** It is being created
  right now in two repos at once and has no entry in `family.md`.

## Wall from this seat

Do not automate *writing* a synced artifact across a repo boundary (e.g. a bot that
regenerates `uiCopy.ts` and commits it). Automate **detecting** divergence and
reporting it. A generator that commits into a second repo turns a bad core change into
two bad repos before a human sees either.
