# Sitting UI conventions

**Single frontend:** `static/index.html` (+ `themes.js`, fonts). Browser, CLI-launched
web, and **kettle-desktop** all load this file. Do not fork styles into the desktop
repo or the VS Code Desk webview without a deliberate shared token plan.

## Product palette (Kettle theme)

Host-neutral brand colors live in **`static/kettle-palette.json`** (16 ANSI colors +
interface/slot role indices for dark and light). That file is the source of truth for:

| Surface | Projection |
|---------|------------|
| Reference sitting / desktop | `static/themes.js` builtin `kettle` (must match; `test_palette.py`) |
| VS Code / Cursor | `kettle-vscode` generates `themes/kettle-*-color-theme.json` via `npm run sync-palette` |

Adapters own host packing (workbench keys, TextMate scopes). They do **not** invent a
second brand palette. After changing `kettle-palette.json`, update `themes.js` and
regenerate adapter themes so drift checks stay green.

When you touch sitting chrome, **read this file first**. Fixing one panel and leaving a
sibling panel on ad-hoc white text is a regression against these rules.

## Type hierarchy (required)

CSS variables live on `:root` in `static/index.html`. Prefer **role tokens**, not raw
`--fg` / hex, for chrome and supporting copy.

| Role | Token | Use for |
|------|--------|---------|
| **Heading** | `--text-heading` | Pane titles (`project`, `agent`), section chrome |
| **Label** | `--text-label` | Field names: ask, brief, path, status, “context” |
| **Secondary** | `--text-secondary` | Second lines in the queue, brief/ask *values*, supporting copy, meta values |
| **Primary** | `--text-primary` | File names in the queue, active control text, editor content |
| **Muted** | `--text-muted` | Tertiary / stream voice / syntax markers |
| **Link** | `--text-link` | Paths that open, wikilinks |
| **Good / warn** | `--text-good` / `--text-warn` | Diff adds, errors, urgency (via `--urg*`) |

Utility classes: `.t-heading`, `.t-label`, `.t-secondary`, `.t-primary`, `.t-muted`, `.t-link`.

**Implementation:** type tokens use `color-mix(in srgb, var(--fg) N%, var(--bg))`, **not**
`var(--dim)`. Theme defaults set `--muted`/`--dim` equal to `--fg` (opacity is applied
only to some iface roles in JS), so aliasing labels to `--dim` made subheaders the same
white as body text. Always mix toward `--bg` for gray chrome.

### Rules of thumb

1. **Chrome is gray.** Pane headers and field labels are never body-white (`--fg` / `--text-primary`).
2. **Supporting copy is gray.** Brief text, ask text, queue second lines, meta values → `--text-secondary`.
3. **Primary ink is scarce.** Queue *file names*, editor body, focused control labels.
4. **New panes inherit the ladder.** A new tab or panel must map every string to a role *before* shipping; do not default new copy to `--fg` because it “looks fine alone.”
5. **Same roles across tabs.** Info and Brief share `#meta dt` / `#meta dd` roles — do not invent a second type scale for a sibling tab.
6. **Selection is subtle.** Active queue row: faint link wash (`--row-active-bg`) only — no left bar.
   Mid chrome bars (`#midbar`, `#midfoot`) use the same wash so selection and editor chrome match.
7. **Diff badges** color `.qdiff .add` / `.del` with good/warn in **both** midbar and queue.
8. **Icon-only chrome** (reload, settings): `.btn-icon.btn-ghost` is borderless — no box around glyphs.

## Titles, heds, subheds

User-facing **titles, headings, and subheadings** use **Title Case** across web,
plugin Desk, and generated desk documents (e.g. **Desk Proposal**, **Beginning Interview**,
**Desk Confirmation Card**, **Found Desk**, **Add Project**).

- Markdown document heds written by the curator (`#` / `##` in `DESK-PROPOSAL.md`,
  egress notes, etc.) follow the same rule — prompts name the headings in Title Case.
