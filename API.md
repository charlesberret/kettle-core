# Setsweep HTTP API

Localhost contract for viewports (web UI, desktop sidecar, VS Code/Cursor plugin, future hosts).
Authoritative implementation: `server.py`. Contract tests: `test_server.py`.

**Base:** `http://127.0.0.1:<port>/` — default port **4242**. Desktop may use an ephemeral port; see Discovery.

**Conventions**

| Rule | Detail |
|------|--------|
| Bind | `127.0.0.1` only |
| JSON keys | `snake_case` |
| Mutations | **POST** only (no PUT/PATCH/DELETE) |
| Errors | `{ "error": "<string>" }` with 400 / 403 / 404 / 500 |
| Project scope | **`project` is required** on every project-scoped route (query or body). Omitting it returns 400 — it no longer defaults to the first registry entry. |
| File fence | `safe_path()` — registered roots (+ optional `SETSWEEP_ALLOWED_ROOTS`) |

---

## Discovery & identity

### `GET /api/ping`

```json
{
  "app": "setsweep",
  "pid": 12345,
  "port": 4242,
  "started": "2026-07-11T14:00:00-0400",
  "projects": "/path/to/projects.json",
  "settings": "/path/to/settings.json",
  "curator": { "provider": "claude", "command": "claude", "command_resolved": "...", "command_exists": true, "models": {} }
}
```

### `GET /api/curator/catalog`

Single source of truth for desk/settings model UIs:

```json
{
  "providers": [{ "id": "claude", "label": "Claude Code", "command": "claude", "command_exists": true, "hint": "…", "stream": "stream-json" }],
  "models": [{ "id": "sonnet", "provider": "claude", "label": "Sonnet", "blurb": "…", "good_for": ["setup","chat"], "effort_supported": true }],
  "models_by_provider": { "claude": ["sonnet", "opus", "haiku", "fable"] },
  "efforts_by_provider": { "claude": [{ "id": "high", "label": "high" }] },
  "defaults_by_provider": { "claude": { "setup": "sonnet", "chat": "sonnet" } },
  "menu": { "claude": ["sonnet", "opus", "haiku"] },
  "visible": [{ "id": "sonnet", "provider": "claude", "ready": true, "forced": false }],
  "active": { "provider": "claude", "command": "claude", "models": {}, "effort": "default" }
}
```

- `menu` = patron checkmarks (`settings.curator.menu`); seeded to Claude sonnet/opus/haiku when missing.
- `visible` = checked ∩ CLI-on-PATH, always including the active chat model (`forced: true` when needed).

- Set on **every** bind path (`start_server` and `main` / sidecar) via `_record_bind`.
- Informational cache: `~/.cache/setsweep/server.json` — `{ pid, port, started, url, projects, settings }`. Ping is authoritative.
- Circuit-breaker: a second launch on 4242 defers unless the predecessor is stale or `--replace` is passed.

### Registry paths (which desk am I talking to?)

Resolution order (`resolve_projects_path`):

1. `$DESK_PROJECTS` — explicit (desktop sidecar always sets this)
2. User registry if it exists — macOS `~/Library/Application Support/Setsweep/projects.json`, else `~/.config/setsweep/projects.json`
3. Repo-local `<setsweep-core>/projects.json` if present (dev checkout)
4. Otherwise the user path (first write creates the shared registry)

Desktop always points `DESK_PROJECTS` at Application Support. After the `.app` has run once, CLI `setsweep` without an override prefers that same file when present — one desk across viewports.

`GET /api/ping` and `GET /api/projects` expose the live path (`projects` / `registry`).

### Port discovery (multi-viewport)

| Viewport | Port behavior |
|----------|---------------|
| CLI `setsweep --web` | Prefers **4242** (circuit-breaker / `--replace`) |
| Desktop `.app` | Prefers **4242** when free; otherwise ephemeral |
| Plugin | Tries `setsweep.baseUrl` → `server.json` → `:4242`, each validated by ping |

When desktop falls back to an ephemeral port, the plugin finds it via `server.json` (last successful bind). Prefer one live core when possible — two desks (repo registry vs Application Support) can diverge.

### Side-effecting GETs

`GET /api/queue` and `GET /api/interview` heal founding status and (queue) create snapshots by default. Pass **`?mutate=0`** for a pure read (plugin polling).

### Founding state machine

| `status` | Meaning |
|----------|---------|
| `none` | No session / not started |
| `interviewing` | Founding interview in progress (chat, read-only) |
| `proposing` | `DESK-PROPOSAL.md` drafted; patron edits/approves |
| `founded` | Curator filed ≥1 *content* queue entry (proposal alone does not count) |

`GET /api/interview` also returns:

- `has_session` — project session id present
- `has_entries` / `entry_count` — **content** queue items only (**available under `mutate=0`**)
- `has_proposal` / `proposal_path` — desk proposal on disk or queued

Rule: **content entries on disk ⇒ desk is founded**. A sole `desk-proposal` entry keeps status
`proposing`. Prefer `has_entries || status === "founded"` in viewports.

