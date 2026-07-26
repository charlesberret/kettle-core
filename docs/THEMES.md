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
- `nord.json`, `solarized.json`, `tokyo-night.json`, `gruvbox.json`, `material.json`, `one-dark.json`, `classic.json`

Shortcut for brand-only consumers: `static/kettle-palette.json` (mirrors marquee).

## Custom themes

Drop a pack JSON in the user themes directory:

| Platform | Path |
|----------|------|
| macOS | `~/Library/Application Support/Kettle/themes/` |
| Linux | `${XDG_CONFIG_HOME:-~/.config}/kettle/themes/` |
| override | `$KETTLE_THEMES_DIR` |

Filename stem = theme id (`my-desk.json` → `my-desk`). Schema:
[`static/themes/README.md`](../static/themes/README.md).

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

## Web appearance vs pack files

The sitting UI still embeds builtins in `themes.js` for zero-latency load. Keep
`themes.js` kettle hexes aligned with `static/themes/kettle.json` /
`kettle-palette.json` (`test_palette.py`). Export of all builtins to JSON is
the shared catalog for non-browser viewports.
