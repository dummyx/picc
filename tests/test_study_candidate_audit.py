from __future__ import annotations

import json
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
            rust_policy = {"source_extensions": [".rs"], "audit": {"allowed_dependencies": []}}
            # A nested manifest the root build does not compile is developer
            # tooling, not the product (v9 Amendment 2): no finding.
            (workspace / "Cargo.toml").write_text(
                '[package]\nname = "picc"\nversion = "0.1.0"\n[dependencies]\n', encoding="utf-8"
            )
            self.assertTrue(evaluator.source_audit(workspace, rust_policy)["passed"])
            # Declared as a workspace member, it is built, so it is audited.
            (workspace / "Cargo.toml").write_text(
                '[package]\nname = "picc"\nversion = "0.1.0"\n[dependencies]\n'
                '[workspace]\nmembers = ["member"]\n',
                encoding="utf-8",
            )
            rust_audit = evaluator.source_audit(workspace, rust_policy)
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


class RustCandidateAuditTests(unittest.TestCase):
    """Rust candidates: the audit covers the Cargo package's src/ and whatever
    src/ pulls in by path, not the agent's own test tooling (v6 Amendment 2)."""

    ADAPTER = {"source_extensions": [".rs"], "audit": {"allowed_dependencies": []}}

    def workspace(self, files: dict[str, str]) -> Path:
        temporary = tempfile.TemporaryDirectory(prefix="picc-rust-audit-")
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name).resolve()
        (root / "Cargo.toml").write_text('[package]\nname = "picc"\nversion = "0.1.0"\nedition = "2021"\n', encoding="utf-8")
        for relative, content in files.items():
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
        return root

    def test_fuzzer_under_tests_is_not_the_compiler(self) -> None:
        # The v6-tests-none-r3 case: a differential fuzzer under tests/ assembles,
        # links, and runs the compiler's output with std::process::Command.
        root = self.workspace(
            {
                "src/main.rs": "mod lex;\nfn main() { lex::run(); }\n",
                "src/lex.rs": "pub fn run() {}\n",
                "tests/fuzz.rs": 'use std::process::Command;\nfn main() { Command::new("as").output().unwrap(); }\n',
                "devtest/run.sh": "#!/bin/sh\n./target/release/picc $1\n",
            }
        )
        audit = evaluator.source_audit(root, self.ADAPTER)
        self.assertTrue(audit["passed"], audit["findings"])
        self.assertFalse(audit["blocking"])
        self.assertEqual(audit["source_files_scanned"], 2)

    def test_out_of_build_devtools_crate_depending_on_the_candidate_is_not_a_dependency(self) -> None:
        """v9-tests-none-r1: a self-written simulator crate under devtools/ with
        `picc = { path = ".." }` and its own [workspace]; the root build never
        compiles it (v9 Amendment 2)."""
        root = self.workspace(
            {
                "Cargo.toml": '[package]\nname = "picc"\nversion = "0.1.0"\n[dependencies]\n',
                "src/main.rs": "fn main() {}\n",
                "devtools/Cargo.toml": '[package]\nname = "picc-devtools"\nversion = "0.1.0"\n'
                '[dependencies]\npicc = { path = ".." }\n[workspace]\n',
                "devtools/src/main.rs": "fn main() { let _ = std::process::Command::new(\"as\"); }\n",
            }
        )
        audit = evaluator.source_audit(root, self.ADAPTER)
        self.assertTrue(audit["passed"], audit["findings"])

    def test_subprocess_use_inside_src_is_still_blocking(self) -> None:
        root = self.workspace({"src/main.rs": 'use std::process::Command;\nfn main() { Command::new("gcc"); }\n'})
        audit = evaluator.source_audit(root, self.ADAPTER)
        self.assertTrue(audit["blocking"])
        self.assertEqual({row.get("path") for row in audit["blocking_findings"]}, {"src/main.rs"})

    def test_path_attribute_and_include_pull_outside_files_into_the_audit(self) -> None:
        root = self.workspace(
            {
                "src/main.rs": '#[path = "../helpers/extra.rs"]\nmod extra;\nfn main() { extra::go(); }\n',
                "helpers/extra.rs": 'use std::process::Command;\npub fn go() { Command::new("cc"); }\n',
                "tests/bench.rs": "use std::process::Command;\n",
            }
        )
        audit = evaluator.source_audit(root, self.ADAPTER)
        self.assertTrue(audit["blocking"])
        paths = {row.get("path") for row in audit["blocking_findings"]}
        self.assertEqual(paths, {"helpers/extra.rs"})
        self.assertEqual(audit["source_files_scanned"], 2)

        included = self.workspace(
            {
                "src/main.rs": 'fn main() { let t = include_str!("../assets/table.rs"); }\n',
                "assets/table.rs": 'pub const RUN: &str = "std::process::Command";\n',
            }
        )
        audit = evaluator.source_audit(included, self.ADAPTER)
        self.assertIn("assets/table.rs", {row.get("path") for row in audit["findings"]})

    def test_declared_roots_still_win(self) -> None:
        adapter = {"source_extensions": [".rs"], "audit": {"allowed_dependencies": [], "roots": ["compiler"]}}
        root = self.workspace(
            {
                "compiler/main.rs": "fn main() {}\n",
                "src/legacy.rs": "use std::process::Command;\n",
            }
        )
        audit = evaluator.source_audit(root, adapter)
        self.assertTrue(audit["passed"], audit["findings"])
        self.assertEqual(audit["source_files_scanned"], 1)


