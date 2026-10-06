#!/usr/bin/env python3
"""Canonical sitting UI copy — defaults from package data, overlaid with user edits.

`static/ui-copy.json` is the one source for every viewport. This module is how a
viewport that is not JavaScript reads it (CLI viewport in-process; TUI over
`GET /api/ui-copy`), and how the sitting's debug mode writes a tweak back.

Two override kinds, and the difference matters:

* **keys** — a catalogued string. Overriding one reaches *every* viewport, because
  every viewport resolves the same key. This is the cross-platform contract.
* **selectors** — an element in the web sitting whose text is still hardcoded in
  `index.html`. Overriding one is local to the sitting: nothing else knows that
  element exists. It is a staging area, not a destination; `promote_plan()` turns
  one into a real key so it can join the contract.

A third section, **tokens**, holds CSS custom properties (`--pane-gap` and friends).
Those are size and placement, not copy — they live here because they are the same
concern (tweaks the user made to their own sitting, kept out of package data), and
the sitting applies them at boot from the same payload.

Nothing here writes to `static/`. Package data is read-only in a wheel and lives in
a vanishing temp dir inside the standalone binary, and `index.html` is run-critical
(CLAUDE.md). User edits land in `ui-copy-overrides.json` beside `settings.json`.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Callable

CATALOG_NAME = "ui-copy.json"
OVERRIDES_NAME = "sitting-overrides.json"

# A key is an identifier so it can be a property name in every viewport's language.
KEY_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]{0,79}$")
# Deliberately not "any CSS selector": a single id, optionally narrowed by nothing
# else. An override is a label change, not a licence to restyle the document, and a
# broad selector ("*", "body") would let one stray edit blank the whole sitting.
SELECTOR_RE = re.compile(r"^#[A-Za-z][A-Za-z0-9_-]{0,63}$")
# A CSS custom property name, nothing else: an override retunes a token the
# stylesheet already reads, it does not add declarations.
TOKEN_RE = re.compile(r"^--[a-z][a-z0-9-]{0,63}$")
# A token value must be inert. `;` or `}` would end the declaration and start a new
# one; url() would make the sitting fetch something; var() could recurse. None of
# those is needed to change a length, a color, or a font stack.
TOKEN_VALUE_BAD = re.compile(r"[;{}<>\\]|url\(|var\(|@import|expression\(", re.I)
MAX_TOKEN_VALUE = 120
# Attributes an override may set. All are rendered as text by the browser — none can
# execute, and none can move an element somewhere it was not already.
FIELDS = ("text", "short", "title", "placeholder", "aria-label")
MAX_TEXT = 2000
MAX_ENTRIES = 500


class CopyError(ValueError):
    """An override patch that must be refused (bad key, bad field, too long)."""


def catalog_path(static_dir: Path) -> Path:
    return Path(static_dir) / CATALOG_NAME


def load_catalog(static_dir: Path) -> dict:
    """Read the shipped catalog. A broken catalog is a packaging bug, not user input.

    Returns an empty catalog rather than raising: the sitting keeps the literal text
    baked into `index.html` as its fallback, so a missing catalog degrades to plain
    hardcoded copy instead of an unusable window.
    """
    try:
        raw = json.loads(catalog_path(static_dir).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"keys": {}}
    keys = raw.get("keys")
    if not isinstance(keys, dict):
        return {"keys": {}}
    out: dict[str, dict] = {}
    for k, v in keys.items():
        if not KEY_RE.match(str(k)):
            continue
        if isinstance(v, str):  # tolerate a flat {key: "text"} entry
            v = {"text": v}
        if isinstance(v, dict) and isinstance(v.get("text"), str):
            out[str(k)] = v
    states = raw.get("states")
    states = states if isinstance(states, dict) else {}
    return {"keys": out, "states": states, "_schema": raw.get("_schema", 1)}


def load_overrides(path: Path | None) -> dict:
    """Read user overrides. Corrupt or absent means "no overrides", never an error."""
    empty: dict[str, dict] = {"keys": {}, "selectors": {}, "tokens": {}}
    if not path:
        return empty
    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8") or "{}")
    except (OSError, ValueError):
        return empty
    if not isinstance(raw, dict):
        return empty
    keys = raw.get("keys") if isinstance(raw.get("keys"), dict) else {}
    sels = raw.get("selectors") if isinstance(raw.get("selectors"), dict) else {}
    toks = raw.get("tokens") if isinstance(raw.get("tokens"), dict) else {}
    return {
        "keys": {k: v for k, v in keys.items() if KEY_RE.match(str(k)) and isinstance(v, dict)},
        "selectors": {
            s: v for s, v in sels.items() if SELECTOR_RE.match(str(s)) and isinstance(v, dict)
        },
        "tokens": {
            t: v
            for t, v in toks.items()
            if TOKEN_RE.match(str(t))
            and isinstance(v, str)
            and len(v) <= MAX_TOKEN_VALUE
            and not TOKEN_VALUE_BAD.search(v)
        },
    }


def payload(static_dir: Path, overrides_path: Path | None = None) -> dict:
    """The merged catalog every viewport consumes.

    `keys` carries the effective strings. `overridden` names which keys the user has
    changed, so a viewport (and the debug badge) can say "this is your edit, not
    ours" without diffing against package data it may not be able to read.
    """
    catalog = load_catalog(static_dir)
    over = load_overrides(overrides_path)
    keys: dict[str, dict] = {}
    for k, v in catalog["keys"].items():
        keys[k] = dict(v)
    for k, v in over["keys"].items():
        base = keys.setdefault(k, {"note": "user-defined key (not in the shipped catalog)"})
        for field in ("text", "short"):
            if isinstance(v.get(field), str):
                base[field] = v[field]
    return {
        "_schema": catalog.get("_schema", 1),
        "keys": keys,
        # One message per flow state, in three registers. Not overridable yet: a
        # state message is the contract between viewports, so retyping one is a
        # catalog edit, not a per-install tweak.
        "states": catalog.get("states", {}),
        "selectors": over["selectors"],
        "tokens": over["tokens"],
        "overridden": sorted(over["keys"]),
    }


def text(pay: dict, key: str, short: bool = False, default: str = "") -> str:
    """Resolve one string. `short=True` prefers the terse variant, then the full text.

    A narrow surface asks for `short`; it must never get a *different instruction*
    than the wide surface, only fewer words — which is a rule about what goes in the
    catalog, enforced by review, not by this function.
    """
    rec = (pay.get("keys") or {}).get(key)
    if not isinstance(rec, dict):
        return default
    if short:
        s = rec.get("short")
        if isinstance(s, str) and s:
            return s
    t = rec.get("text")
    return t if isinstance(t, str) and t else default


def state_text(pay: dict, state: str, register: str = "full", default: str = "") -> str:
    """The message for a flow state, in the register a surface affords.

    `line` for a status bar, `short` for one sentence, `full` for a guide. A missing
    register falls back to the longest one present rather than to nothing: a narrow
    surface showing too many words beats a surface showing none.
    """
    rec = (pay.get("states") or {}).get(state)
    if not isinstance(rec, dict):
        return default
    v = rec.get(register)
    if isinstance(v, str) and v:
        return v
    for alt in ("full", "short", "line"):
        v = rec.get(alt)
        if isinstance(v, str) and v:
            return v
    return default


def validate_patch(patch: Any) -> dict:
    """Check an override patch from the sitting before it reaches disk.

    Refuses rather than sanitizes: a rejected edit the user can see and retype beats
    a silently mangled one they discover in the UI three days later.
    """
    if not isinstance(patch, dict):
        raise CopyError("patch must be an object")
    out: dict[str, Any] = {"keys": {}, "selectors": {}, "tokens": {}}
    tokens = patch.get("tokens", {})
    if tokens:
        if not isinstance(tokens, dict):
            raise CopyError("tokens must be an object")
        for name, value in tokens.items():
            if not TOKEN_RE.match(str(name)):
                raise CopyError(f"not a CSS custom property: {name!r}")
            if value is None:
                out["tokens"][str(name)] = None
                continue
            if not isinstance(value, str):
                raise CopyError(f"{name!r} must be a string")
            if len(value) > MAX_TOKEN_VALUE:
                raise CopyError(f"{name!r} exceeds {MAX_TOKEN_VALUE} characters")
            if TOKEN_VALUE_BAD.search(value):
                raise CopyError(
                    f"{name!r}: a token value may not contain ; {{ }} url() or var()"
                )
            out["tokens"][str(name)] = value
    for kind, pattern in (("keys", KEY_RE), ("selectors", SELECTOR_RE)):
        section = patch.get(kind, {})
        if section in (None, {}):
            continue
        if not isinstance(section, dict):
            raise CopyError(f"{kind} must be an object")
        for name, fields in section.items():
            if not pattern.match(str(name)):
                raise CopyError(f"invalid {kind[:-1]} name: {name!r}")
            if fields is None:  # an explicit null clears this override
                out[kind][str(name)] = None
                continue
            if not isinstance(fields, dict):
                raise CopyError(f"{name!r} must map fields to strings")
            clean: dict[str, str] = {}
            for field, value in fields.items():
                if field not in FIELDS:
                    raise CopyError(f"{name!r}: unknown field {field!r}")
                if kind == "keys" and field not in ("text", "short"):
                    raise CopyError(
                        f"{name!r}: {field!r} is a web-element attribute; "
                        "catalog keys carry text/short only"
                    )
                if not isinstance(value, str):
                    raise CopyError(f"{name!r}.{field} must be a string")
                if len(value) > MAX_TEXT:
                    raise CopyError(f"{name!r}.{field} exceeds {MAX_TEXT} characters")
                clean[field] = value
            out[kind][str(name)] = clean
    if not out["keys"] and not out["selectors"] and not out["tokens"]:
        raise CopyError("patch changes nothing")
    return out


def apply_patch(current: dict, patch: dict) -> dict:
    """Merge a validated patch into the overrides document (field-level merge).

    A `None` entry removes that override entirely — the way back to the shipped
    string, which must always be one action away.
    """
    merged = {
        "keys": dict(current.get("keys") or {}),
        "selectors": dict(current.get("selectors") or {}),
        "tokens": dict(current.get("tokens") or {}),
    }
    for name, value in (patch.get("tokens") or {}).items():
        if value is None or value == "":
            merged["tokens"].pop(name, None)
        else:
            merged["tokens"][name] = value
    for kind in ("keys", "selectors"):
        for name, fields in (patch.get(kind) or {}).items():
            if fields is None:
                merged[kind].pop(name, None)
                continue
            entry = dict(merged[kind].get(name) or {})
            for field, value in fields.items():
                if value == "":  # empty string clears one field, keeping the others
                    entry.pop(field, None)
                else:
                    entry[field] = value
            if entry:
                merged[kind][name] = entry
            else:
                merged[kind].pop(name, None)
    total = len(merged["keys"]) + len(merged["selectors"]) + len(merged["tokens"])
    if total > MAX_ENTRIES:
        raise CopyError(f"too many overrides ({total} > {MAX_ENTRIES})")
    return merged


def write_overrides(path: Path, doc: dict, writer: Callable[[Path, str], None]) -> dict:
    """Persist overrides through the caller's atomic writer (server owns the fence)."""
    body = {
        "_note": (
            "Your tweaks to this sitting, written by its UI debug mode. `keys` are "
            "catalog strings and reach every viewport; `selectors` relabel one element "
            "of the web sitting and stay local until promoted; `tokens` retune CSS "
            "custom properties the stylesheet already reads. Delete an entry — or the "
            "whole file — to go back to the shipped sitting."
        ),
        "keys": doc.get("keys") or {},
        "selectors": doc.get("selectors") or {},
        "tokens": doc.get("tokens") or {},
    }
    writer(Path(path), json.dumps(body, indent=2, ensure_ascii=False) + "\n")
    return body


