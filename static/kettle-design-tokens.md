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

- Marquee product palette: `kettle-core/static/kettle-palette.json`
- Full theme pack: `kettle-core/static/themes/kettle.json`
- VS Code projection: `kettle-vscode/themes/kettle-{dark,light}-color-theme.json`
- Schema: 16 ANSI colors + `iface`/`slots` role → ANSI index maps (not freeform hex soups).

## ANSI ladder (shared 16)

Index order is standard terminal: 0–7 normal, 8–15 bright.

### Dark ANSI

| Idx | Name | Hex |
|----:|------|-----|
| 0 | black | `#16161e` |
| 1 | red | `#d4756b` |
| 2 | green | `#7dba6f` |
| 3 | yellow | `#c8a24a` |
| 4 | blue | `#7d9fc8` |
| 5 | magenta | `#9a76c2` |
| 6 | cyan | `#389bb4` |
| 7 | white | `#d8d8e0` |
| 8 | bright black | `#32323f` |
| 9 | bright red | `#e8928a` |
| 10 | bright green | `#94c98a` |
| 11 | bright yellow | `#d4b86a` |
| 12 | bright blue | `#9db4d8` |
| 13 | bright magenta | `#b094d2` |
| 14 | bright cyan | `#59b4cc` |
| 15 | bright white | `#ececf2` |

### Light ANSI

| Idx | Name | Hex |
|----:|------|-----|
| 0 | black | `#f4f4f6` |
| 1 | red | `#c0392b` |
| 2 | green | `#2d7a3a` |
| 3 | yellow | `#9a7200` |
| 4 | blue | `#2f5f9a` |
| 5 | magenta | `#7a4a9a` |
| 6 | cyan | `#18788a` |
| 7 | white | `#1a1a22` |
| 8 | bright black | `#d8d8de` |
| 9 | bright red | `#d4756b` |
| 10 | bright green | `#7dba6f` |
| 11 | bright yellow | `#c8a24a` |
| 12 | bright blue | `#7d9fc8` |
| 13 | bright magenta | `#9a76c2` |
| 14 | bright cyan | `#389bb4` |
| 15 | bright white | `#ffffff` |

## Resolved interface roles

`iface` maps a semantic UI role to an ANSI index. Hex below is fully resolved.

### Dark iface

| Role | Hex | ANSI idx | Use |
|------|-----|---------:|-----|
| `bg` | `#16161e` | 0 | Primary surface / canvas |
| `fg` | `#d8d8e0` | 7 | Primary text / ink |
| `muted` | `#d8d8e0` | 7 | Secondary text (often mixed with bg for lower contrast) |
| `panel` | `#16161e` | 0 | Raised panel / chrome surface |
| `panel2` | `#16161e` | 0 | Secondary panel |
| `line` | `#32323f` | 8 | Borders, rules, hairlines |
| `acc` | `#c8a24a` | 3 | Accent (emphasis, highlights, dark-mode gold / light-mode blue) |
| `link` | `#7d9fc8` | 4 | Links and interactive focus cues |
| `activebg` | `#32323f` | 8 | Active / selected row background |
| `selection` | `#7d9fc8` | 4 | Text selection wash (often used with alpha) |
| `good` | `#7dba6f` | 2 | Success / low urgency / positive |
| `warn` | `#d4756b` | 1 | Warning / high urgency / error-adjacent |
| `urghigh` | `#d4756b` | 1 | Urgency: high |
| `urgmed` | `#c8a24a` | 3 | Urgency: medium |
| `urglow` | `#7dba6f` | 2 | Urgency: low |

**Derived (how adapters actually paint muted text / washes):**

- `mutedText` ≈ mix(`fg` → `bg`, 0.42) → `#87878f`
- `selection` wash often `#7d9fc855` (33% for inactive)
- `lineHighlight` often `#32323f66`

### Light iface

| Role | Hex | ANSI idx | Use |
|------|-----|---------:|-----|
| `bg` | `#f4f4f6` | 0 | Primary surface / canvas |
| `fg` | `#1a1a22` | 7 | Primary text / ink |
| `muted` | `#1a1a22` | 7 | Secondary text (often mixed with bg for lower contrast) |
| `panel` | `#ffffff` | 15 | Raised panel / chrome surface |
| `panel2` | `#ffffff` | 15 | Secondary panel |
| `line` | `#d8d8de` | 8 | Borders, rules, hairlines |
| `acc` | `#2f5f9a` | 4 | Accent (emphasis, highlights, dark-mode gold / light-mode blue) |
| `link` | `#2f5f9a` | 4 | Links and interactive focus cues |
| `activebg` | `#d8d8de` | 8 | Active / selected row background |
| `selection` | `#7d9fc8` | 12 | Text selection wash (often used with alpha) |
| `good` | `#2d7a3a` | 2 | Success / low urgency / positive |
| `warn` | `#c0392b` | 1 | Warning / high urgency / error-adjacent |
| `urghigh` | `#c0392b` | 1 | Urgency: high |
| `urgmed` | `#9a7200` | 3 | Urgency: medium |
| `urglow` | `#2d7a3a` | 2 | Urgency: low |

