---
id: 19
title: Enforce the agent fence
repo: kettle-core
touches: [sandbox.py (new), runtime.py, server.py, curator.py, API.md, test_sandbox.py (new)]
risk: run-critical
depends-on: [03, 06]
status: open
---

## Context

Kettle's thesis is a boundary: agents prepare, the user rules. But three of the
invariants that express it are enforced by **prompt**, not architecture — writes stay
inside the project root, append-only records are never mutated, the desk never transmits.
All three are requests, not guarantees.

The tool tier is an allowlist of **binary names**. It constrains *which* programs a turn
may run; it cannot constrain *where* they write. `rm`, `mv`, `cp`, and `tee` take arbitrary
paths, and `sed -i` / `awk '{print > f}'` in the `agent` tier do too. `python`/`python3`
were dropped from the sweep tier on 2026-07-20 (evidence: no prompt under `kits/` ever
referenced them), which narrowed the hole without closing it. Provider variance widens it
again: Grok's tiers map to `bypassPermissions` with open Bash, which brief 06 can *detect
and refuse* but cannot *fix*. And `safe_path` — the fence people assume covers this — governs
Kettle's own HTTP routes (`/api/file`, `/api/save`), not the tools a spawned curator holds.

**The ambition.** Make the fence a property of the system rather than a line in a prompt:
*point Kettle at a folder and it cannot touch anything outside it.* No adjacent agent tool
makes that claim, and it is the natural completion of the product's own thesis — a division
of labor is only as real as its boundary.

## The ladder

1. **Honest labeling** — done 2026-07-20. `API.md` now says trusted-not-fenced rather than
   implying a guarantee.
2. **Narrow the grants** — `python`/`python3` removed. `sed`/`awk` in `SHELL_KIT` still owed
   an audit.
3. **OS sandbox around the curator process** — *this brief's increment.* Highest value per
   unit of effort, because it fences whatever the CLI does, including raw shell, regardless
   of which vendor's permission model sits underneath. Provider-agnostic by construction.
4. **Mediated tools** — Kettle exposes its own fenced tool layer (read/grep/edit/write, all
   through `safe_path`) and the agent holds no raw shell. Strongest guarantee, and it is the
   same build DESIGN already flagged as the local-model tool harness, so it pays twice: real
   containment *and* tool use for models without native tool-calling.
5. **Verification** — prove it rather than assert it. `lineage.py` already reconciles
   out-of-band edits; extend it to assert nothing outside the root changed during a sitting.

## Honest constraints (read before promising anything)

- **The curator CLI needs network** to reach its model endpoint. Blanket network denial
  breaks every turn, so "never transmits" *cannot* be enforced by cutting the network — it
  needs host allowlisting (the provider API only) via SBPL rules or a local proxy. Stage that
  after filesystem containment, and do not claim it in docs before it lands.
- **The CLI needs paths outside the project**: its own config (`~/.claude` and peers),
  caches, temp dirs. The profile must permit them or nothing runs. This is a *containment*
  boundary, not a hermetic one — say so plainly.
- **Never silently degrade.** If the profile cannot be applied, refuse the turn or warn
  loudly in the stream. A sandbox that quietly falls back to unsandboxed is worse than none,
  because it manufactures false confidence.

## Task (first increment only)

1. Write `sandbox.py`: build a per-sitting profile from the project root + its `.kettle/`
   + a temp dir, and expose `wrap_argv(argv, project_root) -> argv`. macOS first
   (`sandbox-exec` + generated SBPL); Linux second (`bubblewrap`, or Landlock where the
   kernel supports it).
2. Thread it through `build_turn_cmd` behind a setting (`sandbox.enabled`, default `false`).
3. Add a `sandboxed` field to the provider capability table (brief 06's structure) so
   `/api/ping` reports honestly whether the active turn is contained.
4. Tests (`test_sandbox.py`): the profile denies a write to `/tmp` and to `$HOME` outside the
   root; permits writes inside the root and `.kettle/`; the turn refuses or warns when
   `sandbox-exec` is unavailable.
5. **Measure the cost**: run a real founding and a real sweep under the sandbox and record
   what breaks. That measurement is the deliverable, not an afterthought.

## Constraints

- Opt-in first; the default stays `false` until a real founding *and* sweep run clean.
- Do not change tool tiers in this brief — sandboxing and allowlisting are separate layers,
  and conflating them makes both hard to reason about.
- `settings.json` is run-critical and its loader currently normalizes the curator block
  against a fixed key set; verify a new `sandbox` group actually round-trips before relying
  on it (see the `allow_unfenced_readonly` regression, 2026-07-20).

## Done when

- With `sandbox.enabled`, a curator turn instructed to write outside the project root fails,
  and the failure is visible in the stream rather than silent.
- A full founding → sitting → sweep completes under the sandbox on macOS.
- `/api/ping` reports containment status truthfully.

## Verify

The adversarial write test above, plus one real end-to-end sitting under the sandbox.

## Afterwards

`status: done`; `API.md`'s "What a tier is — and is not" becomes conditional on
`sandbox.enabled`; the ROADMAP ambition line gains its first landed stage; `docs/RELEASE.md`
security gate references containment.
