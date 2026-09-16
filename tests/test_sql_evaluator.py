from __future__ import annotations

import json
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EVALUATOR = ROOT / "studies" / "runtime" / "sql" / "evaluate.py"
SMOKE = ROOT / "fixtures" / "smoke-sql"


def build_smoke_partitions(root: Path) -> Path:
    output = root / "partitions"
    subprocess.run(
        [
            sys.executable, str(ROOT / "scripts" / "select_sqllogictest.py"),
            "--source", str(SMOKE), "--selection", str(SMOKE / "selection.json"),
            "--output", str(output), "--seed", "20260916", "--visible-fraction", "0.7",
            "--source-revision", "local-smoke",
        ],
        check=True, capture_output=True, text=True, cwd=ROOT,
    )
    return output


def run_evaluator(root: Path, fixture: str, partition: Path, *, sqlite_version: str | None = None, timeout: int = 60) -> dict:
    workspace = root / f"ws-{fixture}"
    if workspace.exists():
        shutil.rmtree(workspace)
    shutil.copytree(ROOT / "fixtures" / fixture, workspace)
    task = root / f"task-{fixture}.json"
    parameters = {"script_timeout_seconds": timeout}
    if sqlite_version is not None:
        parameters["sqlite_version"] = sqlite_version
    task.write_text(json.dumps({"runtime": "sql-engine", "parameters": parameters}), encoding="utf-8")
    output = root / f"{fixture}.json"
    result = subprocess.run(
        [
            sys.executable, str(EVALUATOR), "--workspace", str(workspace),
            "--tests-root", str(partition), "--manifest", str(partition / "manifest.json"),
            "--candidate-config", str(workspace / "candidate.json"), "--task-config", str(task),
            "--max-stage", "8", "--output", str(output), "--summary-json",
        ],
        capture_output=True, text=True, cwd=ROOT,
    )
    payload = json.loads(output.read_text(encoding="utf-8"))
    payload["_returncode"] = result.returncode
    return payload


class SqlEvaluatorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temporary = tempfile.TemporaryDirectory(prefix="picc-sql-eval-")
        cls.root = Path(cls.temporary.name)
        cls.partitions = build_smoke_partitions(cls.root)
        cls.all_scripts = cls.root / "all"
        # One partition holding every smoke script, for the candidate comparisons.
        cls.all_scripts.mkdir()
        rows = []
        for partition in ("visible", "hidden"):
            manifest = json.loads((cls.partitions / partition / "manifest.json").read_text())
            for row in manifest["tests"]:
                source = cls.partitions / partition / row["relative_path"]
                target = cls.all_scripts / row["relative_path"]
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)
                rows.append(row)
        (cls.all_scripts / "manifest.json").write_text(json.dumps({**manifest, "partition": "all", "tests": rows}))

    @classmethod
    def tearDownClass(cls) -> None:
        cls.temporary.cleanup()

    def test_reference_backed_candidate_scores_everything(self) -> None:
        payload = run_evaluator(self.root, "mock-pisql-sqlite", self.all_scripts, sqlite_version=sqlite3.sqlite_version)
        summary = payload["summary"]
        self.assertEqual(payload["_returncode"], 0)
        self.assertTrue(summary["build_ok"] and summary["audit_ok"], payload.get("source_audit"))
        self.assertEqual(summary["score"], 1.0, summary)
        self.assertEqual(summary["passed"], 2)
        self.assertEqual(summary["records_passed"], summary["records_total"])
        self.assertEqual(payload["task"]["sqlite_version"], sqlite3.sqlite_version)
        for row in payload["tests"]:
            self.assertEqual(row["records"]["reference_disagreements"], 0)
            self.assertEqual(row["records"]["setup_failures"], 0)
            self.assertEqual(row["score"], 1.0)
        # Records the reference runner would skip or halt on are neither executed nor scored.
        basic = next(row for row in payload["tests"] if row["id"].endswith("create_insert_select.test"))
        self.assertEqual(basic["records"]["executed"], 4 + 9 + 1)
        self.assertEqual(basic["records"]["total"], 9 + 1)
        rules = next(row for row in payload["tests"] if row["id"].endswith("null_and_join.test"))
        self.assertEqual(rules["records"]["executed"], 6 + 3 + 1)

    def test_reject_all_candidate_earns_only_the_expected_error_records(self) -> None:
        payload = run_evaluator(self.root, "mock-pisql-reject", self.all_scripts)
        summary = payload["summary"]
        self.assertTrue(summary["build_ok"])
        # The smoke corpus holds exactly two `statement error` records (one per
        # script); rejecting everything satisfies those and nothing else.
        self.assertEqual(summary["records_passed"], 2)
        self.assertEqual(summary["passed"], 0)
        self.assertAlmostEqual(summary["score"], (1 / 10 + 1 / 4) / 2)
        for row in payload["tests"]:
            self.assertEqual(row["failure_type"], "wrong_results")
            self.assertGreater(row["records"]["setup_failures"], 0)

    def test_constant_output_candidate_scores_low(self) -> None:
        payload = run_evaluator(self.root, "mock-pisql-constant", self.all_scripts)
        summary = payload["summary"]
        self.assertTrue(summary["build_ok"])
        self.assertLess(summary["score"], 0.15, summary)
        self.assertEqual(summary["passed"], 0)
        self.assertEqual(summary["records_passed"], 0)
        # Setup statements are not scored, so `ok` answers earn nothing there.
        self.assertEqual(summary["records_total"], 10 + 4)

    def test_pinned_sqlite_version_mismatch_refuses_to_score(self) -> None:
        payload = run_evaluator(self.root, "mock-pisql-sqlite", self.all_scripts, sqlite_version="0.0.1")
        self.assertEqual(payload["_returncode"], 2)
        self.assertIn("refusing to score", payload["error"])

    def test_script_timeout_is_recorded(self) -> None:
        workspace = self.root / "ws-slow"
        shutil.copytree(ROOT / "fixtures" / "mock-pisql-sqlite", workspace)
        (workspace / "pisql.py").write_text("import time\ntime.sleep(5)\n", encoding="utf-8")
        payload = run_evaluator(self.root, "mock-pisql-sqlite", self.all_scripts, timeout=1)
        # run_evaluator copies the fixture afresh; patch the copy and rerun directly instead.
        shutil.rmtree(self.root / "ws-mock-pisql-sqlite")
        shutil.copytree(workspace, self.root / "ws-mock-pisql-sqlite")
        output = self.root / "slow.json"
        subprocess.run(
            [
                sys.executable, str(EVALUATOR), "--workspace", str(self.root / "ws-mock-pisql-sqlite"),
                "--tests-root", str(self.all_scripts), "--manifest", str(self.all_scripts / "manifest.json"),
                "--candidate-config", str(workspace / "candidate.json"), "--task-config", str(self.root / "task-mock-pisql-sqlite.json"),
                "--output", str(output), "--summary-json",
            ],
            capture_output=True, text=True, cwd=ROOT,
        )
        payload = json.loads(output.read_text())
        self.assertEqual({row["failure_type"] for row in payload["tests"]}, {"script_timeout"})
        self.assertEqual(payload["summary"]["score"], 0.0)

    def test_real_sql_adapters_prohibit_database_engines(self) -> None:
        sys.path.insert(0, str(ROOT / "studies" / "runtime"))
        import candidate_runtime  # noqa: E402

        adapters = ROOT / "studies" / "assets" / "candidates" / "sql"
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary)
            (workspace / "pisql.py").write_text("import sqlite3\nprint(sqlite3.sqlite_version)\n", encoding="utf-8")
            audit = candidate_runtime.source_audit(workspace, json.loads((adapters / "python-stdlib.json").read_text()))
            self.assertTrue(audit["blocking"], audit)
            self.assertEqual(audit["blocking_findings"][0]["value"], "sqlite3")
            (workspace / "src").mkdir()
            (workspace / "src" / "pisql.js").write_text("const { DatabaseSync } = require('node:sqlite');\n", encoding="utf-8")
            audit = candidate_runtime.source_audit(workspace, json.loads((adapters / "javascript-node.json").read_text()))
            self.assertTrue(audit["blocking"], audit)
            self.assertTrue(any(f.get("value") == "node:sqlite" for f in audit["blocking_findings"]), audit)
            (workspace / "src" / "main.rs").mkdir(parents=True, exist_ok=True)
            (workspace / "src" / "main.rs").rmdir()
            (workspace / "src" / "main.rs").write_text("use rusqlite::Connection;\nfn main() {}\n", encoding="utf-8")
            audit = candidate_runtime.source_audit(workspace, json.loads((adapters / "rust-std.json").read_text()))
            self.assertTrue(audit["blocking"], audit)
            self.assertTrue(any(f.get("reason") == "database engine library reference" for f in audit["blocking_findings"]), audit)


if __name__ == "__main__":
    unittest.main()
