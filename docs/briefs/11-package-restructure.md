---
id: 11
title: Package restructure + version
repo: setsweep-core
touches: [pyproject.toml, all *.py (moves), server.py APPDIR, setsweep_main.py, INSTALL.md]
risk: run-critical
depends-on: [01, 04]
status: open
---

## Context

Install is editable-only by construction: `APPDIR` resolves file-relative
(`_app_dir()` at server.py:~50 — `Path(__file__).resolve().parent` in dev, the
PyInstaller `_MEIPASS` dir when frozen), so `static/` and `kits/` load from the source
tree, and the
sdist/wheel contain only `.py` files (SOURCES.txt shows no static/, kits/, or
projects.example.json) — so `pip install setsweep` from a wheel yields a server that
404s its own frontend. Ten generic top-level module names (`server`, `cli`, `runtime`,
`kits`…) will collide in any shared environment. Version `0.2.0` exists only in
pyproject: no `__version__`, nothing in `/api/ping`, no tags — a desktop sidecar and a
newer core cannot even detect skew. The PyPI name `setsweep` was verified unclaimed
(404 on pypi.org/simple/setsweep/) as of 2026-07-17. The build floor is under-pinned:
PEP 639 `license = "MIT"` needs setuptools>=77, pyproject requires >=61.

## Task

1. Restructure under `setsweep/`: the ten modules move in (`setsweep/server.py`, …),
   `static/` and `kits/` become package data, `projects.example.json` ships. Replace
   `APPDIR` file-relative resolution with `importlib.resources` (files() API). Console
   scripts (`setsweep`, `setsweep-watch`) keep their names.
2. Single-source the version: `setsweep.__version__` via `importlib.metadata`, surfaced
   in `/api/ping` (a `version` field), `setsweep --help`, and the desktop sidecar's
   version.json flow.
3. Pin `setuptools>=77`; verify `requires-python >= 3.11` actually passes at 3.11 (CI
   matrix in brief 14 enforces it thereafter).
4. Reserve the PyPI name **first and separately**: a minimal 0.0.1 placeholder upload
   (name, README pointer, no code claims) — cheap insurance, do it before the
   restructure lands.
5. Editable install keeps working from the repo root (contributor path is sacred).

## Constraints

- This collides with every open edit to core — land at a quiet moment after brief 01,
  as one large mechanical commit (moves) plus small focused commits (resource loading).
- `test_server.py`'s global-redirect fixture will need path updates; budget for it.
- Do not rename modules while moving them (import churn only, no identity churn).

## Done when

- In a clean venv on a machine-like tempdir: `pip install dist/*.whl` then
  `setsweep --web --port 0`-equivalent boots, `GET /` serves the app, `/api/kits` lists
  five kinds, `/api/ping` reports the version.
- `pipx install <wheel>` works; editable install still works; full suite green both ways.

## Verify

The wheel-install smoke above, scripted (it becomes CI's packaging job in brief 14);
`python3 -c "import setsweep; print(setsweep.__version__)"`.

## Afterwards

`status: done`; INSTALL.md rewritten for both paths; brief 15 (desktop) picks up the
version field; brief 13 documents it in the ping shape.
