# Counsel (repo-topology) — architect-gemini

**Verified Facts:**
- Disk contains 7 directories starting with `kettle`: `kettle`, `kettle-cli`, `kettle-core`, `kettle-desktop`, `kettle-mcp`, `kettle-obsidian`, `kettle-vscode`.
- `kettle/.local/family.md` lists `kettle-cli` as "not a separate repo" and `kettle-mcp` as "under core or kettle-mcp" for later.

**Recommendations:**
- The family currently operates on 4 active git repositories (`kettle`, `kettle-core`, `kettle-vscode`, `kettle-desktop`). `kettle-obsidian` is a deferred scaffold, and `kettle-cli`/`kettle-mcp` are empty stubs violating the current architecture rules. We should formally remove the 2 stubs.
- Preliminary ballot on G1: concur-with-correction.
