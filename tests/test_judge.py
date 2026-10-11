"""The sitting judge writes byte-stable scores without calling a model."""

from __future__ import annotations

import json
import shlex
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

from tools.judge.engine import runner_argv
from tools.judge.rubric import load_rubric, normalise_body
from tools.judge.scenarios import load_scenarios
from tools.judge.schema import SCHEMA_PATH, SchemaError, load_schema, validate
from tools.judge.yamlio import YAMLError, loads

ROOT = Path(__file__).resolve().parents[1]
JUDGE = ROOT / "tools" / "judge"
RUBRIC = JUDGE / "rubrics" / "sitting.md"
FOUNDING = JUDGE / "scenarios" / "founding-interview.yaml"

RUNNER = textwrap.dedent(
    """\
    import json, sys, time
    sid = sys.argv[1]
    mode = sys.argv[2] if len(sys.argv) > 2 else "ok"
    delays = {"slow": 0.25, "mid": 0.12, "fast": 0.02, "last": 0.01}
    if mode == "sleep":
        time.sleep(delays.get(sid, 0.05))
    if mode == "fail" and sid == "bad":
        print("boom from runner", file=sys.stderr)
        raise SystemExit(3)
    if mode == "hang" and sid == "hung":
        time.sleep(5)
    if mode == "badjson" and sid == "bad":
        print("not-json")
        raise SystemExit(0)
    if mode == "unknown":
        print(json.dumps({"notes": "", "scores": {"mission": 1, "warmth": 3}}))
        raise SystemExit(0)
    dims = json.load(sys.stdin)["rubric"]["dimensions"]
    scores = {"mission": 1, "tone": 2}
    if not set(scores) <= set(dims):
        scores = {dim: 1 for dim in dims}
    print(json.dumps({"notes": " note " + sid + " ", "scores": scores}))
    """
)

RUBRIC_TEXT = textwrap.dedent(
    """\
    ---
    version: "0"
    dimensions:
      - tone
      - mission
    ---

    # Temp rubric

    TODO(patron): score tone before mission.
    """
)


class JudgeAcceptanceTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.rubric_path = self.root / "rubric.md"
        self.rubric_path.write_text(RUBRIC_TEXT, encoding="utf-8")
        self.script = self.root / "runner.py"
        self.script.write_text(RUNNER, encoding="utf-8")
        self.scenarios = self.root / "scenarios.yaml"

    def _fixture(self, name: str) -> None:
        (self.root / "fixtures" / name).mkdir(parents=True)

    def _write_scenarios(self, ids: list[str]) -> None:
        lines = ["name: temp", "scenarios:"]
        for sid in ids:
            self._fixture(sid)
            lines.append(f"  - id: {sid}")
            lines.append(f"    title: {sid}")
            lines.append(f"    fixture: fixtures/{sid}")
        self.scenarios.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def _runner(self, mode: str = "ok") -> str:
        return (
            f"{shlex.quote(sys.executable)} {shlex.quote(str(self.script))} "
            f"{{scenario}} {mode}"
        )

    def _cli(self, args: list[str]) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, "-m", "tools.judge", *args],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

    def _run(self, out: Path, *, parallel: int, mode: str = "ok", timeout: float | None = None,
             rubric: Path | None = None) -> subprocess.CompletedProcess[str]:
        cmd = [
            "run",
            "--rubric", str(rubric or self.rubric_path),
            "--scenarios", str(self.scenarios),
            "--runner", self._runner(mode),
            "--parallel", str(parallel),
            "--out", str(out),
        ]
        if timeout is not None:
            cmd.extend(["--timeout", str(timeout)])
        return self._cli(cmd)

    def test_identical_inputs_are_byte_identical(self):
        self._write_scenarios(["slow", "mid", "fast", "last"])
        first = self.root / "a.json"
        second = self.root / "b.json"
        serial = self._run(first, parallel=1, mode="sleep")
        again = self._run(second, parallel=4, mode="sleep")
        self.assertEqual(serial.returncode, 0, serial.stderr)
        self.assertEqual(again.returncode, 0, again.stderr)
        self.assertEqual(first.read_bytes(), second.read_bytes())
        rows = json.loads(first.read_text(encoding="utf-8"))
        self.assertEqual([row["scenario"] for row in rows], ["slow", "mid", "fast", "last"])
        validate(rows, load_schema())
        self.assertEqual(list(rows[0]["scores"]), ["tone", "mission"])
        self.assertNotIn("error", rows[0])
        self.assertTrue(first.read_bytes().endswith(b"\n"))

    def test_parallel_matches_serial_order_when_completion_order_differs(self):
        self._write_scenarios(["slow", "last"])
        serial = self.root / "serial.json"
        wide = self.root / "wide.json"
        self.assertEqual(self._run(serial, parallel=1, mode="sleep").returncode, 0)
        self.assertEqual(self._run(wide, parallel=4, mode="sleep").returncode, 0)
        self.assertEqual(serial.read_bytes(), wide.read_bytes())
        rows = json.loads(wide.read_text(encoding="utf-8"))
        self.assertEqual([row["scenario"] for row in rows], ["slow", "last"])

    def test_editing_the_rubric_changes_the_hash_and_fails_verify(self):
        self._write_scenarios(["alpha"])
        scores = self.root / "scores.json"
        self.assertEqual(self._run(scores, parallel=1).returncode, 0)
        original = load_rubric(self.rubric_path)
        verified = self._cli(["verify", str(scores), "--rubric", str(self.rubric_path)])
        self.assertEqual(verified.returncode, 0, verified.stderr)
        self.assertIn(original.sha256, verified.stdout)

        spaced = self.root / "spaced.md"
        spaced.write_text(RUBRIC_TEXT.replace("mission.\n", "mission.   \n"), encoding="utf-8")
        self.assertEqual(load_rubric(spaced).sha256, original.sha256)

        crlf = self.root / "crlf.md"
        crlf.write_bytes(RUBRIC_TEXT.replace("\n", "\r\n").encode("utf-8"))
        self.assertEqual(load_rubric(crlf).sha256, original.sha256)

        bumped = self.root / "bumped.md"
        bumped.write_text(RUBRIC_TEXT.replace('version: "0"', 'version: "1"'), encoding="utf-8")
        self.assertEqual(load_rubric(bumped).sha256, original.sha256)
        self.assertEqual(load_rubric(bumped).version, "1")
        still = self._cli(["verify", str(scores), "--rubric", str(bumped)])
        self.assertEqual(still.returncode, 0, still.stderr)

        edited = self.root / "edited.md"
        edited.write_text(
            RUBRIC_TEXT.replace("TODO(patron)", "TODO(patron) edited"),
            encoding="utf-8",
        )
        changed = load_rubric(edited)
        self.assertNotEqual(changed.sha256, original.sha256)
        failed = self._cli(["verify", str(scores), "--rubric", str(edited)])
        self.assertEqual(failed.returncode, 1)
        self.assertIn(original.sha256, failed.stderr)
        self.assertIn(changed.sha256, failed.stderr)

        rescored = self.root / "rescored.json"
        self.assertEqual(self._run(rescored, parallel=1, rubric=edited).returncode, 0)
        ok = self._cli(["verify", str(rescored), "--rubric", str(edited)])
        self.assertEqual(ok.returncode, 0, ok.stderr)

    def test_changing_only_the_dimensions_fails_verify(self):
        self._write_scenarios(["alpha"])
        scores = self.root / "scores.json"
        self.assertEqual(self._run(scores, parallel=1).returncode, 0)
        original = load_rubric(self.rubric_path)

        redimensioned = self.root / "redimensioned.md"
        redimensioned.write_text(
            RUBRIC_TEXT.replace("  - mission\n", "  - mission\n  - warmth\n"),
            encoding="utf-8",
        )
        changed = load_rubric(redimensioned)
        self.assertEqual(changed.body, original.body)
        self.assertEqual(changed.dimensions, ("tone", "mission", "warmth"))
        self.assertNotEqual(changed.sha256, original.sha256)
        failed = self._cli(["verify", str(scores), "--rubric", str(redimensioned)])
        self.assertEqual(failed.returncode, 1, failed.stdout)
        self.assertIn(changed.sha256, failed.stderr)

    def test_one_failing_scenario_is_an_error_row_and_the_rest_continue(self):
        self._write_scenarios(["good", "bad", "also-good"])
        out = self.root / "scores.json"
        result = self._run(out, parallel=4, mode="fail")
        self.assertEqual(result.returncode, 1, result.stderr)
        rows = json.loads(out.read_text(encoding="utf-8"))
        validate(rows, load_schema())
        self.assertEqual([row["scenario"] for row in rows], ["good", "bad", "also-good"])
        self.assertNotIn("error", rows[0])
        self.assertNotIn("error", rows[2])
        self.assertEqual(rows[0]["scores"], {"tone": 2, "mission": 1})
        self.assertIn("error", rows[1])
        self.assertIn("boom from runner", rows[1]["error"])
        self.assertEqual(rows[1]["scores"], {})
        self.assertEqual(rows[0]["rubric_sha256"], rows[1]["rubric_sha256"])

    def test_a_hung_scenario_times_out_and_the_next_row_is_kept(self):
        self._write_scenarios(["hung", "ok"])
        out = self.root / "scores.json"
        result = self._run(out, parallel=2, mode="hang", timeout=1)
        self.assertEqual(result.returncode, 1, result.stderr)
        rows = json.loads(out.read_text(encoding="utf-8"))
        self.assertEqual([row["scenario"] for row in rows], ["hung", "ok"])
        self.assertIn("timed out", rows[0]["error"])
        self.assertNotIn("error", rows[1])
        validate(rows, load_schema())

    def test_bad_stdout_is_an_error_row(self):
        self._write_scenarios(["bad"])
        out = self.root / "scores.json"
        result = self._run(out, parallel=1, mode="badjson")
        self.assertEqual(result.returncode, 1)
        rows = json.loads(out.read_text(encoding="utf-8"))
        self.assertIn("not JSON", rows[0]["error"])
        validate(rows, load_schema())

    def test_a_score_outside_the_rubric_dimensions_is_an_error_row(self):
        self._write_scenarios(["alpha"])
        out = self.root / "scores.json"
        result = self._run(out, parallel=1, mode="unknown")
        self.assertEqual(result.returncode, 1, result.stderr)
        rows = json.loads(out.read_text(encoding="utf-8"))
        validate(rows, load_schema())
        self.assertEqual(rows[0]["error"], "score warmth is not a rubric dimension")
        self.assertEqual(rows[0]["scores"], {})

    def test_schema_rejects_a_row_missing_notes(self):
        with self.assertRaises(SchemaError):
            validate([{"scenario": "x", "run_id": "ab", "scores": {}}], load_schema())

    def test_runner_placeholder_is_one_argument(self):
        self.assertEqual(runner_argv("echo {scenario}", "empty-folder"), ["echo", "empty-folder"])
        self.assertEqual(
            runner_argv("cmd --id={scenario}", "empty-folder"),
            ["cmd", "--id=empty-folder"],
        )
        missing = self._cli([
            "run", "--rubric", str(self.rubric_path), "--scenarios", str(FOUNDING),
            "--runner", "echo hello", "--out", str(self.root / "nope.json"),
        ])
        self.assertEqual(missing.returncode, 2)
        self.assertIn("{scenario}", missing.stderr)


