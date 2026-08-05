# Counsel — repo-topology seat (architect-grok)

Speaking only from the topology lens.

## Verified this session

| Tree | Git? | Commits | Dirty paths | Remote | Notes |
|------|------|---------|-------------|--------|--------|
| `kettle` | yes | 13 | 0 | `charlesberret/kettle` | Public/home product tree |
| `kettle-core` | yes | 80 | **9** | `charlesberret/kettle-core` | Product core |
| `kettle-vscode` | yes | 6 | **2** | `charlesberret/kettle-vscode` | VS Code/Cursor adapter |
| `kettle-desktop` | yes | 29 | **9** | `charlesberret/kettle-desktop` | Electron shell |
| `kettle-cli` | **no** | — | — | — | Empty dir (0 bytes content) |
| `kettle-mcp` | **no** | — | — | — | Empty dir (0 bytes content) |
| `kettle-obsidian` | **no** | — | — | — | README + `.gitignore` + `.local/`; no `.git` |

**Fact:** four live repos, not seven. **Peer-verified agreement:** matches `architect-opus` topology table (independent re-count this session).

## From project prose (canon)

`kettle/.local/family.md` and `open-questions.md`:

- CLI is **first-class viewport that ships in core**, not a separate repo (settled `[x]`).
- MCP is **optional only; not a pillar** (settled `[x]`); optional home “under core or `kettle-mcp`”.
- `kettle-obsidian` listed as **later** adapter when writing/knowledge kits need it.

`kettle-core/CLAUDE.md` names siblings `kettle-desktop` and `kettle-vscode` only — consistent with four-live-repo reality, not with seven-peer framing.

**Stale prose (not topology decision):** `family.md` still says core is largely setsweep transplant-pending and desktop awaiting rename — false against commit history (inference: state column lag).

## Preliminary gate ballots (this seat only)

| Gate | Ballot | Operative note |
|------|--------|----------------|
| G1 | **concur-with-correction** | Topology = **4 live repos** + **1 deferred adapter** (`kettle-obsidian`) + **2 stubs** (`kettle-cli`, `kettle-mcp`) that contradict settled “not separate repo” decisions unless patron reopens them. |
| G2 | defer to contract seat | Only four trees can own history-backed contracts. |

## Wall

Do not initialize or populate `kettle-cli` / `kettle-mcp` as public repos on the strength of this sitting. Deletion vs justification of stubs is a patron call; creating remotes is near-irreversible.

— `architect-grok` / repo-topology seat
