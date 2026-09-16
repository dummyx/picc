#!/usr/bin/env python3
"""Language-neutral behavioral evaluator for PiCC study conditions.

The product contract is held constant across implementation languages:

    <candidate command> INPUT.c -o OUTPUT.s

Candidate build/run commands and source-audit policy are declared in the frozen
``candidate.json`` adapter.  GCC exists only on the evaluator side: it
establishes expected behavior and assembles/links emitted assembly.

Process control, the build step, and the source audit live in
``candidate_runtime.py`` alongside this file and are shared with the other task
evaluators.  A manifest row may name ``fixtures`` (partner translation units,
assembly helpers, headers) and ``link_flags``; they are compiled or assembled
on the evaluator side only, never handed to the candidate (chapters 11-18
task).  Rows without fixtures are evaluated exactly as before.
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import traceback
from collections import defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
from candidate_runtime import (  # noqa: E402
    ADVISORY_AUDIT_REASONS,
    BINARY_ARTIFACT_EXTENSIONS,
    DEFAULT_SOURCE_PATTERNS,
    MAX_CAPTURE_BYTES,
    NODE_BUILTIN_MODULES,
    NODE_SOURCE_EXTENSIONS,
    PROHIBITED_NODE_MODULES,
    PROHIBITED_PYTHON_MODULES,
    SKIP_PARTS,
    SUBPROCESS_ENV_ALLOWLIST,
    CommandResult,
    atomic_json,
    audit_binary_artifacts,
    audit_cargo,
    audit_node,
    audit_python,
    audit_symlinks,
    build_candidate,
    built_cargo_manifests,
    built_package_manifests,
    excluded_prefixes,
    is_excluded,
    iter_source_files,
    load_object,
    node_import_closure,
    node_import_specifiers,
    node_module_root,
    render_command,
    resolve_candidate_artifact,
    resolve_test_source,
    run_command,
    rust_include_closure,
    select_tests,
    source_audit,
    strip_js_comments,
    subprocess_environment,
    truncate,
)

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


# The candidate is handed the test the way the upstream test suite's driver
# hands it to a student compiler: after the C preprocessor. `-P` drops line
# markers, `-C` keeps the test's own comments (the lexical subset includes
# them), `-nostdinc` keeps GCC's pre-included system header out of the output.
# The reference compile below still uses the original file. A test that fails
# to preprocess falls back to its raw text and is recorded in `input_policy`.
PREPROCESS_COMMAND = ["/usr/bin/gcc", "-E", "-P", "-C", "-nostdinc", "-x", "c"]
PREPROCESS_FALLBACKS: list[str] = []


def candidate_input(source: Path, temp: Path, timeout: int) -> Path:
    """Write the candidate's input for `source` into `temp` and return its path."""
    copied = temp / "input.c"
    result = run_command(PREPROCESS_COMMAND + [str(source), "-o", str(copied)], cwd=temp, timeout=timeout)
    if result.returncode == 0 and not result.timed_out and copied.is_file():
        return copied
    PREPROCESS_FALLBACKS.append(f"{source.name}: {truncate(result.stderr.strip(), 200) or 'preprocessor failed'}")
    shutil.copy2(source, copied)
    return copied


def input_policy() -> dict[str, Any]:
    return {
        "preprocess": " ".join(PREPROCESS_COMMAND[1:]),
        "fallback_to_raw_on_failure": True,
        "raw_fallbacks": list(PREPROCESS_FALLBACKS),
    }


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


FIXTURE_KINDS = ("c", "assembly", "header")
LINK_FLAG_PATTERN = re.compile(r"-l[a-z0-9_]+")


def resolve_fixtures(tests_root: Path, test: Mapping[str, Any]) -> list[tuple[str, Path]]:
    """Evaluator-side companions of a test: partner translation units compiled by
    GCC, assembly helpers, and headers the test includes (chapters 11-18)."""
    fixtures: list[tuple[str, Path]] = []
    for index, row in enumerate(test.get("fixtures") or []):
        if not isinstance(row, dict) or row.get("kind") not in FIXTURE_KINDS:
            raise ValueError(f"Test {test.get('id')}: fixture {index} must declare kind in {FIXTURE_KINDS}")
        fixtures.append((str(row["kind"]), resolve_test_source(tests_root, row)))
    return fixtures


def link_flags_of(test: Mapping[str, Any]) -> list[str]:
    flags = test.get("link_flags") or []
    if not isinstance(flags, list) or not all(isinstance(f, str) and LINK_FLAG_PATTERN.fullmatch(f) for f in flags):
        raise ValueError(f"Test {test.get('id')}: link_flags must be -l<library> strings")
    return list(flags)


