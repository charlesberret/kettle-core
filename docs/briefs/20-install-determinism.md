---
id: 20
title: One setsweep — install determinism
repo: setsweep-core
touches: [INSTALL.md, pyproject.toml, docs (doctor spec in brief 18)]
risk: normal
depends-on: []
status: open
---

## Context

From the 2026-07-21 plugin-sitting handoff: any CLI subcommand died with
`ModuleNotFoundError: No module named 'egress'`. Diagnosed as a stale editable-install
finder MAPPING that listed `cli`/`server`/… but omitted `egress` and `sweepkit` after those
modules were added to `py-modules`. Reinstalling editable fixed it.

That fixed the symptom. Verification on 2026-07-21 found the underlying condition —
**four `setsweep` executables resolve on PATH**:

| Path | Kind |
|---|---|
| `/opt/homebrew/bin/setsweep` | console script — **wins** |
| `~/.local/bin/setsweep` | console script |
| `~/cloud/sync/code/bin/setsweep` | shell shim |
| `~/Seafile/Code/bin/setsweep` | shell shim — **retired pre-migration path** |

And `~/.setsweep-venv/bin/setsweep` — the install the handoff calls canonical — is not on
PATH at all. So "reinstall editable" is ambiguous by construction: it fixes whichever
install you happened to target, while another may still shadow it. This is the same shape
as brief 12's duplicate watcher, and the same shape as the anaconda-on-PATH story: an
accident of resolution order hardened into behavior.

## Task

1. **Pick the canonical install and say so.** Recommendation: the dedicated venv
   (`~/.setsweep-venv`) with exactly one shim on PATH pointing at it. Record the decision
   in `INSTALL.md`.
2. **Retire the strays**: the `~/Seafile/Code/bin` shim (dead path post-migration) and
   whichever of homebrew / `~/.local/bin` is not canonical. Removing a binary from a
   patron's PATH is a *patron action* — propose the list, do not delete unasked.
3. **Document the reinstall rule**: adding a module to `pyproject.toml` `py-modules`
   requires reinstalling editable, or the finder MAPPING goes stale and the CLI breaks at
   import. Put it beside the `py-modules` list itself, not only in `INSTALL.md`, so the
   person editing that list sees it.
4. **Make it self-detecting** (folds into brief 18's `setsweep doctor`): report which
   `setsweep` resolves and whether it is the canonical one; verify every module in
   `py-modules` is importable and present in the finder MAPPING; flag extra executables on
   PATH.

## Constraints

- `INSTALL.md` currently carries uncommitted path-migration edits — land those before
  editing it, or the two changes entangle.
- CLI stays stdlib-only; no new dependency for any of this.
- Do not delete anything from the patron's PATH without an explicit go-ahead.

## Done when

- `which -a setsweep` returns one path, or a documented intentional set with the canonical
  one first.
- Adding a throwaway module to `py-modules` without reinstalling is caught by doctor (or a
  smoke) rather than by a user hitting `ModuleNotFoundError`.
- `INSTALL.md` names the canonical install and the reinstall rule.

## Verify

`which -a setsweep`; `setsweep projects` and `setsweep queue <project>` against the
canonical install; `python3 -c "import cli, server, egress, sweepkit, curator, kits,
runtime, lineage"`.

## Afterwards

`status: done`; brief 18 inherits the doctor checks; note the retirement in the fleet
ops-log if a shim is removed.
