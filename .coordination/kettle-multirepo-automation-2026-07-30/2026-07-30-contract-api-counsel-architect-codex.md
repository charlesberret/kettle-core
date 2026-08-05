# Counsel — contract/API seat (architect-codex)

Speaking only from the contract and authority lens.

## Boundary inventory

| Contract | Canonical owner | Current consumers/projections | Enforcement verified this session |
|---|---|---|---|
| HTTP and NDJSON API | `kettle-core/API.md` plus core runtime/tests | VS Code, Desktop, future adapters | Consumer runtime compatibility checks and native tests; no hosted multi-repo CI |
| Durable Desk schema | `kettle-core` | Core CLI, VS Code, Desktop | Contract integer and consumer manifests; local family checker |
| Core/API/Desk identity | `kettle-core/kettle_contract.py` | `/api/ping`, both adapter manifests | `tools/check_family.py` reports core API 0 / Desk 0 compatible with both adapters |
| Canonical visible copy | `kettle-core/static/ui-copy.js` | VS Code generated `src/uiCopy.ts`; Desktop v2 has a separate presentation surface not yet named in this sync contract | Local core test plus VS Code `--check`; check passed |
| Product palette and semantic roles | `kettle-core/static/kettle-palette.json` and theme pack | VS Code generated themes; Desktop v2 projection still needs an explicit rule | Core palette tests plus VS Code `check-palette`; check passed |
| Bundled core provenance | Exact clean `kettle-core` checkout | Desktop sidecar | Desktop gate fails closed on dirty/unversioned core and stamps commit, contracts, and content hash |
| Public family map and release definition | `kettle` product home | All repos' documentation/routing | Product-home docs CI; no runtime ownership |

The peer phrase “enforced only on Charles's laptop” is too broad. There is real
runtime enforcement in both consumers, a local multi-repo checker, a product
home release gate, and native tests. The precise gap is **hosted cross-repo
verification against an exact core revision**: every current workflow checks
out only its own repository.

## Design-token finding

The current token drafts answer ownership more clearly than the first peer
position allowed:

- Both Markdown handoff files explicitly name
  `kettle-core/static/kettle-palette.json` as source of truth.
- The core and VS Code Markdown files are byte-identical.
- `sync-palette.mjs --check` confirms the committed VS Code themes match the
  core palette.
- Core UI guidance says adapters own host packing but must not invent a second
  brand palette.

The untracked VS Code JSON is a resolved projection, not a competing canonical
schema. The unresolved part is how Desktop v2 consumes the same roles, not who
owns the host-neutral vocabulary.

## Preliminary ballots

| Gate | Ballot | Operative correction |
|---|---|---|
| G2 | **concur-with-correction** | Core owns semantics and cross-host sources; adapters own compatibility declarations and host projections. State that local/runtime enforcement exists while hosted cross-repo CI does not. Add Desktop v2's local UI to the projection inventory. |
| G3 | **concur-with-qualification** | Automate exact-revision, read-only verification. Keep regeneration an explicit maintainer action. |
| G6 | **concur-with-correction** | Core owns the host-neutral palette/tokens; VS Code and Desktop own generated or host-specific projections only. Decide Desktop's projection mechanism in Tranche 0. |

## Wall

No bot may regenerate and commit a consumer projection across a repository
boundary. A multi-repo check must use an exact, reviewable core revision and
read-only access; it must fail closed when that input cannot be resolved.

