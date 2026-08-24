#!/usr/bin/env python3
"""Language-neutral behavioral evaluator for PiCC study conditions.

The product contract is held constant across implementation languages:

    <candidate command> INPUT.c -o OUTPUT.s

Candidate build/run commands and source-audit policy are declared in the frozen
``candidate.json`` adapter.  GCC exists only on the evaluator side: it
establishes expected behavior and assembles/links emitted assembly.
"""

from __future__ import annotations

import argparse
import ast
import contextlib
import hashlib
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import traceback
from collections import defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

MAX_CAPTURE_BYTES = 1024 * 1024
DEPENDENCY_TABLES = {"dependencies", "dev-dependencies", "build-dependencies"}
SKIP_PARTS = {".git", ".pi", "target", "node_modules", "__pycache__", ".pytest_cache"}
SUBPROCESS_ENV_ALLOWLIST = {
    "CARGO_HOME",
    "LANG",
    "LC_ALL",
    "PATH",
    "RUSTUP_HOME",
    "TERM",
}
# Audit findings split into two kinds. A blocking finding means the candidate
# either delegated the task or is unsafe to execute, so its measured behaviour
# would be meaningless; those still gate scoring. An advisory finding is a broken
# rule that leaves the compiler both safe to run and honestly measurable — it is
# reported as its own compliance outcome rather than nullifying the score, so a
# single debug flag cannot erase an otherwise working compiler.
ADVISORY_AUDIT_REASONS = frozenset({"credential or environment inspection"})

DEFAULT_SOURCE_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (
        re.compile(
            r"\b(?:std::)?env::(?:var|var_os|vars|vars_os)\b|"
            r"\bstd::env::\{[^}\n]*\b(?:var|var_os|vars|vars_os)\b|\bos\.(?:environ|getenv)\b|"
            r"/proc(?:/[^\s]*)?/environ|"
            r"ZAI_(?:API_KEY|CODING_CN_API_KEY)|LOCAL_API_KEY",
            re.I,
        ),
        "credential or environment inspection",
    ),
    (
        re.compile(
            r"\b(?:std::)?process::Command\b|\bCommand::new\s*\(|"
            r"\bsubprocess\b|\bos\.system\s*\(|\bPopen\s*\(|\bexec[lvpe]*\s*\(",
            re.I,
        ),
        "subprocess invocation",
    ),
    (
        re.compile(r"\b(?:libclang|libgccjit|libtcc|LLVM|llvm[_-]sys|clang[_-]sys|tinycc|tcc)\b", re.I),
        "compiler library reference",
    ),
    (
        re.compile(
            r"\b(?:TcpStream|UdpSocket|requests|httpx|urllib|socket)\b|https?://",
            re.I,
        ),
        "network access",
    ),
]
PROHIBITED_PYTHON_MODULES = {
    "ctypes",
    "http",
    "multiprocessing",
    "requests",
    "socket",
    "subprocess",
    "urllib",
}


@dataclass
class CommandResult:
    args: list[str]
    returncode: int
    stdout: str
    stderr: str
    elapsed_seconds: float
    timed_out: bool = False


