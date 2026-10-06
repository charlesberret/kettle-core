#!/usr/bin/env python3
"""Check Kettle's text against its controlled vocabulary.

    tools/lint-lexicon.py [--all] [--json] [paths...]

The lexicon (`kettle/kits/_lexicon.json`) says how each product term is spelled. This
checks the places that text reaches a user and reports where they disagree.

Severity follows who reads the text:

  error   kettle/kits/**            the prompt corpus — an LLM mirrors the casing it
                                    is shown, so drift here becomes drift in every
                                    brief, ask and proposal the curator writes
  error   static/ui-copy.json       the copy catalog's `text` and `short` values —
                                    read verbatim by every viewport
  warn    everything else           docs, READMEs, catalog `note` fields: read by a
                                    person who can shrug

Four checks:

  house-word    a house term on a surface a user reads. The check that matters most:
                a user should not need a glossary to use Kettle, and the catalog is
                the one place that is enforceable. The fix names the plain word.
  avoid-form    a spelling the lexicon explicitly rejects, with the reason
  retired-form  a label or name that was replaced and must not come back
  wrong-case    a Title Case term (a document or a named control) written some
                other way — "desk proposal" where "Desk Proposal" is meant
  stray-capital a common noun capitalised mid-sentence — "the Sweep finished"

Exemptions matter more than the checks. Code spans, fenced blocks, file paths,
URLs, identifiers and a term's own artifact filename (DESK-PROPOSAL.md) are all
skipped, because a linter that cries about `kettle/kits/_base.md` is a linter
people turn off.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LEXICON = ROOT / "kettle" / "kits" / "_lexicon.json"
CATALOG = ROOT / "kettle" / "static" / "ui-copy.json"
# Violations that exist today and have not been fixed yet. They are errors — they
# are listed so CI can block *new* drift without the first commit having to rewrite
# copy nobody has reviewed. Shrink this file; never grow it. An entry that no longer
# matches anything is itself reported, so a fix cannot leave a stale exemption.
BASELINE = ROOT / "kettle" / "kits" / "_lexicon-baseline.json"

# Text the user reads verbatim, or that shapes what the curator writes.
ERROR_GLOBS = ("kettle/kits/**/*.md", "kettle/kits/*.json")
WARN_GLOBS = ("docs/**/*.md", "*.md")
SKIP_PARTS = {".git", "node_modules", "__pycache__", ".venv", "dist", "build", ".local"}

FENCE = re.compile(r"^\s*(```|~~~)")
# Words Title Case leaves lowercase, so "Sweep the Desk?" still reads as a hed.
SMALL_WORDS = {"a", "an", "and", "as", "at", "but", "by", "for", "from", "in", "nor",
               "of", "on", "or", "the", "to", "with"}
# Spans a term may legitimately sit inside without obeying prose rules.
MASKS = (
    re.compile(r"`[^`]*`"),                       # inline code
    re.compile(r"https?://\S+"),                  # urls
    re.compile(r"\[[^\]]*\]\([^)]*\)"),           # md link targets
    re.compile(r"\b[\w.-]+/[\w./-]+"),            # paths
    re.compile(r"\b[A-Z][A-Z0-9-]*\.(md|json|log|jsonl|py|html)\b"),  # artifact filenames
    re.compile(r"\b\w+_\w+\b"),                   # snake_case identifiers
    re.compile(r"<[^>]+>"),                       # html tags
)


def mask(line: str) -> str:
    """Blank out spans where product-prose rules do not apply, keeping offsets."""
    out = line
    for pat in MASKS:
        out = pat.sub(lambda m: "\0" * len(m.group(0)), out)
    return out


def load_lexicon(path: Path = LEXICON) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))["terms"]


def _sentence_start(masked: str, idx: int) -> bool:
    """True when idx begins a sentence, a heading, or a list/table cell.

    A lowercase common noun is correctly capitalised in those positions, so this is
    what keeps `stray-capital` from flagging ordinary English.
    """
    before = masked[:idx]
    stripped = before.strip()
    if not stripped:
        return True
    if before.lstrip().startswith(("#", ">", "-", "*", "|")) and not stripped.rstrip().endswith(","):
        # heading, quote, bullet or table cell whose text starts here
        if re.fullmatch(r"[\s#>*\-|\d.]*", before):
            return True
    return bool(re.search(r"[.!?:;·—]\s+$|^\s*[\d]+\.\s+$|\*\*$|\|\s*$", before))


def is_hed(text: str) -> bool:
    """True when the whole string is Title Case, so every capital in it is correct.

    docs/UI.md puts titles, heds and subheds in Title Case, which makes a common noun
    legitimately capitalised there — "Sweep the Desk?" is a hed, not a stray capital.
    The catalog does not record a string's role, so this reads the casing instead.
    """
    words = re.findall(r"[A-Za-z][\w'’-]*", text)
    significant = [w for i, w in enumerate(words) if i == 0 or w.lower() not in SMALL_WORDS]
    if len(significant) < 2:
        return False
    return all(w[0].isupper() for w in significant)


def _title_spans(masked: str, terms: list[dict]) -> list[tuple[int, int]]:
    """Character ranges covered by a multi-word Title Case term.

    "Desk" inside "Desk Proposal" or "Found Desk" is that term's capital, not a
    stray one. Without this the common-noun check flags every correct use of a
    control name that contains a common noun — which was 38 of the first run's
    findings.
    """
    spans = []
    for t in terms:
        if t["casing"] not in ("title", "sentence"):
            continue
        for m in re.finditer(re.escape(t["term"]), masked, re.I):
            spans.append((m.start(), m.end()))
    return spans


def check_text(text: str, terms: list[dict], *, where: str, line_no: int) -> list[dict]:
    findings = []
    masked = mask(text)
    protected = _title_spans(masked, terms)
    hed = is_hed(text)

    def covered(i: int, j: int) -> bool:
        return any(a <= i and j <= b for a, b in protected)

    for t in terms:
        term, casing = t["term"], t["casing"]

        for check_name, key in (("avoid-form", "avoid"), ("retired-form", "retired")):
            for bad in t.get(key, []):
                form = bad["form"]
                # Whole words only. Without the boundaries, retiring `curator` also
                # flags `curatorial` and `curated` — 94 false warnings on the first
                # run of the rename, and the kind of noise that gets a linter turned
                # off. A form ending in punctuation (`finish ✓`) still works: \w only
                # guards an alphanumeric neighbour.
                for m in re.finditer(r"(?<!\w)" + re.escape(form) + r"(?!\w)", masked):
                    findings.append({
                        "check": check_name, "where": where, "line": line_no,
                        "term": term, "found": form, "why": bad["why"],
                        "fix": f"use {term!r}",
                    })

        if casing in ("title", "sentence"):
            # A single-word control (Sweep, Approve, Comment) shares its spelling with
            # the concept, so case cannot decide which was meant. Documented in the
            # lexicon, not enforced here.
            if t.get("lint_case") is False:
                continue
            for m in re.finditer(re.escape(term), masked, re.I):
                got = masked[m.start():m.end()]
                if got == term or "\0" in got or got.isupper():
                    continue
                findings.append({
                    "check": "wrong-case", "where": where, "line": line_no,
                    "term": term, "found": got,
                    "why": f"{t['kind']} name — Title Case, mid-sentence included",
                    "fix": f"use {term!r}",
                })
        else:
            cap = term[0].upper() + term[1:]
            for m in re.finditer(r"(?<![\w-])" + re.escape(cap) + r"(?![\w-])", masked):
                if "\0" in masked[m.start():m.end()]:
                    continue
                if hed or covered(m.start(), m.end()) or _sentence_start(masked, m.start()):
                    continue
                findings.append({
                    "check": "stray-capital", "where": where, "line": line_no,
                    "term": term, "found": cap,
                    "why": f"{t['kind']} — a common noun; lowercase in prose",
                    "fix": f"use {term!r}",
                })
    return findings


def check_markdown(path: Path, terms: list[dict], rel: str) -> list[dict]:
    findings, in_fence = [], False
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if FENCE.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        findings += check_text(line, terms, where=rel, line_no=i)
    return findings


HOUSE_SKIP = re.compile(r"`[^`]*`")


def check_house_words(text: str, terms: list[dict], *, where: str) -> list[dict]:
    """Flag a house term on a surface a user reads.

    This is the inversion that matters. The first version of this linter enforced
    that we spell our own vocabulary consistently — which protected the vocabulary
    and did nothing for the person trying to use the product. A user should not have
    to learn what a "desk" or a "sitting" is; those words are precise for us and
    opaque to them. So on user-facing surfaces the rule is not "spell it our way",
    it is "do not make them learn it".
    """
    masked = HOUSE_SKIP.sub(lambda m: "\0" * len(m.group(0)), text)
    out = []
    for t in terms:
        if t.get("audience") != "house" or t.get("lint_house") is False:
            continue
        word = t["term"]
        pat = re.compile(r"(?<![\w-])" + re.escape(word) + r"(?:s|es|ing)?(?![\w-])", re.I)
        for m in pat.finditer(masked):
            if "\0" in masked[m.start():m.end()]:
                continue
            plain = t.get("plain")
            out.append({
                "check": "house-word", "where": where, "line": 0, "term": word,
                "found": masked[m.start():m.end()],
                "why": "house word — a user should not have to learn it",
                "fix": f"say {plain!r}" if plain else "internal term; it has no place on screen",
            })
    return out


def check_catalog(path: Path, terms: list[dict], rel: str) -> list[dict]:
    """Catalog values are read verbatim; notes are developer prose."""
    findings = []
    doc = json.loads(path.read_text(encoding="utf-8"))
    for key, rec in (doc.get("keys") or {}).items():
        for field in ("text", "short"):
            v = rec.get(field)
            if isinstance(v, str) and v:
                w = f"{rel}:{key}.{field}"
                for f in check_text(v, terms, where=w, line_no=0) + \
                        check_house_words(v, terms, where=w):
                    f["severity_hint"] = "error"
                    findings.append(f)
        note = rec.get("note")
        if isinstance(note, str) and note:
            # developer prose: spelling is checked, house words are welcome
            for f in check_text(note, terms, where=f"{rel}:{key}.note", line_no=0):
                f["severity_hint"] = "warn"
                findings.append(f)
    for state, rec in (doc.get("states") or {}).items():
        if not isinstance(rec, dict):
            continue
        for field in ("line", "short", "full"):
            v = rec.get(field)
            if isinstance(v, str) and v:
                w = f"{rel}:states.{state}.{field}"
                for f in check_text(v, terms, where=w, line_no=0) + \
                        check_house_words(v, terms, where=w):
                    f["severity_hint"] = "error"
                    findings.append(f)
    return findings


def fingerprint(f: dict) -> str:
    """Identity of a violation, stable across line moves within a file."""
    return f"{f['where']}|{f['check']}|{f['found']}"


def load_baseline() -> dict[str, str]:
    if not BASELINE.exists():
        return {}
    doc = json.loads(BASELINE.read_text(encoding="utf-8"))
    return {e["id"]: e.get("why", "") for e in doc.get("known", [])}


def iter_files(globs, explicit):
    if explicit:
        for p in explicit:
            yield Path(p)
        return
    for g in globs:
        for p in sorted(ROOT.glob(g)):
            if not set(p.parts) & SKIP_PARTS and p.is_file():
                yield p


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("paths", nargs="*", help="files to check (default: the standard set)")
    ap.add_argument("--all", action="store_true", help="treat warnings as errors too")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    ap.add_argument("--update-baseline", action="store_true",
                    help="record the current errors as the accepted baseline")
    ap.add_argument("--show-baseline", action="store_true",
                    help="list the accepted violations instead of hiding them")
    args = ap.parse_args()

    terms = load_lexicon()
    findings = []

    explicit = [Path(p) for p in args.paths]
    if explicit:
        for p in explicit:
            rel = str(p.relative_to(ROOT)) if p.is_absolute() else str(p)
            fs = check_catalog(p, terms, rel) if p.name == "ui-copy.json" else check_markdown(p, terms, rel)
            for f in fs:
                f.setdefault("severity_hint", "error")
            findings += fs
    else:
        for p in iter_files(ERROR_GLOBS, None):
            if p.name.startswith("_lexicon"):
                continue
            rel = str(p.relative_to(ROOT))
            fs = check_markdown(p, terms, rel) if p.suffix == ".md" else []
            for f in fs:
                f["severity_hint"] = "error"
            findings += fs
        if CATALOG.exists():
            findings += check_catalog(CATALOG, terms, str(CATALOG.relative_to(ROOT)))
        for p in iter_files(WARN_GLOBS, None):
            rel = str(p.relative_to(ROOT))
            for f in check_markdown(p, terms, rel):
                f["severity_hint"] = "warn"
                findings.append(f)

    errors = [f for f in findings if f.get("severity_hint") == "error"]
    warns = [f for f in findings if f.get("severity_hint") != "error"]

    baseline = load_baseline()
    if args.update_baseline:
        BASELINE.write_text(json.dumps({
            "_note": ("Known lexicon violations, accepted for now so CI can block new "
                      "drift. Shrink this list; never grow it. Regenerate with "
                      "tools/lint-lexicon.py --update-baseline after fixing some."),
            "known": [{"id": fingerprint(f), "fix": f["fix"]} for f in sorted(
                errors, key=fingerprint)],
        }, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"baseline written: {len(errors)} known violation(s)")
        return 0

    seen = {fingerprint(f) for f in errors}
    stale = sorted(set(baseline) - seen)
    baselined = [f for f in errors if fingerprint(f) in baseline]
    errors = [f for f in errors if fingerprint(f) not in baseline]

    if args.json:
        print(json.dumps({"errors": errors, "warnings": warns,
                          "baselined": baselined, "stale_baseline": stale}, indent=2))
    else:
        for label, group in (("error", errors), ("warn", warns)):
            if not group:
                continue
            print(f"\n{'=' * 70}\n{len(group)} {label}{'s' if len(group) != 1 else ''}\n{'=' * 70}")
            for f in group:
                loc = f"{f['where']}:{f['line']}" if f["line"] else f["where"]
                print(f"  {loc}\n    {f['check']}: {f['found']!r} — {f['why']}\n    fix: {f['fix']}")
    if args.show_baseline and baselined and not args.json:
        print(f"\n{'=' * 70}\n{len(baselined)} accepted (baseline)\n{'=' * 70}")
        for f in baselined:
            loc = f"{f['where']}:{f['line']}" if f["line"] else f["where"]
            print(f"  {loc}\n    {f['check']}: {f['found']!r}\n    fix: {f['fix']}")
    if stale and not args.json:
        one = len(stale) == 1
        print(f"\n{len(stale)} baseline entr{'y' if one else 'ies'} no longer "
              f"{'matches' if one else 'match'} anything — rerun with --update-baseline:")
        for sid in stale:
            print(f"  {sid}")
    if not args.json:
        print(f"\n{len(errors)} new error(s), {len(baselined)} accepted, "
              f"{len(warns)} warning(s)")
    return 1 if (errors or stale or (args.all and warns)) else 0


if __name__ == "__main__":
    sys.exit(main())
