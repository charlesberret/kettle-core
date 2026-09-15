# Kettle design tokens (LLM handoff)

Use this palette for any UI, illustration, mock, or brand-adjacent design work for **Kettle**.
Do not invent a competing palette. Prefer semantic roles over raw hue names.

## Character

- Quiet, instrument-like review desk — not a neon SaaS dashboard.
- Cool near-neutral surfaces with soft blue-gray ink.
- Accents are restrained: coral/rose for warn, moss green for good, gold (dark) or steel blue (light) for accent.
- High legibility for long reading sessions; avoid pure black/white extremes except as rare highlights.
- Dark mode is the default product feel; light mode is a true inverse, not a washed gray.

## Source of truth

**`kettle/static/kettle-palette.json` is the single machine-readable source.** It is
generated (`_note` in the file names the pipeline) and must not be hand-edited. This
markdown is a **human-readable projection** of that file, kept in sync by hand — if the
two ever disagree, the JSON wins; re-derive this file from it rather than trusting stale
tables here.

- Marquee product palette (JSON, canonical): `kettle-core/kettle/static/kettle-palette.json`
- Full theme pack: `kettle-core/kettle/static/themes/kettle.json`
- VS Code projection: `kettle-vscode/themes/kettle-{dark,light}-color-theme.json`
- Schema: 16 ANSI colors + `iface`/`slots` role → ANSI index maps, plus a `resolved` block
  with the already-opacity-blended hex for the roles (`panel`, `panel2`, `activebg`,
  `muted`) that are painted as an alpha wash over the base surface rather than a flat
  ANSI color (see `ifaceOpacity` in the JSON). The tables below show the **fully
  resolved** hex either way — index lookup for flat roles, the `resolved` value for
  blended ones.

## ANSI ladder (shared 16)

Index order is standard terminal: 0–7 normal, 8–15 bright.

### Dark ANSI

| Idx | Name | Hex |
|----:|------|-----|
| 0 | black | `#16161e` |
| 1 | red | `#d4756b` |
| 2 | green | `#7dba6f` |
| 3 | yellow | `#c8a24a` |
| 4 | blue | `#7d9fc7` |
| 5 | magenta | `#9f7bc7` |
| 6 | cyan | `#389bb4` |
| 7 | white | `#d8d8e0` |
| 8 | bright black | `#3f3f4e` |
| 9 | bright red | `#e79187` |
| 10 | bright green | `#9ad08e` |
| 11 | bright yellow | `#ddbb70` |
| 12 | bright blue | `#98b6da` |
| 13 | bright magenta | `#b495d9` |
| 14 | bright cyan | `#60b1c7` |
| 15 | bright white | `#ececf2` |

### Light ANSI

| Idx | Name | Hex |
|----:|------|-----|
| 0 | black | `#dfe1e8` |
| 1 | red | `#8e1904` |
| 2 | green | `#00591a` |
| 3 | yellow | `#855100` |
| 4 | blue | `#1b4979` |
| 5 | magenta | `#633f81` |
| 6 | cyan | `#006276` |
| 7 | white | `#181a23` |
| 8 | bright black | `#bcbdc6` |
| 9 | bright red | `#b23a26` |
| 10 | bright green | `#287735` |
| 11 | bright yellow | `#a56e28` |
| 12 | bright blue | `#366699` |
| 13 | bright magenta | `#815ba1` |
| 14 | bright cyan | `#2c8095` |
| 15 | bright white | `#fdfdff` |

## Resolved interface roles

`iface` maps a semantic UI role to an ANSI index. Hex below is fully resolved: a flat
ANSI lookup for most roles, or the JSON's own `resolved` value for the opacity-blended
ones (`panel`, `panel2`, `activebg`, `muted` — see `ifaceOpacity`).

### Dark iface

| Role | Hex | ANSI idx | Use |
|------|-----|---------:|-----|
| `bg` | `#16161e` | 0 | Primary surface / canvas |
| `fg` | `#d8d8e0` | 7 | Primary text / ink |
| `muted` | `#8a8a92` | 7 (58% opacity onto `bg`) | Secondary / muted text |
| `panel` | `#1c1c24` | 0 (97% opacity onto `bg`) | Raised panel / chrome surface |
| `panel2` | `#1c1c24` | 0 (97% opacity onto `bg`) | Secondary panel |
| `line` | `#3f3f4e` | 8 | Borders, rules, hairlines |
| `acc` | `#c8a24a` | 3 | Accent (emphasis, highlights, dark-mode gold / light-mode blue) |
| `link` | `#7d9fc7` | 4 | Links and interactive focus cues |
| `activebg` | `#22222b` | 0 (95% opacity onto `bg`) | Active / selected row background |
| `selection` | `#7d9fc7` | 4 | Text selection wash (often used with alpha) |
| `good` | `#7dba6f` | 2 | Success / low urgency / positive |
| `warn` | `#d4756b` | 1 | Warning / high urgency / error-adjacent |
| `urghigh` | `#d4756b` | 1 | Urgency: high |
| `urgmed` | `#c8a24a` | 3 | Urgency: medium |
| `urglow` | `#7dba6f` | 2 | Urgency: low |

