---
id: 17
title: Docs for strangers
repo: setsweep-core
touches: [README.md, INSTALL.md, API.md, kits/README.md, CLAUDE.md, ARCHITECTURE.md (new), _Status.md]
risk: normal
depends-on: [10, 11]
status: done
---

## Context

The docs describe a smaller, older, more personal project than the one that exists. The
architecture document a newcomer needs (`.local/DESIGN.md`) is gitignored, yet tracked
docs cite it — dangling references in any clone. Vocabulary that gates comprehension
("sitting", "ledger", "desk") is used everywhere and defined nowhere. The drift list is
concrete: `kits/README.md` says "four kinds" then lists five; `README.md` documents a
`setsweep sweep-status|close` command where the real one is `sweep-close`; `INSTALL.md`
shows 5 of 14 subcommands; `CLAUDE.md` lists 6 of 8 test files; the
durable-vs-runtime desk split (`.setsweep/runtime/` must be excluded from file sync)
lives only in a `server.py` docstring while README describes pre-split paths;
`kits/frameworks/egress.md`'s header template omits the `approval` kind its own table
includes; the lineage subsystem — a headline feature — has no public documentation at
all; every cross-repo pointer is a Charles-local path; no doc gives a clone URL.

## Task

1. **ARCHITECTURE.md** (public, root): distill from `.local/DESIGN.md` — the desk
   model (desk-is-files, viewports over a local core), the §5 invariants verbatim, tool
   tiers, the durable-vs-runtime split with the sync-exclusion rule, lineage
   attribution (agent/user/unattributed, never guessed), the founding state machine.
   Not a history document — the current shape, ~150 lines.
2. **Glossary** in README: sitting, desk, patron, curator, founding, kit, brief,
   approve-vs-sweep, egress, ledger, viewport. One crisp sentence each.
3. **Quickstart**: the ten-minute path (install → `setsweep add` → founding interview →
   edit proposal → approve → first sitting → sweep), with 2–3 screenshots.
4. **CLI reference**: generate from `cli.py`'s argparse table (the help strings already
   exist); all 14 subcommands.
5. **Fix the drift list** above, item by item; point `kits/README.md`'s dead DESIGN
   reference at ARCHITECTURE.md.
6. **De-personalize the doc layer** (code layer is brief 10): clone URLs instead of
   `~/cloud/git-projects/...` pointers; `_Status.md` reviewed for shipped-repo appropriateness.

## Constraints

- ARCHITECTURE.md summarizes DESIGN.md; it must not contradict it. Where the dossier
  records patron rulings (founding reveal order, intake design), the public doc states
  the behavior without the biographical narrative.
- Vocabulary stays — the product's language is a feature — but every term earns a
  definition at first public contact (the interview-wording lesson, applied to docs).

## Done when

- A fresh clone contains no reference to a gitignored or Charles-local path (grep for
  `.local/DESIGN`, `~/cloud/git-projects/`, `~/cloud/sync/` across tracked docs).
- The quickstart has been executed literally, command by command, on a clean checkout
  by the agent running this brief — every command as written, every claimed output
  observed.
- Every CLI subcommand appears in the reference with its real name.

## Verify

The literal quickstart run; the grep sweep; `kits/README.md` and `README.md` claims
spot-checked against `kits/` contents and `cli.py`.

## Afterwards

`status: done`; RELEASE.md's alpha gate (quickstart exists) ticks; brief 18's doctor
gains a docs pointer to print when checks fail.
