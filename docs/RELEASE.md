# Setsweep — Measurement & Release

*Companion to [`ROADMAP.md`](../ROADMAP.md) (Phase 5). This is the plan for knowing —
not guessing — whether Setsweep works, and the ladder from dogfood to 1.0. Workstreams
reference briefs in [`docs/briefs/`](briefs/) by number.*

## Philosophy

Setsweep is a privacy-respecting tool, and its measurement is built the same way.
**No phone-home, no analytics endpoint, ever** — that decision is taken in the roadmap
and it is not revisited here. Metrics are files under `~/.cache/setsweep/` that the
user owns, reads with the tool, and shares only by deliberate action. Nothing leaves
the machine unless a human copies it out.

This is enough. The audience before 1.0 is small by design: Charles's own desks, then
3–5 named alpha users, then a beta cohort we can actually talk to. Dogfooding plus a
small cohort answering direct questions **is** the telemetry — richer than any event
firehose, because every number comes with a person who can explain it.

## What we measure and why

Three families. Each metric is a definition and a source, so the number is checkable,
not vibes.

**Stability** — does the instrument stay up while the user is in it?

| Metric | Definition | Source |
|---|---|---|
| Crash-free sittings % | Sittings that end without a server death, sidecar crash, or hang | `metrics.jsonl` sitting events vs. crash/kill events |
| Curator watchdog kills | Hung curator CLIs killed by the idle-timeout watchdog (brief 07) | watchdog event in `metrics.jsonl` |
| Blank-window incidents | Boots where the shell loaded but the main script never registered — the boot beacon from the error bootstrap (brief 08) fires without a matching app-ready event | boot beacon in `metrics.jsonl` |
| Circuit-breaker events | Deferred/replaced/retired-stale outcomes from `start_server_preferred` | breaker event in `metrics.jsonl` |
| Stream error-without-done | NDJSON streams that emitted `error` with no terminal `done` (the contract brief 13 specifies) | stream-end events in `metrics.jsonl` |

**Success** — is the desk earning its place?

| Metric | Definition | Source |
|---|---|---|
| Sittings per week | Distinct sittings per desk per week — the retention proxy | sitting events |
| Founding completion rate | Foundings started → desks founded | interview-start vs. founded events |
| Time-to-first-approved-entry | New desk founded → first approve | founded and approve event timestamps |
| Approvals per sitting | Entries ruled on per sitting | approve events per sitting |
| Quiet-close ratio | Mechanical closes / all sweeps — measures how much judgment the desk successfully reserves for the user | sweep events tagged mechanical vs. curator |

**Usability** — where does the tool make people work for it?

| Metric | Definition | Source |
|---|---|---|
| Founding restarts | Interviews abandoned and started over on the same desk | interview-start events per desk |
| Confirm-card parse fallbacks | Streamed cards that fell back to sanitized text because regex parsing failed (the plugin already has this fallback path) | fallback event |
| Error banners shown | Frontend error-banner displays per sitting | banner event via the error bootstrap |
| Doctor runs that find problems | `setsweep doctor` invocations reporting at least one failed check | doctor event |
| Keyboard-only sitting | Select entry, read, comment, approve, sweep without a pointer (brief 09) | manual standing check each release |

## The beacon design

Invariant 6 (DESIGN §5): *every background actor writes a healthbeacon; silent failure
is a bug by definition.* The watcher already beats one at
`~/.cache/setsweep/watch-health.json`; the metrics design extends the same convention
rather than inventing a second one.

- **One append-only file:** `~/.cache/setsweep/metrics.jsonl`. Small typed events:
  `{ts, event, project, fields}` — one line each, written by the server and sweep
  paths (brief 18). Append-only, like every record the desk keeps.
- **Project identity is hashed.** Even local files leak — into screenshots, into
  pasted doctor output, into a shared terminal. The `project` field is a short hash,
  never a path or a name.
- **`setsweep doctor` reads them** (brief 18): install, server, curator CLI, auth,
  desk integrity, plus the recent beacon tail. It is the support channel's first
  question — "run doctor, paste the output" — and the paste is safe by construction.
- **`setsweep metrics`** prints the tables above for a date range, computed locally
  from the file. The beta go/no-go is read off this command, not off memory.

## The dogfood protocol

Charles's own registered desks are cohort zero. Instrumentation without questions is
just a bigger log, so the weekly review asks:

