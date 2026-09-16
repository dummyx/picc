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
import split_tests  # noqa: E402

EVALUATOR = ROOT / "studies" / "runtime" / "evaluate.py"
SMOKE = ROOT / "fixtures" / "smoke-c18"


class FixtureScopeSplitTests(unittest.TestCase):
    def test_fixture_scope_records_partner_units_helpers_headers_and_link_flags(self) -> None:
        tests_root, cases, exclusions = split_tests.collect_tests(SMOKE, 18, "core-with-fixtures")
        by_id = {case.test_id: case for case in cases}
        self.assertEqual(exclusions, {})
        lib = by_id["chapter_11/valid/libraries/add_long.c"]
        client = by_id["chapter_11/valid/libraries/add_long_client.c"]
        self.assertEqual([(f.relative.as_posix(), f.kind) for f in lib.fixtures], [("chapter_11/valid/libraries/add_long_client.c", "c")])
        self.assertEqual([(f.relative.as_posix(), f.kind) for f in client.fixtures], [("chapter_11/valid/libraries/add_long.c", "c")])
        self.assertEqual(lib.family, client.family)
        asm = by_id["chapter_18/valid/structs/use_asm_helper.c"]
        self.assertEqual([(f.relative.as_posix(), f.kind) for f in asm.fixtures], [("chapter_18/valid/structs/big_data_on_page_boundary_linux.s", "assembly")])
        header = by_id["chapter_18/valid/structs/use_header.c"]
        self.assertEqual([(f.relative.as_posix(), f.kind) for f in header.fixtures], [("chapter_18/valid/structs/point.h", "header")])
        dotdot = by_id["chapter_18/invalid_types/missing_member.c"]
        self.assertEqual(dotdot.fixtures[0].relative.as_posix(), "chapter_18/valid/structs/point.h")
        self.assertEqual(by_id["chapter_13/valid/calls/mathlib.c"].link_flags, ("-lm",))
        self.assertEqual(by_id["chapter_10/valid/putchar.c"].fixtures, ())

    def test_core_scope_is_unchanged(self) -> None:
        _, cases, exclusions = split_tests.collect_tests(SMOKE, 18, "core")
        ids = {case.test_id for case in cases}
        self.assertNotIn("chapter_11/valid/libraries/add_long.c", ids)
        self.assertEqual(exclusions.get("excluded_directory"), 2)
        self.assertTrue(all(case.fixtures == () and case.link_flags == () for case in cases))


class FixtureEvaluationTests(unittest.TestCase):
    """The evaluator compiles or assembles fixtures on its own side and links them with the candidate's assembly."""

    @classmethod
    def setUpClass(cls) -> None:
        if not Path("/usr/bin/gcc").exists():
            raise unittest.SkipTest("/usr/bin/gcc is required")
        cls.temporary = tempfile.TemporaryDirectory(prefix="picc-c18-eval-")
        cls.root = Path(cls.temporary.name)
        partitions = cls.root / "partitions"
        subprocess.run(
            [
                sys.executable, str(ROOT / "scripts" / "split_tests.py"), "--source", str(SMOKE), "--output", str(partitions),
                "--seed", "20260916", "--visible-fraction", "0.7", "--max-stage", "18", "--scope", "core-with-fixtures",
                "--source-revision", "local-smoke",
            ],
            check=True, capture_output=True, text=True, cwd=ROOT,
        )
        # Evaluate every smoke test at once: merge both partitions.
        cls.tests = cls.root / "tests"
        rows = []
        for partition in ("visible", "hidden"):
            manifest = json.loads((partitions / partition / "manifest.json").read_text())
            shutil.copytree(partitions / partition, cls.tests, dirs_exist_ok=True)
            rows.extend(manifest["tests"])
        (cls.tests / "manifest.json").write_text(json.dumps({**manifest, "partition": "all", "tests": rows}))

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
                sys.executable, str(EVALUATOR), "--workspace", str(workspace), "--tests-root", str(self.tests),
                "--manifest", str(self.tests / "manifest.json"), "--candidate-config", str(workspace / "candidate.json"),
                "--max-stage", "18", "--cache-dir", str(self.root / "cache"), "--output", str(output), "--summary-json",
            ],
            check=True, capture_output=True, text=True, cwd=ROOT,
        )
        return json.loads(output.read_text())

    def test_gcc_backed_candidate_passes_every_fixture_bearing_test(self) -> None:
        payload = self.evaluate("mock-picc-gcc")
        summary = payload["summary"]
        self.assertTrue(summary["build_ok"] and summary["audit_ok"], payload["source_audit"])
        self.assertEqual(summary["score"], 1.0, summary)
        self.assertEqual(summary["total"], 8)

    def test_reject_all_and_constant_candidates(self) -> None:
        reject = self.evaluate("mock-picc-reject")["summary"]
        self.assertEqual(reject["stages"]["11"]["valid"]["passed"], 0)
        self.assertEqual(reject["stages"]["11"]["invalid"]["passed"], 1)
        constant = self.evaluate("mock-picc-constant")
        types = {row["id"]: row["failure_type"] for row in constant["tests"]}
        self.assertEqual(types["chapter_11/invalid_parse/bad_suffix.c"], "unexpected_accept")
        # The constant assembly defines main; linked with the client half (which
        # also defines main) it cannot link, with the library half it runs wrong.
        self.assertEqual(types["chapter_11/valid/libraries/add_long.c"], "assembly_or_link_failure")
        self.assertEqual(types["chapter_11/valid/libraries/add_long_client.c"], "wrong_behavior")
        self.assertEqual(types["chapter_13/valid/calls/mathlib.c"], "wrong_behavior")
        self.assertLess(constant["summary"]["score"], 0.3)

    def test_reference_cache_key_includes_fixtures_and_flags(self) -> None:
        from test_study_evaluator import evaluator as module
        source = self.tests / "chapter_11/valid/libraries/add_long.c"
        partner = self.tests / "chapter_11/valid/libraries/add_long_client.c"
        plain = module.cache_key(source)
        self.assertNotEqual(plain, module.cache_key(source, [("c", partner)]))
        self.assertNotEqual(plain, module.cache_key(source, [], ["-lm"]))
        self.assertEqual(plain, module.cache_key(source, [], []))


if __name__ == "__main__":
    unittest.main()
