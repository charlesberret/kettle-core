# Sitting UI conventions

**Single frontend:** `static/index.html` (+ `themes.js`, fonts). Browser, CLI-launched
web, and **kettle-desktop** all load this file. Do not fork styles into the desktop
repo or the VS Code Desk webview without a deliberate shared token plan.

## Product palette and theme packs

Host-neutral **theme packs** live under **`static/themes/`** (marquee default:
`kettle.json`). The shortcut **`static/kettle-palette.json`** mirrors the marquee
pack for brand-only consumers. Full story: [`THEMES.md`](./THEMES.md).

| Surface | Projection |
|---------|------------|
| Reference sitting / desktop | `static/themes.js` builtins + Appearance UI |
| Built-in CLI editor | `theme_catalog` + `syntax` + `tui_editor` |
| VS Code / Cursor | `npm run sync-palette` from marquee palette |

Adapters own host packing. They do **not** invent a second brand palette.
After changing the marquee pack, keep `themes.js` / `kettle-palette.json` aligned
(`tests/test_palette.py`) and regenerate VS Code themes.

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
   Mid chrome bars (`#midbar`, `#midfoot`) use the canvas (`--bg`) so they match the editor body,
   not the queue selection tint.
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

## Who the words are for

Kettle keeps precise internal terms **and** talks to users in words they already have.
Those are two registers, and `kettle/kits/_lexicon.json` is where they stay straight.

| Audience | Where | Example |
|---|---|---|
| `house` | code, prompts, docs, our own conversation | desk, sitting, sweep, ruling, charter, founding, brief, entry |
| `both` | anywhere, users included | project, file, queue, agent, proposal, Finish batch |

**A house word on screen is a CI error.** Not a style preference — the product's job is
to be usable without a glossary, and a user should never have to work out what a "desk"
or a "sitting" is to review their own files. The lexicon names the plain word and
`tools/lint-lexicon.py` quotes it as the fix.

This replaces an earlier rule that enforced spelling our vocabulary consistently
*everywhere*, screen included. That protected the vocabulary and cost the reader; it
also hardened into CI exactly the entrenchment it should have caught.

**No invented words on screen, buttons included.** The button that ends a batch was
"Sweep" until 2026-10-06; it is **Finish batch** now, and "sweep" is a house word like the
rest. Prose that names a control still says what it does: "press Finish batch: the agent
applies your decisions." Any house word in explanatory copy is a bug.

The unit of a user's concern is **their project**. Never a desk, and never a "project
desk".

## Shared UI copy (all viewports)

User-facing **strings** must not drift between web, desktop, the plugin Desk, and
the TUI.

| Role | Location |
|------|----------|
| **Canonical (edit here only)** | `kettle/static/ui-copy.json` |
| **Web / desktop** | `GET /ui-copy.js` → `window.KETTLE_UI_COPY`, rendered from the JSON per request |
| **Python viewports (CLI, TUI)** | `kettle.uicopy`, or `GET /api/ui-copy` out of process |
| **VS Code (generated)** | `kettle-vscode/src/uiCopy.ts` — **do not hand-edit** |

There is no committed JavaScript copy of the catalog. `static/ui-copy.js` used to
exist and was deleted: a generated file beside its source is a second source, and
it drifted.

### Each entry

```json
"sweepLabel": {
  "text": "Finish batch",
  "short": "Finish",
  "note": "The button that ends a batch. Internally this is a sweep; the word stays off screen."
}
```

- **`text`** — the string. Case follows *Titles, heds, subheds* and *Buttons* above.
- **`short`** — optional, for a surface too narrow for the full string (a TUI status
  bar, a two-line pane). Same meaning in fewer words — **never a different
  instruction**. A viewport asks for it; it falls back to `text`.
- **`note`** — where this appears and what it is for, written for a reader who has
  only the key. Required: it is what lets an agent act on a key it has never seen.
  `tests/test_ui_copy.py` fails on a key without one.

### Binding a string in the sitting

Tag the element; do not read the catalog by hand.

| Attribute | Sets |
|---|---|
| `data-uic="key"` | `textContent` |
| `data-uic-title="key"` | `title` |
| `data-uic-ph="key"` | `placeholder` |
| `data-uic-aria="key"` | `aria-label` |

**Keep the real English in the markup.** It is the fallback when `/ui-copy.js`
cannot load, so the sitting degrades to today's wording rather than to blank
shells. A test asserts every tagged literal equals its catalog text byte for byte
— if you change one, change both.

Tag the **leaf** that holds the text. `data-uic` on a wrapper would delete its
child elements; the boot pass refuses that case and records it instead.

### Workflow

1. Edit `kettle/static/ui-copy.json` only.
2. Update the literal in `index.html` to match, if the string is tagged there.
3. In the plugin package: `npm run sync-ui-copy`, then commit the generated
   snapshot. `npm run check-ui-copy` verifies it against the intended core checkout.
4. `KETTLE_SRC` (core root) or `KETTLE_UI_COPY` (path to `ui-copy.json`) override
   discovery when the repos are not siblings.

**Tests:** `tests/test_ui_copy.py` checks required keys, that every key has a note,
that no `short` is longer than its `text`, that every `data-uic*` tag resolves, that
tagged literals match exactly, and — when the plugin tree is checked out beside core
— that the generated mirror still agrees.

## UI debug mode

Diagnostics → **Inspect Interface Copy**, or `?uidebug=1` for one load. Off by
default; the flag lives in `localStorage`, never in `settings.json`, because it is
a per-viewer developer affordance and must not follow a project to another machine.

It outlines every element bound to a catalog key, pins an inspector showing that
key, what it binds, the owning file and the catalog note, and produces one
pasteable reference line — which is the point: an agent can act on
`key=sweepLabel · file=kettle/static/ui-copy.json`, and cannot act on "the gray
text under the queue".

Alt+click edits a string in place. Edits are **overrides**, written to
`sitting-overrides.json` beside `settings.json` — never into `static/` (read-only
once installed) or `index.html` (run-critical). Overriding a *key* reaches every
viewport; overriding a *selector* relabels one element of this sitting only, until
`GET /api/ui-copy/promote` says what it takes to give it a key.

Size and placement are **tokens, not drag handles**: the inspector lists the CSS
custom properties the rules matching that element read, and each is editable live.
The sitting cannot express arbitrary geometry, and the value lives in a token
either way.

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