The JSON's `resolved` block also names `well` (`#101017`) and `highlight`
(`#ececf2`) and `faint` (`#6c6d74`) — deeper-well and faint-text shades used by some
consumers beyond the legacy `iface` role set above.

**Derived alpha washes** (mechanically computed — 33%/66% hex-alpha suffix on the base
`resolved` hex above; not a literal field in `kettle-palette.json`):

- `selection` wash: `#7d9fc755` (33%, for inactive selection)
- `lineHighlight`: `#3f3f4e66`

### Light iface

| Role | Hex | ANSI idx | Use |
|------|-----|---------:|-----|
| `bg` | `#dfe1e8` | 0 | Primary surface / canvas |
| `fg` | `#181a23` | 7 | Primary text / ink |
| `muted` | `#5b5d66` | 7 (52% opacity onto `bg`) | Secondary / muted text |
| `panel` | `#e7e9ee` | 15 (92% opacity onto `bg`) | Raised panel / chrome surface |
| `panel2` | `#e7e9ee` | 15 (92% opacity onto `bg`) | Secondary panel |
| `line` | `#bcbdc6` | 8 | Borders, rules, hairlines |
| `acc` | `#1b4979` | 4 | Accent (emphasis, highlights, dark-mode gold / light-mode blue) |
| `link` | `#1b4979` | 4 | Links and interactive focus cues |
| `activebg` | `#f0f1f5` | 15 (95% opacity onto `bg`) | Active / selected row background |
| `selection` | `#366699` | 12 | Text selection wash (often used with alpha) |
| `good` | `#00591a` | 2 | Success / low urgency / positive |
| `warn` | `#8e1904` | 1 | Warning / high urgency / error-adjacent |
| `urghigh` | `#8e1904` | 1 | Urgency: high |
| `urgmed` | `#855100` | 3 | Urgency: medium |
| `urglow` | `#00591a` | 2 | Urgency: low |

The JSON's `resolved` block also names `well` (`#d7d9df`) and `highlight`
(`#fdfdff`) and `faint` (`#787a82`) — deeper-well and faint-text shades used by some
consumers beyond the legacy `iface` role set above.

**Derived alpha washes** (mechanically computed — 33%/66% hex-alpha suffix on the base
`resolved` hex above; not a literal field in `kettle-palette.json`):

- `selection` wash: `#36669955` (33%, for inactive selection)
- `lineHighlight`: `#bcbdc666`

## Content / stream slots

### Dark slots

| Slot | Hex | ANSI idx | Use |
|------|-----|---------:|-----|
| `mdhead` | `#c8a24a` | 3 | Markdown headings |
| `ctxhead` | `#d8d8e0` | 7 | Context block headers |
| `ctxbody` | `#d8d8e0` | 7 | Context body text |
| `cmthead` | `#d8d8e0` | 7 | Comment headers |
| `comment` | `#7d9fc7` | 4 | Comments / annotations |
| `agent` | `#d8d8e0` | 7 | Agent / curator stream text |
| `user` | `#7d9fc7` | 4 | User / human stream text |

### Light slots

| Slot | Hex | ANSI idx | Use |
|------|-----|---------:|-----|
| `mdhead` | `#1b4979` | 4 | Markdown headings |
| `ctxhead` | `#181a23` | 7 | Context block headers |
| `ctxbody` | `#181a23` | 7 | Context body text |
| `cmthead` | `#181a23` | 7 | Comment headers |
| `comment` | `#1b4979` | 4 | Comments / annotations |
| `agent` | `#181a23` | 7 | Agent / curator stream text |
| `user` | `#1b4979` | 4 | User / human stream text |

## VS Code chrome surfaces (projected)

Useful when matching editor/plugin chrome, not required for greenfield web/app design.
This table is a separate hand projection into VS Code's own token names (source:
`kettle-vscode/themes/kettle-{dark,light}-color-theme.json`), not a section of
`kettle-palette.json` — check that file directly before relying on exact hexes here.

