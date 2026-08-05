# Counsel — automation-safety seat (architect-opus)

Speaking only from the safety lens. The charge is to *accelerate development through
automation*; this seat's job is to name what automation must not be allowed to touch,
and to be the one voice in the room arguing against its own sitting's enthusiasm.

## Self-report first (honesty rail, and it counts against me)

During evidence-gathering I executed `node kettle-vscode/scripts/sync-ui-copy.mjs` —
a script in a sibling repo that **is capable of writing** `src/uiCopy.ts` there. It
reported "up to date" and wrote nothing (verified after the fact:
`git -C kettle-vscode status --porcelain` shows only two pre-existing untracked theme
files, no modification to `uiCopy.ts`). No harm occurred, but this **brushed my own
declared Wall 1** ("sibling repos are read-only") in my protocol ballot. I record it
rather than omit it. The lesson generalizes directly to the charge: I reached for a
convenient script to answer a question and did not first check whether it mutates. An
automation harness will do that a thousand times an hour and will not notice.

## The fence that already exists, and why it is load-bearing

`kettle-core/CLAUDE.md` names five run-critical files — `server.py`,
`static/index.html`, `kettle_main.py`, `projects.json`, `settings.json` — and says
plainly: *"Handoff only — never edit from within Kettle itself."* It also says **never
bind or signal port 4242**, the live window's port.

This is not bureaucratic. Kettle is a tool that reviews code **while the user is
sitting in it**. An agent that edits `static/index.html` badly blanks the window of
the instrument being used to review the edit. The failure mode is self-erasing: the
surface that would have shown you the error is the surface you broke. Automation
raises the frequency of exactly this class of change.

Verified: `kettle-core` is dirty on `main` right now — 9 modified/untracked paths,
including `runtime.py`, `gitmap.py`, `API.md`, **and `static/index.html`** (one of the
five). Any automation designed this sitting would land in a tree with uncommitted work
in a run-critical file.

## Risk tiering for the proposed automation surface

Borrowing the fleet charter's green/yellow/red, which the patron already operates by:

| Tier | Automation | Verdict |
|---|---|---|
| **Green** | Cross-repo *drift detection* in CI (checkout core beside consumer, assert `ui-copy` snapshot and compatibility manifests agree); doctor extensions; report-only sweeps | Safe. Reversible, additive, no run-critical file, fails loud in CI where a human already looks. |
| **Yellow** | Release/version coordination; a generated topology doc; pre-commit hooks in the four repos | Acceptable **with** a human in the merge path. Note `kettle/scripts/install-git-hooks.sh` and per-repo `git-hooks/` already exist — extend that pattern, don't invent a second one. |
| **Red** | Anything that commits or pushes across a repo boundary; anything that edits the five run-critical files unattended; any new always-on cron/launchd/watcher; anything binding 4242 | **Propose only.** The fleet charter puts re-enabling an autonomous headless job at red explicitly. |

## The specific thing I want on the record

The charge says "automated to accelerate development." The strongest safety argument I
can make is that **for this codebase, verification automation accelerates more than
generation automation** — because the bottleneck is not typing, it is *confidence that
a core change did not silently break two consumers*. Today that confidence is produced
by one human running scripts in sibling checkouts. Automating the *check* removes the
bottleneck and adds no new failure mode. Automating the *write* removes the bottleneck
and adds a new class of failure that lands in a repo nobody was looking at.

## Ballot from this seat

- **G3 — concur with qualification**: safe to automate now = the green tier above,
  scoped to CI and doctor. Explicitly **not** safe: unattended cross-repo commits, and
  anything inside the five run-critical files.
- **G5 — qualified**: the first tranche must be *observation before action*.

## Walls from this seat (majority cannot breach)

1. No unattended write to `server.py`, `static/index.html`, `kettle_main.py`,
   `projects.json`, `settings.json`.
2. No process binds, probes, or signals port **4242**.
3. No automation gets push credentials to a second repo in this tranche.
4. Nothing is stood up as always-on (cron/launchd/hook-on-schedule) without an explicit
   separate patron authorization — recommending it here does not authorize it.
