# Setsweep — Roadmap

*Written 2026-07-17 from a full-system survey of the three repos (eleven subsystem audits;
methods and raw findings summarized in `docs/` and the briefs). This is the master plan:
what Setsweep is, what it is becoming, and the ordered work between here and a version
strangers can use. Detail lives in the companion documents — this file is the spine.*

| Companion | Carries |
|---|---|
| [`docs/PLATFORMS.md`](docs/PLATFORMS.md) | Viewport expansion: adapters, desktop app, remote access |
| [`docs/ENGINEERING.md`](docs/ENGINEERING.md) | Test strategy, CI, debugging systems, code health |
| [`docs/RELEASE.md`](docs/RELEASE.md) | Measurement, stability/usability gates, the release ladder |
| [`docs/briefs/`](docs/briefs/) | Ready-to-run work packages for autonomous agent sessions |

## North star

Setsweep is a **review instrument for human–agent coworking**. Agents prepare and
propagate; the patron reads and rules. As agents write more of every codebase and corpus,
the scarce resource is no longer production — it is deliberate human judgment. Setsweep
concentrates that judgment: a curator pays the context cost once and delivers it pre-packed
(the brief), the patron rules once, and the ruling is applied outward mechanically (the
sweep). Nothing asks the patron to re-derive what an agent already knows; nothing lets an
agent rule on what is the patron's to rule.

What it could become: **the standing desk between a person and every fast-moving project
they steward** — code, writing, records, knowledge, inboxes — with the person's attention
routed to exactly the decisions that need a human, an auditable trail of who decided what,
and viewports wherever the person already works (browser, editor, desktop, notes app).

**Strategic bets** the rest of this roadmap honors:

1. **The desk is files.** All state in `.setsweep/` — human-readable, sync-friendly, no
   database. Any frontend renders the same desk; a desk with no app installed is still
   legible. (DESIGN §3.)
2. **Viewports over a local core.** One localhost server, many thin clients. The wire
   contract (`API.md`) is the product's real platform surface.
3. **Provider-agnostic curation.** The curator is whichever agent CLI the patron runs —
   Claude, Codex, Gemini, Grok — behind one narrow adapter (`runtime.py`).
4. **Attribution as a feature.** `agent · user · unattributed`, never guessed
   (`lineage.py`). "Who decided this?" is a query, not an archaeology dig. No adjacent
   tool offers this; it is a headline, not a footnote.
5. **The patron's hand is the only authority.** Approve is a bookmark; sweep is the
   commit; egress stages and never transmits. These asymmetries are the product.
6. **Invariants survive rewrites.** DESIGN §5 verbatim: localhost-only, file-fence on
   every route, append-only records never auto-mutated, patron's words beat the files,
   memory is distillation, every automated actor beats a healthbeacon.
7. **The fence should be real.** Today the project-root boundary is enforced by prompt,
   not architecture — a tool allowlist names binaries, it cannot bound where they write
   (see `API.md`, "What a tier is — and is not"). The ambition is containment as a
   property of the system: *point Setsweep at a folder and it cannot touch anything
   outside it.* No adjacent agent tool makes that claim, and it is the natural completion
   of the division of labor this product exists to enforce. Ladder and first increment:
   [brief 19](docs/briefs/19-enforce-the-fence.md).

## Where it stands (2026-07-17, honest)

**Strong:** a stdlib-only core with ~225 tests including a real stub-curator harness for
the streaming endpoints; a solid file fence (symlink, dotdot, null-byte cases covered); a
circuit breaker that never kills a healthy live window; genuinely provider-neutral stream
normalization across four CLI dialects; a clean kit system; working lineage attribution;
three live viewports (web, Electron desktop, VS Code) plus a serverless CLI.

**Fragile:** nearly all recent work is uncommitted — the egress layer is untracked, core
carries ~4,000 uncommitted inserted lines (roughly 1,700 of them on run-critical files),
and the VS Code plugin
exists as *two divergent implementations* (an 8,223-line committed branch with tests and
sidecar vs. a 3,293-line leaner rewrite sitting untracked on main). The HTTP surface has
no auth/Origin/Host checks. Charles's personal fleet is baked into shipped prompts, egress
routes, and admin panels. Truth is duplicated in ~8 places (tool tiers twice and diverged,
prompts split across `server.py` and `kits/`, two folder-watchers, two model catalogs).
Install is editable-only; a wheel would ship a broken app. The frontend can fail to a
blank window with its own error handler unregistered. Docs describe a smaller, older
project than the one that exists.

