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
| Web UI (`static/index.html`) | Server injects `<meta name="kettle-token">` into the served HTML **only when the connecting socket belongs to the server's own Unix user** (see *Who gets the page's token*); the page reads it and sends `X-Kettle-Token` on every `/api/` fetch. |
| CLI / TUI (`kettle-tui`) | Reads `token` from `~/.cache/kettle/server.json` and sends `X-Kettle-Token`. |
| Editor viewports (`kettle-vscode`, `kettle-desktop`) | `kettle-vscode` reads `token` from the discovery record itself and sends it. `kettle-desktop`'s live sitting is the served `static/index.html` (same-origin), so it inherits the meta-tag path above; the shell also exposes an IPC bridge for the token, currently unused by the live renderer. **See Conformance.** |
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

**Who gets the page's token.** Because `GET /` needs no token, anything that can reach
loopback could once read the token out of the page — including another Unix user's
process, which defeats the 0600 record. The server now looks up the owner of the
*client* socket before injecting the meta tag (`server.peer_is_own_user`):

- **macOS / BSD:** `lsof -nP -a -iTCP@<client-host>:<client-port> -Fpun`, taking the
  process whose socket has that address as its *local* end. `lsof` run as the user
  cannot list other users' processes, so another user's client is simply not found.
- **Linux:** the matching row of `/proc/net/tcp` and its `uid` column.

The token goes into the page only when that uid equals the server's. Otherwise the page
loads without it: every `/api/` call returns `403 auth`, and the sitting says it could not
confirm the browser runs as the user. The lookup costs one `lsof` call per page load on
macOS (~0.1 s). On a platform where the owner cannot be determined, set
`KETTLE_SKIP_PEER_CHECK=1` to restore the old behaviour knowingly. The Electron shell and
any browser the user opens run as the user, so nothing changes for them; `kettle-vscode`
never loads `/`.

**Rotation.** New token every boot. A restart (`--replace`, crash + relaunch,
new session) mints a fresh token and overwrites the discovery record; the old
token is dead the moment the old process exits. There is no in-session rotation
and no expiry — lifetime is exactly the process lifetime.

## Threat model

In scope — the token (with Host/Origin) defends against:

- **Other local users** on a shared machine: they cannot read the 0600 record, and the
  served page withholds the token from a socket they own, so they cannot mint valid
  `/api/` requests.
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
| `kettle-vscode` | ✅ `KettleApi` (`src/api.ts`) reads `token` fresh from `~/.cache/kettle/server.json` on every request and sends `X-Kettle-Token` |
| `kettle-desktop` | ✅ (indirect) — the shipped sitting is core's own `static/index.html`, loaded same-origin off the sidecar, so it gets the server-injected `<meta name="kettle-token">` and sends the header exactly like the Web UI. `main.js`/`preload.js` also expose an IPC bridge (`window.kettle.getCoreToken`) that reads the same discovery record, but as of this record the live renderer does not call it — the only caller is the retired `legacy/v2-scaffold/app.js` scaffold. |

`kettle-vscode` was updated to read the discovery token and send it (closing the gap
this record originally flagged). `kettle-desktop` never needed the bridge for its
current, minimal shell — it inherits the Web UI's own token path by loading the same
served HTML — but the bridge exists unused, which is worth cleaning up or wiring to a
real caller before it looks like dead code with no owner.

The served sitting also carries a per-response `Content-Security-Policy`
(`server.sitting_csp`): script execution is limited to same-origin plus the exact
sha256-pinned inline `<script>` blocks index.html ships, so an injected `<script>` or
`<img onerror>` in a rendered file cannot exfiltrate the token even if it got past the
sanitizer. See `kettle/server.py` `sitting_csp()`.

## Follow-ups

- Wire `kettle-desktop`'s `getCoreToken` IPC bridge to an actual caller, or remove it —
  today it is unused by the live renderer.
- Consider a shared, tested token-read helper per client so a future
  discovery-schema change updates one place.
- No token-in-URL and no env-var token: keep the secret in the 0600 file only.
