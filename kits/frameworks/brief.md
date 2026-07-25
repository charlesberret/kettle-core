# Brief framework

Use when writing or rewriting a queue entry `brief` (founding, restock, hand-file).
Also shapes the one-line `ask` field.

## Who the brief is for

The user may have been deep in another project for weeks, or may have **vibe-coded** this
tree and never carefully read the file. The brief must work for both: a clear, unassuming
introduction to **what this file is** and **what they are being asked to do**, with no
assumption that they remember internal codenames, round numbers, or prior memos.

It appears the instant the file loads — **before** any chat reply — so it must stand alone.

## Three jobs (in order of priority)

1. **Orient** — what kind of document is this, in plain language?
2. **Refresh** — what situation does it sit in (one short beat of context, no insider slang)?
3. **Invite** — what decision or read is wanted from them (gentle, specific, undemanding)?

The `ask` field is the shortest form of job 3 (one line). The `brief` field does 1–3.

## Shape (required)

**Movement 1 — lead sentence (plain English only)**  
One sentence a smart non-specialist could use cold:

- Prefer: *what the file is* + *why it is in front of them*.  
- Example good: “This memo records open product choices that must be settled before the
  data formats for the exchange are locked; read it and accept, adjust, or reject the
  proposal.”  
- Example bad: “Round 2 founder decision memo on D10 partially-open model before schema freeze.”

**Movement 2 — 1–3 short sentences of scaffolding (still plain)**  
Only what helps them open the file without decoding:

- What section or decision to look at first (by plain name, not code).  
- What “done” looks like in everyday words (approve / send back / note a change).  
- Spell out every acronym or code the **first** time it appears; if a code is not needed
  to act, **omit it** from the brief (it lives in the file).

Do **not** restate movement 1 in fancier words. Do **not** pack a design review into the brief.

**Length:** 2–4 sentences total. Prefer shorter.

## Anti-patterns (reject these)

| Anti-pattern | Why it fails | Instead |
|--------------|--------------|---------|
| Bare codes (`D10`, `EDTF L1`, `GREASE`) without expansion | Cold reader cannot act | Expand once, or drop from brief |
| Insider phase labels (“Round 2 research”) as the subject | Assumes memory of process | “Earlier research proposed…; this memo asks you to decide…” |
| Stacked noun phrases / clipped memo voice | High cognitive load | Full ordinary sentences |
| Demanding tone (“must decide X or send pieces back”) | Undermines undemanding re-entry | “You can accept the proposal as-is, change specific parts, or reject it.” |
| Agent procedure (“check file X first”) | Brief is for the human | Put cross-refs into `ask` only if the human needs them |
| Jargon that the file itself defines | Brief becomes a second paper | Point at the idea in English; leave the paper to define terms |

## Worked rewrite

**Bad (insider):**  
“This is the founder decision memo from Round 2 research: what must be true before the
exchange schemas freeze. Decide whether to accept the proposed D10 partially-open model
(reserved x_ fields, producer/consumer schema split, version major/minor, criticality,
GREASE) and EDTF Level 1 for temporal fields, or send specific pieces back. These changes
touch the digest-covered surface and cannot be slipped in later without breaking
byte-identity rebuilds.”

**Good (cold re-entry):**  
“This memo lists product choices that need your say before the shared data formats for
the exchange are locked in. Read the recommended approach for how open or closed those
formats should be, and how dates should be written; you can accept the recommendation,
change parts of it, or send it back. Settling this now matters because later format
changes would break rebuilds that depend on exact file identity.”

**Matching ask (one line):**  
“Accept, adjust, or reject the recommended format rules before they are frozen.”

## Constraints

- Plain English first; technical detail only after a human can already act.  
- Spell out abbreviations on first use; prefer zero bare codes in the brief.  
- No procedural agent tails.  
- Prefer `FAMILIARITY.md` for structure you already know; do not re-derive the corpus map
  in every brief.  
- Never make the user decode shorthand to learn why the file is in front of them.