@dataclass
class TestResult:
    id: str
    stage: int
    validity: str
    passed: bool
    failure_type: str | None
    detail: str | None
    compile_seconds: float
    execute_seconds: float
    compiler_returncode: int | None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--tests-root", type=Path)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--candidate-config", type=Path, default=Path(__file__).with_name("candidate.json"))
    parser.add_argument("--max-stage", type=int, default=10)
    parser.add_argument("--latest-only", action="store_true")
    parser.add_argument("--test-id")
    parser.add_argument("--oracle-source", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--summary-json", action="store_true")
    parser.add_argument("--cache-dir", type=Path, default=Path("/run-artifacts/reference-cache"))
    parser.add_argument("--build-timeout", type=int, default=900)
    parser.add_argument("--compile-timeout", type=int, default=30)
    parser.add_argument("--run-timeout", type=int, default=10)
    args = parser.parse_args()
    if args.oracle_source is None and (args.tests_root is None or args.manifest is None):
        parser.error("--tests-root and --manifest are required unless --oracle-source is used")
    return args


def load_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return value


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def resolve_test_source(tests_root: Path, test: Mapping[str, Any]) -> Path:
    raw_relative = test.get("relative_path")
    if not isinstance(raw_relative, str) or not raw_relative.strip():
        raise ValueError("Test relative_path must be a nonempty string")
    relative = Path(raw_relative)
    if relative.is_absolute() or relative == Path(".") or ".." in relative.parts:
        raise ValueError(f"Test relative_path must stay within the partition: {raw_relative!r}")

    candidate = tests_root / relative
    if candidate.is_symlink():
        raise ValueError(f"Test source must not be a symlink: {raw_relative}")
    try:
        source = candidate.resolve(strict=True)
        source.relative_to(tests_root)
    except (FileNotFoundError, ValueError) as error:
        raise ValueError(f"Test source must resolve within the partition: {raw_relative}") from error
    if not source.is_file():
        raise ValueError(f"Test source is not a regular file: {raw_relative}")

    expected = test.get("sha256")
    if not isinstance(expected, str) or re.fullmatch(r"[0-9a-fA-F]{64}", expected) is None:
        raise ValueError(f"Test has an invalid SHA-256 digest: {raw_relative}")
    actual = sha256_file(source)
    if actual != expected.lower():
        raise ValueError(f"Test source SHA-256 mismatch: {raw_relative}")
    return source


def truncate(value: str, limit: int = 8000) -> str:
    if len(value) <= limit:
        return value
    return value[:limit] + f"\n... [truncated {len(value) - limit} characters]"


def atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(value, handle, indent=2, sort_keys=True, ensure_ascii=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        with contextlib.suppress(FileNotFoundError):
            os.unlink(temporary)


def subprocess_environment(overrides: Mapping[str, str] | None = None) -> dict[str, str]:
    env = {key: os.environ[key] for key in SUBPROCESS_ENV_ALLOWLIST if key in os.environ}
    env.setdefault("PATH", os.defpath)
    env.update({"HOME": "/tmp", "TMPDIR": "/tmp"})
    if overrides:
        env.update(overrides)
    return env


def run_command(
    args: Sequence[str],
    *,
    cwd: Path,
    timeout: int,
    env: Mapping[str, str] | None = None,
) -> CommandResult:
    started = time.monotonic()
    process = subprocess.Popen(
        list(args),
        cwd=cwd,
        env=subprocess_environment(env),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        errors="replace",
        start_new_session=True,
    )
    timed_out = False
    try:
        stdout, stderr = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        timed_out = True
        with contextlib.suppress(ProcessLookupError):
            os.killpg(process.pid, signal.SIGTERM)
        try:
            stdout, stderr = process.communicate(timeout=2)
        except subprocess.TimeoutExpired:
            with contextlib.suppress(ProcessLookupError):
                os.killpg(process.pid, signal.SIGKILL)
            stdout, stderr = process.communicate()
    return CommandResult(
        args=list(args),
        returncode=process.returncode if process.returncode is not None else 128,
        stdout=stdout[:MAX_CAPTURE_BYTES],
        stderr=stderr[:MAX_CAPTURE_BYTES],
        elapsed_seconds=time.monotonic() - started,
        timed_out=timed_out,
    )


def render_command(parts: Sequence[str], variables: Mapping[str, str]) -> list[str]:
    rendered: list[str] = []
    for part in parts:
        value = part
        for key, replacement in variables.items():
            value = value.replace("{" + key + "}", replacement)
        unresolved = re.findall(r"\{([a-zA-Z0-9_]+)\}", value)
        if unresolved:
            raise ValueError(f"Unresolved candidate command variables: {unresolved}")
        rendered.append(value)
    return rendered


def iter_dependency_tables(value: Any, path: tuple[str, ...] = ()) -> Iterable[tuple[tuple[str, ...], dict[str, Any]]]:
    if not isinstance(value, dict):
        return
    for key, child in value.items():
        child_path = (*path, str(key))
        if str(key) in DEPENDENCY_TABLES and isinstance(child, dict):
            yield child_path, child
        if isinstance(child, dict):
            yield from iter_dependency_tables(child, child_path)


def iter_source_files(
    workspace: Path,
    extensions: set[str],
    roots: Sequence[str] | None = None,
) -> Iterable[Path]:
    candidates: list[Path] = []
    for raw_root in roots or ["."]:
        root = (workspace / raw_root).resolve()
        try:
            root.relative_to(workspace)
        except ValueError:
            continue
        if root.is_file():
            candidates.append(root)
        elif root.is_dir():
            candidates.extend(root.rglob("*"))
    seen: set[Path] = set()
    for path in sorted(candidates):
        if path in seen or not path.is_file() or path.is_symlink():
            continue
        seen.add(path)
        relative = path.relative_to(workspace)
        if any(part in SKIP_PARTS for part in relative.parts):
            continue
        if path.suffix in extensions:
            yield path


def audit_cargo(workspace: Path, policy: dict[str, Any], findings: list[dict[str, Any]]) -> None:
    allowed = {str(item).lower().replace("_", "-") for item in policy.get("allowed_dependencies", [])}
    manifests: list[Path] = []
    for cargo_toml in sorted(workspace.rglob("Cargo.toml")):
        if not cargo_toml.is_file() or cargo_toml.is_symlink():
            continue
        relative = cargo_toml.relative_to(workspace)
        if any(part in SKIP_PARTS for part in relative.parts):
            continue
        manifests.append(cargo_toml)

    for cargo_toml in manifests:
        relative = cargo_toml.relative_to(workspace).as_posix()
        try:
            import tomllib

            cargo = tomllib.loads(cargo_toml.read_text(encoding="utf-8"))
        except Exception as error:
            findings.append({"path": relative, "kind": "toml_error", "reason": str(error)})
            continue
        for table_path, dependencies in iter_dependency_tables(cargo):
            for name in dependencies:
                normalized = str(name).lower().replace("_", "-")
                if normalized not in allowed:
                    findings.append(
                        {
                            "path": relative,
                            "kind": "dependency",
                            "table": ".".join(table_path),
                            "value": name,
                            "reason": "dependency is outside the frozen candidate policy",
                        }
                    )


def imported_roots(tree: ast.AST) -> set[str]:
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".", 1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            roots.add(node.module.split(".", 1)[0])
    return roots


def audit_python(workspace: Path, files: list[Path], policy: dict[str, Any], findings: list[dict[str, Any]]) -> None:
    allow_stdlib = bool(policy.get("python_stdlib_only", False))
    allowed = {str(item).split(".", 1)[0] for item in policy.get("allowed_python_modules", [])}
    stdlib = set(getattr(sys, "stdlib_module_names", set()))
    local_modules = {path.stem for path in files}
    local_modules |= {path.parent.name for path in files if (path.parent / "__init__.py").is_file()}
    for path in files:
        relative = path.relative_to(workspace).as_posix()
        try:
            tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"), filename=relative)
        except SyntaxError as error:
            findings.append({"path": relative, "line": error.lineno, "kind": "python_syntax", "reason": str(error)})
            continue
        for module in imported_roots(tree):
            if module in PROHIBITED_PYTHON_MODULES:
                findings.append(
                    {
                        "path": relative,
                        "kind": "python_import",
                        "value": module,
                        "reason": "subprocess, network, or dynamic-loading module is prohibited",
                    }
                )
            elif allow_stdlib and module not in stdlib and module not in local_modules and module not in allowed:
                findings.append(
                    {
                        "path": relative,
                        "kind": "python_import",
                        "value": module,
                        "reason": "non-standard-library import is outside the frozen candidate policy",
                    }
                )


def audit_symlinks(workspace: Path, findings: list[dict[str, Any]]) -> None:
    for path in sorted(workspace.rglob("*")):
        relative = path.relative_to(workspace)
        if any(part in SKIP_PARTS for part in relative.parts):
            continue
        if path.is_symlink():
            findings.append(
                {
                    "path": relative.as_posix(),
                    "kind": "symlink",
                    "reason": "symlinks are prohibited in candidate source and manifests",
                }
            )


def source_audit(workspace: Path, adapter: dict[str, Any]) -> dict[str, Any]:
    findings: list[dict[str, Any]] = []
    policy = adapter.get("audit", {})
    if not isinstance(policy, dict):
        policy = {}
    extensions = {str(item) for item in adapter.get("source_extensions", [])}
    roots = policy.get("roots") if isinstance(policy.get("roots"), list) else None
    files = list(iter_source_files(workspace, extensions, roots))
    audit_symlinks(workspace, findings)
    audit_cargo(workspace, policy, findings)
    if ".py" in extensions:
        audit_python(workspace, [path for path in files if path.suffix == ".py"], policy, findings)

    patterns = list(DEFAULT_SOURCE_PATTERNS)
    for row in policy.get("prohibited_patterns", []):
        if isinstance(row, dict) and isinstance(row.get("pattern"), str):
            patterns.append((re.compile(row["pattern"], re.I), str(row.get("reason", "prohibited source pattern"))))
    for path in files:
        relative = path.relative_to(workspace).as_posix()
        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError as error:
            findings.append({"path": relative, "kind": "read_error", "reason": str(error)})
            continue
        for line_number, line in enumerate(lines, 1):
            for pattern, reason in patterns:
                if pattern.search(line):
                    findings.append(
                        {
                            "path": relative,
                            "line": line_number,
                            "kind": "source_pattern",
                            "reason": reason,
                            "excerpt": truncate(line.strip(), 300),
                        }
                    )
    blocking = [
        finding for finding in findings if finding.get("reason") not in ADVISORY_AUDIT_REASONS
    ]
    return {
        "passed": not findings,
        "blocking": bool(blocking),
        "findings": findings,
        "blocking_findings": blocking,
        "advisory_findings": [finding for finding in findings if finding not in blocking],
        "source_files_scanned": len(files),
        "source_extensions": sorted(extensions),
    }


def resolve_candidate_artifact(workspace: Path, logical: Path) -> Path:
    if logical.is_symlink():
        raise ValueError("Candidate artifact must not be a symlink")
    artifact = logical.resolve()
    try:
        artifact.relative_to(workspace)
    except ValueError as error:
        raise ValueError("Candidate artifact must resolve inside the workspace") from error
    if artifact.exists() and not artifact.is_file():
        raise ValueError("Candidate artifact must be a regular file")
    return artifact


def build_candidate(workspace: Path, adapter: dict[str, Any], timeout: int) -> tuple[CommandResult, Path]:
    build = adapter["build"]
    logical_artifact = workspace / str(build["artifact"])
    artifact = resolve_candidate_artifact(workspace, logical_artifact)
    variables = {"workspace": str(workspace), "artifact": str(artifact)}
    command = render_command(build["command"], variables)
    env = {
        "CARGO_NET_OFFLINE": "true",
        "RUST_BACKTRACE": "1",
        "PYTHONDONTWRITEBYTECODE": "1",
        "PIP_NO_INDEX": "1",
        "PIP_DISABLE_PIP_VERSION_CHECK": "1",
    }
    if command:
        result = run_command(command, cwd=workspace, timeout=int(build.get("timeout_seconds", timeout)), env=env)
    else:
        result = CommandResult([], 0, "", "", 0.0, False)
    try:
        verified_artifact = resolve_candidate_artifact(workspace, logical_artifact)
    except ValueError as error:
        detail = f"candidate artifact policy failure: {error}"
        result = CommandResult(
            result.args,
            result.returncode if result.returncode != 0 else 1,
            result.stdout,
            (result.stderr + "\n" + detail).strip(),
            result.elapsed_seconds,
            result.timed_out,
        )
        return result, logical_artifact
    return result, verified_artifact


def candidate_compile(
    workspace: Path,
    adapter: dict[str, Any],
    artifact: Path,
    source: Path,
    assembly: Path,
    timeout: int,
) -> CommandResult:
    variables = {
        "workspace": str(workspace),
        "artifact": str(artifact),
        "input": str(source),
        "output": str(assembly),
    }
    command = render_command(adapter["run"]["command"], variables)
    env = {"CARGO_NET_OFFLINE": "true", "PYTHONDONTWRITEBYTECODE": "1", "PIP_NO_INDEX": "1"}
    return run_command(command, cwd=workspace, timeout=timeout, env=env)


def cache_key(test: dict[str, Any]) -> str:
    payload = f"v2\0{test['sha256']}\0gcc-c17-pedantic-O0-no-pie"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def reference_result(
    source: Path,
    test: dict[str, Any],
    cache_dir: Path,
    compile_timeout: int,
    run_timeout: int,
) -> dict[str, Any]:
    key = cache_key(test)
    cache_path = cache_dir / f"{key}.json"
    if cache_path.exists():
        with contextlib.suppress(OSError, json.JSONDecodeError):
            value = json.loads(cache_path.read_text(encoding="utf-8"))
            if isinstance(value, dict) and value.get("ok") is True:
                return value

    cache_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="picc-reference-") as temporary:
        temp = Path(temporary)
        copied = temp / "input.c"
        executable = temp / "reference"
        shutil.copy2(source, copied)
        compile_result = run_command(
            [
                "/usr/bin/gcc",
                "-std=c17",
                "-pedantic-errors",
                "-O0",
                "-fno-pie",
                "-no-pie",
                "-D",
                "SUPPRESS_WARNINGS",
                str(copied),
                "-o",
                str(executable),
            ],
            cwd=temp,
            timeout=compile_timeout,
        )
        if compile_result.returncode != 0 or compile_result.timed_out:
            value = {
                "ok": False,
                "failure_type": "reference_compile_failure",
                "compile": asdict(compile_result),
            }
        else:
            execution = run_command([str(executable)], cwd=temp, timeout=run_timeout)
            value = {
                "ok": not execution.timed_out,
                "failure_type": "reference_timeout" if execution.timed_out else None,
                "returncode": execution.returncode,
                "stdout": execution.stdout,
                "stderr": execution.stderr,
                "compile_seconds": compile_result.elapsed_seconds,
                "execute_seconds": execution.elapsed_seconds,
            }
    if value.get("ok") is True:
        atomic_json(cache_path, value)
    return value


def oracle_result(source: Path, compile_timeout: int, run_timeout: int) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="picc-oracle-") as temporary:
        temp = Path(temporary)
        copied = temp / "query.c"
        executable = temp / "query"
        shutil.copy2(source, copied)
        compile_result = run_command(
            [
                "/usr/bin/gcc",
                "-std=c17",
                "-pedantic-errors",
                "-O0",
                "-fno-pie",
                "-no-pie",
                str(copied),
                "-o",
                str(executable),
            ],
            cwd=temp,
            timeout=compile_timeout,
        )
        if compile_result.timed_out:
            return {"ok": False, "accepted": False, "failure_type": "reference_compile_timeout"}
        if compile_result.returncode != 0:
            return {
                "ok": True,
                "accepted": False,
                "compile_returncode": compile_result.returncode,
                "diagnostic": truncate(compile_result.stderr, 2000),
            }
        execution = run_command([str(executable)], cwd=temp, timeout=run_timeout)
        if execution.timed_out:
            return {"ok": False, "accepted": True, "failure_type": "reference_execution_timeout"}
        return {
            "ok": True,
            "accepted": True,
            "returncode": execution.returncode,
            "stdout": execution.stdout,
            "stderr": execution.stderr,
        }


