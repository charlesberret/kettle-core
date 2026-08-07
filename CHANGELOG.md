# Changelog

Kettle Core follows semantic versioning for its Python distribution. The API
and Desk schema have their own integer contract versions.

## Unreleased

### Added

- `kettle migrate`: dry-run-first migration of `.setsweep/` desks → `.kettle/` (and the
  legacy Setsweep user registry when clearly applicable). Default is dry-run; pass
  `--apply` to write. Refuses split desks (both directories present) so a project never
  keeps two writable desks. See `INSTALL.md` § Migrating from Setsweep.
- `kettle doctor` expands beyond PATH / package-module mapping: Python + package install
  mode, active curator CLI resolve (`curator.provider_readiness`), registry readability,
  desk integrity (`queue.json` parse + desk dirs), legacy `.setsweep/` migration hints
  (pointing at `kettle migrate`), runtime discovery (`~/.cache/kettle/server.json`), and
  a localhost `/api/ping` when discovery lists a non-conventional port (never binds or
  probes `4242`).
- CI `package-install` job: build wheel, audit bundled `static/` + `kits/` package data,
  clean-venv wheel install smoke, ephemeral-port server smoke, and pipx-style isolated
  install smoke on Python 3.11 and 3.14.
- `kettle.__version__` (via `importlib.metadata`) surfaced in `/api/ping` and
  `kettle --help`.

### Changed

- Restructured the flat modules into the `kettle/` package; `static/`, `kits/`, and
  `projects.example.json` ship as package data so a wheel can serve the web UI.
  `APPDIR` resolves through `importlib.resources.files()` (PyInstaller `_MEIPASS` kept).
  Build floor pinned to `setuptools>=77`.
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
- Localhost HTTP hardening: per-boot `X-Kettle-Token` (discovery file mode 0600),
  Host/Origin rejection, and normalized `{error, code}` envelopes (`str(e)` only).

## 0.2.0

This was the final pre-Kettle package version inherited from the Setsweep
development line. Git history preserves the detailed implementation record.
