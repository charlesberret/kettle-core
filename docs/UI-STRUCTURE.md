# Sitting UI structure

**Authority:** this document defines the **regions, roles, and interaction model** of
the Kettle sitting. All viewports (browser, desktop, VS Code Desk, future TUI)
must map to it. Implementation details (CSS, widgets, host chrome) may differ;
structure and meaning must not.

| Companion doc | Owns |
|---------------|------|
| [`UI.md`](./UI.md) | Type hierarchy, buttons, copy workflow, theme projection |
| [`PLATFORMS.md`](./PLATFORMS.md) | Viewport capability levels and founding state |
| [`API.md`](../API.md) | Wire contract for every region’s data |
| [`SITTING-FLOWS.md`](./SITTING-FLOWS.md) | Order of calls and derived state for each flow |
| [`ARCHITECTURE.md`](../ARCHITECTURE.md) | Desk-is-files; app is a viewport |
| [`REVIEW.md`](./REVIEW.md) | Briefing for a full-tree review of current form |
| `static/index.html` | Reference **layout implementation** (browser / desktop) |
| `kettle-vscode` Desk | Reference **host-adapted** projection (editor is the host) |

If this file and a viewport disagree, **this file + the reference sitting win** —
fix the viewport or open a deliberate structure change. Do not “improve” a
viewport by importing patterns from other TUI apps (session search, three-pane
chat, command-palette-first UX) without amending this document.

---

## 1. What the sitting is

Kettle is a **review instrument**. The sitting is the human surface for one
**desk** (one registered project) during one stretch of review work:

```text
queue of prepared work  →  read / edit the file  →  rule (approve · comment)  →  sweep
                              ↑ brief + agent chat sit beside that work
```

It is **not**:

- a multi-session chat browser (no conversation sidebar, no FTS over history as chrome);
- a file manager or fuzzy finder over the project tree;
- a fleet dashboard for many agent processes;
- a second product palette or type system.

The **unit of selection** is a **queue entry** (a prepared review item with path,
brief, ask, urgency, status). The queue is **curated and short**. Navigation is
**list selection**, not search-and-filter.

---

## 2. Canonical layout (graphical sitting)

The reference sitting is **three vertical columns**, resizable, full height:

```text
┌──────────────┬──────────────────────────┬────────────────────────────┐
│ LEFT         │ MID                      │ RIGHT                      │
│              │                          │                            │
│  Queue       │  File surface            │  Desk chrome               │
│  ──────────  │  (read / edit)           │  Project · path · signals  │
│  Info        │                          │  ────────────────────────  │
│  (entry      │  floating: find,         │  Brief (ask + brief body)  │
│   metadata)  │  reading↔source          │  ────────────────────────  │
│              │                          │  Ritual                    │
│              │                          │  Approve · … · Finish batch│
│              │                          │  ────────────────────────  │
│              │                          │  Agent stream + composer   │
│              │                          │  model · context · settings│
└──────────────┴──────────────────────────┴────────────────────────────┘
```

DOM anchors in `static/index.html`:

| Column | Root id | Primary children |
|--------|---------|------------------|
| Left | `#left` | `#queue` → `#qlist`; `#meta` → `#metadl` |
| Mid | `#mid` | `#midtools`, `#findbar`, `#edwrap` / `#editor`, `#render` |
| Right | `#right` | `#desk-top` (chrome + `#desk-brief`), `#ritual`, `#commentpanel`, `#chatwrap` |

Vertical splitters: `#divQ` (queue/info), `#divBrief` / `#divDesk` (brief/ritual/chat).
Horizontal: `#divL`, `#divR`.

**Desktop** loads this same tree (with `body.desktop-shell` titlebar insets).
It does **not** own a second layout.

---

## 3. Region catalog

Each region has a **job**, **primary data**, and **explicit non-jobs**.

### 3.1 Queue (`#queue` / `#qlist`)

