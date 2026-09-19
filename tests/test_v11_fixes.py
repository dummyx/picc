"""The v11 harness fixes: the four v10 interactions of report 16.4/16.5."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import run_experiment as runner  # noqa: E402


def write_events(path: Path, *, tool_calls: int = 0, overflow_error: str | None = None) -> Path:
    lines = [json.dumps({"type": "session", "id": "x"})]
    for _ in range(tool_calls):
        lines.append(json.dumps({"type": "tool_execution_start", "toolName": "bash"}))
    if overflow_error is not None:
        lines.append(json.dumps({"type": "compaction_start", "reason": "overflow"}))
        lines.append(json.dumps({"type": "compaction_end", "reason": "overflow", "errorMessage": overflow_error}))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


class RoundEvidenceTests(unittest.TestCase):
    def test_counts_tool_calls_and_detects_failed_overflow_recovery(self) -> None:
        with tempfile.TemporaryDirectory(prefix="picc-evidence-") as temporary:
            root = Path(temporary)
            working = write_events(root / "a.jsonl", tool_calls=12)
            self.assertEqual(runner.round_evidence(working), {"tool_calls": 12, "overflow_recovery_failed": False})

            dead = write_events(
                root / "b.jsonl",
                overflow_error="Context overflow recovery failed: Summarization failed: 400: request (176392 tokens) exceeds",
            )
            self.assertEqual(runner.round_evidence(dead), {"tool_calls": 0, "overflow_recovery_failed": True})

            # A compaction that succeeded is not a failure.
            recovered = root / "c.jsonl"
            recovered.write_text(
                json.dumps({"type": "compaction_end", "reason": "overflow", "errorMessage": ""}) + "\n",
                encoding="utf-8",
            )
            self.assertFalse(runner.round_evidence(recovered)["overflow_recovery_failed"])

    def test_missing_or_malformed_stream_reports_nothing(self) -> None:
        with tempfile.TemporaryDirectory(prefix="picc-evidence-") as temporary:
            root = Path(temporary)
            self.assertEqual(runner.round_evidence(root / "absent.jsonl"), {"tool_calls": 0, "overflow_recovery_failed": False})
            broken = root / "broken.jsonl"
            broken.write_text('{"type":"compaction_end" NOT JSON\n', encoding="utf-8")
            self.assertEqual(runner.round_evidence(broken)["overflow_recovery_failed"], False)


class EvaluatorShortCircuitTests(unittest.TestCase):
    """A candidate that hangs on every input must not consume the evaluator's
    whole ceiling; the remaining tests are recorded without being run."""

    def setUp(self) -> None:
        if not Path("/usr/bin/gcc").exists():
            self.skipTest("/usr/bin/gcc is required")
        self.temporary = tempfile.TemporaryDirectory(prefix="picc-shortcircuit-")
        self.root = Path(self.temporary.name)
        self.addCleanup(self.temporary.cleanup)

        self.workspace = self.root / "workspace"
        self.workspace.mkdir()
        (self.workspace / "picc.sh").write_text("#!/usr/bin/env bash\nsleep 300\n", encoding="utf-8")
        (self.workspace / "candidate.json").write_text(
            json.dumps(
                {
                    "schema_version": 1, "language": "shell", "framework": "test-fixture",
                    "build": {"command": ["bash", "-n", "picc.sh"], "artifact": "picc.sh", "timeout_seconds": 60},
                    "run": {"command": ["bash", "{artifact}", "{input}", "-o", "{output}"]},
                    "source_extensions": [".sh"], "audit": {},
                }
            ),
            encoding="utf-8",
        )

        self.tests = self.root / "tests"
        rows = []
        for index in range(40):
            relative = f"chapter_1/valid/return_{index}.c"
            path = self.tests / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(f"int main(void) {{ return {index % 200}; }}\n", encoding="utf-8")
            rows.append({"id": relative, "relative_path": relative, "stage": 1, "validity": "valid"})
        (self.tests / "manifest.json").write_text(json.dumps({"partition": "all", "tests": rows}), encoding="utf-8")

    def test_hanging_candidate_stops_after_the_consecutive_limit(self) -> None:
        output = self.root / "result.json"
        limit = 25
        subprocess.run(
            [
                sys.executable, str(ROOT / "studies" / "runtime" / "evaluate.py"),
                "--workspace", str(self.workspace), "--tests-root", str(self.tests),
                "--manifest", str(self.tests / "manifest.json"),
                "--candidate-config", str(self.workspace / "candidate.json"),
                "--max-stage", "1", "--compile-timeout", "1", "--run-timeout", "1",
                "--cache-dir", str(self.root / "cache"), "--output", str(output), "--summary-json",
            ],
            check=True, capture_output=True, text=True, cwd=ROOT,
        )
        payload = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual(payload["summary"]["score"], 0.0)
        self.assertEqual(payload["summary"]["total"], 40)
        self.assertEqual(payload["input_policy"]["short_circuited_tests"], 40 - limit)
        self.assertTrue(all(row["failure_type"] == "compiler_timeout" for row in payload["tests"]))
        # Skipped rows are recorded, not silently dropped, and cost no time.
        skipped = [row for row in payload["tests"] if row["compile_seconds"] == 0.0]
        self.assertEqual(len(skipped), 40 - limit)


class BudgetAccountingTests(unittest.TestCase):
    def test_evaluation_time_is_not_charged_to_the_agent_budget(self) -> None:
        source = (ROOT / "scripts" / "run_experiment.py").read_text(encoding="utf-8")
        # The loop must gate on the evaluation-adjusted deadline, never the raw one.
        self.assertIn("def agent_deadline()", source)
        self.assertIn("return deadline + evaluation_seconds", source)
        self.assertNotIn("remaining_seconds = max(0.0, deadline - time.monotonic())", source)
        self.assertNotIn("if time.monotonic() >= deadline:", source)
        self.assertIn("evaluation_seconds += time.monotonic() - evaluation_started", source)


class StallRuleTests(unittest.TestCase):
    def test_only_a_capped_round_without_work_counts_as_a_stall(self) -> None:
        source = (ROOT / "scripts" / "run_experiment.py").read_text(encoding="utf-8")
        self.assertIn('if round_result["timed_out"] and not produced_work:', source)
        self.assertIn('termination_reason = "context_overflow"', source)
        self.assertIn("MAX_CONSECUTIVE_DEAD_ROUNDS", source)


if __name__ == "__main__":
    unittest.main()


class ContextBudgetInvariantTests(unittest.TestCase):
    """The v10/v11 context-overflow deaths: one model turn must never be able
    to push the session past the window and leave it unsummarizable."""

    def problems(self, *, window: int, output: int, reserve: int, keep_recent: int = 20000, enabled: bool = True):
        from common import context_budget_problems

        return context_budget_problems(
            {"LOCAL_CONTEXT_WINDOW": str(window), "LOCAL_MAX_OUTPUT": str(output)},
            {"enabled": enabled, "reserveTokens": reserve, "keepRecentTokens": keep_recent},
        )

    def test_rejects_the_configuration_that_killed_v10_and_v11_runs(self) -> None:
        problems = self.problems(window=131072, output=65536, reserve=16384)
        self.assertTrue(problems)
        self.assertIn("unsummarizable", problems[0])

    def test_accepts_the_corrected_configuration(self) -> None:
        self.assertEqual(self.problems(window=131072, output=32768, reserve=40960, keep_recent=49152), [])

    def test_rejects_a_turn_larger_than_the_keep_recent_budget(self) -> None:
        # The v13 finding: a single assistant message bigger than
        # keepRecentTokens forces Pi's split-turn compaction, which summarizes
        # a span containing every oversized turn and outgrows the window.
        problems = self.problems(window=131072, output=32768, reserve=40960, keep_recent=20000)
        self.assertTrue(problems)
        self.assertIn("split-turn", problems[0])

    def test_rejects_a_reserve_that_cannot_fit_beside_the_output(self) -> None:
        self.assertTrue(self.problems(window=65536, output=32768, reserve=40960))
        self.assertTrue(self.problems(window=40000, output=32768, reserve=32768, keep_recent=20000))

    def test_the_live_configuration_satisfies_the_invariant(self) -> None:
        from common import context_budget_problems, load_config

        self.assertEqual(context_budget_problems(load_config()), [])

    def test_a_run_refuses_to_start_on_an_unsafe_budget(self) -> None:
        source = (ROOT / "scripts" / "run_experiment.py").read_text(encoding="utf-8")
        self.assertIn("require_context_budget(config)", source)
