from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tests.test_study_evaluator import evaluator


class ReferenceCacheTests(unittest.TestCase):
    def test_cached_failure_is_retried_and_success_replaces_it(self) -> None:
        with tempfile.TemporaryDirectory(prefix="picc-reference-cache-") as temporary:
            root = Path(temporary)
            source = root / "input.c"
            source.write_text("int main(void) { return 0; }\n", encoding="utf-8")
            cache = root / "cache"
            cache.mkdir()
            cache_path = cache / f"{evaluator.cache_key(source)}.json"
            cache_path.write_text(
                json.dumps({"ok": False, "failure_type": "reference_timeout"}),
                encoding="utf-8",
            )
            compile_result = evaluator.CommandResult(
                ["gcc"],
                0,
                "",
                "",
                0.1,
                False,
            )
            execution = evaluator.CommandResult(
                ["reference"],
                0,
                "expected output",
                "",
                0.1,
                False,
            )

            with mock.patch.object(
                evaluator,
                "run_command",
                side_effect=[compile_result, execution],
            ) as run:
                result = evaluator.reference_result(source, cache, 10, 10)

            self.assertEqual(run.call_count, 2)
            self.assertTrue(result["ok"])
            self.assertTrue(json.loads(cache_path.read_text(encoding="utf-8"))["ok"])

    def test_transient_reference_failure_is_not_cached(self) -> None:
        with tempfile.TemporaryDirectory(prefix="picc-reference-cache-") as temporary:
            root = Path(temporary)
            source = root / "input.c"
            source.write_text("int main(void) { return 0; }\n", encoding="utf-8")
            cache = root / "cache"
            failure = evaluator.CommandResult(["gcc"], 1, "", "failed", 0.1, False)

            with mock.patch.object(evaluator, "run_command", return_value=failure):
                result = evaluator.reference_result(source, cache, 10, 10)

            self.assertFalse(result["ok"])
            self.assertFalse((cache / f"{evaluator.cache_key(source)}.json").exists())

    def test_success_is_reused_until_source_changes(self) -> None:
        with tempfile.TemporaryDirectory(prefix="picc-reference-cache-") as temporary:
            root = Path(temporary)
            source = root / "input.c"
            source.write_text("int main(void) { return 0; }\n", encoding="utf-8")
            cache = root / "cache"
            compile_result = evaluator.CommandResult(["gcc"], 0, "", "", 0.1, False)
            first_execution = evaluator.CommandResult(["reference"], 0, "", "", 0.1, False)
            changed_execution = evaluator.CommandResult(["reference"], 1, "", "", 0.1, False)

            with mock.patch.object(
                evaluator,
                "run_command",
                side_effect=[compile_result, first_execution, compile_result, changed_execution],
            ) as run:
                first = evaluator.reference_result(source, cache, 10, 10)
                cached = evaluator.reference_result(source, cache, 10, 10)
                self.assertEqual(run.call_count, 2)
                self.assertEqual(cached, first)

                source.write_text("int main(void) { return 1; }\n", encoding="utf-8")
                changed = evaluator.reference_result(source, cache, 10, 10)

            self.assertEqual(run.call_count, 4)
            self.assertEqual(first["returncode"], 0)
            self.assertEqual(changed["returncode"], 1)
