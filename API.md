# Kettle HTTP API

Localhost contract for viewports (web UI, desktop sidecar, VS Code/Cursor plugin, future hosts).
Authoritative implementation: `server.py`. Contract tests: `tests/test_server.py`.

**Base:** `http://127.0.0.1:<port>/` — default port **4242**. Desktop may use an ephemeral port; see Discovery.

**Conventions**

| Rule | Detail |
|------|--------|
| Bind | `127.0.0.1` only |
| Auth | Every `/api/` request requires header `X-Kettle-Token` (per-boot token from `~/.cache/kettle/server.json`) |
| Host | `Host` must be `127.0.0.1[:port]` or `localhost[:port]` — else 403 |
| Origin | If `Origin` is present, it must be the server's own origin — else 403 |
| JSON keys | `snake_case` |
| Mutations | **POST** only (no PUT/PATCH/DELETE) |
| Errors | `{ "error": "<string>", "code": "<slug>" }` with 400 / 403 / 404 / 500 (`str(e)`, never `repr(e)`) |
| Project scope | **`project` is required** on every project-scoped route (query or body). Omitting it returns 400 — it no longer defaults to the first registry entry. |
| File fence | `safe_path()` — registered roots (+ optional `KETTLE_ALLOWED_ROOTS`) |

---

## Discovery & identity

### `GET /api/ping`

```json
{
  "app": "kettle",
  "version": "0.2.0",
  "api_version": 0,
  "desk_schema_version": 0,
  "pid": 12345,
  "port": 4242,
  "started": "2026-07-11T14:00:00-0400",
  "projects": "/path/to/projects.json",
  "settings": "/path/to/settings.json",
  "curator": { "provider": "claude", "command": "claude", "command_resolved": "...", "command_exists": true, "models": {} }
}
```

`version` is the core package version single-sourced from `pyproject.toml`.
`api_version` identifies the localhost HTTP/NDJSON contract;
`desk_schema_version` identifies the durable `.kettle/` file format. The
contract versions are integers. Version `0` means pre-stable: viewports should
still declare which values they support and report skew clearly instead of
guessing at an unfamiliar route or file shape. A move to `1` is the explicit
compatibility promise.

### `GET /api/themes`

Color theme catalog for the sitting Appearance menu, desktop shell, and CLI
parity. Packs are host-neutral JSON under `static/themes/` plus the user themes
directory (see `docs/THEMES.md`).

```json
{
  "default": "kettle",
  "user_dir": "/Users/you/Library/Application Support/Kettle/themes",
  "themes": [
    { "id": "kettle", "label": "Kettle", "marquee": true, "source": "bundled" },
    { "id": "nord", "label": "Nord", "marquee": false, "source": "bundled" }
  ]
}
```

Query `full=1` includes a `packs` object mapping each id to the web-shaped
preset (`dark` / `light` with `--ansi-N` colors and role maps).

### `GET /api/themes/<id>`

One pack in web-shaped form (`label`, `dark`, `light`, `marquee`, `source`).
Invalid ids return 400; missing packs return 404.

### `POST /api/themes/install`

Install a host-neutral theme pack into the user themes directory (same path the
CLI reads). Body is the pack object (`schema_version`, `id`, `label`, `dark`,
`light`, …).

```json
{ "ok": true, "id": "my-theme", "label": "My Theme", "path": "…/themes/my-theme.json", "pack": { "…": "web-shaped" }, "catalog": { "…": "metadata" } }
```

Validation errors return 400.

### `GET /api/curator/catalog`

Single source of truth for desk/settings model UIs:

```json
{
  "providers": [{ "id": "claude", "label": "Claude Code", "command": "claude", "command_exists": true, "hint": "…", "stream": "stream-json" }],
  "models": [{ "id": "sonnet", "provider": "claude", "label": "Sonnet", "blurb": "…", "good_for": ["setup","chat"], "effort_supported": true }],
  "models_by_provider": { "claude": ["fable", "haiku", "opus", "sonnet"] },
  "efforts_by_provider": { "claude": [{ "id": "high", "label": "high" }] },
  "defaults_by_provider": { "claude": { "setup": "sonnet", "chat": "sonnet" } },
  "menu": { "claude": ["haiku", "sonnet", "opus"] },
  "visible": [{ "id": "sonnet", "provider": "claude", "ready": true, "forced": false }],
  "active": { "provider": "claude", "command": "claude", "models": {}, "effort": "default" }
}
```

