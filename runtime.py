"""
Kettle agent runtime — the viewport-neutral adapter (v2 seed).

The prototype's right-pane agent borrows three things from the `claude` process that
the desk should own. This module takes them back, with no dependency on `server.py`,
so any viewport — the Electron shell today, the CLI tomorrow — drives the same adapter:

  1. **spawn** — run the headless agent, normalize its stream into clean client events
     (the SAME shapes `static/index.html` already reads: model · text · tool · done ·
     error — so this is drop-in — plus a live `usage` event).
  2. **usage** — correct context-occupancy vs. cumulative-spend accounting. The bug this
     fixes: the prototype drove the context bar from the `result` event's usage, which
     aggregates every internal model call in a turn, so cache re-reads got summed and the
     bar sailed past the window while the session was fine. Occupancy is a property of a
     *single* call; we read it from each `assistant` message and report the latest.
  3. **the session ledger** — the conversation lives in the desk
     (`.kettle/sessions/<id>.jsonl`), reconstructable and inspectable, instead of only
     in the agent process's private store. `--resume` still threads the live agent; the
     desk is now the source of truth.

Stdlib only. Pure functions (`build_cmd`, `normalize`, `UsageMeter`, `SessionLedger`) are
unit-tested without spawning `claude`; `Runtime.spawn` is the thin subprocess driver.

See `DESIGN.md` §3 (viewport-neutral architecture) and `LINEAGE.md` (state in files, not
borrowed from a process — the same cure applied to the conversation).
"""
from __future__ import annotations

import json
import re
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

class _TextGapFixer:
    """Insert paragraph breaks when consecutive text events glue prose together.

    Agents often emit separate assistant text blocks (between tools) that each end
    with a period and start the next with a capital — without a newline. Naive
    concat yields: ``...setup.Writing the desk proposal...``.
    """

    def __init__(self) -> None:
        self._tail = ""

    def feed(self, s: str) -> str:
        if not s:
            return s
        out = s
        if self._tail:
            a, b = self._tail[-1], s[0]
            if not a.isspace() and not b.isspace():
                ends_sentence = bool(re.search(r'[.!?…]"?$', self._tail))
                starts_block = bool(re.match(r"^[A-Z#*\d\-]", s)) or s.startswith("##") or s.startswith("---")
                if ends_sentence and starts_block:
                    out = "\n\n" + s
        self._tail = (self._tail + out)[-24:]
        return out


def normalize(lines: Iterable[str],
              meter: Optional[UsageMeter] = None,
              on_session: Optional[Callable[[str], None]] = None) -> Iterator[dict]:
    """Agent JSONL streams → Kettle client events.

    Understands:
      - Claude: system/init · assistant · result · error
      - Grok Build CLI: text/data · thought · end · error
      - Gemini CLI: init · message · tool_use · tool_result · result · error
      - Codex (`chatgpt`): thread.* · turn.* · item.* · error

    Drop-in client shapes: model · text · tool · usage · done · error.
    """
    meter = meter or UsageMeter()
    gap = _TextGapFixer()
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            ev = json.loads(line)
        except json.JSONDecodeError:
            continue
        for evt in _normalize_event(ev, meter, on_session):
            if evt.get("t") == "text" and isinstance(evt.get("s"), str):
                fixed = gap.feed(evt["s"])
                if fixed is not evt["s"]:
                    evt = {**evt, "s": fixed}
            yield evt


