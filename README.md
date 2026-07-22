# setsweep-core

**A review instrument for working *with* coding/writing agents instead of around them.**

This repo is the **canonical product**: Python server, kits, runtime, CLI, and the reference
three-pane web UI. The desk (`.setsweep/` under each project) is the application; every UI is a
viewport over the same localhost API.

setsweep is a three-pane sitting — an agent-curated **queue** (left) feeds documents into a
plaintext **editor** (middle) beside a project-aware **review agent** (right). Its premise:
**agents prepare and propagate; you read and rule.** Context is paid for once — by a
per-project *curator* agent that writes a short brief for each item — and delivered pre-packed;
your edits and approvals are then applied outward mechanically by a *sweep*. Nothing asks you to
re-derive what an agent already knows, and nothing lets an agent commit what is yours to decide.

The agent runtime defaults to **Claude Code headless** (the `claude` CLI). Other
first-class curator providers (Admin → Agents, or `settings.curator.provider`):

| Provider | CLI | Auth (ambient — never stored) |
|----------|-----|-------------------------------|
| `claude` (default) | `claude` | Claude login / `ANTHROPIC_API_KEY` |
| `grok` | `grok` | Grok login / `XAI_API_KEY` |
| `chatgpt` | `codex` (OpenAI Codex CLI) | ChatGPT login / `OPENAI_API_KEY` |
| `gemini` | `gemini` | Gemini login / `GEMINI_API_KEY` |

Raw chat-completions HTTP is intentionally out of scope — Setsweep drives **agentic CLIs**
through the same spawn → normalize → NDJSON path. The server and CLI are Python-stdlib-only.
Host chrome lives in sibling repos:

| Repo | Role |
|------|------|
| **setsweep-core** (this tree) | Desk + API + reference web UI + CLI |
| [`setsweep-desktop`](../setsweep-desktop/) | macOS Electron shell (`.app`) |
| [`setsweep-plugin`](../setsweep-plugin/) | Host adapters — VS Code/Cursor first; Obsidian & Sublime planned |

Where this is all going: [`ROADMAP.md`](./ROADMAP.md) — north star, phased plan, and the
agent-brief work packages under [`docs/briefs/`](./docs/briefs/).

> **Vocabulary.** Two words recur in this project. **You** are the reviewer (the docs sometimes
> call you *the patron*). The **curator** is a per-project agent *identity carried in files*
> (`<project>/.setsweep/`), not a long-lived chat session — any fresh agent instance that reads
> those files *is* that project's curator.

## Install

```bash
pip install -e .            # CLI + web mode — standard library only
```

Requirements: **Python 3.11+** and a curator CLI on your `PATH` — **`claude`** (default),
**`grok`**, **`codex`** (ChatGPT / Codex), or **`gemini`**. setsweep stores **no API key** —
it uses the CLI’s ambient auth.
See [`INSTALL.md`](./INSTALL.md) for the native `.app` bundle.

## Run

```bash
setsweep              # browser / server mode  (default)
setsweep --web        # same — http://127.0.0.1:4242
setsweep add <dir>    # register a project from the CLI
setsweep projects     # list registered projects
setsweep doctor       # install health (PATH + editable mapping)
```

Canonical install is `~/.setsweep-venv` with one PATH shim — see [`INSTALL.md`](./INSTALL.md).

A bare launch prints the desk URL and a one-line CLI hint (`CLI: setsweep projects | add | queue | chat …`), so the windowless half of the product is discoverable from the terminal.

Both modes share one fixed port (4242). At launch the app pings the port (`/api/ping` identity
beacon) and retires a previous setsweep still holding it — but only on a verified ping answer,
never on a stale pidfile — so a bookmarked tab can't talk to an orphaned server running old code.
A foreign occupant of the port → graceful fallback to an ephemeral one.

HTTP contract for viewports (tiers, streaming, `project` required): [`API.md`](./API.md).

## Concepts

- **`server.py`** — Python 3 stdlib server. Binds `127.0.0.1` only. File I/O is fenced
  (resolve-then-`is_relative_to`) to registered project roots plus a configurable base; registered
  roots extend the fence, so registration is the gate (a folder must exist, be a directory, and
  live under your home).
- **Viewports** — browser (`setsweep --web`), CLI (`setsweep queue|open|chat`), macOS
  [`setsweep-desktop`](../setsweep-desktop/), and editor plugins in
  [`setsweep-plugin`](../setsweep-plugin/) (VS Code/Cursor now; Obsidian/Sublime later). All talk to
  this server; none own the desk.
- **`projects.json`** — the registry (self-creates; see [`projects.example.json`](./projects.example.json)).
  One stanza per project: `id`, `name`, `root` (the agent's working directory), `kit` (the curator
  playbook — see below), an optional `role`
  (per-project system prompt for the review agent), and — for the inbox kind — an optional `intake`
  block. Add a project by hand, with `setsweep add`, or via the in-app **＋ add project** flow.
