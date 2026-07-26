# Engineering guide

This document records the test, CI, and debugging discipline behind Kettle
Core. Product direction lives in [`ROADMAP.md`](../ROADMAP.md).

## Test shape

The Python runtime is standard-library only. The development extra supplies
pytest and coverage:

```sh
python3 -m venv .venv
.venv/bin/pip install -e '.[dev]'
.venv/bin/python -m pytest
```

The suite is intentionally serial. Several integration tests replace
module-level state and start real HTTP servers on ephemeral loopback ports.
Parallel execution is unsupported until those globals are isolated.

The tests cover:

- CLI registration, queue, chat, egress, and close helpers;
- contract identity and cross-family compatibility;
- curator providers, timeouts, and streaming terminal events;
- the registered-root file fence and path traversal;
- founding, proposal, approval, chat, and sweep lifecycle;
- lineage, kits, survey, watcher, and runtime discovery;
- structural browser UI and shared-copy checks.

Structural frontend tests are not a browser smoke. A small real-browser boot,
queue, and settings check remains useful release work.

## CI and package evidence

Core CI should run the serial suite on the oldest supported Python and a current
Python across macOS and Linux. A public package additionally needs:

- an sdist and wheel contents audit;
- a clean virtual-environment install with no source checkout on `sys.path`;
- `kettle doctor`, `kettle --help`, and static/kits resource smoke tests;
- a recorded API and Desk contract identity.

Cross-repository checks live in `tools/check_family.py`. They verify independent
versions, adapter manifests, and optionally clean worktrees and native tests.

## Debugging

- Core actors write structured stderr and health beacons under
  `~/.cache/kettle/`.
- `kettle doctor` is the first install and runtime diagnostic.
- Viewports must display their own version/build identity and expose local logs.
- Tests and tooling never bind, signal, or probe the conventional live port
  `4242`; integration servers use ephemeral ports.

## Code health

`server.py` and `static/index.html` are intentionally direct but large. Changes
should first improve enforceable boundaries and test seams. A route-table or
frontend-module extraction is useful only when it preserves the standard-library
runtime, no-build browser UI, and readable error paths.

Run-critical files are:

- `server.py`
- `static/index.html`
- `kettle_main.py`
- the active project registry and settings file

Changes to them need focused tests before and after. A working live Desk is not
a test fixture.

Historical implementation briefs under [`briefs/`](./briefs/) explain how some
of these constraints emerged. Their frontmatter is not current project status.