- Did any sitting die mid-stream? (Check the stream error-without-done count against
  what you remember noticing — silent deaths are the worst kind.)
- Did founding confuse anyone — including you, on a new desk kind?
- What did you approve without reading — and why? If the honest answer is "the brief
  earned the trust," good; if it is "the queue was long," the product has a problem
  the numbers alone won't show.

Answers land in a metrics-review note in this repo, dated, beside the numbers that
prompted them. The quarterly roadmap sitting reads the accumulated notes and files
deltas against `ROADMAP.md` — evidence in, plan out.

## The release ladder

Three rungs. Each has entry and exit gates, and each gate is checkable — a command,
a count, or a named artifact, never a feeling.

**Private alpha** — 3–5 named users, hand-held.

- *Entry:* Phases 0–2 exit tests pass; an install path that works on a stranger's
  machine (clone + `~/.setsweep-venv` in [`INSTALL.md`](../INSTALL.md) / README
  quickstart — ✅ brief 17; pipx or signed DMG still briefs 11/15); a quickstart doc
  (✅ README); the security pass landed (briefs 05/06) and an adversarial session found
  no localhost-bypass write path.
  - *Read-only tier honesty (brief 06):* the founding interview refuses (HTTP 409
    `read_only_unavailable`) under any provider whose `read_only_tier` capability is
    false, unless `curator.allow_unfenced_readonly` is explicitly set. The single
    authority is `runtime.PROVIDER_CAPABILITIES` — if a provider's CLI quirks change
    (e.g. Grok gains a real read-only mode), update that table and nothing else. Verify
    with `/api/ping` and `/api/curator/catalog` (both carry `capabilities`).
- *Exit:* each alpha user completed a founding and 5 sittings; no severity-1 incident
  (data loss, crash-with-loss, security); founding completion ≥ 80% without help.

**Public beta** — anyone can install; we can still break things, loudly.

- *Entry:* Phases 3–4 done; marketplace VSIX and DMG published; versioned API with
  changelog discipline (brief 13); de-personalization audit clean — brief 10 for
  code, brief 17 for docs (checklist below).
- *Exit:* crash-free sittings ≥ 98% across the cohort's metrics files; no unresolved
  data-loss report; `setsweep doctor` resolves at least half of support asks without
  a human.

**1.0** — the compatibility promise.

- The desk file format and the API v1 surface are stable. Breaking changes get
  deprecation windows and changelog entries, not surprises.
- A support channel exists and is named in the README.
- Recommendation (echoing the roadmap's open question): the promise covers the desk
  file format itself. The desk outlives the app — that is the point — so the format
  is the contract that matters most.

## The de-personalization checklist

Charles's fleet is baked into shipped surfaces today. The audit is a grep, run before
the beta entry gate, over everything that ships — code, prompts, kit files, docs:

    avicenna  hesiod  majordomo  Seafile  Xanadu  Dramaturge  /Users/charles

**Code items (brief 10):** ✅ done 2026-07-22

- `egress.py` defaults are neutral (`peers` / `escalation` / `launch` / `domain`); personal
  routes live in `settings.egress.routes` (local overlay).
- Sweep prompt ballots are generic fill-entries (no Dramaturge/Characters hardcoding).
- `/api/admin` fleet panels (sentinel, desk-events, watcher, persona family) gated behind
  `admin.fleet_panels` (default false).
- Desktop first-run may seed its registry from a local core checkout — harmless on a
  stranger's machine, but it should use a published example or empty registry (desktop
  brief 15).

**Docs items (brief 17):** ✅ done 2026-07-22

- Public [`ARCHITECTURE.md`](../ARCHITECTURE.md), README glossary + quickstart + CLI
  reference, clone-based [`INSTALL.md`](../INSTALL.md).
- Kit egress docs use neutral routes (brief 10); drift fixes (five kinds, sweep-close).
- `_Status.md` slimmed to generic maintainer status (no private topology).

**Licensing:** LICENSE files present in all three repos. Core has one (MIT, declared
in `pyproject.toml`); desktop and plugin currently lack LICENSE files, and the plugin
also lacks a `repository` field — its packaging leans on `--allow-missing-repository
--skip-license`, which blocks marketplace publication. Fixed in briefs 15 and 16's
packaging passes.
