# Bundled Kettle themes

Host-neutral **theme packs** shared by the reference web sitting, desktop shell,
and the built-in CLI editor.

| File | Role |
|------|------|
| `index.json` | Catalog: default id (`kettle`) + bundled theme ids |
| `kettle.json` | **Marquee** product theme (shipped as default) — *generated* |
| `kettle-<pack>.json` | Glaze family (cerise, nectar, artichaut, marseille, cobalt, graphite) — *generated* |
| `*.json` | Other bundled packs (Nord, Solarized, …) |

The marquee and the glaze family are generated. The palette library and its
promotion script live outside this repository (`docs/THEMES.md`). Edit a pack
here only when you mean to bypass that generator.

Custom user packs load from the user themes directory (see
[`docs/THEMES.md`](../../docs/THEMES.md)), not from this folder.

## Pack schema (`schema_version: 1`)

```json
{
  "schema_version": 1,
  "id": "kettle",
  "label": "Kettle",
  "marquee": true,
  "dark": {
    "ansi": ["#……", "… 16 hex colors …"],
    "iface": { "bg": 0, "fg": 7, "acc": 3, "link": 4, "…": 0 },
    "slots": { "mdhead": 3, "comment": 4, "…": 0 }
  },
  "light": { "ansi": [], "iface": {}, "slots": {} }
}
```

- **ansi** — indices 0–15 (standard terminal palette order).
- **iface / slots** — role → ANSI index (not raw hex), so packs stay portable.
- **marquee** — only the product default should set `true`.

Optional per-mode keys (the loader ignores what it does not know):

- **ifaceOpacity / slotOpacity** — solid % per role, overriding the sitting defaults.
- **resolved** — hex for `well`, `ground`, `panel`, `active`, `line`, `highlight`,
  `muted`, `faint`: the shade steps and text tones the index map cannot carry,
  for consumers that take hex (kettle-vscode). Not read by the desk.
- **glaze** — `{hex, on_glaze, wash, accent}` on glaze packs, with a top-level
  **voice** (`text` | `body`): the enamel, the text polarity it can carry,
  and the wash a fixed-text selection falls back to.

The shortcut file `../kettle-palette.json` mirrors the marquee pack for
adapters that only need the brand palette (e.g. VS Code theme projection).
