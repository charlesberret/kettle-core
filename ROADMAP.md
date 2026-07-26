# Kettle Core roadmap

Kettle is a local-first review instrument for human-agent work. Agents prepare
and propagate; the user reads and rules. The roadmap protects that division of
labor while making the instrument easier to install, trust, and extend.

The public product and repository map lives at
[charlesberret/kettle](https://github.com/charlesberret/kettle). This document
covers the core only.

## Current baseline

- Python 3.11+ standard-library runtime
- First-class CLI and reference browser desk
- Localhost API with explicit core, API, and desk-schema identity
- Durable `.kettle/` desks with non-destructive `.setsweep/` fallback
- Curator adapters for Claude, Codex, Gemini, and Grok CLIs
- Project-root file fence, deterministic founding survey, lineage, egress, and
  mechanical close helpers
- VS Code/Cursor and macOS consumers validated through compatibility manifests

Kettle remains pre-1.0. The desk format and API are versioned, but the integer
contracts are still at `0`.

## Now: trustworthy public alpha

### Installation

- Restructure the flat modules into a package with bundled `static/` and `kits/`
  resources.
- Verify wheel and `pipx` installation in CI while keeping editable installs
  excellent for contributors.
- Expand `kettle doctor` to cover provider availability, registry selection,
  desk integrity, runtime discovery, and legacy migration state.

### Security

- Add explicit Host and Origin validation to the localhost HTTP surface.
- Design a per-boot authentication token shared through the local discovery
  record.
- Replace any provider permission that is only prompt-fenced with an enforceable
  process or filesystem boundary where the host permits it.
- Keep remote and multi-user serving out of scope until there is a separate
  threat model.

### Migration

- Add an explicit, dry-run-first `kettle migrate` command for `.setsweep/` desks
  and legacy user registries.
- Never maintain two writable desks for one project.
- Publish a deprecation window before removing the old command aliases or
  process identity.

## Now: themes and the CLI sitting editor

- Marquee **Kettle** theme pack plus bundled alternatives under `static/themes/`.
- User-installable theme packs (shared by CLI and eventually web/desktop loaders).
- Built-in **CLI TUI editor** with stdlib syntax coloring (`kettle open` / `edit`).
- Deepen language tokenizers and wire web `renderBack` to the same role map.
- Desktop continues to ship the core sitting (bundled themes in Appearance);
  load file-based custom packs into the web UI as a follow-on.

## Next: reliable release surfaces

- Stabilize the API and desk schemas at version `1` only after their contracts
  are documented and exercised by real adapters.
- Finish packaged VS Code/Cursor and desktop smoke tests against exact core
  provenance.
- Keep the changelog and release checklist current with compatibility,
  security, third-party notices, source archives, and clean-tree gates.
- Validate a complete stranger path: install, found a real desk, review an
  entry, and close a sitting without maintainer help.

## Later: evidence-led expansion

- Improve watch support with native filesystem notifications.
- Extract a shared client only when a second TypeScript adapter needs it.
- Build an Obsidian adapter when a concrete writing or knowledge workflow is
  ready to dogfood.
- Add a narrow MCP bridge only for model-host tools over the same desk. It
  should not replace the CLI or full sitting.
- Consider remote or multi-user operation only after authentication, tenant
  isolation, desk ownership, and session ownership are designed together.

## Permanent product invariants

1. The desk is ordinary, inspectable files.
2. Viewports depend on the core; the core never imports viewports.
3. Approve is a bookmark, not an outward action.
4. Sweep applies rulings and restocks under explicit policy.
5. Egress stages; Kettle does not silently transmit.
6. Unattributed edits remain unattributed.
7. Provider credentials stay with the provider CLI.
8. Background actors expose health instead of failing silently.
9. Breaking API or desk changes advance a contract version and ship with a
   migration story.

Detailed pre-rename engineering briefs remain under
[`docs/briefs/`](./docs/briefs/) as historical design evidence. Their status
frontmatter is not the current public roadmap.
