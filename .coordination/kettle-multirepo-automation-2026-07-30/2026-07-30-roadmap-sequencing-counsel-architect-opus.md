# Counsel — roadmap-sequencing seat (architect-opus)

Speaking only from the sequencing lens: given two roadmaps and a mission to accelerate,
what order does the work actually go in, and what does automation get to touch first.

## Two roadmaps exist and they do not fully agree

**Public** — `kettle-core/ROADMAP.md` (100 lines, verified). "Now" = trustworthy public
alpha: package restructure, wheel/pipx in CI, `kettle doctor` expansion, Host/Origin
validation, per-boot auth token, `kettle migrate` (dry-run first), plus themes and the
CLI TUI editor.

**Private** — `kettle/.local/roadmap.md` (126 lines, verified). "Now" = core identity in
the family, CLI × Desk-chat signature craft, vscode dogfood, honest home docs.

The private roadmap's "Now" item 1 is *"Transplant or grow `kettle-core` from
`setsweep-core`"* — **already done** (80 commits, full package). Several of its framings
("setsweep CLI still OK", "when private or public is intentional") predate the current
state. The public ROADMAP is the fresher document.

Where they genuinely differ: the public roadmap leads with **installation and
security**; the private one leads with **signature craft** (CLI × Desk chat as one
muscle). Neither is wrong. But an automation plan that optimizes for the public
roadmap's "Now" builds CI and packaging machinery, while one that optimizes for the
private roadmap's "Now" builds nothing automated at all — signature craft is
taste-work, and taste does not parallelize.

**This is the sequencing question the sitting actually has to answer**, and I do not
think it is a strand's call to make alone. It is close to "what is Kettle for this
quarter," which is the patron's.

## The `agent-surfaces.md` constraint on any automation plan

The private canon states a **signature rule**: *"If you make the CLI better at X, ask
how the plugin agent chat gets X too — and the reverse,"* and marks single-surface
semantic changes as **incomplete** work. It also names a **shared spine** to implement
once in core: desk/queue semantics, curator session protocol, canonical copy, founding
state machine, contract versions.

This has a sharp implication for the charge. **Parallelizing agents across repos cuts
against the signature rule.** Three agents working three viewports in parallel is
precisely how you get a CLI that is better at something the Desk cannot express — the
named anti-pattern ("clever CLI flags that invent behavior the Desk can't express").
The canon says: fix the spine once in core; adapters stay thin.

So the honest sequencing answer is that the acceleration available here is **not**
"more agents on more repos at once." It is:
1. automate the *verification* layer so a core spine change is provably safe for all
   consumers (contract seat's green tier), then
2. change the spine confidently and often, with adapters following mechanically.

Automation buys **confidence velocity**, not parallel-repo throughput. I want that
distinction on the record because the charge's phrasing ("three smart agents…
collectively coordinating") could easily be read the other way.

## Proposed sequence

**Tranche 0 — reconcile the map (no code).** Fix `family.md`'s stale state column;
resolve the two stubs; decide the design-token owner (G6). Cheap, unblocks everything,
and is the only tranche this sitting can authorize on its own evidence.

**Tranche 1 — verification automation (green).** Cross-repo drift check in CI for
`ui-copy` + compatibility manifests; extend `kettle doctor`. Additive, no run-critical
file, matches public ROADMAP's "Now."

**Tranche 2 — spine work, human-driven, machine-checked.** Signature craft per
`agent-surfaces.md`, now safe to do fast because Tranche 1 catches consumer breakage.

**Not yet.** Cross-repo write automation; always-on jobs; anything in the five
run-critical files; MCP or CLI repo creation.

## Ballot from this seat

- **G4 — qualified**: substrate should be **in-repo and per-occasion** (this
  `.coordination/` dir), *not* the fleet Desk. The fleet `majordomo-inbox/` is for
  escalations above a lane; a product's design record belongs with the product. But see
  the open question of whether this directory is committed — that is a patron gate.
- **G5 — concur with qualification**: first tranche = Tranche 0 + Tranche 1 above.
- **Flag for the patron**: public-vs-private roadmap precedence is unresolved and I do
  not claim authority to resolve it.

## Wall from this seat

Do not let an automation plan quietly overwrite the signature rule. Any proposal that
has agents advancing CLI and Desk independently must be rejected as contrary to
`agent-surfaces.md` unless the patron explicitly retires that rule.
