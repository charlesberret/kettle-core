# Protocol ballot — architect-codex

Occasion: `kettle-multirepo-automation-2026-07-30`  
Sender: `architect-codex`  
Role: `architect` co-leader  
Mode: `ACTIVE_PARTICIPANT`  
Phase: 0 (protocol)  
Filed: 2026-07-30

## Adopted configuration

- Canonical coordination directory:
  `/Users/charles/cloud/git-projects/kettle-core/.coordination/kettle-multirepo-automation-2026-07-30`
- Canonical project root: `/Users/charles/cloud/git-projects/kettle-core`
- Additional read roots: the six sibling Kettle trees under
  `/Users/charles/cloud/git-projects/`
- Declared strands, in order: `architect-opus`, `architect-codex`,
  `architect-grok`
- N = 3; majority = 2-of-3; quorum policy = `full-N`
- Specialist seats: repo topology; contract/API; automation safety; roadmap
  sequencing
- Audit depth: `bounded`; watcher mode: `none`
- First position deadline: 20 minutes from confirmed join
- Commit policy: no commits; push policy: no push

Patron goal, adopted from the existing protocol:

> One ratified multi-repo coordination plan for Kettle — naming, for each of the
> 7 repos, its role, its contract with core, and what may be automated —
> sufficient to authorize the first tranche of automation work.

Done condition: one joint decision memo with per-gate tallies, plus the patron's
answers to the human gates. No code is authorized in this sitting.

## Article ballots

| # | Article | Ballot | Operative note |
|---|---|---|---|
| 1 | Identity and sender id | **concur** | I am `architect-codex`, one of three co-leaders in the shared `architect` role. |
| 2 | Canonical coordination path | **concur** | Absolute path above confirmed by inventory. |
| 3 | Write discipline | **concur** | I will write only `architect-codex` sender-scoped files. Only the deterministic scribe may write decision or closure files. |
| 4 | N, majority, quorum, silence | **concur** | N = 3, majority = 2-of-3, full-N. Silence is absence, never concurrence. No present-count arbitration is authorized. |
| 5 | Scribe selection | **concur** | Earliest protocol mtime, lexical id as tie-break. `architect-opus` currently holds the pen by verified mtime; this is not a super-vote. |
| 6 | Required phases | **concur** | Protocol → four counsel seats → position → reconcile → decision. Late evidence belongs in an addendum. |
| 7 | Watcher | **concur** | `none`; no heartbeat, poller, cron, or other always-on process. |
| 8 | Evidence and honesty rail | **concur** | Claims will be marked verified this session, peer-verified, from prose, or inference. Narrow checks will not be inflated into general proof. |
| 9 | Gate list and human gates | **concur-with-qualification** | G1 topology; G2 contract ownership; G3 safe automation; G4 coordination substrate; G5 first tranche. G6 design-token ownership and G7 roadmap precedence are valid proposed additions awaiting full ballots. Human gates are topology reversal/stub disposition, coordination-record disposition, design-token ownership, roadmap precedence, code or cross-repo edits, commits/pushes, and any always-on automation. |

## Qualifications and walls

1. The charge's phrase “7 repos” is a proposition to verify, not runtime proof.
   Gate G1 must establish topology before G3 or G5 becomes operative.
2. No writes outside this occasion directory; all sibling repositories remain
   read-only.
3. No commits, pushes, branches, publication, or external messages.
4. No edits to `server.py`, `static/index.html`, `kettle_main.py`,
   `projects.json`, or `settings.json`; no process may bind, probe, or signal
   port 4242.
5. No initialization or population of `kettle-cli`, `kettle-mcp`, or any other
   stub; no unattended cross-repo writes; no always-on automation.
6. Recommendations do not authorize implementation. Any ambiguity in human
   replies satisfies only the gate explicitly answered.

## Scribe request

Record this strand as present for Phase 0, preserve full-N semantics, and keep
all decision language provisional until every declared strand has filed both a
position and a reconcile.
