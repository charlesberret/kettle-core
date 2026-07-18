"""
Pluggable curator backends for Setsweep.

The desk owns prompts, tool allowlists, NDJSON event shapes, and the session ledger.
A curator *provider* only supplies the executable (and stream dialect) that runs a
turn. Claude Code CLI remains the default. First-class alternatives are agentic CLIs
— never raw chat-completions HTTP:

  claude  → Claude Code (`claude`)
  grok    → Grok Build CLI (`grok`)
  chatgpt → OpenAI Codex CLI (`codex exec`)
  gemini  → Google Gemini CLI (`gemini`)
  cli     → custom stream-json-compatible binary

Auth stays ambient (CLI login / env keys) — never stored in settings.json.

settings.json shape (preferred):

  {
    "curator": {
      "provider": "claude",   # claude | grok | chatgpt | gemini | cli
      "command": "claude",    # executable name or absolute path
      "models": {
        "setup": "sonnet",
        "chat": "sonnet",
              },
      "menu": {
        "claude": ["sonnet", "opus", "haiku"]
      }
    }
  }

`menu.<provider>` = ordered model ids shown in the desk model selector.
Missing menu is seeded (Claude sonnet/opus/haiku only) — not "show everything".

Legacy (still read): top-level "model" and "agents": {setup, chat}. Glance task was removed.
"""
from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

DEFAULT_MODELS = {
    "setup": "sonnet",
    "chat": "sonnet",
}

DEFAULT_MODELS_GROK = {
    "setup": "grok-4.5",
    "chat": "grok-4.5",
}

DEFAULT_MODELS_CHATGPT = {
    "setup": "gpt-5.1",
    "chat": "gpt-5.1",
}

DEFAULT_MODELS_GEMINI = {
    "setup": "gemini-2.5-pro",
    "chat": "gemini-2.5-pro",
}

DEFAULT_COMMAND = {
    "claude": "claude",
    "grok": "grok",
    "chatgpt": "codex",
    "gemini": "gemini",
    "cli": "claude",
}

KNOWN_PROVIDERS = frozenset({"claude", "grok", "chatgpt", "gemini", "cli"})
PROVIDER_ORDER = ("claude", "grok", "chatgpt", "gemini", "cli")

# Labels for Admin / ping diagnostics
STREAM_LABEL = {
    "claude": "stream-json",
    "cli": "stream-json",
    "grok": "streaming-json",
    "chatgpt": "codex-json",
    "gemini": "stream-json",
}

AUTH_HINT = {
    "claude": None,
    "cli": None,
    "grok": "XAI_API_KEY",
    "chatgpt": "OPENAI_API_KEY",
    "gemini": "GEMINI_API_KEY",
}

PROVIDER_LABEL = {
    "claude": "Claude Code",
    "grok": "Grok Build CLI",
    "chatgpt": "ChatGPT / Codex",
    "gemini": "Gemini CLI",
    "cli": "Custom CLI",
}

PROVIDER_HINT = {
    "claude": "Ambient auth: Claude login / ANTHROPIC_API_KEY",
    "grok": "Needs grok on PATH · XAI_API_KEY or Grok login",
    "chatgpt": "Needs codex on PATH · ChatGPT login / OPENAI_API_KEY",
    "gemini": "Needs gemini on PATH · GEMINI_API_KEY or Gemini login",
    "cli": "Any binary that speaks Claude-compatible stream-json",
}

# Desk menu checkmarks — seeded on first ensure (not the full catalog).
DEFAULT_MENU: dict[str, list[str]] = {
    "claude": ["sonnet", "opus", "haiku"],
}

