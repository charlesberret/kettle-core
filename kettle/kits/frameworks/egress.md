# Desk egress

The desk's `outbound/` folder (the `outbound/` directory inside the desk directory named
elsewhere in this prompt — do not assume it is `.kettle/`; an unmigrated desk keeps its
legacy directory) is the **staging queue** for signals meant for other agents or systems.
Stage here; never transmit mail or route outside the project from the curator sandbox.
External pickup drains `Status: staged` files and routes them.

**Not** the inbox kit's `<root>/outbox` — that holds approved mail drafts for an out-of-band sender.

## Filename

`YYYY-MM-DD-<kind>-<slug>.md`

Kinds: `handoff` | `escalation` | `launch` | `domain` | `approval`

## Header

```markdown
# Egress: <topic>
**From:** kettle/<project-id> · **Date:** YYYY-MM-DD
**Kind:** handoff | escalation | launch | domain | approval
**Route:** <hint>
**Status:** staged

<body>
```

## Kind → Route

Default route hints ship neutral (product code). Override per machine in
`settings.json` under `egress.routes` (deep-merged).

| Kind | Use when | Default Route |
|------|----------|---------------|
| `handoff` | Peer facts for another machine/agent | `peers` |
| `escalation` | Above the desk's lane — needs human or orchestrator attention | `escalation` |
| `launch` | Ledger "go"/grant/schedule — do not execute | `launch` |
| `domain` | Project-domain inbox (specialist process outside the desk) | `domain` |
| `approval` | User approved (or still blocks) work other agents depend on | `peers` |

## Discipline

1. Prefer `kettle egress <project> …` (or the helper) over freehand filenames.
2. Launch rulings: append `LAUNCH DIRECTIVE:` to `runtime/sweep.log` **and** stage a `launch` egress memo.
3. Domain memos may still write to their project path; also stage a short `domain` egress pointer.
4. **Approvals (approve + sweep):** when the user's pass unblocks other agents (roadmap,
   specs, gates named in `unblocks` / charter peer map), stage a `kind: approval` memo
   listing paths, entry ids, and whether work may proceed. Also note remaining **pending**
   queue items that still block peers. Mechanical close stages this automatically when
   possible; judgment sweeps must still do it.
5. Session logs: point at egress paths; do not restate the body.
6. Leave `Status: staged` — pickup flips status / archives after routing.
