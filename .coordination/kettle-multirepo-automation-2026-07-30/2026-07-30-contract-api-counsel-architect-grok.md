# Counsel — contract/API seat (architect-grok)

Speaking only from the contract lens.

## Boundary contracts (verified / peer-aligned)

| ID | Contract | Owner (prose + layout) | Consumers | Enforcement observed |
|----|----------|------------------------|-----------|----------------------|
| C1 | HTTP API `/api/*` (port 4242) | kettle-core (`API.md`) | vscode, desktop | Docs + runtime in core; **no cross-repo CI checkout of core** in vscode workflow |
| C2 | Desk schema (`.kettle/`) | kettle-core | vscode, desktop, CLI-in-core | Same pattern |
| C3 | UI copy catalog `static/ui-copy.js` | kettle-core | vscode `src/uiCopy.ts` snapshot | `scripts/sync-ui-copy.mjs` — maintainer action; resolution via env then sibling paths |
| C4 | Core source for desktop bundling | kettle-core tree | desktop sidecar | `check-core-source.sh` (local; dirty-tree fail-closed) — **peer-described**; script presence verified in desktop `scripts/` |

**Verified this session:**

- `kettle-vscode/.github/workflows/ci.yml`: single `actions/checkout`, then `npm ci` / `test` / `package` — no second checkout of kettle-core.
- `sync-ui-copy.mjs` header documents sibling resolution and “explicit maintainer action”; supports `--check` (read path for CI-shaped use).
- Untracked design-token surfaces exist in **two** trees: `kettle-core/static/kettle-design-tokens.md` and `kettle-vscode/themes/kettle-design-tokens.{json,md}` — a nascent **C5** without declared owner in family canon.

**Honesty:** did **not** run `sync-ui-copy.mjs` this session (peer opus did and self-reported a near wall-brush). Did not exhaustively search every test file for `kettle-compatibility.json` reads. Snapshot sync state treated as **peer-verified, not independently reproduced**.

## Structural gap

Cross-repo contracts are **documented and locally scripted**, not **machine-enforced across remotes**. Compatibility manifests assert versions; consumer CI does not re-verify against core HEAD. That is honor-system coupling.

## Preliminary gate ballots (this seat only)

| Gate | Ballot | Operative note |
|------|--------|----------------|
| G2 | **concur-with-correction** | Core owns C1–C4. Correction: ownership is real; **enforcement is local/honor-system**, not CI-coupled. Plan language must not call them “enforced contracts” without that qualifier. |
| G3 | **concur-with-qualification** | Highest-value automation is **verification** (checkout core beside consumer; fail on ui-copy / compatibility drift), not auto-commit generation across repos. |
| G6* | **propose adopt** | Design-token vocabulary needs an owner **now** while dual-repo drafts exist. Recommendation: **canonical prose/tokens in kettle-core**; vscode holds **generated/projected theme JSON** only. |

## Wall

Do not automate **unattended cross-repo writes** of synced artifacts (bot regenerates consumer snapshot and commits). Automate **detect + fail** first.

— `architect-grok` / contract-api seat
