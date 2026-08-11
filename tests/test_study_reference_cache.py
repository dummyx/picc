from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tests.test_study_evaluator import digest, evaluator


class ReferenceCacheTests(unittest.TestCase):
    def test_cached_failure_is_retried_and_success_replaces_it(self) -> None:
        with tempfile.TemporaryDirectory(prefix="picc-reference-cache-") as temporary:
            root = Path(temporary)
            source = root / "input.c"
            source.write_text("int main(void) { return 0; }\n", encoding="utf-8")
            test = {"sha256": digest(source)}
            cache = root / "cache"
            cache.mkdir()
            cache_path = cache / f"{evaluator.cache_key(test)}.json"
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
                result = evaluator.reference_result(source, test, cache, 10, 10)

            self.assertEqual(run.call_count, 2)
            self.assertTrue(result["ok"])
            self.assertTrue(json.loads(cache_path.read_text(encoding="utf-8"))["ok"])

    def test_transient_reference_failure_is_not_cached(self) -> None:
        with tempfile.TemporaryDirectory(prefix="picc-reference-cache-") as temporary:
            root = Path(temporary)
            source = root / "input.c"
            source.write_text("int main(void) { return 0; }\n", encoding="utf-8")
            test = {"sha256": digest(source)}
            cache = root / "cache"
            failure = evaluator.CommandResult(["gcc"], 1, "", "failed", 0.1, False)

            with mock.patch.object(evaluator, "run_command", return_value=failure):
                result = evaluator.reference_result(source, test, cache, 10, 10)

            self.assertFalse(result["ok"])
            self.assertFalse((cache / f"{evaluator.cache_key(test)}.json").exists())
