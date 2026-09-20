from __future__ import annotations

import copy
import json
import re
import shutil
import unittest
import uuid
from pathlib import Path

from test_study import ROOT, study


class TaskBlockValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.payload, conditions = study.load_study(ROOT / "studies" / "sql" / "study.json")
        self.condition = copy.deepcopy(conditions[0])

    def test_default_task_is_the_original_compiler_task(self) -> None:
        _, conditions = study.load_study(ROOT / "studies" / "minimal" / "study.json")
        self.assertNotIn("task", conditions[0])
        self.assertEqual(study.condition_task(conditions[0]), study.DEFAULT_TASK)
        _, starter = study.load_study(ROOT / "studies" / "starter" / "study.json")
        self.assertTrue(all(study.condition_task(row)["max_stage"] == 10 for row in starter))

    def test_rejects_bad_runtime_stage_and_parameters(self) -> None:
        for patch, message in (
            ({"runtime": "prolog"}, "task.runtime"),
            ({"max_stage": 0}, "max_stage"),
            ({"parameters": {"sqlite_version": "latest"}}, "sqlite_version"),
            ({"parameters": {"sqlite_version": "3.40.1", "script_timeout_seconds": 0}}, "script_timeout_seconds"),
            ({"bogus": 1}, "unknown keys"),
        ):
            with self.subTest(patch=patch):
                condition = copy.deepcopy(self.condition)
                condition["task"] = study.deep_merge(condition["task"], patch)
                with self.assertRaisesRegex(study.StudyError, message):
                    study.validate_condition(condition, self.payload)

    def test_budget_stage_is_capped_by_the_task(self) -> None:
        condition = copy.deepcopy(self.condition)
        condition["budget"]["main_max_stage"] = 9
        with self.assertRaisesRegex(study.StudyError, "at most the task's max_stage"):
            study.validate_condition(condition, self.payload)
        _, c18 = study.load_study(ROOT / "studies" / "c18" / "study.json")
        self.assertEqual(c18[0]["budget"]["main_max_stage"], 18)

    def test_oracle_reference_is_compiler_only(self) -> None:
        condition = copy.deepcopy(self.condition)
        condition["prompt"]["experiment_tools"] = True
        condition["reference"].update(mode="oracle", oracle_limit=3)
        with self.assertRaisesRegex(study.StudyError, "only for the c-compiler"):
            study.validate_condition(condition, self.payload)


