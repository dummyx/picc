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