def _normalize_event(ev: dict, meter: UsageMeter,
                     on_session: Optional[Callable[[str], None]]) -> Iterator[dict]:
    t = ev.get("type")

    # --- Claude / Grok ---
    if t == "system" and ev.get("subtype") == "init":
        sid = ev.get("session_id")
        if sid and on_session:
            on_session(sid)
        yield {"t": "model", "s": ev.get("model", "?"), "session": sid}
        return

    if t == "assistant":
        msg = ev.get("message", {}) or {}
        for block in msg.get("content", []) or []:
            bt = block.get("type")
            if bt == "text" and block.get("text"):
                yield {"t": "text", "s": block["text"]}
            elif bt == "tool_use":
                inp = block.get("input", {}) or {}
                name = block.get("name", "tool")
                hint = (inp.get("file_path") or inp.get("pattern")
                        or inp.get("command") or "")
                yield {"t": "tool", "s": f"{name} {str(hint)[:120]}".strip(),
                       "tool": name, "path": inp.get("file_path")}
        usage = msg.get("usage")
        if usage:
            meter.feed_assistant(usage)
            yield {"t": "usage", **meter.snapshot()}
        return

    # --- Grok Build CLI (streaming-json): token deltas + terminal `end` ---
    if t == "text" and "data" in ev:
        data = ev.get("data")
        if data:
            yield {"t": "text", "s": str(data)}
        return

    if t == "thought":
        # Grok streams reasoning as thought tokens and does not emit discrete tool
        # events in streaming-json. Surface only a coarse activity signal: provider
        # reasoning text is not part of the public viewport contract.
        if ev.get("data"):
            yield {"t": "activity", "s": "thinking…", "kind": "thought"}
        return

    if t == "end":
        sid = ev.get("sessionId") or ev.get("session_id")
        if sid and on_session:
            on_session(sid)
        usage = ev.get("usage") if isinstance(ev.get("usage"), dict) else {}
        if usage:
            meter.feed_assistant({
                "input_tokens": int(usage.get("input_tokens") or 0),
                "cache_read_input_tokens": int(
                    usage.get("cache_read_input_tokens") or 0),
                "cache_creation_input_tokens": int(
                    usage.get("cache_creation_input_tokens") or 0),
                "output_tokens": int(usage.get("output_tokens") or 0),
            })
            yield {"t": "usage", **meter.snapshot()}
        model = "?"
        mu = ev.get("modelUsage")
        if isinstance(mu, dict) and mu:
            model = next(iter(mu))
        yield {"t": "model", "s": model, "session": sid}
        stop = str(ev.get("stopReason") or ev.get("stop_reason") or "").strip()
        err = None
        raw_err = ev.get("error")
        if isinstance(raw_err, dict):
            err = raw_err.get("message") or str(raw_err)
        elif isinstance(raw_err, str) and raw_err.strip():
            err = raw_err
        if not err and stop.lower() in (
            "cancelled", "canceled", "permission_cancelled", "error",
        ):
            err = f"curator turn cancelled ({stop})"
        snap = meter.snapshot()
        yield {
            "t": "done",
            "cost": None,
            "ctx": snap["context"] or None,
            "usage": snap,
            "error": err,
        }
        if err:
            yield {"t": "error", "s": err}
        return

    # --- Gemini CLI ---
    if t == "init":
        sid = ev.get("session_id")
        if sid and on_session:
            on_session(sid)
        yield {"t": "model", "s": ev.get("model", "?"), "session": sid}
        return

    if t == "message":
        role = (ev.get("role") or "").lower()
        if role in ("", "assistant", "model"):
            content = ev.get("content") if ev.get("content") is not None else ev.get("text")
            if content:
                yield {"t": "text", "s": str(content)}
        return

    if t == "tool_use" and "message" not in ev:
        # Top-level Gemini tool_use (Claude nests tool_use inside assistant)
        name = ev.get("tool_name") or ev.get("name") or "tool"
        inp = ev.get("parameters") or ev.get("input") or ev.get("args") or {}
        if not isinstance(inp, dict):
            inp = {}
        hint = (inp.get("file_path") or inp.get("path") or inp.get("pattern")
                or inp.get("command") or "")
        path = inp.get("file_path") or inp.get("path")
        yield {"t": "tool", "s": f"{name} {str(hint)[:120]}".strip(),
               "tool": name, "path": path}
        return

    if t == "tool_result":
        return  # ignore; progress was on tool_use

    # --- Codex (chatgpt) ---
    if t == "thread.started":
        sid = ev.get("thread_id") or ev.get("session_id")
        if sid and on_session:
            on_session(sid)
        yield {"t": "model", "s": ev.get("model") or "codex", "session": sid}
        return

    if t in ("item.started", "item.completed"):
        item = ev.get("item") or {}
        itype = item.get("type") or ""
        if itype == "agent_message" and t == "item.completed":
            text = item.get("text") or item.get("content") or ""
            if text:
                yield {"t": "text", "s": str(text)}
        elif itype == "command_execution":
            cmd = item.get("command") or ""
            yield {"t": "tool", "s": f"Bash {str(cmd)[:120]}".strip(),
                   "tool": "Bash", "path": None}
        elif itype in ("file_change", "file_edit", "apply_patch"):
            path = item.get("path") or item.get("file_path")
            if not path:
                changes = item.get("changes")
                if isinstance(changes, list) and changes and isinstance(changes[0], dict):
                    path = changes[0].get("path")
            hint = path or item.get("summary") or ""
            yield {"t": "tool", "s": f"Edit {str(hint)[:120]}".strip(),
                   "tool": "Edit", "path": path}
        elif itype == "mcp_tool_call":
            name = item.get("tool") or item.get("name") or "mcp"
            yield {"t": "tool", "s": str(name)[:120], "tool": name, "path": None}
        return

    if t == "turn.completed":
        usage = ev.get("usage") or {}
        if usage:
            meter.feed_assistant({
                "input_tokens": int(usage.get("input_tokens") or 0),
                "cache_read_input_tokens": int(usage.get("cached_input_tokens") or 0),
                "cache_creation_input_tokens": 0,
                "output_tokens": int(usage.get("output_tokens") or 0),
            })
            yield {"t": "usage", **meter.snapshot()}
        snap = meter.snapshot()
        yield {"t": "done", "cost": None, "ctx": snap["context"] or None,
               "usage": snap, "error": None}
        return

    if t == "turn.failed":
        msg = ev.get("error") or ev.get("message") or "turn failed"
        if isinstance(msg, dict):
            msg = msg.get("message") or msg.get("error") or str(msg)
        yield {"t": "error", "s": str(msg)}
        snap = meter.snapshot()
        yield {"t": "done", "cost": None, "ctx": snap["context"] or None,
               "usage": snap, "error": str(msg)}
        return

    # --- shared result / error (Claude, Grok, Gemini) ---
    if t == "result":
        # Gemini may include a final response string + stats; Claude uses usage/cost.
        resp = ev.get("response")
        if isinstance(resp, str) and resp.strip():
            yield {"t": "text", "s": resp}
        stats = ev.get("stats") if isinstance(ev.get("stats"), dict) else None
        if stats:
            # Best-effort occupancy from Gemini stats shapes
            models = stats.get("models") if isinstance(stats.get("models"), dict) else {}
            inp = out = cache = 0
            if models:
                for mstats in models.values():
                    if not isinstance(mstats, dict):
                        continue
                    tokens = mstats.get("tokens") if isinstance(mstats.get("tokens"), dict) else mstats
                    inp += int(tokens.get("input") or tokens.get("prompt") or 0)
                    out += int(tokens.get("output") or tokens.get("candidates") or 0)
                    cache += int(tokens.get("cached") or tokens.get("cache") or 0)
            else:
                inp = int(stats.get("input_tokens") or stats.get("promptTokenCount") or 0)
                out = int(stats.get("output_tokens") or stats.get("candidatesTokenCount") or 0)
            if inp or out or cache:
                meter.feed_assistant({
                    "input_tokens": inp, "cache_read_input_tokens": cache,
                    "cache_creation_input_tokens": 0, "output_tokens": out,
                })
                yield {"t": "usage", **meter.snapshot()}
        meter.feed_result(ev)
        snap = meter.snapshot()
        err = None
        if ev.get("is_error"):
            err = ev.get("subtype") or "error"
        elif isinstance(ev.get("error"), dict):
            err = ev["error"].get("message") or "error"
        elif isinstance(ev.get("error"), str):
            err = ev["error"]
        yield {
            "t": "done",
            "cost": ev.get("total_cost_usd"),
            "ctx": snap["context"] or None,
            "usage": snap,
            "error": err,
        }
        return

    if t == "error":
        msg = ev.get("message") or ev.get("error") or "curator error"
        if isinstance(msg, dict):
            msg = msg.get("message") or str(msg)
        yield {"t": "error", "s": str(msg)}
        return


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


