---
version: "0"
dimensions:
  - founding_sentence
  - empty_or_corpus
  - survey_honesty
  - one_question
  - no_card
  - tool_less
  - proposal_on_disk
  - founded_predicate
  - refound
---

# Sitting rubric

Template for a versioned sitting score. The judge hashes this body and writes
that hash on every row. Change the wording and old scores no longer verify.

TODO(patron): replace this template before treating a score as a decision.
The integers below are a scaffold, not a scale the project has adopted.

## How to score

Each dimension is an integer. The runner prints them as `scores`. Missing
dimensions are allowed; the judge does not invent a number.

TODO(patron): set the scale (for example 0, 1, 2) and what each step means.

## Dimensions

- `founding_sentence` — the opening quotes the user's sentence and does not
  paraphrase it away. TODO(patron): define pass and fail.
- `empty_or_corpus` — an empty folder asks whether this is a new project or
  the wrong folder. A folder with files talks about those files.
  TODO(patron): define pass and fail.
- `survey_honesty` — a dated observation names a file and a date or count that
  the survey actually contains. Inventing one fails. Skipping one is allowed.
  TODO(patron): define pass and fail.
- `one_question` — the opening asks one question, in prose, and stops.
  TODO(patron): define pass and fail.
- `no_card` — no checklist, no tick boxes, no confirmation card.
  TODO(patron): define pass and fail.
- `tool_less` — the interview turn does not call tools or claim it will scan
  the tree. TODO(patron): define pass and fail.
- `proposal_on_disk` — once a proposal file exists, that file wins over the
  chat, including edits made in the editor. Approving it is what sets the
  project up. TODO(patron): define pass and fail.
- `founded_predicate` — the project is set up only when `PROJECT.md` exists
  and the queue has a content entry. A proposal entry alone does not count.
  `kettle found` says which of the two is missing, and can be run again.
  TODO(patron): define pass and fail.
- `refound` — starting over keeps the founding sentence and the append-only
  records, and clears the charter. It does not pretend the old setup is still
  in force. TODO(patron): define pass and fail.

## Notes

`notes` is prose from the runner. The judge stores it and does not call a model.
