# Position — architect-gemini

Occasion: `kettle-multirepo-automation-2026-07-30`
Sender: `architect-gemini`
Phase: 2 (position)

## Synthesis
The multirepo automation plan must prioritize cross-repository confidence through verification, rather than aggressive cross-repo generation. The physical topology of 7 directories on disk obscures the reality of 4 active repositories, 1 scaffold, and 2 empty stubs that contradict the canonical design. By anchoring our automation on read-only drift detection across these 4 live repos, we maintain safety walls.

## Gate ballots

| ID | Ballot | Operative qualification |
|---|---|---|
| G1 | **concur-with-correction** | 4 active repos, 1 scaffold, 2 empty non-member stubs. The claim of 7 repos is structurally false. |
| G2 | **concur-with-correction** | Core owns semantics/contracts, but enforcement is strictly local/manual. Hosted exact-revision CI is required. |
| G3 | **concur-with-qualification** | Green tier only (read-only drift detection, native tests). No write bots or always-on jobs. |
| G4 | **concur-with-qualification** | Use product-local per-occasion `.coordination/`. Final disposition of this directory is a human gate. |
| G5 | **concur-with-correction** | Tranche 0 (architectural cleanup/stub removal). Tranche 1 (green drift checks). |
| G6 | **concur-with-correction** | Core owns host-neutral palette; adapters own projections. |
| G7 | **concur-with-correction** | Scope-based routing governs roadmaps; there is no binary precedence. |

## Expected disagreements
None beyond existing minor peer corrections regarding desktop v2 specifics and roadmap routing, which I have integrated from the earlier positions.

## Human gates
1. Authorize deletion of empty stubs (`kettle-cli`, `kettle-mcp`).
2. Decide disposition of `.coordination/`.
3. Ratify roadmap scope routing and token ownership.
4. Explicitly authorize Tranche 1 engineering paths.

## Verified-evidence table
| Claim | Method | Result |
|---|---|---|
| Topology | `ls` and `family.md` | 7 dirs present, but `family.md` refutes CLI/MCP as separate repos |
