# Sitting UI conventions

**Single frontend:** `static/index.html` (+ `themes.js`, fonts). Browser, CLI-launched
web, and **setsweep-desktop** all load this file. Do not fork styles into the desktop
repo or the VS Code Desk webview without a deliberate shared token plan.

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
| **Muted** | `--text-muted` | Tertiary / default stream voice |
| **Link** | `--text-link` | Paths that open, wikilinks |
| **Good / warn** | `--text-good` / `--text-warn` | Diff adds, errors, urgency (via `--urg*`) |

Utility classes: `.t-heading`, `.t-label`, `.t-secondary`, `.t-primary`, `.t-muted`, `.t-link`.

### Rules of thumb

1. **Chrome is gray.** Pane headers and field labels are never body-white (`--fg` / `--text-primary`).
2. **Supporting copy is gray.** Brief text, ask text, queue second lines, meta values → `--text-secondary`.
3. **Primary ink is scarce.** Queue *file names*, editor body, focused control labels.
4. **New panes inherit the ladder.** A new tab or panel must map every string to a role *before* shipping; do not default new copy to `--fg` because it “looks fine alone.”
5. **Same roles across tabs.** Info and Brief share `#meta dt` / `#meta dd` roles — do not invent a second type scale for a sibling tab.

## Buttons

Shared kit: `.btn` + `.btn-sm` / `.btn-md` + role (`.btn-default` | `.btn-primary` | `.btn-ghost` | `.btn-signature`).

- Default / primary / ghost labels: **lowercase**, same font as the rest of the UI.
- Do not recolor a single midfoot action (e.g. `#comment`) with `--link` — it breaks the kit.
- Signature actions (sweep) may keep uppercase tracking; that is intentional emphasis.

## Urgency

- Color squares only (`.dot.high|medium|low`); **no H/M/L letters** in the glyph.
- Always set `title` + `aria-label` for the urgency name (a11y without text-in-dot).
- Low = green (`--urglow` → green ANSI), not gray.

## Meta pane (brief / info)

- Default tab: **brief** (ask + brief).
- Labels use `--text-label`; ask and brief *bodies* use `--text-secondary` (not primary white).
- Do not auto-inject the brief into chat on file select — brief lives in this pane.

## Checklist before merging UI

- [ ] Every new string maps to a type role in the table above.
- [ ] No new `color: var(--fg)` on labels, pane titles, or supporting paragraphs.
- [ ] Buttons use the shared kit; midfoot actions match each other.
- [ ] Bump `meta name="setsweep-ui"` content so reloads are obvious.
- [ ] Desktop: no CSS fork — only core `static/` (rebuild sidecar for packaged app).

## Plugin / desktop note

| Viewport | UI source |
|----------|-----------|
| Web / `setsweep --web` | `static/index.html` |
| Desktop `.app` | Same file via sidecar |
| VS Code / Cursor Desk | Separate `deskPanel.ts` — should *follow* these roles when restyled; not a second source of truth for the main sitting |