class ShippedJudgeTest(unittest.TestCase):
    def test_template_rubric_and_both_scenario_files(self):
        rubric = load_rubric(RUBRIC)
        self.assertEqual(rubric.version, "0")
        self.assertIn("TODO(patron)", rubric.body)
        self.assertGreaterEqual(rubric.body.count("TODO(patron)"), 3)
        self.assertEqual(len(rubric.sha256), 64)
        self.assertTrue((JUDGE / "scenarios" / "template.yaml").is_file())
        self.assertTrue(FOUNDING.is_file())
        self.assertEqual(SCHEMA_PATH.name, "scores.schema.json")
        template, _ = load_scenarios(JUDGE / "scenarios" / "template.yaml")
        self.assertIn("TODO(patron)", json.dumps(template))

    def test_founding_scenarios_name_real_fixtures(self):
        _, scenarios = load_scenarios(FOUNDING)
        self.assertGreaterEqual(len(scenarios), 8)
        ids = [scenario.id for scenario in scenarios]
        for required in ("empty-folder", "folder-with-notes", "interrupted-founding", "re-found"):
            self.assertIn(required, ids)
        self.assertEqual(ids, list(dict.fromkeys(ids)))
        for scenario in scenarios:
            self.assertTrue(scenario.fixture.is_dir(), scenario.fixture)
            self.assertTrue(str(scenario.fixture).startswith(str(JUDGE)))

    def test_fixtures_are_synthetic_and_match_the_founding_cases(self):
        from kettle.survey import build_survey

        forbidden = (
            "/Users/", "/home/", "api_key", "BEGIN OPENSSH", "BEGIN PRIVATE", "charlesberret",
        )
        for path in (JUDGE / "fixtures").rglob("*"):
            if path.is_file():
                text = path.read_text(encoding="utf-8", errors="replace")
                for needle in forbidden:
                    self.assertNotIn(needle, text, f"{needle} in {path}")

        empty = build_survey(JUDGE / "fixtures" / "founding" / "empty-folder")
        self.assertTrue(empty["empty"])
        notes = build_survey(JUDGE / "fixtures" / "founding" / "folder-with-notes")
        self.assertFalse(notes["empty"])
        self.assertIn("README.md", notes["samples"])

        base = JUDGE / "fixtures" / "founding"
        self.assertFalse((base / "interrupted-founding" / ".kettle" / "PROJECT.md").exists())
        self.assertTrue((base / "interrupted-founding" / ".kettle" / "DESK-PROPOSAL.md").is_file())
        self.assertTrue((base / "charter-without-content" / ".kettle" / "PROJECT.md").is_file())
        charter_queue = json.loads(
            (base / "charter-without-content" / ".kettle" / "runtime" / "queue.json").read_text()
        )
        self.assertEqual([e["id"] for e in charter_queue["entries"]], ["desk-proposal"])
        self.assertFalse((base / "content-without-charter" / ".kettle" / "PROJECT.md").exists())
        content_queue = json.loads(
            (base / "content-without-charter" / ".kettle" / "runtime" / "queue.json").read_text()
        )
        self.assertEqual([e["id"] for e in content_queue["entries"]], ["field-notes"])
        founded = json.loads(
            (base / "already-founded" / ".kettle" / "runtime" / "session.json").read_text()
        )
        self.assertEqual(founded["status"], "founded")
        self.assertTrue((base / "already-founded" / ".kettle" / "PROJECT.md").is_file())
        unmarked = json.loads(
            (base / "unmarked-on-disk" / ".kettle" / "runtime" / "session.json").read_text()
        )
        self.assertNotEqual(unmarked.get("status"), "founded")
        self.assertTrue((base / "unmarked-on-disk" / ".kettle" / "PROJECT.md").is_file())
        refound_path = base / "re-found" / ".kettle" / "runtime" / "session.json"
        refound = json.loads(refound_path.read_text())
        self.assertIn("founding_note", refound)
        self.assertNotIn("status", refound)
        self.assertFalse((base / "re-found" / ".kettle" / "PROJECT.md").exists())
        self.assertFalse((base / "re-found" / ".kettle" / "DESK-PROPOSAL.md").exists())
        self.assertTrue((base / "re-found" / ".kettle" / "runtime" / "approvals.log").is_file())
        self.assertTrue((base / "re-found" / ".kettle" / "working-record.jsonl").is_file())
        edited = (base / "proposal-edited" / ".kettle" / "DESK-PROPOSAL.md").read_text()
        self.assertIn("USER EDIT", edited)

    def test_shipped_suite_scores_are_stable_and_verify(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            script = root / "runner.py"
            script.write_text(RUNNER, encoding="utf-8")
            runner = f"{shlex.quote(sys.executable)} {shlex.quote(str(script))} {{scenario}}"
            serial = root / "serial.json"
            wide = root / "wide.json"
            base = [
                sys.executable, "-m", "tools.judge", "run",
                "--rubric", "sitting",
                "--scenarios", "founding-interview",
                "--runner", runner,
            ]
            first = subprocess.run(
                [*base, "--parallel", "1", "--out", str(serial)],
                cwd=ROOT, text=True, capture_output=True, check=False,
            )
            second = subprocess.run(
                [*base, "--parallel", "4", "--out", str(wide)],
                cwd=ROOT, text=True, capture_output=True, check=False,
            )
            self.assertEqual(first.returncode, 0, first.stderr)
            self.assertEqual(second.returncode, 0, second.stderr)
            self.assertEqual(serial.read_bytes(), wide.read_bytes())
            rows = json.loads(serial.read_text(encoding="utf-8"))
            validate(rows, load_schema())
            _, scenarios = load_scenarios(FOUNDING)
            self.assertEqual([row["scenario"] for row in rows], [s.id for s in scenarios])
            rubric = load_rubric(RUBRIC)
            self.assertTrue(all(row["rubric_sha256"] == rubric.sha256 for row in rows))
            self.assertTrue(all(row["rubric_version"] == "0" for row in rows))
            verified = subprocess.run(
                [
                    sys.executable, "-m", "tools.judge", "verify",
                    str(serial), "--rubric", "sitting",
                ],
                cwd=ROOT, text=True, capture_output=True, check=False,
            )
            self.assertEqual(verified.returncode, 0, verified.stderr)
            edited = root / "sitting.md"
            edited.write_text(
                RUBRIC.read_text(encoding="utf-8").replace("TODO(patron)", "TODO(patron) x"),
                encoding="utf-8",
            )
            rejected = subprocess.run(
                [
                    sys.executable, "-m", "tools.judge", "verify",
                    str(serial), "--rubric", str(edited),
                ],
                cwd=ROOT, text=True, capture_output=True, check=False,
            )
            self.assertEqual(rejected.returncode, 1)
            self.assertNotEqual(load_rubric(edited).sha256, rubric.sha256)


class YamlSubsetTest(unittest.TestCase):
    def test_maps_lists_and_folded_scalars(self):
        data = loads(textwrap.dedent(
            """\
            name: sample
            summary: >
              one line
              still one
            items:
              - id: alpha
                title: "has: a colon"
                n: 2
            """
        ))
        self.assertEqual(data["summary"], "one line still one\n")
        self.assertEqual(data["items"][0]["title"], "has: a colon")
        self.assertEqual(data["items"][0]["n"], 2)

    def test_tabs_are_rejected(self):
        with self.assertRaises(YAMLError):
            loads("name:\tbad\n")

    def test_normalise_drops_surrounding_blank_lines(self):
        self.assertEqual(normalise_body("\n\nalpha  \n\n"), "alpha\n")


if __name__ == "__main__":
    unittest.main()
