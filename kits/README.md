# Curator kits

A **kit** arms a project's resident curator. `_base.md` is the shared handbook every curator
reads; each `<kind>.json` here is a **kind playbook** layered on top, and a project picks one at
founding (its `kit` field in `projects.json`) — the patron chooses; there is no auto-detection.

The four kinds are cut on one axis — the **review posture** the curator takes:

- **writing** — prose you compose/refine (notes, drafts, articles, reports, correspondence)
- **code** — any software project
- **records** — structured data kept accurate against a source of truth (datasets, inventories, logs)
- **knowledge** — an interlinked body of canonical docs kept coherent (notes systems, wikis, specs, governance, agent definitions, research archives)
- **inbox** — a pile to work through (emails, support requests, reports, applications): the curator triages each incoming item and **drafts a response**; you read the summary and edit the reply

Leaving a project's kit unset gives a general curator with no specialized lens.

## Product prompts (`prompts/`)

`prompts/*.md` is Setsweep's user-visible curator language: founding, sweep, accrue,
chat-context, and live-reporting instructions. The server reads each file once at import.
Prompt files are safe to tune directly; preserve their `{placeholders}` and run the prompt
format smoke test after editing. A missing file logs a warning and uses a short built-in
emergency prompt so a prompt-editing mistake cannot stop the server from booting.

## The inbox kind is special — it has live intake

Every other kind queues an **existing project file** you review (the brief summarizes the file you
edit). **Inbox inverts this:** the brief summarizes a **source item** (the incoming email/report/
request) and the file you edit is a **freshly-drafted response** to it. Two extra mechanics, both
configured on the **project stanza** (not the kit — intake paths are personal wiring), under an
`intake` block:

```json
"kit": "inbox",
"intake": {
  "watch":     "~/Mail/ToReview",   // folder to watch | "." (project root) | "reports/" (subdir)
  "responses": "<root>/responses",  // where drafts are written (default: <root>/responses)
  "outbound":  "<root>/outbox"      // where the sweep stages approved drafts (default: <root>/outbox)
}
```

- **Live intake** — `setsweep-watch` (cron, ~15 min) scans `watch`, diffs against a per-project
  seen-set, and fires a curate agent for each new file: it drafts a response into `responses/`
  and files a queue entry (brief + a `source` field pointing at the incoming item). When `watch`
  is the project root or a subdir, intake ignores its own output (`responses/`, `outbound/`,
  `.setsweep/`).
- **Sweep routes outward** — approve is a bookmark; at sweep the approved drafts are **staged to
  `outbound/`** (a send-queue an external tool picks up). The sweep never transmits — staging
  only, per the localhost-only invariant. See `DESIGN.md` → "The inbox kit + live intake".

## Kit schema (`<kind>.json`)

| Field | Meaning |
|---|---|
| `name` | display name (e.g. "Writing") |
| `kind` | the project-kind this is the default for: `writing · code · records · knowledge · inbox` |
| `lens` | the review lens — what this curator looks for (injected into the review agent) |
| `urgency` | the high/medium/low rubric for this kind |
| `firstQueue` | founding heuristic — which documents to surface first |
| `interview` | kit-specific founding stems (merged with shared base stems: status, horizon, direction, fences, sweep_actions, fleet) |
| `sweepChecks` | self-check assertions appended to every sweep |
| `tools` | **extra** capabilities beyond the always-on builtins — empty in shipped defaults |

## The `tools` slot

`Read · Grep · Edit · Write · shell` are always granted (the builtins), so shipped kits ship with
`"tools": []`. The slot is where a *specific* project bolts on capability — typed entries, since
each wires differently at spawn:

```json
"tools": [
  {"type":"skill",  "ref":"notes"},                 // a Claude Code skill
  {"type":"mcp",    "ref":"arena-mcp"},              // an MCP server
  {"type":"rag",    "ref":"writing-style-rag"},      // a retrieval endpoint
  {"type":"corpus", "ref":"~/Seafile/Notes"}         // a reference dir made available to the agent
]
```

These are *personal* to a project and its owner — never hardcode them into a shipped default.

## Defaults vs. user kits

- **Shipped defaults** — the `<kind>.json` files here. Read-only baseline; sync via the repo.
- **User kits / edits** — live in `settings.kits` (local, like saved palettes). Editing a built-in
  **forks a copy** into the user layer; the shipped file stays pristine.
- **Resolution for a project:** explicit `kit` assignment → that kind's default → none (unset).
- **Import/export** — a kit is just JSON.
