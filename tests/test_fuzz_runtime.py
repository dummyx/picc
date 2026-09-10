from __future__ import annotations

import importlib.util
import json
import random
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
RUNTIME = ROOT / "studies" / "runtime"
sys.path.insert(0, str(RUNTIME))
sys.path.insert(0, str(ROOT / "scripts"))

from fuzz_generator import NORM, Generator, normalise  # noqa: E402
import evaluate_run  # noqa: E402


class GeneratorTests(unittest.TestCase):
    def test_same_seed_same_programs(self) -> None:
        first = [Generator(random.Random(7), 10, False).program() for _ in range(3)]
        second = [Generator(random.Random(7), 10, False).program() for _ in range(3)]
        self.assertEqual(first, second)
        self.assertNotEqual(first, [Generator(random.Random(8), 10, False).program() for _ in range(3)])

    def test_stage_gating(self) -> None:
        for stage in range(1, 11):
            generator = Generator(random.Random(stage), stage, False)
            for _ in range(20):
                source, status, stdout = generator.program()
                self.assertEqual(stdout, "")
                self.assertTrue(0 <= status < NORM)
                if stage < 5:
                    self.assertNotIn("int v", source)
                    self.assertEqual(source.count("return"), 1)
                if stage < 9:
                    self.assertNotIn("int f0(", source)
                if stage < 10:
                    self.assertNotIn("int g0 =", source)
                if stage < 8:
                    self.assertNotIn("while", source)
        self.assertEqual(normalise(-1), NORM - 1)
        self.assertEqual(normalise(NORM + 3), 3)


class FuzzEvaluateTests(unittest.TestCase):
    def run_scorer(self, workspace: Path, adapter: Path, max_stage: int, extra: list[str]) -> dict:
        with tempfile.TemporaryDirectory(prefix="picc-fuzz-test-") as temporary:
            output = Path(temporary) / "fuzz.json"
            result = subprocess.run(
                [
                    sys.executable,
                    str(RUNTIME / "fuzz_evaluate.py"),
                    "--workspace", str(workspace),
                    "--candidate-config", str(adapter),
                    "--max-stage", str(max_stage),
                    "--output", str(output),
                    "--summary-json",
                    *extra,
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            return json.loads(output.read_text(encoding="utf-8"))

    def test_javascript_mock_scores_stage_one_and_fails_stage_two(self) -> None:
        if shutil.which("node") is None or not Path("/usr/bin/gcc").exists():
            self.skipTest("node and /usr/bin/gcc are required")
        with tempfile.TemporaryDirectory(prefix="picc-fuzz-ws-") as temporary:
            workspace = Path(temporary) / "workspace"
            shutil.copytree(ROOT / "fixtures" / "mock-picc-js", workspace)
            full = self.run_scorer(
                workspace, ROOT / "studies" / "assets" / "candidates" / "javascript-node.json", 2, ["--count", "12"]
            )
        summary = full["summary"]
        self.assertTrue(summary["build_ok"] and summary["audit_ok"])
        self.assertEqual(full["stages"]["1"]["status"], "complete")
        self.assertEqual(full["stages"]["1"]["pass_rate"], 1.0)
        # The mock only accepts `return N;`, so unary programs are rejected.
        self.assertLess(full["stages"]["2"]["pass_rate"], 1.0)
        self.assertIn("rejected_valid_program", full["stages"]["2"]["mismatch_kinds"])
        self.assertAlmostEqual(summary["fuzz_macro"], (1.0 + full["stages"]["2"]["pass_rate"]) / 2)
        self.assertEqual(summary["stage_pass_rates"], [full["stages"]["1"]["pass_rate"], full["stages"]["2"]["pass_rate"]])
        self.assertEqual(full["policy"]["programs_per_stage"], 12)
        self.assertLessEqual(len(full["stages"]["2"]["samples"]), 3)

    def test_blocking_audit_and_deadline_score_zero_without_running(self) -> None:
        with tempfile.TemporaryDirectory(prefix="picc-fuzz-ws-") as temporary:
            workspace = Path(temporary) / "workspace"
            (workspace / "src").mkdir(parents=True)
            (workspace / "src" / "picc.js").write_text('require("child_process");\n', encoding="utf-8")
            full = self.run_scorer(
                workspace, ROOT / "studies" / "assets" / "candidates" / "javascript-node.json", 3, ["--count", "5"]
            )
            self.assertTrue(full["summary"]["audit_blocking"])
            self.assertEqual(full["summary"]["fuzz_macro"], 0.0)
            self.assertEqual({row["reason"] for row in full["stages"].values()}, {"source_audit_failure"})

            (workspace / "src" / "picc.js").write_text("process.exitCode = 0;\n", encoding="utf-8")
            if shutil.which("node") is None:
                return
            full = self.run_scorer(
                workspace,
                ROOT / "studies" / "assets" / "candidates" / "javascript-node.json",
                3,
                ["--count", "5", "--deadline-seconds", "0"],
            )
            self.assertTrue(full["summary"]["deadline_hit"])
            self.assertEqual(full["summary"]["fuzz_macro"], 0.0)
            self.assertEqual({row.get("reason") for row in full["stages"].values()}, {"deadline"})


class FuzzPolicyTests(unittest.TestCase):
    def test_disabled_and_enabled_policies(self) -> None:
        self.assertIsNone(evaluate_run.fuzz_policy({}))
        self.assertIsNone(evaluate_run.fuzz_policy({"FUZZ_STAGE_PROGRAMS": "0"}))
        policy = evaluate_run.fuzz_policy({"FUZZ_STAGE_PROGRAMS": "100", "FUZZ_RUN_TIMEOUT_SECONDS": "3"})
        self.assertEqual(policy["programs_per_stage"], 100)
        self.assertEqual(policy["run_timeout_seconds"], 3)
        self.assertEqual(policy["seed_base"], 20260830)
        with self.assertRaises(evaluate_run.ExperimentError):
            evaluate_run.fuzz_policy({"FUZZ_STAGE_PROGRAMS": "many"})


if __name__ == "__main__":
    unittest.main()