class NodeCandidateAuditTests(unittest.TestCase):
    """JavaScript/TypeScript candidates: imports, manifests, suppressions, and build output."""

    TS_ADAPTER = {
        "source_extensions": [".ts", ".mts", ".cts"],
        "audit": {
            "roots": ["src"],
            "entry": "src/picc.ts",
            "node_builtins_only": True,
            "allowed_node_modules": [],
            "exclude_paths": ["dist"],
        },
    }
    JS_ADAPTER = {
        "source_extensions": [".js", ".mjs", ".cjs"],
        "audit": {
            "roots": ["src"],
            "entry": "src/picc.js",
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

    def test_package_manifests_outside_the_build_are_not_audited(self) -> None:
        """v9 Amendment 2 for Node: only the root package.json and declared
        workspaces are the product's manifests."""
        root = self.workspace(
            {
                "src/picc.js": "process.exit(0);\n",
                "package.json": '{"name": "picc", "dependencies": {}}\n',
                "tools/package.json": '{"name": "tools", "dependencies": {"lodash": "^4"}}\n',
            }
        )
        self.assertFalse(evaluator.source_audit(root, self.JS_ADAPTER)["blocking"])
        (root / "package.json").write_text('{"name": "picc", "dependencies": {}, "workspaces": ["tools"]}\n', encoding="utf-8")
        audit = evaluator.source_audit(root, self.JS_ADAPTER)
        self.assertTrue(audit["blocking"])
        self.assertIn(("dependency", "lodash"), {(row.get("kind"), row.get("value")) for row in audit["blocking_findings"]})

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

    def test_test_drivers_outside_the_source_roots_are_not_the_compiler(self) -> None:
        # The v4 first-run case: a fuzz driver in .scratch/ spawns the candidate.
        root = self.workspace(
            {
                "src/picc.js": 'const { lex } = require("./lexer");\nprocess.exitCode = lex() ? 0 : 1;\n',
                "src/lexer.js": "module.exports = { lex: () => true };\n",
                ".scratch/fuzz2.js": 'const { execFileSync } = require("child_process");\nexecFileSync("node", ["src/picc.js"]);\n',
                "dev/runone.js": 'require("node:child_process").spawnSync("as");\n',
            }
        )
        audit = evaluator.source_audit(root, self.JS_ADAPTER)
        self.assertTrue(audit["passed"], audit["findings"])
        self.assertEqual(audit["source_files_scanned"], 2)

    def test_import_closure_still_reaches_modules_outside_the_roots(self) -> None:
        root = self.workspace(
            {
                "src/picc.js": 'const helper = require("../lib/helper");\nhelper.run();\n',
                "lib/helper.js": 'const cp = require("child_process");\nmodule.exports = { run: () => cp.execSync("gcc") };\n',
            }
        )
        audit = evaluator.source_audit(root, self.JS_ADAPTER)
        self.assertTrue(audit["blocking"], audit["findings"])
        self.assertIn("lib/helper.js", {row.get("path") for row in audit["blocking_findings"]})
        self.assertEqual(audit["source_files_scanned"], 2)

        typed = self.workspace(
            {
                "src/picc.ts": 'import { lex } from "./lexer";\nimport * as util from "../tools/util";\nlex(); util.x;\n',
                "src/lexer.ts": "export function lex(): void {}\n",
                "tools/util.ts": 'import { spawn } from "node:child_process";\nexport const x = spawn;\n',
                "tools/bench.ts": 'import "node:child_process";\n',
            }
        )
        audit = evaluator.source_audit(typed, self.TS_ADAPTER)
        self.assertTrue(audit["blocking"])
        paths = {row.get("path") for row in audit["blocking_findings"]}
        self.assertIn("tools/util.ts", paths)
        self.assertNotIn("tools/bench.ts", paths)

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


class PythonAuditScopeTests(unittest.TestCase):
    """v10 Amendment 2: the Python audit covers the entry module's import
    closure, not every .py file in the workspace."""

    ROOT = Path(__file__).resolve().parent.parent
    ADAPTER = "studies/assets/candidates/sql/python-untyped.json"

    def audit(self, files: dict[str, str], adapter: dict | None = None) -> dict:
        if adapter is None:
            adapter = json.loads((self.ROOT / self.ADAPTER).read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory(prefix="picc-python-audit-") as temporary:
            workspace = Path(temporary).resolve()
            for name, text in files.items():
                path = workspace / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(text, encoding="utf-8")
            return evaluator.source_audit(workspace, adapter)

    def test_agent_test_driver_outside_the_closure_is_not_audited(self) -> None:
        audit = self.audit(
            {
                "pisql.py": "import sys\nprint('ok 0')\n",
                "tests/run_tests.py": "import subprocess\nsubprocess.run(['pisql'])\n",
                "difftest.py": "import subprocess\n",
            }
        )
        self.assertFalse(audit["blocking"], audit["blocking_findings"])
        self.assertEqual(audit["source_files_scanned"], 1)

    def test_product_and_its_imports_are_still_audited(self) -> None:
        delegating = self.audit({"pisql.py": "import sqlite3\n"})
        self.assertTrue(delegating["blocking"])
        self.assertEqual(delegating["blocking_findings"][0]["value"], "sqlite3")

        indirect = self.audit({"pisql.py": "import engine\n", "engine.py": "import subprocess\n"})
        self.assertTrue(indirect["blocking"], indirect)
        self.assertEqual(indirect["source_files_scanned"], 2)

        package = self.audit(
            {
                "pisql.py": "from pkg import core\n",
                "pkg/__init__.py": "",
                "pkg/core.py": "from . import helper\n",
                "pkg/helper.py": "import socket\n",
            }
        )
        self.assertTrue(package["blocking"], package)
        self.assertEqual(package["source_files_scanned"], 4)

    def test_missing_entry_module_scans_nothing(self) -> None:
        audit = self.audit({"notes.md": "no code yet"})
        self.assertFalse(audit["blocking"])
        self.assertEqual(audit["source_files_scanned"], 0)

    def test_explicit_roots_still_win(self) -> None:
        adapter = json.loads((self.ROOT / self.ADAPTER).read_text(encoding="utf-8"))
        adapter["audit"]["roots"] = ["."]
        audit = self.audit(
            {"pisql.py": "print('ok 0')\n", "helper.py": "import subprocess\n"},
            adapter=adapter,
        )
        self.assertTrue(audit["blocking"], audit)