# Canonical model catalog (single source of truth for UIs).
CATALOG_MODELS: list[dict[str, Any]] = [
    {"id": "sonnet", "provider": "claude", "label": "Sonnet",
     "blurb": "Balanced default for chat and sweeps.",
     "good_for": ["setup", "chat"], "effort_supported": True},
    {"id": "opus", "provider": "claude", "label": "Opus",
     "blurb": "Heavier reasoning for founding and hard sweeps.",
     "good_for": ["setup", "chat"], "effort_supported": True},
    {"id": "haiku", "provider": "claude", "label": "Haiku",
     "blurb": "Fast and cheap — light turns.",
     "good_for": ["chat"], "effort_supported": True},
    {"id": "fable", "provider": "claude", "label": "Fable",
     "blurb": "Optional Claude family id — enable after you confirm it works.",
     "good_for": ["chat"], "effort_supported": True},
    {"id": "grok-4.5", "provider": "grok", "label": "Grok 4.5",
     "blurb": "Primary Grok Build CLI model.",
     "good_for": ["setup", "chat"], "effort_supported": True},
    {"id": "grok-composer-2.5-fast", "provider": "grok", "label": "Composer 2.5 fast",
     "blurb": "Faster Grok for light turns.",
     "good_for": ["chat"], "effort_supported": True},
    {"id": "gpt-5.1", "provider": "chatgpt", "label": "GPT-5.1",
     "blurb": "Primary Codex / ChatGPT model.",
     "good_for": ["setup", "chat"], "effort_supported": True},
    {"id": "gpt-5-mini", "provider": "chatgpt", "label": "GPT-5 mini",
     "blurb": "Cheaper Codex model for light turns.",
     "good_for": ["chat"], "effort_supported": True},
    {"id": "o3", "provider": "chatgpt", "label": "o3",
     "blurb": "Reasoning-oriented Codex model.",
     "good_for": ["setup", "chat"], "effort_supported": True},
    {"id": "o4-mini", "provider": "chatgpt", "label": "o4-mini",
     "blurb": "Smaller reasoning Codex model.",
     "good_for": ["chat"], "effort_supported": True},
    {"id": "gemini-2.5-pro", "provider": "gemini", "label": "Gemini 2.5 Pro",
     "blurb": "Primary Gemini CLI model.",
     "good_for": ["setup", "chat"], "effort_supported": False},
    {"id": "gemini-2.5-flash", "provider": "gemini", "label": "Gemini 2.5 Flash",
     "blurb": "Fast Gemini for light turns.",
     "good_for": ["chat"], "effort_supported": False},
    {"id": "gemini-2.0-flash", "provider": "gemini", "label": "Gemini 2.0 Flash",
     "blurb": "Earlier Gemini flash id.",
     "good_for": ["chat"], "effort_supported": False},
    # Custom CLI mirrors Claude family ids (stream-json compatible).
    {"id": "sonnet", "provider": "cli", "label": "Sonnet",
     "blurb": "Pass-through model id for a custom stream-json CLI.",
     "good_for": ["setup", "chat"], "effort_supported": True},
    {"id": "opus", "provider": "cli", "label": "Opus",
     "blurb": "Pass-through model id for a custom stream-json CLI.",
     "good_for": ["setup", "chat"], "effort_supported": True},
    {"id": "haiku", "provider": "cli", "label": "Haiku",
     "blurb": "Pass-through model id for a custom stream-json CLI.",
     "good_for": ["chat"], "effort_supported": True},
    {"id": "fable", "provider": "cli", "label": "Fable",
     "blurb": "Pass-through model id for a custom stream-json CLI.",
     "good_for": ["chat"], "effort_supported": True},
]

EFFORT_BY_PROVIDER: dict[str, list[dict[str, str]]] = {
    "claude": [
        {"id": "low", "label": "low"},
        {"id": "medium", "label": "medium"},
        {"id": "high", "label": "high"},
        {"id": "xhigh", "label": "xhigh (extra)"},
        {"id": "max", "label": "max"},
    ],
    "cli": [
        {"id": "low", "label": "low"},
        {"id": "medium", "label": "medium"},
        {"id": "high", "label": "high"},
        {"id": "xhigh", "label": "xhigh"},
        {"id": "max", "label": "max"},
    ],
    "grok": [
        {"id": "low", "label": "low"},
        {"id": "medium", "label": "medium"},
        {"id": "high", "label": "high"},
        {"id": "xhigh", "label": "xhigh"},
    ],
    "chatgpt": [
        {"id": "low", "label": "low"},
        {"id": "medium", "label": "medium"},
        {"id": "high", "label": "high"},
        {"id": "xhigh", "label": "xhigh"},
        {"id": "max", "label": "max"},
        {"id": "ultra", "label": "ultra"},
    ],
    "gemini": [],
}

# Commands that are provider defaults — safe to swap on provider switch
DEFAULT_COMMAND_VALUES = frozenset(DEFAULT_COMMAND.values())


def models_by_provider() -> dict[str, list[str]]:
    """Ordered model ids per provider from the canonical catalog."""
    out: dict[str, list[str]] = {p: [] for p in PROVIDER_ORDER}
    for row in CATALOG_MODELS:
        p = row["provider"]
        mid = row["id"]
        if p in out and mid not in out[p]:
            out[p].append(mid)
    return out