### Dark

| Token | Hex |
|-------|-----|
| `editor.background` | `#16161e` |
| `editor.foreground` | `#d8d8e0` |
| `sideBar.background` | `#101016` |
| `activityBar.background` | `#0d0d11` |
| `panel.background` | `#101016` |
| `statusBar.background` | `#0d0d11` |
| `button.background` | `#7d9fc8` |
| `button.foreground` | `#16161e` |
| `focusBorder` | `#7d9fc8` |
| `textLink.foreground` | `#9db4d8` |
| `input.background` | `#1e1e26` |
| `input.border` | `#32323f` |
| `list.activeSelectionBackground` | `#32323f` |
| `list.hoverBackground` | `#22222a` |
| `editor.selectionBackground` | `#7d9fc855` |

### Light

| Token | Hex |
|-------|-----|
| `editor.background` | `#f4f4f6` |
| `editor.foreground` | `#1a1a22` |
| `sideBar.background` | `#eaeaee` |
| `activityBar.background` | `#e5e5e9` |
| `panel.background` | `#eaeaee` |
| `statusBar.background` | `#e5e5e9` |
| `button.background` | `#2f5f9a` |
| `button.foreground` | `#ffffff` |
| `focusBorder` | `#2f5f9a` |
| `textLink.foreground` | `#7d9fc8` |
| `input.background` | `#fafafb` |
| `input.border` | `#d8d8de` |
| `list.activeSelectionBackground` | `#d8d8de` |
| `list.hoverBackground` | `#ededf0` |
| `editor.selectionBackground` | `#7d9fc855` |

## Machine-readable

**Read `kettle/static/kettle-palette.json` directly** — it is the single
machine-readable source, generated by an out-of-repo promotion pipeline (see
`docs/THEMES.md`), and must not be hand-edited. Do not paste a second full copy of it
into this markdown: a stale hand-maintained duplicate here is exactly what drifted out
of sync with the real file before this fix. If you need the JSON somewhere else, copy
it fresh from `kettle/static/kettle-palette.json` (or `kettle/static/themes/kettle.json`
for the full pack) at the time you need it.

## Design rules for agents

1. **Stay on-palette.** Only use colors from the tables above (or transparent mixes of them).
2. **Prefer roles.** `bg`/`fg`/`line`/`acc`/`link`/`good`/`warn` — not "that blue".
3. **Accent sparingly.** One accent per region; gold (dark) or steel blue (light) for focus, not decoration spam.
4. **Warn is coral/rose, good is moss** — do not swap traffic-light hues.
5. **Surfaces stay cool gray-blue**, never warm beige or pure black voids.
6. **Type:** system UI sans for chrome; monospace only for code/paths. Keep long-form body at comfortable contrast (use `fg` on `bg`, not `muted` for primary reading).
7. **Borders** use `line` (`bright black`); avoid pure white 1px outlines on dark.
8. When generating CSS variables, name them after roles: `--kettle-bg`, `--kettle-fg`, `--kettle-acc`, etc.

## Suggested CSS variables

```css
:root, [data-theme="dark"] {
  --kettle-bg: #16161e;
  --kettle-fg: #d8d8e0;
  --kettle-muted: #8a8a92;
  --kettle-panel: #1c1c24;
  --kettle-panel2: #1c1c24;
  --kettle-line: #3f3f4e;
  --kettle-acc: #c8a24a;
  --kettle-link: #7d9fc7;
  --kettle-activebg: #22222b;
  --kettle-selection: #7d9fc7;
  --kettle-good: #7dba6f;
  --kettle-warn: #d4756b;
  --kettle-urghigh: #d4756b;
  --kettle-urgmed: #c8a24a;
  --kettle-urglow: #7dba6f;
}
[data-theme="light"] {
  --kettle-bg: #dfe1e8;
  --kettle-fg: #181a23;
  --kettle-muted: #5b5d66;
  --kettle-panel: #e7e9ee;
  --kettle-panel2: #e7e9ee;
  --kettle-line: #bcbdc6;
  --kettle-acc: #1b4979;
  --kettle-link: #1b4979;
  --kettle-activebg: #f0f1f5;
  --kettle-selection: #366699;
  --kettle-good: #00591a;
  --kettle-warn: #8e1904;
  --kettle-urghigh: #8e1904;
  --kettle-urgmed: #855100;
  --kettle-urglow: #00591a;
}
```
