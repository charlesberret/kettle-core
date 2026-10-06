# Platforms and viewports

A Kettle viewport is a thin client on the localhost core. It renders one Desk
and holds no durable Desk state of its own. The wire contract is
[`API.md`](../API.md); the canonical browser UI is `static/index.html`.

## Capability levels

| Level | User capability | Core surface |
|---|---|---|
| Attach and read | Discover core, list projects, read queue and files | Ping, discovery, projects, queue, file |
| Full sitting | Comment, approve, chat, inspect diffs, sweep | Read surface plus sitting writes and NDJSON streams |
| Founding | Bring a new project under care | Register (founding sentence) → interview → propose → Found Desk |

## Current viewports

| Viewport | Attach/read | Full sitting | Founding | Notes |
|---|---|---|---|---|
| Browser | Yes | Yes | Yes | Reference UI served by core |
| Desktop | Yes | Yes | Yes | Loads the same core web UI |
| VS Code / Cursor | Yes | Yes | Candidate | Automated adapter tests are green; packaged live-host dogfood remains a release gate |
| CLI | Yes | Partial | Yes | First-class serverless commands; no graphical editor or approval panel |

The desktop does not own a frontend. A desktop UX gap is normally a core web
gap. The editor extension may adapt layout to the host but must preserve the
same founding state and ritual meanings. Sitting visual, copy, and palette
changes land in this tree; desktop inherits `static/index.html`. VS Code runs
`sync-ui-copy` / `sync-palette` when those sources change. See
[`REVIEW.md`](./REVIEW.md).

## Founding state

Every graphical viewport derives the same state from core:

```text
none -> interviewing -> proposing -> founded
```

It must not infer a second state machine from local UI state. Proposal approval
and founding remain distinct routes.

## Ritual invariants

| Action | Meaning |
|---|---|
| Approve | Bookmark the user's ruling; do not apply or transmit |
| Comment | Attach send-back context to the selected entry |
| Finish batch (sweep) | Close the sitting under explicit policy and restock the queue |
| Egress | Stage an outward action for review |

Shared visible strings are owned by `static/ui-copy.json`. The web and desktop
read it through `/ui-copy.js` (rendered per request); Python viewports read it
through `kettle.uicopy` or `GET /api/ui-copy`; the VS Code adapter commits a
generated TypeScript snapshot and checks it for drift. A viewport that hardcodes
a string the catalog already holds is a bug — see `docs/UI.md` § Shared UI copy.

## Adding a viewport

A new viewport should have:

1. a concrete host workflow and dogfood owner;
2. an explicit compatibility manifest;
3. attach/read behavior before write behavior;
4. tests for discovery, contract rejection, and ritual semantics;
5. a packaging and update path.

For a non-TypeScript host, [`API.md`](../API.md) is the platform and
[`SITTING-FLOWS.md`](./SITTING-FLOWS.md) is the order of calls. A shared
client should be extracted only after multiple real consumers need it.

Kettle remains a single-user, loopback-only instrument. Remote and multi-user
serving are not viewport features.
