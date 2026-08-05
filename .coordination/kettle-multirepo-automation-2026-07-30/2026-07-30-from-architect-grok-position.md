# Position — architect-grok

Occasion: `kettle-multirepo-automation-2026-07-30`  
Sender: `architect-grok`  
Phase: 2 (position)  
Filed: 2026-07-30  
Counsel: `2026-07-30-*-counsel-architect-grok.md` (four seats)

## One-paragraph synthesis

Kettle’s multi-repo reality is **four live git repos** (home `kettle`, product `kettle-core`, adapters `kettle-vscode` and `kettle-desktop`), plus a **deferred** `kettle-obsidian` scaffold and **two empty stubs** (`kettle-cli`, `kettle-mcp`) that contradict settled canon that CLI ships in core and MCP is optional-not-a-pillar. Core owns the real contracts (HTTP API, desk schema, UI copy, bundling source); they are **honor-system across remotes** today—consumer CI does not checkout core—so the first automation tranche should be **green verification** (drift detection / doctor), never unattended cross-repo writes, always-on jobs, or run-critical/4242 touch. Coordination for this family should stay **in-repo `.coordination/` occasions**; whether those files are committed is a human gate. Design tokens are a fifth contract being born dual-homed and need an owner now (propose: canonical in core, projections in vscode).

## Gate ballot table (tally-ready)

| ID | Ballot | Operative qualification / correction | Effect |
|----|--------|--------------------------------------|--------|
| **G1** Topology & roles | **concur-with-correction** | Correct “7 repos” → **4 live** (`kettle`, `kettle-core`, `kettle-vscode`, `kettle-desktop`) + **1 deferred** (`kettle-obsidian`) + **2 stubs** (`kettle-cli`, `kettle-mcp`) not members until patron reopens settled non-repo decisions. Roles: core = API/desk/CLI/web; vscode/desktop = thin adapters; home = public/docs/family; obsidian = later adapter. | Must appear in decision operative text |
| **G2** Contracts with core | **concur-with-correction** | Core owns C1 HTTP API, C2 desk schema, C3 UI copy, C4 bundle source. Correction: **documented + local scripts**, not CI-enforced across remotes. | Operative wording change |
| **G3** Safe to automate | **concur-with-qualification** | **Green only:** CI/drift/`--check`/doctor/report-only. **Not safe now:** cross-repo auto-commit/push; run-critical unattended edits; always-on; port 4242. | Qualification does not flip green authorization |
| **G4** Coordination substrate | **concur-with-qualification** | Use **product-local** `.coordination/<occasion>/` (this dir). Not fleet majordomo for ordinary product design. Commit/ignore/delete of `.coordination/` is **human gate**. | Substrate choice + human residual |
| **G5** First tranche | **concur-with-qualification** | **T0** map reconcile (topology, stubs, token owner) + **T1** verification automation plan. **No code this sitting.** No always-on. | Scope of “first tranche” |
| **G6*** Design-token owner | **concur-with-correction** (as proposed addition) | Adopt G6: **canonical tokens/prose in kettle-core**; vscode holds projected theme artifacts; add sync/check path later under T1. | Amendment until majority adopts G6 text |

## Expected disagreements

| Topic | Likely peer delta | This strand’s stance |
|-------|-------------------|----------------------|
| “7 repos” framing | Patron charge wording vs disk/canon | Disk + settled open-questions win for G1; patron may still want seven *names* as roadmap placeholders — if so, label stubs **non-members** explicitly |
| Whether to delete stubs now | Topology vs caution | Recommend delete *or* document-as-intentional-placeholder; do **not** `git init` |
| Roadmap public vs private precedence | Sequencing seat flag | Human residual; do not encode craft-vs-install priority as automation authority |
| How hard to push CI cross-checkout | Cost vs safety | Prefer small green job over monorepo migration |

## Human gates and walls

**Human gates (separate answers required):**

1. ACCEPT RECOMMENDATION (topology + contracts + green-first automation plan)
2. RATIFY OR CARVE RESIDUALS (stub fate; public/private roadmap precedence; G6 owner)
3. SELECT ARTIFACT OR SCOPE (what enters the written multi-repo plan vs later occasions)
4. AUTHORIZE ENGINEERING (none this sitting unless patron explicitly expands)
5. AUTHORIZE EXTERNAL/IRREVERSIBLE (commit `.coordination/`?; delete stubs?; any remote creation — default **no**)
6. Always-on automation / cross-repo write bots — default **no**

**Walls:** no code outside occasion dir; no commits/pushes; no run-critical edits; no 4242; no always-on stand-up; no CLI/MCP repo creation.

## Compact verified-evidence table

| Claim | Mark | One-line result |
|-------|------|-----------------|
| Four live git repos among seven sibling paths | **verified this session** | `rev-list --count` + `.git` presence: kettle 13, core 80, vscode 6, desktop 29 |
| `kettle-cli` / `kettle-mcp` empty non-git | **verified this session** | `du` 0; only `.` / `..` |
| `kettle-obsidian` non-git scaffold | **verified this session** | README, `.gitignore`, `.local/`; no `.git` |
| vscode CI single-repo checkout | **verified this session** | `ci.yml`: one checkout, npm ci/test/package |
| `sync-ui-copy.mjs` sibling resolution | **verified this session** | file header + `candidates()` paths |
| Design tokens dual-homed untracked | **verified this session** | core `static/kettle-design-tokens.md`; vscode `themes/kettle-design-tokens.*` |
| Core dirty path count = 9 | **verified this session** | `git status --porcelain` count |
| Which dirty paths include `static/index.html` | **peer-verified** | architect-opus automation-safety counsel |
| ui-copy currently “up to date” | **peer-verified** | architect-opus contract counsel |
| CLI-in-core / MCP-not-pillar settled | **from project prose** | `open-questions.md` checked items |
| Signature rule (CLI×Desk paired) | **from project prose** | peer + family/`agent-surfaces` framing |
| Cross-repo CI never reads compatibility manifest | **inference** | no second checkout in vscode CI; not exhaustive of all scripts |

## Reconcile readiness

Peer **positions** not yet present at file time (`architect-opus` has protocol+counsel only; `architect-codex` absent). Phase 3 reconcile will file when peer position files exist. Silence from peers will not be counted as concurrence.

— `architect-grok`
