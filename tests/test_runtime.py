#!/usr/bin/env python3
"""Unit tests for runtime.py — the viewport-neutral agent adapter.

Stdlib only (unittest). Run:  python3 test_runtime.py   (or python3 -m unittest)

The two tests that matter most are the regressions for the haywire token bar:
`test_context_is_single_call_not_turn_aggregate` and
`test_done_ctx_ignores_result_aggregate` — they pin the exact bug (summing a turn's
cache re-reads into the context bar so it sails past the window) so it can't return.
"""
import io
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import kettle.runtime as runtime
from kettle.runtime import (
    UsageMeter, SessionLedger, Runtime, build_cmd, build_argv, normalize,
    tools_argv, system_append_argv, effort_argv, session_name_argv,
)


def _ev(d):
    return json.dumps(d)


class TestUsageMeter(unittest.TestCase):
    def test_occupancy_is_sum_of_one_calls_input_classes(self):
        u = {"input_tokens": 1200, "cache_read_input_tokens": 150_000,
             "cache_creation_input_tokens": 4000, "output_tokens": 300}
        self.assertEqual(UsageMeter.occupancy(u), 155_200)

    def test_context_is_single_call_not_turn_aggregate(self):
        """THE BUG: a tool-loop turn makes 3 internal calls, each re-reading the full
        ~150k cache. The prototype summed them (→ ~465k, past the 200k window). Context
        occupancy is ONE call's context — the latest — and stays bounded by the window."""
        m = UsageMeter(window=200_000)
        for _ in range(3):
            m.feed_assistant({"input_tokens": 1200, "cache_read_input_tokens": 150_000,
                              "cache_creation_input_tokens": 4000, "output_tokens": 300})
        self.assertEqual(m.context_tokens, 155_200)   # one call, not 3×
        self.assertLess(m.fraction, 1.0)              # not "way over the limit"
        self.assertEqual(m.output_tokens, 900)        # cumulative output is billing-side

    def test_context_tracks_latest_growing_call(self):
        m = UsageMeter()
        m.feed_assistant({"input_tokens": 1000, "cache_read_input_tokens": 50_000})
        m.feed_assistant({"input_tokens": 1000, "cache_read_input_tokens": 80_000})
        self.assertEqual(m.context_tokens, 81_000)    # latest
        self.assertEqual(m.peak_tokens, 81_000)

    def test_cost_from_result_not_context(self):
        m = UsageMeter()
        m.feed_assistant({"input_tokens": 1000, "cache_read_input_tokens": 150_000})
        m.feed_result({"total_cost_usd": 0.42,
                       "usage": {"input_tokens": 9999, "cache_read_input_tokens": 999_999}})
        self.assertEqual(m.cost_usd, 0.42)
        self.assertEqual(m.context_tokens, 151_000)   # result.usage did NOT touch context

    def test_fraction_caps_at_one(self):
        m = UsageMeter(window=100)
        m.feed_assistant({"input_tokens": 500})
        self.assertEqual(m.fraction, 1.0)

    def test_snapshot_and_zero_window(self):
        m = UsageMeter(window=0)
        m.feed_assistant({"input_tokens": 10, "output_tokens": 2})
        m.feed_result({"total_cost_usd": 0.125})
        self.assertEqual(m.fraction, 0.0)
        snap = m.snapshot()
        self.assertEqual(snap["context"], 10)
        self.assertEqual(snap["output"], 2)
        self.assertEqual(snap["cost"], 0.125)
        self.assertEqual(snap["fraction"], 0.0)

    def test_empty_usage_does_not_reset_context(self):
        m = UsageMeter()
        m.feed_assistant({"input_tokens": 1000})
        m.feed_assistant({})  # occupancy 0 — keep prior context
        self.assertEqual(m.context_tokens, 1000)


