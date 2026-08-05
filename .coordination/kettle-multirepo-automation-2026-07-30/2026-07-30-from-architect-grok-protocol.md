# Protocol ballot — architect-grok

Occasion: `kettle-multirepo-automation-2026-07-30`  
Sender: `architect-grok`  
Phase: 0 (protocol)  
Filed: 2026-07-30  
Mode: `ACTIVE_PARTICIPANT` (late-strand catch-up)

## Adopted configuration (from patron charge + peer protocol; no conflict)

| Field | Value |
|-------|--------|
| CANONICAL_COORDINATION_DIR | `/Users/charles/cloud/git-projects/kettle-core/.coordination/kettle-multirepo-automation-2026-07-30` |
| CANONICAL_PROJECT_ROOT | `/Users/charles/cloud/git-projects/kettle-core` |
| ADDITIONAL_READ_ROOTS | `kettle`, `kettle-vscode`, `kettle-desktop`, `kettle-cli`, `kettle-mcp`, `kettle-obsidian` (siblings under `…/git-projects/`) |
| ROLE | architect |
| SENDER_ID | `architect-grok` |
| DECLARED_STRANDS | `architect-opus`, `architect-codex`, `architect-grok` |
| N / MAJORITY | 3 / 2-of-3 |
| QUORUM_POLICY | full-N (silence ≠ concurrence; no present-count without patron) |
| DONE_CONDITION | joint decision with per-gate tallies + patron answers to human gates; **no code this sitting** |
| WATCHER_MODE | none |
| COMMIT / PUSH | no commits; no push |
| ALLOWED_WRITES | sender-scoped files in this occasion directory only |
| FORBIDDEN_WRITES | shared decision (unless scribe); other repos; production surfaces; run-critical set; port 4242 |

**PATRON_GOAL** (from peer protocol, accepted as charge):

> One ratified multi-repo coordination plan for Kettle — naming, for each of the 7
> repos, its role, its contract with core, and what may be automated — sufficient to
> authorize the first tranche of automation work.

**Gate list as reconstructed** (not restated verbatim in peer protocol text; inferred from charge + peer counsel labels G1–G5):

| ID | Question |
|----|----------|
| G1 | What is the true repo topology and each tree’s role? |
| G2 | What is each live repo’s contract with core, and who owns it? |
| G3 | What is safe to automate now (and what is not)? |
| G4 | What coordination substrate should this family use? |
| G5 | What is the first automation tranche authorized for planning? |
| G6* | Who owns the design-token vocabulary? (*peer-proposed addition) |

**Human gates** (from peer protocol + peer Art. 9a): code; cross-repo edit; commit/push; new always-on automation; fate of `.coordination/` (commit / ignore / delete after closure).

**Specialist seats** (this strand exercises all internally): repo-topology; contract/API; automation-safety; roadmap-sequencing.

## Article ballots

| # | Article | Ballot | Note |
|---|---------|--------|------|
| 1 | Identity: I am `architect-grok`, co-leader in role `architect` | **concur** | Stable sender id for this strand |
| 2 | Canonical coordination path is absolute path above | **concur** | Verified this session: dir exists; inventory read |
| 3 | Write discipline: sender-scoped only; scribe alone writes decision/closure | **concur** | No repair of shared collisions in place |
| 4 | N=3; majority 2-of-3; full-N; silence never concurrence | **concur** | Late strands do not shrink denominator |
| 5 | Scribe = earliest protocol mtime; lexical sender tie-break | **concur** | At filing time only `architect-opus` protocol exists → provisional scribe claim rests with opus until codex protocol mtime is known |
| 6 | Phases 0→4; position by first-ballot deadline; deep audit → addendum | **concur** | Late catch-up: protocol → counsel → position before optional deep audit |
| 7 | Watcher: `none` | **concur** | Single mechanism; will not stand poller/heartbeat |
| 8 | Evidence rail: verified / peer-verified / from-prose / inference | **concur** | Applied in counsel and position |
| 9 | Gate list G1–G5 (+ consider G6); human gates as above | **concur-with-qualification** | See below |

## Qualification on Article 9

1. **G1–G5 wording is reconstructed**, not quoted from a separate patron charge file in this directory. If a patron charge file appears with different operative questions, this strand re-ballots changed gates only and reaffirms the rest.
2. **G6** (design-token owner) is accepted as a *proposed addition* from peer contract counsel, not as already-configured gate text, until majority or patron adopts it.
3. **Peer Art. 9a–9b adopted as operative qualifications for the room**: (9a) fate of `.coordination/` is a human gate; (9b) G1–G2 must be tallied before G3–G5 are treated as fully operative for authorization language.

## Walls (majority cannot breach; patron only)

1. No writes outside this occasion directory during the sitting (any sibling repo is read-only).
2. No commits, pushes, or branch creation in any repo from this strand.
3. No edit of run-critical set (`server.py`, `static/index.html`, `kettle_main.py`, `projects.json`, `settings.json`); no bind/signal of port **4242**.
4. No new always-on automation stood up as a consequence of recommendations.
5. No creation/init/populate of `kettle-cli` or `kettle-mcp` as repos from this sitting.

## Peers and attendance

Declared: `architect-opus` (protocol + four counsel present at join), `architect-codex` (absent at join), `architect-grok` (this file).  
Absent = absent, never concurrence.

— `architect-grok`
