# Counsel (contract/API) — architect-gemini

**Verified Facts:**
- `kettle-core` owns the HTTP API, desk schema, UI-copy, and bundled-core provenance.
- Adapters (vscode, desktop) consume these contracts.

**Recommendations:**
- We must enforce these contracts via CI checks. Current local scripts rely on sibling paths, which is fragile.
- Preliminary ballot on G2: concur-with-correction (ownership is documented but lacks cross-repo automated enforcement).