class TestNormalize(unittest.TestCase):
    def test_emits_drop_in_event_shapes(self):
        lines = [
            _ev({"type": "system", "subtype": "init", "model": "claude-opus-4-8", "session_id": "s1"}),
            _ev({"type": "assistant", "message": {"content": [
                {"type": "text", "text": "hello"},
                {"type": "tool_use", "name": "Read", "input": {"file_path": "/x/y.md"}},
            ], "usage": {"input_tokens": 1000, "cache_read_input_tokens": 50_000, "output_tokens": 20}}}),
            _ev({"type": "result", "is_error": False, "total_cost_usd": 0.1,
                 "usage": {"input_tokens": 3000, "cache_read_input_tokens": 450_000}}),
        ]
        evs = list(normalize(lines))
        kinds = [e["t"] for e in evs]
        self.assertEqual(kinds, ["model", "text", "tool", "usage", "done"])
        self.assertEqual(evs[0]["s"], "claude-opus-4-8")
        self.assertEqual(evs[0]["session"], "s1")
        self.assertEqual(evs[1]["s"], "hello")
        self.assertTrue(evs[2]["s"].startswith("Read /x/y.md"))

    def test_done_ctx_ignores_result_aggregate(self):
        """done.ctx must be the assistant call's occupancy (51k), NOT the result event's
        inflated aggregate (453k)."""
        lines = [
            _ev({"type": "system", "subtype": "init", "model": "m", "session_id": "s1"}),
            _ev({"type": "assistant", "message": {"content": [{"type": "text", "text": "hi"}],
                 "usage": {"input_tokens": 1000, "cache_read_input_tokens": 50_000}}}),
            _ev({"type": "result", "is_error": False, "total_cost_usd": 0.42,
                 "usage": {"input_tokens": 3000, "cache_read_input_tokens": 450_000}}),
        ]
        done = [e for e in normalize(lines) if e["t"] == "done"][0]
        self.assertEqual(done["ctx"], 51_000)
        self.assertEqual(done["cost"], 0.42)
        self.assertIsNone(done["error"])

    def test_grok_thought_emits_activity(self):
        """Grok streaming-json has no tool events — thought must surface as activity."""
        lines = [
            _ev({"type": "thought", "data": "Scanning"}),
            _ev({"type": "text", "data": "Done."}),
            _ev({"type": "end", "sessionId": "g1",
                 "usage": {"input_tokens": 10, "output_tokens": 2}}),
        ]
        evs = list(normalize(lines))
        kinds = [e["t"] for e in evs]
        self.assertIn("activity", kinds)
        act = next(e for e in evs if e["t"] == "activity")
        self.assertEqual(act.get("kind"), "thought")
        self.assertEqual(act.get("s"), "thinking…")
        self.assertNotIn("Scanning", str(act))
        self.assertIn("text", kinds)

    def test_grok_end_emits_model_before_usage(self):
        """Context bar sizes the window from model; usage-first flashed false 100% red."""
        lines = [
            _ev({
                "type": "end",
                "sessionId": "g1",
                "modelUsage": {"grok-4.5": {"inputTokens": 120000}},
                "usage": {
                    "input_tokens": 120000,
                    "output_tokens": 800,
                    "cache_read_input_tokens": 0,
                    "cache_creation_input_tokens": 0,
                },
            }),
        ]
        evs = list(normalize(lines))
        kinds = [e["t"] for e in evs]
        self.assertIn("model", kinds)
        self.assertIn("usage", kinds)
        self.assertLess(kinds.index("model"), kinds.index("usage"))
        model = next(e for e in evs if e["t"] == "model")
        self.assertEqual(model["s"], "grok-4.5")
        usage = next(e for e in evs if e["t"] == "usage")
        self.assertEqual(usage["context"], 120000)

    def test_tool_use_carries_name_and_path(self):
        # consumers auto-log file edits off these structured fields
        lines = [_ev({"type": "assistant", "message": {"content": [
            {"type": "tool_use", "name": "Edit", "input": {"file_path": "/p/x.md"}}]}})]
        tool = [e for e in normalize(lines) if e["t"] == "tool"][0]
        self.assertEqual(tool["tool"], "Edit")
        self.assertEqual(tool["path"], "/p/x.md")

    def test_session_callback_fires(self):
        seen = []
        lines = [_ev({"type": "system", "subtype": "init", "model": "m", "session_id": "abc"})]
        list(normalize(lines, on_session=seen.append))
        self.assertEqual(seen, ["abc"])

    def test_error_result_surfaces_subtype(self):
        lines = [_ev({"type": "result", "is_error": True, "subtype": "error_max_turns"})]
        done = [e for e in normalize(lines) if e["t"] == "done"][0]
        self.assertEqual(done["error"], "error_max_turns")

    def test_garbage_lines_skipped(self):
        lines = ["", "not json", _ev({"type": "assistant", "message": {"content": [
            {"type": "text", "text": "ok"}]}})]
        evs = list(normalize(lines))
        self.assertEqual([e["t"] for e in evs], ["text"])


