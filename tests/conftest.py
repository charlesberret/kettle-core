"""Test-run setup shared by every module.

Fixtures `git init` throwaway repositories and commit to them. A developer's global
`init.templateDir` can install hooks into each new repository (one house template
aborts the first commit until a generated .gitignore is staged), which fails those
fixtures on that machine and nowhere else. An empty template directory for the run
keeps them the same everywhere. Kettle's own lineage git already runs with
`core.hooksPath=/dev/null`, so this concerns test setup only.
"""

import os
import tempfile
from pathlib import Path

import kettle
from kettle import runtime

os.environ["GIT_TEMPLATE_DIR"] = tempfile.mkdtemp(prefix="kettle-test-git-template-")

_ROOT = Path(__file__).resolve().parents[1]
_imported = Path(kettle.__file__).resolve()
if _ROOT not in _imported.parents:
    raise RuntimeError(
        f"tests imported kettle from {_imported}, not this tree {_ROOT}"
    )

# Gemini turns spawn from a per-project folder under ~/.cache/kettle (runtime.isolate_turn);
# a test run must not create those in the developer's home.
runtime.GEMINI_WORKSPACES = Path(tempfile.mkdtemp(prefix="kettle-test-gemini-ws-"))
