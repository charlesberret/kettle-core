# Sitting judge

Versioned rubrics and headless scenario runs. The judge does not call a model
and does not read an API key. A runner command scores one scenario and prints JSON.

```sh
python -m tools.judge run \
  --rubric sitting \
  --scenarios founding-interview \
  --runner 'python my_runner.py {scenario}' \
  --parallel 4 \
  --out scores.json

python -m tools.judge verify scores.json --rubric sitting
```

## Rubric

`rubrics/<name>.md` opens with front matter (`version`, and `dimensions` in
score order). The hash covers the dimension list and the body after the
closing `---`: SHA-256 over `dimensions: ` plus the dimensions joined by commas
and a newline, followed by the normalised body.

Body normalisation:

- newlines become `\n`
- trailing whitespace is stripped on each line
- blank lines at the start and end of the body are dropped
- the hashed text ends with one newline

`version` is stored on every row and is not part of the hash. Edit the body or
add, drop, or reorder a dimension and `verify` rejects scores recorded under
the old hash.

`rubrics/sitting.md` is a template. It is full of `TODO(patron)` markers.

## Scenarios

`scenarios/<name>.yaml` is a list of scenarios. Each one has an `id` and a
`fixture` directory. `scenarios/template.yaml` is the placeholder.
`scenarios/founding-interview.yaml` is the founding set (empty folder, notes,
interrupted founding, re-found, and the other `kettle found` outcomes). The
fixtures are synthetic.

## Runner

`{scenario}` in `--runner` is replaced with the scenario id (after the command
is split, so the id stays one argument). The process starts in `tools/judge`.
Stdin is a JSON object with the scenario, the fixture path, and the rubric hash.
The environment also carries `JUDGE_SCENARIO`, `JUDGE_FIXTURE`, `JUDGE_RUBRIC`,
`JUDGE_RUBRIC_VERSION`, and `JUDGE_RUBRIC_SHA256`.

Stdout is one JSON object:

```json
{"scores": {"founding_sentence": 1}, "notes": "short prose"}
```

Score values are integers. A non-zero exit, a timeout, or stdout that is not
that object becomes an `error` row. The other scenarios still run. Rows are
written in scenario-file order, so `--parallel 4` matches `--parallel 1`.

`run_id` is the first 16 hex characters of SHA-256 over
`rubric_sha256`, a newline, and the scenario id. Identical inputs write
byte-identical `scores.json`.

## Verify

`verify` loads `schemas/scores.schema.json`, recomputes the rubric hash, and
fails when any row was recorded under a different body.
