# Counsel — repo-topology seat (architect-codex)

Speaking only from the topology lens.

## Verified inventory

| Tree | Current kind | Evidence this session | Load-bearing role |
|---|---|---|---|
| `kettle` | Git repo, 13 commits, clean `main` | Git history/status/remote | Product home, public family map, release definition |
| `kettle-core` | Git repo, 80 commits, dirty `main` | Git history/status/remote | Product semantics, Desk, API, CLI, runtime, reference web |
| `kettle-vscode` | Git repo, 6 commits, dirty `main` | Git history/status/remote | VS Code/Cursor adapter and generated projections |
| `kettle-desktop` | Git repo, 29 commits, dirty `main` | Git history/status/remote plus live README/charter | Electron lifecycle, local v2 presentation viewport, sidecar packaging |
| `kettle-obsidian` | Non-Git scaffold | README, `.gitignore`, `.local/`; no `.git` | Deferred host adapter only |
| `kettle-cli` | Empty non-Git directory | 0 bytes | No independent role; CLI is in core |
| `kettle-mcp` | Empty non-Git directory | 0 bytes | No current role; optional future bridge trigger has not been recorded |

The accurate count is **four repositories, one deferred adapter scaffold, and
two empty paths**, not seven repositories.

## Material topology correction

The live, committed Desktop v2 baseline does not load
`kettle-core/static/index.html`. `kettle-desktop/README.md`,
`docs/DESKTOP_V2.md`, and `main.js` establish a local `app/index.html`
presentation viewport that talks to core over HTTP. This is newer
implementation evidence than core prose still saying Desktop loads the same
file and has no style fork.

That does not move Desk semantics out of core, but it changes the adapter map:
VS Code and Desktop now both own host presentation code over one core spine.
Any coordination plan that treats Desktop as merely a wrapper around the core
web file is stale.

## From project prose

- `kettle/.local/open-questions.md` records CLI-in-core and optional MCP as
  settled.
- `kettle/.local/mcp.md` says no `kettle-mcp` directory until implementation
  starts.
- The public product roadmap says new repositories require a real
  implementation and release path.

These are authority statements, not proof of filesystem state; the inventory
above independently establishes the current state.

## Preliminary ballots

| Gate | Ballot | Operative correction |
|---|---|---|
| G1 | **concur-with-correction** | Preserve all seven names in the plan, but classify them as 4 Git repos + 1 deferred scaffold + 2 empty non-members. Do not initialize CLI or MCP repos. |
| G2 | **concur-with-correction** | Desktop is a thin semantic adapter but owns its v2 presentation viewport; reconcile stale shared-web-shell prose before automating its projection contracts. |

## Wall

Do not create repositories or remotes for the three non-repositories from this
sitting. Removing the two empty directories is reversible locally but still
requires an explicit patron answer because deletion was not authorized.