- `menu` = user checkmarks (`settings.curator.menu`); seeded to Claude sonnet/opus/haiku when missing.
- `models_by_provider` / `visible` model order = A–Z by display label within each provider.
- `visible` = checked ∩ CLI-on-PATH only (`forced` remains on the wire as always `false`; the active chat model is no longer force-included).

### `GET /api/git/activity?project=<id>&weeks=auto`

Local activity heatmap for the project root (desk chrome strip next to the
project selector). Implementation: [`gitmap.py`](./gitmap.py).

| Pin | Choice |
|-----|--------|
| Root | Registered project `root` only (no parent walk-up) |
| Source | **`git`** when the root is a work tree (commit heatmap); else **`mtime`** (files by last-modified day — Seafile / notes / System trees) |
| Window | **Adaptive** by default (history age → 2–26 weeks). Pass `weeks=N` to force fixed. |
| Grain | `day` when dense; `week` (one bar per week) when sparse / young |
| Week start | **Sunday** (GitHub classic) for day grain |
| Git scope | `git log --all`, all authors |
| mtime walk | Skips `.kettle` / `.git` / `node_modules` / venvs / build noise; caps at 12k files |
| Levels | 0–7 in **sevenths** of full (1 commit or 1 file-touch / 1 active day = 1/7); quieter of absolute × relative |
| Network | None |

```json
{
  "ok": true,
  "git": true,
  "source": "git",
  "weeks": 8,
  "grain": "week",
  "rows": 1,
  "adaptive": true,
  "dow_start": 0,
  "first_date": "2026-06-01",
  "last_date": "2026-07-28",
  "repo_first": "2026-06-03",
  "total": 12,
  "max": 4,
  "cells": [
    { "date": "2026-06-01", "date_end": "2026-06-07", "count": 2, "level": 2 }
  ]
}
```

Non-git example (`source: "mtime"`): `count` is files whose mtime falls on that day/week;
UI paints the strip with the link (blue) wash instead of good (green).

- Omit `weeks` / `weeks=auto` → adaptive. `weeks=4` → fixed 4-week window.
- Day grain: `rows=7`, cells column-major (week × weekday). Week grain: `rows=1`, one cell per week.
- Restart the server after updating `gitmap.py` / `py-modules`.

- Set on **every** bind path (`start_server` and `main` / sidecar) via `_record_bind`.
- Discovery cache: `~/.cache/kettle/server.json` (mode **0600**) — `{ pid, port, started, url, projects, settings, token }`.
  Viewports and CLI read `token` and send it as `X-Kettle-Token` on every `/api/` call. Ping remains the identity authority.
- The reference web UI receives the token via a served `<meta name="kettle-token">` injection (same-origin; zero user-visible change).
- Circuit-breaker: a second launch on 4242 defers unless the predecessor is stale or `--replace` is passed.

### Registry paths (which desk am I talking to?)

Resolution order (`resolve_projects_path`):

1. `$DESK_PROJECTS` — explicit (desktop sidecar always sets this)
2. Kettle user registry if it exists — macOS `~/Library/Application Support/Kettle/projects.json`, else `~/.config/kettle/projects.json`
3. Existing legacy Setsweep user registry, used in place without splitting state
4. Repo-local `<kettle-core>/projects.json` if present (development checkout)
5. Otherwise the Kettle user path (first write creates the shared registry)

Desktop always points `DESK_PROJECTS` at Application Support. After the `.app` has run once, CLI `kettle` without an override prefers that same file when present — one desk across viewports.

`GET /api/ping` and `GET /api/projects` expose the live path (`projects` / `registry`).

### Port discovery (multi-viewport)

| Viewport | Port behavior |
|----------|---------------|
| CLI `kettle --web` | Prefers **4242** (circuit-breaker / `--replace`) |
| Desktop `.app` | Prefers **4242** when free; otherwise ephemeral |
| VS Code / Cursor | Tries `kettle.serverUrl` → `server.json` → `:4242`, each validated by ping |

When desktop falls back to an ephemeral port, the plugin finds it via `server.json` (last successful bind). Prefer one live core when possible — two desks (repo registry vs Application Support) can diverge.

### Side-effecting GETs

`GET /api/queue` and `GET /api/interview` heal founding status and (queue) create snapshots by default. Pass **`?mutate=0`** for a pure read (plugin polling).

### Founding state machine

