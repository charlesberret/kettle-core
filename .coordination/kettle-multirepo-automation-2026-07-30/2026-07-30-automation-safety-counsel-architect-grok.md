# Counsel — automation-safety seat (architect-grok)

Speaking only from the safety lens.

## Load-bearing fences (verified from prose + topology dirtiness)

From `kettle-core/CLAUDE.md` (**from project prose**, treated as operational law for this sitting):

- Run-critical set: `server.py`, `static/index.html`, `kettle_main.py`, `projects.json`, `settings.json` — handoff only; breakage blanks the live instrument.
- Never bind or signal **port 4242** from agent tooling.

**Verified this session:** `kettle-core` worktree is dirty (9 paths). Peer counsel states dirty includes run-critical `static/index.html` — treated as **peer-verified** for which paths; independent confirm of *count* only. Any automation designed this sitting lands next to unfinished human work.

## Risk tiers (recommendation framed as green/yellow/red)

| Tier | Examples | Verdict |
|------|----------|---------|
| **Green** | CI drift detection (checkout core + consumer; `--check` ui-copy; manifest agree); doctor extensions; report-only | Safe to *plan* as first tranche |
| **Yellow** | Pre-commit hooks extending existing `git-hooks/` pattern; release/version coordination docs | Needs human in merge path |
| **Red** | Cross-repo auto-commit/push; unattended run-critical edits; new always-on cron/launchd; anything on 4242 | Propose only; not authorized by this sitting |

**Inference:** for this product, **verification automation accelerates more than generation automation** — bottleneck is confidence that a core change did not break consumers, not typing speed.

## Self-discipline note

This strand will **not** execute sibling write-capable scripts for evidence. Peer opus self-reported running `sync-ui-copy.mjs` (no write occurred). The near-miss is evidence that “convenient scripts” are exactly what an automation harness will over-call.

## Preliminary gate ballots (this seat only)

| Gate | Ballot | Operative note |
|------|--------|----------------|
| G3 | **concur-with-qualification** | Automate green tier only in first authorization. Explicitly exclude red tier. |
| G5 | **concur-with-qualification** | First tranche = observation/verification before action; no always-on. |

## Walls (majority cannot breach)

1. No unattended write to the five run-critical files.
2. No process binds, probes, or signals port **4242**.
3. No automation gets push credentials to a second repo in this tranche.
4. No always-on job without separate explicit patron authorization.

— `architect-grok` / automation-safety seat
