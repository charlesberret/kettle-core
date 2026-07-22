# Setsweep — Platforms & Viewports

*Companion to [`ROADMAP.md`](../ROADMAP.md). Current-state claims below: **2026-07-22**
(brief 22 founding parity). Refresh this file when a viewport ships a ritual change.
Stale matrices are how desktop “falls behind” without anyone forking it.*

## What a viewport is

A viewport is a thin client on the localhost core. It renders the desk; it holds no desk
state of its own (the desk is files in `.setsweep/`; the wire contract is
[`API.md`](../API.md)). Viewports differ only in how much of the contract they speak and
how they host chrome.

| Level | What the patron can do | API surface |
|---|---|---|
| **A — attach + read** | Find the live core, see the queue and briefs | Discovery (`server.json` → `:4242`), `GET /api/ping`, `/api/projects`, `/api/queue`, `/api/file` |
| **B — full sitting** | Approve, comment, diffs, sweep, chat | Tiers 1–2 writes + NDJSON streams |
| **C — founding** | Bring a new folder under care | Interview → propose → approve proposal → found (Tier 3) |

Tier A is the floor. Tier B is a real sitting. Tier C is the product’s front door — and
the place viewports have diverged.

## Canonical UI rule (non-negotiable)

| Surface | Source of truth |
|---------|-----------------|
| **Sitting chrome** (queue, editor, agent pane, modals, type scale) | `setsweep-core/static/index.html` + [`docs/UI.md`](./UI.md) |
| **Desktop `.app`** | **No separate frontend** — BrowserWindow loads the sidecar’s web app |
| **Plugin Desk** | Host-adapted UI (`deskPanel.ts`) — may layout for the editor, but **rituals must match** the web state machine and copy bar |
| **CLI** | Serverless desk access; no full graphical founding |

**Implication:** if desktop “looks behind” the plugin on founding, fix **web** (and the
plugin only if it still diverges). Do not invent an Electron-only wizard.

## Capability matrix (A/B/C)

| Viewport | A | B | C | Notes (2026-07-22) |
|---|---|---|---|---|
| **Web** (`static/index.html`) | yes | yes | yes | Reference sitting: kits, lineage, admin, themes, UI.md type roles. |
| **Desktop** (Electron) | yes | yes | yes | Same UI as web via sidecar. Gaps = **web gaps** + distribution (brief 15). |
| **VS Code / Cursor** (plugin ≥0.6.4) | yes | yes | yes | Auto-starts core on `:4242`. Full Desk sitting; founding **in-panel** (quality bar for C). No full kits/lineage/admin parity with web. |
| **CLI** | yes | partial | yes | `found` / `queue` / `chat` / sweep helpers; no graphical approve/comment. |

## Ritual parity matrix (the real product)

Same ritual, every graphical viewport. Cells: **same** (matches canonical web) ·
**better** (ahead of web — must fold back) · **gap** · **host-only** (OK) · **n/a**.

| Ritual | Web | Desktop | Plugin | CLI |
|--------|-----|---------|--------|-----|
| Discover / start core | same | same (sidecar) | same (auto-start default → live `:4242`) | n/a |
| First-run curator setup | same (setup modal, hard gate) | same | host settings + core settings deep-link | ambient CLI auth |
| Add / register project | same (name + folder hot path; kit/depth/note under *more options*) | same | host-only folder pick + API | `setsweep add` |
| Founding interview | same (right pane + founding head; empty queue orients to agent) | same | same ritual (Desk layout; fixed founding stream) | `setsweep found` / chat |
| Confirm card → proposal | same | same | same (confirm-card logic) | n/a |
| Proposal approve → found | same | same | same | n/a |
| Sitting (approve / comment / sweep) | same | same | same (Desk ritual buttons) | partial |
| Type hierarchy (gray chrome) | same (UI.md) | same | **gap** (Desk CSS still separate) | n/a |
| Brief on file select | left brief tab; no auto chat dump | same | Desk brief region | n/a |

