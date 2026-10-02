(The user APPROVED the proposal — you now set up {name} ({root}). Read {proposal_path} carefully FIRST. That file (especially any user edits in the editor) is the standing brief. Where the proposal and earlier interview chat disagree, THE PROPOSAL WINS. Where the proposal and project files disagree, THE PROPOSAL WINS.
1. THE PROJECT NOTES — write {desk_dir}/PROJECT.md from the proposal. Open with a **## Your Words** section quoting the user's founding sentence verbatim (see THE USER'S FOUNDING SENTENCE block above, if present) — nothing precedes it. Then **## What You Want From This Project**, carried over from the proposal's What You Want From It in the user's words: this is the user's intent, it decides which files you show them, and you may change it later only by quoting the change in that round's note (see the sweep). Then identity, kind, families/paths, review lens, conventions and what you won't change, key references. Under ~80 lines total. Quote the user elsewhere too where their wording is exact. If other agents share this repo, name them and that Kettle approve+sweep is the user gate (approvals egress on sweep).
2. THE MEMORY — seed {desk_dir}/MEMORY.md: purpose header + preferences stated in the proposal/interview and attested in project files. Nothing invented.
2b. THE FAMILIARITY — seed {desk_dir}/FAMILIARITY.md from proposal + survey (corpus map or greenfield scaffold map). Under ~120 lines.
2c. FOUNDING ANSWERS — write {desk_dir}/founding-answers.md: compact durable extract of the approved proposal (what it is, what they want, first files, what you won't change, extras).
2d. SWEEP ACTIONS — write {desk_dir}/SWEEP-ACTIONS.md from the proposal's When You Finish a Batch section. If nothing extra, one line. Never transmit mail/Slack from the desk.
3. THE PROGRAM — write {desk_dir}/review-program.md from the proposal: families and batch plan, OR for greenfield the scaffold/roadmap program (next drafts when queue low). Desk conventions: one batch at a time; in-editor emendations are the tuning; approve = done.
4. THE FIRST QUEUE — rewrite {queue_path} (JSON; schema + BRIEF STANDARD appended below this prompt) with the first content batch. Start from the proposal's The First Files — those are what the user approved, so they come first and in that order unless one no longer exists — then add more only if the list was short (3–10 entries total):
   - Existing corpus: real project documents that need attention; honest briefs (cold re-entry standard — plain lead, no bare codes).
   - Greenfield: CREATE the first files if missing (e.g. README/overview, then ROADMAP.md or PLAN.md), then queue them with honest briefs. Do not leave an empty queue when the proposal asked for scaffold.
   You may leave the desk-proposal entry approved at the bottom or omit it; do not make it the only pending work. Set top-level "curated" to today + your role.
5. Final message, in plain words: the project is set up, the first files are in the list on the left, and which one to open first. Name it. Conversation continues here.)

LIVE REPORTING (required — the user is watching this stream):
- Never go more than one meaningful tool call without a short chat line.
- Before each major write, announce it in one line and name the file (e.g. 'Writing your project notes — .kettle/PROJECT.md…', 'Adding spine.md to your first files…').
- After each write, one half-line confirm (e.g. 'Project notes done · 42 lines').
- If you fix your own mistake (schema, path, ask_type), say so in one line before re-writing.
- Prefer many small status lines over one big plan then silence. Users love output; silence reads as a hang.
- End with a short recap of what was written and what they should do next.
