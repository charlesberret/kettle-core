# Repository ownership and compatibility

Kettle's repositories keep separate histories because they have different
release units. Coherence comes from one core authority, explicit versioned
contracts, and cross-family validation. The canonical family map lives in the
product home's
[`architecture explanation`](https://github.com/charlesberret/kettle/blob/main/docs/explanation/architecture.md);
this document covers implementation compatibility.

## Ownership

| Repository | Owns | Does not own |
|---|---|---|
| `kettle` | Public product story, family navigation, launch-facing roadmap | Runtime or adapter code |
| `kettle-core` | Product semantics, `.kettle/` format and migrations, localhost API, curator runtime, first-class CLI, kits, reference web UI | Electron lifecycle or editor-host behavior |
| `kettle-vscode` | VS Code/Cursor activation, commands, panels, packaging, and a generated core-copy snapshot | Desk state, migrations, or core decisions |
| `kettle-desktop` | Electron lifecycle, sidecar bundling, signing, notarization, updates, and native menus | A separate frontend or product rules |

Dependency direction is one-way:

```text
kettle-vscode ────┐
                   ├──> kettle-core API + desk format
kettle-desktop ───┘

kettle-core never imports adapter repositories.
```

Future adapters should exist only when they have a real host implementation and
release path. The CLI remains part of `kettle-core`.

## Sources of truth

| Fact | Authority |
|---|---|
| Public product story and family map | `kettle` |
| Architecture and product semantics | `kettle-core/ARCHITECTURE.md` |
| HTTP and NDJSON behavior | `kettle-core/API.md` plus contract tests |
| Core, API, and desk-schema versions | `kettle-core/kettle/kettle_contract.py` |
| Supported core contracts | Each adapter's `kettle-compatibility.json` |
| Host implementation and release notes | The relevant adapter repository |

Generated core-owned copy may be committed in an adapter so ordinary builds are
independent. Regeneration is explicit and drift-checked. The desktop release
build consumes one resolved core checkout and stamps its exact provenance.

## Compatibility rules

`GET /api/ping` publishes:

- `app`: `kettle`
- `version`: the core distribution version
- `api_version`: the HTTP and NDJSON contract integer
- `desk_schema_version`: the durable Desk contract integer

During the Setsweep transition, consumers may accept `app: "setsweep"` and
existing `.setsweep/` Desks. Branding alone does not advance either contract
integer. A known unsupported contract is a user-facing error, never a guess.

Versions advance independently. Core, desktop, and VS Code do not need matching
package versions.

## Cross-repository changes

1. Land the core change backward-compatibly with contract tests.
2. Advance a contract integer only for an incompatible public change.
3. Update each affected adapter against that exact contract.
4. Run the family checker and each repository's native suite.
5. Remove deprecated behavior only after supported releases have migrated.

## Local family check

With sibling checkouts under one parent directory:

```sh
cd kettle-core
python3 tools/check_family.py
python3 tools/check_family.py --run-tests
python3 tools/check_family.py --require-clean
```

The checker reports branch, commit, dirty state, release versions, and declared
contract compatibility. `--require-clean` is a release gate. It does not replace
desktop sidecar provenance checks or packaged-install smoke tests.
