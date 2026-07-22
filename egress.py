"""Desk egress — durable staging of outward signals under `.setsweep/outbound/`.

Distinct from inbox kit mail staging (`<root>/outbox`). The desk writes Status: staged;
external pickup drains and routes. Never transmits from the desk process itself.
"""
from __future__ import annotations

import re
from datetime import date
from pathlib import Path
from typing import Any

import server

KINDS = frozenset({"handoff", "escalation", "launch", "domain", "approval"})

# Neutral product defaults. Personal fleet routes live in settings.egress.routes
# (see INSTALL / API — brief 10).
DEFAULT_ROUTES = {
    "handoff": "peers",
    "escalation": "escalation",
    "launch": "launch",
    "domain": "domain",
    "approval": "peers",
}
# Back-compat alias for older imports/tests
_DEFAULT_ROUTES = DEFAULT_ROUTES


def routes_for_settings(settings: dict | None = None) -> dict[str, str]:
    """Resolve kind → route hint: product defaults overlaid by settings.egress.routes."""
    routes = dict(DEFAULT_ROUTES)
    raw = settings if settings is not None else server.load_settings()
    block = raw.get("egress") if isinstance(raw, dict) else None
    custom = block.get("routes") if isinstance(block, dict) else None
    if isinstance(custom, dict):
        for kind, hint in custom.items():
            if kind in KINDS and isinstance(hint, str) and hint.strip():
                routes[kind] = hint.strip()
    return routes


def egress_dir(proj: dict) -> Path:
    return server.desk_dir(proj) / "outbound"


def _framework_text() -> str:
    path = server.APPDIR / "kits" / "frameworks" / "egress.md"
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError:
        return (
            "# Desk egress\n\n"
            "`.setsweep/outbound/` stages outward signals for external pickup. "
            "Not the inbox kit's `<root>/outbox` (mail drafts). "
            "Status: staged — never route or transmit from the desk.\n"
        )


def ensure_egress(proj: dict) -> Path:
    """Create `.setsweep/outbound/` and seed README.md from the egress framework if missing."""
    d = egress_dir(proj)
    d.mkdir(parents=True, exist_ok=True)
    readme = d / "README.md"
    if not readme.exists():
        server.atomic_write(readme, _framework_text() + "\n")
    return d


def _slug_topic(topic: str) -> str:
    s = re.sub(r"[^A-Za-z0-9._-]+", "-", (topic or "").strip().lower()).strip("-")
    return (s[:48] or "memo").rstrip("-")


def stage_egress(
    proj: dict,
    *,
    kind: str,
    topic: str,
    body: str,
    route: str | None = None,
    day: str | None = None,
) -> dict[str, Any]:
    """Write one staged egress memo. Returns {path, kind, topic, route}."""
    kind = str(kind or "").strip().lower()
    if kind not in KINDS:
        raise ValueError(f"kind must be one of {sorted(KINDS)}")
    topic = str(topic or "").strip()
    if not topic:
        raise ValueError("topic required")
    body = str(body or "").strip()
    if not body:
        raise ValueError("body required")
    route = (route or "").strip() or routes_for_settings()[kind]
    day = day or date.today().isoformat()
    ensure_egress(proj)
    fname = f"{day}-{kind}-{_slug_topic(topic)}.md"
    path = egress_dir(proj) / fname
    # Avoid clobber: if same-day same-slug exists, suffix -2, -3, …
    if path.exists():
        n = 2
        while True:
            alt = egress_dir(proj) / f"{day}-{kind}-{_slug_topic(topic)}-{n}.md"
            if not alt.exists():
                path = alt
                break
            n += 1
    pid = proj.get("id") or "desk"
    text = (
        f"# Egress: {topic}\n"
        f"**From:** setsweep/{pid} · **Date:** {day}\n"
        f"**Kind:** {kind}\n"
        f"**Route:** {route}\n"
        f"**Status:** staged\n"
        f"\n"
        f"{body.rstrip()}\n"
    )
    server.atomic_write(path, text)
    return {"path": str(path), "kind": kind, "topic": topic, "route": route, "status": "staged"}


def list_staged(proj: dict) -> list[dict[str, Any]]:
    """List staged egress memos (Status: staged). Skips README."""
    d = egress_dir(proj)
    if not d.is_dir():
        return []
    out: list[dict[str, Any]] = []
    for p in sorted(d.glob("*.md")):
        if p.name.upper() == "README.MD" or p.name == "README.md":
            continue
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        status = "unknown"
        kind = topic = route = None
        for line in text.splitlines()[:12]:
            if line.startswith("# Egress:"):
                topic = line[len("# Egress:"):].strip()
            elif line.startswith("**Kind:**"):
                kind = line.split(":**", 1)[-1].strip().strip("*").strip()
            elif line.startswith("**Route:**"):
                route = line.split(":**", 1)[-1].strip().strip("*").strip()
            elif line.startswith("**Status:**"):
                status = line.split(":**", 1)[-1].strip().strip("*").strip()
        if status != "staged":
            continue
        out.append({
            "path": str(p),
            "name": p.name,
            "kind": kind,
            "topic": topic,
            "route": route,
            "status": status,
        })
    return out


def status_for_prompt(proj: dict) -> str:
    """Compact block for sweep prompts."""
    ensure_egress(proj)
    staged = list_staged(proj)
    lines = [
        f"DESK EGRESS — stage outward signals under {egress_dir(proj)} "
        "(not inbox <root>/outbox). Prefer `setsweep egress`. Status stays staged; "
        "external pickup routes.",
        f"Currently staged: {len(staged)}",
    ]
    for row in staged[:12]:
        lines.append(f"  - {row['name']} ({row.get('kind')}) → {row.get('route')}")
    return "\n".join(lines)