def normalize_menu(raw: Any) -> dict[str, list[str]]:
    """Normalize curator.menu to {provider: [model_id, ...]}."""
    if not isinstance(raw, dict):
        return {}
    out: dict[str, list[str]] = {}
    for key, val in raw.items():
        p = str(key or "").strip().lower()
        if p == "codex":
            p = "chatgpt"
        if p not in KNOWN_PROVIDERS:
            continue
        if not isinstance(val, list):
            continue
        seen: set[str] = set()
        ids: list[str] = []
        for item in val:
            mid = str(item or "").strip()
            if not mid or mid in seen:
                continue
            seen.add(mid)
            ids.append(mid)
        out[p] = ids
    return out


def default_menu() -> dict[str, list[str]]:
    return {k: list(v) for k, v in DEFAULT_MENU.items()}


def _command_exists(command: str) -> bool:
    cmd = (command or "").strip()
    if not cmd:
        return False
    p = Path(cmd)
    if p.is_file():
        return True
    return shutil.which(cmd) is not None


def _resolved_command(command: str, provider: str) -> str:
    fallback = DEFAULT_COMMAND.get(provider, "claude")
    cmd = (command or fallback).strip() or fallback
    if "/" in cmd or cmd.startswith("."):
        return cmd
    return shutil.which(cmd) or cmd


def provider_readiness(
    provider: str,
    *,
    active_provider: str = "claude",
    active_command: str = "",
) -> dict[str, Any]:
    """PATH readiness for a provider (uses active command when that provider is current)."""
    p = provider if provider in KNOWN_PROVIDERS else "claude"
    if p == active_provider and (active_command or "").strip():
        command = active_command.strip()
    else:
        command = DEFAULT_COMMAND.get(p, "claude")
    resolved = _resolved_command(command, p)
    out: dict[str, Any] = {
        "id": p,
        "label": PROVIDER_LABEL.get(p, p),
        "hint": PROVIDER_HINT.get(p, ""),
        "command": command,
        "command_resolved": resolved,
        "command_exists": _command_exists(resolved) or _command_exists(command),
        "stream": STREAM_LABEL.get(p, "unknown"),
    }
    hint = AUTH_HINT.get(p)
    if hint:
        out["auth_hint"] = hint
    return out


def build_catalog(settings: Optional[dict] = None) -> dict[str, Any]:
    """
    Full catalog payload for UIs: models, provider readiness, menu checkmarks,
    and `visible` = ready ∩ checked (+ force-include active chat model).
    """
    settings = settings if isinstance(settings, dict) else {}
    cfg = resolve_curator(settings)
    block = settings.get("curator") if isinstance(settings.get("curator"), dict) else {}
    menu = normalize_menu(block.get("menu"))
    if not menu:
        menu = default_menu()

    providers = [
        provider_readiness(
            p, active_provider=cfg.provider, active_command=cfg.command,
        )
        for p in PROVIDER_ORDER
    ]
    ready_by = {p["id"]: bool(p["command_exists"]) for p in providers}

    catalog = [dict(row) for row in CATALOG_MODELS]
    active_chat = (cfg.models.get("chat") or "").strip()
    visible: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()

    def _add_visible(row: dict[str, Any], *, forced: bool = False) -> None:
        key = (row["provider"], row["id"])
        if key in seen:
            return
        seen.add(key)
        item = dict(row)
        item["forced"] = forced
        item["ready"] = ready_by.get(row["provider"], False)
        visible.append(item)

    for row in catalog:
        p, mid = row["provider"], row["id"]
        checked = mid in menu.get(p, [])
        if checked and ready_by.get(p, False):
            _add_visible(row)

    # Active chat model always remains selectable (even if unchecked / CLI missing).
    if active_chat:
        match = next(
            (r for r in catalog
             if r["provider"] == cfg.provider and r["id"] == active_chat),
            None,
        )
        if match:
            _add_visible(match, forced=True)
        else:
            _add_visible(
                {
                    "id": active_chat,
                    "provider": cfg.provider,
                    "label": active_chat,
                    "blurb": "Active custom model id.",
                    "good_for": ["chat"],
                    "effort_supported": True,
                },
                forced=True,
            )

    return {
        "providers": providers,
        "models": catalog,
        "models_by_provider": models_by_provider(),
        "efforts_by_provider": {
            p: [dict(e) for e in EFFORT_BY_PROVIDER.get(p, [])]
            for p in PROVIDER_ORDER
        },
        "defaults_by_provider": {
            "claude": dict(DEFAULT_MODELS),
            "cli": dict(DEFAULT_MODELS),
            "grok": dict(DEFAULT_MODELS_GROK),
            "chatgpt": dict(DEFAULT_MODELS_CHATGPT),
            "gemini": dict(DEFAULT_MODELS_GEMINI),
        },
        "menu": menu,
        "visible": visible,
        "active": {
            "provider": cfg.provider,
            "command": cfg.command,
            "models": dict(cfg.models),
            "effort": cfg.effort or "default",
        },
    }


