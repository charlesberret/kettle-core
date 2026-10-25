#!/usr/bin/env python3
"""Fail CI when an OSV advisory exists for a vendored JS build.

The sanitizer is the boundary between curator output and the sitting DOM, so a
known XSS in a vendored copy cannot wait for a human to re-query OSV. Versions
are read from the vendored file banners, which is the only place they cannot
drift from what ships:

- kettle/static/marked.min.js  — "marked v<ver>" in the leading comment
- kettle/static/purify.min.js  — "DOMPurify <ver>" in the license banner

Usage: check-vendored-osv.py [--root DIR] [--probe name@version ...]

--probe queries an arbitrary package@version instead of the tree (used by the
job's self-check to prove a vulnerable version actually fails).
Exit 0 = clean; exit 1 = advisories found or a version could not be read.
"""

import json
import re
import sys
import urllib.request
from pathlib import Path

OSV_URL = "https://api.osv.dev/v1/query"

# (npm package name, vendored file, banner regex)
VENDORED = [
    ("marked", "kettle/static/marked.min.js", r"marked v(\d+\.\d+\.\d+)"),
    ("dompurify", "kettle/static/purify.min.js", r"DOMPurify (\d+\.\d+\.\d+)"),
]


def query_osv(package: str, version: str) -> list[dict]:
    body = json.dumps(
        {"package": {"name": package, "ecosystem": "npm"}, "version": version}
    ).encode()
    req = urllib.request.Request(
        OSV_URL, data=body, headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read()).get("vulns", [])


def vendored_version(root: Path, rel: str, pattern: str) -> str:
    head = (root / rel).read_text(encoding="utf-8")[:1000]
    m = re.search(pattern, head)
    if not m:
        raise ValueError(f"{rel}: version not found in banner")
    return m.group(1)


def main() -> int:
    args = sys.argv[1:]
    pairs: list[tuple[str, str]] = []
    if "--probe" in args:
        i = args.index("--probe")
        pairs = [tuple(a.split("@", 1)) for a in args[i + 1 :]]
    else:
        root = Path(args[args.index("--root") + 1]) if "--root" in args else Path(__file__).resolve().parent.parent
        for package, rel, pattern in VENDORED:
            try:
                pairs.append((package, vendored_version(root, rel, pattern)))
            except (OSError, ValueError) as e:
                print(f"error: {e}", file=sys.stderr)
                return 1

    bad = False
    for package, version in pairs:
        vulns = query_osv(package, version)
        if vulns:
            bad = True
            ids = ", ".join(v["id"] for v in vulns)
            print(f"{package}@{version}: {len(vulns)} open advisories: {ids}")
        else:
            print(f"{package}@{version}: clean")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
