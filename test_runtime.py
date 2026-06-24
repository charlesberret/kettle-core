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
from runtime import UsageMeter, SessionLedger, build_cmd, normalize


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

    def test_resume_threads_the_session(self):
        cmd = build_cmd("claude", "hi", session_id="s1", extra=["--add-dir", "/p"])
        self.assertIn("--resume", cmd)
        self.assertEqual(cmd[cmd.index("--resume") + 1], "s1")
        self.assertIn("--add-dir", cmd)


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