class TestBuildCmd(unittest.TestCase):
    def test_fresh_turn_has_no_resume(self):
        cmd = build_cmd("claude", "hi")
        self.assertNotIn("--resume", cmd)
        self.assertEqual(cmd[:4], ["claude", "-p", "hi", "--output-format"])
        self.assertIn("stream-json", cmd)
        self.assertIn("--verbose", cmd)

    def test_resume_threads_the_session(self):
        cmd = build_cmd("claude", "hi", session_id="s1", extra=["--add-dir", "/p"])
        self.assertIn("--resume", cmd)
        self.assertEqual(cmd[cmd.index("--resume") + 1], "s1")
        self.assertIn("--add-dir", cmd)

    def test_grok_uses_streaming_json_no_verbose(self):
        cmd = build_cmd("grok", "hi", provider="grok")
        self.assertIn("streaming-json", cmd)
        self.assertNotIn("--verbose", cmd)
        self.assertNotIn("stream-json", cmd)


class TestDialectArgv(unittest.TestCase):
    def test_claude_chat_tools(self):
        bits = tools_argv("chat", "claude")
        self.assertIn("--allowedTools", bits)
        self.assertIn("Read", bits)
        self.assertIn("--disallowedTools", bits)

    def test_grok_chat_tools_use_allow(self):
        bits = tools_argv("chat", "grok")
        self.assertIn("--allow", bits)
        self.assertIn("Read", bits)
        # NotebookEdit deny is Claude-only — Grok mis-parses it as deny-all-edits
        self.assertNotIn("NotebookEdit", bits)
        self.assertNotIn("--deny", bits)
        self.assertNotIn("--allowedTools", bits)
        self.assertIn("--always-approve", bits)
        self.assertIn("bypassPermissions", bits)
        # Open Bash — fine-grained Bash(ls:*) cancels Grok shell turns
        self.assertIn("Bash", bits)
        self.assertNotIn("Bash(ls:*)", bits)

    def test_grok_sweep_tools_expand_shell_and_auto_approve(self):
        bits = tools_argv("sweep", "grok")
        self.assertIn("--always-approve", bits)
        self.assertIn("Bash", bits)
        self.assertEqual(bits.count("--always-approve"), 1)
        self.assertNotIn("Bash(mv:*)", bits)  # open Bash instead of fine-grained
        self.assertIn("bypassPermissions", bits)
        self.assertNotIn("NotebookEdit", bits)
        self.assertNotIn("--deny", bits)

    def test_normalize_grok_cancelled_end(self):
        lines = [_ev({"type": "end", "stopReason": "cancelled",
                       "sessionId": "s1"})]
        evs = list(normalize(lines))
        self.assertTrue(any(e["t"] == "error" and "cancelled" in e["s"] for e in evs))
        self.assertEqual(evs[-2]["t"], "done")
        self.assertIn("cancelled", str(evs[-2].get("error")))

    def test_system_append_maps_rules_for_grok(self):
        self.assertEqual(system_append_argv("hello", "claude")[0], "--append-system-prompt")
        self.assertEqual(system_append_argv("hello", "grok"), ["--rules", "hello"])

    def test_build_argv_grok_omits_name(self):
        class Cfg:
            provider = "grok"
            def resolved_command(self):
                return "grok"
        cmd = build_argv(Cfg(), "hi", session_name="proj", tools_tier="glance")
        self.assertNotIn("--name", cmd)
        self.assertIn("streaming-json", cmd)

    def test_normalize_grok_error_event(self):
        lines = [_ev({"type": "error", "message": "Couldn't create session"})]
        evs = list(normalize(lines))
        self.assertEqual(evs, [{"t": "error", "s": "Couldn't create session"}])

    def test_normalize_grok_streaming_json(self):
        captured = []
        lines = [
            _ev({"type": "thought", "data": "hmm"}),
            _ev({"type": "text", "data": "Hi"}),
            _ev({"type": "text", "data": "!"}),
            _ev({
                "type": "end",
                "stopReason": "EndTurn",
                "sessionId": "grok-sid-1",
                "usage": {"input_tokens": 10, "output_tokens": 2,
                          "cache_read_input_tokens": 0},
                "modelUsage": {"grok-4.5": {"inputTokens": 10}},
            }),
        ]
        evs = list(normalize(lines, on_session=captured.append))
        texts = [e["s"] for e in evs if e["t"] == "text"]
        self.assertEqual(texts, ["Hi", "!"])
        self.assertEqual(captured, ["grok-sid-1"])
        kinds = [e["t"] for e in evs]
        self.assertIn("usage", kinds)
        self.assertIn("model", kinds)
        self.assertEqual(kinds[-1], "done")
        self.assertEqual(evs[-1].get("error"), None)

    def test_normalize_stitches_glued_prose_blocks(self):
        """Separate assistant text events that omit a newline between sentences."""
        lines = [
            _ev({"type": "assistant", "message": {"content": [
                {"type": "text", "text": "checking how proposals are shaped in this setup."}]}}),
            _ev({"type": "assistant", "message": {"content": [
                {"type": "text", "text": "Writing the desk proposal and queueing it from your ticks."}]}}),
            _ev({"type": "assistant", "message": {"content": [
                {"type": "text", "text": "Desk Proposal filed — edit it next."}]}}),
        ]
        texts = [e["s"] for e in normalize(lines) if e["t"] == "text"]
        self.assertEqual(texts[0], "checking how proposals are shaped in this setup.")
        self.assertTrue(texts[1].startswith("\n\nWriting"), texts[1])
        self.assertTrue(texts[2].startswith("\n\nDesk"), texts[2])
        joined = "".join(texts)
        self.assertIn("setup.\n\nWriting", joined)
        self.assertIn("ticks.\n\nDesk", joined)

    def test_normalize_gemini_stream(self):
        lines = [
            _ev({"type": "init", "session_id": "g1", "model": "gemini-2.5-flash"}),
            _ev({"type": "message", "role": "assistant", "content": "hi"}),
            _ev({"type": "tool_use", "tool_name": "read_file",
                 "parameters": {"path": "/x.md"}}),
            _ev({"type": "result", "response": "", "stats": {
                "input_tokens": 100, "output_tokens": 10}}),
        ]
        evs = list(normalize(lines))
        kinds = [e["t"] for e in evs]
        self.assertEqual(kinds[0], "model")
        self.assertEqual(evs[0]["session"], "g1")
        self.assertIn("text", kinds)
        self.assertIn("tool", kinds)
        self.assertEqual(kinds[-1], "done")

    def test_normalize_codex_stream(self):
        lines = [
            _ev({"type": "thread.started", "thread_id": "thr-1"}),
            _ev({"type": "turn.started"}),
            _ev({"type": "item.completed", "item": {
                "type": "agent_message", "text": "hello from codex"}}),
            _ev({"type": "item.started", "item": {
                "type": "command_execution", "command": "ls -la"}}),
            _ev({"type": "turn.completed", "usage": {
                "input_tokens": 200, "cached_input_tokens": 50, "output_tokens": 20}}),
        ]
        evs = list(normalize(lines))
        self.assertEqual(evs[0]["t"], "model")
        self.assertEqual(evs[0]["session"], "thr-1")
        texts = [e for e in evs if e["t"] == "text"]
        self.assertEqual(texts[0]["s"], "hello from codex")
        tools = [e for e in evs if e["t"] == "tool"]
        self.assertTrue(tools[0]["s"].startswith("Bash"))
        self.assertEqual(evs[-1]["t"], "done")

    def test_build_cmd_chatgpt_uses_codex_exec(self):
        cmd = build_cmd("codex", "hi", provider="chatgpt")
        self.assertEqual(cmd[:3], ["codex", "exec", "--json"])
        self.assertEqual(cmd[-1], "hi")
        self.assertIn("--skip-git-repo-check", cmd)

    def test_build_cmd_chatgpt_resume(self):
        cmd = build_cmd("codex", "more", session_id="abc", provider="chatgpt")
        self.assertEqual(cmd[:5], ["codex", "exec", "resume", "abc", "--json"])

    def test_build_cmd_gemini(self):
        cmd = build_cmd("gemini", "hi", provider="gemini")
        self.assertIn("stream-json", cmd)
        self.assertNotIn("--verbose", cmd)

    def test_chatgpt_tools_use_sandbox(self):
        self.assertEqual(tools_argv("chat", "chatgpt"),
                         ["--sandbox", "workspace-write"])
        self.assertEqual(tools_argv("interview", "chatgpt"),
                         ["--sandbox", "read-only"])

    def test_gemini_tools_use_approval_mode(self):
        bits = tools_argv("sweep", "gemini")
        self.assertIn("--approval-mode", bits)
        self.assertIn("auto_edit", bits)

    def test_effort_argv_per_provider(self):
        self.assertEqual(effort_argv("high", "claude"), ["--effort", "high"])
        self.assertEqual(effort_argv("high", "grok"), ["--reasoning-effort", "high"])
        self.assertEqual(
            effort_argv("medium", "chatgpt"),
            ["-c", "model_reasoning_effort=medium"],
        )
        self.assertEqual(effort_argv("high", "gemini"), [])  # no flag yet
        self.assertEqual(effort_argv("default", "claude"), [])
        self.assertEqual(effort_argv("", "claude"), [])
        self.assertEqual(effort_argv("high", "codex"),
                         ["-c", "model_reasoning_effort=high"])

    def test_session_name_argv_claude_only(self):
        self.assertEqual(session_name_argv("desk", "claude"), ["--name", "desk"])
        self.assertEqual(session_name_argv("desk", "cli"), ["--name", "desk"])
        self.assertEqual(session_name_argv("desk", "grok"), [])
        self.assertEqual(session_name_argv("", "claude"), [])

    def test_system_append_empty_and_prompt_prefix_providers(self):
        self.assertEqual(system_append_argv("", "claude"), [])
        self.assertEqual(system_append_argv("hi", "chatgpt"), [])
        self.assertEqual(system_append_argv("hi", "gemini"), [])
        self.assertEqual(system_append_argv("hi", "codex"), [])

    def test_unknown_tools_tier_is_empty(self):
        self.assertEqual(tools_argv("nope", "claude"), [])
        self.assertEqual(tools_argv("glance", "grok"), [])

    def test_build_argv_string_cfg_with_model_and_prefix_system(self):
        cmd = build_argv(
            "gemini",
            "hi",
            system_append="be brief",
            model="gemini-2.5-flash",
            tools_tier="interview",
        )
        self.assertEqual(cmd[0], "gemini")
        self.assertIn("--model", cmd)
        self.assertIn("gemini-2.5-flash", cmd)
        # Gemini folds system text into the prompt, not argv flags.
        joined = " ".join(cmd)
        self.assertIn("be brief", joined)
        self.assertNotIn("--append-system-prompt", cmd)
        self.assertNotIn("--rules", cmd)

    def test_build_argv_chatgpt_session_name_omitted_on_resume(self):
        cmd = build_argv(
            SimpleNamespace(provider="chatgpt", command="codex",
                            resolved_command=lambda: "codex"),
            "more",
            session_id="thr-1",
            session_name="ignored-on-resume",
            effort="low",
        )
        self.assertEqual(cmd[:5], ["codex", "exec", "resume", "thr-1", "--json"])
        self.assertNotIn("--name", cmd)
        self.assertIn("model_reasoning_effort=low", cmd)