def evaluate_valid(
    workspace: Path,
    adapter: dict[str, Any],
    artifact: Path,
    source: Path,
    test: dict[str, Any],
    cache_dir: Path,
    compile_timeout: int,
    run_timeout: int,
) -> TestResult:
    expected = reference_result(source, test, cache_dir, compile_timeout, run_timeout)
    if not expected.get("ok"):
        return TestResult(
            str(test["id"]),
            int(test["stage"]),
            "valid",
            False,
            str(expected.get("failure_type", "reference_failure")),
            truncate(json.dumps(expected, sort_keys=True), 2000),
            0.0,
            0.0,
            None,
        )

    with tempfile.TemporaryDirectory(prefix="picc-test-") as temporary:
        temp = Path(temporary)
        copied = temp / "input.c"
        assembly = temp / "output.s"
        executable = temp / "candidate"
        shutil.copy2(source, copied)
        compile_result = candidate_compile(workspace, adapter, artifact, copied, assembly, compile_timeout)
        if compile_result.timed_out:
            return TestResult(str(test["id"]), int(test["stage"]), "valid", False, "compiler_timeout", None, compile_result.elapsed_seconds, 0.0, compile_result.returncode)
        if compile_result.returncode < 0:
            return TestResult(str(test["id"]), int(test["stage"]), "valid", False, "compiler_crash", truncate(compile_result.stderr, 1000), compile_result.elapsed_seconds, 0.0, compile_result.returncode)
        if compile_result.returncode != 0:
            return TestResult(str(test["id"]), int(test["stage"]), "valid", False, "unexpected_reject", truncate(compile_result.stderr, 1000), compile_result.elapsed_seconds, 0.0, compile_result.returncode)
        if not assembly.exists() or assembly.stat().st_size == 0:
            return TestResult(str(test["id"]), int(test["stage"]), "valid", False, "missing_assembly", None, compile_result.elapsed_seconds, 0.0, compile_result.returncode)

        link_result = run_command(
            ["/usr/bin/gcc", "-x", "assembler", "-fno-pie", "-no-pie", str(assembly), "-o", str(executable)],
            cwd=temp,
            timeout=compile_timeout,
        )
        if link_result.timed_out:
            return TestResult(str(test["id"]), int(test["stage"]), "valid", False, "link_timeout", None, compile_result.elapsed_seconds + link_result.elapsed_seconds, 0.0, compile_result.returncode)
        if link_result.returncode != 0:
            return TestResult(str(test["id"]), int(test["stage"]), "valid", False, "assembly_or_link_failure", truncate(link_result.stderr, 1500), compile_result.elapsed_seconds + link_result.elapsed_seconds, 0.0, compile_result.returncode)

        execution = run_command([str(executable)], cwd=temp, timeout=run_timeout)
        if execution.timed_out:
            return TestResult(str(test["id"]), int(test["stage"]), "valid", False, "execution_timeout", None, compile_result.elapsed_seconds + link_result.elapsed_seconds, execution.elapsed_seconds, compile_result.returncode)
        differences: list[str] = []
        if execution.returncode != expected["returncode"]:
            differences.append(f"return code expected {expected['returncode']} got {execution.returncode}")
        if execution.stdout != expected["stdout"]:
            differences.append(f"stdout expected {expected['stdout']!r} got {execution.stdout!r}")
        if execution.stderr != expected["stderr"]:
            differences.append(f"stderr expected {expected['stderr']!r} got {execution.stderr!r}")
        if differences:
            return TestResult(
                str(test["id"]),
                int(test["stage"]),
                "valid",
                False,
                "wrong_behavior",
                truncate("; ".join(differences), 1500),
                compile_result.elapsed_seconds + link_result.elapsed_seconds,
                execution.elapsed_seconds,
                compile_result.returncode,
            )
        return TestResult(
            str(test["id"]),
            int(test["stage"]),
            "valid",
            True,
            None,
            None,
            compile_result.elapsed_seconds + link_result.elapsed_seconds,
            execution.elapsed_seconds,
            compile_result.returncode,
        )


