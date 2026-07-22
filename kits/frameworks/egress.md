# Desk egress

`.setsweep/outbound/` is the desk's **staging queue** for signals meant for the broader agent
ecosystem. Stage here; never route from the curator sandbox into `~/cloud/sync/system/` or transmit
mail. Fleet pickup drains `Status: staged` files and routes them.

**Not** the inbox kit's `<root>/outbox` — that holds approved mail drafts for an out-of-band sender.

## Filename

`YYYY-MM-DD-<kind>-<slug>.md`

Kinds: `handoff` | `escalation` | `launch` | `domain` | `approval`

## Header

```markdown
# Egress: <topic>
**From:** setsweep/<project-id> · **Date:** YYYY-MM-DD
**Kind:** handoff | escalation | launch | domain
**Route:** <hint>
**Status:** staged

<body>
```

## Kind → Route

| Kind | Use when | Typical Route |
|------|----------|---------------|
| `handoff` | Peer facts for another machine/agent | `avicenna`, `hesiod`, `all`, or a handoff topic hint |
| `escalation` | Above the desk's lane — needs Majordomo | `majordomo` |
| `launch` | Ledger "go"/grant/schedule — do not execute | `handoff-setsweep-avicenna-directives` |
| `domain` | Project-domain inbox (e.g. Characters recast) | `Characters/inbox` (or the charter path) |
| `approval` | Patron approved (or still blocks) work other agents depend on | `fleet`, project AGENTS.md peers, or a named agent |

## Discipline

1. Prefer `setsweep egress <project> …` (or the helper) over freehand filenames.
2. Launch rulings: append `LAUNCH DIRECTIVE:` to `runtime/sweep.log` **and** stage a `launch` egress memo.
3. Domain memos may still write to their project path; also stage a short `domain` egress pointer.
4. **Approvals (approve + sweep):** when the patron's pass unblocks other agents (roadmap,
   specs, gates named in `unblocks` / charter fleet map), stage a `kind: approval` memo
   listing paths, entry ids, and whether work may proceed. Also note remaining **pending**
   queue items that still block peers. Mechanical close stages this automatically when
   possible; judgment sweeps must still do it.
5. Session logs: point at egress paths; do not restate the body.
6. Leave `Status: staged` — pickup flips status / archives after routing.
