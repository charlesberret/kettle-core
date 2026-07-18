# Setsweep — Platforms & Viewports

*Companion to [`ROADMAP.md`](../ROADMAP.md) Phases 3 and 6. The roadmap says what order the
platform work happens in; this file says what the platforms are, what each covers today, and
which adapters come next and why. Current-state claims below trace to the 2026-07-17 subsystem
surveys or to the files cited.*

## What a viewport is

A viewport is a thin client on the localhost core. It renders the desk; it holds no desk state
of its own (the desk is files in `.setsweep/`; the wire contract is [`API.md`](../API.md)).
Viewports differ only in how much of the contract they speak. Three capability levels, built
from API.md's route tiers:

| Level | What the patron can do | API surface |
|---|---|---|
| **A — attach + read** | Find the live core, see the queue and briefs | Discovery (`~/.cache/setsweep/server.json` → `:4242`, ping-validated), `GET /api/ping`, `/api/projects`, `/api/queue?mutate=0`, `/api/file` — API.md Tiers 0–1 reads |
| **B — full sitting** | Rule: approve, comment, read diffs, sweep, chat | `POST /api/approve`, `/api/comment`, `GET /api/diff` + `/api/diffstat`, the `/api/sweep` and `/api/chat`/`/api/compact` NDJSON streams, `/api/save` — API.md Tiers 1–2 |
| **C — founding** | Bring a new folder under care | `GET/POST /api/interview`, the confirm card, `POST /api/propose`, proposal approve, `POST /api/found` — API.md Tier 3 |

Tier A is the floor for calling something a viewport. Tier B is a real sitting. Tier C is the
hardest to build — the founding interview streams GFM that the client must upgrade into an
interactive confirm card, and the state machine (`none → interviewing → proposing → founded`)
must be derived from `/api/interview`, not guessed. API.md Tier 4 (kits, lineage, admin) and
Tier 5 (host-specific) are desk administration, not part of the viewport contract; a viewport
that never touches them is complete.

## The current matrix

| Viewport | A | B | C | Honest gaps (survey findings) |
|---|---|---|---|---|
| Web app (`static/index.html`) | yes | yes | yes | The reference implementation — also the only one with kits UI, lineage, admin, themes. One 4,254-line file; survivability work is Phase 2 (briefs 08–09), not platform work. |
| Electron desktop | yes | yes | yes | Attach-and-render: it loads the web frontend from the bundled sidecar, so it inherits every capability and every gap. Its own problems are distribution, not coverage — see below. |
| VS Code extension | yes | yes | yes | No kits UI, no lineage, no model picker (`/api/curator/catalog` unimplemented in its client); chatlog is not rehydrated on reload, so founding resume loses the transcript; no sidecar auto-start on main — attach-only. And it exists as two divergent trees (8,223-line committed branch vs 3,293-line untracked rewrite) awaiting brief 02. |
| CLI (`setsweep …`) | yes | partial | yes | Serverless — imports the desk code directly, never binds a port. 14 subcommands cover found/queue/chat/sweep-close/lineage/egress, but its agent turns hardcode the Claude dialect (brief 03 ports it onto `runtime.TOOL_TIERS`), and there is no approve/comment subcommand — ruling still happens in a graphical viewport. |

The pattern to notice: every viewport that exists reached Tier C, because founding is where a
desk begins. The gaps cluster in Tier B polish (streams rehydrated, models pickable) and in
Tier 4 conveniences nobody has needed outside the web app yet.

## The shared client

The VS Code extension already contains the seed of every future TypeScript adapter. Five files
— `api.ts` (393 lines), `discover.ts` (80), `confirmCard.ts` (173), `state.ts` (113),
`paths.ts` (35) — are host-agnostic today: ~800 lines with zero `vscode` imports, verified by
grep in the plugin survey. Brief 16 extracts them into `packages/core-client` in the plugin
monorepo.

What belongs in core-client: the typed API client, the NDJSON line parser and stream reducer
(partial-line buffering, the six event types, EOF-is-terminal), the confirm-card parser and
tick serializer, server discovery, and the ephemeral sitting-state store. What never belongs
there: rendering, webviews, commands, keybindings, or anything that knows what a panel is. The
extraction also forces the reconciliation of the two `api.ts` variants the divergent plugin
trees currently carry — brief 02 and brief 16 are the same cleanup seen from two ends.

For hosts that can't consume TypeScript, there is no shared client — **`API.md` is the
platform**. That is why the contract work (brief 13: queue-entry schema, Tier-4 shapes, the
streaming protocol spelled out, changelog discipline) is platform work, not documentation
housekeeping. Every non-TS adapter below is built from that document alone.

## Adapter candidates, ranked

