---
id: 06
title: Provider capability table
repo: kettle-core
touches: [runtime.py, curator.py, server.py, API.md, test_runtime.py]
risk: run-critical
depends-on: [03]
status: done
---

## Context

Kettle's safety story leans on tool tiers, but tiers are only as real as each provider
makes them. On Grok, the "read-only" interview tier maps to `--allow Bash` +
`--always-approve` (runtime.py:~546–558) because of documented Grok flag quirks — so a
founding interview under `provider: grok` can execute arbitrary shell, including writes.
Grok write tiers use `--permission-mode bypassPermissions` with open Bash
(runtime.py:~535–544), far broader than the Claude allowlist the docs describe. Nothing
tells the user; nothing refuses. The tier table in API.md reads as a guarantee the
implementation cannot keep on every provider.

> **From brief 03 (done):** the tool tiers are now single-sourced in
> `runtime.TOOL_TIERS` (the `server.py` duplicates are gone) and the CLI resolves the
> provider from settings via `build_turn_cmd`, so a capability table added here has one
> authority to derive from. The `sweep` tier deliberately keeps `Bash(rm:*)` /
> `Bash(python3:*)` (live posture; rm/python3 escape the Edit fence — flagged for the
> user, not changed unattended). API.md now has a "Tool tiers" section to extend with
> the per-provider matrix.

## Task

1. Add a per-provider capability table to `runtime.py` (beside TOOL_TIERS):
   `read_only_tier`, `tool_allowlist`, `resume`, `effort`, `fenced_writes` — honest
   booleans derived from the argv builders that already encode the quirks.
2. Surface it: `/api/ping`'s curator block and `/api/curator/catalog` carry the active
   provider's capabilities.
3. Enforce the one that is a safety contract: when a turn requires the read-only tier
   (founding interview, discussion-mode chat) and the active provider cannot guarantee
   it, **refuse** with a clear error naming the options (switch provider for founding,
   or acknowledge an explicit settings override `curator.allow_unfenced_readonly:
   true`). Warn-and-proceed is not enough for founding: the interview is the trust
   ceremony.
4. Document per-provider reality in API.md's tier section — a small honest matrix.

## Constraints

- No behavior change for `provider: claude`.
- The refusal must be a pre-stream JSON 4xx (the stream never starts), so viewports show
  it as a normal error, not a hung turn.
- Keep the table beside the argv builders that justify it — same file, so drift between
  claim and construction is visible in one diff.

## Done when

- `interview` under a stubbed grok config → 4xx with the documented error code, pinned
  by a test; with the override set → proceeds, and the response notes the downgrade.
- `/api/ping` shows capabilities; catalog too; API.md matrix matches the code table.

## Verify

`python3 -m pytest test_runtime.py test_server.py -q`; manual `/api/ping` against a
scratch server with each provider configured (stub commands).

## Afterwards

`status: done`; note in RELEASE.md's security checklist; if the Grok quirks ever get
fixed upstream, the capability table is the one place to update.
