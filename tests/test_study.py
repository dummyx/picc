from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import study  # noqa: E402


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_partition(root: Path, partition: str) -> Path:
    destination = root / partition
    rows = []
    fixtures = {
        "tests/chapter_1/valid/return_2.c": "int main(void) { return 2; }\n",
        "tests/chapter_1/valid/return_3.c": "int main(void) { return 3; }\n",
        "tests/chapter_1/invalid_parse/missing_semicolon.c": "int main(void) { return 2 }\n",
        "tests/chapter_1/invalid_parse/missing_brace.c": "int main(void) { return 2;\n",
    }
    for relative, content in fixtures.items():
        path = destination / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        validity = "valid" if "/valid/" in relative else "invalid"
        rows.append(
            {
                "id": relative,
                "relative_path": relative,
                "stage": 1,
                "validity": validity,
                "family": str(Path(relative).with_suffix("")),
                "sha256": sha(path),
            }
        )
    manifest = {
        "schema_version": 1,
        "partition": partition,
        "source": {"revision": "test"},
        "counts": {"total": len(rows)},
        "tests": rows,
    }
    (destination / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return destination


class StudyManifestTests(unittest.TestCase):
    def test_starter_manifest_is_valid_and_unique(self) -> None:
        payload, conditions = study.load_study(ROOT / "studies" / "starter" / "study.json")
        self.assertEqual(payload["id"], "picc-essential-v1")
        self.assertEqual(len(conditions), 12)
        self.assertEqual(len({row["id"] for row in conditions}), len(conditions))
        baseline = next(row for row in conditions if row["id"] == "baseline")
        self.assertEqual(baseline["tests"]["access"], "tool")
        self.assertEqual(baseline["candidate"]["language"], "rust")

    def test_visible_subset_is_deterministic_and_stratified(self) -> None:
        rows = []
        for stage in (1, 2):
            for validity in ("valid", "invalid"):
                for index in range(8):
                    rows.append(
                        {
                            "id": f"s{stage}/{validity}/{index}.c",
                            "relative_path": f"s{stage}/{validity}/{index}.c",
                            "stage": stage,
                            "validity": validity,
                            "family": f"s{stage}/{validity}/family-{index}",
                            "sha256": "0" * 64,
                        }
                    )
        manifest = {"tests": rows}
        first = study.select_visible_tests(manifest, 0.25, 7)
        second = study.select_visible_tests(manifest, 0.25, 7)
        self.assertEqual(first, second)
        strata = {(row["stage"], row["validity"]) for row in first}
        self.assertEqual(strata, {(1, "valid"), (1, "invalid"), (2, "valid"), (2, "invalid")})
        self.assertEqual(len(first), 8)


class ScheduleTests(unittest.TestCase):
    def test_schedule_is_deterministic_with_stable_run_ids(self) -> None:
        study_path = Path("studies/starter/study.json")
        with tempfile.TemporaryDirectory(prefix="picc-study-schedule-") as temporary:
            payloads = []
            for filename in ("first.json", "second.json"):
                output = Path(temporary) / filename
                result = subprocess.run(
                    [
                        sys.executable,
                        str(ROOT / "scripts" / "study.py"),
                        "schedule",
                        "--study",
                        str(study_path),
                        "--replicates",
                        "2",
                        "--profile",
                        "pilot",
                        "--output",
                        str(output),
                    ],
                    cwd=ROOT,
                    check=False,
                    capture_output=True,
                    text=True,
                )
                self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
                payloads.append(json.loads(output.read_text(encoding="utf-8")))

        self.assertEqual(payloads[0], payloads[1])
        payload = payloads[0]
        rows = payload["rows"]
        self.assertEqual(len(rows), 24)
        self.assertEqual([row["sequence"] for row in rows], list(range(1, 25)))
        self.assertEqual(
            [row["condition"] for row in rows[:12]],
            [
                "tests-none",
                "tests-files",
                "spec-brief",
                "tests-quarter",
                "spec-architecture",
                "reference-oracle",
                "scaffold-rust",
                "language-python",
                "tests-aggregate",
                "spec-inline",
                "prompt-minimal",
                "baseline",
            ],
        )
        for row in rows:
            replicate = row["replicate"]
            expected_run_id = f"picc-essential-v1-pilot-r{replicate:02d}-{row['condition']}"
            self.assertEqual(row["run_id"], expected_run_id)
            self.assertEqual(row["profile"], "pilot")
            self.assertIn(f"RUN_ID={expected_run_id}", row["command"])
            self.assertIn(f"REPLICATE={replicate}", row["command"])


class MaterializationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.partition_root = ROOT / "data" / ".study-test-partitions"
        self.materialization_id = "unit-study-materialization"
        self.materialization = ROOT / "runs" / ".study-materializations" / self.materialization_id
        self.withheld_id = "unit-study-withheld"
        self.withheld = ROOT / "runs" / ".study-materializations" / self.withheld_id
        shutil.rmtree(self.partition_root, ignore_errors=True)
        shutil.rmtree(self.materialization, ignore_errors=True)
        shutil.rmtree(self.withheld, ignore_errors=True)
        write_partition(self.partition_root, "visible")
        write_partition(self.partition_root, "hidden")

    def tearDown(self) -> None:
        shutil.rmtree(self.partition_root, ignore_errors=True)
        shutil.rmtree(self.materialization, ignore_errors=True)
        shutil.rmtree(self.withheld, ignore_errors=True)

    def condition_with_test_partitions(self, condition_id: str):
        payload, conditions = study.load_study(ROOT / "studies" / "starter" / "study.json")
        condition = next(row for row in conditions if row["id"] == condition_id)
        condition = study.deep_merge(
            condition,
            {
                "tests": {
                    "visible_partition": str(self.partition_root.relative_to(ROOT) / "visible"),
                    "hidden_partition": str(self.partition_root.relative_to(ROOT) / "hidden"),
                }
            },
        )
        return payload, condition

    def test_materialization_freezes_condition_and_renders_extensions(self) -> None:
        payload, condition = self.condition_with_test_partitions("reference-oracle")
        root = study.materialize(
            ROOT / "studies" / "starter" / "study.json",
            payload,
            condition,
            self.materialization_id,
        )
        self.assertEqual(root, self.materialization)
        tools = (root / "pi" / "extensions" / "experiment-tools.ts").read_text(encoding="utf-8")
        runner = (root / "scripts" / "run_experiment.py").read_text(encoding="utf-8")
        self.assertIn('const REFERENCE_MODE = "oracle"', tools)
        self.assertIn("const ORACLE_LIMIT = 50", tools)
        self.assertIn("reference_oracle", runner)
        self.assertIn("__pycache__/", runner)
        self.assertNotIn("__REFERENCE_MODE__", tools)
        self.assertTrue((root / "study-materialization.json").is_file())
        self.assertTrue((root / "data" / "partitions" / "hidden" / "manifest.json").is_file())

        node = shutil.which("node")
        if node is not None:
            probe = subprocess.run(
                [node, "-e", "require.resolve('typescript')"],
                check=False,
                capture_output=True,
                text=True,
            )
            if probe.returncode == 0:
                script = r"""
const fs = require('node:fs');
const ts = require('typescript');
let failed = false;
for (const filename of process.argv.slice(1)) {
  const result = ts.transpileModule(fs.readFileSync(filename, 'utf8'), {
    fileName: filename, reportDiagnostics: true,
    compilerOptions: {target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ESNext, strict: true}
  });
  for (const diagnostic of result.diagnostics || []) {
    failed = true;
    console.error(ts.flattenDiagnosticMessageText(diagnostic.messageText, '\n'));
  }
}
process.exit(failed ? 1 : 0);
"""
                extensions = sorted(str(path) for path in (root / "pi" / "extensions").glob("*.ts"))
                transpile = subprocess.run(
                    [node, "-e", script, *extensions],
                    check=False, capture_output=True, text=True,
                )
                self.assertEqual(transpile.returncode, 0, transpile.stderr)


    def test_tests_none_physically_withholds_agent_visible_test_files(self) -> None:
        payload, condition = self.condition_with_test_partitions("tests-none")
        root = study.materialize(
            ROOT / "studies" / "starter" / "study.json",
            payload,
            condition,
            self.withheld_id,
        )
        agent_manifest = json.loads((root / "data" / "agent-visible" / "manifest.json").read_text())
        harness_manifest = json.loads((root / "data" / "partitions" / "visible" / "manifest.json").read_text())
        self.assertEqual(agent_manifest["tests"], [])
        self.assertGreater(len(harness_manifest["tests"]), 0)
        runner = (root / "scripts" / "run_experiment.py").read_text(encoding="utf-8")
        self.assertIn("visible_tests=agent_visible_tests,", runner)



class GenericEvaluatorTests(unittest.TestCase):
    def test_python_adapter_evaluates_valid_and_invalid_programs(self) -> None:
        with tempfile.TemporaryDirectory(prefix="picc-study-eval-") as temporary:
            temp = Path(temporary)
            workspace = temp / "workspace"
            tests = temp / "tests"
            workspace.mkdir()
            tests.mkdir()
            compiler = workspace / "picc.py"
            compiler.write_text(
                """#!/usr/bin/env python3
import pathlib
import re
import sys

args = sys.argv[1:]
if len(args) != 3 or args[1] != '-o':
    raise SystemExit(2)
source = pathlib.Path(args[0]).read_text()
match = re.fullmatch(r'\\s*int\\s+main\\(void\\)\\s*\\{\\s*return\\s+(\\d+)\\s*;\\s*\\}\\s*', source)
if not match:
    print('error: unsupported construct', file=sys.stderr)
    raise SystemExit(1)
value = int(match.group(1))
pathlib.Path(args[2]).write_text(f'.globl main\\nmain:\\n  movl ${value}, %eax\\n  ret\\n')
""",
                encoding="utf-8",
            )
            valid = tests / "valid.c"
            invalid = tests / "invalid.c"
            valid.write_text("int main(void) { return 7; }\n", encoding="utf-8")
            invalid.write_text("int main(void) { return 7 }\n", encoding="utf-8")
            manifest = {
                "schema_version": 1,
                "partition": "visible",
                "source": {"revision": "unit"},
                "tests": [
                    {
                        "id": "valid.c",
                        "relative_path": "valid.c",
                        "stage": 1,
                        "validity": "valid",
                        "family": "valid",
                        "sha256": sha(valid),
                    },
                    {
                        "id": "invalid.c",
                        "relative_path": "invalid.c",
                        "stage": 1,
                        "validity": "invalid",
                        "family": "invalid",
                        "sha256": sha(invalid),
                    },
                ],
            }
            manifest_path = tests / "manifest.json"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            output = temp / "result.json"
            result = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "studies" / "runtime" / "evaluate.py"),
                    "--workspace",
                    str(workspace),
                    "--tests-root",
                    str(tests),
                    "--manifest",
                    str(manifest_path),
                    "--candidate-config",
                    str(ROOT / "studies" / "assets" / "candidates" / "python-stdlib.json"),
                    "--max-stage",
                    "1",
                    "--cache-dir",
                    str(temp / "cache"),
                    "--output",
                    str(output),
                    "--summary-json",
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            summary = json.loads(result.stdout)
            self.assertEqual(summary["score"], 1.0)
            self.assertEqual(summary["passed"], 2)
            self.assertTrue(summary["build_ok"])
            self.assertTrue(summary["audit_ok"])


if __name__ == "__main__":
    unittest.main()
