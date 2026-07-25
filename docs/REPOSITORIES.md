# Setsweep repository boundaries

Setsweep is one product in three repositories. Their histories stay separate
because the release units and host concerns are different. Coherence comes from
one authoritative core and tested contracts, not copied product logic.

## Ownership

| Repository | Owns | Does not own |
|---|---|---|
| `setsweep-core` | Product semantics; durable `.setsweep/` format and migrations; localhost API; curator runtime; CLI; reference web UI; product roadmap and architecture | Electron lifecycle or editor-host behavior |
| `setsweep-desktop` | Electron lifecycle; sidecar bundling; signing, notarization, updates, and native menus | Desk state, product rules, or a fork of the web UI |
| `setsweep-plugin` | Host adapters; shared host-neutral TypeScript client; editor commands, panels, and keybindings | Desk state, migrations, or duplicated core decisions |

Dependency direction is one-way:

```text
setsweep-desktop ──┐
                   ├──> setsweep-core API + desk format
setsweep-plugin ───┘

setsweep-core never imports either viewport repository.
```

Generated snapshots of core-owned material may be committed in a viewport so its
source compiles independently. Plugin snapshot regeneration is an explicit
maintainer action; an ordinary plugin compile/package must not require a sibling
checkout. Desktop is the deliberate exception: its release build consumes one
resolved core checkout, rejects unverified input, and stamps the exact bundled
core provenance.

## Sources of truth

| Fact | Authority |
|---|---|
| Product direction and sequencing | `setsweep-core/ROADMAP.md` |
| Architecture and invariants | `setsweep-core/ARCHITECTURE.md` |
| HTTP and NDJSON behavior | `setsweep-core/API.md` + core contract tests |
| Current API and desk-schema versions | `setsweep-core/setsweep_contract.py` |
| A viewport's supported contract versions | That viewport's compatibility declaration |
| Host implementation and release notes | The host repository |

Repo READMEs summarize and link. They do not restate the master roadmap.

## Compatibility

`GET /api/ping` publishes:

- `version`: core package version, single-sourced from `pyproject.toml`
- `api_version`: integer HTTP/NDJSON contract version
- `desk_schema_version`: integer durable-desk format version

Every viewport declares the integer versions it supports. A mismatch is a
user-facing compatibility error, not an opportunity to guess. Desktop bundles
one exact core build and records its version, commit, contract versions, and
dirty state in `resources/version.json`.

Versions advance independently. Setsweep does not force core, desktop, and
plugins to share a release number.

## Cross-repo change procedure

For work touching more than one repository:

1. Give the initiative one stable issue or work-package id.
2. Link one implementation issue in each affected repository.
3. Land the core change backward-compatibly and add contract tests.
4. Release or otherwise pin the core revision.
5. Update each viewport against that exact contract.
6. Remove deprecated behavior only after supported viewports have migrated.

Matching branch names can help navigation, but they are not the coordination
record.

## Local family check

With sibling checkouts under one directory, run from `setsweep-core`:

```sh
python3 tools/check_family.py
python3 tools/check_family.py --require-clean
python3 tools/check_family.py --run-tests
```

The first form is read-only. It reports each repo's resolved path, branch,
commit, dirty state, release version, and viewport contract compatibility.
`--require-clean` is a release precondition. `--run-tests` is a serial
cross-repo convenience check; it is not a substitute for the desktop's
dirty-core build gate, bundled-sidecar smoke, or packaged-install verification.
It never starts the live core or binds port 4242.
