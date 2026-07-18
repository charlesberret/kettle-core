#!/usr/bin/env python3
"""Unit tests for runtime.py — the viewport-neutral agent adapter.

Stdlib only (unittest). Run:  python3 test_runtime.py   (or python3 -m unittest)

The two tests that matter most are the regressions for the haywire token bar:
`test_context_is_single_call_not_turn_aggregate` and
`test_done_ctx_ignores_result_aggregate` — they pin the exact bug (summing a turn's
cache re-reads into the context bar so it sails past the window) so it can't return.
"""
import json
import tempfile
import unittest
from pathlib import Path

import runtime
from runtime import (
    UsageMeter, SessionLedger, build_cmd, build_argv, normalize,
    tools_argv, system_append_argv, effort_argv,
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
                {"type": "text", "text": "Desk proposal filed — edit it next."}]}}),
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


if __name__ == "__main__":
    unittest.main()
