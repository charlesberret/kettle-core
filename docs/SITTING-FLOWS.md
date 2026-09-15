# Sitting flows

**Authority:** this file defines the **order of calls and the state each viewport derives**
for one sitting. `API.md` owns the wire shapes; [`UI-STRUCTURE.md`](./UI-STRUCTURE.md) owns
regions and ritual meaning; this file owns the sequences between them. Extracted from the
reference sitting (`kettle/static/index.html`) and `kettle/server.py` so no viewport has to
read that JavaScript to know what to call and when.

Each step is marked:

- **MUST** — the core contract. A viewport that skips it can strand a desk or lie to the user.
- **SHOULD** — reference-sitting behaviour worth copying; a viewport may do it differently
  and say so.
- **MAY** — convenience of the reference sitting only.

**TUI marks** (kettle-tui `0619b60`, against this draft): **matched** (we do this) /
**guessed** (we reverse-engineered it; the spec now owns it) / **diverged** (we do it
differently, and why) / **absent** (not in the TUI).

Route shapes, the error envelope and the NDJSON event table are in
[`API.md`](../API.md). Every `/api/` request carries `X-Kettle-Token`
([`AUTH-TOKEN.md`](./AUTH-TOKEN.md)).

---

## 0. Attach

1. **MUST** read `~/.cache/kettle/server.json` for `port` + `token` (the graphical sitting is
   served the token in a meta tag instead; that path is for browsers only).
2. **MUST** `GET /api/ping` → `app: "kettle"`, `version`, `api_version`, `desk_schema_version`,
   plus the active curator, and keep `api_version` where a bug report can see it. `API_VERSION`
   is still `0` (deliberately pre-stable), so **SHOULD NOT** refuse an unknown value yet: warn
   and proceed. Once core reaches `1`, refuse a core whose `api_version` is above the highest
   you support (decision D4).
3. **MUST** `GET /api/projects` → `{projects, home}`.
4. **MUST** `GET /api/queue?project=<id>` for the opened desk. Pass **`?mutate=0`** when
   polling: the mutating read heals founding status, re-files a lost proposal entry and takes
   first-sight snapshots.
5. **SHOULD** `GET /api/interview?project=<id>` at the same time — that is the founding state
   (§3). Open the sitting in whichever phase it reports; never infer a second state machine.
6. **MAY** `GET /api/git/activity`, `GET /api/chatlog` (restore the transcript),
   `GET /api/settings`.

**Reconnect.** A `403 {code:"auth"}` means the core restarted and minted a new token: re-read
the discovery record and retry once. A `404` naming a missing project folder, and a
`409 {code:"queue_corrupt"}`, are **desk-local** — report them on that desk and leave the rest
of the app usable.

**TUI §0.** 1 matched (`load_discovery`). 2 **diverged** — we ping and show `version`, but we
do not refuse an unknown `api_version`. 3 matched. 4 matched (`mutate=0` on attach and every
later queue read). 5 matched (`GET /api/interview?mutate=0` on attach). 6 absent (no
git/activity, chatlog, or settings fetch). Reconnect: auth retry **matched**; queue_corrupt
desk-local **matched**; a 404 "project folder is missing" is shown as a generic `ClientError`,
not a project-list refresh.

---

## 1. Select an entry

1. **MUST** `GET /api/file?project=&path=` for the entry's `path`.
2. **MUST** treat the entry's `brief` / `ask` as the Brief region's content — never
   "whatever is in chat history".
3. **SHOULD** autosave a dirty buffer before switching (§2.1), and clear find/comment chrome.
4. **MAY** `GET /api/diff` / `GET /api/diffstat` for the sitting's diff badge; `GET /api/entry`
   for metadata editing.

A queue entry is the unit of selection. The proposal entry (`desk-proposal`) is selected the
same way but drives §3, not §2.

**TUI §1.** 1 matched (`GET /api/file`). 2 matched (brief/ask from the entry, never from
chat). 3 **diverged** — dirty buffer is a save/discard modal, not autosave. 4 **diverged** —
`v` loads `GET /api/diff` (`text` with `diff` fallback); no `/api/diffstat`, no `/api/entry`
editor. Proposal rows use the same select path and then §3.

---

## 2. Ritual

