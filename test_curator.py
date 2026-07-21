#!/usr/bin/env python3
"""Unit tests for curator.py — pluggable curator settings / resolution."""
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import curator
from curator import CuratorConfig, deep_merge_settings, ensure_curator_settings, resolve_curator


class TestResolveCurator(unittest.TestCase):
    def test_defaults(self):
        cfg = resolve_curator({})
        self.assertEqual(cfg.provider, "claude")
        self.assertEqual(cfg.command, "claude")
        self.assertEqual(cfg.models["setup"], "sonnet")
        self.assertEqual(cfg.models["chat"], "sonnet")
        self.assertNotIn("glance", cfg.models)

    def test_legacy_agents_and_model(self):
        cfg = resolve_curator({"model": "opus", "agents": {"setup": "opus"}})
        self.assertEqual(cfg.models["setup"], "opus")
        self.assertEqual(cfg.models["chat"], "opus")  # from legacy model
        self.assertNotIn("glance", cfg.models)

    def test_curator_block_wins(self):
        cfg = resolve_curator({
            "agents": {"setup": "sonnet"},
            "curator": {
                "provider": "cli",
                "command": "/usr/local/bin/my-agent",
                "models": {"setup": "opus", "chat": "opus"},
            },
        })
        self.assertEqual(cfg.provider, "cli")
        self.assertEqual(cfg.command, "/usr/local/bin/my-agent")
        self.assertEqual(cfg.models["setup"], "opus")

    def test_unknown_provider_falls_back_to_claude(self):
        cfg = resolve_curator({"curator": {"provider": "vscode-lm", "command": "claude"}})
        self.assertEqual(cfg.provider, "claude")

    def test_grok_provider_defaults(self):
        cfg = resolve_curator({"curator": {"provider": "grok"}})
        self.assertEqual(cfg.provider, "grok")
        self.assertEqual(cfg.command, "grok")
        self.assertEqual(cfg.models["setup"], "grok-4.5")
        self.assertEqual(cfg.models["chat"], "grok-4.5")
        self.assertNotIn("glance", cfg.models)
        pub = cfg.as_public_dict()
        self.assertEqual(pub["stream"], "streaming-json")
        self.assertEqual(pub["auth_hint"], "XAI_API_KEY")

    def test_grok_ignores_claude_legacy_agents(self):
        cfg = resolve_curator({
            "agents": {"setup": "sonnet", "chat": "opus"},
            "curator": {"provider": "grok"},
        })
        self.assertEqual(cfg.models["setup"], "grok-4.5")
        self.assertEqual(cfg.models["chat"], "grok-4.5")

    def test_grok_explicit_models_win(self):
        cfg = resolve_curator({
            "agents": {"setup": "sonnet"},
            "curator": {
                "provider": "grok",
                "models": {"setup": "custom-grok", "chat": "custom-grok"},
            },
        })
        self.assertEqual(cfg.models["setup"], "custom-grok")
        self.assertEqual(cfg.models["chat"], "custom-grok")

    def test_chatgpt_provider_defaults(self):
        cfg = resolve_curator({"curator": {"provider": "chatgpt"}})
        self.assertEqual(cfg.provider, "chatgpt")
        self.assertEqual(cfg.command, "codex")
        self.assertEqual(cfg.models["setup"], "gpt-5.1")
        self.assertEqual(cfg.models["chat"], "gpt-5.1")
        pub = cfg.as_public_dict()
        self.assertEqual(pub["stream"], "codex-json")
        self.assertEqual(pub["auth_hint"], "OPENAI_API_KEY")

    def test_codex_alias_maps_to_chatgpt(self):
        cfg = resolve_curator({"curator": {"provider": "codex"}})
        self.assertEqual(cfg.provider, "chatgpt")
        self.assertEqual(cfg.command, "codex")

    def test_gemini_provider_defaults(self):
        cfg = resolve_curator({"curator": {"provider": "gemini"}})
        self.assertEqual(cfg.provider, "gemini")
        self.assertEqual(cfg.command, "gemini")
        self.assertEqual(cfg.models["setup"], "gemini-2.5-pro")
        self.assertEqual(cfg.models["chat"], "gemini-2.5-pro")
        self.assertEqual(cfg.as_public_dict()["stream"], "stream-json")
        self.assertEqual(cfg.as_public_dict()["auth_hint"], "GEMINI_API_KEY")

    def test_model_for_override(self):
        cfg = CuratorConfig(models={"setup": "sonnet", "chat": "sonnet"})
        self.assertEqual(cfg.model_for("setup", "opus"), "opus")
        self.assertIsNone(cfg.model_for("setup", "default"))
        self.assertEqual(cfg.model_for("chat"), "sonnet")

    def test_model_for_ignores_cross_provider_override(self):
        cfg = CuratorConfig(
            provider="claude",
            models={"setup": "sonnet", "chat": "sonnet"},
        )
        # Desk cache still holding grok-4.5 after a provider flip must not win.
        self.assertEqual(cfg.model_for("chat", "grok-4.5"), "sonnet")
        self.assertEqual(cfg.model_for("chat", "opus"), "opus")

    def test_resolve_sanitizes_illegal_model_pair(self):
        cfg = resolve_curator({
            "curator": {
                "provider": "claude",
                "models": {"setup": "sonnet", "chat": "grok-4.5"},
            },
        })
        self.assertEqual(cfg.provider, "claude")
        self.assertEqual(cfg.models["chat"], "sonnet")

    def test_deep_merge_sanitizes_foreign_chat_model(self):
        cur = {"curator": {"provider": "claude", "command": "claude",
                           "models": {"setup": "sonnet", "chat": "sonnet"}}}
        out = deep_merge_settings(cur, {"curator": {"models": {"chat": "grok-4.5"}}})
        self.assertEqual(out["curator"]["provider"], "claude")
        self.assertEqual(out["curator"]["models"]["chat"], "sonnet")

    def test_apply_curator_selection_model_sets_provider(self):
        from curator import apply_curator_selection
        out = apply_curator_selection({}, model="grok-4.5")
        self.assertEqual(out["curator"]["provider"], "grok")
        self.assertEqual(out["curator"]["models"]["chat"], "grok-4.5")
        self.assertEqual(out["curator"]["command"], "grok")

    def test_apply_curator_selection_rejects_mismatched_pair(self):
        from curator import apply_curator_selection
        with self.assertRaises(ValueError):
            apply_curator_selection({}, provider="claude", model="grok-4.5")

    def test_effort_roundtrip(self):
        cfg = resolve_curator({"curator": {"provider": "claude", "effort": "xhigh"}})
        self.assertEqual(cfg.effort, "xhigh")
        self.assertEqual(cfg.effort_for("chat"), "xhigh")
        self.assertEqual(cfg.as_public_dict()["effort"], "xhigh")
        cfg2 = resolve_curator({"curator": {"provider": "claude", "effort": "default"}})
        self.assertEqual(cfg2.effort, "")
        self.assertIsNone(cfg2.effort_for("chat"))


