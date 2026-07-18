import json
import tempfile
import unittest
from pathlib import Path

import kits


class KitsTest(unittest.TestCase):
    def setUp(self):
        # the real shipped kits, beside this test
        self.shipped = Path(__file__).resolve().parent / "kits"

    # ---- defaults ----

    def test_load_defaults_has_all_kinds(self):
        d = kits.load_defaults(self.shipped)
        self.assertEqual(set(d), set(kits.KINDS))
        self.assertEqual(set(kits.KINDS), {"writing", "code", "records", "knowledge", "inbox"})
        for kind, kit in d.items():
            self.assertEqual(kit["kind"], kind)
            self.assertTrue(kit["lens"] and kit["urgency"] and kit["firstQueue"])
            self.assertEqual(kit["tools"], [])          # defaults ship builtins-only
            self.assertTrue(kit["sweepChecks"])

    def test_underscore_files_skipped(self):
        # _base.md is markdown, not a kit; load_defaults only globs *.json and skips _*
        self.assertNotIn("_base", kits.load_defaults(self.shipped))

    def test_load_defaults_missing_dir(self):
        self.assertEqual(kits.load_defaults(Path("/nope/kits")), {})

    # ---- resolution ----

    def test_resolve_kind(self):
        self.assertEqual(kits.resolve("writing", self.shipped)["kind"], "writing")

    def test_inbox_kit_resolves_and_renders(self):
        kit = kits.resolve("inbox", self.shipped)
        self.assertIsNotNone(kit)
        self.assertEqual(kit["kind"], "inbox")
        # the review lens names the inbox inversion: the artifact is the response, not the item
        self.assertIn("RESPONSE", kit["lens"])
        # the sweep self-check asserts the staging-not-transmitting invariant
        sweep_ctx = kits.as_context(kit, "sweep")
        self.assertIn("outbound", sweep_ctx)
        self.assertIn("never transmitted", sweep_ctx)

    def test_resolve_none_and_unknown(self):
        self.assertIsNone(kits.resolve(None, self.shipped))
        self.assertIsNone(kits.resolve("nonsense", self.shipped))

    def test_user_kit_overrides_default(self):
        settings = {"kits": {"writing": {"name": "My writing", "kind": "writing", "lens": "X"}}}
        self.assertEqual(kits.resolve("writing", self.shipped, settings)["name"], "My writing")

    def test_custom_user_kit_by_name(self):
        settings = {"kits": {"My Special": {"name": "My Special", "kind": "custom", "lens": "Y"}}}
        self.assertEqual(kits.resolve("My Special", self.shipped, settings)["lens"], "Y")

    def test_for_project(self):
        self.assertEqual(kits.for_project({"kit": "knowledge"}, self.shipped)["kind"], "knowledge")
        self.assertIsNone(kits.for_project({}, self.shipped))     # unassigned → None

    # ---- rendering ----

    def test_as_context_modes(self):
        kit = kits.resolve("code", self.shipped)
        rev = kits.as_context(kit, "review")
        self.assertIn("Review lens:", rev)
        self.assertIn("Urgency rubric:", rev)
        swp = kits.as_context(kit, "sweep")
        self.assertIn("Sweep self-check", swp)
        self.assertTrue(swp.count("\n- ") >= 1)
        fnd = kits.as_context(kit, "found")
        self.assertIn("First-queue heuristic:", fnd)
        iv = kits.as_context(kit, "interview")
        self.assertIn("Founding prompt list", iv)
        self.assertIn("[status]", iv)
        self.assertIn("[sweep_actions]", iv)
        self.assertIn("[priority]", iv)  # kit-specific stem
        self.assertIn("Kit default lens", iv)

    def test_interview_stems_merge_base_and_kit(self):
        stems = kits.interview_stems(kits.resolve("inbox", self.shipped))
        ids = [s["id"] for s in stems]
        self.assertEqual(ids[0], "status")
        self.assertIn("sweep_actions", ids)
        self.assertIn("fleet", ids)
        self.assertIn("priority", ids)
        # inbox overrides sweep_actions options: staging drafts for send leads the list
        sa = next(s for s in stems if s["id"] == "sweep_actions")
        self.assertIn("sending", sa["options"][0].lower())
        fl = next(s for s in stems if s["id"] == "fleet")
        self.assertTrue(any("coding agents" in o.lower() for o in fl["options"]))

    def test_interview_without_kit_still_has_base(self):
        iv = kits.as_context({"name": "general", "interview": []}, "interview")
        self.assertIn("[sweep_actions]", iv)
        self.assertIn("[fleet]", iv)
        self.assertNotIn("Kit default lens", iv)

    def test_as_context_empty(self):
        self.assertEqual(kits.as_context(None, "review"), "")
        self.assertEqual(kits.as_context({"name": "x"}, "sweep"), "")  # no checks → ''

    # ---- tools ----

    # ---- list_kits (the editor's view) ----

    def test_list_kits_defaults_only(self):
        lst = kits.list_kits(self.shipped)
        self.assertEqual(len(lst), len(kits.KINDS))
        self.assertTrue(all(k["_source"] == "default" for k in lst))
        self.assertEqual({k["_key"] for k in lst}, set(kits.KINDS))

    def test_list_kits_user_override_and_custom(self):
        settings = {"kits": {
            "writing": {"name": "My writing", "kind": "writing", "lens": "X"},   # overrides a default
            "Investigations": {"name": "Investigations", "kind": "custom", "lens": "Y"},  # custom
        }}
        lst = kits.list_kits(self.shipped, settings)
        by_key = {k["_key"]: k for k in lst}
        self.assertEqual(by_key["writing"]["_source"], "user")
        self.assertEqual(by_key["writing"]["name"], "My writing")
        self.assertEqual(by_key["code"]["_source"], "default")            # untouched default
        self.assertEqual(by_key["Investigations"]["_source"], "user")     # custom appears
        self.assertEqual(len(lst), len(kits.KINDS) + 1)

    def test_extra_tools_filters_builtins(self):
        kit = {"tools": [{"type": "builtin", "ref": "Read"},
                         {"type": "skill", "ref": "notes"},
                         {"type": "mcp", "ref": "arena-mcp"}]}
        refs = [t["ref"] for t in kits.extra_tools(kit)]
        self.assertEqual(refs, ["notes", "arena-mcp"])
        self.assertEqual(kits.extra_tools(None), [])


