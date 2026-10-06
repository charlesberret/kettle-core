# Kettle lexicon

**Generated from `kettle/kits/_lexicon.json` — do not edit by hand.**
Regenerate with `tools/render-lexicon-doc.py`; `--check` runs in CI.

One place a Kettle term is defined and spelled. `tools/lint-lexicon.py` fails on a
violation in the prompt corpus or the copy catalog, and warns elsewhere.

## Casing

- **`title`** — A proper name — a document, or a named control that is also a title. Always exactly as `term`, mid-sentence included. docs/UI.md: signature actions that are also titles stay Title Case.
- **`lower`** — A common noun or verb. Lowercase in prose; a capital is correct only at the start of a sentence or inside a Title Case heading. `sweep` the act is lowercase; `Sweep` the control is its own entry.

## Fields

- **`avoid`** — Literal wrong spellings of THIS term. Decidable by a linter, so these are errors.
- **`not_synonyms`** — Different words that do not mean this term. Guidance for writers and for the curator; never linted, because only a reader can tell whether 'summary' is standing in for 'brief'.
- **`lint_case`** — false when the term is a single ordinary word and the lowercase form is legitimately the concept.
- **`retired`** — Literal strings that used to mean this term and must not come back (an old button label, a renamed document). Decidable, so these are errors too.

## Concepts

### ask

The one-line question an entry puts to the user — what judgment is wanted on this file.

*casing: `lower`*

Not a synonym for this term:

- `request` — the product word is ask
- `prompt` — 'prompt' means the curator's instructions

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

- `config` — a charter is prose the user and curator both read

### desk

One project as Kettle holds it: its charter, memory, queue, and records, kept in the project's desk directory. A desk is founded once and then worked, sitting by sitting.

*casing: `lower`*

Not a synonym for this term:

- `workspace` — a desk is not an IDE workspace
- `Desk directory` — common noun

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

Bringing a desk into being: register, survey, interview, Draft Proposal, Found Desk. Founding is a conversation, not a confirmation card.

*casing: `lower`*

Not a synonym for this term:

- `onboarding` — not the product word
- `setup wizard` — founding is a conversation; a wizard is the thing it is not

### founding interview

The tool-less conversation in which the curator learns what the project is and what the user wants from a second reader. A common noun: lowercase in prose.

*casing: `lower`*

Wrong spellings (these fail the linter):

- `Founding Interview` — a common noun, not a document title — lowercase in prose

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

- `session` — 'session' is the curator's conversation state, not the user's working period

### sweep

Closing the sitting: apply rulings, diff and assess the batch, fix or flag ripples, write the session log, restock the queue. Both noun and verb.

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

### curator

The project's resident agent: curates the queue, converses about the open file, and sweeps. Its identity lives in files, not in a session, so any agent that reads them is the curator.

*casing: `lower`*

Not a synonym for this term:

- `assistant` — generic; the curator is a defined role
- `the AI` — never refer to the curator this way in product copy
- `the bot` — never refer to the curator this way in product copy

## Documents

### Desk Proposal

The document the founding interview produces, written to DESK-PROPOSAL.md. The user edits it until it matches the project, then founds the desk from it. The document of record during the proposing state.

*casing: `title` · file: `DESK-PROPOSAL.md`*

Not a synonym for this term:

- `proposal doc` — not a product term
- `draft desk` — not a product term

## Controls

### Approve

The control that bookmarks a ruling on the open entry. It does not apply or commit anything — only a sweep does that.

*casing: `title` · not case-checked*

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

### Found Desk

The control that founds the desk from the edited Desk Proposal and stocks the first queue. The Approve control takes this label while proposing.

*casing: `title`*

Wrong spellings (these fail the linter):

- `found desk` — a named control — Title Case

Not a synonym for this term:

- `Create Desk` — a desk is founded, not created

### Start Interview

The control that registers a project and opens founding. docs/UI.md lists it among the signature actions that are also titles.

*casing: `title`*

### Sweep

The control that closes the sitting. The act is 'sweep' (lowercase); this entry is the named control only.

*casing: `title` · not case-checked*

## Viewports

### VS Code Desk

The panel kettle-vscode contributes to VS Code and Cursor. Name it in full. A bare `Desk` for the panel collides with `desk` the common noun and reads as a stray capital; write `the Desk panel` only where the context is already VS Code.

*casing: `title`*

Not a synonym for this term:

- `the extension` — the extension is the package; the panel it contributes is the `VS Code Desk`
