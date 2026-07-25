# setsweep

**A review instrument for working *with* coding/writing agents instead of around them.**

[![GitHub](https://img.shields.io/badge/github-charlesberret%2Fsetsweep-blue)](https://github.com/charlesberret/setsweep)

This repo is the **canonical product**: Python server, kits, runtime, CLI, and the reference
three-pane web UI. The desk (`.setsweep/` under each project) is the application; every UI is a
**viewport** over the same localhost API.

Setsweep is a three-pane **sitting** — an agent-curated **queue** (left) feeds documents into a
plaintext **editor** (middle) beside a project-aware **review agent** (right). Its premise:
**agents prepare and propagate; you read and rule.** Context is paid for once — by a
per-project *curator* that writes a short **brief** for each item — and delivered pre-packed;
your edits and approvals are then applied outward mechanically by a *sweep*.

Architecture (invariants, tool tiers, desk layout): [`ARCHITECTURE.md`](./ARCHITECTURE.md).  
Roadmap and briefs: [`ROADMAP.md`](./ROADMAP.md), [`docs/briefs/`](./docs/briefs/).
Repository ownership and compatibility: [`docs/REPOSITORIES.md`](./docs/REPOSITORIES.md).

## Glossary

| Term | Meaning |
|------|---------|
| **User** | You — the human reviewer who reads and rules (never “patron”). Prefer the person’s name when higher-level agent config supplies one; otherwise “user” / “you.” |
| **Curator** | Per-project agent *identity in files* (`.setsweep/`), not a chat session; any fresh agent that reads those files *is* the curator. |
| **Desk** | The files under `<project>/.setsweep/` that *are* the application state. |
| **Viewport** | Any UI over the desk (browser, CLI, desktop shell, editor plugin). |
| **Sitting** | One focused review session on a desk’s queue — read, comment, approve, then sweep. |
| **Founding** | Talk → proposal → approve that creates charter, memory, and first queue. |
| **Kit** | Curator playbook for a project kind (`writing`, `code`, `records`, `knowledge`, `inbox`). |
| **Brief** | Prepaid context on a queue entry — shown to you and injected into the review agent. |
| **Approve** | Bookmark that your pass on an entry is done; does not apply rulings outward. |
| **Sweep** | The iteration’s close: apply rulings, assess diffs, restock the queue, stage egress. |
| **Egress** | Staged outward memos under `.setsweep/outbound/` for external pickup (never transmitted by Setsweep). |
| **Ledger** | Optional rulings file (checkboxes/fills) applied exactly as written at sweep. |

## Quickstart (about ten minutes)

Requirements: **Python 3.11+**, a curator CLI on `PATH` (**`claude`** recommended), ambient
auth already working (`claude` login or `ANTHROPIC_API_KEY`). Setsweep stores **no API key**.

```sh
git clone https://github.com/charlesberret/setsweep.git
cd setsweep
python3 -m venv ~/.setsweep-venv
~/.setsweep-venv/bin/pip install -e .
ln -sf ~/.setsweep-venv/bin/setsweep ~/.local/bin/setsweep   # ensure ~/.local/bin is on PATH
hash -r
setsweep doctor
```

1. **Register a folder**  
   `setsweep add ~/path/to/a-project`  
   Or open the web UI (`setsweep --web`) → **＋ Project** (name + folder; more options for kit).
2. **Founding interview** — core surveys the folder, then a tool-less interview runs after add.
   When ready, **draft proposal ✓** writes a desk proposal into the editor.
3. **Edit the proposal**, then **approve** — the curator founds charter, memory, and the
   first content queue.
4. **First sitting** — open a queue entry, read the brief, edit if needed, **comment**,
   **Approve**. Keyboard: Tab/arrows in the queue, Enter to open; ⌘E toggles reading/source.
5. **Sweep** — closes the sitting and restocks. Prefer the in-app Sweep button, or
   `setsweep sweep-status <id>` / `setsweep sweep-close <id>` when the sitting is quiet.

Full install notes (PATH hygiene, reinstall rule, desktop): [`INSTALL.md`](./INSTALL.md).

## Install & run

```bash
pip install -e .            # from a clone — standard library only at runtime
setsweep                    # browser / server → http://127.0.0.1:4242
setsweep --web
setsweep projects
setsweep doctor
```

Canonical install is `~/.setsweep-venv` with **one** PATH shim. A bare launch prints the desk
URL and a CLI hint (`CLI: setsweep projects | add | queue | chat …`).

Default port **4242**. Launch pings `/api/ping` and may retire a previous healthy Setsweep
instance; a foreign port occupant falls back to an ephemeral port.

HTTP contract: [`API.md`](./API.md).

## CLI reference

| Command | What it does |
|---------|----------------|
| `setsweep` / `--web` | Start the browser viewport (default) |
| `projects` | List registered desks |
| `add <folder>` | Register a folder as a desk |
| `init` | Register the current directory |
| `found <project>` | Curator founds the desk (charter, memory, first queue) |
| `queue <project>` | Show the desk’s queue |
| `open <project> <id>` | Open an entry’s file in `$EDITOR` |
| `chat <project> [id]` | Talk to the resident curator |
| `lineage <project>` | Who edited what: agent / user / unattributed |
| `bind <project>` | Add the lineage directive to the project’s `CLAUDE.md` |
| `doctor` | Install health (PATH + editable mapping) |
| `sweep-status <project>` | CLOSE readiness (quiet / judgment / accrue) |
| `sweep-close <project>` | Quiet mechanical CLOSE when safe |
| `sweep-archive <project>` | Archive queue entries (after judgment) |
| `egress <project> …` | Stage a desk egress memo under `.setsweep/outbound/` |
| `egress-status <project>` | List staged egress memos |

`setsweep --help` and `setsweep <cmd> --help` always match the installed argparse.

## Concepts

- **Server** — Python 3 stdlib. Binds `127.0.0.1` only. File I/O is fenced
  (resolve-then-`is_relative_to`) to registered project roots; registration is gated under `$HOME`.
- **Viewports** — browser, CLI, optional macOS desktop and editor plugins (sibling repos).
  None own the desk; all talk HTTP to this core.
- **`projects.json`** — registry (see [`projects.example.json`](./projects.example.json)).
  Fields: `id`, `name`, `root`, `kit`, optional `role` and inbox `intake`.
- **`kits/`** — five kind playbooks: `writing`, `code`, `records`, `knowledge`, `inbox`.
  See [`kits/README.md`](./kits/README.md).
- **Desk layout** — durable files in `.setsweep/`; high-churn queue/chatlog/snapshots in
  `.setsweep/runtime/` (**exclude that path from file sync**). Details in
  [`ARCHITECTURE.md`](./ARCHITECTURE.md).

## Founding a project

**Founding is talk → proposal → approve, not a silent bootstrap.** When you add a project (web:
name + folder; desktop same UI; CLI `setsweep add`), the curator surveys its files and interviews
you in the **agent pane** (kit prompt list + open discussion: status, direction, fences,
priorities, **sweep actions**). **Draft proposal ✓** writes one editable **desk proposal**
(`.setsweep/DESK-PROPOSAL.md`) into the center pane. You edit freely (and can still chat to revise
it). **Approve** on that proposal hands it back to the curator, who digests *your* text and founds
the desk:

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
  (**→ editor** / **copy**); implement on disk when the user asks. Interview stays
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
6. **Egress** — `.setsweep/outbound/`: staged memos for other agents or systems (handoffs,
   escalations, launch directives, domain pointers). `setsweep egress` / `egress-status`. Distinct
   from the inbox kit's `<root>/outbox` (mail drafts). External pickup drains `Status: staged`.

Charter, memory, familiarity, and sweep actions are injected into every agent the app spawns. Any fresh agent that
reads these files *is* the curator; sync the directory and the curator exists on any machine. The
desk is the application; the app is a viewport — `PROJECT.md` and the logs read as plain documents
even with no app installed.

## The sweep cycle

**Sweep is the iteration's turn** — fired whenever a round of work reaches a review point (not only
at day's end). One pass, watched live: **close (cheap when quiet) → accrue familiarity → restock.**

**Close** — the server runs a mechanical close-kit (`sweepkit` / `setsweep sweep-status` and
`setsweep sweep-close`) when the sitting is quiet and ready: stage inbox drafts, archive, thin
session log. When judgment is needed (diffs, comments, ledger), the curator still closes by hand,
then archives via the kit. Precomputed diffs stay in the prompt so the agent does not re-derive
them. Then honor `SWEEP-ACTIONS.md` for any extra work (egress for dispatch, plaintext sitting
logs, sheets, reporting) — never transmit from the desk.

**Accrue + restock** — deepen `FAMILIARITY.md` (project-centered expertise) while reading the next
batch, then load honest briefs into the queue (`kits/frameworks/` scaffolds the brief and familiarity
shapes; `kits/skills/setsweep-sweep` is the thin conductor). This is where curator time should go.

If the project configures a rulings `ledger`, ticked/filled/struck rows are applied to the canonical
documents exactly as written; "launch"-type rulings are never executed — logged as `LAUNCH DIRECTIVE`
in `sweep.log` **and** staged under `.setsweep/outbound/` for external pickup.

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
- **Two tool tiers.** The founding interview is tool-less (core survey snapshot); review chat, the sweep, and founding
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
