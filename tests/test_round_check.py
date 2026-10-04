"""The round check (v20): the scorer runs the specification's build command
and worked example on every snapshot, and the harness reports the result in
the next round's message. Scorers are exercised on the real mock programs
under fixtures/, the message on the scorers' own output."""
from __future__ import annotations

import copy
import importlib.util
import json
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import common  # noqa: E402
import run_experiment  # noqa: E402
import study  # noqa: E402
from test_sql_evaluator import build_smoke_partitions  # noqa: E402

SQL_EVALUATOR = ROOT / "studies" / "runtime" / "sql" / "evaluate.py"
C_EVALUATOR = ROOT / "studies" / "runtime" / "evaluate.py"
SQL_EXAMPLE = ROOT / "studies" / "sql" / "example"
C_EXAMPLE = ROOT / "studies" / "c18" / "example"
# The v20 manifests (current); the v19 ones are kept as study-v9.json / study-v5.json.
CURRENT_MANIFESTS = {"sql": ROOT / "studies" / "sql" / "study.json", "c18": ROOT / "studies" / "c18" / "study.json"}


def run_sql_evaluator(root: Path, fixture: str, partition: Path, *, example: Path | None = SQL_EXAMPLE) -> dict:
    workspace = root / f"ws-{fixture}"
    if workspace.exists():
        shutil.rmtree(workspace)
    shutil.copytree(ROOT / "fixtures" / fixture, workspace)
    task = root / f"task-{fixture}.json"
    task.write_text(json.dumps({"runtime": "sql-engine", "parameters": {"script_timeout_seconds": 60, "sqlite_version": sqlite3.sqlite_version}}))
    output = root / f"{fixture}.json"
    command = [
        sys.executable, str(SQL_EVALUATOR), "--workspace", str(workspace),
        "--tests-root", str(partition), "--manifest", str(partition / "manifest.json"),
        "--candidate-config", str(workspace / "candidate.json"), "--task-config", str(task),
        "--max-stage", "8", "--output", str(output), "--summary-json",
    ]
    if example is not None:
        command += ["--example", str(example)]
    subprocess.run(command, check=True, capture_output=True, text=True, cwd=ROOT)
    return json.loads(output.read_text(encoding="utf-8"))


class SqlExampleCheckTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temporary = tempfile.TemporaryDirectory(prefix="picc-round-check-sql-")
        cls.root = Path(cls.temporary.name)
        cls.partition = build_smoke_partitions(cls.root) / "visible"

    @classmethod
    def tearDownClass(cls) -> None:
        cls.temporary.cleanup()

    def test_the_example_matches_the_specification_text(self) -> None:
        spec = (ROOT / "studies" / "sql" / "task.md").read_text()
        self.assertIn((SQL_EXAMPLE / "input.sql").read_text().rstrip("\n").replace("\n", "\n    "), spec)
        self.assertIn((SQL_EXAMPLE / "expected.txt").read_text().rstrip("\n").replace("\n", "\n    "), spec)
        self.assertNotIn("no such table", (ROOT / "studies" / "sql" / "task-minimal.md").read_text())

    def test_reference_backed_engine_passes_the_example(self) -> None:
        summary = run_sql_evaluator(self.root, "mock-pisql-sqlite", self.partition)["summary"]
        check = summary["check"]
        self.assertTrue(check["passed"], check)
        self.assertTrue(check["build"]["ok"] and check["audit"]["ok"])
        self.assertEqual(check["example"]["status"], "passed")
        self.assertEqual(check["example"]["returncode"], 0)
        self.assertEqual(check["commands"], {"build": "python3 -m py_compile pisql.py", "entry": "python3 pisql.py INPUT"})

    def test_wrong_output_is_reported_next_to_the_required_output(self) -> None:
        summary = run_sql_evaluator(self.root, "mock-pisql-constant", self.partition)["summary"]
        example = summary["check"]["example"]
        self.assertFalse(summary["check"]["passed"])
        self.assertEqual(example["status"], "output_differs")
        self.assertEqual(example["expected"], (SQL_EXAMPLE / "expected.txt").read_text())
        self.assertTrue(example["output"].strip())
        self.assertNotEqual(example["output"], example["expected"])
        # The reject-all engine answers `error` to the one statement that may
        # fail and to the six that may not.
        reject = run_sql_evaluator(self.root, "mock-pisql-reject", self.partition)["summary"]["check"]["example"]
        self.assertEqual(reject["status"], "output_differs")
        self.assertEqual(reject["output"].count("error"), 7)
        self.assertEqual(reject["first_difference"]["line"], 1)
        self.assertEqual(reject["first_difference"]["required"], "ok 0")

    def test_no_example_flag_means_no_check(self) -> None:
        summary = run_sql_evaluator(self.root, "mock-pisql-sqlite", self.partition, example=None)["summary"]
        self.assertNotIn("check", summary)

    def test_error_lines_match_on_the_word_alone(self) -> None:
        # Both scorers are called evaluate.py; load the SQL one by path.
        spec = importlib.util.spec_from_file_location("sql_evaluate", SQL_EVALUATOR)
        sql_evaluate = importlib.util.module_from_spec(spec)
        sys.modules["sql_evaluate"] = sql_evaluate
        spec.loader.exec_module(sql_evaluate)

        expected = (SQL_EXAMPLE / "expected.txt").read_text()
        self.assertTrue(sql_evaluate.example_outputs_match(expected, expected))
        self.assertTrue(sql_evaluate.example_outputs_match(expected.replace("error no such table: missing", "error table missing does not exist"), expected))
        self.assertTrue(sql_evaluate.example_outputs_match(expected.rstrip("\n"), expected))
        self.assertFalse(sql_evaluate.example_outputs_match(expected.replace("2\tNULL\t3.0", "2\tNULL\t3"), expected))
        self.assertFalse(sql_evaluate.example_outputs_match(expected.replace("ok 2\n", "ok 2\n", 1).replace("\t", "|"), expected))
        self.assertFalse(sql_evaluate.example_outputs_match("", expected))
        # The first differing line, as the message reports it.
        self.assertIsNone(sql_evaluate.example_first_difference(expected, expected))
        self.assertEqual(
            sql_evaluate.example_first_difference(expected.replace("ok 0\nok 0\nok 0\n", "ok 0\nok 1\nok 1\n"), expected),
            {"line": 2, "printed": "ok 1", "required": "ok 0"},
        )
        self.assertEqual(sql_evaluate.example_first_difference("", expected), {"line": 1, "printed": None, "required": "ok 0"})
        self.assertEqual(sql_evaluate.example_first_difference(expected + "extra\n", expected), {"line": 12, "printed": "extra", "required": None})


class CompilerExampleCheckTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if not Path("/usr/bin/gcc").exists():
            raise unittest.SkipTest("/usr/bin/gcc is required")
        cls.temporary = tempfile.TemporaryDirectory(prefix="picc-round-check-c-")
        cls.root = Path(cls.temporary.name)
        partitions = cls.root / "partitions"
        subprocess.run(
            [
                sys.executable, str(ROOT / "scripts" / "test_sets" / "split_tests.py"), "--source", str(ROOT / "fixtures" / "smoke-c18"),
                "--output", str(partitions), "--seed", "20260916", "--visible-fraction", "0.7", "--max-stage", "18",
                "--scope", "core-with-fixtures", "--source-revision", "local-smoke",
            ],
            check=True, capture_output=True, text=True, cwd=ROOT,
        )
        cls.tests = partitions / "visible"

    @classmethod
    def tearDownClass(cls) -> None:
        cls.temporary.cleanup()

    def evaluate(self, fixture: str) -> dict:
        workspace = self.root / f"ws-{fixture}"
        if workspace.exists():
            shutil.rmtree(workspace)
        shutil.copytree(ROOT / "fixtures" / fixture, workspace)
        output = self.root / f"{fixture}.json"
        subprocess.run(
            [
                sys.executable, str(C_EVALUATOR), "--workspace", str(workspace), "--tests-root", str(self.tests),
                "--manifest", str(self.tests / "manifest.json"), "--candidate-config", str(workspace / "candidate.json"),
                "--max-stage", "18", "--cache-dir", str(self.root / "cache"), "--output", str(output), "--summary-json",
                "--example", str(C_EXAMPLE),
            ],
            check=True, capture_output=True, text=True, cwd=ROOT,
        )
        return json.loads(output.read_text())

    def test_the_examples_match_the_specification_text(self) -> None:
        spec = (ROOT / "studies" / "c18" / "task.md").read_text()
        self.assertIn("    " + (C_EXAMPLE / "valid.c").read_text().strip(), spec)
        self.assertIn("    " + (C_EXAMPLE / "invalid.c").read_text().strip(), spec)
        self.assertEqual(json.loads((C_EXAMPLE / "example.json").read_text())["valid"]["exit_status"], 5)

    def test_gcc_backed_compiler_passes_both_examples(self) -> None:
        check = self.evaluate("mock-picc-gcc")["summary"]["check"]
        self.assertTrue(check["passed"], check)
        self.assertEqual(check["example"]["valid"]["status"], "passed")
        self.assertEqual(check["example"]["valid"]["exit_status"], 5)
        self.assertEqual(check["example"]["invalid"]["status"], "passed")

    def test_reject_all_and_constant_compilers_fail_one_example_each(self) -> None:
        reject = self.evaluate("mock-picc-reject")["summary"]["check"]["example"]
        self.assertFalse(reject["passed"])
        self.assertEqual(reject["valid"]["status"], "rejected")
        self.assertTrue(reject["invalid"]["passed"])
        constant = self.evaluate("mock-picc-constant")["summary"]["check"]["example"]
        self.assertFalse(constant["passed"])
        self.assertEqual(constant["invalid"]["status"], "accepted")
        self.assertIn(constant["valid"]["status"], {"wrong_exit_status", "passed"})
        self.assertIsNotNone(constant["valid"]["exit_status"])


