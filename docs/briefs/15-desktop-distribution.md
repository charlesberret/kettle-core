---
id: 15
title: Desktop distribution
repo: setsweep-desktop
touches: [package.json, forge config, scripts/, .github/workflows (new), main.js, setsweep-sidecar.spec]
risk: normal
depends-on: [01, 11]
status: open
---

## Context

The Electron shell is deliberate and small (sidecar pattern: spawn the PyInstaller-frozen
core, verify `/api/ping`, load the web app in a hardened BrowserWindow), but distribution
does not exist: no code signing or notarization (`osxSign:false` — a stranger's download
hits Gatekeeper's wall, and `install-app.sh`'s quarantine-strip only exists on the
builder's machine); no updater; zip-only maker while maker-dmg sits installed but
unwired; no CI — the currently installed app was built from a **dirty** core tree
(version.json `setsweepDirty:true`), so bug reports may match no commit; the app is
317 MB with the 20 MB sidecar bundled **twice** (packagerConfig.ignore misses
`^/resources`); `setsweep-sidecar.spec` hiddenimports lists only server/runtime/lineage/
kits — `curator`, `sweepkit`, `egress` bundle today by bytecode-scan luck, and core's
habit of lazy function-level imports makes that luck expire silently; sidecar crash
mid-session shows a dialog and quits, costing the patron their window; darwin-arm64
only; Info.plist ships Electron boilerplate (NSAllowsArbitraryLoads, camera/mic usage
strings for features that don't exist).

## Task

1. **Sign + notarize:** Developer ID cert (the one external prerequisite), osxSign +
   osxNotarize in packagerConfig; wire maker-dmg.
2. **CI:** GitHub Actions on tags — build sidecar, refuse to stamp when
   `setsweepDirty:true` or when core isn't at a named ref, package, sign, notarize,
   attach DMG to a GitHub Release.
3. **Updater:** update-electron-app against GitHub Releases (only meaningful after
   signing).
4. **Bundle hygiene:** add `^/resources($|/)`, README/scripts/spec exclusions to ignore;
   enable asar; expect ~20 MB + dev-file savings (loadVersionInfo already falls back to
   process.resourcesPath, so nothing breaks).
5. **Sidecar robustness:** sync hiddenimports with core's actual module list; extend
   smoke-sidecar.js to hit one curator-touching endpoint so frozen-import gaps fail at
   build; replace dialog-and-quit with restart-with-backoff (2-3 attempts, then the
   dialog).
6. **First-run honesty:** detect the configured curator CLI at launch; if absent, a
   friendly panel explaining what to install — the app's central feature must not fail
   mysteriously.
7. **Plist cleanup**; version from core's `/api/ping` (brief 11) displayed in About,
   skew-warned when shell and sidecar diverge.

## Constraints

- The port-4242-preferred behavior stays (the VS Code plugin attaches to it); never two
  desks on one registry without UI indication — surface the fallback-port case in the
  window title.
- The monkey-patched @electron/packager extract (scripts/patch-electron-extract.js) is
  the pipeline's most fragile link: test whether current forge/packager versions still
  hang; if fixed upstream, delete the patch in this brief.

## Done when

- A machine that has never seen the project downloads the Release DMG, drags to
  Applications, launches, and reaches the three-pane view (or the curator-missing
  panel) with zero terminal commands.
- CI refuses a dirty-tree build (test by inducing one); the DMG passes
  `spctl --assess`; auto-update from N-1 to N works once two releases exist.

## Verify

The stranger-machine test above on a clean macOS account; `codesign --verify --deep`;
smoke-sidecar green in CI logs.

## Afterwards

`status: done`; desktop `_Status.md` + README updated with the release flow; RELEASE.md
alpha gate's install-path box ticks.