class TestNormalizeEdgeCases(unittest.TestCase):
    def test_codex_file_change_and_mcp_tools(self):
        lines = [
            _ev({"type": "item.completed", "item": {
                "type": "file_change", "path": "/p/a.md"}}),
            _ev({"type": "item.started", "item": {
                "type": "mcp_tool_call", "tool": "search"}}),
            _ev({"type": "item.completed", "item": {
                "type": "file_edit",
                "changes": [{"path": "/p/b.md"}]}}),
        ]
        tools = [e for e in normalize(lines) if e["t"] == "tool"]
        self.assertEqual(tools[0]["tool"], "Edit")
        self.assertEqual(tools[0]["path"], "/p/a.md")
        self.assertEqual(tools[1]["tool"], "search")
        self.assertEqual(tools[2]["path"], "/p/b.md")

    def test_codex_turn_failed(self):
        lines = [_ev({"type": "turn.failed",
                       "error": {"message": "rate limited"}})]
        evs = list(normalize(lines))
        self.assertEqual(evs[0], {"t": "error", "s": "rate limited"})
        self.assertEqual(evs[1]["t"], "done")
        self.assertEqual(evs[1]["error"], "rate limited")

    def test_gemini_tool_result_ignored_and_result_response(self):
        lines = [
            _ev({"type": "tool_result", "output": "ok"}),
            _ev({"type": "result", "response": "final answer",
                 "stats": {"models": {"m": {"tokens": {
                     "input": 40, "output": 5, "cached": 10}}}}}),
        ]
        evs = list(normalize(lines))
        self.assertEqual([e["t"] for e in evs], ["text", "usage", "done"])
        self.assertEqual(evs[0]["s"], "final answer")
        self.assertEqual(evs[1]["context"], 50)

    def test_result_error_shapes(self):
        dict_err = list(normalize([_ev({
            "type": "result", "error": {"message": "boom"}})]))
        self.assertEqual(dict_err[-1]["error"], "boom")
        str_err = list(normalize([_ev({
            "type": "result", "error": "nope"})]))
        self.assertEqual(str_err[-1]["error"], "nope")

    def test_grok_end_with_error_object(self):
        lines = [_ev({
            "type": "end",
            "sessionId": "g1",
            "error": {"message": "quota"},
            "usage": {"input_tokens": 3, "output_tokens": 1},
        })]
        evs = list(normalize(lines))
        done = next(e for e in evs if e["t"] == "done")
        self.assertEqual(done["error"], "quota")
        self.assertTrue(any(e["t"] == "error" and e["s"] == "quota" for e in evs))

    def test_error_event_with_nested_message(self):
        evs = list(normalize([_ev({
            "type": "error", "error": {"message": "nested"}})]))
        self.assertEqual(evs, [{"t": "error", "s": "nested"}])

    def test_text_gap_fixer_skips_empty_and_whitespace_join(self):
        lines = [
            _ev({"type": "assistant", "message": {"content": [
                {"type": "text", "text": "Hello."}]}}),
            _ev({"type": "assistant", "message": {"content": [
                {"type": "text", "text": ""}]}}),
            _ev({"type": "assistant", "message": {"content": [
                {"type": "text", "text": " World"}]}}),
        ]
        texts = [e["s"] for e in normalize(lines) if e["t"] == "text"]
        self.assertEqual(texts, ["Hello.", " World"])


