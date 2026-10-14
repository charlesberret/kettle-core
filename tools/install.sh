#!/usr/bin/env bash
# Install Kettle onto PATH from this public git repository.
#
#   tools/install.sh
#   curl -fsSL https://raw.githubusercontent.com/charlesberret/kettle-core/main/tools/install.sh | bash
#
# The name "kettle" on PyPI, Homebrew, and npm already belongs to other
# projects. This script installs the git URL and nothing from those indexes.
set -euo pipefail

URL="git+https://github.com/charlesberret/kettle-core.git"

if command -v uv >/dev/null 2>&1; then
  uv tool install --upgrade "$URL"
elif command -v pipx >/dev/null 2>&1; then
  pipx install --upgrade "$URL"
else
  cat >&2 <<EOF
Kettle installs with uv or pipx. Neither is on PATH.

Install uv from https://docs.astral.sh/uv/getting-started/installation/
and run this script again, or run:

  uv tool install --upgrade $URL

The name kettle on PyPI, Homebrew, and npm is a different project.
EOF
  exit 1
fi

echo "Next: kettle doctor"