**Closed (brief 22):** web/desktop add-project and founding entry match the Desk quality bar
(minimal hot path, interview in-agent, empty-state orientation). Remaining optional debt:
plugin Desk CSS vs UI.md tokens.

## Founding / first-run parity (track owner: brief 22)

### Canonical state machine (all viewports)

```text
none → interviewing → proposing → founded
```

Derived from `GET /api/interview` (and project desk files), never guessed.

### Target product experience (web = canonical)

1. **Setup** once: pick curator provider (no API keys in Setsweep).  
2. **Add project**: name + folder (+ kit) with the lightest chrome that still works —
   not a dense debugging form. Plugin’s in-context start is the quality bar.  
3. **Interview** in the agent surface (right pane / Desk stream), not a second popup.  
4. **Finish** → editable proposal in the editor → **approve** → found + first queue.  
5. **Sitting** continues in the same window.

Desktop inherits steps 1–5 by shipping the web app. Plugin may keep VS Code layout
(Explorer queue + secondary Desk) but must not invent a second state machine.

### Anti-patterns

- Electron-only add-project dialogs that bypass web registration UX.  
- Plugin founding that never lands improvements back into `static/index.html`.  
- “Fix desktop founding” as a desktop brief when the code path is core static.

## Shared TypeScript client (plugin monorepo)

Host-agnostic seed in the VS Code package: `api.ts`, `discover.ts`, `confirmCard.ts`,
`state.ts`, `paths.ts`. Brief **16** extracts `packages/core-client`. Brief **02**
(reconcile plugin trees) is largely superseded by the 0.6.x single VSIX line — confirm
and close or retarget when working the monorepo.

For non-TS hosts, **`API.md` is the platform** (brief 13).

## Adapter candidates (post-parity)

| Rank | Host | Call |
|---|---|---|
| 1 | Obsidian | After founding parity + core-client (16) |
| 2 | MCP viewport | Queue/approve/comment tools; founding stays in full viewport |
| 3 | JetBrains | After demand + contract v1 (13) |
| 4–5 | Sublime / nvim / Emacs | On request or community |

## Desktop distribution road (brief 15)

Still distribution, not a second product UI:

1. Signing + notarization (Apple Developer ID)  
2. DMG + CI that refuses dirty core trees  
3. Auto-update from GitHub Releases  
4. Bundle slim; universal binary; then Windows/Linux horizon  
5. Sidecar crash → restart-with-backoff; curator-CLI onboarding copy  

UX polish for founding rides **brief 22 → core static → rebuild sidecar**.

## Remote access

No listen-on-0.0.0.0. After brief **05** (auth token), remote = **tunnel guidance** only
(SSH / Tailscale to `127.0.0.1:4242`).

## Multi-user server edition (Phase 7 — horizon)

**Not now.** Through 1.0, Setsweep is a **personal** instrument: one patron, one machine
(or one tunnel they control), many thin viewports. Shared state across web / plugin /
desktop is the single-desk model, not multi-tenancy.

A later **server edition** (roadmap Phase 7) would look more like **JupyterHub** than
like “open the port”:

| JupyterHub analogue | Setsweep sketch (when the phase opens) |
|---------------------|----------------------------------------|
| Hub + spawners | Hub routes users to isolated cores or desk sandboxes |
| Per-user home / notebook dir | Per-user (or per-team) desk roots + fence |
| Auth (OAuth, etc.) | Real identity; not a single shared boot token |
| Shared “studio” space | Shared org registry of desks; optional concurrent sittings with ownership |

Do not implement multi-user isolation as a side effect of adapter work (Obsidian, MCP).
When the phase is greenlit, add briefs under Phase 7; until then, concurrent viewports
for **one** patron remain the only supported multi-client pattern.

## Maintenance rule

When you change a ritual in any viewport:

1. Update the **ritual parity matrix** above.  
2. If web and plugin diverge, open or extend a brief — do not leave “better” stranded.  
3. Re-date the subtitle of this file.
