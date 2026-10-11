# Tests

Stdlib-style unit tests for kettle-core. Run from the repo root:

```sh
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
.venv/bin/python -m pytest
```

| Module | Covers |
|--------|--------|
| `test_server.py` | HTTP routes, file fence, founding, streams (serial) |
| `test_cli.py` | CLI viewport (`cli.main`) |
| `test_runtime.py` | Curator adapter / usage / events |
| `test_lineage.py` | Edit attribution |
| `test_kits.py` | Kit load and prompts |
| `test_watch.py` | Folder-watch intake |
| `test_curator.py` | Provider settings / catalog |
| `test_egress.py` | Staged outbound |
| `test_frontend.py` | `static/index.html` script syntax gate |
| `test_ui_copy.py` | Shared UI copy keys |
| `test_contract.py` | Contract versions / family check |
| `test_palette.py` / `test_theme_catalog.py` | Theme packs |
| `test_syntax.py` | Highlighter + TUI buffer helpers |
| `test_kettle_main.py` | Entrypoint routing |
| `test_survey.py` / `test_sweepkit.py` | Survey + mechanical close |
| `test_gitmap.py` | Git/mtime activity heatmap (`kettle/gitmap.py`) |
| `test_judge.py` | Versioned sitting judge (`tools/judge`): hash, order, errors, schema |
| `test_migrate.py` | `kettle migrate` (`.setsweep/` → `.kettle/`, dry-run vs `--apply`) |

Some modules redirect `server` globals into a tempdir and must run **serially**
(the default `pytest` config does not use xdist).
