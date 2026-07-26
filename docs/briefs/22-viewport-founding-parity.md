---
id: 22
title: Viewport founding parity — web canonical, desktop inherits
repo: kettle-core
touches: [static/index.html, docs/PLATFORMS.md, docs/UI.md, README founding section; plugin only if web catches up and Desk still diverges]
risk: run-critical
depends-on: [08, 21]
status: done
---

## Context

As of 2026-07-22, the **plugin Desk** feels further ahead on founding new projects than
the **desktop app**. That is not because Electron forked founding — desktop loads
`kettle-core/static/index.html` via the sidecar. The real split:

| Path | Experience |
|------|------------|
| **Plugin** | Register / begin interview **in the Desk panel**; fixed founding stream; confirm-card upgrade; proposal approve in-context |
| **Web / desktop** | Multi-field **add project** modal + setup modal density; interview in the right pane works, but the *entry* still feels like a form popup |

So desktop “behind” means **shared sitting chrome is behind the plugin’s host-adapted
ritual**. Polishing desktop alone would invent a second product. The roadmap and
[`docs/PLATFORMS.md`](../PLATFORMS.md) now name **web as canonical** and track a ritual
parity matrix so this class of drift is visible.

Related: brief 21 tightened setup/add modal *styles*; it did not re-home founding into
the sitting the way the Desk did. `docs/UI.md` covers type hierarchy; this brief covers
**founding / first-run product shape**.

## Task

1. **Map the two flows side by side** (checklist in the brief’s Verify section): plugin
   `beginFounding` + Desk founding view vs web `#addmodal` / `#setupmodal` / `#foundinghead`
   / interview stream. List every step the user takes; mark which should stay host-only
   (e.g. VS Code folder picker).

2. **Redesign web first-run + add-project toward the Desk quality bar**, without
   abandoning API Tier 3:
   - Fewer fields in the hot path (name + folder; kit with smart default).
   - Prefer **in-sitting** interview (right pane already owns this) over stacked dialogs.
   - After add, land straight into founding chrome (founding head + agent pane), not a
     dead three-pane with an empty queue and no explanation.
   - Keep confirm-card → proposal → approve → found identical to current API contracts.
   - Honor `docs/UI.md` type roles for every new string (labels gray, no ad-hoc white).

3. **Desktop:** no separate implementation. After web lands, rebuild or re-run sidecar
   so the `.app` picks up `static/`. Document one line in kettle-desktop README if the
   rebuild step is easy to miss.

4. **Plugin:** only change if the web ritual now *exceeds* Desk and Desk would confuse
   users — or if Desk still invents a second state machine. Prefer folding Desk
   presentation improvements *into* web first. Optional follow-on: align Desk CSS with
   UI.md tokens (out of scope unless cheap).

5. **Update the ritual parity matrix** in `docs/PLATFORMS.md` so founding rows read
   **same** across web · desktop · plugin (host-only cells called out).

## Constraints

- `static/index.html` is run-critical — suite + `node --check` / `test_frontend.py`
  before and after; never edit from inside a live Kettle sitting.
- Do not bind port 4242 from agent tooling.
- Do not add an Electron-only founding dialog.
- Do not break `GET/POST /api/interview`, `/api/propose`, `/api/found` contracts;
  viewports consume them, they do not redefine them.
- Setup modal remains the hard curator gate (Esc does not dismiss) unless a deliberate
  product change is documented.

## Done when

- A user on **web** and on **desktop** (same core build) can add a folder and complete
  founding without hitting a dense multi-box form that the plugin path avoids.
- State machine remains `none → interviewing → proposing → founded` from the API.
- PLATFORMS ritual matrix updated; brief status `done`.
- UI.md checklist still green (type roles on new copy).
- Full pytest green; frontend convention tests green.

## Verify

1. Cold path (ephemeral port, never 4242): fresh settings + empty registry → setup →
   add project → interview → finish → edit proposal → approve → content queue appears.
2. Same path under desktop dev (`npm start` with editable core) or packaged app after
   sidecar rebuild.
3. Plugin: founding still works; if web improved, no regression on Desk begin-founding.
4. Grep/docs: PLATFORMS founding rows no longer mark web/desktop as the weak entry.

## Afterwards

- `status: done` on this brief; roadmap Phase 4 open bullet for parity can tick.
- If plugin Desk CSS still diverges on type hierarchy, file a small plugin brief or
  extend 16 — do not block core merge.
- Note in `_Status.md` that desktop founding tracks web.

## Closing note (2026-07-22)

| Step | Plugin | Web / desktop (after this brief) |
|------|--------|----------------------------------|
| Start core | auto-start `:4242` | `kettle --web` / Electron sidecar |
| Add project | host folder + API | modal: **name + folder**; kit/depth/note under *more options*; name auto from path |
| Interview | Desk founding pane | right pane + founding head; queue empty-state points to agent |
| Proposal | editor + approve | same |
| Found | first queue batch | same |

Desktop inherits web static only — rebuild sidecar for packaged `.app`.
