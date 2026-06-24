"""
Setsweep agent runtime — the viewport-neutral adapter (v2 seed).

The prototype's right-pane agent borrows three things from the `claude` process that
the desk should own. This module takes them back, with no dependency on `server.py`,
so any viewport — the pywebview app today, a CLI tomorrow — drives the same adapter:

  1. **spawn** — run the headless agent, normalize its stream into clean client events
     (the SAME shapes `static/index.html` already reads: model · text · tool · done ·
     error — so this is drop-in — plus a live `usage` event).
  2. **usage** — correct context-occupancy vs. cumulative-spend accounting. The bug this
     fixes: the prototype drove the context bar from the `result` event's usage, which
     aggregates every internal model call in a turn, so cache re-reads got summed and the
     bar sailed past the window while the session was fine. Occupancy is a property of a
     *single* call; we read it from each `assistant` message and report the latest.
  3. **the session ledger** — the conversation lives in the desk
     (`.setsweep/sessions/<id>.jsonl`), reconstructable and inspectable, instead of only
     in the agent process's private store. `--resume` still threads the live agent; the
     desk is now the source of truth.

Stdlib only. Pure functions (`build_cmd`, `normalize`, `UsageMeter`, `SessionLedger`) are
unit-tested without spawning `claude`; `Runtime.spawn` is the thin subprocess driver.

See `DESIGN.md` §3 (viewport-neutral architecture) and `LINEAGE.md` (state in files, not
borrowed from a process — the same cure applied to the conversation).
"""
from __future__ import annotations

import json
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Callable, Iterable, Iterator, Optional

import lineage

DEFAULT_WINDOW = 200_000


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


# ---------- usage: context-occupancy vs. cumulative spend ----------

class UsageMeter:
    """Two honest numbers, correctly sourced.

    `context_tokens` — how full the window is *right now*: the tokens sent to the model
    on the latest call (non-cached input + cache read + cache creation). Bounded by the
    window, because it is one call, not a turn's worth of summed cache re-reads.

    `cost_usd` / `output_tokens` — the billing side, cumulative. A different quantity,
    kept separate, never mixed into the context bar.
    """

    def __init__(self, window: int = DEFAULT_WINDOW):
        self.window = window
        self.context_tokens = 0   # latest single-call occupancy
        self.peak_tokens = 0      # high-water occupancy this turn
        self.output_tokens = 0    # cumulative output (billing-side)
        self.cost_usd = 0.0

    @staticmethod
    def occupancy(usage: dict) -> int:
        """One call's context: non-cached input + cache read + cache creation."""
        return sum(int(usage.get(k) or 0) for k in (
            "input_tokens", "cache_read_input_tokens", "cache_creation_input_tokens"))

    def feed_assistant(self, usage: dict) -> None:
        occ = self.occupancy(usage)
        if occ:
            self.context_tokens = occ
            self.peak_tokens = max(self.peak_tokens, occ)
        self.output_tokens += int(usage.get("output_tokens") or 0)

    def feed_result(self, ev: dict) -> None:
        # Cost comes from the result; its `usage` is deliberately NOT used for context —
        # that aggregate-as-occupancy read is exactly the bug being fixed.
        cost = ev.get("total_cost_usd")
        if cost is not None:
            self.cost_usd = float(cost)

    @property
    def fraction(self) -> float:
        return min(1.0, self.context_tokens / self.window) if self.window else 0.0

    def snapshot(self) -> dict:
        return {
            "context": self.context_tokens,
            "peak": self.peak_tokens,
            "window": self.window,
            "output": self.output_tokens,
            "cost": round(self.cost_usd, 4),
            "fraction": round(self.fraction, 3),
        }


# ---------- stream normalization ----------

