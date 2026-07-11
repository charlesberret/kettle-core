"""
Pluggable curator backends for Setsweep.

The desk owns prompts, tool allowlists, NDJSON event shapes, and the session ledger.
A curator *provider* only supplies the executable (and later: stream dialect / bridge)
that runs a turn. Claude Code CLI remains the default.

settings.json shape (preferred):

  {
    "curator": {
      "provider": "claude",   # "claude" | "cli" (same stream-json protocol for now)
      "command": "claude",    # executable name or absolute path
      "models": {
        "setup": "sonnet",    # founding survey + sweep
        "chat": "sonnet",     # right-pane / interview continue
        "glance": "haiku"     # file-open glance
      }
    }
  }

Legacy (still read): top-level "model" and "agents": {setup, chat, glance}.
"""
from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

DEFAULT_MODELS = {
    "setup": "sonnet",
    "chat": "sonnet",
    "glance": "haiku",
}

# Providers that speak Claude Code's --output-format stream-json dialect today.
STREAM_JSON_PROVIDERS = frozenset({"claude", "cli"})


@dataclass
class CuratorConfig:
    provider: str = "claude"
    command: str = "claude"
    models: dict[str, str] = field(default_factory=lambda: dict(DEFAULT_MODELS))

    def resolved_command(self) -> str:
        """PATH lookup when command is a bare name; otherwise return as-is."""
        cmd = (self.command or "claude").strip() or "claude"
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
        if override is not None:
            o = str(override).strip()
            if not o or o == "default":
                return None
            return o
        m = (self.models.get(task) or DEFAULT_MODELS.get(task) or "").strip()
        if not m or m == "default":
            return None
        return m

    def as_public_dict(self) -> dict[str, Any]:
        resolved = self.resolved_command()
        return {
            "provider": self.provider,
            "command": self.command,
            "command_resolved": resolved,
            "command_exists": self.command_exists(),
            "models": dict(self.models),
            "stream": "stream-json" if self.provider in STREAM_JSON_PROVIDERS else "unknown",
        }


def _legacy_models(settings: dict) -> dict[str, str]:
    models = dict(DEFAULT_MODELS)
    agents = settings.get("agents")
    if isinstance(agents, dict):
        for k in DEFAULT_MODELS:
            v = agents.get(k)
            if isinstance(v, str) and v.strip():
                models[k] = v.strip()
    # Old single "model" only filled chat when agents.chat absent
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
    if provider not in STREAM_JSON_PROVIDERS:
        # Unknown providers fall back to claude executable until a real adapter exists
        provider = "claude"

    command = str(block.get("command") or "").strip()
    if not command:
        command = "claude"

    models = _legacy_models(settings)
    raw_models = block.get("models")
    if isinstance(raw_models, dict):
        for k in DEFAULT_MODELS:
            v = raw_models.get(k)
            if isinstance(v, str) and v.strip():
                models[k] = v.strip()

    return CuratorConfig(provider=provider, command=command, models=models)


def ensure_curator_settings(settings: dict) -> dict:
    """
    Return a settings dict that includes a normalized `curator` block.
    Does not write to disk — caller may save if they want to persist migration.
    """
    cfg = resolve_curator(settings)
    out = dict(settings)
    out["curator"] = {
        "provider": cfg.provider,
        "command": cfg.command,
        "models": dict(cfg.models),
    }
    # Keep agents in sync for the web Admin UI until it reads curator.models
    out["agents"] = dict(cfg.models)
    return out


def deep_merge_settings(cur: dict, patch: dict) -> dict:
    """Shallow merge with deep merge for curator / agents / models."""
    out = dict(cur)
    for key, val in patch.items():
        if key == "curator" and isinstance(val, dict):
            base = dict(out.get("curator") or {})
            models_patch = val.get("models")
            for k, v in val.items():
                if k == "models":
                    continue
                base[k] = v
            if isinstance(models_patch, dict):
                models = dict(base.get("models") or {})
                models.update({k: v for k, v in models_patch.items() if isinstance(v, str)})
                base["models"] = models
            out["curator"] = base
            # Mirror models into agents for web UI
            if "models" in base:
                agents = dict(out.get("agents") or {})
                agents.update(base["models"])
                out["agents"] = agents
        elif key == "agents" and isinstance(val, dict):
            agents = dict(out.get("agents") or {})
            agents.update({k: v for k, v in val.items() if isinstance(v, str)})
            out["agents"] = agents
            curator = dict(out.get("curator") or {})
            models = dict(curator.get("models") or DEFAULT_MODELS)
            models.update(agents)
            curator["models"] = models
            if "provider" not in curator:
                curator["provider"] = "claude"
            if "command" not in curator:
                curator["command"] = "claude"
            out["curator"] = curator
        else:
            out[key] = val
    return out