class TestProviderCapabilities(unittest.TestCase):
    def test_read_only_guarantee_matches_the_argv_builder(self):
        """The declared read_only_tier must not drift from what tools_argv actually
        constructs for the interview (read-only) tier. A provider genuinely guarantees
        read-only only if its interview argv grants neither open shell nor auto-approval
        that would let shell run."""
        for provider in ("claude", "cli", "grok", "chatgpt", "gemini"):
            argv = tools_argv("interview", provider)
            # Open shell + always-approve (grok's read-only escape) means writes are possible.
            open_shell = "--allow" in argv and "Bash" in argv and "--always-approve" in argv
            derived_read_only = not open_shell
            self.assertEqual(
                runtime.guarantees_read_only(provider), derived_read_only,
                f"{provider}: PROVIDER_CAPABILITIES.read_only_tier disagrees with tools_argv",
            )

    def test_claude_interview_does_not_pass_bare_allowedTools(self):
        """Claude CLI  (2026) requires a value after --allowedTools.

        A founding interview used to pass the flag with no tools; that now
        exits 1: option '--allowedTools, --allowed-tools <tools...>' argument
        missing. plan mode is the tool-less posture.
        """
        for p in ("claude", "cli"):
            argv = tools_argv("interview", p)
            self.assertNotEqual(argv, ["--allowedTools"], p)
            if "--allowedTools" in argv:
                i = argv.index("--allowedTools")
                self.assertLess(i + 1, len(argv), p)
                self.assertFalse(str(argv[i + 1]).startswith("-"), p)
            self.assertEqual(argv, ["--permission-mode", "plan"], p)

    def test_grok_interview_is_tool_less_but_writes_unfenced(self):
        # Interview: no open Bash / always-approve → read_only_tier True.
        # Chat/sweep still bypassPermissions + Bash → fenced_writes False.
        self.assertTrue(runtime.guarantees_read_only("grok"))
        caps = runtime.capabilities_for("grok")
        self.assertFalse(caps["fenced_writes"])
        self.assertFalse(caps["tool_allowlist"])
        argv = tools_argv("interview", "grok")
        self.assertNotIn("Bash", argv)
        self.assertNotIn("--always-approve", argv)
        self.assertIn("--permission-mode", argv)
        self.assertIn("plan", argv)

    def test_claude_family_guarantees_read_only_and_fenced_writes(self):
        for p in ("claude", "cli"):
            caps = runtime.capabilities_for(p)
            self.assertTrue(caps["read_only_tier"])
            self.assertTrue(caps["fenced_writes"])
            self.assertTrue(caps["tool_allowlist"])

    def test_codex_alias_resolves_to_chatgpt(self):
        self.assertEqual(runtime.capabilities_for("codex"),
                         runtime.capabilities_for("chatgpt"))

    def test_unknown_provider_gets_weakest_guarantees(self):
        caps = runtime.capabilities_for("nope")
        self.assertEqual(set(caps.keys()), set(runtime.CAPABILITY_KEYS))
        self.assertFalse(any(caps.values()))