class RegisterTest(unittest.TestCase):
    """Registration + scope helpers (kit assignment is the patron's explicit pick now —
    there is no auto-detection)."""
    def setUp(self):
        import server
        self.server = server
        self._home = server.HOME
        self.tmp = Path(tempfile.mkdtemp())
        server.HOME = self.tmp

    def tearDown(self):
        self.server.HOME = self._home

    def _mk(self, sub, files):
        d = self.tmp / sub; d.mkdir(parents=True, exist_ok=True)
        for f in files:
            (d / f).write_text("x")
        return d

    def test_register_records_explicit_kit(self):
        d = self._mk("proj", ["notes.md"])
        # explicit kit wins over detection; written into the stanza
        import json
        self.server.PROJECTS_PATH = self.tmp / "projects.json"
        self.server.PROJECTS_PATH.write_text(json.dumps({"projects": []}))
        proj = self.server.register_project("Proj", str(d), "knowledge")
        self.assertEqual(proj["kit"], "knowledge")

    def test_scope_note(self):
        self.assertEqual(self.server.scope_note({}), "")
        self.assertEqual(self.server.scope_note({"max_depth": 0}), "")        # 0 → unbounded
        n1 = self.server.scope_note({"max_depth": 1})
        self.assertIn("max depth 1", n1)
        self.assertIn("only files directly in the root", n1)
        self.assertIn("subdirectories", self.server.scope_note({"max_depth": 2}))

    def test_register_stores_max_depth(self):
        import json
        self.server.PROJECTS_PATH = self.tmp / "projects.json"
        self.server.PROJECTS_PATH.write_text(json.dumps({"projects": []}))
        p1 = self.server.register_project("D1", str(self._mk("d1", ["x.md"])), None, 2)
        self.assertEqual(p1["max_depth"], 2)
        p2 = self.server.register_project("D2", str(self._mk("d2", ["y.md"])), None, 0)
        self.assertNotIn("max_depth", p2)                                    # 0 → no field


if __name__ == "__main__":
    unittest.main()
