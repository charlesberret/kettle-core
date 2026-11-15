"""API.md contract drift tests — documented JSON keys must match live handlers.

Fixtures mirror tests/test_server.ServerFixture: temp registry, two-file queue, live
server on an ephemeral port. Parses ```kettle-contract blocks from API.md.
"""

from __future__ import annotations

import json
import re
import unittest
import urllib.request
from pathlib import Path

import kettle.server as server

from test_server import ServerFixture, _auth_headers, _http

ROOT = Path(__file__).resolve().parents[1]
API_MD = ROOT / "API.md"
CONTRACT_RE = re.compile(
    r"```kettle-contract\n(.*?)\n```",
    re.DOTALL,
)


def load_api_contracts() -> list[dict]:
    text = API_MD.read_text(encoding="utf-8")
    out: list[dict] = []
    for block in CONTRACT_RE.findall(text):
        for line in block.strip().splitlines():
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out


def contract_by_scope(contracts: list[dict], scope: str) -> dict | None:
    for c in contracts:
        if c.get("scope") == scope:
            return c
    return None


def route_contract(contracts: list[dict], method: str, path: str) -> dict | None:
    for c in contracts:
        if c.get("scope") == "route" and c.get("method") == method and c.get("path") == path:
            return c
    return None


def assert_key_parity(doc_keys: set[str], live: dict, *, label: str) -> None:
    live_keys = set(live.keys())
    undocumented = live_keys - doc_keys
    missing = doc_keys - live_keys
    if undocumented:
        raise AssertionError(
            f"{label}: handler returned undocumented keys {sorted(undocumented)}"
        )
    if missing:
        raise AssertionError(
            f"{label}: API.md documents keys absent from live JSON {sorted(missing)}"
        )