def cache_key(source: Path, fixtures: Sequence[tuple[str, Path]] = (), link_flags: Sequence[str] = ()) -> str:
    payload = b"v2\0gcc-c17-pedantic-O0-no-pie\0" + source.read_bytes()
    # Rows without fixtures keep the historical key so earlier caches stay valid.
    for kind, path in fixtures:
        payload += b"\0fixture:" + kind.encode() + b":" + path.name.encode() + b"\0" + path.read_bytes()
    for flag in link_flags:
        payload += b"\0link:" + flag.encode()
    return hashlib.sha256(payload).hexdigest()


def reference_result(
    source: Path,
    cache_dir: Path,
    compile_timeout: int,
    run_timeout: int,
    fixtures: Sequence[tuple[str, Path]] = (),
    link_flags: Sequence[str] = (),
) -> dict[str, Any]:
    key = cache_key(source, fixtures, link_flags)
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
        compiled_inputs = [str(fixture) for kind, fixture in fixtures if kind in ("c", "assembly")]
        if compiled_inputs or any(kind == "header" for kind, _ in fixtures):
            # Multi-file rows compile in place so quoted includes resolve and
            # the partner units join the same link, as upstream's driver does.
            inputs = [str(source), *compiled_inputs]
        else:
            shutil.copy2(source, copied)
            inputs = [str(copied)]
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
                *inputs,
                "-o",
                str(executable),
                *link_flags,
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
    fixtures: Sequence[tuple[str, Path]] = (),
    link_flags: Sequence[str] = (),
) -> TestResult:
    expected = reference_result(source, cache_dir, compile_timeout, run_timeout, fixtures, link_flags)
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
        assembly = temp / "output.s"
        executable = temp / "candidate"
        copied = candidate_input(source, temp, compile_timeout)
        compile_result = candidate_compile(workspace, adapter, artifact, copied, assembly, compile_timeout)
        if compile_result.timed_out:
            return TestResult(str(test["id"]), int(test["stage"]), "valid", False, "compiler_timeout", None, compile_result.elapsed_seconds, 0.0, compile_result.returncode)
        if compile_result.returncode < 0:
            return TestResult(str(test["id"]), int(test["stage"]), "valid", False, "compiler_crash", truncate(compile_result.stderr, 1000), compile_result.elapsed_seconds, 0.0, compile_result.returncode)
        if compile_result.returncode != 0:
            return TestResult(str(test["id"]), int(test["stage"]), "valid", False, "unexpected_reject", truncate(compile_result.stderr, 1000), compile_result.elapsed_seconds, 0.0, compile_result.returncode)
        if not assembly.exists() or assembly.stat().st_size == 0:
            return TestResult(str(test["id"]), int(test["stage"]), "valid", False, "missing_assembly", None, compile_result.elapsed_seconds, 0.0, compile_result.returncode)

        companions = [str(fixture) for kind, fixture in fixtures if kind in ("c", "assembly")]
        if companions or link_flags:
            # The candidate's assembly is linked with the GCC-compiled partner
            # units and assembly helpers; the candidate never sees them.
            link_command = [
                "/usr/bin/gcc", "-fno-pie", "-no-pie", "-D", "SUPPRESS_WARNINGS",
                str(assembly), *companions, "-o", str(executable), *link_flags,
            ]
        else:
            link_command = ["/usr/bin/gcc", "-x", "assembler", "-fno-pie", "-no-pie", str(assembly), "-o", str(executable)]
        link_result = run_command(link_command, cwd=temp, timeout=compile_timeout)
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
        assembly = temp / "output.s"
        copied = candidate_input(source, temp, compile_timeout)
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
        elif not result.stderr.strip():
            # Rejecting without saying why is not a correct rejection: a
            # compiler that exits nonzero on everything would otherwise score
            # full marks on this class. The diagnostic is the evidence that the
            # program was actually analysed.
            passed, failure = False, "silent_rejection"
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
    test_fixtures = [resolve_fixtures(tests_root, test) for test in selected]
    test_link_flags = [link_flags_of(test) for test in selected]

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
        for test, source, fixtures, flags in zip(selected, test_sources, test_fixtures, test_link_flags, strict=True):
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
                    fixtures,
                    flags,
                )
            else:
                result = evaluate_invalid(workspace, adapter, artifact, source, test, args.compile_timeout)
            results.append(result)
    else:
        failure_type = "source_audit_failure" if audit["blocking"] else "build_failure"
        detail = (
            truncate(json.dumps(audit["blocking_findings"][:10], sort_keys=True), 2000)
            if audit["blocking"]
            else truncate(
                (build_result.stderr or build_result.stdout) if build_result else "candidate artifact or build command missing",
                2000,
            )
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
        "input_policy": input_policy(),
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