class TestDeepMerge(unittest.TestCase):
    def test_curator_models_merge(self):
        cur = {"curator": {"provider": "claude", "command": "claude",
                           "models": {"setup": "sonnet", "chat": "sonnet"}}}
        out = deep_merge_settings(cur, {"curator": {"models": {"setup": "opus"}}})
        self.assertEqual(out["curator"]["models"]["setup"], "opus")
        self.assertEqual(out["curator"]["models"]["chat"], "sonnet")
        self.assertEqual(out["curator"]["provider"], "claude")
        self.assertEqual(out["agents"]["setup"], "opus")

    def test_agents_mirrors_curator(self):
        out = deep_merge_settings({}, {"agents": {"chat": "opus"}})
        self.assertEqual(out["curator"]["models"]["chat"], "opus")
        self.assertEqual(out["curator"]["provider"], "claude")

    def test_switch_to_grok_installs_defaults(self):
        cur = {"curator": {"provider": "claude", "command": "claude",
                           "models": {"setup": "sonnet", "chat": "sonnet"}}}
        out = deep_merge_settings(cur, {"curator": {"provider": "grok"}})
        self.assertEqual(out["curator"]["provider"], "grok")
        self.assertEqual(out["curator"]["command"], "grok")
        self.assertEqual(out["curator"]["models"]["setup"], "grok-4.5")
        self.assertNotIn("glance", out["agents"])


    def test_switch_to_gemini_installs_defaults(self):
        cur = {"curator": {"provider": "claude", "command": "claude",
                           "models": {"setup": "sonnet", "chat": "sonnet"}}}
        out = deep_merge_settings(cur, {"curator": {"provider": "gemini"}})
        self.assertEqual(out["curator"]["provider"], "gemini")
        self.assertEqual(out["curator"]["command"], "gemini")
        self.assertEqual(out["curator"]["models"]["chat"], "gemini-2.5-pro")


