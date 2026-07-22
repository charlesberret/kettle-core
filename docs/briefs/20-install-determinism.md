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

From the 2026-07-21 plugin-sitting handoff: any CLI subcommand died with `ModuleNotFoundError: No module named 'egress'`. The diagnosis was a stale editable-install finder MAPPING that listed `cli`/`server`/… but omitted `egress` and `sweepkit` after those modules were added to `py-modules`. Reinstalling editable fixed it.

That fixed the symptom. Verification on 2026-07-21 found the underlying condition — four `setsweep` executables resolve on PATH:

| Path | Kind |
|---|---|
| `/opt/homebrew/bin/setsweep` | console script — **currently wins** |
| `~/.local/bin/setsweep` | console script |
| `~/cloud/sync/code/bin/setsweep` | shell shim |
| `~/Seafile/Code/bin/setsweep` | shell shim — **retired pre-migration path** |

And `~/.setsweep-venv/bin/setsweep` — the canonical install (see the ruling below) — is not on PATH at all. So "reinstall editable" is ambiguous by construction: it fixes whichever install you happen to target, while another may still shadow it. This is the same shape as brief 12's duplicate watcher, and the same shape as the anaconda-on-PATH story in the fleet charter: an accident of resolution order hardened into behavior.

## Patron ruling (2026-07-21)

`~/.setsweep-venv` is the **canonical** install. Exactly one shim on PATH should point at it. The agent proposes a retirement list for the strays but **deletes nothing from PATH itself** — removing a binary from the patron's PATH is a patron action.

## Task

Document the canonical install in `INSTALL.md`: `~/.setsweep-venv`, with a single PATH shim pointing at `~/.setsweep-venv/bin/setsweep` and the editable install rooted at the canonical repo path (`~/cloud/git-projects/setsweep-core`, reachable via the `~/Repos` symlink).

Propose — do not execute — the retirement list. The `~/Seafile/Code/bin/setsweep` shim is a dead post-migration path and is the clear first cut; the homebrew and `~/.local/bin` console scripts shadow the venv and should go once the shim is in place. Present this to the patron as a checklist of commands they run, not something the agent runs.

Document the reinstall rule where it will actually be seen: adding a module to `pyproject.toml` `py-modules` requires reinstalling editable, or the finder MAPPING goes stale and the CLI breaks at import. Put a one-line comment beside the `py-modules` list itself, not only in `INSTALL.md`.

Make it self-detecting, folding into brief 18's `setsweep doctor`: report which `setsweep` resolves and whether it is the canonical one; verify every module in `py-modules` is importable and present in the finder MAPPING; flag extra executables on PATH.

## Constraints

`INSTALL.md` currently carries uncommitted path-migration edits (the `~/Seafile` → `~/cloud/sync` sweep). Those must land before this brief edits `INSTALL.md`, or the two changes entangle — treat that commit as this brief's true prerequisite even though the frontmatter lists no dep.

The CLI stays stdlib-only; nothing here adds a dependency. Do not delete anything from the patron's PATH without an explicit go-ahead.

## Done when

`which -a setsweep` returns one path, or a documented intentional set with the canonical one first. Adding a throwaway module to `py-modules` without reinstalling is caught by doctor (or a smoke) rather than by a user hitting `ModuleNotFoundError`. `INSTALL.md` names `~/.setsweep-venv` as canonical and states the reinstall rule.

## Verify

`which -a setsweep`; `setsweep projects` and `setsweep queue <project>` against the canonical install; `python3 -c "import cli, server, egress, sweepkit, curator, kits, runtime, lineage"`.

## Afterwards

Set `status: done`; brief 18 inherits the doctor checks; note any shim retirement the patron approves in the fleet ops-log.
