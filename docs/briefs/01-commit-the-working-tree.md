---
id: 01
title: Commit the working tree
repo: setsweep-core
touches: [git only — no code changes]
risk: normal
depends-on: []
status: open
---

## Context

Branch `codex/shore-up-system` carries roughly 4,000 uncommitted inserted lines
(~4,700 changed), including ~870 changed lines in `server.py` and ~1,260 in
`static/index.html` — the two files whose
breakage takes the app offline. The entire egress layer is untracked (`egress.py`,
`test_egress.py`, `kits/frameworks/egress.md`) even though tracked code depends on it:
`cli.py` imports `egress` and `pyproject.toml` lists it in `py-modules`, so a commit of
the branch that misses the untracked files produces a tree that fails at import. Also
untracked: a 92-byte empty `package-lock.json` at the repo root — npm cruft in a
stdlib-only Python project. A `git clean -fd` or a lost working tree today erases the
newest layer of the product.

## Task

1. Read `git status` and `git diff --stat` and group the changes into coherent commits
   (suggested slices: egress layer + its tests; kit/interview wording; server prompts and
   hardening; frontend; docs). Perfection is not the bar — durability is.
2. `git add` the untracked egress files and any other untracked file that tracked code
   references. Delete `package-lock.json` (root) unless something references it (verify
   with grep first).
3. Commit the slices with honest messages. Push the branch to the remote.
4. Confirm whether `codex/shore-up-system` should merge to `main` — if the tests are
   green and the app boots, propose the merge to the patron rather than deciding alone.

## Constraints

- Commit only; do not rewrite, rebase, or "clean up" code while committing.
- Do not touch the live server or port 4242.
- If any hunk looks like an experiment rather than intended work, ask the patron instead
  of guessing — this tree carries weeks of in-flight decisions.

## Done when

- `git status` is clean (no modified, no untracked files that code references).
- A fresh clone of the pushed branch passes `python3 -m pytest -q` (224+ tests).
- `python3 -c "import cli, server, egress, sweepkit, curator, kits, runtime, lineage"`
  succeeds in the fresh clone.

## Verify

Clone to a temp dir, install editable in a scratch venv, run the suite, boot the server
on an ephemeral port (`start_server(0)` via a short script or the existing tests), GET
`/` and `/api/ping`.

## Afterwards

Update `_Status.md`'s Status paragraph (branch state), set this brief's `status: done`,
and note in the commit message that briefs 03–18 assume this baseline.
