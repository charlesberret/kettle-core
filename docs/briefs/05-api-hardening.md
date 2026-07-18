---
id: 05
title: Harden the HTTP surface
repo: setsweep-core
touches: [server.py, static/index.html, API.md, test_server.py, plugin + desktop follow-ups]
risk: run-critical
depends-on: [01]
status: open
---

## Context

The server binds 127.0.0.1 and stops there: no auth token, no Origin check, no Host
validation, and `read_body` ignores Content-Type (server.py:1553–1555). Browsers happily
send cross-origin `text/plain` POSTs without preflight, and DNS-rebinding defeats
same-origin assumptions — so any web page the patron visits can, in principle, drive
`POST /api/save` (arbitrary file write under every registered root), `/api/sweep`
(spawns a write-armed agent), or `/api/open-link`. Localhost bind is the only barrier.
Separately, the error envelope has sharp edges: malformed JSON → 500 not 400, POST lacks
the FileNotFoundError→404 mapping GET has, and 500 bodies leak `repr(e)` with absolute
paths.

## Task

1. **Per-boot token.** Generate a random token at bind, write it into
   `~/.cache/setsweep/server.json` (mode 0600) beside the port — the discovery file the
   viewports already read. Require it (header `X-Setsweep-Token`) on every `/api/`
   request. The web frontend gets it via server-side injection into `index.html` at
   serve time (it is same-origin; a `<meta>` tag is enough). Desktop and plugin read the
   discovery file they already consume; CLI reads it the same way.
2. **Origin/Host checks** as defense in depth: reject requests whose `Origin` is present
   and not the server's own origin; reject `Host` headers that are not
   `127.0.0.1[:port]`/`localhost[:port]`.
3. **Envelope normalization:** JSONDecodeError→400, FileNotFoundError→404 on POST,
   `{error, code}` shape with `str(e)` never `repr(e)`; `/api/diff`+`/api/diffstat`
   return an error for unknown entry ids instead of empty success.
4. Update `API.md` (auth section + envelope + the open-link 404 shape which the doc
   currently gets wrong) and the three viewports' clients in the sibling repos (small,
   mechanical: one header).

## Constraints

- Token check failure returns 403 with a plain hint; the web app must keep working with
  zero user-visible change on a normal boot.
- Do not break the ephemeral-port test harness — tests read the token the same way
  clients do (the fixture already redirects the cache path).
- HTTP/1.0 close-delimited streaming stays as-is; this brief is auth, not transport.

## Done when

- A POST without the token → 403; with a foreign `Origin` → 403; with `Host: evil.tld`
  → 403 — each pinned by a test.
- Malformed JSON body → 400 `{error, code}`; missing file on save → 404; no `repr(` in
  any response body (grep the handlers).
- All three sibling viewports updated and attaching successfully.

## Verify

Full suite plus a manual check: `curl -X POST -H "Origin: https://evil.example" ...`
against a scratch server on an ephemeral port (never 4242) gets 403.

## Afterwards

`status: done`; API.md stability notes gain the auth paragraph; brief 13 (contract v1)
inherits the envelope standard; RELEASE.md's security-pass checklist ticks its first box.