class TestEnsure(unittest.TestCase):
    def test_ensure_writes_curator_block(self):
        out = ensure_curator_settings({"model": "opus"})
        self.assertIn("curator", out)
        self.assertEqual(out["curator"]["models"]["chat"], "opus")
        self.assertEqual(out["agents"]["chat"], "opus")
        self.assertEqual(out["curator"]["menu"]["claude"], ["sonnet", "opus", "haiku"])

    def test_ensure_preserves_menu(self):
        out = ensure_curator_settings({
            "curator": {
                "provider": "claude",
                "command": "claude",
                "models": {"setup": "sonnet", "chat": "sonnet"},
                "menu": {"claude": ["opus"], "grok": ["grok-4.5"]},
            },
        })
        self.assertEqual(out["curator"]["menu"]["claude"], ["opus"])
        self.assertEqual(out["curator"]["menu"]["grok"], ["grok-4.5"])

    def test_ensure_preserves_idle_timeout(self):
        out = ensure_curator_settings({"curator": {"idle_timeout_s": 12.5}})
        self.assertEqual(out["curator"]["idle_timeout_s"], 12.5)


class TestCatalog(unittest.TestCase):
    def test_build_catalog_seed_menu_and_visible(self):
        # Pin PATH so the visibility assertions cannot pass vacuously on a host with
        # no curator CLIs (or vary because a developer happens to have several).
        with tempfile.TemporaryDirectory(prefix="setsweep-catalog-") as td:
            claude = Path(td) / "claude"
            claude.write_text("#!/bin/sh\nexit 0\n")
            claude.chmod(0o755)
            with mock.patch.dict(os.environ, {"PATH": td}):
                cat = curator.build_catalog({})
        self.assertEqual(cat["menu"]["claude"], ["sonnet", "opus", "haiku"])
        self.assertNotIn("fable", cat["menu"].get("claude", []))
        providers = {p["id"]: p for p in cat["providers"]}
        self.assertTrue(providers["claude"]["command_exists"])
        self.assertFalse(providers["grok"]["command_exists"])
        # Only checked Claude models appear; the pinned fake CLI makes this unconditional.
        claude_visible = [v["id"] for v in cat["visible"] if v["provider"] == "claude"]
        for mid in ("sonnet", "opus", "haiku"):
            self.assertIn(mid, claude_visible)
        self.assertNotIn("fable", claude_visible)
        # Unchecked providers should not contribute visible rows unless forced active
        grok_visible = [v for v in cat["visible"] if v["provider"] == "grok" and not v.get("forced")]
        self.assertEqual(grok_visible, [])

    def test_menu_merge(self):
        cur = {"curator": {"provider": "claude", "command": "claude",
                           "models": {"setup": "sonnet", "chat": "sonnet"},
                           "menu": {"claude": ["sonnet"]}}}
        out = deep_merge_settings(cur, {"curator": {"menu": {"grok": ["grok-4.5"]}}})
        self.assertEqual(out["curator"]["menu"]["claude"], ["sonnet"])
        self.assertEqual(out["curator"]["menu"]["grok"], ["grok-4.5"])

    def test_visible_force_includes_active(self):
        cat = curator.build_catalog({
            "curator": {
                "provider": "claude",
                "command": "claude",
                "models": {"setup": "opus", "chat": "fable"},
                "menu": {"claude": ["sonnet"]},
            },
        })
        ids = {(v["provider"], v["id"]) for v in cat["visible"]}
        self.assertIn(("claude", "fable"), ids)
        forced = next(v for v in cat["visible"] if v["id"] == "fable")
        self.assertTrue(forced.get("forced"))


if __name__ == "__main__":
    unittest.main()
