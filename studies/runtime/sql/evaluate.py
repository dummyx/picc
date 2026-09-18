#!/usr/bin/env python3
"""Behavioral evaluator for the PiSQL task (in-memory SQL query engine).

The product contract, held constant across implementation languages:

    <candidate command> INPUT.sql

The candidate reads a script of SQL statements (each terminated by ``;``) and
prints one block per statement to standard output: ``ok <N>`` followed by N
tab-separated rows, or ``error <message>``.  Each test row of the partition is
one complete sqllogictest script; its ``statement`` and ``query`` records are
handed to the candidate in order, with their setup statements, and the
candidate's blocks are compared under the sqllogictest rules
(``sqllogictest.py``).  A script's score is the share of its scored records
the candidate got right; the stage score is the mean over the stage's
scripts; the corpus score is the mean over stages.

The pinned SQLite (Python's ``sqlite3`` module inside the pinned image; the
version is frozen in ``task.json`` next to this file) re-runs every script
first.  Records whose expected result it does not reproduce are reported as
``reference_disagreements`` and never scored, so the candidate is only ever
compared against expectations the pinned reference confirms.

Build, source audit, and process control come from ``candidate_runtime.py``;
the same frozen adapter, audit, and build gate as the compiler task apply.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import sqlite3
import sys
import tempfile
import time
import traceback
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
# Materialized evaluators are flat (candidate_runtime.py beside this file);
# in the repository the shared module lives one directory up.
for candidate_dir in (HERE, HERE.parent):
    if str(candidate_dir) not in sys.path:
        sys.path.append(str(candidate_dir))
import sqllogictest as slt  # noqa: E402
from candidate_runtime import (  # noqa: E402
    CommandResult,
    atomic_json,
    build_candidate,
    load_object,
    render_command,
    resolve_test_source,
    run_command,
    select_tests,
    source_audit,
    truncate,
)

DEFAULT_SCRIPT_TIMEOUT_SECONDS = 120
# The SQL analogue of the compiler evaluator's hang short-circuit: a candidate
# that times out on this many scripts in a row is hanging on every input.
MAX_CONSECUTIVE_SCRIPT_TIMEOUTS = 3
FAILURE_SAMPLE = 8


@dataclass
class ScriptResult:
    id: str
    stage: int
    validity: str
    passed: bool
    score: float
    failure_type: str | None
    detail: str | None
    compile_seconds: float
    execute_seconds: float
    compiler_returncode: int | None
    records: dict[str, int] = field(default_factory=dict)
    failures: list[dict[str, Any]] = field(default_factory=list)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--tests-root", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--candidate-config", type=Path, default=HERE / "candidate.json")
    parser.add_argument("--task-config", type=Path, default=HERE / "task.json")
    parser.add_argument("--max-stage", type=int, default=99)
    parser.add_argument("--latest-only", action="store_true")
    parser.add_argument("--test-id")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--summary-json", action="store_true")
    # Accepted for command-line parity with the compiler evaluator; the
    # per-script timeout comes from task.json.
    parser.add_argument("--cache-dir", type=Path, default=Path("/run-artifacts/reference-cache"))
    parser.add_argument("--build-timeout", type=int, default=900)
    parser.add_argument("--compile-timeout", type=int, default=30)
    parser.add_argument("--run-timeout", type=int, default=10)
    return parser.parse_args()


def load_task(path: Path) -> dict[str, Any]:
    task: dict[str, Any] = {"runtime": "sql-engine", "parameters": {}}
    if path.is_file():
        task = load_object(path)
    parameters = task.get("parameters") or {}
    pinned = parameters.get("sqlite_version")
    if pinned is not None and str(pinned) != sqlite3.sqlite_version:
        raise ValueError(
            f"pinned SQLite {pinned} is not the evaluator's SQLite {sqlite3.sqlite_version}; refusing to score"
        )
    timeout = int(parameters.get("script_timeout_seconds", DEFAULT_SCRIPT_TIMEOUT_SECONDS))
    if timeout <= 0:
        raise ValueError("script_timeout_seconds must be positive")
    task["effective"] = {"sqlite_version": sqlite3.sqlite_version, "script_timeout_seconds": timeout}
    return task


def thresholds_in_force(records: list[slt.Record]) -> dict[int, int]:
    """The hash threshold applying to each executed record (by record index)."""
    threshold = slt.DEFAULT_HASH_THRESHOLD
    result: dict[int, int] = {}
    for index, record in enumerate(records):
        if record.skipped:
            continue
        if record.kind == "hash-threshold":
            threshold = record.threshold
        result[index] = threshold
    return result


def run_script(
    workspace: Path,
    adapter: dict[str, Any],
    artifact: Path,
    script_path: Path,
    test: dict[str, Any],
    timeout: int,
) -> ScriptResult:
    text = script_path.read_text(encoding="utf-8", errors="replace")
    records = slt.parse_script(text)
    reference = slt.verify_with_sqlite(records)
    disagreeing = {row["line"] for row in reference["disagreements"]}
    executed = slt.statements_of(records)
    thresholds = thresholds_in_force(records)
    threshold_by_id = {id(record): thresholds.get(index, slt.DEFAULT_HASH_THRESHOLD) for index, record in enumerate(records)}

    with tempfile.TemporaryDirectory(prefix="pisql-test-") as temporary:
        temp = Path(temporary)
        script_input = temp / "input.sql"
        script_input.write_text(slt.script_input(executed), encoding="utf-8")
        output_path = temp / "output.txt"
        command = render_command(
            adapter["run"]["command"],
            {"workspace": str(workspace), "artifact": str(artifact), "input": str(script_input)},
        )
        env = {"CARGO_NET_OFFLINE": "true", "PYTHONDONTWRITEBYTECODE": "1", "PIP_NO_INDEX": "1"}
        result = run_command(command, cwd=workspace, timeout=timeout, env=env, stdout_path=output_path)
        output_text = output_path.read_bytes().decode("latin-1") if output_path.is_file() else ""

    blocks, malformed = slt.parse_candidate_output(output_text)
    labels = slt.LabelRegistry()
    counted = 0
    passed = 0
    failures: list[dict[str, Any]] = []
    setup_failures = 0
    for index, record in enumerate(executed):
        if record.line in disagreeing:
            continue
        block = blocks[index] if index < len(blocks) else None
        ok, detail = judge(record, block, threshold_by_id[id(record)], labels)
        if record.kind == "statement" and record.expect == "ok":
            # Setup statements are prerequisites, not scored: an engine that
            # answers `ok 0` to everything earns nothing, while a failed
            # CREATE or INSERT still costs every query that depends on it.
            if not ok:
                setup_failures += 1
                if len(failures) < FAILURE_SAMPLE:
                    failures.append({"line": record.line, "kind": "setup", "detail": detail})
            continue
        counted += 1
        if ok:
            passed += 1
        elif len(failures) < FAILURE_SAMPLE:
            failures.append({"line": record.line, "kind": record.kind, "detail": detail})

    score = passed / counted if counted else 0.0
    if result.timed_out:
        failure_type: str | None = "script_timeout"
    elif result.returncode < 0:
        failure_type = "candidate_crash"
    elif malformed and passed < counted:
        failure_type = "malformed_output"
    elif not counted:
        failure_type = "no_scored_records"
    elif passed < counted:
        failure_type = "wrong_results"
    else:
        failure_type = None
    detail_parts = []
    if malformed:
        detail_parts.append(malformed)
    if result.returncode != 0 and not result.timed_out:
        detail_parts.append(f"exit status {result.returncode}")
    if result.stderr.strip():
        detail_parts.append(truncate(result.stderr.strip(), 500))
    if failures:
        detail_parts.append("; ".join(f"line {f['line']}: {f['detail']}" for f in failures[:3]))
    return ScriptResult(
        str(test["id"]),
        int(test["stage"]),
        str(test.get("validity", "valid")),
        failure_type is None,
        score,
        failure_type,
        truncate(" | ".join(detail_parts), 1500) if detail_parts else None,
        0.0,
        result.elapsed_seconds,
        result.returncode,
        {
            "total": counted,
            "passed": passed,
            "failed": counted - passed,
            "executed": len(executed),
            "setup_failures": setup_failures,
            "blocks": len(blocks),
            "reference_disagreements": len(disagreeing),
        },
        failures,
    )


def judge(record: slt.Record, block: slt.Block | None, threshold: int, labels: slt.LabelRegistry) -> tuple[bool, str | None]:
    if block is None:
        return False, "no output block for this statement"
    if record.kind == "statement":
        expected_ok = record.expect == "ok"
        if block.ok == expected_ok:
            return True, None
        return False, (
            f"statement expected to {'succeed' if expected_ok else 'fail'} but candidate reported "
            f"{'ok' if block.ok else 'error ' + block.message[:100]!r}"
        )
    if not block.ok:
        return False, f"query failed: {block.message[:200]!r}"
    columns = len(record.types)
    values: list[str] = []
    for row in block.rows:
        if len(row) != columns:
            return False, f"row has {len(row)} columns, query declares {columns}"
        for cell, type_char in zip(row, record.types, strict=True):
            values.append(slt.render_candidate_token(cell, type_char))
    return slt.compare_query(record, values, threshold, labels)


def summarize(results: list[ScriptResult], build_ok: bool, audit: dict[str, Any]) -> dict[str, Any]:
    by_stage: dict[int, list[ScriptResult]] = defaultdict(list)
    for result in results:
        by_stage[result.stage].append(result)
    stages: dict[str, Any] = {}
    stage_scores: list[float] = []
    for stage, rows in sorted(by_stage.items()):
        stage_score = sum(row.score for row in rows) / len(rows)
        stage_scores.append(stage_score)
        stages[str(stage)] = {
            "score": stage_score,
            "passed": sum(row.passed for row in rows),
            "total": len(rows),
            "valid": {
                "passed": sum(row.passed for row in rows),
                "total": len(rows),
                "score": stage_score,
            },
            "records": {
                "total": sum(row.records.get("total", 0) for row in rows),
                "passed": sum(row.records.get("passed", 0) for row in rows),
            },
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
        "records_total": sum(row.records.get("total", 0) for row in results),
        "records_passed": sum(row.records.get("passed", 0) for row in results),
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
    task = load_task(args.task_config)
    timeout = int(task["effective"]["script_timeout_seconds"])

    tests_root = args.tests_root.resolve(strict=True)
    manifest = load_object(args.manifest.resolve())
    selected = select_tests(manifest, args.max_stage, args.latest_only, args.test_id)
    if not selected:
        raise ValueError("No tests selected")
    scripts = [resolve_test_source(tests_root, test) for test in selected]

    audit = source_audit(workspace, adapter)
    build_result: CommandResult | None = None
    artifact = workspace / str(adapter["build"]["artifact"])
    build_ok = False
    results: list[ScriptResult] = []
    if not audit["blocking"]:
        build_result, artifact = build_candidate(workspace, adapter, args.build_timeout)
        build_ok = (
            not build_result.timed_out
            and build_result.returncode == 0
            and artifact.is_file()
            and artifact.stat().st_size > 0
        )

    short_circuited = 0
    if build_ok:
        consecutive_timeouts = 0
        for test, script in zip(selected, scripts, strict=True):
            if consecutive_timeouts >= MAX_CONSECUTIVE_SCRIPT_TIMEOUTS:
                short_circuited += 1
                results.append(
                    ScriptResult(
                        str(test["id"]), int(test["stage"]), str(test.get("validity", "valid")), False, 0.0,
                        "script_timeout",
                        f"not run: the candidate timed out on {MAX_CONSECUTIVE_SCRIPT_TIMEOUTS} consecutive scripts",
                        0.0, 0.0, None,
                    )
                )
                continue
            result = run_script(workspace, adapter, artifact, script, test, timeout)
            consecutive_timeouts = consecutive_timeouts + 1 if result.failure_type == "script_timeout" else 0
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
            ScriptResult(str(test["id"]), int(test["stage"]), str(test.get("validity", "valid")), False, 0.0, failure_type, detail, 0.0, 0.0, None)
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
        "task": {
            "runtime": "sql-engine",
            "sqlite_version": task["effective"]["sqlite_version"],
            "script_timeout_seconds": timeout,
        },
        "selection": {
            "max_stage": args.max_stage,
            "latest_only": args.latest_only,
            "test_id": args.test_id,
            "count": len(selected),
        },
        "source_audit": audit,
        "build": asdict(build_result) if build_result else None,
        "input_policy": {
            "protocol": "sqllogictest records as ;-terminated statements; candidate blocks `ok <N>` / `error <message>`",
            "reference_disagreements_excluded": True,
            "max_consecutive_script_timeouts": MAX_CONSECUTIVE_SCRIPT_TIMEOUTS,
            "short_circuited_scripts": short_circuited,
        },
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
