---
id: 04
title: Externalize the prompts
repo: setsweep-core
touches: [server.py, kits/prompts/ (new), test_server.py, test_kits.py]
risk: run-critical
depends-on: [01]
status: done
---

## Context

About 460 lines of prompt constants (server.py:233–691 — INTERVIEW_ROLE, PROPOSE_PROMPT,
FOUND_PROMPT, BOOTSTRAP_PROMPT, SWEEP_PROMPT at ~8,200 chars, ACCRUE, QUEUE_SCHEMA,
verbosity blocks) live inline in a file CLAUDE.md marks handoff-only run-critical — so
tuning a prompt carries app-outage risk, which is exactly backwards: prompts are the most
frequently tuned surface in the product. Meanwhile sibling prompt material already loads
from files (`kits/_base.md`, `kits/frameworks/*.md`) via the graceful-fallback pattern at
server.py:2082–2092. No test formats any constant, so a stray `{` in a prompt edit fails
only at runtime. Doctrine is also duplicated: the brief standard lives in three places
(`_base.md`, QUEUE_SCHEMA, `frameworks/brief.md`), egress discipline in four.

## Task

1. Create `kits/prompts/<name>.md`, one file per constant, contents moved verbatim
   (keep `{placeholders}`).
2. In `server.py`, replace each constant with a loader (same pattern as the frameworks
   loader): read the file once at import, fall back to a short built-in emergency prompt
   plus a logged warning if the file is missing — the server must never fail to boot
   over a prompt file.
3. Add the smoke test that closes the brace-breakage class forever: for every prompt
   file, `.format()` it with dummy values for every placeholder it declares.
4. While moving, collapse the duplicated doctrine: the brief standard's single home is
   `kits/frameworks/brief.md` (QUEUE_SCHEMA references it in one line); egress
   discipline's single home is `kits/frameworks/egress.md`.

## Constraints

- Verbatim moves first, editing after — the diff must show relocation, not rewriting,
  or review becomes impossible.
- Prompt files are user-visible product surface now: they join the "safe to edit"
  list in CLAUDE.md, and that list must be updated in this change.
- Coordinate with brief 10 (de-personalization) — do the move first, genericize second,
  as two commits, so each is reviewable.

## Done when

- `server.py` shrinks by roughly 400+ lines; `grep -c "PROMPT = (" server.py` returns 0.
- The format-smoke test exists and passes; deleting a `{` from any prompt file makes it
  fail.
- Boot-with-missing-prompt-file test: server starts, logs the fallback, `/api/ping` OK.

## Verify

Full suite; boot the server on an ephemeral port; run one stub-curator founding and one
stub sweep (existing harness) confirming the assembled prompts still carry the moved
content (assert a sentinel phrase per file).

## Afterwards

`status: done`; update CLAUDE.md's safe-edit list and `kits/README.md` (new `prompts/`
dir); brief 10 becomes unblocked for the generic-content pass.
