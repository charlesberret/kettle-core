---
id: 18
title: Metrics beacons + setsweep doctor
repo: setsweep-core
touches: [server.py, sweepkit.py, cli.py, setsweep/ metrics module (new), test files]
risk: run-critical
depends-on: [11]
status: open
---

## Context

Phase 5's rule is that the beta go/no-go gets decided from evidence, and the evidence
layer doesn't exist yet. The design constraints are already settled (ROADMAP "Decisions
taken", RELEASE.md): **no phone-home, ever** — measurement is local files the user
owns; and invariant 6 — every automated actor beats a healthbeacon — gives the pattern
to extend. Meanwhile support's first question ("is it installed right, is the server up,
is the curator authed?") has no one-command answer, which is what a support channel
needs before an alpha cohort exists.

## Task

1. **Metrics events.** A small module (`metrics.py`): append-only JSONL at
   `~/.cache/setsweep/metrics.jsonl`, events `{ts, event, project: sha256-prefix,
   fields}` — project identity hashed even locally (files leak into screenshots).
   Instrument the seams that already exist: founding transitions (interview started /
   proposal filed / founded), entry approved (with curated-to-ruled latency), sweep
   completed (kind: mechanical/judgment), curator turn ended (ok/error/watchdog-kill),
   frontend boot-error beacon (one POST from the brief-08 banner). Writes are
   best-effort and never raise into the request path.
2. **`setsweep metrics`**: prints the RELEASE.md tables (stability / success /
   usability) for a date range, from the local file. This is how the user reads their
   own telemetry.
3. **`setsweep doctor`**: checks, in order — **install seed already from brief 20**
   (`cli.install_doctor_checks`: which `setsweep` on PATH vs `~/.setsweep-venv`,
   extra PATH hits, every `py-modules` name importable and present in the installed
   `top_level`); each failing row should point at [`INSTALL.md`](../../INSTALL.md) or
   [`ARCHITECTURE.md`](../../ARCHITECTURE.md) (brief 17); then expand with Python +
   package version and install mode;
   registry readable and desks intact (queue.json parses, desk dirs exist); server
   reachable + version match (the brief-11 ping field) + auth token present; curator
   CLI resolves (`curator.provider_readiness()` exists) plus a real auth probe — new
   work in this brief; today curator.py only has static auth hints; beacon
   freshness (watch, metrics). Table output, nonzero exit on failure, and a docs
   pointer per failing row. Doctor is read-only — it never repairs. Extend
   `cmd_doctor` / `install_doctor_checks` rather than rewriting.
4. Tests: metrics writes from a stubbed sweep; doctor against a broken scratch setup
   (dead server, missing CLI) asserting the right rows go red.

## Constraints

- No network I/O anywhere in this brief beyond localhost ping in doctor.
- Metrics must be off-switchable (`settings metrics.enabled: false`) and the file
  trivially deletable — user ownership is the whole design.
- Event volume stays boring: per-sitting events, never per-token.

## Done when

- A stub founding + sitting + sweep produces the expected event sequence in the JSONL.
- `setsweep metrics` renders honest tables from it; `setsweep doctor` on a healthy
  setup is all green, and on each induced failure names the failing layer with a docs
  pointer.

## Verify

Full suite; a manual doctor run against the live setup (read-only — it must not touch
port 4242 beyond a GET /api/ping); induced-failure runs in a scratch environment.

## Afterwards

`status: done`; RELEASE.md's dogfood protocol starts reading real numbers; _Status.md
healthbeacon table gains the metrics row; the quarterly roadmap sitting cites the file.