**Derived (how adapters actually paint muted text / washes):**

- `mutedText` ≈ mix(`fg` → `bg`, 0.45) → `#7c7c81`
- `selection` wash often `#7d9fc855` (33% for inactive)
- `lineHighlight` often `#d8d8de66`

## Content / stream slots

### Dark slots

| Slot | Hex | ANSI idx | Use |
|------|-----|---------:|-----|
| `mdhead` | `#c8a24a` | 3 | Markdown headings |
| `ctxhead` | `#d8d8e0` | 7 | Context block headers |
| `ctxbody` | `#d8d8e0` | 7 | Context body text |
| `cmthead` | `#d8d8e0` | 7 | Comment headers |
| `comment` | `#7d9fc8` | 4 | Comments / annotations |
| `agent` | `#d8d8e0` | 7 | Agent / curator stream text |
| `user` | `#7d9fc8` | 4 | User / human stream text |

### Light slots

| Slot | Hex | ANSI idx | Use |
|------|-----|---------:|-----|
| `mdhead` | `#2f5f9a` | 4 | Markdown headings |
| `ctxhead` | `#1a1a22` | 7 | Context block headers |
| `ctxbody` | `#1a1a22` | 7 | Context body text |
| `cmthead` | `#1a1a22` | 7 | Comment headers |
| `comment` | `#2f5f9a` | 4 | Comments / annotations |
| `agent` | `#1a1a22` | 7 | Agent / curator stream text |
| `user` | `#2f5f9a` | 4 | User / human stream text |

## VS Code chrome surfaces (projected)

Useful when matching editor/plugin chrome, not required for greenfield web/app design.

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

## Machine-readable (copy as JSON)

