"""Host-neutral theme catalog for web, desktop, and the CLI editor.

Bundled packs live under ``static/themes/``. User packs load from the
platform themes directory (``user_themes_dir()``). The marquee default is
always ``kettle``.
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1
DEFAULT_THEME_ID = "kettle"

# Roles used by sittings and the CLI highlighter.
IFACE_KEYS = (
    "bg", "fg", "muted", "panel", "panel2", "line", "acc", "link",
    "activebg", "selection", "good", "warn", "urghigh", "urgmed", "urglow",
)
SLOT_KEYS = (
    "mdhead", "ctxhead", "ctxbody", "cmthead", "comment", "agent", "user",
)
# Text roles that must resolve to ink (not paper) under the paper-in-0 / ink-in-7 convention.
TEXT_SLOT_KEYS = ("ctxhead", "ctxbody", "cmthead", "agent")
# Preset solid % for interface/text roles (matches static/themes.js).
DEFAULT_IFACE_OPACITY_DARK = {"panel": 92, "panel2": 96, "activebg": 84, "muted": 58}
DEFAULT_IFACE_OPACITY_LIGHT = {"panel": 96, "panel2": 100, "activebg": 92, "muted": 52}
DEFAULT_SLOT_OPACITY_DARK = {"agent": 58}
DEFAULT_SLOT_OPACITY_LIGHT = {"agent": 48}
# Syntax token kinds → preferred iface/slot or fixed ANSI index name.
SYNTAX_ROLE_DEFAULTS = {
    "text": "fg",
    "comment": "comment",       # slot, else muted
    "string": "good",
    "number": "acc",
    "keyword": "link",
    "storage": "link",
    "function": "link",
    "type": "acc",
    "constant": "warn",
    "operator": "muted",
    "punctuation": "muted",
    "property": "link",
    "heading": "mdhead",
    "escape": "link",
    "invalid": "warn",
    "lineno": "muted",
    "status": "muted",
}


def appdir() -> Path:
    """Package data root that contains ``static/`` (same tree as server.APPDIR)."""
    here = Path(__file__).resolve().parent
    if (here / "static" / "themes").is_dir():
        return here
    # Editable / unusual layouts: walk common fallbacks.
    for candidate in (here, Path.cwd()):
        if (candidate / "static" / "themes").is_dir():
            return candidate
    return here


def bundled_themes_dir() -> Path:
    return appdir() / "static" / "themes"


def user_themes_dir() -> Path:
    """Writable directory for custom theme packs."""
    if env := os.environ.get("KETTLE_THEMES_DIR"):
        return Path(env).expanduser()
    if sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support" / "Kettle" / "themes"
    elif sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", Path.home())) / "Kettle" / "themes"
    else:
        xdg = os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config"))
        base = Path(xdg) / "kettle" / "themes"
    return base


def _read_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as fp:
        data = json.load(fp)
    if not isinstance(data, dict):
        raise ValueError(f"{path}: theme pack must be a JSON object")
    return data


def _validate_mode(mode: dict[str, Any], *, path: Path, which: str) -> None:
    ansi = mode.get("ansi")
    if not isinstance(ansi, list) or len(ansi) != 16:
        raise ValueError(f"{path}: {which}.ansi must be 16 hex colors")
    for i, hexv in enumerate(ansi):
        if not isinstance(hexv, str) or not hexv.startswith("#") or len(hexv) != 7:
            raise ValueError(f"{path}: {which}.ansi[{i}] must be #RRGGBB")
    for section in ("iface", "slots"):
        block = mode.get(section) or {}
        if not isinstance(block, dict):
            raise ValueError(f"{path}: {which}.{section} must be an object")
        for key, idx in block.items():
            if not isinstance(idx, int) or not 0 <= idx <= 15:
                raise ValueError(f"{path}: {which}.{section}.{key} must be 0–15")


def validate_pack(data: dict[str, Any], *, path: Path | None = None) -> dict[str, Any]:
    loc = path or Path("<pack>")
    if int(data.get("schema_version", -1)) != SCHEMA_VERSION:
        raise ValueError(f"{loc}: unsupported schema_version")
    if not data.get("id") or not data.get("label"):
        raise ValueError(f"{loc}: id and label are required")
    for which in ("dark", "light"):
        if which not in data:
            raise ValueError(f"{loc}: missing {which}")
        _validate_mode(data[which], path=loc, which=which)
    return data


def load_pack_file(path: Path) -> dict[str, Any]:
    return validate_pack(_read_json(path), path=path)


def list_theme_ids() -> list[str]:
    """Bundled ids first (catalog order), then user ids not already bundled."""
    bundled: list[str] = []
    index_path = bundled_themes_dir() / "index.json"
    if index_path.is_file():
        try:
            index = _read_json(index_path)
            bundled = list(index.get("themes") or [])
        except (OSError, ValueError, json.JSONDecodeError):
            bundled = []
    if not bundled:
        bundled = sorted(
            p.stem for p in bundled_themes_dir().glob("*.json") if p.name != "index.json"
        )
    user: list[str] = []
    udir = user_themes_dir()
    if udir.is_dir():
        user = sorted(
            p.stem for p in udir.glob("*.json")
            if p.stem not in bundled and p.name != "index.json"
        )
    return bundled + user


def resolve_theme_path(theme_id: str) -> Path | None:
    tid = (theme_id or "").strip() or DEFAULT_THEME_ID
    user = user_themes_dir() / f"{tid}.json"
    if user.is_file():
        return user
    bundled = bundled_themes_dir() / f"{tid}.json"
    if bundled.is_file():
        return bundled
    return None


def load_theme(theme_id: str | None = None) -> dict[str, Any]:
    tid = (theme_id or "").strip() or DEFAULT_THEME_ID
    path = resolve_theme_path(tid)
    if path is None:
        if tid != DEFAULT_THEME_ID:
            return load_theme(DEFAULT_THEME_ID)
        raise FileNotFoundError(
            f"theme {tid!r} not found in {bundled_themes_dir()} or {user_themes_dir()}"
        )
    pack = load_pack_file(path)
    pack.setdefault("id", tid)
    pack["_path"] = str(path)
    try:
        pack["_source"] = (
            "user" if path.resolve().is_relative_to(user_themes_dir().resolve()) else "bundled"
        )
    except (OSError, ValueError):
        pack["_source"] = "bundled"
    return pack


def default_theme_id() -> str:
    index_path = bundled_themes_dir() / "index.json"
    if index_path.is_file():
        try:
            return str(_read_json(index_path).get("default") or DEFAULT_THEME_ID)
        except (OSError, ValueError, json.JSONDecodeError):
            pass
    return DEFAULT_THEME_ID


def active_theme_id_from_settings(settings: dict[str, Any] | None) -> str:
    """Pick theme id from kettle settings.json-shaped dict."""
    if not settings:
        return default_theme_id()
    tid = settings.get("builtinTheme") or settings.get("theme") or default_theme_id()
    return str(tid)


def mode_block(pack: dict[str, Any], *, dark: bool = True) -> dict[str, Any]:
    return pack["dark" if dark else "light"]


def ansi_colors(pack: dict[str, Any], *, dark: bool = True) -> list[str]:
    return list(mode_block(pack, dark=dark)["ansi"])


def resolve_role_hex(
    pack: dict[str, Any],
    role: str,
    *,
    dark: bool = True,
) -> str:
    """Resolve an iface role, slot, or syntax role name to #RRGGBB."""
    block = mode_block(pack, dark=dark)
    ansi = block["ansi"]
    iface = block.get("iface") or {}
    slots = block.get("slots") or {}

    if role in iface:
        return ansi[int(iface[role])]
    if role in slots:
        return ansi[int(slots[role])]

    # Syntax aliases
    mapped = SYNTAX_ROLE_DEFAULTS.get(role, "fg")
    if mapped in iface:
        return ansi[int(iface[mapped])]
    if mapped in slots:
        return ansi[int(slots[mapped])]
    if mapped == "fg":
        return ansi[int(iface.get("fg", 7))]
    if mapped == "muted":
        return ansi[int(iface.get("muted", iface.get("fg", 7)))]
    return ansi[int(iface.get("fg", 7))]