def promote_plan(static_dir: Path, overrides_path: Path | None = None) -> dict:
    """What it would take to fold the current overrides into the shipped catalog.

    Key overrides are ready to land — they name a key that already exists, so the
    change is a one-line edit to `ui-copy.json` that every viewport picks up.
    Selector overrides are not: the string they change is still hardcoded in
    `index.html`, so promoting one means minting a key, tagging the element, and
    moving the text. This returns that work as data rather than guessing at it, so an
    agent can carry it out and a reviewer can see the whole cost first.
    """
    catalog = load_catalog(static_dir)
    over = load_overrides(overrides_path)
    ready, needs_key = [], []
    for key, fields in sorted(over["keys"].items()):
        shipped = catalog["keys"].get(key) or {}
        ready.append(
            {
                "key": key,
                "from": {f: shipped.get(f, "") for f in ("text", "short") if f in fields},
                "to": {f: v for f, v in fields.items() if f in ("text", "short")},
                "known": key in catalog["keys"],
            }
        )
    for sel, fields in sorted(over["selectors"].items()):
        needs_key.append(
            {
                "selector": sel,
                "to": dict(fields),
                "work": (
                    f"mint a catalog key for {sel}, tag the element with data-uic "
                    "(or data-uic-title/-ph/-aria), and move the literal text out of "
                    "index.html into ui-copy.json"
                ),
            }
        )
    return {
        "catalog": str(catalog_path(static_dir)),
        "ready": ready,
        "needs_key": needs_key,
        # Tokens are not copy and have no catalog to land in: promoting one means
        # changing its default in index.html's :root (or the theme pack it comes
        # from), which is a design decision, not a string edit.
        "tokens": [
            {"token": t, "to": v, "work": "change the default on :root in index.html"}
            for t, v in sorted(over["tokens"].items())
        ],
    }


