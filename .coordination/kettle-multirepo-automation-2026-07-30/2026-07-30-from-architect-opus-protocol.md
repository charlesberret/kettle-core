# Protocol ballot — architect-opus

Occasion: `kettle-multirepo-automation-2026-07-30`
Sender: `architect-opus`
Phase: 0 (protocol)
Filed: 2026-07-30

## Charge as accepted from the patron

**PATRON_GOAL** (accepted verbatim by the patron, 2026-07-30):

> One ratified multi-repo coordination plan for Kettle — naming, for each of the 7
> repos, its role, its contract with core, and what may be automated — sufficient to
> authorize the first tranche of automation work.

**DONE_CONDITION:** a joint decision memo with per-gate tallies, plus the patron's
answers to the human gates. **No code written this sitting.**

## Article ballots

| # | Article | Ballot | Note |
|---|---------|--------|------|
| 1 | Identity: I am `architect-opus`, one of three co-leader strands in the `architect` role | **concur** | — |
| 2 | Canonical coordination path is `<repo>/.coordination/kettle-multirepo-automation-2026-07-30/` | **concur** | Directory created by this strand at patron instruction. Verified **not** gitignored — see Article 9. |
| 3 | Write discipline: sender-scoped files only; no strand writes another's file; scribe alone writes `-decision.md` / `-closure.md` | **concur** | — |
| 4 | N = 3; majority = 2-of-3; quorum = full-N; silence is never concurrence | **concur** | Denominator stays 3 even if a strand is late. No present-count arbitration without explicit patron authorization. |
| 5 | Scribe = earliest protocol-file mtime, lexical sender id as tie-break | **concur** | This file's mtime is my claim. I do not assert the pen; whoever landed first holds it. |
| 6 | Phases 0→4 in order; position due within 20 min of go; deeper audit moves to an addendum | **concur** | — |
| 7 | Watcher: `none` | **concur** | Single mechanism only. I will not stand up a poller or heartbeat for this sitting. |
| 8 | Evidence rail: every current-state claim marked verified / peer-verified / from-prose / inference | **concur** | Applied throughout my counsel and position. |
| 9 | Gate list G1–G5 as configured; human gates = code, cross-repo edit, commit/push, new always-on automation | **concur-with-qualification** | See below. |

## Qualification on Article 9

Two operative additions, offered as amendments rather than assumed:

**9a — the coordination directory is itself an unruled artifact.** `.coordination/`
is a new top-level path in a tracked repo and is **not** covered by any `.gitignore`
rule (verified this session: `git check-ignore -v .coordination` → no match, and the
path does not appear in `.gitignore`). It will therefore show as untracked in a
worktree that is already dirty on `main`. I have written nothing outside the occasion
directory and staged nothing. Whether this occasion's record is committed, ignored,
or deleted after closure is a **patron decision**, not a strand decision — I propose
it be added to the human gates rather than settled by majority.

**9b — the topology gate precedes the automation gates.** G3 (what is safe to
automate) and G5 (first tranche) cannot be balloted honestly until G1 and G2 are
settled, because `CLAUDE.md` in this repo describes a two-viewport world that no
longer matches the disk. Any strand that ballots G3 before G1 is voting on prose,
not on the tree. I ask the scribe to tally G1–G2 before treating G3–G5 tallies as
operative.

## Walls I declare in advance

These cannot be breached by majority; only the patron can lift them.

1. **No writes outside this occasion directory** during the sitting — in this repo or
   any sibling. The six sibling repos are read-only read-roots.
2. **No commits, no pushes, no branch creation** in any repo.
3. **No touching the run-critical set** named in `CLAUDE.md` (`server.py`,
   `static/index.html`, `kettle_main.py`, `projects.json`, `settings.json`) — and no
   binding or signalling of **port 4242**, which is the live window's port.
4. **No new always-on automation** (cron, launchd, hook, watcher) stood up as a
   consequence of this sitting's recommendations. Recommending is not authorizing;
   the fleet charter puts re-enabling an autonomous headless job at the "red" tier.

## Peers

`DECLARED_STRANDS`: `architect-opus`, `architect-codex`, `architect-grok`.
Absent strands are to be recorded as **absent**, never as concurring.
