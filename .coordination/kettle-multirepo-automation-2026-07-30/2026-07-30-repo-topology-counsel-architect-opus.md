# Counsel — repo-topology seat (architect-opus)

Speaking only from the topology lens: what trees exist, what they are, what is load-bearing.

## Verified inventory (this session, `git -C <r> log/rev-list/status`, `ls`)

| Tree | Git? | Commits | Last commit | Dirty | Remote |
|---|---|---|---|---|---|
| `kettle` | yes | 13 | 2026-07-27 | 0 | `charlesberret/kettle` |
| `kettle-core` | yes | 80 | 2026-07-28 | **9** | `charlesberret/kettle-core` |
| `kettle-vscode` | yes | 6 | 2026-07-28 | 2 | `charlesberret/kettle-vscode` |
| `kettle-desktop` | yes | 29 | 2026-07-26 | 9 | `charlesberret/kettle-desktop` |
| `kettle-cli` | **no** | — | — | — | — (0 bytes, empty dir, created 2026-07-25) |
| `kettle-mcp` | **no** | — | — | — | — (0 bytes, empty dir, created 2026-07-25) |
| `kettle-obsidian` | **no** | — | — | — | — (12K: README + `.gitignore` + `.local/`, no `.git`) |

**There are four repos, not seven.** Three of the trees are empty placeholder
directories with no git history, no remote, and — for two of them — literally zero
bytes of content.

## The finding that matters most

`kettle/.local/family.md` — the private design canon for exactly this question —
**already rules against two of the three stubs**, under a heading titled
"Not separate repos (by default)" and "CLI (not a separate repo)":

> "The **CLI ships in kettle-core** but is a **first-class viewport** … Do not treat
> it as 'just how you start the server.'"

and lists MCP as *"Optional later — under core **or** `kettle-mcp`"*, gated on a
trigger ("Model-in-host tools over the desk") that has not fired.
`open-questions.md` records `[x] CLI first-class (not GUI sidecar); ships in core`
and `[x] MCP optional only; not a pillar` as **settled**.

So `kettle-cli/` and `kettle-mcp/` are not "repos we haven't started." They are empty
directories whose existence **contradicts a settled decision**. A sitting that treats
them as members of the family will plan work the canon has already declined.

`kettle-obsidian/` is different in kind: `family.md` lists it as a real future
adapter ("Later — when writing/knowledge kits need it"), and it has a README and a
`.local/`. It is a legitimately deferred repo, not a contradiction.

## Where `CLAUDE.md` in kettle-core is stale

The orientation file names exactly two siblings (`kettle-desktop`, `kettle-vscode`)
and says "A future MCP bridge would be a narrow tool adapter." That is **consistent
with the canon** and inconsistent only with the *stub directories on disk*. My read:
`CLAUDE.md` is right and the disk is wrong. This inverts the framing in the patron's
charge ("the 7 repos") — I flag it rather than quietly plan around it.

`family.md` is itself stale in the other direction: it describes `kettle-core` as
"content still largely `setsweep-core` until transplant" (false — 80 commits, 134
tracked files, full Python package) and desktop as awaiting rename (false — renamed,
29 commits). The canon's *decisions* hold; its *state column* does not.

## Ballot from this seat

- **G1 — concur with a correction**: the topology is **4 live repos + 1 deferred
  adapter (`kettle-obsidian`) + 2 stubs that should be deleted or justified**, not 7 peers.
- **G2 — defer to the contract seat**, but note topology constrains it: only four
  trees can *own* anything, because only four have history.

## Wall from this seat

Do not create, initialize, or populate `kettle-cli` or `kettle-mcp` as repos on the
strength of this sitting. Reversing a settled decision in `open-questions.md` is the
patron's call, and creating a repo is close to irreversible in a public account.