- Queue entry **titles** (not body `ask`/`brief` prose) are Title Case.
- Mid-sentence product names of those actions match Title Case when referred to as
  the control or document name.

## Buttons

Shared kit: `.btn` + `.btn-sm` / `.btn-md` + role (`.btn-default` | `.btn-primary` | `.btn-ghost` | `.btn-signature`).

- Ordinary default / primary / ghost labels: **lowercase**, same font as the rest of the UI
  (e.g. `sweep`, `approve` in midfoot chrome).
- **Named signature actions that are also titles** (e.g. **Found Desk**, **Draft Proposal ✓**,
  **Start Interview**) stay Title Case so they match their hed/title role.
- Do not recolor a single midfoot action (e.g. `#comment`) with `--link` — it breaks the kit.
- Signature actions (sweep) may keep uppercase tracking; that is intentional emphasis.

## Urgency

- Color squares only (`.dot.high|medium|low`); **no H/M/L letters** in the glyph.
- Always set `title` + `aria-label` for the urgency name (a11y without text-in-dot).
- Low = green (`--urglow` → green ANSI), not gray.

## Meta pane (brief / info)

- Default tab: **brief** (ask + brief).
- **Labels** (`ask`, `brief`, `path`, …): `--text-label` (gray).
- **Bodies** (the ask sentence, the brief paragraph, path values): `--text-primary` (readable white).
  Do not paint the whole pane secondary gray — only the subheaders.
- Do not auto-inject the brief into chat on file select — brief lives in this pane.

## Shared UI copy (all viewports)

User-facing **strings** must not drift between web, desktop, and the plugin Desk.

| Role | Location |
|------|----------|
| **Canonical (edit here only)** | `static/ui-copy.js` → `window.KETTLE_UI_COPY` (`/ui-copy.js`) |
| **VS Code (generated)** | `kettle-vscode/src/uiCopy.ts` — **do not hand-edit** |
| **Desktop** | inherits web (same static files via sidecar) |

**Workflow**

1. Edit `kettle-core/static/ui-copy.js` only.
2. In the plugin package: `npm run sync-ui-copy`, then commit the generated snapshot.
3. Run `npm run check-ui-copy` against the intended core checkout.
4. Ordinary plugin compile/package consumes the committed snapshot and stays
   sibling-independent; rebuild/reinstall the VSIX if needed.

`KETTLE_SRC` (core root) or `KETTLE_UI_COPY` (path to `ui-copy.js`) override discovery
when the repos are not siblings.

**Test:** `test_ui_copy.py` asserts core keys exist and, when the plugin tree is present,
that generated `uiCopy.ts` still matches (CI safety if someone hand-edits the mirror).

## Founding / add project (brief 22)

- Add-project **hot path:** name + folder only. Kit, max depth, and notes live under
  *more options* (collapsed by default).
- Name may be derived from the folder basename when left blank.
- After add, land in **founding chrome** (agent pane interview + project-list empty-state),
  not a blank three-pane with no orientation.
- Empty queue during founding/proposing uses `.qfounding-hint` with `--text-secondary` body
  and `--text-label` strong headers — same type ladder as the rest of the sitting.

## Checklist before merging UI

- [ ] Every new string maps to a type role in the table above.
- [ ] No new `color: var(--fg)` on labels, pane titles, or supporting paragraphs.
- [ ] Buttons use the shared kit; midfoot actions match each other.
- [ ] Bump `meta name="kettle-ui"` content so reloads are obvious.
- [ ] Desktop: no CSS fork — only core `static/` (rebuild sidecar for packaged app).

## Editor / desktop note

| Viewport | UI source |
|----------|-----------|
| Web / `kettle --web` | `static/index.html` |
| Desktop `.app` | Same file via sidecar |
| VS Code / Cursor Desk | Separate `deskPanel.ts` — should *follow* these roles when restyled; not a second source of truth for the main sitting |