@dataclass
class CuratorConfig:
    provider: str = "claude"
    command: str = "claude"
    models: dict[str, str] = field(default_factory=lambda: dict(DEFAULT_MODELS))
    # Reasoning / effort level. Provider-specific names (claude: low…max;
    # grok: none…xhigh; chatgpt: low…ultra). Empty / "default" = omit CLI flag.
    effort: str = ""

    def stream_format(self) -> str:
        return STREAM_LABEL.get(self.provider, "unknown")

    def effort_for(self, task: str = "chat") -> Optional[str]:
        """Resolved effort for a turn."""
        e = (self.effort or "").strip()
        if not e or e.lower() == "default":
            return None
        return e

    def resolved_command(self) -> str:
        """PATH lookup when command is a bare name; otherwise return as-is."""
        fallback = DEFAULT_COMMAND.get(self.provider, "claude")
        cmd = (self.command or fallback).strip() or fallback
        if "/" in cmd or cmd.startswith("."):
            return cmd
        return shutil.which(cmd) or cmd

    def command_exists(self) -> bool:
        path = self.resolved_command()
        p = Path(path)
        if p.is_file():
            return True
        return shutil.which(path) is not None

    def model_for(self, task: str, override: Optional[str] = None) -> Optional[str]:
        """Resolve model id for a task. override from the request body wins when set."""
        defaults = default_models_for(self.provider)
        if override is not None:
            o = str(override).strip()
            if not o or o == "default":
                return None
            return o
        m = (self.models.get(task) or defaults.get(task) or "").strip()
        if not m or m == "default":
            return None
        return m

    def as_public_dict(self) -> dict[str, Any]:
        resolved = self.resolved_command()
        out: dict[str, Any] = {
            "provider": self.provider,
            "command": self.command,
            "command_resolved": resolved,
            "command_exists": self.command_exists(),
            "models": dict(self.models),
            "effort": self.effort or "default",
            "stream": self.stream_format(),
        }
        hint = AUTH_HINT.get(self.provider)
        if hint:
            out["auth_hint"] = hint
        return out


def default_models_for(provider: str) -> dict[str, str]:
    if provider == "grok":
        return dict(DEFAULT_MODELS_GROK)
    if provider == "chatgpt":
        return dict(DEFAULT_MODELS_CHATGPT)
    if provider == "gemini":
        return dict(DEFAULT_MODELS_GEMINI)
    return dict(DEFAULT_MODELS)


def _legacy_models(settings: dict) -> dict[str, str]:
    models = dict(DEFAULT_MODELS)
    agents = settings.get("agents")
    if isinstance(agents, dict):
        for k in DEFAULT_MODELS:
            v = agents.get(k)
            if isinstance(v, str) and v.strip():
                models[k] = v.strip()
    legacy = settings.get("model")
    if isinstance(legacy, str) and legacy.strip():
        if not (isinstance(agents, dict) and agents.get("chat")):
            models["chat"] = legacy.strip()
    return models


def resolve_curator(settings: Optional[dict] = None) -> CuratorConfig:
    """Build CuratorConfig from settings.json (with legacy migration)."""
    settings = settings if isinstance(settings, dict) else {}
    block = settings.get("curator")
    if not isinstance(block, dict):
        block = {}

    provider = str(block.get("provider") or "claude").strip().lower() or "claude"
    # Accept alias codex → chatgpt
    if provider == "codex":
        provider = "chatgpt"
    if provider not in KNOWN_PROVIDERS:
        provider = "claude"

    command = str(block.get("command") or "").strip()
    if not command:
        command = DEFAULT_COMMAND.get(provider, "claude")

    models = default_models_for(provider)
    if provider in ("claude", "cli"):
        models.update({k: v for k, v in _legacy_models(settings).items() if v})
    raw_models = block.get("models")
    if isinstance(raw_models, dict):
        for k in DEFAULT_MODELS:
            v = raw_models.get(k)
            if isinstance(v, str) and v.strip():
                models[k] = v.strip()

    effort = str(block.get("effort") or "").strip()
    if effort.lower() == "default":
        effort = ""

    return CuratorConfig(
        provider=provider, command=command, models=models, effort=effort,
    )