def evaluate_invalid(
    workspace: Path,
    adapter: dict[str, Any],
    artifact: Path,
    source: Path,
    test: dict[str, Any],
    compile_timeout: int,
) -> TestResult:
    with tempfile.TemporaryDirectory(prefix="picc-invalid-") as temporary:
        temp = Path(temporary)
        copied = temp / "input.c"
        assembly = temp / "output.s"
        shutil.copy2(source, copied)
        result = candidate_compile(workspace, adapter, artifact, copied, assembly, compile_timeout)
        has_output = assembly.exists() and assembly.stat().st_size > 0
        if result.timed_out:
            passed, failure = False, "compiler_timeout"
        elif result.returncode < 0:
            passed, failure = False, "compiler_crash"
        elif result.returncode == 0:
            passed, failure = False, "unexpected_accept"
        elif has_output:
            passed, failure = False, "invalid_output_created"
        else:
            passed, failure = True, None
        return TestResult(
            str(test["id"]),
            int(test["stage"]),
            "invalid",
            passed,
            failure,
            None if passed else truncate(result.stderr, 1000),
            result.elapsed_seconds,
            0.0,
            result.returncode,
        )


def select_tests(manifest: dict[str, Any], max_stage: int, latest_only: bool, test_id: str | None) -> list[dict[str, Any]]:
    tests = [row for row in manifest.get("tests", []) if int(row["stage"]) <= max_stage]
    if latest_only:
        tests = [row for row in tests if int(row["stage"]) == max_stage]
    if test_id:
        exact = [row for row in tests if row["id"] == test_id]
        if not exact:
            exact = [row for row in tests if test_id in row["id"]]
        if len(exact) != 1:
            raise ValueError(f"--test-id matched {len(exact)} tests; use one exact manifest ID")
        tests = exact
    return sorted(tests, key=lambda row: (int(row["stage"]), str(row["validity"]), str(row["id"])))


