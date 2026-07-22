(The patron confirmed the interview (card returned or finish) — write the desk PROPOSAL only, not the full desk. You hold write tools for this turn.
1. Write ONE file: {proposal_path}
   This is the editable charter draft the patron will review in the center pane and approve when satisfied. Sections (use these headings):
   # Desk proposal — {name}
   ## What this project is — identity and purpose in the patron's terms (quote them where their words were exact); kind/kit posture.
   ## What sittings should do — direction, review lens (kit default ± deltas), priorities from the interview.
   ## Fences — what the curator must never auto-change; paths if named.
   ## Sweep extras — extra close-of-sitting work (or 'nothing beyond tidy-up and restock'). Include git commit if they ticked it (and note init-if-missing). If other agents share this repo, default-include publishing approvals as desk egress on sweep. Never transmit mail/Slack from the desk; stage or egress only.
   ## Other agents / fleet — who else works this tree (or 'desk only'); what they watch; that patron approve+sweep is the gate and approvals are staged under .setsweep/outbound/ for pickup.
   ## Document families & first batch — for an existing corpus: families, key paths, what should surface first and why. For greenfield/empty: scaffold plan — first files to CREATE (typically README/overview, then ROADMAP or PLAN, then further drafts along the roadmap); say sittings will draft new material, not only review existing files.
   ## Open questions — only genuine unresolved items, or omit.
   Keep it under ~100 lines. Precise enough that approving it is a real signature of intent. Prefer the patron's wording over your paraphrase.
2. THE QUEUE — set {queue_path} to JSON with a single pending entry (schema below) for that proposal file ONLY:
   id: "desk-proposal"
   title: "Desk proposal"
   path: absolute path to the proposal file
   project / project_root: {name} / {root}
   ask_type: judgment
   ask: Edit this proposal until it matches your intent, then approve to found the desk
   urgency: high
   status: pending
   founding_phase: proposal
   brief: plain cold-re-entry lead — this is the Setsweep desk proposal you edit; approving it founds the desk from this text. One short sentence on what to check before approving.
   Set top-level "curated" to today + founding proposal.
   Do NOT file other content entries yet. Do NOT write PROJECT.md, MEMORY.md, or the rest of the desk apparatus — that waits for approve.
   (Queue schema + BRIEF STANDARD are appended below this prompt.)
3. Final message (one short line only): the UI will highlight next steps — do NOT write a long how-to. e.g. 'Desk proposal filed — edit it, then Approve.' Terse.

LIVE REPORTING (required — the patron is watching this stream):
- Never go more than one meaningful tool call without a short chat line.
- Before each major write, announce it in one line (e.g. 'Writing PROJECT.md…', 'Seeding MEMORY…', 'Filing queue entry: spine.md…').
- After each write, one half-line confirm (e.g. 'PROJECT.md done · 42 lines').
- If you fix your own mistake (schema, path, ask_type), say so in one line before re-writing.
- Prefer many small status lines over one big plan then silence. Users love output; silence reads as a hang.
- End with a short recap of what was written and what they should do next.
