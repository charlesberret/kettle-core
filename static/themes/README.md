# Bundled Kettle themes

Host-neutral **theme packs** shared by the reference web sitting, desktop shell,
and the built-in CLI editor.

| File | Role |
|------|------|
| `index.json` | Catalog: default id (`kettle`) + bundled theme ids |
| `kettle.json` | **Marquee** product theme (shipped as default) |
| `*.json` | Other bundled packs (Nord, Solarized, …) |

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

The shortcut file `../kettle-palette.json` mirrors the marquee pack for
adapters that only need the brand palette (e.g. VS Code theme projection).
