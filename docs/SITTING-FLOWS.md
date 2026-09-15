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

Route shapes, the error envelope and the NDJSON event table are in
[`API.md`](../API.md). Every `/api/` request carries `X-Kettle-Token`
([`AUTH-TOKEN.md`](./AUTH-TOKEN.md)).

---

## 0. Attach

1. **MUST** read `~/.cache/kettle/server.json` for `port` + `token` (the graphical sitting is
   served the token in a meta tag instead; that path is for browsers only).
2. **MUST** `GET /api/ping` → `app: "kettle"`, `version`, `api_version`, `desk_schema_version`,
   plus the active curator. Refuse to drive a core whose `api_version` you do not support.
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
while `founded` is false; if its queue entry is missing, the mutating
`GET /api/interview` re-files it.

### 3.5 Found Desk
1. **MUST** `POST /api/approve` on the proposal entry (response: `founding: true`).
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

---

## 4. Sweep

`POST /api/sweep {project, model?, thrust?, verbosity?}` → NDJSON. `thrust` is the user's
optional steer for this pass.

1. **SHOULD** confirm first (the reference sitting shows a dialog with the steer field, or an
   armed undo when confirmation is off).
2. **MUST** treat sweep as closing the sitting: clear the selected entry and the file surface,
   and do not let the user edit a file mid-sweep.
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

---

## 5. A chat turn

`POST /api/chat {project, id|null, message, model?}` → NDJSON.

- `id` is the selected entry or `null` for a project-level turn (for example, answering a
  question the sweep raised with no file open). **MUST** support the `null` form.
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

---

## 7. What this file does not decide

Layout, region jobs, keybindings and ritual copy: [`UI-STRUCTURE.md`](./UI-STRUCTURE.md) and
[`UI.md`](./UI.md). Capability levels and what a viewport must ship:
[`PLATFORMS.md`](./PLATFORMS.md). Wire shapes: [`API.md`](../API.md). If a sequence here and the
reference sitting disagree, the reference sitting is the evidence — fix this file or fix it.