- **`kits/`** — curator **playbooks**, one per kind of project (`writing`, `code`, `records`,
  `knowledge`, `inbox`). A kit arms a project's curator with a review lens, an urgency rubric, a
  first-queue heuristic, and sweep self-checks. Shipped defaults are read-only; user edits/custom
  kits live in `settings.json`. See [`kits/README.md`](./kits/README.md).

## Founding a project

**Founding is talk → proposal → approve, not a silent bootstrap.** When you add a project, the
curator surveys its files and interviews you in the agent chat (kit prompt list + open discussion:
status, direction, fences, priorities, **sweep actions**). **Finish ✓** drafts one editable
**desk proposal** (`.setsweep/DESK-PROPOSAL.md`) and loads it in the center pane. You edit freely
(and can still chat to revise it). **Approve** on that proposal hands it back to the curator, who
digests *your* text and founds the desk:

1. **Charter** (`PROJECT.md`) — from the approved proposal (your wording wins).
2. **Memory seed** (`MEMORY.md`) — only stated and file-attested preferences, never invented.
3. **Familiarity seed** (`FAMILIARITY.md`) — thin project map; sweeps deepen it.
4. **Founding answers** (`founding-answers.md`) — durable extract of the approved proposal.
5. **Sweep actions** (`SWEEP-ACTIONS.md`) — extra close-of-sitting work (stage/egress only; never
   transmit from Setsweep).
6. **Review program** + **first content queue** — existing corpus, or greenfield drafts
   (README/overview, roadmap, …) when the folder was empty.

Empty folders get a greenfield opening (new project vs wrong folder). Founding is complete when
*content* queue entries land (the proposal alone does not count). **Skip for now** leaves the
desk unfounded until you reselect the project.

## How it works

- **Queue** — per-project `queue.json`. Each entry carries a path, an `ask`, an urgency, a status,
  and a **`brief`**: curatorial context written when the entry is filed, shown to you on load **and**
  injected into the review agent's prompt, so neither side re-derives it. Entries sort by urgency
  (approved sink to the bottom). A **⟳ reload** button refetches the queue to pick up entries filed
  out of band, reconciling the open entry without wiping the chat.
- **Snapshots** — on first sight of a pending entry, the app caches the file's bytes
  (`<desk>/snapshots/<id>.orig`). First sight = the original; the sweep diffs against it and deletes
  it when the batch is archived.
- **Editor** — a soft-wrapped textarea with a line-number gutter; ⌘S saves atomically. An inline
  find/replace bar; an optional *unwrap on open* that reflows hard-wrapped prose for editing. The
  rendered (reading) view turns Obsidian-style **`[[wikilinks]]`** into clickable links that open
  the target (fenced to the allowed roots) in your default editor.
- **Info pane** — the active entry's fields, editable in place through a whitelisted endpoint
  (never path/id). For an inbox entry it also shows the **`source`** — the incoming item the draft
  answers.
- **Glance** — optional: when a file loads, the agent fires a one-breath reaction to its *brief only* (no
  tools, no session) to surface anything unclear. Non-blocking; superseded the instant another file
  opens. Off by default; enable in Admin.
- **Review agent** — each turn spawns the active curator CLI in the project root
  (Claude `stream-json`, Grok `streaming-json`, Codex `--json`, Gemini `stream-json`) with
  project-fenced edits when the tier allows. Prefer fenced proposals for small emendations
  (**→ editor** / **copy**); implement on disk when the patron asks. Interview stays
  read-only until Finish/Found. Sessions persist per project. Switch provider in Admin →
  Agents (`curator.provider`: `claude` | `grok` | `chatgpt` | `gemini`).
- **Approve** — marks the entry approved and logs it. Approve is a bookmark; the sweep is the
  commit. Leave an entry pending if your pass is not done; use **comment** for sweep instructions.

## The resident curator

Each project's `.setsweep/` directory *is* its curator — a persistent identity in **files, not
sessions**:

1. **Charter** — `PROJECT.md`, amendable when evidence contradicts it.
2. **Memory** — `MEMORY.md`: rulings and preferences already learned, never re-asked. Bounded
   (~80 lines); leave untouched when a sitting produced nothing generalizable.
3. **Familiarity** — `FAMILIARITY.md`: accrued project-centered expertise (families, roles, paths,
   relationships, pitfalls). Deepened on restock so briefs improve over time (~120 lines).
4. **Sweep actions** — `SWEEP-ACTIONS.md`: extra close-of-sitting work armed at founding
   (outbound stage, egress for dispatch, plaintext sitting logs, sheets, reporting).
5. **Record** — the append-only history: `approvals.log`, `comments.log`, `sweep.log`, `sessions/`,
   `archive/`, plus `founding-answers.md` from the confirmation card.
