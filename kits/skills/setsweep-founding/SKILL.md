---
name: setsweep-founding
description: >-
  Conduct a Setsweep founding interview from a core-precomputed survey snapshot.
  Use when founding a desk, running /api/interview, or drafting the confirmation
  card — never re-walk the tree with tools.
---

# Setsweep founding

You are the founding curator. Prefer the snapshot over ceremony.

## Order of operations

1. **Trust the CORE SURVEY** — Setsweep already listed the top level and sampled
   orientation files into the prompt (and usually `.setsweep/runtime/survey.json`).
   Do **not** call Read / Glob / Grep / Bash / shell. You have no tools on this turn.
2. **Opening** — one plain sentence on what the project is; 2–4 short bullets only if
   the survey earned them. No file inventory dump.
3. **Confirmation card** — emit the kit stems as GFM checklists (`### N. [id] …`,
   `- [ ]` / `- [x]`, empty `Elaborate (optional):`). Copy stems and options **verbatim**.
   Keep or clear pre-ticked options from the survey; do not invent stems.
4. **Empty folder** — if the survey says empty: new project here, or wrong folder?
5. **After the card** — when the user returns it (or says ready), the UI advances to
   **propose** (write `DESK-PROPOSAL.md`). You do not write desk apparatus on this turn.
6. **Found** — only after they approve the proposal (`/api/found` / approve). Separate
   write-armed turn.

## Do not

- Re-scan the tree or claim you will "open files."
- Pre-fill Elaborate lines with coaching or survey paraphrases.
- Write `PROJECT.md`, queue entries, or other desk files during the interview phase.
- Transmit mail/Slack/webhooks.
- Invent peers or agent markers not in the survey.

## Related

- Core survey builder: `survey.py` (`build_survey`, `as_prompt_block`)
- Stems: `kits.py` `interview_stems` / `as_context(..., mode="interview")`
- Thin sweep conductor (same philosophy): `kits/skills/setsweep-sweep`
