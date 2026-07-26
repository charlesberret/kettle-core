---
id: 20
title: One kettle — install determinism
repo: kettle-core
touches: [INSTALL.md, pyproject.toml, docs (doctor spec in brief 18)]
risk: normal
depends-on: []
status: done
---

## Context

From the 2026-07-21 plugin-sitting handoff: any CLI subcommand died with `ModuleNotFoundError: No module named 'egress'`. The diagnosis was a stale editable-install finder MAPPING that listed `cli`/`server`/… but omitted `egress` and `sweepkit` after those modules were added to `py-modules`. Reinstalling editable fixed it.

That fixed the symptom. Verification on 2026-07-21 found the underlying condition — four `kettle` executables resolve on PATH:

| Path | Kind |
|---|---|
| package-manager bin | console script that currently wins |
| user-local bin | console script |
| current sync root | shell shim |
| retired sync root | stale shell shim |

And `~/.kettle-venv/bin/kettle` — the canonical install (see the ruling below) — is not on PATH at all. So "reinstall editable" is ambiguous by construction: it fixes whichever install you happen to target, while another may still shadow it. This is the same shape as brief 12's duplicate watcher, and the same shape as the anaconda-on-PATH story in the fleet charter: an accident of resolution order hardened into behavior.

## User ruling (2026-07-21)

`~/.kettle-venv` is the **canonical** install. Exactly one shim on PATH should point at it. The agent proposes a retirement list for the strays but **deletes nothing from PATH itself** — removing a binary from the user's PATH is a user action.

## Task

Document the canonical install in `INSTALL.md`: `~/.kettle-venv`, with a single
PATH shim pointing at `~/.kettle-venv/bin/kettle` and the editable install
rooted at the chosen checkout.

Propose, but do not execute, the retirement list. Stale sync-root and
package-manager scripts should go only after the canonical shim is in place.
Present this as a checklist of commands the user runs.

Document the reinstall rule where it will actually be seen: adding a module to `pyproject.toml` `py-modules` requires reinstalling editable, or the finder MAPPING goes stale and the CLI breaks at import. Put a one-line comment beside the `py-modules` list itself, not only in `INSTALL.md`.

Make it self-detecting, folding into brief 18's `kettle doctor`: report which `kettle` resolves and whether it is the canonical one; verify every module in `py-modules` is importable and present in the finder MAPPING; flag extra executables on PATH.

## Constraints

Path-migration edits must land before this brief edits `INSTALL.md`, or the two
changes entangle.

The CLI stays stdlib-only; nothing here adds a dependency. Do not delete anything from the user's PATH without an explicit go-ahead.

## Done when

`which -a kettle` returns one path, or a documented intentional set with the canonical one first. Adding a throwaway module to `py-modules` without reinstalling is caught by doctor (or a smoke) rather than by a user hitting `ModuleNotFoundError`. `INSTALL.md` names `~/.kettle-venv` as canonical and states the reinstall rule.

## Verify

`which -a kettle`; `kettle projects` and `kettle queue <project>` against the canonical install; `python3 -c "import cli, server, egress, sweepkit, curator, kits, runtime, lineage"`.

## Afterwards

Set `status: done`; brief 18 inherits the doctor checks; note any shim retirement the user approves in the fleet ops-log.
