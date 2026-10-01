#!/usr/bin/env python3
"""Render docs/LEXICON.md from kettle/kits/lexicon.json.

The JSON is canonical; this file is the human projection, the same arrangement
kettle-palette.json / kettle-design-tokens.md already uses — except generated, so
the two cannot disagree. `--check` fails when the committed doc is stale.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "kettle" / "kits" / "_lexicon.json"
OUT = ROOT / "docs" / "LEXICON.md"

KIND_ORDER = ["concept", "role", "document", "control", "viewport"]
KIND_HED = {
    "concept": "Concepts",
    "role": "Roles",
    "document": "Documents",
    "control": "Controls",
    "viewport": "Viewports",
}


def render(doc: dict) -> str:
    terms = doc["terms"]
    out = [
        "# Kettle lexicon",
        "",
        "**Generated from `kettle/kits/_lexicon.json` — do not edit by hand.**",
        "Regenerate with `tools/render-lexicon-doc.py`; `--check` runs in CI.",
        "",
        "One place a Kettle term is defined and spelled. `tools/lint-lexicon.py` fails on a",
        "violation in the prompt corpus or the copy catalog, and warns elsewhere.",
        "",
        "## Casing",
        "",
    ]
    for k, v in doc["_casing"].items():
        out.append(f"- **`{k}`** — {v}")
    out += [
        "",
        "## Fields",
        "",
    ]
    for k, v in doc["_fields"].items():
        out.append(f"- **`{k}`** — {v}")
    out.append("")

    for kind in KIND_ORDER:
        group = [t for t in terms if t["kind"] == kind]
        if not group:
            continue
        out += [f"## {KIND_HED[kind]}", ""]
        for t in sorted(group, key=lambda x: x["term"].lower()):
            out.append(f"### {t['term']}")
            out.append("")
            out.append(t["gloss"])
            out.append("")
            bits = [f"casing: `{t['casing']}`"]
            if t.get("artifact"):
                bits.append(f"file: `{t['artifact']}`")
            if t.get("lint_case") is False:
                bits.append("not case-checked")
            out.append("*" + " · ".join(bits) + "*")
            out.append("")
            if t.get("avoid"):
                out.append("Wrong spellings (these fail the linter):")
                out.append("")
                for b in t["avoid"]:
                    out.append(f"- `{b['form']}` — {b['why']}")
                out.append("")
            if t.get("retired"):
                out.append("Retired — must not come back (these fail the linter):")
                out.append("")
                for b in t["retired"]:
                    out.append(f"- `{b['form']}` — {b['why']}")
                out.append("")
            if t.get("not_synonyms"):
                out.append("Not a synonym for this term:")
                out.append("")
                for b in t["not_synonyms"]:
                    out.append(f"- `{b['form']}` — {b['why']}")
                out.append("")
    return "\n".join(out).rstrip() + "\n"


def main() -> int:
    body = render(json.loads(SRC.read_text(encoding="utf-8")))
    if "--check" in sys.argv:
        current = OUT.read_text(encoding="utf-8") if OUT.exists() else ""
        if current != body:
            print("docs/LEXICON.md is stale — run tools/render-lexicon-doc.py", file=sys.stderr)
            return 1
        print("docs/LEXICON.md up to date")
        return 0
    OUT.write_text(body, encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)} ({len(json.loads(SRC.read_text())['terms'])} terms)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
