# Handoff: Viewport ↔ core alignment (2026-07-25)

**Audience:** the next agent taking a full-system pass on Setsweep  
**Repos:** `setsweep-core`, `setsweep-plugin` (and desktop only where it loads core web)  
**User:** Charles, primarily **VS Code** plugin + live core on `:4242`  
**Monitor:** stopped (session debug watch killed at memo time)

This memo records what broke in production UX, what we tried, what is still dirty on disk, and how the last several days of “shore up / parity” work created blind spots. Use it to design a **second big pass** that realigns core + plugin + desktop around one founding/sitting state machine—not more drive-by patches.

---

## 0. Executive thesis (your suspicion, refined)

A **core-centric overhaul** (tool tiers, provider capabilities, brief standard, founding parity briefs, ui-copy, shore-up branch) improved honesty and architecture **behind** the API. Simultaneously the **plugin Desk** evolved as a host-adapted UI that *claims* Tier C founding parity in `docs/PLATFORMS.md` but **does not implement the full web state machine**.

The result: core can be “correct” while the user cannot complete founding, see agent work, compact a session, or even open a dropdown—because those behaviors live in **viewport glue** that was never re-walked against `static/index.html` after the overhaul.

**Canonical rule already written (and under-enforced):**

| Surface | Source of truth |
|---------|-----------------|
| Sitting rituals / state machine | `setsweep-core/static/index.html` + `API.md` |
| Desktop | Same web file via sidecar — **no separate frontend** |
| Plugin Desk | May re-layout, **must match web rituals** (`docs/PLATFORMS.md`) |

The next pass should treat **plugin ≠ second product**: it is an adapter that must re-verify every cell of the PLATFORMS ritual matrix after core changes.

---

## 1. Map of the system (read first)

| Path | Role |
|------|------|
| [`ROADMAP.md`](../../ROADMAP.md) | Spine: phases 0–7, north star, fragile gaps |
| [`docs/PLATFORMS.md`](../PLATFORMS.md) | Viewport A/B/C levels; **ritual parity matrix**; founding state machine |
| [`docs/UI.md`](../UI.md) | Sitting type hierarchy; read before editing web UI |
| [`API.md`](../../API.md) | Wire contract (interview / propose / found / chat / compact / tiers) |
| [`ARCHITECTURE.md`](../../ARCHITECTURE.md) | Desk files, tool tiers, invariants |
| [`docs/briefs/`](../briefs/) | Work packages; especially **22** founding parity, **06** capabilities, **19** fence, **16** extract client |
| [`docs/briefs/22-viewport-founding-parity.md`](../briefs/22-viewport-founding-parity.md) | Explicit founding UX target |
| [`docs/ENGINEERING.md`](../ENGINEERING.md) | Tests, doctor, debugging posture |
| [`docs/RELEASE.md`](../RELEASE.md) | Security / release gates |
| [`Claude.md`](../../Claude.md) / `CLAUDE.md` | Agent orientation; **run-critical** files; never bind `:4242` casually |
| Plugin [`packages/vscode/DESK.md`](../../../setsweep-plugin/packages/vscode/DESK.md) | Desk anatomy for contributors |
| Plugin `packages/vscode/src/deskPanel.ts` | Entire plugin sitting UI (HTML/CSS/JS template) |
| Plugin `packages/vscode/src/extension.ts` | Host glue, commands, sidecar |
| Plugin `packages/vscode/src/api.ts` | HTTP + NDJSON client |
| Core `static/index.html` | **Reference** sitting + founding UX |
| Core `runtime.py` | Stream normalize, tool tiers, provider capabilities |
| Core `server.py` | Routes; run-critical |
| Core `survey.py` | Tool-less founding survey (Phase A) |

**Three repos:**

| Repo | Branch / tip (at handoff) | Notes |
|------|---------------------------|--------|
| `setsweep-core` | `codex/shore-up-system` @ `dc67d74` (+ **uncommitted** survey/UX follow-ons) | Ahead of origin by 1 commit; dirty tree after that |
| `setsweep-plugin` | `main` @ `cb9584a` (+ **large uncommitted** Desk/founding/compact work) | Ahead of origin by 1; live VS Code loads **installed** extension, not git tree |
| `setsweep-desktop` | (not deeply touched this session) | Loads core web UI |

---

## 2. Direction of the last several days (core)

Recent `codex/shore-up-system` history (newest first, abbreviated):