# ---------- tool tiers (abstract) + dialect argv ----------

# Shell parts allowed under each tier. Claude needs each Bash(…) atomically;
# Grok receives the same rule strings via --allow.
SHELL_KIT = [
    "Bash(ls:*)", "Bash(cat:*)", "Bash(head:*)", "Bash(tail:*)", "Bash(echo:*)",
    "Bash(rg:*)", "Bash(grep:*)", "Bash(fd:*)", "Bash(find:*)", "Bash(wc:*)",
    # sed/awk are text transformers, but `sed -i` and awk's `print > file` write
    # arbitrary paths — same trusted-not-fenced caveat as SHELL_SWEEP below.
    "Bash(sed:*)", "Bash(awk:*)", "Bash(sort:*)", "Bash(uniq:*)", "Bash(diff:*)",
    "Bash(date:*)", "Bash(basename:*)", "Bash(dirname:*)", "Bash(mkdir:*)",
]

SHELL_CHAT = [
    "Bash(ls:*)", "Bash(cat:*)", "Bash(head:*)", "Bash(tail:*)",
    "Bash(rg:*)", "Bash(fd:*)", "Bash(find:*)", "Bash(wc:*)",
]

SHELL_SWEEP = [
    "Bash(ls:*)", "Bash(cat:*)", "Bash(rg:*)", "Bash(fd:*)", "Bash(find:*)",
    "Bash(diff:*)",
    # Restock/archive often shells through when Write is sticky — keep these tight.
    "Bash(mkdir:*)", "Bash(mv:*)", "Bash(cp:*)", "Bash(rm:*)", "Bash(tee:*)",
    # python/python3 removed 2026-07-20 (user ruling). Evidence: no prompt under
    # kits/ ever referenced them, and an interpreter is the widest possible escape —
    # one line writes anywhere the user can.
    #
    # HONEST RESIDUAL: what remains still takes arbitrary paths (rm/mv/cp/tee), as do
    # sed/awk in SHELL_KIT. A tool allowlist constrains WHICH binaries run, never WHERE
    # they write, so every shell-bearing tier is TRUSTED, NOT FENCED. Real enforcement
    # needs an OS sandbox around the curator process — docs/briefs/19-enforce-the-fence.md.
]

