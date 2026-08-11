from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tests.test_study_evaluator import evaluator


class CandidateIsolationTests(unittest.TestCase):
    def test_subprocess_environment_excludes_provider_credentials(self) -> None:
        inherited = {
            "PATH": "/usr/bin",
            "HOME": "/state/home",
            "LANG": "C.UTF-8",
            "ZAI_API_KEY": "secret-global",
            "ZAI_CODING_CN_API_KEY": "secret-cn",
            "UNRELATED_PRIVATE_VALUE": "secret-other",
        }
        with mock.patch.dict(evaluator.os.environ, inherited, clear=True):
            env = evaluator.subprocess_environment({"CARGO_NET_OFFLINE": "true"})

        self.assertEqual(env["PATH"], "/usr/bin")
        self.assertEqual(env["HOME"], "/tmp")
        self.assertEqual(env["TMPDIR"], "/tmp")
        self.assertEqual(env["CARGO_NET_OFFLINE"], "true")
        self.assertNotIn("ZAI_API_KEY", env)
        self.assertNotIn("ZAI_CODING_CN_API_KEY", env)
        self.assertNotIn("UNRELATED_PRIVATE_VALUE", env)

    def test_source_audit_scans_test_paths_and_nested_cargo_manifests(self) -> None:
        with tempfile.TemporaryDirectory(prefix="picc-evaluator-audit-") as temporary:
            workspace = Path(temporary).resolve()
            hidden = workspace / "tests" / "implementation.py"
            hidden.parent.mkdir()
            hidden.write_text("import subprocess\n", encoding="utf-8")
            python_adapter = {
                "source_extensions": [".py"],
                "audit": {
                    "python_stdlib_only": True,
                    "allowed_python_modules": [],
                    "exclude_test_paths": True,
                },
            }
            python_audit = evaluator.source_audit(workspace, python_adapter)
            self.assertFalse(python_audit["passed"])
            self.assertTrue(
                any(row.get("path") == "tests/implementation.py" for row in python_audit["findings"])
            )

            member = workspace / "member"
            member.mkdir()
            (member / "Cargo.toml").write_text(
                '[package]\nname = "member"\nversion = "0.1.0"\n'
                '[dependencies]\nserde = "1"\n',
                encoding="utf-8",
            )
            rust_audit = evaluator.source_audit(
                workspace,
                {"source_extensions": [".rs"], "audit": {"allowed_dependencies": []}},
            )
            self.assertFalse(rust_audit["passed"])
            self.assertTrue(
                any(row.get("path") == "member/Cargo.toml" for row in rust_audit["findings"])
            )

    def test_rust_argument_access_is_not_environment_inspection(self) -> None:
        with tempfile.TemporaryDirectory(prefix="picc-evaluator-audit-") as temporary:
            workspace = Path(temporary).resolve()
            (workspace / "main.rs").write_text(
                "use std::env;\nfn main() { let _ = env::args_os(); }\n",
                encoding="utf-8",
            )
            audit = evaluator.source_audit(
                workspace,
                {"source_extensions": [".rs"], "audit": {"allowed_dependencies": []}},
            )
            self.assertTrue(audit["passed"], audit["findings"])
