#!/usr/bin/env python3
"""Stage-averaged differential-fuzz score for one candidate snapshot.

The corpus oracle (`evaluate.py`) checks a fixed set of hand-written programs
and invalid-program rejection. This scorer checks generated valid programs:
for each stage 1..K it generates N programs restricted to that stage's
cumulative feature subset (`fuzz_generator.py`), compiles each with GCC as the
reference, then with the candidate through the same assemble/link/run path the
corpus evaluator uses, and compares exit status and stdout. A stage's pass rate
is the share of evaluated programs on which the two agree; the **fuzz macro**
is the mean over stages, the analogue of the corpus macro score. One broken
feature therefore costs the stages that use it rather than every program.

Failures counted against the candidate: rejecting a valid program, a compiler
hang, emitted assembly that does not assemble or link, a hang or crash of the
compiled program, and a wrong result. Programs the reference itself disagrees
with are generator defects and are skipped, never charged to the candidate.

The same frozen adapter, audit, and build path as the corpus evaluator apply: a
blocking audit finding or a failed build scores 0 on every stage. A wall-clock
deadline bounds the whole evaluation; a stage not reached by the deadline
scores 0, and a stage cut short scores on its evaluated programs only if at
least MIN_EVALUATED_FOR_STAGE were evaluated.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import random
import statistics
import sys
import tempfile
import time
import traceback
from collections import Counter
from dataclasses import asdict
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import evaluate as corpus  # noqa: E402  (the frozen study evaluator alongside this file)
from fuzz_generator import Generator  # noqa: E402

GCC = "/usr/bin/gcc"
REFERENCE_BUILD = [GCC, "-std=c17", "-O0", "-w"]
LINK = [GCC, "-x", "assembler", "-fno-pie", "-no-pie"]
MIN_EVALUATED_FOR_STAGE = 20
SAMPLE_LIMIT = 3


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--candidate-config", type=Path, default=HERE / "candidate.json")
    parser.add_argument("--max-stage", type=int, required=True)
    parser.add_argument("--count", type=int, default=100, help="programs per stage")
    parser.add_argument("--seed-base", type=int, default=20260830, help="stage s uses seed base + s")
    parser.add_argument("--run-timeout", type=int, default=3, help="seconds for each compiled program")
    parser.add_argument("--compile-timeout", type=int, default=10, help="seconds for each candidate compile")
    parser.add_argument("--build-timeout", type=int, default=900)
    parser.add_argument("--deadline-seconds", type=int, default=5400, help="wall-clock bound for the whole evaluation")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--summary-json", action="store_true")
    args = parser.parse_args()
    if args.max_stage < 1 or args.count < 1:
        parser.error("--max-stage and --count must be positive")
    return args


def failure_detail(result: corpus.CommandResult) -> str:
    text = (result.stderr or result.stdout or "").strip()
    return corpus.truncate(text, 300) if text else f"exit status {result.returncode}"


def fuzz_stage(
    workspace: Path,
    adapter: dict[str, Any],
    artifact: Path,
    stage: int,
    args: argparse.Namespace,
    deadline: float,
) -> dict[str, Any]:
    generator = Generator(random.Random(args.seed_base + stage), stage, False)
    skipped = evaluated = passed = 0
    kinds: Counter[str] = Counter()
    samples: list[dict[str, Any]] = []
    deadline_hit = False
    with tempfile.TemporaryDirectory(prefix="picc-fuzz-") as temporary:
        temp = Path(temporary)
        for index in range(args.count):
            if time.monotonic() > deadline:
                deadline_hit = True
                break
            source, expected_status, expected_stdout = generator.program()
            src = temp / "case.c"
            src.write_text(source, encoding="utf-8")

            # Oracle 1: GCC must agree with the generator's own evaluation; a
            # disagreement is a generator defect and is skipped, not charged.
            reference = temp / "reference"
            built = corpus.run_command(REFERENCE_BUILD + [str(src), "-o", str(reference)], cwd=temp, timeout=args.compile_timeout)
            if built.timed_out or built.returncode != 0:
                skipped += 1
                continue
            ref_run = corpus.run_command([str(reference)], cwd=temp, timeout=args.run_timeout)
            if ref_run.timed_out or ref_run.returncode != expected_status or ref_run.stdout != expected_stdout:
                skipped += 1
                continue

            # Oracle 2: the candidate through the corpus evaluator's own path.
            evaluated += 1
            assembly = temp / "case.s"
            assembly.unlink(missing_ok=True)
            compiled = corpus.candidate_compile(workspace, adapter, artifact, src, assembly, args.compile_timeout)
            kind: str | None
            detail = ""
            if compiled.timed_out:
                kind, detail = "compiler_timeout", f"no result within {args.compile_timeout}s"
            elif compiled.returncode != 0 or not assembly.exists() or assembly.stat().st_size == 0:
                kind, detail = "rejected_valid_program", failure_detail(compiled)
            else:
                executable = temp / "candidate"
                linked = corpus.run_command(LINK + [str(assembly), "-o", str(executable)], cwd=temp, timeout=args.compile_timeout)
                if linked.timed_out or linked.returncode != 0:
                    kind, detail = "assembly_or_link_failure", failure_detail(linked)
                else:
                    got = corpus.run_command([str(executable)], cwd=temp, timeout=args.run_timeout)
                    if got.timed_out:
                        kind, detail = "timeout", f"program did not finish within {args.run_timeout}s"
                    elif got.returncode != expected_status or got.stdout != expected_stdout:
                        kind = "wrong_behavior"
                        detail = (
                            f"expected status {expected_status} stdout {expected_stdout!r}; "
                            f"got status {got.returncode} stdout {corpus.truncate(got.stdout, 100)!r}"
                        )
                    else:
                        kind = None
            if kind is None:
                passed += 1
                continue
            kinds[kind] += 1
            if len(samples) < SAMPLE_LIMIT:
                samples.append({"index": index, "kind": kind, "detail": detail, "source": corpus.truncate(source, 1500)})

    # A stage that ran every requested program scores on all of them; a stage
    # the deadline cut short scores on what it evaluated only if that is at
    # least MIN_EVALUATED_FOR_STAGE, otherwise 0 (conservative for a compiler
    # too slow or too hang-prone to evaluate).
    if evaluated == 0:
        pass_rate, status = 0.0, ("insufficient" if deadline_hit else "empty")
    elif deadline_hit and evaluated < MIN_EVALUATED_FOR_STAGE:
        pass_rate, status = 0.0, "insufficient"
    else:
        pass_rate, status = passed / evaluated, ("partial" if deadline_hit else "complete")
    return {
        "stage": stage,
        "seed": args.seed_base + stage,
        "status": status,
        "generated": skipped + evaluated,
        "skipped": skipped,
        "evaluated": evaluated,
        "passed": passed,
        "mismatches": evaluated - passed,
        "pass_rate": pass_rate,
        "mismatch_kinds": dict(kinds),
        "samples": samples,
        "deadline_hit": deadline_hit,
    }


def not_run(stage: int, reason: str) -> dict[str, Any]:
    return {
        "stage": stage,
        "status": "not_run",
        "reason": reason,
        "generated": 0,
        "skipped": 0,
        "evaluated": 0,
        "passed": 0,
        "mismatches": 0,
        "pass_rate": 0.0,
        "mismatch_kinds": {},
        "samples": [],
        "deadline_hit": False,
    }


def main() -> int:
    args = parse_args()
    started = time.time()
    deadline = time.monotonic() + args.deadline_seconds
    workspace = args.workspace.resolve()
    adapter = corpus.load_object(args.candidate_config.resolve())
    if adapter.get("schema_version") != 1:
        raise ValueError("Unsupported candidate adapter schema")

    audit = corpus.source_audit(workspace, adapter)
    build_result: corpus.CommandResult | None = None
    artifact = workspace / str(adapter["build"]["artifact"])
    build_ok = False
    if not audit["blocking"]:
        build_result, artifact = corpus.build_candidate(workspace, adapter, args.build_timeout)
        build_ok = (
            not build_result.timed_out
            and build_result.returncode == 0
            and artifact.is_file()
            and artifact.stat().st_size > 0
        )

    stages: dict[str, dict[str, Any]] = {}
    for stage in range(1, args.max_stage + 1):
        if audit["blocking"]:
            stages[str(stage)] = not_run(stage, "source_audit_failure")
        elif not build_ok:
            stages[str(stage)] = not_run(stage, "build_failure")
        elif time.monotonic() > deadline:
            stages[str(stage)] = not_run(stage, "deadline")
        else:
            stages[str(stage)] = fuzz_stage(workspace, adapter, artifact, stage, args, deadline)

    rates = [float(stages[str(stage)]["pass_rate"]) for stage in range(1, args.max_stage + 1)]
    kinds: Counter[str] = Counter()
    for row in stages.values():
        kinds.update(row["mismatch_kinds"])
    summary = {
        "fuzz_macro": statistics.mean(rates) if rates else 0.0,
        "stage_pass_rates": rates,
        "max_stage": args.max_stage,
        "programs_per_stage": args.count,
        "evaluated_total": sum(int(row["evaluated"]) for row in stages.values()),
        "passed_total": sum(int(row["passed"]) for row in stages.values()),
        "mismatches_total": sum(int(row["mismatches"]) for row in stages.values()),
        "skipped_total": sum(int(row["skipped"]) for row in stages.values()),
        "mismatch_kinds": dict(kinds),
        "stages_complete": sum(1 for row in stages.values() if row["status"] == "complete"),
        "deadline_hit": any(row.get("deadline_hit") or row.get("reason") == "deadline" for row in stages.values()),
        "build_ok": build_ok,
        "audit_ok": bool(audit.get("passed")),
        "audit_blocking": bool(audit.get("blocking")),
    }
    output = {
        "schema_version": 1,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "elapsed_seconds": time.time() - started,
        "workspace": str(workspace),
        "candidate": {
            "language": adapter.get("language"),
            "framework": adapter.get("framework"),
            "artifact": str(artifact),
        },
        "policy": {
            "max_stage": args.max_stage,
            "programs_per_stage": args.count,
            "seed_base": args.seed_base,
            "run_timeout_seconds": args.run_timeout,
            "compile_timeout_seconds": args.compile_timeout,
            "build_timeout_seconds": args.build_timeout,
            "deadline_seconds": args.deadline_seconds,
            "min_evaluated_for_stage": MIN_EVALUATED_FOR_STAGE,
            "reference_build": REFERENCE_BUILD,
        },
        "source_audit": audit,
        "build": asdict(build_result) if build_result else None,
        "stages": stages,
        "summary": summary,
    }
    corpus.atomic_json(args.output, output)
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
            corpus.atomic_json(parsed.output, failure)
        print(json.dumps(failure, sort_keys=True))
        raise SystemExit(2)