def summarize(results: list[TestResult], build_ok: bool, audit: dict[str, Any]) -> dict[str, Any]:
    by_stage: dict[int, list[TestResult]] = defaultdict(list)
    for result in results:
        by_stage[result.stage].append(result)
    stages: dict[str, Any] = {}
    stage_scores: list[float] = []
    for stage, rows in sorted(by_stage.items()):
        validity_scores: dict[str, float] = {}
        validity_counts: dict[str, Any] = {}
        for validity in ("valid", "invalid"):
            subset = [row for row in rows if row.validity == validity]
            if subset:
                passed = sum(row.passed for row in subset)
                score = passed / len(subset)
                validity_scores[validity] = score
                validity_counts[validity] = {"passed": passed, "total": len(subset), "score": score}
        stage_score = sum(validity_scores.values()) / len(validity_scores) if validity_scores else 0.0
        stage_scores.append(stage_score)
        stages[str(stage)] = {
            "score": stage_score,
            "passed": sum(row.passed for row in rows),
            "total": len(rows),
            **validity_counts,
        }
    passed = sum(row.passed for row in results)
    failures = [
        {
            "id": row.id,
            "stage": row.stage,
            "validity": row.validity,
            "failure_type": row.failure_type,
            "detail": row.detail,
        }
        for row in results
        if not row.passed
    ]
    return {
        "score": sum(stage_scores) / len(stage_scores) if stage_scores else 0.0,
        "micro_score": passed / len(results) if results else 0.0,
        "passed": passed,
        "failed": len(results) - passed,
        "total": len(results),
        "build_ok": build_ok,
        "audit_ok": bool(audit.get("passed")),
        "audit_blocking": bool(audit.get("blocking")),
        "stages": stages,
        "failures": failures[:12],
    }