class TaskStudyManifestTests(unittest.TestCase):
    def test_language_conditions_share_the_behavioral_contract(self) -> None:
        for name in ("c18", "sql"):
            with self.subTest(study=name):
                payload, conditions = study.load_study(ROOT / "studies" / name / "study.json")
                self.assertEqual(payload["design"], "one-factor-at-a-time")
                self.assertEqual([row["id"] for row in conditions], ["rust", "python", "python-typed"])
                spec = (ROOT / conditions[0]["specification"]["path"]).read_text()
                for row in conditions:
                    self.assertFalse(row["prompt"]["experiment_tools"])
                    self.assertEqual(row["tests"]["access"], "none")
                    self.assertEqual(row["reference"]["mode"], "none")
                    self.assertIsNone(row["candidate"]["scaffold"])
                    self.assertEqual(row["specification"]["delivery"], "initial_prompt_only")
                # Only the language, build, and entry command vary between conditions.
                self.assertEqual(set(re.findall(r"\{\{([A-Z_]+)\}\}", spec)), {"LANGUAGE", "BUILD_COMMAND", "ENTRY_COMMAND"})
                for word in ("Stage 1", "PROGRESS.md", "interface", "trait", "class hierarchy", "type annotations", "lexer", "parser"):
                    self.assertNotIn(word, spec)

    def test_materialization_installs_the_task_runtime(self) -> None:
        for name, files, hidden_dir in (
            ("c18", {"candidate.json", "candidate_runtime.py", "evaluate.py", "fuzz_evaluate.py", "fuzz_generator.py", "task.json"}, "data/partitions-c18/hidden"),
            ("sql", {"candidate.json", "candidate_runtime.py", "evaluate.py", "sqllogictest.py", "task.json"}, "data/partitions-sql/hidden"),
        ):
            if not (ROOT / hidden_dir / "manifest.json").is_file():
                continue
            with self.subTest(study=name):
                path = ROOT / "studies" / name / "study.json"
                payload, conditions = study.load_study(path)
                run_id = f"unit-task-{name}-{uuid.uuid4().hex}"
                root = ROOT / "runs" / ".study-materializations" / run_id
                self.addCleanup(shutil.rmtree, root, ignore_errors=True)
                study.materialize(path, payload, conditions[0], run_id)
                self.assertEqual({p.name for p in (root / "evaluator").iterdir()}, files)
                task = json.loads((root / "evaluator" / "task.json").read_text())
                self.assertEqual(task, study.condition_task(conditions[0]))
                record = json.loads((root / "study-materialization.json").read_text())
                self.assertEqual(record["task"], task)
                self.assertEqual(record["effective_config"]["FUZZ_STAGE_PROGRAMS"], "0")
                self.assertEqual(record["effective_config"]["MAIN_MAX_STAGE"], str(task["max_stage"]))
                self.assertEqual(record["effective_config"]["PI_TOOLS"], "read,bash,edit,write,grep,find,ls")
                self.assertEqual(
                    sorted(p.name for p in (root / "pi" / "extensions").iterdir()),
                    ["compaction-bound.ts", "experiment-guard.ts"],
                )
                hidden = json.loads((root / "data" / "partitions" / "hidden" / "manifest.json").read_text())
                for row in hidden["tests"]:
                    for fixture in row.get("fixtures", []):
                        self.assertTrue((root / "data" / "partitions" / "hidden" / fixture["relative_path"]).is_file(), fixture)
                self.assertEqual(json.loads((root / "data" / "agent-visible" / "manifest.json").read_text())["tests"], [])
                initial = (root / "prompts" / "INITIAL.txt").read_text()
                self.assertNotIn("{{", initial)
                self.assertEqual((root / "prompts" / "AGENTS.md").read_text().strip(), "")

    def test_python_arms_differ_only_in_the_type_gate(self) -> None:
        for name in ("c18", "sql"):
            _, conditions = study.load_study(ROOT / "studies" / name / "study.json")
            untyped = study.load_json_object(ROOT / conditions[1]["candidate"]["adapter"])
            typed = study.load_json_object(ROOT / conditions[2]["candidate"]["adapter"])
            self.assertEqual(untyped["run"], typed["run"])
            self.assertEqual(untyped["build"]["artifact"], typed["build"]["artifact"])
            self.assertEqual(typed["build"]["command"][:2], ["mypy", "--strict"])
            self.assertEqual(untyped["build"]["command"][:3], ["python3", "-m", "py_compile"])
            blocked = [re.compile(row["pattern"], re.I) for row in untyped["agent_policy"]["blocked_bash_patterns"]]
            for command in ("mypy --strict pisql.py", "python3 -m mypy .", "pyright src"):
                self.assertTrue(any(p.search(command) for p in blocked), command)
            self.assertFalse(any(p.search("python3 -m py_compile pisql.py") for p in blocked))
            # The typed arm withholds nothing beyond the task's own prohibitions.
            typed_blocks = [row["pattern"] for row in typed["agent_policy"]["blocked_bash_patterns"]]
            self.assertFalse(any("mypy" in pattern for pattern in typed_blocks))
            self.assertEqual(len(typed_blocks), len(blocked) - 1)
            self.assertTrue(any(row["reason"] == "type-check suppression" for row in typed["audit"]["prohibited_patterns"]))

    def test_sql_guard_blocks_database_engines(self) -> None:
        if not (ROOT / "data/partitions-sql/hidden/manifest.json").is_file():
            self.skipTest("SQL partitions not fetched")
        path = ROOT / "studies" / "sql" / "study.json"
        payload, conditions = study.load_study(path)
        run_id = f"unit-task-sql-guard-{uuid.uuid4().hex}"
        root = ROOT / "runs" / ".study-materializations" / run_id
        self.addCleanup(shutil.rmtree, root, ignore_errors=True)
        study.materialize(path, payload, conditions[1], run_id)
        guard = (root / "pi" / "extensions" / "experiment-guard.ts").read_text()
        self.assertIn("existing database engine", guard)
        patterns = [row["pattern"] for row in json.loads((root / "evaluator" / "candidate.json").read_text())["agent_policy"]["blocked_bash_patterns"]]
        compiled = [re.compile(p, re.I) for p in patterns]
        for command in ("sqlite3 test.db", "python3 -c 'import sqlite3'", "node -e \"require('node:sqlite')\""):
            self.assertTrue(any(p.search(command) for p in compiled), command)
        self.assertFalse(any(p.search("cargo build --release --offline") for p in compiled))


class SummaryScoreTests(unittest.TestCase):
    def test_fractional_script_scores_are_recomputed(self) -> None:
        import importlib.util
        import sys

        sys.path.insert(0, str(ROOT / "scripts"))
        import summarize_study

        rows = [
            {"stage": 1, "validity": "valid", "passed": True, "score": 1.0},
            {"stage": 1, "validity": "valid", "passed": False, "score": 0.5},
            {"stage": 2, "validity": "valid", "passed": False, "score": 0.0},
        ]
        recomputed = summarize_study.recomputed_hidden_scores(rows)
        self.assertAlmostEqual(recomputed["score"], (0.75 + 0.0) / 2)
        self.assertEqual((recomputed["passed"], recomputed["total"]), (1, 3))
        with self.assertRaisesRegex(summarize_study.SummaryError, "disagrees"):
            summarize_study.recomputed_hidden_scores([{"stage": 1, "validity": "valid", "passed": True, "score": 0.5}])
        plain = [{"stage": 1, "validity": "valid", "passed": True}, {"stage": 1, "validity": "invalid", "passed": False}]
        self.assertEqual(summarize_study.recomputed_hidden_scores(plain)["score"], 0.5)


if __name__ == "__main__":
    unittest.main()
