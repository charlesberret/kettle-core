---
name: setsweep-sweep
description: >-
  Run a Setsweep desk sweep efficiently: mechanical CLOSE via sweepkit / CLI,
  then ACCRUE familiarity and restock briefs. Use when closing a Setsweep sitting,
  restocking the queue, or updating FAMILIARITY.md / MEMORY.md after review.
---

# Setsweep sweep

You are closing a Setsweep sitting. Prefer scripts over ceremony.

## Order of operations

1. **Status** — `setsweep sweep-status <project>` (or trust CLOSE KIT STATUS in the prompt).
2. **Quiet CLOSE** — if `can_mechanical_close`, run `setsweep sweep-close <project>` (or rely on the server, which already did). Do **not** re-diff, hand-`mv` archives, or re-stage inbox drafts.
3. **Judgment CLOSE** — only when `needs_judgment`: apply comments/ledger, ripple mechanical fixes, flag judgment. Then archive with `setsweep sweep-archive <project>` (or `--approved-only` for inbox).
4. **ACCRUE** — read `FAMILIARITY.md` + kits frameworks; restock from `review-program.md` with honest briefs; deepen familiarity; touch `MEMORY.md` only for standing prefs.
5. **Log** — thin session log (one line per entry). Point at domain memos; do not restate them.

## Do not

- Re-run `diff -u` when precomputed diffs / close-kit status are present.
- Write thin process notes into MEMORY.
- Dump sitting transcripts into FAMILIARITY.
- Transmit inbox outbound mail — staging only.

## Frameworks

- `kits/frameworks/brief.md` — brief standard
- `kits/frameworks/familiarity.md` — familiarity map shape
