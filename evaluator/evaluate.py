#!/usr/bin/env python3
"""Controlled behavioral evaluator for the PiCC experiment.

The agent calls this only through the project-local Pi extension. It builds PiCC,
uses GCC as an evaluator-side oracle for valid programs, and checks that invalid
programs are rejected without an output assembly file.
"""

from __future__ import annotations

import argparse
import base64
import contextlib
import hashlib
import json
import os
import re
import shutil
import signal
import subprocess
import tempfile
import time
import traceback
from collections import defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable, Sequence

MAX_CAPTURE_BYTES = 1024 * 1024
PROHIBITED_DEPENDENCY_TERMS = {
    "cc",
    "clang",
    "clang-sys",
    "gcc",
    "gccjit",
    "inkwell",
    "libloading",
    "llvm-sys",
    "tcc",
}
SOURCE_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\b(?:std::)?process::Command\b|\bCommand::new\s*\("), "subprocess invocation"),
    (re.compile(r"\b(?:libclang|libgccjit|libtcc|LLVM|llvm_sys|clang_sys)\b", re.I), "compiler library reference"),
    (re.compile(r"\b(?:TcpStream|UdpSocket)\b|https?://", re.I), "network access"),
]


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
    parser.add_argument("--tests-root", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--max-stage", type=int, default=10)
    parser.add_argument("--latest-only", action="store_true")
    parser.add_argument("--test-id")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--summary-json", action="store_true")
    parser.add_argument("--cache-dir", type=Path, default=Path("/run-artifacts/reference-cache"))
    parser.add_argument("--build-timeout", type=int, default=900)
    parser.add_argument("--compile-timeout", type=int, default=30)
    parser.add_argument("--run-timeout", type=int, default=10)
    return parser.parse_args()


def truncate(value: str, limit: int = 8000) -> str:
    if len(value) <= limit:
        return value
    return value[:limit] + f"\n... [truncated {len(value) - limit} characters]"


def run_command(
    args: Sequence[str],
    *,
    cwd: Path,
    timeout: int,
    env: dict[str, str] | None = None,
) -> CommandResult:
    started = time.monotonic()
    process = subprocess.Popen(
        list(args),
        cwd=cwd,
        env=env,
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


def iter_dependency_tables(value: Any, path: tuple[str, ...] = ()) -> Iterable[tuple[tuple[str, ...], dict[str, Any]]]:
    if not isinstance(value, dict):
        return
    for key, child in value.items():
        child_path = (*path, str(key))
        if str(key) in {"dependencies", "dev-dependencies", "build-dependencies"} and isinstance(child, dict):
            yield child_path, child
        if isinstance(child, dict):
            yield from iter_dependency_tables(child, child_path)


def source_audit(workspace: Path) -> dict[str, Any]:
    findings: list[dict[str, Any]] = []
    cargo_toml = workspace / "Cargo.toml"
    if cargo_toml.exists():
        try:
            import tomllib

            cargo = tomllib.loads(cargo_toml.read_text(encoding="utf-8"))
            for table_path, dependencies in iter_dependency_tables(cargo):
                for name in dependencies:
                    normalized = name.lower().replace("_", "-")
                    reason = "external dependency is outside the frozen std-only task"
                    if normalized in PROHIBITED_DEPENDENCY_TERMS:
                        reason = "prohibited compiler/delegation dependency"
                    findings.append(
                        {
                            "path": "Cargo.toml",
                            "line": None,
                            "kind": "dependency",
                            "value": name,
                            "table": ".".join(table_path),
                            "reason": reason,
                        }
                    )
        except Exception as error:  # malformed TOML will be reported by Cargo too
            findings.append(
                {
                    "path": "Cargo.toml",
                    "line": None,
                    "kind": "toml_error",
                    "reason": str(error),
                }
            )

    for path in sorted(workspace.rglob("*.rs")):
        if "target" in path.parts or ".git" in path.parts:
            continue
        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError as error:
            findings.append({"path": str(path), "kind": "read_error", "reason": str(error)})
            continue
        relative = path.relative_to(workspace).as_posix()
        for line_number, line in enumerate(lines, start=1):
            for pattern, reason in SOURCE_PATTERNS:
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
    return {"passed": not findings, "findings": findings}


def build_compiler(workspace: Path, timeout: int) -> tuple[CommandResult, Path]:
    cargo = shutil.which("cargo") or "cargo"
    args = [cargo, "build", "--release", "--offline"]
    if (workspace / "Cargo.lock").exists():
        args.append("--locked")
    env = dict(os.environ)
    env.update({"CARGO_NET_OFFLINE": "true", "RUST_BACKTRACE": "1"})
    result = run_command(args, cwd=workspace, timeout=timeout, env=env)
    return result, workspace / "target" / "release" / "picc"


def cache_key(test: dict[str, Any]) -> str:
    payload = f"v1\0{test['sha256']}\0gcc-c17-pedantic-O0-no-pie"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def encode_text(value: str) -> dict[str, str]:
    return {
        "text": value,
        "base64": base64.b64encode(value.encode("utf-8", errors="replace")).decode("ascii"),
    }


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
        try:
            return json.loads(cache_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            pass

    cache_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="picc-reference-") as temporary:
        temp = Path(temporary)
        copied = temp / "input.c"
        shutil.copy2(source, copied)
        executable = temp / "reference"
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
    atomic_json(cache_path, value)
    return value


def evaluate_valid(
    compiler: Path,
    source: Path,
    test: dict[str, Any],
    cache_dir: Path,
    compile_timeout: int,
    run_timeout: int,
) -> TestResult:
    expected = reference_result(source, test, cache_dir, compile_timeout, run_timeout)
    if not expected.get("ok"):
        return TestResult(
            id=test["id"],
            stage=int(test["stage"]),
            validity="valid",
            passed=False,
            failure_type=str(expected.get("failure_type", "reference_failure")),
            detail=truncate(json.dumps(expected, sort_keys=True), 2000),
            compile_seconds=0.0,
            execute_seconds=0.0,
            compiler_returncode=None,
        )

    with tempfile.TemporaryDirectory(prefix="picc-test-") as temporary:
        temp = Path(temporary)
        copied = temp / "input.c"
        assembly = temp / "output.s"
        executable = temp / "candidate"
        shutil.copy2(source, copied)

        compile_result = run_command(
            [str(compiler), str(copied), "-o", str(assembly)],
            cwd=temp,
            timeout=compile_timeout,
        )
        if compile_result.timed_out:
            return TestResult(test["id"], int(test["stage"]), "valid", False, "compiler_timeout", None, compile_result.elapsed_seconds, 0.0, compile_result.returncode)
        if compile_result.returncode < 0:
            return TestResult(test["id"], int(test["stage"]), "valid", False, "compiler_crash", truncate(compile_result.stderr, 1000), compile_result.elapsed_seconds, 0.0, compile_result.returncode)
        if compile_result.returncode != 0:
            return TestResult(test["id"], int(test["stage"]), "valid", False, "unexpected_reject", truncate(compile_result.stderr, 1000), compile_result.elapsed_seconds, 0.0, compile_result.returncode)
        if not assembly.exists() or assembly.stat().st_size == 0:
            return TestResult(test["id"], int(test["stage"]), "valid", False, "missing_assembly", None, compile_result.elapsed_seconds, 0.0, compile_result.returncode)

        link_result = run_command(
            ["/usr/bin/gcc", "-x", "assembler", "-fno-pie", "-no-pie", str(assembly), "-o", str(executable)],
            cwd=temp,
            timeout=compile_timeout,
        )
        if link_result.timed_out:
            return TestResult(test["id"], int(test["stage"]), "valid", False, "link_timeout", None, compile_result.elapsed_seconds + link_result.elapsed_seconds, 0.0, compile_result.returncode)
        if link_result.returncode != 0:
            return TestResult(test["id"], int(test["stage"]), "valid", False, "assembly_or_link_failure", truncate(link_result.stderr, 1500), compile_result.elapsed_seconds + link_result.elapsed_seconds, 0.0, compile_result.returncode)

        execution = run_command([str(executable)], cwd=temp, timeout=run_timeout)
        if execution.timed_out:
            return TestResult(test["id"], int(test["stage"]), "valid", False, "execution_timeout", None, compile_result.elapsed_seconds + link_result.elapsed_seconds, execution.elapsed_seconds, compile_result.returncode)
        differences: list[str] = []
        if execution.returncode != expected["returncode"]:
            differences.append(f"return code expected {expected['returncode']} got {execution.returncode}")
        if execution.stdout != expected["stdout"]:
            differences.append(f"stdout expected {expected['stdout']!r} got {execution.stdout!r}")
        if execution.stderr != expected["stderr"]:
            differences.append(f"stderr expected {expected['stderr']!r} got {execution.stderr!r}")
        if differences:
            return TestResult(
                test["id"],
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
            test["id"],
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
    compiler: Path,
    source: Path,
    test: dict[str, Any],
    compile_timeout: int,
) -> TestResult:
    with tempfile.TemporaryDirectory(prefix="picc-invalid-") as temporary:
        temp = Path(temporary)
        copied = temp / "input.c"
        assembly = temp / "output.s"
        shutil.copy2(source, copied)
        result = run_command(
            [str(compiler), str(copied), "-o", str(assembly)],
            cwd=temp,
            timeout=compile_timeout,
        )
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
            id=test["id"],
            stage=int(test["stage"]),
            validity="invalid",
            passed=passed,
            failure_type=failure,
            detail=None if passed else truncate(result.stderr, 1000),
            compile_seconds=result.elapsed_seconds,
            execute_seconds=0.0,
            compiler_returncode=result.returncode,
        )


def select_tests(manifest: dict[str, Any], max_stage: int, latest_only: bool, test_id: str | None) -> list[dict[str, Any]]:
    tests = [test for test in manifest.get("tests", []) if int(test["stage"]) <= max_stage]
    if latest_only:
        tests = [test for test in tests if int(test["stage"]) == max_stage]
    if test_id:
        exact = [test for test in tests if test["id"] == test_id]
        if not exact:
            exact = [test for test in tests if test_id in test["id"]]
        if len(exact) != 1:
            raise ValueError(f"--test-id matched {len(exact)} tests; use one exact manifest ID")
        tests = exact
    return sorted(tests, key=lambda test: (int(test["stage"]), test["validity"], test["id"]))


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
                validity_scores[validity] = passed / len(subset)
                validity_counts[validity] = {"passed": passed, "total": len(subset), "score": passed / len(subset)}
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
        {"id": row.id, "stage": row.stage, "validity": row.validity, "failure_type": row.failure_type, "detail": row.detail}
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
        "stages": stages,
        "failures": failures[:12],
    }


