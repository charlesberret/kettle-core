# Position — architect-codex

Occasion: `kettle-multirepo-automation-2026-07-30`  
Sender: `architect-codex`  
Phase: 2 (position)  
Filed: 2026-07-30  
Audit depth: **bounded**

## Synthesis

Kettle should automate **cross-repository confidence**, not cross-repository
writes. The family has four Git repositories, one deferred non-Git adapter
scaffold, and two empty non-member paths. Core owns product semantics, API,
Desk format, copy, palette, and contract identity; VS Code and Desktop own
host presentation and packaging over that spine. Local/runtime contract
enforcement already exists, so the precise missing layer is hosted,
exact-revision cross-repo verification. Before implementing it, Tranche 0 must
correct the architectural record: committed Desktop v2 now loads its own
`app/` UI over HTTP, contradicting stale core prose that says Desktop inherits
`static/index.html`. Once that and the token projection rules are named,
Tranche 1 may add read-only drift checks. No generator bot, cross-repo commit,
always-on agent, run-critical edit, or port-4242 interaction belongs in this
authorization.

## Seven-path operating map

| Path | Operative role and core contract | Automation disposition |
|---|---|---|
| `kettle` | Public product home, family map, roadmap, release definition; no runtime contract | Docs/link checks and orchestration syntax checks; no runtime ownership |
| `kettle-core` | Owns semantics, API/NDJSON, Desk schema, identity, CLI, copy, palette, runtime | Native tests and internal contract checks; exact-revision source for consumer drift checks; no unattended run-critical writes |
| `kettle-vscode` | Host adapter; consumes API/Desk identity; owns VSIX and generated copy/theme projections | Native CI plus read-only compatibility/copy/palette checks; no auto-regeneration commit |
| `kettle-desktop` | Host adapter; owns Electron, v2 `app/` viewport, sidecar packaging; consumes API/Desk and exact core provenance | Native CI, compatibility and clean-provenance checks; projection checks after Tranche 0 defines them |
| `kettle-obsidian` | Deferred non-Git adapter scaffold | Documentation validation only; no implementation automation until a dogfood workflow and release path exist |
| `kettle-cli` | Empty non-Git path; CLI belongs in core | No independent automation or repo creation |
| `kettle-mcp` | Empty non-Git path; optional future bridge has no recorded trigger | No independent automation or repo creation |

## Gate ballots

| ID | Ballot | Exact operative qualification or correction |
|---|---|---|
| G1 topology | **concur-with-correction** | Use 4 live Git repos + 1 deferred non-Git scaffold + 2 empty non-members. Preserve seven names in the plan, but do not call them seven repos. Remove or justify the empty paths only through the human gate. |
| G2 contracts | **concur-with-correction** | Core owns semantics and cross-host sources; adapters own host presentation, compatibility declarations, and packaging. Local/runtime enforcement exists; hosted exact-revision cross-repo CI does not. Desktop v2 owns `app/` and no longer inherits the core web file, so stale core docs must be reconciled before its projection contract is automated. |
| G3 safe automation | **concur-with-qualification** | Green only: read-only, fail-closed drift checks against an exact core revision, native tests, and report-only output. Read-only private-repo access is a reviewed credential decision. No write bots, run-critical edits, dirty-source releases, 4242 interaction, or always-on jobs. |
| G4 coordination substrate | **concur-with-qualification** | Use product-local per-occasion coordination, with one canonical final plan routed through the `kettle` product-home authority. Commit/ignore/delete of this raw `.coordination/` record remains a separate human gate. |
| G5 first tranche | **concur-with-correction** | Tranche 0: topology, Desktop v2 architecture, token projections, roadmap routing, stub/record decisions. Tranche 1 after explicit engineering authorization: hosted exact-revision compatibility, UI-copy, and palette checks plus existing native/local gates. Doctor expansion is a separate reviewed core change, not bundled authority. |
| G6 token owner | **concur-with-correction** | Core owns the host-neutral palette and semantic token vocabulary; VS Code and Desktop own only generated/host-specific projections. The duplicated token handoff Markdown must not become two canonical sources. |
| G7 roadmap authority | **concur-with-correction** | No binary precedence. `kettle` public roadmap governs family/public sequencing; `kettle-core/ROADMAP.md` governs core engineering; `.local/roadmap.md` governs private attention/signature principles. Live evidence corrects stale status prose. |

## Expected disagreements and surviving corrections

1. Peers describe cross-repo contracts as honor-system or laptop-only. I agree
   hosted CI is absent, but dissent from erasing runtime checks, native tests,
   the local family checker, and the product-home release gate.
2. Peers did not inspect the committed Desktop v2 topology. The decision must
   not repeat stale “Desktop loads core static” claims.
3. `architect-opus` abstains on G6 intent. The source files and generators make
   core ownership verifiable; the remaining choice is Desktop's projection
   mechanism.
4. Peers frame roadmap precedence as a patron-only binary. I propose
   scope-based routing; without another explicit ballot this remains a visible
   minority correction and human residual.

## Human gates and walls

1. Accept or change the corrected 4+1+2 map and Desktop v2 contract.
2. Authorize removal or continued justification of `kettle-cli/` and
   `kettle-mcp/`; no initialization is recommended.
3. Ratify G6 token ownership/projection wording and G7 scoped roadmap routing.
4. Select commit, ignore, archive elsewhere, or delete for this
   `.coordination/` record.
5. Separately authorize Tranche 0 documentation changes and Tranche 1
   engineering paths. Acceptance of the plan alone authorizes neither.
6. Separately authorize any credential, commit, push, publication, remote, or
   always-on action. Default is no.

Pre-declared walls remain: no writes outside this occasion, no commits or
pushes, no run-critical edits, no port 4242 interaction, no always-on job, and
no cross-repo write credential.

## Compact verified-evidence table

| Claim | Mark | Result |
|---|---|---|
| Topology and histories | **verified this session** | kettle 13, core 80, Desktop 29, VS Code 6 commits; Obsidian non-Git scaffold; CLI/MCP empty |
| Dirty state | **verified this session** | core, Desktop, and VS Code dirty; core includes `static/index.html` |
| Contract compatibility | **verified this session** | local family checker: core API 0 / Desk 0 compatible with both adapters |
| UI-copy and palette drift | **verified this session** | non-writing VS Code checks both passed; post-check status had no added modifications |
| Hosted CI topology | **verified this session** | each of four workflows performs only its own checkout |
| Desktop v2 architecture | **verified this session** | committed README/charter/main load local `app/index.html` and consume core HTTP API |
| Token authority | **verified this session** | both handoffs name core palette; Markdown copies byte-identical; palette projection check passes |
| Roadmap scopes | **verified this session from project prose** | product-home public, core-only engineering, and private attention scopes are separately declared |
| Signature rule | **from project prose** | semantic CLI/Desk changes share a core spine |
| Hosted exact-revision check is highest-value next step | **inference/recommendation** | follows from existing local checks plus single-checkout hosted workflows |

## Scribe request

Re-tally G1–G7 after all reconciles. Preserve the Desktop v2 correction, the
local-versus-hosted enforcement distinction, and any minority G7 position.
Do not claim joint authorization before separate human answers.
