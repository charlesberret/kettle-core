# Position — architect-opus

Occasion: `kettle-multirepo-automation-2026-07-30` · Phase 2 · Filed 2026-07-30
Audit depth: **bounded**. Peers: `architect-codex`, `architect-grok` (ballots awaited).

## Synthesis

The charge assumes a seven-repo family and asks how to automate across it. The tree
does not support that assumption: **there are four repos, not seven** — `kettle`,
`kettle-core`, `kettle-vscode`, `kettle-desktop` — plus one legitimately deferred
adapter (`kettle-obsidian`, README only) and two empty directories (`kettle-cli`,
`kettle-mcp`, 0 bytes each) whose existence contradicts decisions already recorded as
**settled** in `kettle/.local/open-questions.md` ("CLI first-class… ships in core";
"MCP optional only; not a pillar"). The private canon in `kettle/.local/family.md`
has a section literally headed "Not separate repos (by default)." So the first
deliverable of a multi-repo plan is *subtraction*, not coordination.

The real coupling between the four live repos is genuine but **enforced only on this
laptop**: `sync-ui-copy.mjs` finds core by walking sibling filesystem paths, and every
CI workflow checks out exactly one repo. The compatibility manifests
(`{"api_versions":[0],…}`) are assertions no machine cross-checks. Nothing is broken
today — the snapshot is currently in sync — but it is in sync by diligence, not by
construction.

That reframes what "automate to accelerate" should mean here. The bottleneck is not
typing; it is *confidence that a core change didn't silently break two consumers*.
And `agent-surfaces.md` actively forbids the obvious parallelization: its signature
rule says a semantic change that improves the CLI without the Desk is **incomplete**.
So the acceleration available is **confidence velocity** — automate verification, then
change the shared spine fast and often — not three agents on three repos. I hold this
as my central claim and expect it to be the sitting's main disagreement.

## Gate ballots

| ID | Gate | Ballot | Operative qualification |
|---|---|---|---|
| **G1** | True repo topology; load-bearing vs dormant | **concur-with-correction** | Not 7. **4 live** (`kettle` home/docs · `kettle-core` engine · `kettle-vscode` primary adapter · `kettle-desktop` built, low-attention), **1 deferred** (`kettle-obsidian`), **2 stubs to delete or justify** (`kettle-cli`, `kettle-mcp`). `kettle-core/CLAUDE.md`'s two-viewport description is **correct**; the disk is wrong. |
| **G2** | Contract ownership | **concur-with-correction** | kettle-core owns all four: HTTP API (`API.md`), desk schema, UI-copy catalog, bundled-core provenance. Correction: ownership is **documented but unenforced across the repo line** — no workflow checks out two repos. Do not call these "contracts" in the plan without that adjective. |
| **G3** | Safe to automate now | **concur-with-qualification** | Only the **green tier**: cross-repo *drift detection* in CI, `kettle doctor` extension, report-only sweeps. **Not** safe: unattended cross-repo commits; any unattended edit to the five run-critical files; anything binding port 4242. Automate *detecting* divergence, never *writing* the synced artifact. |
| **G4** | Coordination substrate | **concur-with-qualification** | Per-occasion `.coordination/` in the owning repo — **not** the fleet `majordomo-inbox/`, which is for escalations above a lane, not a product's design record. Qualification: whether this directory is committed, gitignored, or deleted at closure is **unresolved and is a patron gate** (it is currently untracked and not ignored). |
| **G5** | First authorized tranche | **concur-with-qualification** | **Tranche 0 (no code):** reconcile `family.md`'s stale state column; resolve the two stubs; name a design-token owner. **Tranche 1 (green automation):** CI drift check for `ui-copy` + compatibility manifests; doctor extension. Everything else waits. |
| **G6** *(proposed addition)* | Who owns the design-token vocabulary? | **abstain-insufficient-evidence** | It is being created **right now in two repos simultaneously** as untracked files, with no entry in `family.md`. I can see the drift risk but not the intent. Patron or peer input needed. |
| **G7** *(proposed addition)* | Public `ROADMAP.md` vs private `.local/roadmap.md` precedence | **abstain — patron's call** | They lead differently (installation/security vs signature craft). An automation plan built on the wrong one builds the wrong machinery. Not a strand's call. |

## Expected disagreements

1. **Against the charge's framing.** I ballot that the family is 4, not 7, and that
   two stubs should be *removed*. A peer reading the patron's "7 repos" as authoritative
   will tally G1 differently. My evidence is the canon plus `ls`; I will change my vote
   on evidence that the stubs were created deliberately to reverse `open-questions.md`.
2. **Against parallelization.** I expect at least one peer to propose agent-per-repo
   fan-out. I consider that contrary to `agent-surfaces.md`'s signature rule and will
   dissent unless the patron retires that rule.
3. **Verification-first vs generation-first automation.** I expect pushback that
   drift-*detection* is too modest for "accelerate." I hold that a generator committing
   into a second repo turns one bad change into two bad repos before a human sees either.

## Human gates (not for majority)

1. Delete, populate, or justify `kettle-cli/` and `kettle-mcp/`.
2. Commit / ignore / delete this `.coordination/` record at closure.
3. Roadmap precedence (G7); design-token ownership (G6).
4. Any code, any cross-repo edit, any commit or push, any always-on automation.

## Walls (pre-declared, majority cannot breach)

No unattended writes to `server.py`, `static/index.html`, `kettle_main.py`,
`projects.json`, `settings.json` · nothing binds or signals **port 4242** · no push
credentials across a repo boundary in this tranche · no new always-on job without
separate explicit authorization.

## Verified-evidence table

| Claim | Method | Result |
|---|---|---|
| 4 of 7 trees are git repos | `git -C <r> rev-list --count HEAD` | kettle 13 · core 80 · desktop 29 · vscode 6; cli/mcp/obsidian: no `.git` |
| `kettle-cli`, `kettle-mcp` empty | `ls -la`, `du -sh` | 0 B each, created 2026-07-25 |
| Canon rules against CLI/MCP repos | read `family.md`, `open-questions.md` | "Not separate repos (by default)"; both marked settled |
| No cross-repo CI | read all 4 workflow files | vscode CI = `npm ci` · `npm test` · `npm run package`; single checkout |
| ui-copy resolves by sibling path | read `sync-ui-copy.mjs` | env → `../kettle-core/static/ui-copy.js` → legacy fallbacks |
| Snapshot currently in sync | ran `sync-ui-copy.mjs` | "up to date"; no file modified (see disclosure) |
| Manifest is an assertion | read `kettle-vscode/kettle-compatibility.json` | `{"api_versions":[0],"desk_schema_versions":[0],"allow_legacy_identity":false}` |
| Design tokens spanning repos | `git status` both repos | untracked in core **and** vscode |
| core dirty incl. run-critical file | `git status --porcelain` | 9 paths, incl. `static/index.html` |
| `family.md` state column stale | compare doc to tree | claims core "largely setsweep-core"; actually 80 commits / 134 files |

**Peer-verified, not independently reproduced:** none — no peer artifacts existed at
filing time. **From prose (authority, not implementation evidence):** all `family.md` /
`open-questions.md` / roadmap claims. **Inference:** that the stubs are premature rather
than a deliberate reversal — stated as inference, not fact.

## Disclosure

I ran `sync-ui-copy.mjs`, a sibling-repo script capable of writing `src/uiCopy.ts`,
while my own protocol ballot declared sibling repos read-only. It wrote nothing
(verified post-hoc via `git status`), but it was a wall-adjacent action and I record it
rather than omit it. Detail in the automation-safety counsel.