1. **`dc67d74`** — Tool-less founding interview via core survey snapshot (`survey.py`); Grok no longer refused with `read_only_unavailable` *when process reloads*.
2. **`faa8d74` / `ff18413`** — Port circuit-breaker; pair curator provider with default command.
3. **`6019de7` / `5742ac7`** — `refresh-briefs` + cold-re-entry brief standard.
4. **`e904f62` / `1bc893d`** — Shared **ui-copy** catalog; plugin syncs via package script.
5. **UI hierarchy commits** — type roles, mid chrome, brief pane gray labels (`docs/UI.md`).
6. **`41eef02` / brief 22** — Founding parity: slim add-project; orient into interview.
7. **Earlier shore-up** — tool tiers single-source, prompts externalized, provider capabilities, watchdog, frontend survivability (briefs 03–09, 20–21).

**Intent of the overhaul:** one truth for tiers/prompts/capabilities; honest provider matrix; viewport parity *documented*; web as canonical sitting.

**Blind spot:** “parity” was declared for plugin founding (PLATFORMS matrix “same”) without a **mechanical checklist** that the plugin still implements web’s full chain:

```text
none → interviewing → proposing → founded
  interview stream → confirm card → propose → open DESK-PROPOSAL
  → Approve(=found) → /api/found → first queue batch
```

Web still does this in `static/index.html` (`approve` → `foundFromProposal`). Plugin had partially regressed.

---

## 3. Problems we hit (production symptoms)

### 3.1 Founding blocked: `Founding interview failed: read_only_unavailable`

| | |
|--|--|
| **Symptom** | Toast with error code only; interview never streams |
| **Root** | Live core process still on **old** code with Grok `read_only_tier: false` and pre-stream 409 on `/api/interview` |
| **Confounders** | Editable install `~/.setsweep-venv` → core tree, but **Python does not hot-reload**; plugin “restart core” often **attaches** to healthy `:4242` without `--replace`; `~/.cache/setsweep/server.json` may point at **test** ports |
| **Fix path used** | `pip install -e .` after adding `survey` module; kill stale PID; `setsweep --web --port 4242 --replace`; verify `/api/ping` `capabilities.read_only_tier` and new `started` |
| **Committed** | `dc67d74` tool-less interview + survey |
| **Still dirty** | Follow-on: blank card prechecks, prompts, index.html parse blank ticks |

### 3.2 Plugin shipped stale while git was fixed

| | |
|--|--|
| **Symptom** | “Begin interview” button next to Approve; stays during interviewing |
| **Root** | VS Code loads `~/.vscode/extensions/charlesberret.setsweep-0.6.64/` — **not** the git checkout; version number unchanged so “reload” reloads old bits |
| **Method** | `rg btnBeginFounding` across installs; `cmp` git dist vs install; copy dist into install; later removed button from source |
| **Lesson** | Any plugin fix requires **compile + install path** (or VSIX version bump). Prefer version bump (`0.6.65+`) so “latest” is unambiguous |

### 3.3 Confirmation card UX: mixed radios/checkboxes + pre-ticked options

| | |
|--|--|
| **Symptom** | Confusing single vs multi controls; options already checked |
| **Root** | Plugin `confirmCard.ts` used `multi: id !== "status"` (wrong); survey `suggested_prechecks` pre-ticked GFM `- [x]` |
| **Fix** | Align multi detection with web (`(choose one)` + status/horizon); start **blank** for user; stop injecting prechecks into stems |
| **Files** | `confirmCard.ts`, `kits.py`, `survey.py`, `server.py` interview inject, `static/index.html` parse |

### 3.4 Proposal drafted but never opens

| | |
|--|--|
| **Symptom** | Toast “open DESK-PROPOSAL.md” only; user must open manually |
| **Root** | Plugin `propose` never called `openTextDocument`; web loads proposal into editor |
| **Fix (dirty)** | `openDraftedProposal()` after propose; non-preview tab; delayed re-open to beat webview focus |
| **Verify** | Neogenie desk had `status=proposing`, file on disk, queue entry `desk-proposal` under `.setsweep/runtime/queue.json` |

### 3.5 Unclear / impossible to approve proposal (“Found desk”)

| | |
|--|--|
| **Symptom** | After proposal, no clear control to found the desk |
| **Root (critical)** | Plugin treated `proposing` as `isFounding()` → CSS hid **all** ritual buttons including Approve; `canApprove` required `!founding`. Web **pulses Approve** in `body.proposing` and on proposal approve runs **`/api/found`**. Plugin only bookmarked via `/api/approve`. |
| **Fix (dirty)** | Split **interviewing** vs **proposing** chrome; show **Found desk** label + pulse; `approveEntry` → `foundFromProposal` → `runHostStream("found")` → `/api/found` |
| **Web reference** | `static/index.html`: `isProposalEntry`, `approve()`, `foundFromProposal()` |

