from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

from tests.test_study_evaluator import evaluator


class CandidateArtifactSafetyTests(unittest.TestCase):
    def test_build_cannot_replace_candidate_with_outside_symlink(self) -> None:
        with tempfile.TemporaryDirectory(prefix="picc-artifact-safety-") as temporary:
            root = Path(temporary).resolve()
            workspace = root / "workspace"
            workspace.mkdir()
            outside = root / "outside-compiler"
            outside.write_text("outside\n", encoding="utf-8")
            adapter = {
                "build": {
                    "artifact": "picc",
                    "command": [
                        sys.executable,
                        "-c",
                        f"import os; os.symlink({str(outside)!r}, 'picc')",
                    ],
                }
            }

            result, artifact = evaluator.build_candidate(workspace, adapter, 10)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("artifact policy failure", result.stderr)
            self.assertEqual(artifact, workspace / "picc")
            self.assertTrue(artifact.is_symlink())

    def test_configured_artifact_must_stay_inside_workspace(self) -> None:
        with tempfile.TemporaryDirectory(prefix="picc-artifact-safety-") as temporary:
            root = Path(temporary).resolve()
            workspace = root / "workspace"
            workspace.mkdir()
            adapter = {
                "build": {
                    "artifact": "../outside",
                    "command": [],
                }
            }

            with self.assertRaisesRegex(ValueError, "inside the workspace"):
                evaluator.build_candidate(workspace, adapter, 10)


    def test_source_symlink_is_an_audit_failure(self) -> None:
        with tempfile.TemporaryDirectory(prefix="picc-artifact-safety-") as temporary:
            root = Path(temporary).resolve()
            workspace = root / "workspace"
            workspace.mkdir()
            outside = root / "outside.py"
            outside.write_text("import subprocess\n", encoding="utf-8")
            try:
                (workspace / "picc.py").symlink_to(outside)
            except OSError:
                self.skipTest("symlinks are unavailable on this host")
            audit = evaluator.source_audit(workspace, {"source_extensions": [".py"], "audit": {}})
            self.assertFalse(audit["passed"])
            self.assertTrue(any(row.get("kind") == "symlink" for row in audit["findings"]))


if __name__ == "__main__":
    unittest.main()