# Interview is tool-less: core precomputes a survey snapshot (survey.py) and injects it.
# SHELL_INTERVIEW retained only as documentation of the *former* explore allowlist.
SHELL_INTERVIEW: list[str] = []

# Tier name → (permission_mode | None, allow list, deny list)
# interview: empty allow + empty deny → tools_argv special-cases a true no-tools posture
# for every provider (founding trust ceremony without provider-specific refuse UX).
TOOL_TIERS: dict[str, tuple[Optional[str], list[str], list[str]]] = {
    "agent": (
        "acceptEdits",
        ["Read", "Glob", "Grep", "Edit", "Write", *SHELL_KIT, "Bash(mv:*)", "Bash(cp:*)"],
        ["NotebookEdit"],
    ),
    "chat": (
        "acceptEdits",
        ["Read", "Glob", "Grep", "Edit", "Write", *SHELL_CHAT],
        ["NotebookEdit"],
    ),
    "sweep": (
        "acceptEdits",
        ["Read", "Glob", "Grep", "Edit", "Write", *SHELL_SWEEP],
        ["NotebookEdit"],
    ),
    "interview": (
        None,
        [],
        [],
    ),
}

# ---------- per-provider capabilities (honest, derived from tools_argv above) ----------
#
# A tier is only as real as the provider's CLI makes it. Each boolean states what the
# provider *actually* guarantees under the argv `tools_argv` builds below — not what we
# wish it did. Kept beside TOOL_TIERS / tools_argv so a change to the builder and a change
# to this claim land in one diff (test_runtime cross-checks the load-bearing ones).
#
#   read_only_tier — the interview tier genuinely cannot write or run shell.
#       Founding interview is tool-less for every provider (core survey snapshot); so
#       all listed providers report True. Chat/sweep write posture is separate
#       (see fenced_writes).
#   tool_allowlist — write/chat tiers gated by a per-tool allowlist (claude/cli) rather
#       than a coarse sandbox / approval mode (chatgpt/gemini) or open Bash (grok).
#   resume — threads a prior session (--resume / `exec resume`).
#   effort — honors a reasoning-effort flag (EFFORT_BY_PROVIDER is non-empty; gemini none).
#   fenced_writes — write tiers stay inside the project cwd (allowlist or workspace
#       sandbox) rather than open Bash. grok write = bypassPermissions + open Bash → not
#       fenced.
PROVIDER_CAPABILITIES: dict[str, dict[str, bool]] = {
    "claude":  {"read_only_tier": True,  "tool_allowlist": True,  "resume": True, "effort": True,  "fenced_writes": True},
    "cli":     {"read_only_tier": True,  "tool_allowlist": True,  "resume": True, "effort": True,  "fenced_writes": True},
    "grok":    {"read_only_tier": True,  "tool_allowlist": False, "resume": True, "effort": True,  "fenced_writes": False},
    "chatgpt": {"read_only_tier": True,  "tool_allowlist": False, "resume": True, "effort": True,  "fenced_writes": True},
    "gemini":  {"read_only_tier": True,  "tool_allowlist": False, "resume": True, "effort": False, "fenced_writes": True},
}

