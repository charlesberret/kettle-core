#!/usr/bin/env bash
# Build the standalone `kettle` binary and smoke-test it.
#
#   tools/build-binary.sh [outdir]
#
# Produces <outdir>/kettle (default: dist/). No Python needed on the machine that
# runs the result. PyInstaller is a build-time dependency only: the shipped
# package stays stdlib-only, which is why the build happens in a throwaway venv
# rather than in the developer's environment.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUTDIR="${1:-$ROOT/dist}"
BUILD_DIR="$(mktemp -d "${TMPDIR:-/tmp}/kettle-binary.XXXXXX")"
cleanup() { [[ -n "${SRV:-}" ]] && kill "$SRV" 2>/dev/null; rm -rf "$BUILD_DIR"; }
trap cleanup EXIT

PYTHON_BIN="${PYTHON:-python3}"
if ! "$PYTHON_BIN" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)'; then
  echo "error: need python >= 3.11 to build (found $("$PYTHON_BIN" -V 2>&1))" >&2
  exit 1
fi

echo "[build] venv: $BUILD_DIR/venv"
"$PYTHON_BIN" -m venv "$BUILD_DIR/venv"
VPY="$BUILD_DIR/venv/bin/python"
"$VPY" -m pip install -q -U pip
# Install the package itself (not editable): the spec collects data from the
# installed tree, so a file missing from the wheel is missing from the binary.
"$VPY" -m pip install -q "$ROOT"
"$VPY" -m pip install -q pyinstaller

VERSION="$("$VPY" -c 'from kettle import __version__; print(__version__)')"
echo "[build] kettle $VERSION"

"$VPY" -m PyInstaller \
  --clean --noconfirm \
  --distpath "$OUTDIR" \
  --workpath "$BUILD_DIR/work" \
  "$ROOT/packaging/kettle.spec"

BIN="$OUTDIR/kettle"
[[ -x "$BIN" ]] || { echo "error: no binary at $BIN" >&2; exit 1; }

echo "[smoke] $BIN"
"$BIN" --version
"$BIN" --help >/dev/null

# Run every smoke from a scratch HOME and a cwd with no kettle source in sight:
# the sitting and the kits must come from inside the binary.
SMOKE_HOME="$BUILD_DIR/home"
mkdir -p "$SMOKE_HOME"
cd "$BUILD_DIR"

HOME="$SMOKE_HOME" DESK_PROJECTS="$SMOKE_HOME/projects.json" \
  "$BIN" doctor >"$BUILD_DIR/doctor.txt" 2>&1 || true
grep -qi "kettle" "$BUILD_DIR/doctor.txt" || { echo "error: doctor produced nothing" >&2; exit 1; }

# Serve on an ephemeral port and check the sitting + identity beacon. Never 4242:
# that is the live window's port on a developer machine. Port and token come from
# the discovery record — the same contract every viewport uses — because stdout is
# block-buffered when it is not a tty, so parsing the banner is unreliable.
HOME="$SMOKE_HOME" DESK_PROJECTS="$SMOKE_HOME/projects.json" \
  "$BIN" --web --port 0 --no-open >"$BUILD_DIR/server.log" 2>&1 &
SRV=$!

DISCOVERY="$SMOKE_HOME/.cache/kettle/server.json"
for _ in $(seq 1 60); do
  [[ -s "$DISCOVERY" ]] && break
  sleep 0.2
done
[[ -s "$DISCOVERY" ]] || { echo "error: no discovery record after 12s"; cat "$BUILD_DIR/server.log"; exit 1; }

PORT="$("$VPY" -c 'import json,pathlib,sys; print(json.loads(pathlib.Path(sys.argv[1]).read_text())["port"])' "$DISCOVERY")"
TOKEN="$("$VPY" -c 'import json,pathlib,sys; print(json.loads(pathlib.Path(sys.argv[1]).read_text())["token"])' "$DISCOVERY")"
[[ "$PORT" != "4242" ]] || { echo "error: smoke bound the live window port"; exit 1; }

code="$(curl -s -o "$BUILD_DIR/ping.json" -w '%{http_code}' -H "X-Kettle-Token: $TOKEN" "http://127.0.0.1:$PORT/api/ping")"
[[ "$code" == "200" ]] || { echo "error: /api/ping returned $code"; cat "$BUILD_DIR/ping.json"; exit 1; }
grep -q '"app": *"kettle"' "$BUILD_DIR/ping.json" || { echo "error: ping is not kettle"; exit 1; }

root_code="$(curl -s -o "$BUILD_DIR/root.html" -w '%{http_code}' "http://127.0.0.1:$PORT/")"
[[ "$root_code" == "200" ]] || { echo "error: GET / returned $root_code"; exit 1; }
# The sitting is inside the binary, not read from a repo beside it.
grep -q "kettle-ui" "$BUILD_DIR/root.html" || { echo "error: served page is not the sitting"; exit 1; }

kill "$SRV" 2>/dev/null || true
SRV=""

SIZE="$(du -h "$BIN" | cut -f1 | tr -d ' ')"
SHA="$("$VPY" -c 'import hashlib,sys; print(hashlib.sha256(open(sys.argv[1],"rb").read()).hexdigest())' "$BIN")"
echo
echo "kettle $VERSION → $BIN ($SIZE)"
echo "sha256 $SHA"
