# Setsweep — Engineering Charter

*Companion to [`ROADMAP.md`](../ROADMAP.md). The roadmap says what gets built; this file
says how the building stays sound — tests, CI, debugging systems, code health. Written
2026-07-17 from the same eleven-subsystem survey. Briefs referenced by number live in
[`docs/briefs/`](briefs/README.md).*

## Where testing stands

The suite is honest about what it is: ~225 tests (run `python3 -m pytest
--collect-only -q` for the live number), all stdlib `unittest` + `urllib` — pytest is
the runner, nothing more. No fixtures, no third-party test deps, matching the product's
stdlib-only invariant. Every suite redirects module globals into a tempdir; the real
registry, settings, and desk are never touched.

`test_server.py` carries roughly half the suite (109 tests) and is the crown jewel: a
real HTTP server booted on an ephemeral port via `start_server(0)` — never 4242 — plus a
shell-script stub curator (`_stub_claude`) and a Popen-capturing fake (`_capture_cmds`)
that exercise the streaming endpoints end to end. The stub harness already covers the
hard cases: malformed ndjson mid-stream, non-zero curator exit surfacing as an error
event, a missing binary leaving the server alive, provider/model mismatch skipping
`--resume`, and prompt-content assertions on sweep. The file fence has 12 dedicated
tests (symlink escape, dotdot, null byte, multi-root union); the port-4242 circuit
breaker has 7 regression tests that stub its seams without ever binding a real port.
Regression tests are annotated with the incident they pin — keep doing that.

Now the holes, named:

- **Hang and disconnect.** No test simulates a curator that stays open emitting
  nothing, and no watchdog exists to kill one — `run_curator`'s read loop blocks on
  stdout with only a `proc.wait(timeout=10)` after EOF. A hung CLI pins a handler
  thread indefinitely. Client-disconnect mid-stream is equally untested. Brief 07 owns
  both the watchdog and its tests.
- **Untested routes.** Six-plus routes have zero coverage: `GET /api/kits`,
  `POST /api/kits/save`, `POST /api/kits/delete` (file-writing endpoints with untested
  fencing), `GET`+`POST /api/chatlog`, `POST /api/compact`,
  `POST /api/projects/refound`, and all static serving — including the `/fonts/` route's
  own inline traversal check.
- **`cli.py`: 454 lines, zero tests.** Fourteen subcommands, argv parsing, exit codes,
  and the only consumer of `Runtime.spawn` — which no test ever constructs.
- **The frontend: 4,254 lines, zero tests.** The one file whose breakage takes the app
  offline while the patron is in it has no harness at all — not even a smoke test that
  the page parses.
- **No end-to-end lifecycle test.** Every stage of founding-to-close is tested in
  isolation; nothing composes them, so cross-stage state regressions are caught only
  piecewise.
- **No coverage measurement.** All coverage claims are by inspection.
- **The suite is serial-only.** Tests monkeypatch module globals and even
  `subprocess.Popen` in place; this is safe under a single runner and breaks under
  pytest-xdist. That is a documented constraint, not a bug — do not parallelize the
  suite without first removing the global patching.

## The harness roadmap

What to build, in the order the briefs sequence it:

1. **Stub-curator extensions** (brief 07). Add sleep-then-emit, die-mid-stream, and
   client-disconnect variants to `_stub_claude`, landed together with the read watchdog
   they exercise. The harness pattern already exists; this closes the last standing
   item from `_Status.md`'s original test wishlist.
2. **The e2e lifecycle test** (brief 14). One test that drives register → interview →
   propose → approve → found → chat → approve → sweep → close against the stub. It will
   document the founding state machine better than any prose, and it is the single
   cheapest guard against the class of bug the session-healing logic already patches.
3. **Frontend, in three steps.** First the extract-and-node-check syntax gate (brief
   08) — pull the inline script, run `node --check`, fail CI on a parse error; this
   closes the blank-window class structurally. Then the injection corpus against the
   sanitizer (brief 09). Then `data-testid` attributes and exactly ONE Playwright smoke:
   boot → queue renders → settings opens. Position: unit-test the pure functions by
   extracting them into plain `.js` files — we do not adopt a JS framework test stack.
   The frontend stays no-build; the tests respect that.
4. **Plugin tests** (briefs 02, 16). `@vscode/test-electron` for extension activation
   plus a confirm-card round-trip (GFM in → ticks out) — the two things that break
   silently today.
