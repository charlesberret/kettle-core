---
id: 07
title: Curator watchdog
repo: setsweep-core
touches: [server.py, test_server.py]
risk: run-critical
depends-on: [01]
status: done
---

## Context

`run_curator`'s read loop blocks on the subprocess's stdout with no read timeout
(server.py:2465–2500); `proc.wait(timeout=10)` applies only after EOF. A curator CLI
that hangs with its pipe open pins a handler thread indefinitely — the exact failure
`_Status.md` has flagged since June and the one class the otherwise-strong stub-curator
harness never exercises. Two adjacent warts live in the same function: a spawn failure
after headers are sent double-writes an HTTP response into the open NDJSON stream, and a
process that dies mid-stream can end the stream with an `error` event but **no `done`**
— adapters keying completion on `done` hang their spinners.

## Task

1. Add an idle watchdog: if no event arrives for `curator.idle_timeout_s` (settings,
   default ~300), kill the process, emit `{t:"error", ...}` naming the timeout, then
   `{t:"done"}`, then close. Reset the timer on every event — the loop already has the
   per-event hook.
2. Guarantee `done` is the last event on every path: normal EOF, error, watchdog kill,
   client-gone kill.
3. Fix the double-response wart with a `has_streamed` flag: pre-stream failures return
   JSON 4xx/5xx; post-stream failures are `{t:"error"}` events.
4. Extend the stub harness: a sleep-then-emit stub (hangs N seconds silently), a
   die-mid-stream stub, and a client-disconnect test (close the socket mid-stream,
   assert the subprocess gets killed — `stream_line` returning False already triggers
   `proc.kill()`, it just has no test).

## Constraints

- The watchdog must not fire during legitimately long silent tool work if the provider
  emits keep-alive/tool events — confirm each dialect's event cadence before choosing
  the default; make it a setting, not a constant.
- No change to the event vocabulary (model/text/tool/usage/done/error) — brief 13
  documents it; this brief makes it reliable.

## Done when

- A hung stub curator is killed after the (test-shortened) timeout and the client
  receives error-then-done, pinned by a test.
- Every streaming test asserts `done` is terminal.
- Client-disconnect test passes; spawn-failure returns a clean JSON error with no
  double-write.

## Verify

`python3 -m pytest test_server.py -q -k "stream or sweep or chat or interview"` plus the
full suite.

## Afterwards

`status: done`; _Status.md's oldest Next-action item finally dies; API.md's streaming
notes (brief 13) can now promise done-is-terminal.