def main() -> int:
    args = parse_args()
    started = time.time()
    workspace = args.workspace.resolve()
    adapter = load_object(args.candidate_config.resolve())
    if adapter.get("schema_version") != 1:
        raise ValueError("Unsupported candidate adapter schema")

    if args.oracle_source is not None:
        oracle = oracle_result(args.oracle_source.resolve(), args.compile_timeout, args.run_timeout)
        output = {
            "schema_version": 1,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "elapsed_seconds": time.time() - started,
            "oracle": oracle,
        }
        atomic_json(args.output, output)
        print(json.dumps(oracle, sort_keys=True) if args.summary_json else json.dumps(output, indent=2, sort_keys=True))
        return 0

    tests_root = args.tests_root.resolve(strict=True)
    manifest = load_object(args.manifest.resolve())
    selected = select_tests(manifest, args.max_stage, args.latest_only, args.test_id)
    if not selected:
        raise ValueError("No tests selected")
    test_sources = [resolve_test_source(tests_root, test) for test in selected]

    audit = source_audit(workspace, adapter)
    build_result: CommandResult | None = None
    artifact = workspace / str(adapter["build"]["artifact"])
    build_ok = False
    results: list[TestResult] = []
    if not audit["blocking"]:
        build_result, artifact = build_candidate(workspace, adapter, args.build_timeout)
        build_ok = (
            not build_result.timed_out
            and build_result.returncode == 0
            and artifact.is_file()
            and artifact.stat().st_size > 0
        )

    if build_ok:
        for test, source in zip(selected, test_sources, strict=True):
            if test["validity"] == "valid":
                result = evaluate_valid(
                    workspace,
                    adapter,
                    artifact,
                    source,
                    test,
                    args.cache_dir,
                    args.compile_timeout,
                    args.run_timeout,
                )
            else:
                result = evaluate_invalid(workspace, adapter, artifact, source, test, args.compile_timeout)
            results.append(result)
    else:
        failure_type = "source_audit_failure" if audit["blocking"] else "build_failure"
        detail = (
            truncate(json.dumps(audit["blocking_findings"][:10], sort_keys=True), 2000)
            if audit["blocking"]
            else truncate(build_result.stderr if build_result else "candidate artifact or build command missing", 2000)
        )
        results = [
            TestResult(
                str(test["id"]),
                int(test["stage"]),
                str(test["validity"]),
                False,
                failure_type,
                detail,
                0.0,
                0.0,
                None,
            )
            for test in selected
        ]

    summary = summarize(results, build_ok, audit)
    output = {
        "schema_version": 1,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "elapsed_seconds": time.time() - started,
        "workspace": str(workspace),
        "partition": manifest.get("partition"),
        "source_revision": manifest.get("source", {}).get("revision"),
        "candidate": {
            "language": adapter.get("language"),
            "framework": adapter.get("framework"),
            "adapter_sha256": hashlib.sha256(args.candidate_config.read_bytes()).hexdigest(),
            "artifact": str(artifact),
        },
        "selection": {
            "max_stage": args.max_stage,
            "latest_only": args.latest_only,
            "test_id": args.test_id,
            "count": len(selected),
        },
        "source_audit": audit,
        "build": asdict(build_result) if build_result else None,
        "summary": summary,
        "tests": [asdict(result) for result in results],
    }
    atomic_json(args.output, output)
    print(json.dumps(summary, sort_keys=True) if args.summary_json else json.dumps(output, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        failure = {
            "schema_version": 1,
            "error": f"{type(error).__name__}: {error}",
            "traceback": traceback.format_exc(),
        }
        with contextlib.suppress(Exception):
            parsed = parse_args()
            atomic_json(parsed.output, failure)
        print(json.dumps(failure, sort_keys=True))
        raise SystemExit(2)
