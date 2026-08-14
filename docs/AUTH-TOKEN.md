# Per-boot local auth token

Design record for the token that gates Kettle's localhost HTTP API. Status:
**implemented** in core; this document captures who mints it, where it lives,
how viewports get it, when it rotates, and the threat model — plus the current
viewport conformance. (LAB-29.)

## Why

The core serves an HTTP API on `127.0.0.1`. Loopback is not a security boundary
on a shared machine: any local process — and, via the browser, any web page the
user visits (DNS-rebinding / CSRF against `localhost`) — can send requests to
the port. Host/Origin checks blunt the browser vector; a per-boot bearer token
adds a secret that a drive-by page and an unrelated local user do not possess.

## Design

**Who mints it.** The server, once per boot, in `_record_bind()` right after a
successful port bind:

```python
SERVER_TOKEN = secrets.token_urlsafe(32)   # 256 bits of os.urandom
```

`kettle/server.py` — one token per process. `start_server()` (tests/daemon) and
`main()` (blocking sidecar / CLI web) share `_record_bind`, so every way of
starting a core mints one.

**Where it is stored.** The discovery record `~/.cache/kettle/server.json`,
written atomically at mode **0600** (temp file + `os.replace`, then `chmod`):

```json
{ "pid": …, "port": …, "started": …, "url": "http://127.0.0.1:<port>/",
  "projects": …, "settings": …, "token": "<urlsafe-32>" }
```

0600 means only the owning Unix user can read the token. The file doubles as the
port/URL discovery record, so a viewport that can find the core can also read its
token.

**How adapters get it.**

| Surface | Mechanism |
|---|---|
| Web UI (`static/index.html`) | Server injects `<meta name="kettle-token">` into the served HTML; the page reads it and sends `X-Kettle-Token` on every `/api/` fetch. |
| CLI / TUI (`kettle-tui`) | Reads `token` from `~/.cache/kettle/server.json` and sends `X-Kettle-Token`. |
| Editor viewports (`kettle-vscode`, `kettle-desktop`) | **Should** read `token` from the same discovery record and send it. **See Conformance — currently they do not.** |
| Core circuit-breaker | `_discovery_token()` reads the record so a new boot can authenticate its ping to a live predecessor before deferring/replacing. |

**How it is enforced.** `Handler.check_request_guards(require_token=…)`:

- Host header must be loopback (`_host_allowed`);
- Origin, if present, must match the server's own origin (`_origin_allowed`);
- if `require_token`, the request must carry `X-Kettle-Token` equal to
  `SERVER_TOKEN`, compared with `hmac.compare_digest` (constant-time).

The dispatcher sets `require_token = url.path.startswith("/api/")`, so **every
`/api/` route requires the token** (including `/api/ping`); the root document and
static assets do not (they only clear Host/Origin), which is what lets the web UI
bootstrap and read the injected meta tag.

**Rotation.** New token every boot. A restart (`--replace`, crash + relaunch,
new session) mints a fresh token and overwrites the discovery record; the old
token is dead the moment the old process exits. There is no in-session rotation
and no expiry — lifetime is exactly the process lifetime.

## Threat model

In scope — the token (with Host/Origin) defends against:

- **Other local users** on a shared machine: they cannot read the 0600 record,
  so they cannot mint valid `/api/` requests.
- **Malicious web origins**: a page the user visits cannot read the token (it is
  not in the DOM of *their* origin, and CORS/Origin rules block cross-origin
  reads), so DNS-rebinding / CSRF against the localhost port is refused at the
  token gate even if Host/Origin were somehow satisfied.

Out of scope — explicitly not defended:

- **The same Unix user.** Any process running as the user can read
  `~/.cache/kettle/server.json` and act as the user. This is by design: the desk
  is that user's data; local-user compromise is out of scope.
- **Remote / multi-user.** The server binds `127.0.0.1` only; there is no
  network auth, no accounts, no TLS. Multi-user and remote access are a separate,
  larger design and remain out of scope (per the issue).

## Conformance (as of this record)

| Viewport | Sends `X-Kettle-Token`? |
|---|---|
| Web UI | ✅ meta-tag injection |
| `kettle-tui` | ✅ from discovery record |
| `kettle-vscode` | ❌ `KettleApi` sends only `Content-Type` — **all `/api/` calls 403** |
| `kettle-desktop` | ❌ `app/api.js` sends only `Content-Type` — **all `/api/` calls 403** |

The two editor viewports were not updated when the token gate landed, so against
a current core their ping (and everything else) is rejected with
`403 {code:"auth"}`. For the plugin this presents as "core couldn't launch from
the editor host" — the failed ping reads as *unreachable*, the auto-start loop
spawns cores it equally cannot reach, and it gives up. Fixing those two clients
to read the discovery token and send the header is tracked as follow-up work; it
is the implementation this design record unblocks.

## Follow-ups

- Make `kettle-vscode` and `kettle-desktop` read `token` from the discovery
  record and send `X-Kettle-Token` on every `/api/` request (ping + streams).
- Consider a shared, tested token-read helper per client so a future
  discovery-schema change updates one place.
- No token-in-URL and no env-var token: keep the secret in the 0600 file only.
