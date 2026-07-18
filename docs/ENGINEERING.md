# Setsweep — Engineering Charter

*Companion to [`ROADMAP.md`](../ROADMAP.md). The roadmap says what gets built; this file
says how the building stays sound — tests, CI, debugging systems, code health. Written
2026-07-17 from the same eleven-subsystem survey. Briefs referenced by number live in
[`docs/briefs/`](briefs/README.md).*

## Where testing stands

The suite is honest about what it is: 249 tests as of brief 14 (run `python3 -m pytest
--collect-only -q` for the live number), written with stdlib `unittest` + `urllib` and
run by pytest. Product runtime remains stdlib-only; the `dev` extra adds pytest,
coverage.py, and pytest-cov for measurement and CI. No custom fixtures are required.
Every suite redirects module globals into a tempdir; the real registry, settings, and
desk are never touched.

`test_server.py` carries roughly half the suite (117 tests) and is the crown jewel: a
real HTTP server booted on an ephemeral port via `start_server(0)` — never 4242 — plus a
shell-script stub curator (`_stub_claude`) and a Popen-capturing fake (`_capture_cmds`)
that exercise the streaming endpoints end to end. The stub harness already covers the
hard cases: malformed ndjson mid-stream, non-zero curator exit surfacing as an error
event, a missing binary leaving the server alive, provider/model mismatch skipping
`--resume`, and prompt-content assertions on sweep. The file fence has 12 dedicated
tests (symlink escape, dotdot, null byte, multi-root union); the port-4242 circuit
breaker has 7 regression tests that stub its seams without ever binding a real port.
Route smokes now cover kits GET/save/delete, chatlog GET/POST, compact, refound, static
assets, and font traversal. A stub-curator lifecycle composes register → interview →
proposal → approve → found → chat → approve → sweep/close. `test_cli.py` covers the
serverless add/init/projects/queue/egress paths and current Runtime handoff; watcher and
entrypoint routing tests pin their beacons and dispatch. Regression tests are annotated
with the incident they pin — keep doing that.

Coverage is measured in CI and locally with `python -m pytest --cov`. The brief-14
baseline is 80% total; every shipped Python module is at or above 62%. CI rejects any
module below 60% and publishes the full table in the job summary.

Now the holes, named:

- **The frontend: 4,254 lines, zero tests.** The one file whose breakage takes the app
  offline while the patron is in it has no harness at all — not even a smoke test that
  the page parses.
- **The suite is serial-only.** Tests monkeypatch module globals and even
  `subprocess.Popen` in place; this is safe under a single runner and breaks under
  pytest-xdist. That is a documented constraint, not a bug — do not parallelize the
  suite without first removing the global patching. CI runs plain pytest with no xdist;
  `test_server.py` repeats this warning at the top of the file where a future test-runner
  change is most likely to see it.

## The harness roadmap

What to build, in the order the briefs sequence it:

1. **Stub-curator extensions** (brief 07, landed). Sleep-then-emit, die-mid-stream,
   client-disconnect, and spawn-failure cases pin the idle watchdog and terminal `done`
   contract. This closes the last standing item from `_Status.md`'s original test
   wishlist.
2. **The e2e lifecycle test** (brief 14, landed). It drives register → interview →
   propose → approve → found → chat → approve → sweep → close against the stub and is
   now executable documentation for the founding state machine.
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
6. **Coverage, measured honestly** (brief 14, landed). `coverage.py` is dev-only and CI
   publishes the number. The target is *no module below 60% and no new code untested* —
   a floor and a ratchet, not a vanity total. Coverage of `server.py`'s route handlers
   matters more than a repo-wide percentage.

## CI

Core now has `.github/workflows/test.yml`: PRs and this working branch run the serial
suite with coverage on Python 3.11/3.14 across Ubuntu and macOS, enforce the per-module
floor, and publish the coverage table. The plugin and desktop still need their own
workflows; no repo has a release workflow yet.

| Repo | PR lane | Nightly / release |
|---|---|---|
| **core** | pytest + coverage on Python 3.11 and 3.14 × ubuntu and macos; wheel-install smoke joins after brief 11; the `node --check` frontend gate joins after brief 08 | A later nightly can reuse the same full matrix |
| **plugin** | compile, tests, `vsce package` producing the VSIX as an artifact | — |
| **desktop** | build + sidecar smoke on macOS (the smoke script exists; CI just runs it) | Release job on tags, refusing to stamp a build from a dirty core tree (brief 15) — the currently installed app was built dirty, which is exactly the failure this closes |

The matrix earns its keep immediately: the live venv runs 3.14 and CI now exercises the
declared 3.11 floor off the development laptop.

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

- **`server.py` (about 2,470 lines).** Brief 04 moved the product prompt constants to
  `kits/prompts/*.md`, loaded once at import with logged emergency fallbacks. A format
  smoke test checks every file and makes prompt tuning a safe edit. Beyond that, the
  ~40 routes are dispatched through flat if/elif
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