### 3.6 Compact “does nothing”

| | |
|--|--|
| **Symptom** | Chat compact command no visible effect |
| **Root** | Plugin had **zero** compact client path; web uses context-bar → `POST /api/compact` |
| **Fix (dirty)** | `api.compact`, Desk intercept `/compact`, command `setsweep.compactSession` |
| **Caveat** | No session_id → server no-ops with empty stream; Grok may not implement Claude-style `/compact` the same way |

### 3.7 No visual indication of background agent activity

| | |
|--|--|
| **Symptom** | Stream idle while agent works (esp. under Grok) |
| **Root** | (1) Grok `streaming-json` emits only `thought` / `text` / `end` — **no tool events** even when tools run (`num_turns`>1). Core **dropped** `thought`. (2) Plugin filtered empty streaming stubs; no spinner chrome. Web has `showSpin` / `setSpinLabel`. |
| **Fix (dirty)** | Core: `thought` → `{t:"activity", kind:"thought"}`. Plugin: activity strip (dot + label + elapsed); tools still update strip under interview freeze |
| **Requires** | Core process restart to load `runtime.py` change |

### 3.8 Project dropdown unclickable

| | |
|--|--|
| **Symptom** | Project pill does nothing / menu not usable |
| **Root** | Absolute dropdown under header painted **under** later flex siblings (brief/stream); `z-index` on menu ineffective without stacking context on header; body `overflow:hidden` |
| **Fix (dirty)** | `header.top { position:relative; z-index:100 }`; menus `z-index:200`; mousedown outside-to-close |

---

## 4. Methods used this session (for reproducibility)

1. **Resume Claude session** (`session_reader.py`) — landed mid plugin commit work.  
2. **Live process forensics** — `lsof :4242`, `ps`, `/api/ping` (pid, `started`, `capabilities`).  
3. **Disk vs memory** — editable install loads `setsweep-core` tree; compare `import runtime` file path vs process start time.  
4. **Install path forensics** — `~/.vscode/extensions/charlesberret.setsweep-*` vs git `packages/vscode/dist`.  
5. **API probes** — POST `/api/interview` (expect no 409), GET queue/interview status per project.  
6. **Provider stream sampling** — `grok -p … --output-format streaming-json` to learn real event types.  
7. **Web vs plugin cross-walk** — grep `foundFromProposal`, `body.proposing`, spin, compact in `static/index.html` vs `deskPanel.ts` / `extension.ts`.  
8. **Persistent debug watch** (now stopped) — `/tmp/setsweep-debug/watch.sh` on ping + button remnant.  
9. **Hot install** — `npm run compile` + `cp dist/*` into VS Code extension folder (no VSIX bump).  
10. **Tests** — `pytest test_survey test_runtime test_server` subsets; plugin `npm test` (39).

**Operational rules that blocked false “restarts”:**

- Do not trust “Restart Core” without checking **new pid + started timestamp**.  
- Do not trust plugin “reload” without checking **file mtime / content** of installed `dist/deskPanel.js`.  
- After new top-level modules (`survey.py`), always `pip install -e .` (py-modules mapping).  
- Prefer not to kill `:4242` from agents without user intent; this session eventually required real replace.

---

## 5. Current git / install state (honest)

### Core (`codex/shore-up-system`)

- **Committed:** tool-less interview + survey (`dc67d74`).  
- **Uncommitted (approx):** blank-card policy, interview prompts, `runtime` activity events, `ui-copy` proposing strings, `static/index.html` blank ticks, tests.  
- **Live runtime:** depends on last `--replace`; verify with ping.

### Plugin (`main`)

- **Committed tip:** register project + earlier desk rework.  
- **Uncommitted (large):** Found desk, open proposal, compact, activity strip, dropdown z-index, confirm card multi/blank, DESK.md, package.json command.  
- **Installed:** patches copied into `~/.vscode/extensions/charlesberret.setsweep-0.6.64` — **fragile**; may diverge from git; version still 0.6.64.

### Not done

- Clean commits / push for either tree.  
- VSIX version bump + formal reinstall.  
- Full re-walk of PLATFORMS ritual matrix with automated or scripted checklist.  
- Desktop-specific verification (should equal web if core web is healthy).  
- Grok: true tool events in streaming-json (upstream limitation; activity is a workaround).  
- Context-bar / token meter parity in plugin (web has it; plugin partial).

---

## 6. Recommended “big pass” for the next agent

### Goal