### 2.1 Save
`POST /api/save {project, path, content}`. **MUST** be the only way a viewport writes a
project file. Core records the user's authorship in the working record. A save whose path
would follow a symlink out of the project is refused with `403 {code:"unsafe_path"}`.

### 2.2 Approve
`POST /api/approve {project, id}` — a **bookmark**, never an apply or a transmit. Re-approving
is idempotent (the first date stands, one line in `approvals.log`).

The response carries `founding: true` when the approved entry is the desk proposal on an
unfounded desk. **MUST** then run §3.5 rather than treating it as an ordinary approval.

### 2.3 Comment
`POST /api/comment {project, id, text}` attaches send-back context to that entry. An empty
`text` clears the note **and retracts its history**, so a later sweep does not replay it.
`GET /api/queue` returns `comment_history` per entry (retired comments are already filtered out).

### 2.4 Sweep
§4.

**TUI §2.** Save matched (`POST /api/save`). Approve matched as a bookmark; **diverged** on
the founding fork — we route Approve to Found Desk from local `phase == "proposing"`, and do
not read `founding: true` on the approve response. Comment matched, including empty `text`
to clear. Sweep §4.

---

## 3. Founding

State comes from `GET /api/interview`:

```text
none ──register──▶ interviewing ──propose──▶ proposing ──found──▶ founded
```

**MUST** derive `founded` from the response's `founded` boolean (charter on disk **and** at
least one content entry). `has_entries` alone is **not** founded: a found run can file entries
and fail to write `PROJECT.md`. `has_charter` is reported beside it for diagnosis.

### 3.1 Register
`POST /api/projects/add {name, root, note, kit?, max_depth?}`.

- **MUST** require `note` — the user's founding sentence ("what is this, and what do you want
  from a second reader here?"). It is quoted first in the charter; core has no way to recover
  it later.
- Core refuses a root that is not under `$HOME`, is `$HOME` itself, overlaps a credential or
  agent-config folder, or contains Kettle's own settings (`400`).
- **SHOULD** land straight in the founding phase for that project (a fresh desk reports
  `status: "interviewing"` once its first interview turn runs).

### 3.2 Interview turns
`POST /api/interview {project, message, model?}` → NDJSON.

- **MUST** send an **empty** `message` for the kickoff turn. Core supplies the kickoff prompt,
  the founding role, the deterministic survey and the founding sentence on the first turn of a
  fresh interview session.
- Subsequent turns send the user's text.
- The interview is **tool-less**: expect `text` events, no `tool` events.
- **SHOULD** offer "resume" wording when re-entering an interview that already has turns; the
  reference sitting sends a one-line steer asking the curator to restate where things stand.
- Core starts a **fresh** curator session unless the stored session is already an interview, so
  a chat opened before founding cannot become the interview.

### 3.3 Draft Proposal
`POST /api/propose {project, model?}` → NDJSON. Writes `DESK-PROPOSAL.md` and files exactly one
queue entry (`desk-proposal`). Status becomes `proposing`.

- **MUST NOT** treat propose as founding. Core refuses to promote a desk to `founded` from a
  propose turn.
- **SHOULD** open the proposal file in the file surface afterwards and tell the user to edit it
  there.

### 3.4 The user edits the proposal
Ordinary §1/§2.1 file editing, plus §5 chat to revise. **MUST** keep the proposal openable
while `founded` is false.

Core re-files a lost `desk-proposal` entry at the end of `/api/propose` and after a failed
`/api/found`, so a poll-pure viewport does not have to trigger it. The mutating
`GET /api/interview` performs the same heal as a safety net (an entry lost some other way — a
hand-edited queue, an older core). A viewport that only ever polls with `mutate=0`
**SHOULD** issue one mutating read when the user explicitly refreshes an unfounded desk
(decision D1).

### 3.5 Found Desk
1. **MUST** `POST /api/approve` on the proposal entry. Its response carries `founding: true`;
   that flag is core's own answer and is preferred over a locally cached phase, which can be
   stale after another viewport acted on the same desk (decision D3).
2. **MUST** `POST /api/found {project, model?}` → NDJSON, and keep the user informed while it
   streams.
3. **MUST** re-read `GET /api/interview` when the stream ends and announce a founded desk
   **only when `founded` is true**. A stream that ended is not a founded desk.