def syntax_color_table(pack: dict[str, Any], *, dark: bool = True) -> dict[str, str]:
    """Map syntax token kinds → hex for highlighters / VS Code projectors."""
    return {kind: resolve_role_hex(pack, kind, dark=dark) for kind in SYNTAX_ROLE_DEFAULTS}


def pack_to_web(pack: dict[str, Any]) -> dict[str, Any]:
    """Convert a pack to the shape expected by ``static/themes.js`` / the sitting UI.

    ``dark`` / ``light`` each expose ``colors`` (``--ansi-N`` → hex), ``iface`` and
    ``slots`` (role → ``--ansi-N``), matching the browser applyTheme() path.
    Missing opacities fall back to the sitting defaults (themes.js IFACE_/SLOT_OPACITY_*).
    """

    def mode(block: dict[str, Any], *, which: str) -> dict[str, Any]:
        ansi = list(block["ansi"])
        colors = {f"--ansi-{i}": ansi[i] for i in range(16)}
        iface = {
            str(k): f"--ansi-{int(v)}"
            for k, v in (block.get("iface") or {}).items()
        }
        slots = {
            str(k): f"--ansi-{int(v)}"
            for k, v in (block.get("slots") or {}).items()
        }
        if which == "light":
            iface_op = dict(DEFAULT_IFACE_OPACITY_LIGHT)
            slot_op = dict(DEFAULT_SLOT_OPACITY_LIGHT)
        else:
            iface_op = dict(DEFAULT_IFACE_OPACITY_DARK)
            slot_op = dict(DEFAULT_SLOT_OPACITY_DARK)
        iface_op.update(block.get("ifaceOpacity") or {})
        slot_op.update(block.get("slotOpacity") or {})
        return {
            "colors": colors,
            "iface": iface,
            "slots": slots,
            "ifaceOpacity": iface_op,
            "slotOpacity": slot_op,
        }

    return {
        "id": pack.get("id"),
        "label": pack.get("label"),
        "marquee": bool(pack.get("marquee")),
        "source": pack.get("_source", "bundled"),
        "dark": mode(pack["dark"], which="dark"),
        "light": mode(pack["light"], which="light"),
    }


