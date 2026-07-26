# Core release checklist

The family-wide release definition lives in the
[Kettle product home](https://github.com/charlesberret/kettle/blob/main/docs/reference/release-gates.md).
This checklist covers the core artifact.

## Source release

- [ ] `python3 -m pytest` passes serially.
- [ ] `python3 tools/check_family.py --require-clean` passes with supported
  adapter checkouts.
- [ ] `git diff --check` is clean.
- [ ] `kettle_contract.py` matches the documented API and Desk behavior.
- [ ] The changelog names compatibility, migration, and security changes.
- [ ] Public documentation contains no private topology or maintainer-only
  operational state.

## Python package

- [ ] Build sdist and wheel from a clean tagged tree.
- [ ] Audit package contents for `static/`, kits, notices, and accidental local
  files.
- [ ] Install the wheel in a clean virtual environment without the source tree
  on `sys.path`.
- [ ] Run `kettle doctor`, `kettle --help`, and a loopback ping.
- [ ] Verify both canonical commands and any promised legacy aliases.
- [ ] Test the oldest supported Python and a current Python on macOS and Linux.

## Manual behavior

- [ ] Register a clean project.
- [ ] Complete founding and inspect the generated Desk.
- [ ] Review, comment, approve, and sweep one entry.
- [ ] Confirm approval alone did not apply or transmit work.
- [ ] Confirm legacy registry and `.setsweep/` fallback do not create split
  writable state.
- [ ] Inspect staged egress and verify no outward transmission occurred.

Kettle has no phone-home analytics. Release evidence is local test output,
package contents, and an explicit dogfood record.