## The arc

Phases are dependency-ordered, not dated. Each phase names its exit test — the thing that
proves it done. Workstreams reference briefs in `docs/briefs/` by number.

### Phase 0 — Secure the ground

The program's biggest risk is a `git clean`, not a bug.

- Commit the core working tree; track the egress layer (brief 01).
- Reconcile the two plugin implementations into one canonical tree; retire the other
  (brief 02).
- Adopt the desktop rule: never stamp a build from a dirty core tree (folded into 15).
- Refresh `_Status.md` to present reality (done 2026-07-17 alongside this roadmap).
- Reserve the PyPI name (verified unclaimed as of 2026-07-17) with a placeholder (in 11).

**Exit test:** `git status` clean on all three repos; a fresh clone of each builds and
tests green; the plugin has one implementation.

### Phase 1 — One truth per fact

Every duplicated fact is a future drift bug. Collapse them while the codebase is small.

- Tool tiers: delete the `server.py` copies, port `cli.py` onto
  `build_turn_cmd`/`runtime.TOOL_TIERS` — also un-hardcodes the CLI from Claude (brief 03).
- Prompts: move the ~460 lines of constants out of run-critical `server.py` into
  `kits/prompts/*.md`, loaded like `kits/_base.md` already is; add the
  format-every-prompt smoke test (brief 04).
- Watchers: one `setsweep-watch`, provider-aware, with seen-state migration (brief 12).
- Version: single-source from `pyproject.toml`, surfaced in `/api/ping` and `--help`
  (inside brief 11) so viewports can detect skew.
- Doctrine: brief standard and egress discipline each stated in one home, referenced
  elsewhere (folded into briefs 04 and 10).

**Exit test:** grep finds one definition of each: tool tiers, sweep prompt, brief
standard, egress routes, model catalog, watcher.

### Phase 2 — Harden the shell

Everything a stranger's machine — or a hostile web page — could do to a desk.

- API hardening: per-boot bearer token written to `~/.cache/setsweep/server.json` (the
  discovery file is the natural channel), reject cross-origin requests, normalize the
  error envelope, stop leaking `repr(e)` (brief 05).
- Provider capability table: declare per-provider guarantees; refuse or loudly warn when
  a turn's required tier is unavailable — today a Grok founding interview silently runs
  with open Bash under a "read-only" tier (brief 06).
- Curator watchdog: idle-timeout kill so a hung CLI can never pin a handler thread;
  stub-curator tests for hang and client-disconnect (brief 07).
- Frontend survivability: error banner bootstraps from its own tiny script; guarded
  init; syntax gate in CI — closes the blank-window class structurally (brief 08).
- Rendering safety + access: allowlist sanitizer (vendored DOMPurify), aria-live on the
  stream, keyboard path through the queue, focus-trapped modals (brief 09).
- De-personalization: egress routes into settings with neutral defaults; generic sweep
  prompt; `kits/_base.md` split into generic core + user overlay; personal admin panels
  gated (brief 10).

**Exit test:** a security review session (external agent, adversarial) finds no
localhost-bypass write path; founding on every configured provider honors read-only; the
app survives an induced frontend syntax error with a visible banner; grep for personal
topology in shipped surfaces returns nothing.

### Phase 3 — Package for arrival

From "works in Charles's venv" to "installs anywhere."

- Core: restructure under a `setsweep/` package with `package-data`;
  `importlib.resources` for `static/` and `kits/`; wheel + pipx paths verified in CI
  (brief 11).
- Desktop: Developer ID signing, notarization, DMG, auto-update against GitHub Releases,
  CI builds that refuse dirty trees, bundle slimming, sidecar-import smoke (brief 15).
- Plugin: LICENSE + repository field, real tests, bundled webview, marketplace-ready
  packaging (briefs 02 and 16).
- Contract: document the queue-entry schema and Tier-4 shapes; specify the streaming
  protocol (200-always, error-without-done, EOF-is-terminal); changelog discipline for
  breaking changes (brief 13).

**Exit test:** on a machine that has never seen Setsweep: `pipx install setsweep` +
`setsweep --web` works; the DMG opens without Gatekeeper surgery; the VSIX installs from
the marketplace; a viewport detects version skew and says so.

### Phase 4 — Docs meet strangers

- Public `ARCHITECTURE.md` distilled from `.local/DESIGN.md` (desk model, invariants,
  durable-vs-runtime split, tool tiers) — fixes the dangling references shipped today.