def install_user_pack(data: dict[str, Any]) -> dict[str, Any]:
    """Validate and write a theme pack into the user themes directory.

    Returns the loaded pack (with ``_path`` / ``_source``). Refuses to overwrite
    a bundled id that is not already shadowed by a user file *unless* the
    payload id matches — user packs may intentionally override bundled ids.
    """
    if not isinstance(data, dict):
        raise ValueError("theme pack must be a JSON object")
    pack = validate_pack(dict(data))
    tid = str(pack["id"]).strip()
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}", tid):
        raise ValueError("theme id must be 1–64 chars [A-Za-z0-9._-]")
    pack["id"] = tid
    # Never write internal keys
    clean = {k: v for k, v in pack.items() if not str(k).startswith("_")}
    udir = user_themes_dir()
    udir.mkdir(parents=True, exist_ok=True)
    path = udir / f"{tid}.json"
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(clean, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)
    return load_theme(tid)


def catalog_payload(*, full: bool = False) -> dict[str, Any]:
    """JSON for ``GET /api/themes`` (and ``?full=1`` including web-shaped packs)."""
    themes_meta = []
    packs: dict[str, Any] = {}
    for tid in list_theme_ids():
        try:
            pack = load_theme(tid)
        except (OSError, ValueError, FileNotFoundError):
            continue
        themes_meta.append({
            "id": pack.get("id") or tid,
            "label": pack.get("label") or tid,
            "marquee": bool(pack.get("marquee")),
            "source": pack.get("_source", "bundled"),
        })
        if full:
            packs[tid] = pack_to_web(pack)
    out: dict[str, Any] = {
        "default": default_theme_id(),
        "user_dir": str(user_themes_dir()),
        "themes": themes_meta,
    }
    if full:
        out["packs"] = packs
    return out


def prefer_dark_mode() -> bool:
    """Best-effort system appearance; default dark (marquee sitting)."""
    if env := os.environ.get("KETTLE_THEME_MODE"):
        return env.strip().lower() not in {"light", "day"}
    if sys.platform == "darwin":
        try:
            import subprocess
            out = subprocess.run(
                ["defaults", "read", "-g", "AppleInterfaceStyle"],
                capture_output=True, text=True, timeout=1,
            )
            return "dark" in (out.stdout or "").lower() or out.returncode != 0
        except (OSError, subprocess.SubprocessError):
            return True
    return True