CAPABILITY_KEYS = ("read_only_tier", "tool_allowlist", "resume", "effort", "fenced_writes")


def capabilities_for(provider: str) -> dict[str, bool]:
    """Honest capability booleans for a provider. Unknown providers get the weakest
    guarantees (all False) so read-only enforcement refuses rather than assumes."""
    provider = "chatgpt" if provider == "codex" else provider
    caps = PROVIDER_CAPABILITIES.get(provider)
    if caps is None:
        return {k: False for k in CAPABILITY_KEYS}
    return dict(caps)


def guarantees_read_only(provider: str) -> bool:
    """True iff the provider's read-only (interview) tier truly cannot write or run shell."""
    return capabilities_for(provider)["read_only_tier"]


# Providers that accept Claude-style --append-system-prompt / --name / --verbose
CLAUDE_FAMILY = frozenset({"claude", "cli"})
# Providers that take system text as prompt prefix (no dedicated flag)
PROMPT_PREFIX_SYSTEM = frozenset({"chatgpt", "gemini"})


def _provider_of(cfg) -> str:
    if cfg is None:
        return "claude"
    if isinstance(cfg, str):
        p = cfg
    else:
        p = getattr(cfg, "provider", None) or "claude"
    return "chatgpt" if p == "codex" else p


def tools_argv(tier: str, provider: str = "claude") -> list[str]:
    """Map an abstract tool tier to provider-specific CLI flags."""
    provider = "chatgpt" if provider == "codex" else provider
    spec = TOOL_TIERS.get(tier)
    if not spec:
        return []
    mode, allow, deny = spec
    write = mode == "acceptEdits"

    # Tool-less founding interview: survey is precomputed by core (survey.py).
    # No open shell, no always-approve — pure generation under every provider.
    if tier == "interview":
        if provider == "chatgpt":
            return ["--sandbox", "read-only"]
        if provider == "gemini":
            return ["--approval-mode", "plan", "--skip-trust"]
        if provider == "grok":
            # plan = no project writes; no --allow Bash / --always-approve
            return ["--permission-mode", "plan"]
        # Claude / cli: empty allowlist (no tools registered for the turn)
        return ["--allowedTools"]

    if provider == "chatgpt":
        # Codex: sandbox policy stands in for tool allowlists
        if not write and not allow:
            return ["--sandbox", "read-only"]
        if write:
            return ["--sandbox", "workspace-write"]
        return ["--sandbox", "read-only"]

    if provider == "gemini":
        # Gemini: approval-mode ≈ Claude permission-mode
        if write:
            return ["--approval-mode", "auto_edit", "--skip-trust"]
        if allow:  # read-only with tools
            return ["--approval-mode", "plan", "--skip-trust"]
        return ["--skip-trust"]

    if provider == "grok":
        if not allow and not deny and not mode:
            return []
        out: list[str] = []
        # Headless desk work must not stop for approval prompts. Fine-grained
        # Claude Bash(ls:*) allowlists also abort Grok turns: a native
        # run_terminal_command outside the list resolves as cancelled and the
        # whole turn ends (permission_cancelled) — see Principles sweep 2026-07-13.
        #
        # Never pass Claude's `--deny NotebookEdit` to Grok: that rule string is
        # mis-parsed as a blanket edit deny ("Write tool denied by permission
        # policy"), so sweeps report "write policy blocked all mutations" while
        # queue/archive stay untouched. Grok has no NotebookEdit tool; omit it.
        # CLI `--permission-mode acceptEdits` is also a no-op on Grok today —
        # only bypassPermissions / --always-approve take effect (Grok docs).
        def _grok_deny_rules(rules: list[str]) -> list[str]:
            skip = {"NotebookEdit", "Notebook"}
            bits: list[str] = []
            for rule in rules:
                if str(rule) in skip:
                    continue
                bits += ["--deny", rule]
            return bits

        if write:
            out += [
                "--always-approve",
                "--permission-mode", "bypassPermissions",
                "--allow", "Read",
                "--allow", "Write",
                "--allow", "Edit",
                "--allow", "Bash",
            ]
            out += _grok_deny_rules(deny)
            return out
        if mode:
            out += ["--permission-mode", mode]
        out += ["--always-approve"]
        # Coalesce Claude Bash(cmd:*) fragments into open Bash — same cancel risk.
        saw_bash = False
        for rule in allow:
            if str(rule).startswith("Bash"):
                saw_bash = True
                continue
            out += ["--allow", rule]
        if saw_bash:
            out += ["--allow", "Bash"]
        out += _grok_deny_rules(deny)
        return out

    # Claude / cli
    if not allow and not deny and not mode:
        return []
    out = []
    if mode:
        out += ["--permission-mode", mode]
    if allow:
        out += ["--allowedTools", *allow]
    if deny:
        out += ["--disallowedTools", *deny]
    return out


