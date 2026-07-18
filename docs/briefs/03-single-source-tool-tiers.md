---
id: 03
title: Single-source the tool tiers
repo: setsweep-core
touches: [cli.py, server.py, runtime.py, test_server.py, test_runtime.py]
risk: run-critical
depends-on: [01]
status: open
---

## Context

The write-power ladder (read-only interview → chat with fenced edits → sweep/found with
broader shell) is defined **twice** and has drifted: `runtime.TOOL_TIERS`
(runtime.py:447–474, with the shell allowlists just above at 421–445) — used by every
HTTP route via `build_turn_cmd` — grants the sweep
tier `Bash(rm:*)`, `Bash(python3:*)`, `Bash(tee:*)` that the older `server.py:185–231`
constants lack. Those server constants are consumed only by `cli.py` (lines ~170, ~276),
so an HTTP sweep and a CLI sweep run with different powers under the same tier name.
`server.CHAT_TOOLS` and `server.INTERVIEW_TOOLS` are dead code. Worse, `cli.py`
hardcodes the Claude dialect — `Runtime(server.CLAUDE)`, `--append-system-prompt`,
`--name` — so `setsweep found`/`chat` under a Grok/Gemini/Codex curator passes Claude
flags to a foreign CLI or silently spawns Claude against the user's configured provider.

## Task

1. Port `cli.py`'s agent-turn commands (`found`, `chat`, and any other path that builds
   curator argv directly) onto `build_turn_cmd`/`runtime.build_argv`, resolving the
   provider from settings exactly as the HTTP routes do.
2. Delete the duplicate tool-tier constants from `server.py` (185–231) once nothing
   consumes them. `runtime.TOOL_TIERS` becomes the single authority.
3. Decide deliberately (don't inherit by accident) whether the sweep tier *should* hold
   `Bash(rm:*)` and `Bash(python3:*)` — a Python script escapes the edit fence by
   construction. If they stay, add one comment stating why; if they go, update
   runtime.py and its tests. Surface the question to the patron if unclear.

## Constraints

- `server.py` is run-critical: run the full suite before and after; never edit from
  inside a live Setsweep session.
- CLI behavior under `provider: claude` must be byte-compatible where tests assert argv.

## Done when

- `grep -n "SWEEP_TOOLS\|CHAT_TOOLS\|INTERVIEW_TOOLS" server.py cli.py` finds only
  `runtime.`-qualified uses (or nothing).
- A `settings.json` with `curator.provider: grok` makes `setsweep chat` build Grok argv
  (assert via a captured-command test, pattern in test_server.py `_capture_cmds`).
- Full suite green.

## Verify

`python3 -m pytest -q`; then a manual `setsweep chat` dry-run with a stub curator command
configured, confirming the built argv matches the provider.

## Afterwards

`status: done`; note the tier decision (rm/python3 kept or dropped) in `API.md`'s tier
table and in brief 06's context.