class RoundCheckMessageTests(unittest.TestCase):
    CONTINUE = "Continue.\n"

    def check(self, **overrides) -> dict:
        base = {
            "commands": {"build": "cargo build --release --offline", "entry": "./target/release/pisql INPUT.sql"},
            "build": {"ok": True, "ran": True, "timed_out": False, "returncode": 0, "output": None},
            "audit": {"ok": True, "findings": []},
            "example": None,
            "passed": False,
        }
        base.update(overrides)
        return base

    def message(self, check: dict | None, error: str | None = None) -> str:
        visible: dict = {"score": 0.0}
        if check is not None:
            visible["check"] = check
        if error:
            visible["error"] = error
        return run_experiment.round_check_message(visible, self.CONTINUE)

    def test_every_message_starts_with_the_check_and_ends_with_the_continuation(self) -> None:
        for check in (None, self.check(), self.check(build={"ok": False, "ran": True, "timed_out": False, "returncode": 101, "output": "error[E0425]: x"})):
            text = self.message(check)
            self.assertTrue(text.startswith(run_experiment.ROUND_CHECK_HEAD + "\n"), text)
            self.assertTrue(text.endswith("\n\nContinue.\n"), text)
            for word in ("score", "test", "hidden", "round "):
                self.assertNotIn(word, text.lower().replace("standard", ""))

    def test_build_failure_shows_the_command_and_its_output(self) -> None:
        text = self.message(self.check(build={"ok": False, "ran": True, "timed_out": False, "returncode": 1, "output": "pisql.py:12: error: Incompatible types\npisql.py:40: error: Missing return"}))
        self.assertIn("The build command `cargo build --release --offline`, run in /workspace, failed:", text)
        self.assertIn("    pisql.py:12: error: Incompatible types\n    pisql.py:40: error: Missing return", text)
        timed_out = self.message(self.check(build={"ok": False, "ran": True, "timed_out": True, "returncode": -9, "output": ""}))
        self.assertIn("did not finish within its time limit:\n    (no output)", timed_out)

    def test_forbidden_source_is_named(self) -> None:
        text = self.message(self.check(audit={"ok": False, "findings": [{"path": "pisql.py", "line": 3, "reason": "prohibited python module", "excerpt": "import sqlite3"}]}))
        self.assertIn("The program was not built: the source check found what the specification forbids.", text)
        self.assertIn("    pisql.py:3: prohibited python module: import sqlite3", text)

    def test_sql_example_differs_shows_both_outputs(self) -> None:
        expected = (SQL_EXAMPLE / "expected.txt").read_text()
        example = {"passed": False, "status": "output_differs", "output": "1|x|2.5\n2||3\n", "expected": expected, "returncode": 0, "timed_out": False, "timeout_seconds": 120, "stderr": "",
                   "first_difference": {"line": 1, "printed": "1|x|2.5", "required": "ok 0"}}
        text = self.message(self.check(example=example))
        self.assertIn("\n\nThe first difference is on line 1: the program printed `1|x|2.5`, the specification requires `ok 0`.", text)
        nothing = self.message(self.check(example={**example, "output": "", "first_difference": {"line": 1, "printed": None, "required": "ok 0"}}))
        self.assertIn("The first difference is on line 1: the program printed nothing, the specification requires `ok 0`.", nothing)
        extra = self.message(self.check(example={**example, "first_difference": {"line": 12, "printed": "x", "required": None}}))
        self.assertIn("the program printed `x`, the specification requires nothing more.", extra)
        self.assertIn("Run as `./target/release/pisql INPUT.sql` on the example input from the specification, the program printed:\n    1|x|2.5\n    2||3\n\nThe specification requires:\n    ok 0\n    ok 0\n    ok 0\n    ok 2\n    2\tNULL\t3.0", text)
        self.assertNotIn("exited with status", text)
        empty = self.message(self.check(example={**example, "output": "", "returncode": 1, "stderr": "Traceback\nValueError: x"}))
        self.assertIn("printed:\n    (nothing)\n", empty)
        self.assertIn("It exited with status 1.", empty)
        self.assertIn("On standard error it printed:\n    Traceback\n    ValueError: x", empty)
        slow = self.message(self.check(example={**example, "status": "timed_out", "timed_out": True, "returncode": -9}))
        self.assertIn("It did not finish within 120 seconds.", slow)

    def test_sql_example_passed_is_one_line(self) -> None:
        text = self.message(self.check(passed=True, example={"passed": True, "status": "passed", "output": "x", "expected": "x", "returncode": 0, "timed_out": False, "timeout_seconds": 120, "stderr": ""}))
        self.assertIn("succeeded, and run as `./target/release/pisql INPUT.sql` on the example input from the specification, the program printed exactly the required output.", text)
        self.assertNotIn("requires", text)

    def test_compiler_examples_are_reported_one_by_one(self) -> None:
        valid = {"source": "int main(void) { return 2 + 3; }\n", "expected_exit_status": 5, "compiler_returncode": 0, "compiler_timed_out": False, "compiler_stderr": "", "assembly_written": True, "link_stderr": None, "exit_status": 0, "status": "wrong_exit_status", "passed": False}
        invalid = {"source": "int main(void) { return 2 + ; }\n", "compiler_returncode": 0, "compiler_timed_out": False, "compiler_stderr": "", "assembly_written": True, "status": "accepted", "passed": False}
        text = self.message(self.check(commands={"build": "cargo build --release --offline", "entry": "./target/release/picc INPUT.c OUTPUT.s"}, example={"passed": False, "valid": valid, "invalid": invalid}))
        self.assertIn("On the first example (`int main(void) { return 2 + 3; }`), which must give a program that exits with status 5:\n    the assembled and linked program exited with status 0.", text)
        self.assertIn("On the second example (`int main(void) { return 2 + ; }`), which must be rejected with a nonzero exit status, a diagnostic on standard error and no `OUTPUT.s`:\n    the compiler exited 0 and wrote `OUTPUT.s`.", text)
        rejected = self.message(self.check(example={"passed": False, "valid": {**valid, "status": "rejected", "compiler_returncode": 1, "compiler_stderr": "panic at src/main.rs:10", "assembly_written": False}, "invalid": {**invalid, "status": "passed", "passed": True}}))
        self.assertIn("    the compiler exited with status 1 and wrote no usable `OUTPUT.s`.\n    The compiler printed on standard error:\n        panic at src/main.rs:10", rejected)
        self.assertIn("    the compiler rejected it as required.", rejected)
        passed = self.message(self.check(passed=True, example={"passed": True, "valid": {**valid, "status": "passed", "passed": True, "exit_status": 5}, "invalid": {**invalid, "status": "passed", "passed": True}}))
        self.assertIn("the compiler behaved as the specification requires.", passed)

    def test_an_evaluator_failure_is_said_plainly(self) -> None:
        text = self.message(None, error="evaluator exit 2: boom")
        self.assertIn("The check could not be completed this time (evaluator exit 2: boom).", text)


