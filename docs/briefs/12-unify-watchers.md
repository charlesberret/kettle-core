---
id: 12
title: Unify the folder-watchers
repo: setsweep-core
touches: [setsweep_watch.py, test_watch.py, crontab (fleet), ~/cloud/sync/code/bin/setsweep-watch (retire)]
risk: normal
depends-on: [03]
status: open
---

## Context

Two implementations share one name. The repo ships `setsweep_watch.py` (the packaged
`setsweep-watch` console script, state under `~/.cache/setsweep/`), but cron actually
runs `~/cloud/sync/code/bin/setsweep-watch` every 15 minutes — an older fork with an extra
PICKUP pass and state under `~/.cache/claude/`. Fixes to the repo version never reach
production and vice versa; their seen-state files differ, so a naive cutover would
re-curate previously seen intake items and spam drafts. The repo version also resolves
the registry and settings differently from the server (`DESK_PROJECTS` else
`SCRIPT_DIR/projects.json`, `SCRIPT_DIR/settings.json` — setsweep_watch.py:36, 91–95),
skipping the user-registry path the server prefers, and is Claude-only (hardcoded
binary at :40, hand-built argv at :203–208) despite the provider-agnostic runtime.
`intake_pass` — the code that mutates live queues on a timer — has no test.

## Task

1. Diff the fork against the repo version; port the PICKUP pass (or consciously retire
   it, in writing) into `setsweep_watch.py`.
2. Converge resolution on the server's: import and use `server.resolve_projects_path()`
   and the same settings path (the watcher already imports sibling modules; `server`
   import is side-effect-free by design).
3. Make agent-firing provider-aware via `build_turn_cmd`/`runtime.build_argv` (depends
   on brief 03's pattern).
4. Write the seen-state migration: read the fork's state file, translate, write the
   packaged path; idempotent; refuses to run twice.
5. Cut cron over to the venv console script; delete or archive the bin fork; update
   `routines.md` in the System repo (the canonical cron narrative) — that update is
   part of this brief, not optional.
6. Tests for `intake_pass` with a stub curator (the `test_server.py` capture pattern):
   new file → one curate spawn → entry normalized to pending.

## Constraints

- The watcher writes a healthbeacon (invariant 6) — keep it beating through the
  migration; a silent gap looks like a dead watcher on the dashboard.
- Never re-curate seen items: migration correctness is the whole risk here. Test it
  against a copy of the real state file before cutover.

## Done when

- One watcher exists; cron runs the packaged script; the fork is gone or archived.
- A synthetic new intake file produces exactly one curate spawn with provider-correct
  argv; previously seen items produce zero.
- `test_watch.py` covers intake_pass; the healthbeacon shows an unbroken cadence.

## Verify

Run the watcher once by hand with a scratch project and stub curator; check the beacon;
run the suite.

## Afterwards

`status: done`; ops-log entry in the System repo for the cutover; `_Status.md`
healthbeacon line updated if the path changed.