| `status` | Meaning |
|----------|---------|
| `none` | No session / not started |
| `interviewing` | Founding interview in progress (tool-less chat over core survey) |
| `proposing` | `DESK-PROPOSAL.md` drafted; user edits/approves |
| `founded` | `PROJECT.md` (the charter) exists **and** the queue holds ≥1 *content* entry (the proposal alone does not count) |

`GET /api/interview` also returns:

- `founded` — the founded predicate above, as a boolean. **Viewports use this.**
- `has_charter` — `PROJECT.md` exists
- `has_session` — project session id present
- `has_entries` / `entry_count` — **content** queue items only (**available under `mutate=0`**).
  Entries alone do not mean founded: a found run can file entries and fail to write the charter.
- `has_proposal` / `proposal_path` — desk proposal on disk or queued

A sole `desk-proposal` entry keeps status `proposing`. While proposing, only a founding step
(`POST /api/found`, `POST /api/bootstrap`, `kettle found`) may promote the desk to `founded` —
a propose turn or a queue read never does. When `DESK-PROPOSAL.md` exists on an unfounded desk
but its queue entry is missing (a failed Found Desk, or a propose turn that wrote no entry), the
mutating `GET /api/interview` re-files it.

Flow: `POST /api/interview` → `POST /api/propose` (finish) → user edits → `POST /api/approve`
on the proposal (`founding: true`) → `POST /api/found` (digest proposal + first batch) → check
`GET /api/interview` `founded` before announcing success. `/api/interview` starts a fresh
session (with the founding role, survey and sentence) unless the stored session is already an
interview.

Idempotency: `POST /api/interview`, `/api/propose`, `/api/found`, and `/api/bootstrap` short-circuit
with an NDJSON notice when the desk is already `founded`, or when `/api/found`/`/api/bootstrap` can
heal from existing content entries. Use `POST /api/projects/refound` to start over.

### Diff responses

| Route | Canonical key | Legacy alias |
|-------|---------------|--------------|
| `GET /api/diff` | `text` (string) | `diff` (same string) |
| `GET /api/diffstat` | `stat` (`{added,removed}\|null`) | `diff` (same object) |

Prefer `text` / `stat` in new clients. Unknown `id` values return **404**
`{ "error": "unknown entry id: …", "code": "not_found" }` (not an empty success).

---

## Auth & request guards

Every route under `/api/` requires:

```
X-Kettle-Token: <token from ~/.cache/kettle/server.json>
```

Missing or wrong token → **403** `{ "error": "…", "code": "auth" }` with a short hint.
Static assets (`/`, `/index.html`, scripts, fonts) do not require the token.

Defense in depth on **all** requests (including static):

| Check | Reject when | Code |
|-------|-------------|------|
| `Host` | not `127.0.0.1[:port]` / `localhost[:port]` | `bad_host` |
| `Origin` | header present and not `http://127.0.0.1:<port>` / `http://localhost:<port>` | `bad_origin` |

Absent `Origin` (curl, native clients) is allowed.

### Error envelope

Handler failures use `{ "error": "<str(e)>", "code": "<slug>" }`:

| Situation | Status | `code` |
|-----------|--------|--------|
| Malformed JSON body | 400 | `bad_json` |
| Missing / unknown project or field | 400 | `bad_request` |
| Auth / Host / Origin | 403 | `auth` / `bad_host` / `bad_origin` |
| Missing file (incl. POST `/api/save`) | 404 | `not_found` |
| Unhandled exception | 500 | `internal` |

Never `repr(e)` in response bodies.

---

## Response modes

### JSON

Most routes return `application/json`.

Success shapes vary today (see Stability notes). Prefer:

- Mutations: `{ "ok": true, ... }`
- Resources: bare object or `{ "projects": [...] }` as documented per route

### NDJSON streams

`Content-Type: application/x-ndjson` — **not** a single JSON object. Clients must read line-by-line.

| Event `t` | Fields | Meaning |
|-----------|--------|---------|
| `model` | `s`, `session?` | Model / session id |
| `text` | `s` | Assistant text chunk |
| `tool` | `s`, `tool?`, `path?` | Tool use hint |
| `activity` | `s`, `kind?` | Coarse working-state hint for chrome (for example `thinking…`); never provider reasoning text |
| `usage` | `context`, `peak`, `window`, … | Live context meter |
| `done` | `cost?`, `ctx?`, `usage?`, `error?` | Turn finished |
| `error` | `s` | Process / parse failure |

