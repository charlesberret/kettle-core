#!/usr/bin/env python3
"""Unit tests for curator.py — pluggable curator settings / resolution."""
import unittest

import curator
from curator import CuratorConfig, deep_merge_settings, ensure_curator_settings, resolve_curator


class TestResolveCurator(unittest.TestCase):
    def test_defaults(self):
        cfg = resolve_curator({})
        self.assertEqual(cfg.provider, "claude")
        self.assertEqual(cfg.command, "claude")
        self.assertEqual(cfg.models["setup"], "sonnet")
        self.assertEqual(cfg.models["chat"], "sonnet")
        self.assertEqual(cfg.models["glance"], "haiku")

    def test_legacy_agents_and_model(self):
        cfg = resolve_curator({"model": "opus", "agents": {"setup": "opus", "glance": "haiku"}})
        self.assertEqual(cfg.models["setup"], "opus")
        self.assertEqual(cfg.models["chat"], "opus")  # from legacy model
        self.assertEqual(cfg.models["glance"], "haiku")

    def test_curator_block_wins(self):
        cfg = resolve_curator({
            "agents": {"setup": "sonnet"},
            "curator": {
                "provider": "cli",
                "command": "/usr/local/bin/my-agent",
                "models": {"setup": "opus", "chat": "opus", "glance": "haiku"},
            },
        })
        self.assertEqual(cfg.provider, "cli")
        self.assertEqual(cfg.command, "/usr/local/bin/my-agent")
        self.assertEqual(cfg.models["setup"], "opus")

    def test_unknown_provider_falls_back_to_claude(self):
        cfg = resolve_curator({"curator": {"provider": "vscode-lm", "command": "claude"}})
        self.assertEqual(cfg.provider, "claude")

    def test_model_for_override(self):
        cfg = CuratorConfig(models={"setup": "sonnet", "chat": "sonnet", "glance": "haiku"})
        self.assertEqual(cfg.model_for("setup", "opus"), "opus")
        self.assertIsNone(cfg.model_for("setup", "default"))
        self.assertEqual(cfg.model_for("glance"), "haiku")


class TestDeepMerge(unittest.TestCase):
    def test_curator_models_merge(self):
        cur = {"curator": {"provider": "claude", "command": "claude",
                           "models": {"setup": "sonnet", "chat": "sonnet", "glance": "haiku"}}}
        out = deep_merge_settings(cur, {"curator": {"models": {"setup": "opus"}}})
        self.assertEqual(out["curator"]["models"]["setup"], "opus")
        self.assertEqual(out["curator"]["models"]["chat"], "sonnet")
        self.assertEqual(out["curator"]["provider"], "claude")
        self.assertEqual(out["agents"]["setup"], "opus")

    def test_agents_mirrors_curator(self):
        out = deep_merge_settings({}, {"agents": {"chat": "opus"}})
        self.assertEqual(out["curator"]["models"]["chat"], "opus")
        self.assertEqual(out["curator"]["provider"], "claude")


class TestEnsure(unittest.TestCase):
    def test_ensure_writes_curator_block(self):
        out = ensure_curator_settings({"model": "opus"})
        self.assertIn("curator", out)
        self.assertEqual(out["curator"]["models"]["chat"], "opus")
        self.assertEqual(out["agents"]["chat"], "opus")


if __name__ == "__main__":
    unittest.main()
