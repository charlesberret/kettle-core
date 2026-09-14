# Reviewing this tree

This file is the briefing for a full-tree review of **kettle-core as it is**,
not as a generic agent IDE. Product home:
[charlesberret/kettle](https://github.com/charlesberret/kettle).

## What this is

Kettle is a **local-first review instrument**. Agents prepare and propagate;
the human reviewer reads and rules. Durable state is ordinary files under
`<project>/.kettle/`. One stdlib Python server binds `127.0.0.1` only
(default **4242**). Graphical sitting is **one file**: `kettle/static/index.html`.
Desktop and VS Code are viewports, not a second product.

It is **not** a coding agent, a session sidebar, a fleet dashboard, or a
chat app with a file pane.

Read first: [`ARCHITECTURE.md`](../ARCHITECTURE.md) (thesis + invariants),
[`docs/UI.md`](./UI.md), [`docs/UI-STRUCTURE.md`](./UI-STRUCTURE.md),
[`docs/PLATFORMS.md`](./PLATFORMS.md), [`API.md`](../API.md),
[`ROADMAP.md`](../ROADMAP.md), [`CLAUDE.md`](../CLAUDE.md).
`docs/briefs/` is historical evidence — prefer code and tests when they disagree.

## Guiding principles (non-negotiable)

1. Localhost only; file I/O fenced; no API keys in settings.
2. Append-only records are never auto-mutated. Approve **bookmarks**; Sweep **closes**.
3. The curator never invents. The user’s words beat the files.
4. Memory is distillation (~80 lines), not a log.
5. Every background actor writes a healthbeacon.
6. One sitting structure (`UI-STRUCTURE.md`). Do not import TUI-app chrome
   (conversation search, command-palette-first, three-pane chat as the product).

## Current form (founding)

Initiation P1–P4 is the live ceremony. Judge founding against this, not against
leftover card CSS.

1. **Register** requires a **founding sentence** (“what is this, and what do you
   want from a second reader here?”). That sentence is quoted first in the
   charter (`## Your Words`).
2. **Survey** is deterministic core (`survey.py`) — git activity + mtimes, no
   curator CLI.
3. **Interview** is a **tool-less conversation**. Opening: one sentence on what
   this is (anchored on their words) · 2–3 dated survey observations · a posture
   guess · **one** mission question in prose. No checklist, no fences
   interrogation, no confirmation card. Talk until they are ready or click
   **Draft Proposal ✓**.
4. **Propose** writes `DESK-PROPOSAL.md` and queues it. User edits the file.
5. **Found Desk** (Approve while proposing) founds the desk. A desk is
   **founded** only when `PROJECT.md` exists **and** the queue has a content
   entry (not the proposal stub alone).

P5 (proposal diet: four headings, cut `founding-answers.md`, Found lands on the
first brief) is **not done**. `propose.md` still uses the older section list.
Do not treat that leftover as the destination.

**Known sitting debt (P4):** `static/index.html` still contains confirmation-card
parser/CSS. It must **not** upgrade agent GFM into a tick form. Agent chat
renders GFM (headings, lists, task ticks) as display markdown. Flag remaining
card machinery as cleanup, not as the product.

## Current form (elsewhere)

- **Curator default in code** is Claude Code CLI. Grok / Codex / Gemini are
  first-class. Interview argv is `--permission-mode plan` (Claude must never
  pass a bare `--allowedTools` — current CLIs exit 1).
- **Auth:** per-boot `X-Kettle-Token` + Host/Origin gates are **shipped**
  (`docs/AUTH-TOKEN.md`). ROADMAP security bullets that still read as todo are
  lag. Remaining: prompt-fenced provider permissions; no remote/multi-user.
- **Viewports:** desktop loads this sitting. A desktop UX gap is a core web gap.
  VS Code host-adapts; `ui-copy.js` / palette snapshots must stay in sync.
  Two macOS Application Support folders (`Kettle` vs `kettle-desktop`) are a
  **desktop** registry issue, not a missing core feature.

## How to review

Harsh on stranger-path failure, silent founding/sweep breakage, CLI argv a
current binary will reject, sitting that dumps raw GFM, and docs that
contradict the live tree.

Do **not** propose: turning Kettle into a coding agent; a second frontend in
this repo; remote serving; inventing desktop/VS Code bugs you cannot see here.

**Output wanted:** ranked Critical / High / Medium / Low with file:line, which
invariant or stranger-path step it breaks, and a concrete fix. End with top 5
before public preview; what is load-bearing and must not be casually rewritten;
one-paragraph verdict — coherent instrument vs pile of viewports.