5. **Contract snapshots** (brief 13). Tests that pin the wire shapes `API.md` promises —
   queue entry, ping, the streaming event vocabulary — so a viewport-breaking change to
   the envelope fails a test in core before it fails a plugin in the field.
6. **Coverage, measured honestly.** `coverage.py` as a dev-only tool with a visible
   number. The target is *no module below 60% and no new code untested* — a floor and a
   ratchet, not a vanity total. Coverage of `server.py`'s route handlers matters more
   than a repo-wide percentage.

## CI

There is no CI anywhere today — no `.github/` in any of the three repos, no tags, no
release workflow. Each repo gets its own GitHub Actions setup. PR runs are the fast
lane; nightly is the full lane.

| Repo | PR lane | Nightly / release |
|---|---|---|
| **core** | pytest on a matrix (Python 3.11 and 3.14 × ubuntu and macos — 3.11 is the declared floor and currently untested); wheel-install smoke from brief 11; the `node --check` frontend gate from brief 08 | Full matrix plus the coverage report |
| **plugin** | compile, tests, `vsce package` producing the VSIX as an artifact | — |
| **desktop** | build + sidecar smoke on macOS (the smoke script exists; CI just runs it) | Release job on tags, refusing to stamp a build from a dirty core tree (brief 15) — the currently installed app was built dirty, which is exactly the failure this closes |

The matrix earns its keep immediately: the live venv runs 3.14, `requires-python>=3.11`
has never been exercised at its floor, and no build has ever happened off the dev
laptop.

## Debugging systems

Three conventions, one per layer:

- **Viewports: the `debug.ts` pattern.** The VS Code plugin's identity surface —
  a hand-stamped `BUILD_ID`, an output channel, and a `showDebugLog` command — was born
  of real pain (an installed 0.5.113 VSIX drifting silently against a 0.2.0 repo). It is
  the standard for every viewport: a viewport must always be able to say exactly which
  build it is and show its own log.
- **Core: healthbeacons and structured stderr.** Every automated actor beats a
  healthbeacon (DESIGN invariant 6) — the watcher already writes
  `~/.cache/setsweep/watch-health.json` on every exit path, including failure. New
  actors extend that `~/.cache/setsweep/` convention; the Phase-5 metrics beacons are
  the same idea grown up. The server logs structured lines to stderr; a curator turn
  that fails should be reconstructable from the log alone.
- **Triage: `setsweep doctor`** (brief 18). One command that checks install mode,
  versions (core, viewport, skew between them), server reachability, curator CLI
  presence and auth, desk integrity, and beacon freshness. It is the support channel's
  first question, pre-answered.

## Code health

Two monoliths dominate the codebase, and each has a shrink path that preserves what
makes it work:

- **`server.py` (2,708 lines).** Prompt extraction (brief 04) moves the ~460 lines of
  inline prompt constants — about 17% of the file — out to `kits/prompts/*.md`, loaded
  the way `kits/_base.md` already is, turning prompt tuning from a run-critical handoff
  into a safe edit. Beyond that, the ~40 routes are dispatched through flat if/elif
  chains; a route table (path → handler, needs-project, streaming flag) would give
  uniform envelope handling and a generated route reference in one move. That is a
  documented opportunity, not yet a brief — it waits until the streaming and hardening
  work (05, 07) settles the handler shapes.
- **`static/index.html` (4,254 lines).** Splits into 3–5 plain `.js` files served
  as-is — boot/error first, then pure helpers, stream consumer, UI — preserving the
  no-build property while making parse failures partial instead of total. Briefs 08 and
  09 do the safety-critical part (error bootstrap, sanitizer) first; the rest of the
  split follows, not leads.
- **Plugin `deskPanel.ts` (1,319 lines, ~49 KB).** Half of it is one inline HTML/CSS/JS
  template string that no compiler checks. Brief 16 splits host logic from the webview
  via esbuild, putting the webview half back under the type checker.

The run-critical discipline, restated. `server.py`, `static/index.html`,
`setsweep_main.py`, `projects.json`, and `settings.json` are the files whose breakage
takes the live app down while the patron is in it. They are edited only by an external
session — never from inside Setsweep itself — that runs the tests before and after the
change. Never bind, signal, or curl port 4242 from any tooling; tests boot on ephemeral
ports, as `test_server.py` already does.