- Glossary (sitting, desk, patron, curator, founding, kit, sweep, egress, ledger,
  viewport); ten-minute quickstart with screenshots; generated CLI reference; sync-layer
  guidance for `.setsweep/runtime/`. All in brief 17.

**Exit test:** someone who has never seen the project installs it, founds a desk on a
real folder, and completes a sitting without asking a question the docs don't answer.

### Phase 5 — Prove it works

Measurement before beta; growth only on evidence. Full design in `docs/RELEASE.md`.

- Local-first metrics beacons (no phone-home): sittings, founding completions,
  time-to-first-approved-entry, quiet-close ratio, crash/hang/blank-window incidents
  (brief 18).
- `setsweep doctor`: one command that checks install, server, curator CLI, auth, desk
  integrity — the support channel's first question (brief 18).
- Dogfood cohort: Charles's own projects instrumented, weekly review questions answered.
- Release ladder: private alpha (3–5 outside users) → public beta → 1.0, with the entry
  and exit gates in `docs/RELEASE.md`.

**Exit test:** the beta go/no-go is decided from the metrics file, not from vibes.

### Phase 6 — Grow the surface

Post-beta expansion, ordered by evidence of demand. Full analysis in `docs/PLATFORMS.md`.

- Obsidian adapter on the extracted `core-client` package — the writing/knowledge
  audience is half the kit system's reason to exist.
- MCP viewport: expose the desk as an MCP server so any MCP-capable host becomes a thin
  viewport for queue/approve/comment.
- JetBrains, Sublime, Neovim as demand shows; each consumes `API.md`, not TypeScript.
- Intake upgrades: FSEvents/inotify replacing cron polling (DESIGN §4's standing item).
- Kit `tools` slot wired for real (skills first) — the documented, tested, unwired
  extension point.
- The local-model tool harness (DESIGN "flagged future project"): a curated, fenced
  bash-utility layer that lets tool-less local models do real curator work.
- Re-founding as merge, not amnesia (DESIGN §4) — needs a real design.

## Progress scaffolding

How this roadmap stays true instead of rotting:

- **Briefs carry status.** Every workstream item is a brief in `docs/briefs/` with
  `status:` frontmatter (`open` → `in-progress` → `done`). The briefs index is the
  progress board; this file links, never duplicates.
- **`_Status.md` is the dashboard face.** Its Status paragraph is refreshed whenever a
  phase advances; its Next-action list points at the current phase's open briefs. The
  sidecar-dashboard contract stays honest because sweeps and sessions update it in the
  same change that does the work.
- **Exit tests are the phase truth.** A phase is done when its exit test passes in a
  fresh session, not when its briefs are marked done.
- **Every new automated actor beats a healthbeacon** (invariant 6) — the metrics beacons
  of Phase 5 extend the existing `~/.cache/setsweep/` convention, and `setsweep doctor`
  reads them.
- **Quarterly roadmap sitting.** Setsweep reviews itself: this repo is a registered desk;
  a quarterly sitting reads this file against reality and files the deltas.

## Decisions taken (reversible, but taken)

- **Editable install stays supported forever** — it is the contributor path; the wheel
  path is additive (Phase 3), not a replacement.
- **The single-file frontend is split for survivability, not rewritten** — a few plain
  `.js` files with no build step preserves the no-build property while making parse
  failures partial. A framework rewrite is not on this roadmap.
- **Desktop stays Electron-with-sidecar** through 1.0. DESIGN's pywebview-vs-Tauri
  question is answered by shipping evidence: the sidecar pattern works today; revisit
  only if bundle size or memory becomes a beta complaint.
- **Remote (non-localhost) viewports wait for Phase 2 auth**, and then arrive as tunnel
  guidance, not as a listening-on-0.0.0.0 flag.
- **No phone-home telemetry, ever.** Measurement is local files the patron owns; sharing
  them is a patron action (see `docs/RELEASE.md`).

## Open questions for the patron

Inherited from DESIGN §6 and still genuinely open: multi-desk sittings (unified queue
across projects, or one-desk-at-a-time as a feature?); the curator's voice (named persona
per project, or anonymous office?); interview-transcript retention (founding testimony
kept forever in the desk, or distilled and discarded?). New from this survey: which two
adapter platforms after VS Code (recommendation in `docs/PLATFORMS.md`: Obsidian, then
the MCP viewport); and whether 1.0's compatibility promise covers the desk file format
(recommendation: yes — the desk outlives the app; that is the point).
