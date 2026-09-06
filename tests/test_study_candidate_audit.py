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


class NodeCandidateAuditTests(unittest.TestCase):
    """JavaScript/TypeScript candidates: imports, manifests, suppressions, and build output."""

    TS_ADAPTER = {
        "source_extensions": [".ts", ".mts", ".cts"],
        "audit": {
            "node_builtins_only": True,
            "allowed_node_modules": [],
            "exclude_paths": ["dist"],
        },
    }
    JS_ADAPTER = {
        "source_extensions": [".js", ".mjs", ".cjs"],
        "audit": {
            "node_builtins_only": True,
            "allowed_node_modules": [],
            "exclude_paths": [],
        },
    }

    def workspace(self, files: dict[str, str]) -> Path:
        temporary = tempfile.TemporaryDirectory(prefix="picc-node-audit-")
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name).resolve()
        for relative, content in files.items():
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
        return root

    def reasons(self, audit: dict) -> set[str]:
        return {str(row.get("reason")) for row in audit["findings"]}

    def test_clean_typescript_candidate_passes(self) -> None:
        root = self.workspace(
            {
                "src/picc.ts": (
                    'import * as fs from "node:fs";\n'
                    'import { join } from "path";\n'
                    'import type { Token } from "./lexer";\n'
                    'import { lex } from "./lexer.js";\n'
                    "const match = /x/y.exec(fs.readFileSync(process.argv[2], 'utf8'));\n"
                    "function fetch(): Token { return lex()[0]; }\n"
                    "process.exitCode = 0;\n"
                ),
                "src/lexer.ts": "export type Token = { kind: string };\nexport function lex(): Token[] { return []; }\n",
                "dist/picc.js": 'const cp = require("child_process");\n',
                "tsconfig.json": "{}\n",
            }
        )
        audit = evaluator.source_audit(root, self.TS_ADAPTER)
        self.assertTrue(audit["passed"], audit["findings"])
        self.assertFalse(audit["blocking"])
        self.assertEqual(audit["source_files_scanned"], 2)

    def test_subprocess_and_network_modules_are_blocking(self) -> None:
        for snippet in (
            'const { execSync } = require("child_process");\n',
            'import { spawn } from "node:child_process";\n',
            'const http = require("node:http");\n',
            'import net from "net";\n',
            'const wasi = await import("node:wasi");\n',
        ):
            with self.subTest(snippet=snippet):
                root = self.workspace({"src/picc.js": snippet})
                audit = evaluator.source_audit(root, self.JS_ADAPTER)
                self.assertTrue(audit["blocking"], audit["findings"])
                self.assertIn(
                    "subprocess, network, or dynamic-loading module is prohibited",
                    self.reasons(audit),
                )

    def test_non_builtin_import_and_package_manifests_are_blocking(self) -> None:
        root = self.workspace(
            {
                "src/picc.js": 'const _ = require("lodash");\nimport chalk from "chalk";\n',
                "package.json": '{"name": "picc", "dependencies": {"lodash": "^4"}, "devDependencies": {}}\n',
            }
        )
        audit = evaluator.source_audit(root, self.JS_ADAPTER)
        self.assertTrue(audit["blocking"])
        kinds = {(row.get("kind"), row.get("value")) for row in audit["blocking_findings"]}
        self.assertIn(("node_import", "lodash"), kinds)
        self.assertIn(("node_import", "chalk"), kinds)
        self.assertIn(("dependency", "lodash"), kinds)
        self.assertIn(
            "non-built-in module import is outside the frozen candidate policy",
            self.reasons(audit),
        )

    def test_vendored_node_modules_and_binary_artifacts_are_blocking(self) -> None:
        root = self.workspace(
            {
                "src/picc.js": "process.exitCode = 0;\n",
                "node_modules/left-pad/index.js": "module.exports = () => 0;\n",
                "vendor/cc.wasm": "\0asm",
            }
        )
        audit = evaluator.source_audit(root, self.JS_ADAPTER)
        self.assertTrue(audit["blocking"])
        kinds = {row.get("kind") for row in audit["blocking_findings"]}
        self.assertIn("dependency", kinds)
        self.assertIn("binary_artifact", kinds)

        empty = self.workspace({"src/picc.js": "process.exitCode = 0;\n", "node_modules/.keep": ""})
        # A directory without vendored code is not a dependency finding.
        self.assertEqual(
            [row for row in evaluator.source_audit(empty, self.JS_ADAPTER)["findings"] if row.get("kind") == "dependency"],
            [],
        )

    def test_environment_and_suppressions_are_advisory_only(self) -> None:
        root = self.workspace(
            {
                "src/picc.ts": (
                    "// @ts-nocheck\n"
                    'const debug = process.env.PICC_DBG !== undefined;\n'
                    "// @ts-ignore\n"
                    "process.exitCode = debug ? 1 : 0;\n"
                ),
            }
        )
        audit = evaluator.source_audit(root, self.TS_ADAPTER)
        self.assertFalse(audit["passed"])
        self.assertFalse(audit["blocking"], audit["blocking_findings"])
        self.assertEqual(
            self.reasons(audit),
            {"credential or environment inspection", "type-check suppression"},
        )
        self.assertEqual(len(audit["advisory_findings"]), 3)

    def test_build_output_and_stray_files_are_not_audit_findings(self) -> None:
        root = self.workspace(
            {
                "src/picc.js": "process.exitCode = 0;\n",
                "src/helper.ts": "export const x: number = 1;\n",
                "tools/run.o": "\x7fELF",
            }
        )
        # A file in another language and an object file from self-testing are
        # measured post hoc, not gated: neither is evidence of delegation.
        self.assertTrue(evaluator.source_audit(root, self.JS_ADAPTER)["passed"])

        typed = self.workspace(
            {
                "src/picc.ts": "process.exitCode = 0;\n",
                "dist/picc.js": 'require("child_process");\n',
                "dist/node_modules/x/index.js": "module.exports = 1;\n",
            }
        )
        self.assertTrue(evaluator.source_audit(typed, self.TS_ADAPTER)["passed"])

    def test_comments_cannot_trigger_blocking_findings(self) -> None:
        root = self.workspace(
            {
                "src/picc.ts": (
                    "// The experiment forbids child_process and require('net'); we use neither.\n"
                    "/* import { spawn } from 'node:child_process'; */\n"
                    "// @ts-ignore is also forbidden\n"
                    "process.exitCode = 0;\n"
                ),
            }
        )
        audit = evaluator.source_audit(root, self.TS_ADAPTER)
        self.assertFalse(audit["blocking"], audit["blocking_findings"])
        self.assertEqual(self.reasons(audit), {"type-check suppression"})
        self.assertEqual(audit["advisory_findings"][0]["line"], 3)

    def test_dynamic_loading_calls_are_blocking(self) -> None:
        for snippet in (
            'process.dlopen(module, "./cc.node");\n',
            'WebAssembly.instantiate(bytes, {});\n',
        ):
            with self.subTest(snippet=snippet):
                root = self.workspace({"src/picc.js": snippet})
                audit = evaluator.source_audit(root, self.JS_ADAPTER)
                self.assertTrue(audit["blocking"], audit["findings"])
                self.assertIn("dynamic loading or embedded binary execution", self.reasons(audit))

    def test_import_specifier_parsing(self) -> None:
        text = (
            'import * as fs from "node:fs";\n'
            "import {\n  a,\n  b,\n} from './local';\n"
            'import "./side-effect";\n'
            'export * from "./reexport";\n'
            'export { x } from "@scope/pkg/sub";\n'
            'const y = require( "fs/promises" );\n'
            'const z = await import("os");\n'
        )
        specifiers = evaluator.node_import_specifiers(text)
        self.assertEqual(
            sorted(specifiers),
            sorted(["node:fs", "./local", "./side-effect", "./reexport", "@scope/pkg/sub", "fs/promises", "os"]),
        )
        self.assertEqual(evaluator.node_module_root("node:fs/promises"), "fs")
        self.assertEqual(evaluator.node_module_root("@scope/pkg/sub"), "@scope/pkg")
        self.assertIsNone(evaluator.node_module_root("./local"))
        self.assertIsNone(evaluator.node_module_root("/abs"))