4. If still false: say so, keep the desk in `proposing`, and let the user revise and press
   Found Desk again.
5. **SHOULD** disable Approve / Found Desk while the stream runs, so a second press cannot
   start a second founding.
6. **SHOULD** reload the queue and select the first content entry once founded.

### 3.6 Skip and refound
- **MAY** let the user open an unfounded desk as-is (session-scoped skip). Do not persist it as
  a core state; core still reports the founding phase.
- `POST /api/projects/refound {id}` resets founding state, keeps append-only records, and backs
  the desk up under `~/.cache/kettle-refound-backups/`. It is refused with
  `409 {code:"busy"}` while a curator turn streams on that desk. **SHOULD** offer to start the
  interview again afterwards rather than doing it automatically.

**TUI §3.** Founded predicate **matched** (as of `0619b60`; was **guessed** via `has_entries`).
3.1 **absent** — no `POST /api/projects/add`; new desks come from `kettle init` / the web.
3.2 kickoff empty message **matched** (was guessed). Resume-steer wording **absent**. Fresh
interview session is core-side; we do not special-case a pre-founding chat. 3.3 propose
**matched**; we then select `desk-proposal`. 3.4 **diverged** — every interview GET uses
`mutate=0`, so we never trigger core's "re-file a lost proposal entry" heal. 3.5 **matched**
(approve → `/api/found` → re-GET `founded` before announcing; streaming locks a second press;
post-found selects a content entry). 3.6 skip and refound **absent**.

---

## 4. Sweep

`POST /api/sweep {project, model?, thrust?, verbosity?}` → NDJSON. `thrust` is the user's
optional steer for this pass.

1. **SHOULD** confirm first (the reference sitting shows a dialog with the steer field, or an
   armed undo when confirmation is off).
2. **MUST** stop the user editing a file while the sweep streams: the sweep rewrites the queue
   and may archive the entry under the cursor.
   **SHOULD** also clear the selected entry and the file surface, as the reference sitting does
   — an entry left on screen through a restock may no longer exist when the stream ends.
3. **MUST NOT** start a second sweep on a desk that is already sweeping. Core also refuses:
   the stream then carries one `text` notice ("A sweep is already running for this desk") and a
   `done`.
4. Core may answer without spawning a curator at all: "Nothing to sweep — queue empty and
   quiet", or a quiet mechanical close. Both arrive as a `text` + `done` NDJSON pair.
5. **MUST** reload the queue when the stream ends (the sweep restocks it) and re-render the
   Brief region.
6. **MAY** read `<desk>/runtime/sweep-health.json` (`state: running|done|failed|idle`) to show
   that the last sweep did not finish. Core uses it to restock instead of reporting an empty
   desk as idle.
7. **MAY** auto-sweep when every queue entry is handled (off by default in the reference
   sitting).

**TUI §4.** 1 matched (confirm modal + optional steer). 2 **diverged** — ritual is locked
while `streaming`, but we do not clear the selected entry or the file surface. 3 matched
locally (`streaming` blocks a second sweep); a core idle notice would show as stream text.
4 matched (text+done). 5 matched (queue reload after the stream). 6 **absent** (we do not
read `sweep-health.json`). 7 absent.

---

## 5. A chat turn

`POST /api/chat {project, id|null, message, model?}` → NDJSON.

- `id` is the selected entry, or **absent / `null`** for a project-level turn (for example,
  answering a question the sweep raised with no file open). Core treats a missing key and an
  explicit `null` identically (`if eid:`), so either is correct (decision D2). **MUST** support
  that project-level form.
- Core injects the active-file context block on the first turn of a session and whenever the
  selected entry changed; a viewport **MUST NOT** paste its own copy of the brief into the
  message.
- **MUST** handle the event stream: `model`, `text`, `tool`, `activity`, `usage`, `error`,
  `done` (`API.md` § Streaming). A `done` may carry `error`.
- **SHOULD** render agent text as **display-only** markdown. Never turn agent output into an
  interactive form (a checkbox a click can submit) — founding is a conversation, not a card.
- **SHOULD** reload the open file when a `tool` event reports a write to it and the buffer is
  not dirty.