def main() -> int:
    args = parse_args()
    started = time.time()
    workspace = args.workspace.resolve()
    tests_root = args.tests_root.resolve()
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    selected = select_tests(manifest, args.max_stage, args.latest_only, args.test_id)
    if not selected:
        raise ValueError("No tests selected")

    audit = source_audit(workspace)
    build_result: CommandResult | None = None
    compiler = workspace / "target" / "release" / "picc"
    build_ok = False
    results: list[TestResult] = []

    if audit["passed"]:
        build_result, compiler = build_compiler(workspace, args.build_timeout)
        build_ok = (
            not build_result.timed_out
            and build_result.returncode == 0
            and compiler.is_file()
            and os.access(compiler, os.X_OK)
        )

    if build_ok:
        for test in selected:
            source = tests_root / test["relative_path"]
            if test["validity"] == "valid":
                result = evaluate_valid(
                    compiler,
                    source,
                    test,
                    args.cache_dir,
                    args.compile_timeout,
                    args.run_timeout,
                )
            else:
                result = evaluate_invalid(compiler, source, test, args.compile_timeout)
            results.append(result)
    else:
        failure_type = "source_audit_failure" if not audit["passed"] else "build_failure"
        detail = (
            truncate(json.dumps(audit["findings"][:10], sort_keys=True), 2000)
            if not audit["passed"]
            else truncate((build_result.stderr if build_result else "Cargo.toml or compiler missing"), 2000)
        )
        results = [
            TestResult(
                id=test["id"],
                stage=int(test["stage"]),
                validity=test["validity"],
                passed=False,
                failure_type=failure_type,
                detail=detail,
                compile_seconds=0.0,
                execute_seconds=0.0,
                compiler_returncode=None,
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
    if args.summary_json:
        print(json.dumps(summary, sort_keys=True))
    else:
        print(json.dumps(output, indent=2, sort_keys=True))
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