| | |
|--|--|
| **Job** | Show the current sitting’s review batch; select the active entry. |
| **Data** | `GET /api/queue?project=` → `entries[]` (server may enrich `diff`, comments). |
| **Row (line 1)** | Urgency **dot** + **file base name** (primary ink) + optional note dot + diff badge. |
| **Row (line 2)** | Optional `ask_type` tag + title/summary snippet (secondary). Full path on hover. |
| **Sort** | Unhandled first; then urgency high → medium → low. Handled (`approved` / `rework`) sink. |
| **Selection** | One active entry; subtle row wash (`--row-active-bg`); no left accent bar. |
| **Empty** | Founding: leave empty (work is in the agent pane). Proposing: founding-hint copy only. |
| **Keyboard** | Arrow up/down among items; Enter/Space select (reference web). |

**Not in the queue**

- No filter / search box / `/` prompt over the list.
- No project tree, no git file list, no multi-select for bulk ops.
- No chat history, tags browser, or session list.

*Rationale:* the queue is the curator’s short brief stack. If it is long enough to
need fuzzy find, the product problem is batch size or sweep cadence — not a search UI.

### 3.2 Info (`#meta`)

| | |
|--|--|
| **Job** | Structured facts about the **selected entry** (path, status, urgency, changes, …). |
| **Data** | Fields on the selected queue entry + live diffstat / word count as implemented. |
| **Chrome** | Pane title **Info**; optional **edit** for entry fields (`#metaedit`). |
| **Type roles** | Labels → `--text-label`; values → `--text-primary` (see `UI.md`). |

**Not in Info**

- Not the prose brief (that is region **Brief** on the right).
- Not chat. Not project settings.

> **Note:** older copy in `UI.md` spoke of brief/info “tabs” inside meta. The
> **live reference layout** keeps **Brief on the right** (`#desk-brief`) and
> **Info on the left**. Prefer this document + DOM over the tab wording.

### 3.3 File surface (`#mid`)

| | |
|--|--|
| **Job** | Let the user **read and edit** the entry’s file (or proposal during proposing). |
| **Modes** | **Reading** (`body.reading`, `#render`) vs **source** (`#editor` / `#edwrap`). |
| **Tools** | Floating `#midtools`: find/replace (`⌘F`), toggle reading/source (`⌘E`). |
| **Save** | `⌘S` → `POST /api/save` (when a file is open). |
| **Host rule** | In VS Code/Cursor, the **host editor replaces mid**. The Desk webview must not re-implement a second full editor. |

**Not mid’s job**

- Project picker, ritual buttons, or agent model controls (those are right-column).
- Queue navigation chrome.

### 3.4 Desk chrome (top of `#right`)

| | |
|--|--|
| **Job** | Orient: **which project**, **which file**, sitting signals. |
| **Contents** | Project label + `#proj` select; git activity strip (`#gitmap`); path (`#fname`); sitting diff; dirty · note dots. |

### 3.5 Brief (`#desk-brief`)

| | |
|--|--|
| **Job** | Deliver the curator’s packed context for the selected entry. |
| **Contents** | Ask / takeaway (`#takeaway`) + brief body (`#briefbody`). |
| **Rule** | Do **not** auto-inject the brief into chat on select — brief lives here. |
| **Empty** | When a project is bound but no entry is selected, use shared empty copy (`ui-copy` / `noEntryBriefBody`). |

### 3.6 Ritual (`#ritual`)

| Control | Meaning | API |
|---------|---------|-----|
| **Approve** | Bookmark the user’s ruling; does **not** apply or commit | `POST /api/approve` |
| **Comment** | Note for the sweep, tied to this entry | `POST /api/comment` |
| **Not this** | Set the file aside; the next sweep reads it as a sign of what the user doesn't want | `POST /api/set-aside` |
| **Finish batch** | The sweep: close the sitting (apply/assess/restock under policy) | `POST /api/sweep` (NDJSON) |

During **proposing**, Approve is the signature path to found (the label stays
**Approve**); Comment, Not this and Finish batch stay dimmed. During **founding**,
the whole ritual strip is hidden/disabled; work is interview → Draft Proposal.

**Not ritual**

- No fourth “start interview” button in the founded ritual row (VS Code: host
  commands / empty states handle unfounded desks).
- No “send” or “run agent” in the ritual row (composer is under chat).