class TestSessionLedger(unittest.TestCase):
    def test_append_and_read_roundtrip(self):
        with tempfile.TemporaryDirectory() as d:
            led = SessionLedger(Path(d) / "sessions")
            led.append_turn("s1", "user", "what is X?", agent_text="X is Y",
                            tools=["Read a.md"], usage={"context": 50_000})
            led.append_turn("s1", "user", "and Z?", agent_text="Z is W")
            turns = led.turns("s1")
            self.assertEqual(len(turns), 2)
            self.assertEqual(turns[0]["message"], "what is X?")
            self.assertEqual(turns[0]["agent_text"], "X is Y")
            self.assertEqual(turns[0]["tools"], ["Read a.md"])
            self.assertEqual(turns[1]["agent_text"], "Z is W")

    def test_unknown_session_is_empty(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(SessionLedger(Path(d)).turns("nope"), [])

    def test_each_turn_is_one_jsonl_line(self):
        with tempfile.TemporaryDirectory() as d:
            led = SessionLedger(Path(d))
            led.append_turn("s", "user", "a")
            led.append_turn("s", "user", "b")
            text = led.path("s").read_text()
            self.assertEqual(len([ln for ln in text.splitlines() if ln.strip()]), 2)

    def test_turns_skips_corrupt_and_non_object_lines(self):
        with tempfile.TemporaryDirectory() as d:
            led = SessionLedger(Path(d))
            led.append_turn("s", "user", "ok")
            path = led.path("s")
            with path.open("a", encoding="utf-8") as fp:
                fp.write("not-json\n")
                fp.write("\n")
                fp.write(json.dumps(["array"]) + "\n")
                fp.write(json.dumps({"role": "user", "message": "kept"}) + "\n")
            turns = led.turns("s")
            self.assertEqual(len(turns), 2)
            self.assertEqual(turns[0]["message"], "ok")
            self.assertEqual(turns[1]["message"], "kept")


class TestRuntimeSpawn(unittest.TestCase):
    def test_spawn_normalizes_stream_and_persists_ledger(self):
        stream = "\n".join([
            _ev({"type": "system", "subtype": "init", "model": "m",
                 "session_id": "sid-1"}),
            _ev({"type": "assistant", "message": {"content": [
                {"type": "text", "text": "hello"},
                {"type": "tool_use", "name": "Read",
                 "input": {"file_path": "/p/x.md"}},
            ], "usage": {"input_tokens": 10, "output_tokens": 2}}}),
            _ev({"type": "result", "is_error": False, "total_cost_usd": 0.01}),
            "",
        ]) + "\n"

        class FakeProc:
            def __init__(self):
                self.stdout = io.StringIO(stream)
                self.returncode = 0

            def wait(self, timeout=None):
                return 0

            def poll(self):
                return 0

            def kill(self):
                raise AssertionError("kill should not run after exit")

        with tempfile.TemporaryDirectory() as d:
            rt = Runtime("claude", Path(d) / "sessions")
            with mock.patch("kettle.runtime.subprocess.Popen", return_value=FakeProc()):
                evs = list(rt.spawn("hi", cwd=d))
            kinds = [e["t"] for e in evs]
            self.assertEqual(kinds[0], "model")
            self.assertIn("text", kinds)
            self.assertIn("tool", kinds)
            self.assertEqual(kinds[-1], "done")
            turns = rt.ledger.turns("sid-1")
            self.assertEqual(len(turns), 1)
            self.assertEqual(turns[0]["message"], "hi")
            self.assertEqual(turns[0]["agent_text"], "hello")
            self.assertTrue(turns[0]["tools"][0].startswith("Read"))

    def test_spawn_nonzero_exit_emits_error(self):
        class FakeProc:
            def __init__(self):
                self.stdout = io.StringIO("")
                self.returncode = 2

            def wait(self, timeout=None):
                return 2

            def poll(self):
                return 2

            def kill(self):
                pass

        with tempfile.TemporaryDirectory() as d:
            rt = Runtime("claude", Path(d))
            with mock.patch("kettle.runtime.subprocess.Popen", return_value=FakeProc()):
                evs = list(rt.spawn("hi", cwd=d, session_id="pre"))
            self.assertTrue(any(
                e["t"] == "error" and "exited 2" in e["s"] for e in evs
            ))
            self.assertEqual(len(rt.ledger.turns("pre")), 1)


if __name__ == "__main__":
    unittest.main()