| Rank | Host | Language / consumes | Audience | Effort | Call |
|---|---|---|---|---|---|
| 1 | Obsidian | TypeScript, Electron / `core-client` | Writing + knowledge kits | Moderate | **Build first** |
| 2 | MCP viewport | Python, in core / `API.md` internally | Any MCP host | Small | **Build second** |
| 3 | JetBrains | Kotlin / `API.md` | Large code audience | Heavy | After demand evidence |
| 4 | Sublime | Python / `API.md` | Modest | Moderate | Only on request |
| 5 | Neovim / Emacs | Lua, Elisp / `API.md` | Enthusiast | — | Document, don't build |

**Obsidian** is the clear first adapter. It is TypeScript on Electron, so it consumes
core-client directly — the client work is already done the day brief 16 lands, leaving only the
plugin shell and panel rendering. More importantly it reaches the audience the kit system was
half built for: the writing and knowledge kits assume a patron who lives in a notes vault, and
today that patron's only viewport is a browser tab. Effort is moderate; payoff is a second
proof that the desk is host-neutral, in front of the right users.

**The MCP viewport** is the cheapest surface-area multiplier available. Expose the desk as an
MCP server — tools for queue, entry, approve, comment, plus sweep behind a confirmation — and
every MCP-capable host (Claude Desktop, other agent clients) becomes a Tier A/B viewport
without us writing a line of host code. It is a thin translation layer over routes that
already exist. What it will not carry well is Tier C: the founding interview's confirm-card
choreography doesn't map onto tool calls, and shouldn't be forced to. Found in a full viewport;
sit anywhere.

**JetBrains** has the largest paying code audience of anything on this list, and no path to the
TypeScript client — a Kotlin plugin consumes `API.md` and nothing else, which makes it the
truest test of brief 13's contract. It is also the heaviest build (its own UI toolkit, its own
review conventions) and should wait for evidence that VS Code + Cursor users are asking for it.

**Sublime** is a Python host, so an adapter is honest, modest work against the HTTP contract —
but the audience is small and shrinking. Build it if a real user asks; don't build it on spec.

**Neovim and Emacs** users build their own integrations better than we would, and resent being
handed one. The right investment is a complete, truthful `API.md` with the streaming protocol
and queue-entry schema documented (brief 13), plus a short "writing an adapter" note — then
let the community shape what fits their editors.

## The desktop app's road

Today's honest state, from the desktop survey: the app works and its Electron security posture
is genuinely careful, but it is not distributable. No signing or notarization (`osxSign:
false`; the built bundle carries an adhoc signature with `Identifier=Electron`), zip-only maker
with the DMG maker installed but unwired, no auto-update, no CI, no release tags. The bundle is
317 MB with the 20 MB PyInstaller sidecar shipped twice, darwin-arm64 only — and the currently
installed app was built from a dirty core tree (`setsweepDirty: true` in its own version.json).

The road out is ordered and mostly known (brief 15 carries it):

1. **Signing + notarization** — Developer ID in the forge config; the one step with an
   external prerequisite (an Apple Developer account) and the hardest wall between the repo
   and a downloadable app.
2. **DMG** — wire the maker that is already a devDependency.
3. **CI on tags** — build, sign, and release from GitHub Actions, and refuse to stamp a build
   when the core tree is dirty. A bug report must correspond to a commit.
4. **Auto-update** against GitHub Releases — the stamped version.json already gives an honest
   local version to compare.
5. **Bundle slim** — stop shipping the sidecar twice, exclude dev files, enable asar.
6. **Universal binary** — arm64+x64 doubles the addressable macOS audience at modest cost.
7. **Windows/Linux horizon** — the PyInstaller sidecar makes both plausible (nothing in core
   is macOS-bound except `/api/open-link`), but neither is promised until macOS is clean.

Two sidecar-lifecycle fixes ride along: a sidecar crash today shows a dialog and quits the app,
costing the patron their window — replace with restart-with-backoff and reattach. And the
app's hardest external dependency, the curator CLI, gets no onboarding at all — a first-launch
detection with a friendly explanation is the cheapest fix for the worst first impression.

## Remote access

No viewport leaves localhost until two preconditions hold, in order: the Phase 2 per-boot auth
token (brief 05) ships, and access arrives as **tunnel guidance** — SSH port-forward or
Tailscale-style overlay to `127.0.0.1:4242` on the desk machine — documented for patrons who
want it. There will never be a listen-on-0.0.0.0 flag.

The reason is the write surface: `/api/save` writes files under every registered project root,
and `/api/sweep` spawns an agent with write-tier tools — so any host that can reach the port
can edit the patron's files. Localhost-only is DESIGN §5's first invariant, and remote access
must be something a patron builds a tunnel for on purpose, never something the server offers.