def ensure_curator_settings(settings: dict) -> dict:
    """
    Return a settings dict that includes a normalized `curator` block.
    Does not write to disk — caller may save if they want to persist migration.
    Seeds curator.menu when missing (Claude sonnet/opus/haiku).
    """
    cfg = resolve_curator(settings)
    prior_curator = settings.get("curator") if isinstance(settings.get("curator"), dict) else {}
    out = dict(settings)
    prev = settings.get("curator") if isinstance(settings.get("curator"), dict) else {}
    menu = normalize_menu(prev.get("menu"))
    if not menu:
        menu = default_menu()
    cur: dict[str, Any] = {
        "provider": cfg.provider,
        "command": cfg.command,
        "models": dict(cfg.models),
        "menu": menu,
    }
    if cfg.effort:
        cur["effort"] = cfg.effort
    if "idle_timeout_s" in prior_curator:
        cur["idle_timeout_s"] = prior_curator["idle_timeout_s"]
    out["curator"] = cur
    out["agents"] = dict(cfg.models)
    return out


def deep_merge_settings(cur: dict, patch: dict) -> dict:
    """Shallow merge with deep merge for curator / agents / models / menu."""
    out = dict(cur)
    for key, val in patch.items():
        if key == "curator" and isinstance(val, dict):
            base = dict(out.get("curator") or {})
            models_patch = val.get("models")
            menu_patch = val.get("menu")
            for k, v in val.items():
                if k in ("models", "menu"):
                    continue
                base[k] = v
            provider = str(base.get("provider") or "claude").strip().lower() or "claude"
            if provider == "codex":
                provider = "chatgpt"
                base["provider"] = provider
            if provider not in KNOWN_PROVIDERS:
                provider = "claude"
                base["provider"] = provider
            if "provider" in val and not isinstance(models_patch, dict):
                prev = str(base.get("command") or "").strip()
                if not prev or prev in DEFAULT_COMMAND_VALUES:
                    base["command"] = DEFAULT_COMMAND.get(provider, "claude")
                base["models"] = default_models_for(provider)
            elif isinstance(models_patch, dict):
                models = dict(base.get("models") or default_models_for(provider))
                models.update({k: v for k, v in models_patch.items() if isinstance(v, str) and k in DEFAULT_MODELS})
                base["models"] = models
            elif "models" not in base:
                base["models"] = default_models_for(provider)
            if "command" not in base or not base["command"]:
                base["command"] = DEFAULT_COMMAND.get(provider, "claude")
            if isinstance(menu_patch, dict):
                menu = normalize_menu(base.get("menu"))
                if not menu:
                    menu = default_menu()
                patched = normalize_menu(menu_patch)
                menu.update(patched)
                base["menu"] = menu
            elif "menu" not in base or not normalize_menu(base.get("menu")):
                base["menu"] = default_menu()
            out["curator"] = base
            if "models" in base:
                agents = dict(out.get("agents") or {})
                agents.update(base["models"])
                out["agents"] = agents
        elif key == "agents" and isinstance(val, dict):
            agents = dict(out.get("agents") or {})
            agents.update({k: v for k, v in val.items() if isinstance(v, str) and k in DEFAULT_MODELS})
            out["agents"] = agents
            curator = dict(out.get("curator") or {})
            provider = str(curator.get("provider") or "claude").strip().lower() or "claude"
            if provider == "codex":
                provider = "chatgpt"
            models = dict(curator.get("models") or default_models_for(provider))
            models.update({k: v for k, v in agents.items() if k in DEFAULT_MODELS})
            curator["models"] = models
            if "provider" not in curator:
                curator["provider"] = "claude"
            if "command" not in curator:
                curator["command"] = DEFAULT_COMMAND.get(curator["provider"], "claude")
            if "menu" not in curator or not normalize_menu(curator.get("menu")):
                curator["menu"] = default_menu()
            out["curator"] = curator
        else:
            out[key] = val
    return out