def system_append_argv(text: str, provider: str = "claude") -> list[str]:
    """Extra system / rules argv flags (empty when the provider wants a prompt prefix)."""
    if not text:
        return []
    provider = "chatgpt" if provider == "codex" else provider
    if provider in PROMPT_PREFIX_SYSTEM:
        return []  # folded into the prompt by build_argv
    if provider == "grok":
        return ["--rules", text]
    return ["--append-system-prompt", text]


def effort_argv(effort: Optional[str], provider: str = "claude") -> list[str]:
    """Map a Kettle effort level onto provider CLI flags.

    Level names vary by backend (Claude: low…max; Grok: none…xhigh;
    Codex: low…ultra). Empty / 'default' omits the flag. Gemini CLI has no
    effort switch today — returns []. Unsupported values are still passed
    through (the CLI rejects or ignores them).
    """
    if not effort:
        return []
    level = str(effort).strip()
    if not level or level.lower() == "default":
        return []
    provider = "chatgpt" if provider == "codex" else provider
    if provider == "gemini":
        return []
    if provider == "grok":
        return ["--reasoning-effort", level]
    if provider == "chatgpt":
        # Codex: -c model_reasoning_effort=<level>
        return ["-c", f"model_reasoning_effort={level}"]
    # Claude / cli
    return ["--effort", level]


def session_name_argv(name: str, provider: str = "claude") -> list[str]:
    """Claude supports --name; others rely on desk session.json."""
    provider = "chatgpt" if provider == "codex" else provider
    if not name or provider not in CLAUDE_FAMILY:
        return []
    return ["--name", name]


def _with_system_prefix(prompt: str, system_append: Optional[str], provider: str) -> str:
    if not system_append or provider not in PROMPT_PREFIX_SYSTEM:
        return prompt
    return (
        "[System orientation — honor for this turn]\n"
        + system_append.strip()
        + "\n\n— · —\n\n"
        + prompt
    )


