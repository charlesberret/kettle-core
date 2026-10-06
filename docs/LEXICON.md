# Kettle lexicon

**Generated from `kettle/kits/_lexicon.json` — do not edit by hand.**
Regenerate with `tools/render-lexicon-doc.py`; `--check` runs in CI.

One place a Kettle term is defined and spelled. `tools/lint-lexicon.py` fails on a
violation in the prompt corpus or the copy catalog, and warns elsewhere.

## Casing

- **`title`** — A proper name — a document, or a named control that is also a title. Always exactly as `term`, mid-sentence included. docs/UI.md: signature actions that are also titles stay Title Case.
- **`lower`** — A common noun or verb. Lowercase in prose; a capital is correct only at the start of a sentence or inside a Title Case heading. `sweep` the act is a house word; the control is `Finish batch`.
- **`sentence`** — A two-word control name in sentence case (`Finish batch`, `Not this`). Spelled exactly as `term` when it names the control; the lowercase phrase is ordinary prose.

## Fields

- **`avoid`** — Literal wrong spellings of THIS term. Decidable by a linter, so these are errors.
- **`not_synonyms`** — Different words that do not mean this term. Guidance for writers and for the curator; never linted, because only a reader can tell whether 'summary' is standing in for 'brief'.
- **`lint_case`** — false when the term is a single ordinary word and the lowercase form is legitimately the concept.
- **`retired`** — Literal strings that used to mean this term and must not come back (an old button label, a renamed document). Decidable, so these are errors too.
- **`audience`** — `house` (never on screen) or `both` (allowed everywhere).
- **`plain`** — For a `house` term: what a user sees instead. The linter quotes it as the fix.
- **`lint_house`** — false when the house word is also an ordinary English word in another part of speech, so the on-screen check would fire on correct copy.

## Concepts

### ask

The one-line question an entry puts to the user — what judgment is wanted on this file.

*casing: `lower`*

Not a synonym for this term:

- `request` — the product word is ask
- `prompt` — 'prompt' means the `curator`'s instructions

### brief

The curator's 2-4 sentence introduction to an entry, shown the instant the file loads. A clear, unassuming introduction, not a dense memo. Standard: kits/frameworks/brief.md.

*casing: `lower`*

Not a synonym for this term:

- `summary` — a brief introduces and orients; it does not summarise the file
- `description` — vague where the standard is specific

### charter

What a desk is for and how it should be worked, written at founding. Lives in PROJECT.md. A desk is founded only when a charter exists and the queue holds at least one content entry.

*casing: `lower` · file: `PROJECT.md`*

Not a synonym for this term:

- `config` — a charter is prose the user and `curator` both read

### desk

One project as Kettle holds it: its notes, memory, queue and records, in the project's desk directory. House word. On screen a user has a **project** — never a desk, and never a "project desk": a user should not have to learn what a desk is to use Kettle.

*casing: `lower`*

### egress

A signal staged in the desk's outbound/ folder for another agent or system. Staged, never transmitted from the curator sandbox.

*casing: `lower`*

Not a synonym for this term:

- `outbox` — the inbox kit's <root>/outbox is a different thing: approved mail drafts

### entry

One item in the queue: a file, plus its ask, brief, urgency, and status. 'queue entry' in full where the context needs it.

*casing: `lower`*

Not a synonym for this term:

- `ticket` — not an issue tracker
- `card` — not a board

### founding

