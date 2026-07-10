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

The agent runtime is **Claude Code headless** (the `claude` CLI). The server and CLI are
Python-stdlib-only. Host chrome lives in sibling repos:

| Repo | Role |
|------|------|
| **setsweep-core** (this tree) | Desk + API + reference web UI + CLI |
| [`setsweep-desktop`](../setsweep-desktop/) | macOS Electron shell (`.app`) |
| [`setsweep-plugin`](../setsweep-plugin/) | Host adapters — VS Code/Cursor first; Obsidian & Sublime planned |

> **Vocabulary.** Two words recur in this project. **You** are the reviewer (the docs sometimes
> call you *the patron*). The **curator** is a per-project agent *identity carried in files*
> (`<project>/.setsweep/`), not a long-lived chat session — any fresh agent instance that reads
> those files *is* that project's curator.

## Install

```bash
pip install -e .            # CLI + web mode — standard library only
```

Requirements: **Python 3.11+** and the **`claude` CLI** on your `PATH`. setsweep stores **no API
key** — it uses `claude`'s ambient auth (its own login or `ANTHROPIC_API_KEY` in the environment).
See [`INSTALL.md`](./INSTALL.md) for the native `.app` bundle.

## Run

```bash
setsweep              # browser / server mode  (default)
setsweep --web        # same — http://127.0.0.1:4242
setsweep add <dir>    # register a project from the CLI
setsweep projects     # list registered projects
```

Both modes share one fixed port (4242). At launch the app pings the port (`/api/ping` identity
beacon) and retires a previous setsweep still holding it — but only on a verified ping answer,
never on a stale pidfile — so a bookmarked tab can't talk to an orphaned server running old code.
A foreign occupant of the port → graceful fallback to an ephemeral one.

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

**Founding is an interview, not a survey.** When you add a project, the curator reads its files,
then interviews you in the center panel — what the project is *to you*, what you want a second
reader for, what must never be touched. From the interview and the files it founds the desk:

1. **Charter** (`PROJECT.md`) — what the project is, the review lens, the conventions. Your answers
   beat the files where they disagree, quoted where your words were exact.
2. **Memory seed** (`MEMORY.md`) — only interview-stated and file-attested preferences, never invented.
3. **Review program** + the first urgency-ranked **queue batch**, each entry with a real brief.

Founding is marked complete only when entries actually land; an interrupted founding never *traps*
the project — the interview header offers **found from files** (one-shot survey → charter + queue,
no interview) and **skip for now** (open the project as-is, found later).

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
- **Review agent** — each turn spawns `claude -p` (stream-json) in the project root with
  read-only tools (`Read/Glob/Grep` + a fenced shell allowlist). The agent proposes changes in
  fenced code blocks; **→ editor** and **copy** buttons let you apply them in the center pane.
  The sweep and founding steps carry write tools when files must change on disk. Sessions persist
  per project.
- **Approve** — marks the entry approved and logs it. Approve is a bookmark; the sweep is the
  commit. Leave an entry pending if your pass is not done; use **comment** for sweep instructions.

## The resident curator

Each project's `.setsweep/` directory *is* its curator — a persistent identity in **files, not
sessions**:

1. **Charter** — `PROJECT.md`, amendable when evidence contradicts it.
2. **Memory** — `MEMORY.md`, accrued by the sweep's *learn* step: rulings and preferences already
   learned, never re-asked. Bounded (~80 lines), revised against new evidence.
3. **Record** — the append-only history: `approvals.log`, `comments.log`, `sweep.log`, `sessions/`,
   `archive/`.

Charter and memory are injected into every agent the app spawns. Any fresh agent that reads these
files *is* the curator; sync the directory and the curator exists on any machine. The desk is the
application; the app is a viewport — `PROJECT.md` and the logs read as plain documents even with no
app installed.

## The sweep cycle

**Sweep is the iteration's turn** — fired whenever a round of work reaches a review point (not only
at day's end). One streamed pass, watched live: **diff → assess → ripple → learn → log → restock.**

1. **Diff** each queue entry against its cached snapshot.
2. **Assess** what changed and the apparent intent.
3. **Ripple** — check the changes against the rest of the project: mechanical inconsistencies (stale
   cross-references, renamed terms) are fixed in place; judgment calls are flagged; append-only
   records are never auto-mutated.
4. **Learn** — compare the briefs' predictions against what you actually did; record only what
   generalizes into `MEMORY.md`.
5. **Log** the sitting to `sessions/`.
6. **Restock** — archive processed entries, delete their snapshots, load the next batch.

If the project configures a rulings `ledger`, ticked/filled/struck rows are applied to the canonical
documents exactly as written; "launch"-type rulings are never executed, only logged as directives.

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
**⌘⇧A**): per-task agent models (setup / chat / glance), a full color/font/size palette system with
saved palettes, project editing, behaviour toggles (highlight line, markdown highlighting, glance,
unwrap, autosave interval, sweep confirmation), and a debug/health view. Every setting is
live-applied and persisted.

## Security model

- **Localhost only.** The server binds `127.0.0.1`; agents get no network beyond it.
- **Fenced file I/O.** Every path is resolved and checked against the allowed roots. The fence is
  exactly your **registered project roots** (each gated under `$HOME` at registration) — nothing
  else by default. To widen it (e.g. a notes vault whose `[[wikilinks]]` cross project boundaries),
  set `SETSWEEP_ALLOWED_ROOTS` to an `os.pathsep`-separated list of extra base roots.
- **Two tool tiers.** The interview and discussion-mode chat are read-only; edit-mode chat, the
  sweep, and founding get project-write tools fenced to the project root (`acceptEdits`). Append-only
  records are never auto-mutated.
- **No API keys stored** — `claude`'s ambient auth only.

## Status

setsweep is a working tool the author uses daily; it is not a polished product. Known rough edges
and deliberate deferrals (re-founding merge semantics, a queue-entry-creation UI, FSEvents instead
of cron polling, an app icon) are tracked in the issues. Contributions welcome under the terms below.

## License

MIT — see [`LICENSE`](./LICENSE). Use it freely; the only ask is that the copyright and license
notice travel with copies (that's the attribution). Bundles
[marked](https://github.com/markedjs/marked) (MIT) and [IBM Plex](https://github.com/IBM/plex)
(OFL); see [`THIRD_PARTY_NOTICES.md`](./THIRD_PARTY_NOTICES.md).