### 3.7 Comment drawer (`#commentpanel`)

Opens under the ritual bar; Enter saves, Shift+Enter newline, Esc cancels.
Tied to the **selected entry**.

### 3.8 Agent stream (`#chatwrap`)

| | |
|--|--|
| **Job** | Conversation with the desk’s curator for this project/session; founding interview; stream of sweep/chat NDJSON. |
| **Composer** | `#chatin` — Enter sends, Shift+Enter newline. |
| **Controls** | `#agentbar`: model select, context bar, settings (opens admin / appearance). |
| **Founding** | `#foundinghead` under project chrome: skip · **Draft Proposal ✓**. Conversation in the agent pane (one mission question) — **not** a confirmation-card form. |

**Not the agent pane’s job**

- Owning desk files or queue mutations outside API streams.
- Replacing the brief region.

### 3.9 Overlays (global, not columns)

Add project, setup/curator check, sweep confirm, refound, admin/appearance,
add model/provider. Modal focus trap; Esc closes. These are **episodic**, not
persistent columns.

---

## 4. Sitting modes (body classes)

Graphical viewports derive mode from **core desk/session state**, not local invention
(`PLATFORMS.md`):

```text
none → interviewing → proposing → founded
```

| Mode | Body / chrome effects (reference) | User focus |
|------|-----------------------------------|------------|
| **Founding** (`body.founding`) | Queue empty; brief/ritual/path chrome hidden; founding head + agent chat primary | Interview in agent pane |
| **Proposing** (`body.proposing`) | Queue shows proposal hint; mid shows `DESK-PROPOSAL.md`; Approve → Found Desk | Edit proposal; chat to revise |
| **Founded sitting** | Full three columns; ritual live when an entry is selected | Work the queue |
| **`body.nofile`** | Approve/comment/find/mode dimmed — no selected entry |
| **`body.sweeping`** | Ritual and edit tools locked while sweep stream runs |

Adapters must not invent a parallel state machine.

---

## 5. Interaction model (deliberate defaults)

| Principle | Practice |
|-----------|----------|
| **Selection, not search** | Queue is a short list; open by click / arrows / Enter. |
| **Entry-centric** | Mid, brief, info, ritual, comment all bind to the **selected entry**. |
| **Brief beside the work** | Context is always visible while reading/editing — not only in chat history. |
| **Ritual is explicit** | Approve is a bookmark; Finish batch is the close. Labels and API must keep that meaning. |
| **One primary ink surface** | Queue file names + editor body use primary text; chrome stays gray (`UI.md`). |
| **Shared strings** | User-visible sitting copy from `static/ui-copy.js` only. |
| **Thin viewport** | No second desk store; discover core; honor `X-Kettle-Token` when present. |

### Keyboard (reference web — minimum set)

| Binding | Action |
|---------|--------|
| `⌘/Ctrl+S` | Save open file |
| `⌘/Ctrl+E` | Toggle reading / source |
| `⌘/Ctrl+F` | Find (in file surface) |
| Enter (chat) | Send |
| Enter (comment) | Save comment |
| Esc | Close find / comment / modal |
| Queue arrows | Move among entries |

A TUI may remap chords to terminal norms (`j`/`k`, etc.) but must preserve **region
jobs** and **ritual meanings**. Do not add queue-filter or global fuzzy-file as
default chrome without amending §3.1.

---

## 6. Viewport projections

Same structure; different hosts fold columns differently.

### 6.1 Browser / desktop (full)

All three columns in one window. Reference for region presence and ritual copy.

### 6.2 VS Code / Cursor Desk

| Canonical region | Projection |
|------------------|------------|
| Queue | Often Explorer TreeView + Desk selection sync |
| Mid (file) | **Host editor** |
| Right stack | Desk webview: header → brief → ritual → stream → composer |

Documented in `deskPanel.ts` header. Status/urgency chrome stays out of the Desk
header path line; host owns file chrome.

### 6.3 CLI (command viewport)

Not a three-column GUI. Maps **jobs** to verbs:

| Job | CLI |
|-----|-----|
| List desks | `kettle projects` |
| List queue | `kettle queue <project>` |
| Open file surface | `kettle open` / `edit` (built-in curses editor or `$EDITOR`) |
| Agent chat | `kettle chat` |
| Founding | `kettle found` (+ interview flows as documented) |
| Sweep helpers | `kettle sweep-status` / `close` / `archive` |

CLI may omit simultaneous brief+chat+editor; it must not invent a second product
semantics for approve/sweep.

### 6.4 Future terminal sitting (e.g. kettle-tui TUI)

A full-screen TUI is a **new viewport**, not a greenfield app. Required mapping:

| TUI pane | Must implement region |
|----------|----------------------|
| Left list | **Queue** (§3.1) — curated list, no filter chrome |
| Center | **File surface** and/or **Brief** (if space-constrained, tabs or stacked mid: brief over file is OK; do not drop brief permanently) |
| Right / bottom | **Ritual** + **Agent stream** + composer |
| Status line | Project id, mode, connection — not a fourth product column |

**Optional / later:** Info metadata, find-in-file, theme packs, command palette.
**Palette** is host convenience; it is **not** a substitute for visible ritual
controls on the founded sitting.

**Forbidden without structure RFC:** session sidebar, provider switcher as main chrome,
queue full-text search, multi-agent fleet grid, inventing “modes” not in §4.

---

## 7. Data binding (quick map)

| Region | Primary routes |
|--------|----------------|
| Project list | `GET /api/projects`, discovery `~/.cache/kettle/server.json` |
| Queue | `GET /api/queue?project=&mutate=0` for pure read |
| File body | `GET /api/file`, `POST /api/save` |
| Diff | `GET /api/diff`, `GET /api/diffstat` |
| Chat / interview / sweep | `POST /api/chat`, `/api/interview`, `/api/propose`, `/api/found`, `/api/sweep` (NDJSON) |
| Ritual writes | `POST /api/approve`, `POST /api/comment` |
| Identity | `GET /api/ping` (`api_version`, `desk_schema_version`) |

Capability levels: [`PLATFORMS.md`](./PLATFORMS.md).

---

## 8. Checklist — before shipping UI in any viewport

Structure

- [ ] Every visible region maps to a §3 job (or is an episodic overlay).
- [ ] Queue has **no** filter/search chrome unless this doc was amended.
- [ ] Brief is not only “whatever is in chat history.”
- [ ] Approve / Comment / Not this / Finish batch keep ritual meanings (bookmark / note / set aside / close).
- [ ] Founding / proposing / founded follow core state (§4).

Parity

- [ ] Strings from `ui-copy.js` (or generated snapshot).
- [ ] Type roles per `UI.md` (chrome gray, primary scarce).
- [ ] Urgency = color dots only, with accessible names.
- [ ] Diff badges good/warn consistent where shown.

Adapter discipline

- [ ] Talks to localhost API only for desk mutations.
- [ ] Does not invent a second desk store or palette brand.
- [ ] Declares supported `api_version` / compatibility as required by the adapter.

---

## 9. Change control

Structural changes (add/remove a column job, move brief, add queue search, change
ritual set) are **product changes**:

1. Update **this file** first.
2. Update reference `static/index.html` (and VS Code Desk if affected).
3. Note adapter impact in `PLATFORMS.md` / release notes.
4. Desktop inherits the reference sitting — do not add a sitting fork there.
5. Only then implement secondary viewports (TUI, etc.).

Cosmetic changes (spacing, theme tokens, iconography) stay in `UI.md` / themes and
do not require a structure revision.

---

## 10. Glossary (sitting)

| Term | Meaning |
|------|---------|
| **Sitting** | One stretch of human review on a desk (until sweep or abandon). |
| **Desk** | Project-local `.kettle/` state + queue the sitting attaches to. |
| **Queue entry** | One prepared review item (path, brief, ask, status, …). |
| **Brief** | Curator-packed context for an entry; lives in the Brief region. |
| **Ritual** | Explicit human controls: Approve, Comment, Not this, Finish batch. |
| **Viewport** | Thin client rendering desk state via the API. |
| **Founding** | Interview → proposal → Found Desk before a normal queue sitting. |