6. **Egress** — `.setsweep/outbound/`: staged memos for the broader agent ecosystem (handoffs,
   escalations, launch directives, domain pointers). `setsweep egress` / `egress-status`. Distinct
   from the inbox kit's `<root>/outbox` (mail drafts). Fleet pickup drains `Status: staged`.

Charter, memory, familiarity, and sweep actions are injected into every agent the app spawns. Any fresh agent that
reads these files *is* the curator; sync the directory and the curator exists on any machine. The
desk is the application; the app is a viewport — `PROJECT.md` and the logs read as plain documents
even with no app installed.

## The sweep cycle

**Sweep is the iteration's turn** — fired whenever a round of work reaches a review point (not only
at day's end). One pass, watched live: **close (cheap when quiet) → accrue familiarity → restock.**

**Close** — the server runs a mechanical close-kit (`sweepkit` / `setsweep sweep-status|close`) when
the sitting is quiet and ready: stage inbox drafts, archive, thin session log. When judgment is
needed (diffs, comments, ledger), the curator still closes by hand, then archives via the kit.
Precomputed diffs stay in the prompt so the agent does not re-derive them. Then honor
`SWEEP-ACTIONS.md` for any extra work (egress for dispatch, plaintext sitting logs, sheets,
reporting) — never transmit from the desk.

**Accrue + restock** — deepen `FAMILIARITY.md` (project-centered expertise) while reading the next
batch, then load honest briefs into the queue (`kits/frameworks/` scaffolds the brief and familiarity
shapes; `kits/skills/setsweep-sweep` is the thin conductor). This is where curator time should go.

If the project configures a rulings `ledger`, ticked/filled/struck rows are applied to the canonical
documents exactly as written; "launch"-type rulings are never executed — logged as `LAUNCH DIRECTIVE`
in `sweep.log` **and** staged under `.setsweep/outbound/` for fleet pickup.

## The inbox kind

Point setsweep at a pile — emails, support requests, reports — and work it by **reading curated
summaries and editing agent-drafted responses**, rather than answering each from scratch or handing
the whole loop to an agent unwatched. An `inbox` project carries an `intake` block:

```json
"kit": "inbox",
"intake": { "watch": "~/Mail/ToReview", "responses": "responses", "outbound": "outbox" }
```

New files in the watched folder are curated into the queue: for each, a curator drafts a response
into `responses/` and files an entry whose `path` is the **draft** (what you edit) and whose
`source` is the incoming item, with a triage brief. You read the brief, edit the reply by hand, and
approve; at sweep, approved drafts are **staged** to `outbound/` for an out-of-band tool to send —
the sweep never transmits anything itself.

The folder-watch is the bundled **`setsweep-watch`** script (installed as a console command). Run
it on a schedule so new files curate automatically:

```cron
*/15 * * * *  setsweep-watch        # every 15 min; logs health to ~/.cache/setsweep/watch-health.json
```

It's self-contained (stdlib + the `claude` CLI), scans each `intake` project's folder, and curates
only files it hasn't seen before. The in-app sweep handles the outbound staging.

## Settings & Admin

`settings.json` self-creates and backs a floating **Admin** panel (native **View › Admin** or
**⌘⇧A**): per-task agent models (setup / chat), a full color/font/size palette system with
saved palettes, project editing, behaviour toggles (highlight line, markdown highlighting,
unwrap, autosave interval, sweep confirmation), and a debug/health view. Every setting is
live-applied and persisted.

## Security model

- **Localhost only.** The server binds `127.0.0.1`; agents get no network beyond it.
- **Fenced file I/O.** Every path is resolved and checked against the allowed roots. The fence is
  exactly your **registered project roots** (each gated under `$HOME` at registration) — nothing
  else by default. To widen it (e.g. a notes vault whose `[[wikilinks]]` cross project boundaries),
  set `SETSWEEP_ALLOWED_ROOTS` to an `os.pathsep`-separated list of extra base roots.
- **Two tool tiers.** The founding interview is read-only; review chat, the sweep, and founding
  finish/bootstrap get project-write tools fenced to the project root (`acceptEdits`). Append-only
  records are never auto-mutated. (Chat writes are interim always-on; a future chat-window
  redesign may add real permission UX.)
- **No API keys stored** — `claude`'s ambient auth only.

## Status

setsweep is a working tool the author uses daily; it is not a polished product. Known rough edges
and deliberate deferrals (re-founding merge semantics, a queue-entry-creation UI, FSEvents instead
of cron polling, an app icon) are tracked in the issues. Contributions welcome under the terms below.

## License

MIT — see [`LICENSE`](./LICENSE). Use it freely; the only ask is that the copyright and license
notice travel with copies (that's the attribution). Bundles
[marked](https://github.com/markedjs/marked) (MIT),
[DOMPurify](https://github.com/cure53/DOMPurify) (Apache-2.0 / MPL-2.0), and
[IBM Plex](https://github.com/IBM/plex) (OFL); see
[`THIRD_PARTY_NOTICES.md`](./THIRD_PARTY_NOTICES.md).