class ApiContractDocs(ServerFixture):
    """Exercise documented shapes against the same queue fixture as test_server."""

    @classmethod
    def setUpClass(cls):
        cls.contracts = load_api_contracts()

    def setUp(self):
        super().setUp()
        root_s = str(self.root)
        self.write_queue([
            {
                "id": "alpha",
                "title": "Alpha — first",
                "path": str(self.root / "alpha.md"),
                "project": "Test",
                "project_root": root_s,
                "status": "pending",
                "urgency": "high",
                "ask_type": "tuning",
                "ask": "Review tone",
                "unblocks": "—",
                "brief": "Alpha brief for contract test.",
                "desk_item": None,
                "source": str(self.root / "inbox" / "alpha-src.md"),
            },
            {
                "id": "beta",
                "title": "Beta — second",
                "path": str(self.root / "beta.md"),
                "project": "Test",
                "project_root": root_s,
                "status": "approved",
                "approved": "2026-11-01",
                "urgency": "low",
                "ask_type": "judgment",
                "ask": "Sign off",
                "brief": "Beta brief.",
            },
            {
                "id": "gamma",
                "title": "Gamma — set aside",
                "path": str(self.root / "gamma.md"),
                "project": "Test",
                "project_root": root_s,
                "status": "set-aside",
                "set_aside": "2026-11-02",
                "urgency": "medium",
                "ask_type": "fill",
                "ask": "Fill gaps",
                "brief": "Gamma brief.",
            },
            {
                "id": server.PROPOSAL_ENTRY_ID,
                "title": "Proposal",
                "path": str(server.proposal_path(self.proj())),
                "project": "Test",
                "project_root": root_s,
                "status": "pending",
                "founding_phase": "proposal",
                "ask_type": "judgment",
                "ask": "Approve the plan",
                "urgency": "high",
                "brief": "Founding proposal entry for contract coverage.",
            },
        ])
        server.proposal_path(self.proj()).parent.mkdir(parents=True, exist_ok=True)
        server.proposal_path(self.proj()).write_text("# Proposal\n")
        (self.root / "alpha.md").write_text("alpha body\n")
        (self.root / "beta.md").write_text("beta body\n")
        (self.root / "gamma.md").write_text("gamma body\n")
        (self.root / "inbox").mkdir(exist_ok=True)
        (self.root / "inbox" / "alpha-src.md").write_text("upstream\n")
        server.comments_log_path(self.proj()).write_text(
            "2026-06-29\talpha\tlogged note\n"
        )
        _http("POST", f"{self.base}/api/comment",
              {"project": "t", "id": "alpha", "text": "sticky note"})

    def test_queue_envelope_and_entry_keys(self):
        env = contract_by_scope(self.contracts, "queue-envelope")
        entry_doc = contract_by_scope(self.contracts, "queue-entry")
        self.assertIsNotNone(env)
        self.assertIsNotNone(entry_doc)
        doc_entry_keys = set(entry_doc["keys"])

        s, q = _http("GET", f"{self.base}/api/queue?project=t&mutate=0")
        self.assertEqual(s, 200)
        assert_key_parity(set(env["keys"]), q, label="GET /api/queue envelope")

        seen_live: set[str] = set()
        for ent in q["entries"]:
            seen_live |= set(ent.keys())
            extra = set(ent.keys()) - doc_entry_keys
            self.assertFalse(
                extra,
                f"queue entry {ent.get('id')!r} has undocumented keys {sorted(extra)}",
            )
        undocumented = seen_live - doc_entry_keys
        self.assertFalse(undocumented, f"union of live entry keys not in API.md: {sorted(undocumented)}")
        missing = doc_entry_keys - seen_live
        self.assertFalse(
            missing,
            f"API.md queue-entry keys never observed in fixture: {sorted(missing)}",
        )

    def test_tier4_route_keys(self):
        cases = [
            ("GET", "/api/kits", None, f"{self.base}/api/kits"),
            ("GET", "/api/lineage", None, f"{self.base}/api/lineage?project=t"),
            ("POST", "/api/lineage/resolve",
             {"project": "t", "path": "alpha.md", "as": "user"},
             f"{self.base}/api/lineage/resolve"),
            ("POST", "/api/lineage/accept", {"project": "t"}, f"{self.base}/api/lineage/accept"),
            ("POST", "/api/lineage/bind", {"project": "t"}, f"{self.base}/api/lineage/bind"),
            ("POST", "/api/entry",
             {"project": "t", "id": "alpha", "fields": {"urgency": "medium"}},
             f"{self.base}/api/entry"),
            ("GET", "/api/diff", None, f"{self.base}/api/diff?project=t&id=alpha"),
            ("GET", "/api/diffstat", None, f"{self.base}/api/diffstat?project=t&id=alpha"),
            ("GET", "/api/admin", None, f"{self.base}/api/admin?project=t"),
        ]
        _http("GET", f"{self.base}/api/queue?project=t")  # snapshots for diff routes
        (self.root / "alpha.md").write_text("alpha body\nchanged\n")

        for method, path, body, url in cases:
            c = route_contract(self.contracts, method, path)
            self.assertIsNotNone(c, f"missing kettle-contract for {method} {path}")
            if method == "GET":
                status, payload = _http("GET", url)
            else:
                status, payload = _http("POST", url, body)
            self.assertEqual(status, 200, (method, path, payload))
            assert_key_parity(set(c["keys"]), payload, label=f"{method} {path}")

    def test_refound_response_keys(self):
        c = route_contract(self.contracts, "POST", "/api/projects/refound")
        self.assertIsNotNone(c)
        s, payload = _http("POST", f"{self.base}/api/projects/refound", {"id": "t"})
        self.assertEqual(s, 200)
        assert_key_parity(set(c["keys"]), payload, label="POST /api/projects/refound")

    def test_stream_event_kinds_documented(self):
        kinds = contract_by_scope(self.contracts, "stream-event")
        self.assertIsNotNone(kinds)
        allowed = set(kinds["keys"])
        req = urllib.request.Request(
            f"{self.base}/api/compact",
            data=json.dumps({"project": "t"}).encode(),
            method="POST",
        )
        for k, v in _auth_headers({"Content-Type": "application/json"}).items():
            req.add_header(k, v)
        with urllib.request.urlopen(req, timeout=10) as r:
            self.assertEqual(r.status, 200)
            events = [json.loads(line) for line in r.read().decode().splitlines() if line.strip()]
        self.assertTrue(events)
        self.assertEqual(events[-1].get("t"), "done")
        for ev in events:
            t = ev.get("t")
            self.assertIn(t, allowed, f"stream event {t!r} not listed in API.md streaming contract")


if __name__ == "__main__":
    unittest.main()
