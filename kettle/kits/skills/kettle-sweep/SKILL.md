---
name: kettle-sweep
description: >-
  Run a Kettle desk sweep efficiently: mechanical CLOSE via sweepkit / CLI,
  then ACCRUE familiarity and restock briefs. Use when closing a Kettle sitting,
  restocking the queue, or updating FAMILIARITY.md / MEMORY.md after review.
---

# Kettle sweep

You are closing a Kettle sitting. Prefer scripts over ceremony.

## Order of operations

1. **Status** — `kettle sweep-status <project>` (or trust CLOSE KIT STATUS in the prompt).
2. **Quiet CLOSE** — if `can_mechanical_close`, run `kettle sweep-close <project>` (or rely on the server, which already did). Do **not** re-diff, hand-`mv` archives, or re-stage inbox drafts. Mechanical close also stages a `kind: approval` egress memo for peer agents when the sitting had approvals/pending gates.
3. **Judgment CLOSE** — only when `needs_judgment`: apply comments/ledger, ripple mechanical fixes, flag judgment. Then archive with `kettle sweep-archive <project>` (or `--approved-only` for inbox). **Before or after archive**, publish peer-facing approvals: `kettle egress <project> --kind approval --topic sitting-approvals` listing approved paths **and** remaining pending blocks (or rely on the close kit helper if the server already published).
4. **ACCRUE** — read `FAMILIARITY.md` + kits frameworks; restock from `review-program.md` with honest briefs; deepen familiarity; touch `MEMORY.md` only for standing prefs. When a next-batch file is a gate for other agents, say so in the brief and fill `unblocks`.
5. **Fleet scan** — light re-check of AGENTS.md / CLAUDE.md / fleet handoff paths if present; correct the peer map only when evidence changed.
6. **Sweep actions** — honor the desk's `SWEEP-ACTIONS.md` (in the desk directory named in
   the prompt — do not assume `.kettle/`; an unmigrated desk keeps its legacy directory):
   git, outbound stage, egress for dispatch, plaintext sitting logs, sheets, reporting.
   Never transmit mail/Slack/webhooks from the desk.
7. **Egress** — for launch directives, escalations, handoffs, domain memos, or approval publication: `kettle egress <project> --kind … --topic …`. Also append `LAUNCH DIRECTIVE:` to `runtime/sweep.log` for launch rulings.
8. **Log** — thin session log (one line per entry). Point at domain memos / egress paths; do not restate them.

## Do not

- Re-run `diff -u` when precomputed diffs / close-kit status are present.
- Write thin process notes into MEMORY.
- Dump sitting transcripts into FAMILIARITY.
- Transmit inbox outbound mail — staging only (`<root>/outbox`).
- Confuse desk egress (the desk's `outbound/` folder) with inbox mail outbox.
- Execute mail/Slack/webhook dispatch from the curator — stage or egress only.
- Tell peer agents (or imply in egress) that pending queue work is cleared — only **approved** entries after this sitting are cleared.

## Frameworks

- `kits/frameworks/brief.md` — brief standard
- `kits/frameworks/familiarity.md` — familiarity map shape
- `kits/frameworks/egress.md` — desk egress Kind / Route / filename