```json
{
  "id": "kettle",
  "label": "Kettle",
  "schema_version": 1,
  "modes": {
    "dark": {
      "ansi": {
        "black": "#16161e",
        "red": "#d4756b",
        "green": "#7dba6f",
        "yellow": "#c8a24a",
        "blue": "#7d9fc8",
        "magenta": "#9a76c2",
        "cyan": "#389bb4",
        "white": "#d8d8e0",
        "bright black": "#32323f",
        "bright red": "#e8928a",
        "bright green": "#94c98a",
        "bright yellow": "#d4b86a",
        "bright blue": "#9db4d8",
        "bright magenta": "#b094d2",
        "bright cyan": "#59b4cc",
        "bright white": "#ececf2"
      },
      "ansi_indexed": [
        "#16161e",
        "#d4756b",
        "#7dba6f",
        "#c8a24a",
        "#7d9fc8",
        "#9a76c2",
        "#389bb4",
        "#d8d8e0",
        "#32323f",
        "#e8928a",
        "#94c98a",
        "#d4b86a",
        "#9db4d8",
        "#b094d2",
        "#59b4cc",
        "#ececf2"
      ],
      "iface": {
        "bg": "#16161e",
        "fg": "#d8d8e0",
        "muted": "#d8d8e0",
        "panel": "#16161e",
        "panel2": "#16161e",
        "line": "#32323f",
        "acc": "#c8a24a",
        "link": "#7d9fc8",
        "activebg": "#32323f",
        "selection": "#7d9fc8",
        "good": "#7dba6f",
        "warn": "#d4756b",
        "urghigh": "#d4756b",
        "urgmed": "#c8a24a",
        "urglow": "#7dba6f"
      },
      "slots": {
        "mdhead": "#c8a24a",
        "ctxhead": "#d8d8e0",
        "ctxbody": "#d8d8e0",
        "cmthead": "#d8d8e0",
        "comment": "#7d9fc8",
        "agent": "#d8d8e0",
        "user": "#7d9fc8"
      },
      "derived": {
        "mutedText": "#87878f",
        "selectionWash": "#7d9fc855",
        "selectionInactive": "#7d9fc833",
        "lineHighlight": "#32323f66"
      },
      "vscode_chrome": {
        "editor.background": "#16161e",
        "editor.foreground": "#d8d8e0",
        "sideBar.background": "#101016",
        "activityBar.background": "#0d0d11",
        "panel.background": "#101016",
        "statusBar.background": "#0d0d11",
        "button.background": "#7d9fc8",
        "button.foreground": "#16161e",
        "focusBorder": "#7d9fc8",
        "textLink.foreground": "#9db4d8",
        "input.background": "#1e1e26",
        "input.border": "#32323f",
        "list.activeSelectionBackground": "#32323f",
        "list.hoverBackground": "#22222a",
        "editor.selectionBackground": "#7d9fc855"
      }
    },
    "light": {
      "ansi": {
        "black": "#f4f4f6",
        "red": "#c0392b",
        "green": "#2d7a3a",
        "yellow": "#9a7200",
        "blue": "#2f5f9a",
        "magenta": "#7a4a9a",
        "cyan": "#18788a",
        "white": "#1a1a22",
        "bright black": "#d8d8de",
        "bright red": "#d4756b",
        "bright green": "#7dba6f",
        "bright yellow": "#c8a24a",
        "bright blue": "#7d9fc8",
        "bright magenta": "#9a76c2",
        "bright cyan": "#389bb4",
        "bright white": "#ffffff"
      },
      "ansi_indexed": [
        "#f4f4f6",
        "#c0392b",
        "#2d7a3a",
        "#9a7200",
        "#2f5f9a",
        "#7a4a9a",
        "#18788a",
        "#1a1a22",
        "#d8d8de",
        "#d4756b",
        "#7dba6f",
        "#c8a24a",
        "#7d9fc8",
        "#9a76c2",
        "#389bb4",
        "#ffffff"
      ],
      "iface": {
        "bg": "#f4f4f6",
        "fg": "#1a1a22",
        "muted": "#1a1a22",
        "panel": "#ffffff",
        "panel2": "#ffffff",
        "line": "#d8d8de",
        "acc": "#2f5f9a",
        "link": "#2f5f9a",
        "activebg": "#d8d8de",
        "selection": "#7d9fc8",
        "good": "#2d7a3a",
        "warn": "#c0392b",
        "urghigh": "#c0392b",
        "urgmed": "#9a7200",
        "urglow": "#2d7a3a"
      },
      "slots": {
        "mdhead": "#2f5f9a",
        "ctxhead": "#1a1a22",
        "ctxbody": "#1a1a22",
        "cmthead": "#1a1a22",
        "comment": "#2f5f9a",
        "agent": "#1a1a22",
        "user": "#2f5f9a"
      },
      "derived": {
        "mutedText": "#7c7c81",
        "selectionWash": "#7d9fc855",
        "selectionInactive": "#7d9fc833",
        "lineHighlight": "#d8d8de66"
      },
      "vscode_chrome": {
        "editor.background": "#f4f4f6",
        "editor.foreground": "#1a1a22",
        "sideBar.background": "#eaeaee",
        "activityBar.background": "#e5e5e9",
        "panel.background": "#eaeaee",
        "statusBar.background": "#e5e5e9",
        "button.background": "#2f5f9a",
        "button.foreground": "#ffffff",
        "focusBorder": "#2f5f9a",
        "textLink.foreground": "#7d9fc8",
        "input.background": "#fafafb",
        "input.border": "#d8d8de",
        "list.activeSelectionBackground": "#d8d8de",
        "list.hoverBackground": "#ededf0",
        "editor.selectionBackground": "#7d9fc855"
      }
    }
  }
}
```

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
  --kettle-muted: #d8d8e0;
  --kettle-panel: #16161e;
  --kettle-panel2: #16161e;
  --kettle-line: #32323f;
  --kettle-acc: #c8a24a;
  --kettle-link: #7d9fc8;
  --kettle-activebg: #32323f;
  --kettle-selection: #7d9fc8;
  --kettle-good: #7dba6f;
  --kettle-warn: #d4756b;
  --kettle-urghigh: #d4756b;
  --kettle-urgmed: #c8a24a;
  --kettle-urglow: #7dba6f;
  --kettle-muted-text: #87878f;
}
[data-theme="light"] {
  --kettle-bg: #f4f4f6;
  --kettle-fg: #1a1a22;
  --kettle-muted: #1a1a22;
  --kettle-panel: #ffffff;
  --kettle-panel2: #ffffff;
  --kettle-line: #d8d8de;
  --kettle-acc: #2f5f9a;
  --kettle-link: #2f5f9a;
  --kettle-activebg: #d8d8de;
  --kettle-selection: #7d9fc8;
  --kettle-good: #2d7a3a;
  --kettle-warn: #c0392b;
  --kettle-urghigh: #c0392b;
  --kettle-urgmed: #9a7200;
  --kettle-urglow: #2d7a3a;
  --kettle-muted-text: #7c7c81;
}
```