def normalize(lines: Iterable[str],
              meter: Optional[UsageMeter] = None,
              on_session: Optional[Callable[[str], None]] = None) -> Iterator[dict]:
    """claude stream-json lines → Setsweep client events.

    Drop-in: emits the shapes the current frontend reads (model/text/tool/done/error).
    Additive: a live `usage` event per assistant message lets a viewport drive a correct,
    live context bar instead of one (wrong) number at the end. `done.ctx` is now the
    real single-call occupancy, not the turn aggregate.
    """
    meter = meter or UsageMeter()
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            ev = json.loads(line)
        except json.JSONDecodeError:
            continue
        t = ev.get("type")
        if t == "system" and ev.get("subtype") == "init":
            sid = ev.get("session_id")
            if sid and on_session:
                on_session(sid)
            yield {"t": "model", "s": ev.get("model", "?"), "session": sid}
        elif t == "assistant":
            msg = ev.get("message", {})
            for block in msg.get("content", []):
                bt = block.get("type")
                if bt == "text" and block.get("text"):
                    yield {"t": "text", "s": block["text"]}
                elif bt == "tool_use":
                    inp = block.get("input", {}) or {}
                    name = block.get("name", "tool")
                    hint = inp.get("file_path") or inp.get("pattern") or inp.get("command") or ""
                    # `tool` + `path` let consumers auto-log file edits to the lineage record
                    yield {"t": "tool", "s": f"{name} {str(hint)[:120]}".strip(),
                           "tool": name, "path": inp.get("file_path")}
            usage = msg.get("usage")
            if usage:
                meter.feed_assistant(usage)
                yield {"t": "usage", **meter.snapshot()}
        elif t == "result":
            meter.feed_result(ev)
            snap = meter.snapshot()
            yield {
                "t": "done",
                "cost": ev.get("total_cost_usd"),
                "ctx": snap["context"] or None,   # correct occupancy, not the aggregate
                "usage": snap,
                "error": ev.get("subtype") if ev.get("is_error") else None,
            }


# ---------- the desk-owned session ledger ----------

class SessionLedger:
    """The conversation, owned by the desk. One JSONL per session, one record per turn —
    reconstructable, inspectable, viewport-portable, and immune to the agent process's
    private store moving or pruning. `--resume` threads the live agent; this is truth."""

    def __init__(self, sessions_dir: Path | str):
        self.dir = Path(sessions_dir)

    def path(self, session_id: str) -> Path:
        return self.dir / f"{session_id}.jsonl"

    def append_turn(self, session_id: str, role: str, message: str,
                    agent_text: str = "", tools: Optional[list] = None,
                    usage: Optional[dict] = None, ts: Optional[str] = None) -> dict:
        rec = {"ts": ts or _now(), "role": role, "message": message,
               "agent_text": agent_text, "tools": tools or [], "usage": usage or {}}
        self.dir.mkdir(parents=True, exist_ok=True)
        with self.path(session_id).open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        return rec

    def turns(self, session_id: str) -> list[dict]:
        p = self.path(session_id)
        if not p.exists():
            return []
        return [json.loads(ln) for ln in p.read_text(encoding="utf-8").splitlines() if ln.strip()]


# ---------- command construction + the spawn driver ----------

def build_cmd(claude: str, prompt: str, session_id: Optional[str] = None,
              extra: Optional[list] = None) -> list:
    cmd = [claude, "-p", prompt, "--output-format", "stream-json", "--verbose"]
    if session_id:
        cmd += ["--resume", session_id]
    if extra:
        cmd += list(extra)
    return cmd


class Runtime:
    """spawn(role, message, session?) → normalized event stream, with the turn persisted
    to the desk ledger on completion. The one piece that touches the process world; kept
    thin so the testable logic (above) stays pure."""

    def __init__(self, claude: str, sessions_dir: Path | str, window: int = DEFAULT_WINDOW):
        self.claude = claude
        self.ledger = SessionLedger(sessions_dir)
        self.window = window

    def spawn(self, prompt: str, cwd: Path | str, session_id: Optional[str] = None,
              role: str = "chat", extra: Optional[list] = None) -> Iterator[dict]:
        meter = UsageMeter(self.window)
        cap = {"sid": session_id, "text": [], "tools": [], "edits": []}
        cmd = build_cmd(self.claude, prompt, session_id, extra)
        proc = subprocess.Popen(cmd, cwd=str(cwd), stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, text=True)
        assert proc.stdout is not None
        try:
            for evt in normalize(proc.stdout, meter, lambda s: cap.__setitem__("sid", s)):
                if evt["t"] == "text":
                    cap["text"].append(evt["s"])
                elif evt["t"] == "tool":
                    cap["tools"].append(evt["s"])
                    if evt.get("tool") in lineage.WRITE_TOOLS and evt.get("path"):
                        cap["edits"].append(evt["path"])
                yield evt
            proc.wait(timeout=10)
            if proc.returncode not in (0, None, -9):
                yield {"t": "error", "s": f"claude exited {proc.returncode}"}
        finally:
            if cap["sid"]:
                self.ledger.append_turn(cap["sid"], role, prompt,
                                        agent_text="".join(cap["text"]),
                                        tools=cap["tools"], usage=meter.snapshot())
            if cap["edits"]:                          # the agent's file edits self-record
                try:
                    lineage.log_agent_edits(cwd, cap["edits"], actor=role,
                                            session=cap["sid"] or "")
                except OSError:
                    pass
            if proc.poll() is None:
                proc.kill()