Bringing a desk into being: register, survey, interview, the proposal, approval. Founding is a conversation, not a confirmation card. (`Found Desk` was the approval control's label until 2026-10-01; it is retired.)

*casing: `lower`*

Not a synonym for this term:

- `onboarding` — not the product word
- `setup wizard` — founding is a conversation; a wizard is the thing it is not

### founding interview

The tool-less conversation in which the curator learns what the project is and what the user wants from a second reader. A common noun: lowercase in prose. Lowercase in prose; as a pane hed it takes Title Case like any hed (docs/UI.md), which is why `Founding Interview` is correct in the status strip.

*casing: `lower`*

Not a synonym for this term:

- `onboarding interview` — see founding

### memory

The desk's distilled standing knowledge, in MEMORY.md. Memory is distillation — it is never a transcript.

*casing: `lower` · file: `MEMORY.md`*

### queue

The batch of entries the curator has staged for this sitting, ranked by urgency.

*casing: `lower`*

Not a synonym for this term:

- `inbox` — the inbox kit is a specific kit; the queue is the general structure
- `task list` — entries are files to read, not tasks

### ruling

The user's judgment on an entry, bookmarked by Approve. A ruling is not applied until the sitting is swept.

*casing: `lower`*

Not a synonym for this term:

- `decision` — reserve 'decision' for design decisions in docs
- `verdict` — not the product word

### sitting

One working session at a desk: the user reviews the queue, rules on entries, and closes with a sweep. The web UI as a whole is 'the sitting'.

*casing: `lower`*

Not a synonym for this term:

- `session` — 'session' is the `curator`'s conversation state, not the user's working period

### sweep

Finishing a batch: apply the user's decisions, review what changed, note the ripples, save a record, line up the next files. House word since 2026-10-06: the button reads **Finish batch**, and prose says 'finish the batch'. Identifiers (`/api/sweep`, `sweepLabel`, `sweep.log`) are contract, not copy.

*casing: `lower`*

Not a synonym for this term:

- `sync` — a sweep is not a synchronisation
- `commit the sitting` — a sweep does not make a git commit

### viewport

A client onto a desk: the web sitting, the desktop shell, the TUI, the VS Code Desk, the CLI. Every viewport attaches to the same desk and the same API.

*casing: `lower`*

Not a synonym for this term:

- `frontend` — there are several, and they are not all web
- `client app` — not the product word

## Roles

### agent

The project's resident agent: curates the queue, converses about the open file, and sweeps. Its identity lives in files, not in a session, so any model that reads them is the agent. Renamed from `curator` on 2026-10-01; the verb `curate` and the adjective `curatorial` survive, and so does every identifier (`curator.provider` in settings, `/api/curator`, `curatorProvider`), which is contract, not copy.

*casing: `lower`*

Retired — must not come back (these fail the linter):

- `curator` — the role is `agent` in user-facing copy (2026-10-01)
- `Curator` — the role is `agent` in user-facing copy (2026-10-01)

Not a synonym for this term:

- `assistant` — generic; the agent is a defined role
- `the AI` — never refer to the agent this way in product copy
- `the bot` — never refer to the agent this way in product copy

## Documents

### Desk Proposal

The document the setup questions produce, written to DESK-PROPOSAL.md. House name. On screen it is just **the proposal**.

*casing: `title` · file: `DESK-PROPOSAL.md`*

Not a synonym for this term:

- `proposal doc` — not a product term
- `draft desk` — not a product term

## Controls

### Approve

The control that rules on the open entry. On a founded project desk it bookmarks a ruling and applies nothing until a sweep. While a proposal is open it founds the project desk — the label no longer changes, so the sitting promotes the control visually instead (`body.proposing #approve`).

*casing: `title` · not case-checked*

Retired — must not come back (these fail the linter):

- `Found Desk` — the control reads Approve in both states (2026-10-01); `found` survives as the verb

Not a synonym for this term:

- `Accept` — not the product word

### Comment

The control that opens a note on the open file for the curator to address during the sweep.

*casing: `title` · not case-checked*

### Draft Proposal

The control that ends the founding interview early and writes the Desk Proposal. Carries a check glyph in the sitting: 'Draft Proposal ✓'.

*casing: `title`*

Retired — must not come back (these fail the linter):

- `finish ✓` — retired label
- `Finish Interview` — retired label

### Finish batch

The button that finishes a batch (internally, a sweep). Sentence case, like the other two-word controls; prose that names it says 'press Finish batch'.

*casing: `sentence` · not case-checked*

Retired — must not come back (these fail the linter):

- `Sweep` — the button is Finish batch on screen (2026-10-06)

### Start Interview

The control that registers a project and opens founding. docs/UI.md lists it among the signature actions that are also titles.

*casing: `title`*

## Viewports

### VS Code Desk

The panel kettle-vscode contributes to VS Code and Cursor. Name it in full. A bare `Desk` for the panel collides with `desk` the common noun and reads as a stray capital; write `the Desk panel` only where the context is already VS Code. On screen it is **the Kettle panel**, matching the view's title.

*casing: `title`*

Not a synonym for this term:

- `the extension` — the extension is the package; the panel it contributes is the `VS Code Desk`