**Streaming routes:** `POST /api/chat`, `/api/compact`, `/api/sweep`, `/api/refresh-briefs`, `/api/bootstrap`, `/api/interview`, `/api/propose`, `/api/found`.

Every established NDJSON stream ends with exactly one terminal `done` event. Failures
emit `error` immediately before `done`; no event follows `done`. If the curator process
cannot be spawned, the route fails before streaming with one JSON 500 response instead.
The server kills a curator that emits no normalized event for
`settings.curator.idle_timeout_s` seconds (default 300) and closes it as
`error` → `done`. A client disconnect also kills the curator process.

---

## Tool tiers

Every agentic turn — HTTP route or CLI — runs under one abstract **tool tier**, single-sourced
in `runtime.TOOL_TIERS` and mapped to each provider's CLI dialect by `runtime.tools_argv`.
There is no second copy in `server.py`; `build_turn_cmd` (→ `runtime.build_argv`) is the only
path that arms a turn.

| Tier | Used by | Write? | Powers (abstract) |
|------|---------|--------|-------------------|
| `interview` | founding interview (`/api/interview`) | no | **none** (tool-less; core survey snapshot) |
| `chat` | — (reserved) | yes (`acceptEdits`) | Read/Glob/Grep/Edit/Write + narrow shell |
| `agent` | review chat (`/api/chat`, `kettle chat`) | yes (`acceptEdits`) | Edit/Write + everyday shell kit (`mv`/`cp`) |
| `sweep` | founding/found, sweep (`/api/found`, `/api/sweep`, `kettle found`) | yes (`acceptEdits`) | Edit/Write + `mkdir`/`mv`/`cp`/`rm`/`tee` |

### What a tier is — and is not

A tier is an **allowlist of tool names**. It constrains *which* binaries a turn may run. It
does **not** constrain *where* those binaries write: `rm`, `mv`, `cp`, and `tee` all take
arbitrary paths, as do `sed` and `awk` in the `agent` tier. So every write-bearing tier is
**trusted, not fenced** — the project-root boundary is a convention the prompts ask agents to
respect, not a boundary the system enforces.

Read that plainly: a curator turn *could* write outside its project root. Nothing today stops
it. `safe_path` fences Kettle's own **HTTP file routes** (`/api/file`, `/api/save`), which is
a different surface from the tools a spawned curator CLI holds.

`python`/`python3` were removed from the `sweep` tier on 2026-07-20 — no prompt ever referenced
them and an interpreter is the widest possible escape — but that narrowed the hole rather than
closing it. Closing it needs an OS-level sandbox around the curator process; that work is
tracked as [brief 19](docs/briefs/19-enforce-the-fence.md) and named as a product ambition in
[`ROADMAP.md`](ROADMAP.md).

### Per-provider capability matrix

A tier is only as real as the provider's CLI makes it. These booleans (source:
`runtime.PROVIDER_CAPABILITIES`, surfaced on `/api/ping` `curator.capabilities` and
`/api/curator/catalog` `active.capabilities` + each `providers[]` entry) state what each
provider **actually** guarantees under the argv `runtime.tools_argv` builds:

| Provider | `read_only_tier` (interview) | `tool_allowlist` | `resume` | `effort` | `fenced_writes` (write tiers) |
|----------|:---:|:---:|:---:|:---:|:---:|
| claude   | ✅ tool-less (`--permission-mode plan`) | ✅ | ✅ | ✅ | ✅ |
| cli      | ✅ tool-less (`--permission-mode plan`) | ✅ | ✅ | ✅ | ✅ |
| chatgpt (codex) | ✅ (`--sandbox read-only`) | ❌ (sandbox, not allowlist) | ✅ | ✅ | ✅ (`workspace-write`) |
| gemini   | ✅ (`--approval-mode plan`) | ❌ | ✅ | ❌ (no effort flag) | ✅ |
| grok     | ✅ tool-less (`--permission-mode plan`, no Bash) | ❌ | ✅ | ✅ | ❌ (bypassPermissions + open Bash on chat/sweep) |

**Founding interview (`/api/interview`)** is the trust ceremony and is **tool-less for every
provider**: core runs a deterministic survey (`survey.py` → `.kettle/runtime/survey.json`)
and injects it into the first turn. The curator rephrases that snapshot into a short
conversation (one mission question in prose — no confirmation card, no shell, no writes).
Users never see provider capability essays for founding. Register requires a founding
sentence; a desk is founded only with `PROJECT.md` **and** a content queue entry.