class RoundCheckManifestTests(unittest.TestCase):
    def setUp(self) -> None:
        self.payload, self.conditions = study.load_study(CURRENT_MANIFESTS["sql"])
        self.condition = copy.deepcopy(self.conditions[0])

    def test_absent_block_is_none_and_adds_nothing(self) -> None:
        _, conditions = study.load_study(ROOT / "studies" / "sql" / "study-v9.json")
        self.assertNotIn("round_check", conditions[0])
        self.assertEqual(study.condition_round_check(conditions[0]), {"mode": "none"})
        study.validate_condition(conditions[0], {"id": "x"})

    def test_rejects_bad_modes_examples_and_runtime_mismatch(self) -> None:
        for block, fragment in (
            ({"mode": "tests"}, "mode must be one of"),
            ({"mode": "none", "example": "studies/sql/example"}, "only valid with a mode other"),
            ({"mode": "build-and-example"}, "round_check.example"),
            ({"mode": "build-and-example", "example": "studies/sql"}, "holding example.json"),
            ({"mode": "build-and-example", "example": "studies/c18/example"}, "runtime"),
            ({"mode": "build-and-example", "example": "studies/sql/example", "extra": 1}, "unknown keys"),
        ):
            condition = copy.deepcopy(self.condition)
            condition["round_check"] = block
            with self.assertRaises(study.StudyError, msg=str(block)) as caught:
                study.validate_condition(condition, self.payload)
            self.assertIn(fragment, str(caught.exception))

    def test_v20_manifests_turn_the_check_on_for_every_condition(self) -> None:
        for name, path in CURRENT_MANIFESTS.items():
            payload, conditions = study.load_study(path)
            with self.subTest(study=name):
                self.assertEqual(payload["id"], {"sql": "picc-sql-minimal-v10", "c18": "picc-c18-minimal-v6"}[name])
                for row in conditions:
                    self.assertEqual(study.condition_round_check(row), {"mode": "build-and-example", "example": f"studies/{name}/example"})
                    self.assertEqual(row["prompt"]["continuation"], "studies/shared/minimal-protocol/continue.txt")
                # Apart from the id, description and the round check, the v20 manifest is the v19 one.
                old_payload, old_conditions = study.load_study(ROOT / "studies" / name / {"sql": "study-v9.json", "c18": "study-v5.json"}[name])
                self.assertEqual([c["id"] for c in conditions], [c["id"] for c in old_conditions])
                for new, old in zip(conditions, old_conditions, strict=True):
                    stripped = {k: v for k, v in new.items() if k != "round_check"}
                    self.assertEqual(stripped, old)

    def test_materialization_freezes_the_example_and_the_switch(self) -> None:
        for name, path in CURRENT_MANIFESTS.items():
            hidden = {"sql": "data/partitions-sql/hidden", "c18": "data/partitions-c18/hidden"}[name]
            if not (ROOT / hidden / "manifest.json").is_file():
                continue
            payload, conditions = study.load_study(path)
            for condition in (conditions[0], conditions[-1]):
                with self.subTest(study=name, condition=condition["id"]):
                    run_id = f"unit-round-check-{name}-{uuid.uuid4().hex}"
                    root = ROOT / "runs" / ".study-materializations" / run_id
                    self.addCleanup(shutil.rmtree, root, ignore_errors=True)
                    study.materialize(path, payload, condition, run_id)
                    example_dir = root / "evaluator" / "example"
                    self.assertEqual(
                        sorted(p.name for p in example_dir.iterdir()),
                        sorted(p.name for p in (ROOT / "studies" / name / "example").iterdir()),
                    )
                    record = json.loads((root / "study-materialization.json").read_text())
                    self.assertEqual(record["effective_config"]["ROUND_CHECK"], "build-and-example")
                    self.assertEqual((root / "prompts" / "CONTINUE.txt").read_text(), "Continue.\n")
                    initial = (root / "prompts" / "INITIAL.txt").read_text()
                    if name == "sql":
                        example_text = (example_dir / "expected.txt").read_text().rstrip("\n").replace("\n", "\n    ")
                    else:
                        example_text = (example_dir / "valid.c").read_text().strip()
                    # The full specification shows the example the check uses; the
                    # minimal one does not, and learns of it only through the check.
                    if condition["id"] == "rust-minimal-spec":
                        self.assertNotIn(example_text, initial)
                    else:
                        self.assertIn(example_text, initial)
                    command = common.evaluation_command(
                        {"EXPERIMENT_IMAGE": "img", "EVALUATION_MEMORY": "8g"}, container_name="c", workspace=root,
                        tests=root, evaluator=root / "evaluator", artifacts=root, output_name="o.json", max_stage=1,
                    )
                    self.assertEqual(command[-2:], ["--example", "/opt/picc-eval/example"])


if __name__ == "__main__":
    unittest.main()
