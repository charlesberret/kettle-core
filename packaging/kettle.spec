# PyInstaller spec for the standalone `kettle` binary.
#
# Build with tools/build-binary.sh, which installs the package into a throwaway
# venv first — the spec collects the *installed* package data so the binary can
# never disagree with the wheel about what ships.
#
# The binary is the whole product: `kettle` (CLI viewport), `kettle --web`
# (server), `kettle doctor`. server._app_dir() already resolves package data to
# sys._MEIPASS when frozen, so nothing in the runtime needs a packaging branch.

import os
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, copy_metadata

# static/ (sitting, fonts, themes) and kits/ (prompts, frameworks, skills) ship
# as package data in the wheel; take them from the same place, not from a repo path.
# collect_data_files keeps the package prefix (kettle/static/...). Flatten it to
# static/… and kits/… — the layout server._app_dir() looks for first when frozen —
# so the bundle matches the runtime contract instead of relying on a fallback.
datas = [
    (src, dest.split("kettle/", 1)[-1] if dest.startswith("kettle/") else dest)
    for src, dest in collect_data_files(
        "kettle", includes=["static/**", "kits/**", "projects.example.json"]
    )
]

# kettle.__version__ reads importlib.metadata, which needs the dist-info inside the
# bundle. Without it the binary reports version "unknown" in --version, /api/ping
# and doctor — the three places a support question starts.
datas += copy_metadata("kettle")

a = Analysis(
    [str(Path(SPECPATH).resolve() / "entry.py")],
    pathex=[],
    binaries=[],
    datas=datas,
    # The package is stdlib-only, but its submodules are reached through
    # kettle_main's lazy dispatch, so name them for the analyser.
    hiddenimports=[
        "kettle",
        "kettle.cli",
        "kettle.server",
        "kettle.runtime",
        "kettle.curator",
        "kettle.kits",
        "kettle.lineage",
        "kettle.sweepkit",
        "kettle.egress",
        "kettle.survey",
        "kettle.migrate",
        "kettle.gitmap",
        "kettle.syntax",
        "kettle.theme_catalog",
        "kettle.tui_editor",
        "kettle.kettle_contract",
        "kettle.kettle_watch",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # No GUI toolkits: the sitting is HTML served over loopback.
    excludes=["tkinter", "webview", "pywebview", "PIL", "numpy"],
    noarchive=False,
)

pyz = PYZ(a.pure)

# Two shapes, one spec. Default is a single file for `tools/build-binary.sh` (a
# stranger downloads one thing). kettle-desktop sets KETTLE_BUNDLE=onedir and
# bundles the directory as its sidecar: a sidecar launches on every app start, and
# onefile re-extracts itself to a temp dir each time.
ONEDIR = os.environ.get("KETTLE_BUNDLE", "onefile") == "onedir"
NAME = os.environ.get("KETTLE_BUNDLE_NAME", "kettle")

exe = EXE(
    pyz,
    a.scripts,
    [] if ONEDIR else a.binaries,
    [] if ONEDIR else a.datas,
    [],
    exclude_binaries=ONEDIR,
    name=NAME,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

if ONEDIR:
    coll = COLLECT(
        exe,
        a.binaries,
        a.datas,
        strip=False,
        upx=False,
        name=NAME,
    )