One founding + sitting **state machine**, three viewports, zero “works in web / broken in plugin” cells on the PLATFORMS matrix.

### Method (do not skip)

1. **Freeze a parity checklist** from `static/index.html` (not from plugin DESK.md alone):  
   register → interview → card → propose → open proposal → Found desk → found stream → queue stocked → chat shows activity → compact → approve/comment/sweep.  
2. For **each step**, write:  
   - web entrypoint (function / CSS class / route)  
   - plugin entrypoint  
   - pass/fail on Charles’s machine  
3. Fix **adapter gaps** in plugin host glue; fix **contract gaps** only in core if web is wrong.  
4. After every core stream/tier change, re-run checklist under **Claude and Grok**.  
5. **Ship discipline:** bump plugin version; install via VSIX or documented `cp` recipe; require ping `started` after core changes.  
6. Consider brief **“23 — Viewport ritual regression bar”**: a small Node or Playwright-less test that asserts plugin message handlers exist for compact/found/propose open, and a markdown checklist in CI for humans.

### High-value code anchors (plugin)

| Ritual | Web | Plugin (should mirror) |
|--------|-----|-------------------------|
| Interview | `/api/interview`, founding head | `beginFounding`, `runFoundingInterview`, confirm card |
| Propose | finish → `/api/propose` + load editor | `confirmCard` → `propose` → `openDraftedProposal` |
| Found | `approve` + `foundFromProposal` | `approveEntry` + `foundFromProposal` + **Found desk** chrome |
| Activity | `showSpin` / tool rows | activity strip + tool rows + core `activity` events |
| Compact | ctx bar → `/api/compact` | `/compact` slash + `setsweep.compactSession` |
| Provider truth | `/api/ping` capabilities | Desk model pill; do not invent capability UX users must parse |

### Anti-patterns observed

- Declaring PLATFORMS “same” without running founding end-to-end on the plugin.  
- Patching git `src/` and assuming VS Code reloads it.  
- Treating `isFounding()` as one chrome state (hides Approve during proposing).  
- Assuming Grok stream looks like Claude stream (tools).  
- Assuming process restart from plugin without pid check.  
- Toast-only recovery for missing ritual buttons.

---

## 7. Suggested immediate sequencing (if continuing tomorrow)

1. **Inventory dirty trees** — split into logical commits (core survey follow-on; plugin founding ritual restore; plugin compact+activity; plugin chrome fixes).  
2. **Bump plugin to 0.6.65**, package, install cleanly; remove reliance on silent dist overwrite.  
3. **End-to-end founding** on a scratch folder under Grok and Claude; film the ritual matrix.  
4. **Parity doc update** — refresh `PLATFORMS.md` date and any cell that is still gap (type hierarchy already noted).  
5. Optional: extract shared founding client logic (brief 16 direction) so open/found/compact cannot drift again.

---

## 8. One-page recovery card (ops)

```bash
# Core really reloaded?
curl -s http://127.0.0.1:4242/api/ping | python3 -m json.tool | head -40
# Expect new started + read_only_tier true under grok after dc67d74+

# Editable install after new modules
cd ~/cloud/git-projects/setsweep-core && ~/.setsweep-venv/bin/pip install -e .

# Force core
kill $(lsof -nP -iTCP:4242 -sTCP:LISTEN | awk 'NR==2{print $2}')  # if needed
~/.setsweep-venv/bin/setsweep --web --port 4242 --replace --no-open

# Plugin from git into VS Code install (dev only)
cd ~/cloud/git-projects/setsweep-plugin/packages/vscode
npm run compile
cp dist/*.js dist/*.js.map package.json \
  ~/.vscode/extensions/charlesberret.setsweep-0.6.64/dist/  # adjust paths
# Then: Developer: Reload Window
```

---

## 9. Closing

The constellation is not mysterious: **core owns the desk and streams; web is the ritual reference; plugin is a host adapter that fell behind on Tier C and stream chrome while core/docs claimed parity.** The last days improved backend honesty (tiers, survey, briefs, providers) faster than the plugin’s reimplementation of the sitting UI.

The next agent’s job is **alignment verification + ritual restoration**, not another isolated feature. Start from `docs/PLATFORMS.md` + `static/index.html`, treat every “same” cell as a failing test until proven on VS Code under Grok and Claude, and ship install/version discipline so fixes reach the process the user actually runs.

---

*Written 2026-07-25 after a multi-hour debug session on founding, Grok capabilities, plugin install skew, and stream UX. Monitor subagent stopped. No claim that dirty work is committed or that live core matches disk without a ping check.*
