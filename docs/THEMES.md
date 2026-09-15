# Themes and syntax coloring

Kettle ships a **marquee theme** (`kettle`) plus other bundled packs, and loads
**custom packs** from a user directory. The same host-neutral packs color:

| Surface | How themes apply |
|---------|------------------|
| Browser / desktop sitting | `static/themes.js` builtins + Appearance UI (saved palettes in settings) |
| Built-in CLI editor | `theme_catalog` + curses colors from the pack |
| VS Code / Cursor | Projection of the marquee palette into workbench token themes (`kettle-vscode`) |

## Bundled packs

Under `static/themes/`:

- `index.json` — default id (`kettle`) and catalog
- `kettle.json` — **marquee** product theme
- `kettle-cerise.json`, `kettle-nectar.json`, `kettle-artichaut.json`,
  `kettle-marseille.json`, `kettle-cobalt.json`, `kettle-graphite.json` — the
  **glaze family**: the marquee skeleton with one enamel colour per pack
- `nord.json`, `solarized.json`, `tokyo-night.json`, `gruvbox.json`, `material.json`, `classic.json`

Shortcut for brand-only consumers: `static/kettle-palette.json` (mirrors marquee).

**The marquee and the family are generated, not hand-edited.** Source of truth
is `~/cloud/sync/design/palettes` (`library/kettle.json`, `library/kettle-glazes.json`);
`scripts/kettle-promote.py --apply` there rewrites `kettle.json`, the six pack
files, `index.json`, `kettle-palette.json` and the marked block in `themes.js`
in lockstep, then runs kettle-vscode's `sync-palette`. Edit the palette, not
these files. The desk's surfaces are shades of one body: `panel`/`activebg`
index the ground (dark) or highlight (light) at an `ifaceOpacity` that lands
on the measured shade step; the resolved hexes ride along in a `resolved`
block for consumers that take hex. Glaze packs carry a `glaze` block
(enamel, its text polarity, and a fixed-text `wash`) and a `voice`:
*text* packs put the enamel in `acc`; *body* packs (warm hues that collide
with a signal) keep the marquee accent and need a chrome-only role the desk
does not yet have — see `.inbox/2026-09-11-from-designer-palettes-glaze-family.md`.

## Custom themes

Drop a pack JSON in the user themes directory:

| Platform | Path |
|----------|------|
| macOS | `~/Library/Application Support/Kettle/themes/` |
| Linux | `${XDG_CONFIG_HOME:-~/.config}/kettle/themes/` |
| override | `$KETTLE_THEMES_DIR` |

Filename stem = theme id (`my-desk.json` → `my-desk`). Schema:
[`static/themes/README.md`](../kettle/static/themes/README.md).

List packs:

```sh
kettle themes
```

## CLI editor

```sh
kettle open  <project> <entry-id>     # built-in TUI (default)
kettle edit  <project> <entry-id>     # same
kettle open  <project> <id> --theme nord
kettle open  <project> <id> --external   # $EDITOR escape hatch
```

Keys: `^S` save · `^Q` quit · `^W` open in `$EDITOR` · arrows / home / end.

Syntax roles (comment, string, keyword, …) map through the active pack’s ANSI
palette via `theme_catalog.syntax_color_table`.

## Desktop and browser

Desktop loads the core web UI. On boot the sitting fetches:

```http
GET /api/themes?full=1
```

and merges packs into the Appearance → theme menu (marquee **Kettle** first,
custom packs tagged). Saved color snapshots in `settings.json` still work; file
packs in the user themes directory are the portable path shared with the CLI.

| Route | Purpose |
|-------|---------|
| `GET /api/themes` | Catalog: default id, user_dir, theme metadata |
| `GET /api/themes?full=1` | Same + `packs` map (web-shaped dark/light presets) |
| `GET /api/themes/<id>` | One web-shaped pack |
| `POST /api/themes/install` | Write a pack JSON into the user themes directory |

Appearance → **Install Theme Pack** pastes JSON and calls install, then refreshes
the menu (and selects the new id).

## Web appearance vs pack files

The sitting UI still embeds builtins in `themes.js` for zero-latency load. Keep
`themes.js` kettle hexes aligned with `static/themes/kettle.json` /
`kettle-palette.json` (`tests/test_palette.py`). Export of all builtins to JSON is
the shared catalog for non-browser viewports.
