from __future__ import annotations

import hashlib
import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SPEC = importlib.util.spec_from_file_location(
    "picc_study_evaluator",
    ROOT / "studies" / "runtime" / "evaluate.py",
)
assert SPEC is not None and SPEC.loader is not None
evaluator = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = evaluator
SPEC.loader.exec_module(evaluator)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class TestSourceIntegrityTests(unittest.TestCase):
    def test_accepts_only_contained_regular_file_with_matching_digest(self) -> None:
        with tempfile.TemporaryDirectory(prefix="picc-evaluator-integrity-") as temporary:
            root = Path(temporary).resolve()
            source = root / "valid" / "return.c"
            source.parent.mkdir()
            source.write_text("int main(void) { return 0; }\n", encoding="utf-8")
            row = {"relative_path": "valid/return.c", "sha256": digest(source)}

            self.assertEqual(evaluator.resolve_test_source(root, row), source)

            source.write_text("int main(void) { return 1; }\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "SHA-256 mismatch"):
                evaluator.resolve_test_source(root, row)

    def test_rejects_traversal_invalid_digest_and_symlink(self) -> None:
        with tempfile.TemporaryDirectory(prefix="picc-evaluator-integrity-") as temporary:
            root = Path(temporary).resolve()
            source = root / "test.c"
            source.write_text("int main(void) { return 0; }\n", encoding="utf-8")

            invalid_rows = [
                {"relative_path": "", "sha256": digest(source)},
                {"relative_path": ".", "sha256": digest(source)},
                {"relative_path": "../test.c", "sha256": digest(source)},
                {"relative_path": str(source), "sha256": digest(source)},
                {"relative_path": "test.c", "sha256": "not-a-digest"},
            ]
            for row in invalid_rows:
                with self.subTest(row=row):
                    with self.assertRaises(ValueError):
                        evaluator.resolve_test_source(root, row)

            link = root / "link.c"
            try:
                link.symlink_to(source)
            except OSError:
                self.skipTest("symlinks are unavailable on this host")
            with self.assertRaisesRegex(ValueError, "must not be a symlink"):
                evaluator.resolve_test_source(
                    root,
                    {"relative_path": "link.c", "sha256": digest(source)},
                )


if __name__ == "__main__":
    unittest.main()


class CandidateInputPreprocessingTests(unittest.TestCase):
    """The candidate sees the test after the C preprocessor, as upstream's driver does."""

    def setUp(self) -> None:
        evaluator.PREPROCESS_FALLBACKS.clear()

    def test_directives_are_resolved_and_comments_kept(self) -> None:
        if not Path("/usr/bin/gcc").exists():
            self.skipTest("/usr/bin/gcc is required")
        with tempfile.TemporaryDirectory(prefix="picc-preprocess-") as temporary:
            temp = Path(temporary)
            source = temp / "test.c"
            source.write_text(
                "#ifdef SUPPRESS_WARNINGS\n#pragma GCC diagnostic ignored \"-Wunused\"\n#endif\n"
                "/* keep me */\nint main(void) {\n    return 2; // trailing\n}\n",
                encoding="utf-8",
            )
            copied = evaluator.candidate_input(source, temp, 30)
            text = copied.read_text(encoding="utf-8")
            self.assertEqual(copied.name, "input.c")
            self.assertNotIn("#", text)
            self.assertIn("/* keep me */", text)
            self.assertIn("// trailing", text)
            self.assertIn("return 2;", text)
            self.assertNotIn("Free Software Foundation", text)
            self.assertEqual(evaluator.PREPROCESS_FALLBACKS, [])
            self.assertEqual(evaluator.input_policy()["raw_fallbacks"], [])

    def test_failed_preprocessing_falls_back_to_the_raw_file(self) -> None:
        with tempfile.TemporaryDirectory(prefix="picc-preprocess-") as temporary:
            temp = Path(temporary)
            source = temp / "odd.c"
            source.write_text("#error deliberate\nint main(void) { return 1; }\n", encoding="utf-8")
            copied = evaluator.candidate_input(source, temp, 30)
            self.assertEqual(copied.read_text(encoding="utf-8"), source.read_text(encoding="utf-8"))
            self.assertEqual(len(evaluator.PREPROCESS_FALLBACKS), 1)
            self.assertTrue(evaluator.PREPROCESS_FALLBACKS[0].startswith("odd.c:"))
            policy = evaluator.input_policy()
            self.assertTrue(policy["fallback_to_raw_on_failure"])
            self.assertEqual(policy["preprocess"], "-E -P -C -nostdinc -x c")
