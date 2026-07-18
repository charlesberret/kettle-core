(The patron APPROVED the desk proposal — you now found the desk for {name} ({root}). Read {proposal_path} carefully FIRST. That file (especially any patron edits in the editor) is the standing brief. Where the proposal and earlier interview chat disagree, THE PROPOSAL WINS. Where the proposal and project files disagree, THE PROPOSAL WINS.
1. THE CHARTER — write {desk_dir}/PROJECT.md from the proposal: identity, kind, families/paths, review lens, conventions and fences, key references. Under ~80 lines. Quote the patron where their wording is exact. If other agents share this repo, name them and that Setsweep approve+sweep is the patron gate (approvals egress on sweep).
2. THE MEMORY — seed {desk_dir}/MEMORY.md: purpose header + preferences stated in the proposal/interview and attested in project files. Nothing invented.
2b. THE FAMILIARITY — seed {desk_dir}/FAMILIARITY.md from proposal + survey (corpus map or greenfield scaffold map). Under ~120 lines.
2c. FOUNDING ANSWERS — write {desk_dir}/founding-answers.md: compact durable extract of the approved proposal (status/direction/fences/priorities/sweep extras/elaborations).
2d. SWEEP ACTIONS — write {desk_dir}/SWEEP-ACTIONS.md from the proposal's sweep extras. If nothing extra, one line. Never transmit mail/Slack from the desk.
3. THE PROGRAM — write {desk_dir}/review-program.md from the proposal: families and batch plan, OR for greenfield the scaffold/roadmap program (next drafts when queue low). Desk conventions: one batch at a time; in-editor emendations are the tuning; approve = done.
4. THE FIRST QUEUE — rewrite {queue_path} (JSON; schema below) with the first content batch (typically 3–10 entries), urgency-ranked from the proposal's intent:
   - Existing corpus: real project documents that need attention; honest briefs.
   - Greenfield: CREATE the first files if missing (e.g. README/overview, then ROADMAP.md or PLAN.md), then queue them with honest briefs. Do not leave an empty queue when the proposal asked for scaffold.
   You may leave the desk-proposal entry approved at the bottom or omit it; do not make it the only pending work. Set top-level "curated" to today + your role.
Queue entry schema (all fields): id (slug), title, path (absolute), project (name), project_root (absolute), ask_type (input|tuning|judgment), ask (one line: what is wanted from the patron), desk_item (null), urgency (high|medium|low), status ("pending"), unblocks (one line or "—"), brief (the curatorial brief — see the brief standard below).
BRIEF STANDARD (both audiences, in order): the brief is shown to the patron the instant a file loads — seconds before any agent reply — so it must do real orienting work on its own. Write it in TWO movements: (1) a FIRST LINE that is plain, jargon-free, and immediately useful to a human — what this document is and what is wanted of them, in a sentence they can act on cold; (2) then 1–3 sentences of precise detail that also prime the review agent (specifics, terms of art, what to check). The two movements MUST NOT restate each other — movement 2 adds only precision movement 1 omitted (an exact quote, the fault's location, a concrete check); if you'd only be re-saying the lead in other words, stop at the lead. Spell out abbreviations on first use; no procedural agent-directed tails ('check file X first') — fold any sharpening cross-reference into the ask itself. 2–4 sentences total. Never make the patron decode shorthand to learn why a file is in front of them.
5. Final message: one line on the desk now standing, sweep actions if any, the first batch, and that they should select the first content entry. Conversation continues here.)

LIVE REPORTING (required — the patron is watching this stream):
- Never go more than one meaningful tool call without a short chat line.
- Before each major write, announce it in one line (e.g. 'Writing PROJECT.md…', 'Seeding MEMORY…', 'Filing queue entry: spine.md…').
- After each write, one half-line confirm (e.g. 'PROJECT.md done · 42 lines').
- If you fix your own mistake (schema, path, ask_type), say so in one line before re-writing.
- Prefer many small status lines over one big plan then silence. Users love output; silence reads as a hang.
- End with a short recap of what was written and what they should do next.
