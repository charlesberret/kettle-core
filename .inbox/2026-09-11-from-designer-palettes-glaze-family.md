# Kettle marquee + glaze family promoted — and one role the desk is missing

- **From:** designer session, `~/cloud/sync/design/palettes` (avicenna, Claude)
- **Kind:** notice + proposal
- **Status:** open — promotion landed in the working tree (uncommitted, on top of `builder/kettle-initiation-p1-p5`); the proposal needs builder's hands

## What landed (generated — do not hand-edit)

`kettle/static/themes/kettle.json`, six `kettle-<pack>.json`, `index.json`,
`kettle-palette.json`, and the marked block in `themes.js` are now written by
`~/cloud/sync/design/palettes/scripts/kettle-promote.py --apply`. All 44
palette / catalog / CLI tests pass. The same run regenerated kettle-vscode's
14 colour themes and agent-deck's house entries. None of the files touched
are in the builder's dirty set; `git add` them by path.

Two schema additions, both optional and ignored by the loader: a per-mode
`resolved` block (shade steps + muted/faint hex) and, on packs, a `glaze`
block with a top-level `voice`. Documented in `docs/THEMES.md` and
`static/themes/README.md`.

## The proposal: a chrome-only `glaze` role

Three of the six packs — Cerise, Nectar, Artichaut — are **body-voiced**: their
hue collides with a signal (warn / gold / good), so the palette rule is that
the enamel is never text. In the desk every accent-ish variable is text
somewhere (`--acc` is `color:` seven times), so those three packs currently
render identical to the marquee. The three cool packs put their accent in
`acc` and are fully expressed.

Ask: add `glaze` to `IFACE_KEYS` / `IFACE_DARK` / `IFACE_LIGHT` (default
`--ansi-3` dark, `--ansi-4` light, i.e. today's accent), expose it as
`--glaze`, and use it for **chrome only**: `accent-color`, the focus ring,
`--row-active-bar`'s replacement (a leading bead on the selected queue row —
not a side stripe), the cursor in the CLI editor. Keep every `color:` on
`--acc`. The pack files already carry the hex (`dark.glaze.hex`); the
generator will switch to emitting an ANSI slot + index the day the role
exists. `index.html` is in the builder's dirty set, which is why this is a
memo and not a patch.

Design rule for the row, from the palette: *the enamel fills a field only
where the field is transient (selection) or small (cursor, bead, dot); a
persistent field is a shade.* Chronology: `design/palettes/sources/kettle/DARK-PASS.md`.