- **MAY** persist the transcript with `POST /api/chatlog` and restore it on attach.
- **MAY** queue interjections typed while a turn streams, and send them when it ends.

### 5.1 Context housekeeping
- `POST /api/compact` → NDJSON. **MAY** run automatically when the `usage` events show the
  context filling (the reference sitting does, above a threshold).
- `POST /api/clear-session {project}` drops the session id so the next turn starts fresh. The
  transcript stays; only the agent session resets.

**TUI §5.** Chat **diverged** on `id`: with no selected entry we **omit** the key rather than
send `id: null`. We do not paste the brief into the message (matched). Event stream: `text`
and `error` matched; `model` / `activity` / `usage` ignored; `done.error` is handled in the
shared `_relay_ndjson_event` (interview/propose/found/compact) but the chat and sweep loops
are copies and still miss `done.error`. Agent text is a plain stream, not markdown.
Reload-on-tool-write **absent**. chatlog **absent**. Interjection queue **absent**. Compact
and clear-session **matched**, both manual (palette), never automatic.

---

## 6. Errors and refusals

| Code | Status | Means | Viewport |
|---|---|---|---|
| `auth` | 403 | Token stale or missing | Re-read discovery, retry once; if the page itself was never given a token, say so |
| `curator_unavailable` | 500 | Curator CLI missing or not executable | Show the message; it names the binary and points at `kettle doctor` |
| `queue_corrupt` | 409 | `queue.json` does not parse (never overwritten by core) | Desk-local error; keep other desks usable |
| `unsafe_path` | 403 | A desk write would follow a symlink out of the project | Show it; do not retry |
| `busy` | 409 | Refound while a curator turn streams | Ask the user to wait |
| `not_found` | 404 | Unknown entry, missing file, moved project folder | Refresh the queue / project list |
| `bad_request`, `bad_json` | 400 | Malformed call | Fix the call |

**MUST** check the HTTP status **before** reading a stream: a refused streaming route returns a
JSON error body, not NDJSON. Reading it as a stream makes a failed turn look like a silent one.

A stream can also end in an `error` event with a `done` — for example the curator idle timeout
(`curator.idle_timeout_s`, default 300 s). **SHOULD** show those as agent-level failures, not
as chat text.

**TUI §6.** Auth retry **matched**. `curator_unavailable` / `queue_corrupt` / `busy` /
`unsafe_path` **matched** (`ClientError` copy). HTTP status is checked before the NDJSON
reader (matched). Stream `error` events matched on the shared relay; see §5 for the chat/sweep
copy. `not_found` for a moved project folder is not a project-list refresh (same as §0).

---

## 7. Decisions

Settled by kettle-core and kettle-tui on 2026-09-15, from the TUI's marking pass. Each is
written into the section above; they are collected here so a third viewport does not re-argue
them.

| # | Question | Decision |
|---|---|---|
| D1 | Must a viewport use the mutating `GET /api/interview` to heal a lost proposal entry? | No. Core heals at the end of propose and after a failed found. Polling stays `mutate=0`; one mutating read on an explicit refresh of an unfounded desk. |
| D2 | Omit `id` or send `id: null` on a project-level chat turn? | Either. Core treats them the same; the spec no longer implies `null` is required. |
| D3 | Local `phase == "proposing"` or the approve response's `founding: true`? | Prefer the response — it is core's answer and survives another viewport acting on the same desk. A refreshed local phase is acceptable, not preferred. |
| D4 | Refuse an unknown `api_version`? | Not while it is `0` (pre-stable): read it, show it, proceed. Refuse above your supported maximum once core reaches `1`. |

Open, deliberate divergences (recorded, not faults): the TUI's dirty-buffer modal instead of
autosave, its plain-text agent stream instead of display markdown (the P4 rule it must keep is
*never interactive*), and no chatlog, interjection queue or auto-compact.

## 8. What this file does not decide

Layout, region jobs, keybindings and ritual copy: [`UI-STRUCTURE.md`](./UI-STRUCTURE.md) and
[`UI.md`](./UI.md). Capability levels and what a viewport must ship:
[`PLATFORMS.md`](./PLATFORMS.md). Wire shapes: [`API.md`](../API.md). If a sequence here and the
reference sitting disagree, the reference sitting is the evidence — fix this file or fix it.
