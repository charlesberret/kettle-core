---
id: 13
title: API contract v1
repo: kettle-core
touches: [API.md, server.py (small), tests/test_server.py]
risk: normal
depends-on: [05, 07, 11]
status: open
---

## Context

`API.md` is honest about what it covers — the audit found no documented-but-missing
routes — but the contract every future adapter depends on is under-specified where it
matters most. The queue-entry schema (the app's central resource) is never written down,
and the server silently injects `diff` and `comment_history` into `GET /api/queue`
responses. Tier 4 routes (kits save/delete, lineage + resolve/accept/bind, entry, admin,
refound) are name-only. The streaming protocol's real rules — streams are always HTTP
200; pre-stream validation errors are JSON 4xx; a crashed curator may emit `error`
without `done` (fixed by brief 07); EOF is terminal; transport is HTTP/1.0
close-delimited — live only in code and in adapter authors' scar tissue. The `usage`
event carries `output`, `cost`, `fraction` beyond the documented fields; `/api/ping`'s
curator block carries `effort`, `stream`, `auth_hint` undocumented; `mutate` accepts
`0/false/no/off` but only `?mutate=0` is documented; one shape is documented wrongly
(open-link 404 returns `{error}`, not `{ok:false,error}`). The real spec today is
`tests/test_server.py`, which strangers cannot read first.

## Task

1. Write the queue-entry schema into API.md: every field the server reads or writes
   (`ENTRY_FIELDS` whitelist), which are server-injected on read (`diff`,
   `comment_history`), which are append-only, the `source` field from the inbox kind.
2. Document every Tier 4 route's request/response shape from the handlers.
3. Add a **Streaming contract** section stating the five rules above, post-brief-07
   (done-is-terminal becomes a promise).
4. Correct the drift list: usage/ping fields, mutate values, open-link 404 shape, the
   `version` field from brief 11, the auth header from brief 05.
5. Add contract snapshot tests: for each documented shape, a test that round-trips the
   live handler and asserts the documented keys (a thin loop over route fixtures —
   pattern exists throughout tests/test_server.py). The point: API.md and the code cannot
   drift silently again.
6. Promote the Stability-notes section into a versioned-changes discipline: a
   `## Changes` log with dates, and the rule that removals get a deprecation entry one
   release before they land.

## Constraints

- Document reality; where reality is wrong (envelope quirks), fix per brief 05's
  standard rather than canonizing the wart — small code changes are in scope, redesigns
  are not.
- Keep API.md's tier structure — viewport authors navigate by it.

## Done when

- An adapter author could implement Tier A/B from API.md alone, without reading
  tests/test_server.py — falsifiable: the snapshot tests enumerate every documented shape.
- The snapshot tests fail when a handler adds or removes a documented key.

## Verify

Full suite; then delete one documented key from a handler locally and confirm the
snapshot test catches it; revert.

## Afterwards

`status: done`; note in docs/PLATFORMS.md that the non-TS adapter path (JetBrains,
Sublime) is unblocked; changelog discipline starts now.
