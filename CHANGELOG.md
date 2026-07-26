# Changelog

Kettle Core follows semantic versioning for its Python distribution. The API
and Desk schema have their own integer contract versions.

## Unreleased

### Changed

- Renamed the product and canonical commands from Setsweep to Kettle.
- New projects use `.kettle/` and the Kettle user registry.
- Public documentation and repository routing now describe the Kettle family.
- CLI `open` / `edit` use a built-in syntax-colored TUI editor by default
  (theme packs under `static/themes/`; marquee default `kettle`). Pass
  `--external` for `$EDITOR`. Search with `^F` / `^G` / `^D`; large files use
  plain mode.
- Web/desktop load theme packs from `GET /api/themes` and can install custom
  packs via Appearance or `POST /api/themes/install`.
- Sitting source view uses shared syntax role classes aligned with the CLI.

### Compatibility

- Existing `.setsweep/` Desks are used in place when no `.kettle/` Desk exists.
- Existing Setsweep user registries remain discoverable without creating split
  state.
- `setsweep` and `setsweep-watch` remain console-script aliases that call the
  same `kettle_main` / `kettle_watch` entrypoints (no separate `setsweep_*`
  modules remain in the tree).
- Kettle adapters may attach to a legacy core identity during the migration
  window.
- The API and Desk-schema contract integers remain unchanged at `0`.

### Security

- Registered-root file fencing, loopback-only serving, deterministic founding
  survey, and staged egress remain release invariants.

## 0.2.0

This was the final pre-Kettle package version inherited from the Setsweep
development line. Git history preserves the detailed implementation record.