Flow: `POST /api/interview` → `POST /api/propose` (finish) → patron edits → `POST /api/approve`
on the proposal (`founding: true`) → `POST /api/found` (digest proposal + first batch).

Idempotency: `POST /api/interview`, `/api/propose`, `/api/found`, and `/api/bootstrap` short-circuit
with an NDJSON notice when the desk is already `founded`, or when `/api/found`/`/api/bootstrap` can
heal from existing content entries. Use `POST /api/projects/refound` to start over.

### Diff responses

| Route | Canonical key | Legacy alias |
|-------|---------------|--------------|
| `GET /api/diff` | `text` (string) | `diff` (same string) |
| `GET /api/diffstat` | `stat` (`{added,removed}\|null`) | `diff` (same object) |

Prefer `text` / `stat` in new clients.

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
| `usage` | `context`, `peak`, `window`, … | Live context meter |
| `done` | `cost?`, `ctx?`, `usage?`, `error?` | Turn finished |
| `error` | `s` | Process / parse failure |

**Streaming routes:** `POST /api/chat`, `/api/compact`, `/api/sweep`, `/api/bootstrap`, `/api/interview`, `/api/propose`, `/api/found`.

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
| `interview` | founding interview (`/api/interview`) | no | Read · Glob · Grep + read-only shell |
| `chat` | — (reserved) | yes (`acceptEdits`) | Read/Glob/Grep/Edit/Write + narrow shell |
| `agent` | review chat (`/api/chat`, `setsweep chat`) | yes (`acceptEdits`) | Edit/Write + everyday shell kit (`mv`/`cp`) |
| `sweep` | founding/found, sweep (`/api/found`, `/api/sweep`, `setsweep found`) | yes (`acceptEdits`) | Edit/Write + `mkdir`/`mv`/`cp`/`rm`/`tee` |

### What a tier is — and is not

A tier is an **allowlist of tool names**. It constrains *which* binaries a turn may run. It
does **not** constrain *where* those binaries write: `rm`, `mv`, `cp`, and `tee` all take
arbitrary paths, as do `sed` and `awk` in the `agent` tier. So every write-bearing tier is
**trusted, not fenced** — the project-root boundary is a convention the prompts ask agents to
respect, not a boundary the system enforces.

Read that plainly: a curator turn *could* write outside its project root. Nothing today stops
it. `safe_path` fences Setsweep's own **HTTP file routes** (`/api/file`, `/api/save`), which is
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

| Provider | `read_only_tier` | `tool_allowlist` | `resume` | `effort` | `fenced_writes` |
|----------|:---:|:---:|:---:|:---:|:---:|
| claude   | ✅ | ✅ | ✅ | ✅ | ✅ |
| cli      | ✅ | ✅ | ✅ | ✅ | ✅ |
| chatgpt (codex) | ✅ (`--sandbox read-only`) | ❌ (sandbox, not allowlist) | ✅ | ✅ | ✅ (`workspace-write`) |
| gemini   | ✅ (`--approval-mode plan`) | ❌ | ✅ | ❌ (no effort flag) | ✅ |
| grok     | ❌ (`--always-approve --allow Bash`) | ❌ | ✅ | ✅ | ❌ (bypassPermissions + open Bash) |

`read_only_tier` is the load-bearing one: the founding interview (`/api/interview`) runs the
read-only tier and is the trust ceremony.

**Enforcement.** When a read-only turn is requested and the active provider's
`read_only_tier` is `false`, the route **refuses pre-stream** with

```
HTTP 409  { "error": "read_only_unavailable", "provider": "...", "message": "...", "options": [...] }
```

The stream never starts (viewports show a normal error, not a hung turn). To proceed anyway,
set `curator.allow_unfenced_readonly: true` in settings — the turn then runs and its stream
opens with a `[read-only downgrade]` notice. For `provider: claude` (the default) this
enforcement is a strict no-op. Unknown providers are treated as the weakest case (refused).

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

### Tier 2 — full sitting

| Method | Path | Mode |
|--------|------|------|
| GET | `/api/file` | JSON — `path` + `project` required |
| POST | `/api/save` | JSON — `path`/`content` required; `project` optional (lineage only) |
| GET/POST | `/api/chatlog` | JSON |
| POST | `/api/chat` | **NDJSON** |
| POST | `/api/compact` | **NDJSON** |
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
| `/api/open-link` | macOS `open -t`; 404 uses `{ ok: false, error }` |

---

## Stability notes (consistency backlog)

1. Success envelopes still vary (`{ok}` vs bare resource). `POST /api/projects/add` returns `{ ok, project, home, …flat fields }`.
2. Legacy `diff` key on both `/api/diff` and `/api/diffstat` remains for back-compat; new clients should use `text` / `stat`.
3. Errors are uniformly `{ "error": string }`.
4. Two cores with different registries remain possible if `$DESK_PROJECTS` differs — check `ping.projects` before assuming a shared desk. Legacy `diff` aliases on `/api/diff` and `/api/diffstat` remain for back-compat; prefer `text` / `stat`.