**Legacy / optional enforcement.** `read_only_unavailable` (HTTP 409) remains for callers that
request a shell-bearing read-only posture from a provider that cannot guarantee it, unless
`curator.allow_unfenced_readonly: true` (stream opens with a `[read-only downgrade]` notice).
`/api/interview` does not use that path.

---

## Route tiers

### Tier 0 — lifecycle

| Method | Path | Notes |
|--------|------|-------|
| GET | `/api/ping` | Identity beacon |

### Tier 1 — plugin MVP

| Method | Path | `project` | Notes |
|--------|------|-----------|-------|
| GET | `/api/projects` | — | `{ projects, home, registry }` |
| GET | `/api/queue` | required | Side effects: snapshots, founded healing |
| POST | `/api/approve` | required | Bookmark only — not the commit |
| POST | `/api/comment` | required | |
| POST | `/api/sweep` | required | **NDJSON** — mechanical close-kit first when quiet; accrue-only or full judgment prompt otherwise |
| POST | `/api/refresh-briefs` | required | **NDJSON** — rewrite `brief` + `ask` on the current queue only (cold re-entry standard; no archive/restock) |

### Tier 2 — full sitting

| Method | Path | Mode |
|--------|------|------|
| GET | `/api/file` | JSON — `path` + `project` required |
| POST | `/api/save` | JSON — `path`/`content` required; `project` optional (lineage only) |
| GET/POST | `/api/chatlog` | JSON |
| POST | `/api/chat` | **NDJSON** |
| POST | `/api/compact` | **NDJSON** |
| POST | `/api/refresh-briefs` | **NDJSON** — current-queue brief rewrite only |
| POST | `/api/clear-session` | JSON |
| GET/POST | `/api/settings` | JSON — POST deep-merges `curator` / `agents` / `curator.menu` / `egress` / `admin` |

Settings groups added for public installs (brief 10):

- `egress.routes` — map of egress kind → route hint string. Product defaults are
  neutral (`peers`, `escalation`, `launch`, `domain`, `approval` → `peers`). Personal
  fleet names belong here, not in code.
- `admin.fleet_panels` — boolean, default false. When true, `/api/admin` includes
  sentinel / desk-events / watcher beacon. Optional persona-family scan runs only when
  `admin.persona_family_relpath` is also set (relative path under a project root).
| GET | `/api/curator/catalog` | Canonical model catalog, menu checkmarks, provider readiness, `visible` desk list |

### Tier 3 — founding

| Method | Path | Mode |
|--------|------|------|
| GET | `/api/interview` | JSON status |
| POST | `/api/interview` | **NDJSON** (read-only chat phase) |
| POST | `/api/propose` | **NDJSON** (finish → write `DESK-PROPOSAL.md` + queue entry) |
| POST | `/api/found` | **NDJSON** (after proposal approve: digest + content batch) |
| POST | `/api/bootstrap` | **NDJSON** (legacy one-shot; CLI / API) |
| POST | `/api/projects/add` | JSON |

### Tier 4 — desk admin

Kits, lineage (`/api/lineage`, resolve/accept/bind), projects edit/delete/refound, `/api/entry`, `/api/diff`, `/api/diffstat`, `/api/admin`.

**Diff caveat:** `/api/diff` returns `{ "diff": "<unified text>" }`; `/api/diffstat` returns `{ "diff": { "added", "removed" } | null }` — same key, different types.

### Tier 5 — host-specific / experimental

| Path | Notes |
|------|-------|
| `/api/open-link` | macOS `open -t`; 404 uses `{ "error": "…", "code": "not_found" }` (no `ok: false`) |

---

## Stability notes (consistency backlog)

1. Success envelopes still vary (`{ok}` vs bare resource). `POST /api/projects/add` returns `{ ok, project, home, …flat fields }`.
2. Legacy `diff` key on both `/api/diff` and `/api/diffstat` remains for back-compat; new clients should use `text` / `stat`.
3. Errors are `{ "error": string, "code": string }` on handler failure paths (`str(e)`, never `repr(e)`). Some older hand-written 4xx responses may still omit `code`.
4. Two cores with different registries remain possible if `$DESK_PROJECTS` differs — check `ping.projects` before assuming a shared desk. Legacy `diff` aliases on `/api/diff` and `/api/diffstat` remain for back-compat; prefer `text` / `stat`.
