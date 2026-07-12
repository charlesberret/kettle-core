---
project: setsweep
kind: software
phase: active
canonical: ~/Seafile/Code/active/setsweep
deps: pip
test_cmd: pytest
test_signal: .pytest_cache/v/cache/lastfailed
healthbeacon: ~/.cache/setsweep/watch-health.json
---

## Status

The test suite is 36 green, including a `LaunchTests` class added on 2026-06-13 that covers the circuit-breaker in `start_server_preferred` (no-predecessor, healthy-current-not-killed, stale-retired, `--replace`, own-pid-safe, foreign-occupant fallback — all stubbed, no real port bound). The port was moved from 8765 to 4242 in the same session; `DEFAULT_PORT = 4242` in `server.py` is the single source of truth and the URL is now `http://127.0.0.1:4242/`. The relaunch loop that looked like crashes is fixed: the circuit-breaker retires a predecessor only when stale (its `started` timestamp predates the newest `server.py` / `static/index.html` mtime) or when `--replace` is passed; a healthy current instance causes `app.py` to defer. Branch `codex/shore-up-system` is in flight with uncommitted changes to `server.py`, `static/index.html`, and `test_server.py`.

## Next action

- [ ] Write a generalized stub-claude harness to cover the streaming endpoints (`chat`, `glance`, `sweep`) and `run_claude` resilience (malformed ndjson mid-stream, non-zero exit, missing binary, hang/timeout)
- [ ] Harden `safe_path` beyond its current 3 tests — see open `.setsweep/handoff-path-fence.md` for the case list (`..`-resolves-back-inside, absolute-path-in-param, encoded/null-byte, multi-root expansion)

## Known gaps

- Chat writes are always-on via `acceptEdits` (interim). A fuller chat-window redesign with real permission UX may replace this later.
- HTTP response envelopes are not yet uniform across routes (see `API.md` stability notes)
- Sweep quiet CLOSE is mechanical (`sweepkit` / CLI); judgment CLOSE and ACCRUE still need curator coverage tests beyond the unit suite
- No settings shallow-merge clobber guard for non-`curator` top-level groups — colors/slots/iface/palettes/adminBox can still be dropped by a bad patch
- Frontend has zero tests — the palette-save bug that was found lived in `static/index.html`; a JS error there produces a blank window with no app left to repair it