def _js_literal(obj: Any) -> str:
    """JSON safe to paste inside a <script> element."""
    return (
        json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace(" ", "\\u2028")
        .replace(" ", "\\u2029")
    )


def render_js(pay: dict) -> str:
    """The `/ui-copy.js` shim, rendered from the catalog at request time.

    Rendering beats committing a generated file: there is no second artifact to fall
    out of step with `ui-copy.json`. `KETTLE_UI_COPY` stays a flat key→text map, the
    shape the sitting and the VS Code snapshot already expect.
    """
    keys = pay.get("keys") or {}
    flat = {k: v.get("text", "") for k, v in keys.items()}
    meta = {
        k: {f: v[f] for f in ("short", "note") if isinstance(v.get(f), str)}
        for k, v in keys.items()
    }
    return (
        "/* GENERATED at request time from static/ui-copy.json — do not edit, and do\n"
        "   not commit a copy of this. Edit the JSON. See docs/UI.md. */\n"
        "(function (root) {\n"
        '  "use strict";\n'
        f"  root.KETTLE_UI_COPY = {_js_literal(flat)};\n"
        f"  root.KETTLE_UI_COPY_META = {_js_literal(meta)};\n"
        f"  root.KETTLE_UI_COPY_SELECTORS = {_js_literal(pay.get('selectors') or {})};\n"
        f"  root.KETTLE_UI_COPY_OVERRIDDEN = {_js_literal(pay.get('overridden') or [])};\n"
        f"  root.KETTLE_UI_TOKENS = {_js_literal(pay.get('tokens') or {})};\n"
        f"  root.KETTLE_UI_STATES = {_js_literal(pay.get('states') or {})};\n"
        "  if (typeof module !== \"undefined\" && module.exports) module.exports = root.KETTLE_UI_COPY;\n"
        '})(typeof globalThis !== "undefined" ? globalThis : this);\n'
    )
