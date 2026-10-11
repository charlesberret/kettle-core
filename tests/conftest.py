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

os.environ["GIT_TEMPLATE_DIR"] = tempfile.mkdtemp(prefix="kettle-test-git-template-")
