---
id: 14
title: Test depth
repo: kettle-core
touches: [tests/test_server.py, tests/test_cli.py (new), tests/test_watch.py, pyproject.toml, .github/workflows (new)]
risk: normal
depends-on: [01]
status: done
---

## Context

~225 tests, genuinely strong where they look — fence, circuit breaker, provider dialects,
streaming resilience via the stub-curator harness — but blind where they don't: six-plus
routes have zero tests (kits GET/save/delete — a **write path** with no fencing test —
chatlog GET/POST, compact, refound, static serving including the /fonts/ traversal
check); `cli.py` (454 lines, 14 subcommands) has no test file at all and `Runtime.spawn`
is never constructed; there is no end-to-end lifecycle test composing the founding state
machine; coverage is asserted by inspection, not measured; the suite monkeypatches
module globals and `subprocess.Popen` in-place, so it is serial-only — undocumented; and
one curator-catalog test passes vacuously on machines lacking the CLI binaries.

## Task

1. **Route smokes:** one test per untested route using the existing `Base`/
   `EndpointTests` fixtures — including a fence test for `/api/kits/save` (path
   traversal in kit names) and the fonts traversal check.
2. **The lifecycle test:** register → interview → propose (proposal entry appears) →
   approve → found (desk files land, queue fills) → chat → approve → sweep → close,
   entirely on the stub curator. This is the founding state machine's executable
   documentation.
3. **`tests/test_cli.py`:** drive `main(argv)` against the tempdir fixture pattern
   (tests/test_egress.py has the template); cover add/init/projects/queue/egress (approval is
   a server route, not a CLI verb) and
   the argv construction for agent turns (post-brief-03, provider-parameterized).
4. **Coverage:** add coverage.py as a dev extra; wire `pytest --cov` into CI; publish
   the number in the CI summary. Target: no module below 60%, no PR that lowers the
   number without saying so.
5. **Honesty fixes:** document serial-only in a comment atop tests/test_server.py and in
   ENGINEERING.md; pin the catalog test's PATH so it asserts deterministically.
6. **CI bootstrap:** `.github/workflows/test.yml` — matrix py3.11/3.14 × ubuntu/macos,
   pytest on PR; the wheel-install smoke joins after brief 11 lands.

## Constraints

- Ephemeral ports only (`start_server(0)`); never 4242.
- Keep the stdlib-only test style — no pytest fixtures/plugins beyond coverage; the
  uniformity is a feature of this suite.

## Done when

- `pytest --collect-only` grows by the route smokes + lifecycle + CLI file; suite green
  on both Python floors locally or in CI.
- Coverage number visible in CI; kits/save fence test exists and fails on an induced
  traversal bug (verify by temporarily weakening the check, then revert).

## Verify

Full suite twice (order stability); CI run green on a pushed branch.

## Afterwards

`status: done`; update ENGINEERING.md's "where testing stands" section and _Status.md's
test facts; brief 11's packaging job plugs into this workflow.