def build_cmd(claude: str, prompt: str, session_id: Optional[str] = None,
              extra: Optional[list] = None, *,
              provider: str = "claude",
              output_format: Optional[str] = None) -> list:
    """Headless argv for Claude / Grok / Gemini / Codex (chatgpt)."""
    provider = "chatgpt" if provider == "codex" else provider
    extra = list(extra or [])

    if provider == "chatgpt":
        # codex exec [--json] … PROMPT   OR   codex exec resume SID [--json] PROMPT
        if session_id:
            cmd = [claude, "exec", "resume", session_id, "--json"]
        else:
            cmd = [claude, "exec", "--json", "--skip-git-repo-check"]
        cmd += extra
        cmd.append(prompt)
        return cmd

    if provider == "gemini":
        cmd = [claude, "-p", prompt, "--output-format",
               output_format or "stream-json"]
        if session_id:
            cmd += ["--resume", session_id]
        cmd += extra
        return cmd

    if provider == "grok":
        fmt = output_format or "streaming-json"
        cmd = [claude, "-p", prompt, "--output-format", fmt]
        if session_id:
            cmd += ["--resume", session_id]
        cmd += extra
        return cmd

    # Claude / cli
    fmt = output_format or "stream-json"
    cmd = [claude, "-p", prompt, "--output-format", fmt, "--verbose"]
    if session_id:
        cmd += ["--resume", session_id]
    cmd += extra
    return cmd


def build_argv(cfg, prompt: str, *,
               session_id: Optional[str] = None,
               system_append: Optional[str] = None,
               session_name: Optional[str] = None,
               tools_tier: Optional[str] = None,
               model: Optional[str] = None,
               effort: Optional[str] = None,
               extra: Optional[list] = None) -> list:
    """Full dialect-aware argv from a CuratorConfig (or provider string + command)."""
    if isinstance(cfg, str):
        provider, command = _provider_of(cfg), cfg
    else:
        provider = _provider_of(cfg)
        command = cfg.resolved_command() if hasattr(cfg, "resolved_command") else str(
            getattr(cfg, "command", "claude")
        )
    prompt = _with_system_prefix(prompt, system_append, provider)
    bits: list[str] = []
    if model:
        bits += ["--model", model]
    if effort:
        bits += effort_argv(effort, provider)
    if system_append:
        bits += system_append_argv(system_append, provider)
    if session_name and not session_id:
        bits += session_name_argv(session_name, provider)
    if tools_tier:
        bits += tools_argv(tools_tier, provider)
    if extra:
        bits += list(extra)
    return build_cmd(command, prompt, session_id, bits, provider=provider)


class Runtime:
    """spawn(role, message, session?) → normalized event stream, with the turn persisted
    to the desk ledger on completion. The one piece that touches the process world; kept
    thin so the testable logic (above) stays pure."""

    def __init__(self, claude: str, sessions_dir: Path | str, window: int = DEFAULT_WINDOW,
                 provider: str = "claude"):
        self.claude = claude
        self.provider = provider
        self.ledger = SessionLedger(sessions_dir)
        self.window = window

    def spawn(self, prompt: str, cwd: Path | str, session_id: Optional[str] = None,
              role: str = "chat", extra: Optional[list] = None,
              cmd: Optional[list] = None) -> Iterator[dict]:
        meter = UsageMeter(self.window)
        cap = {"sid": session_id, "text": [], "tools": [], "edits": []}
        # A caller that resolved the provider from settings (e.g. the CLI via
        # server.build_turn_cmd → build_argv) may pass a fully-built argv; otherwise
        # build the Claude-dialect default here. `prompt`/`session_id` still drive the
        # ledger + capture regardless.
        if cmd is None:
            cmd = build_cmd(self.claude, prompt, session_id, extra, provider=self.provider)
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
                yield {"t": "error", "s": f"curator exited {proc.returncode}"}
        finally:
            if cap["sid"]:
                self.ledger.append_turn(cap["sid"], role, prompt,
                                        agent_text="".join(cap["text"]),
                                        tools=cap["tools"], usage=meter.snapshot())
            if cap["edits"]:
                try:
                    lineage.log_agent_edits(cwd, cap["edits"], actor=role,
                                            session=cap["sid"] or "")
                except OSError:
                    pass
            if proc.poll() is None:
                proc.kill()
