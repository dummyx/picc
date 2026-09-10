#!/usr/bin/env python3
"""Differential fuzzing for a PiCC candidate compiler.

Why this exists: the frozen corpus verifies semantics through a single byte.
224 of its 227 valid tests produce no stdout, so the only compared observable is
the process exit status. `chapter_2/valid/negate_int_max.c` returns -2147483647,
which masks to exit status 1 -- the test nominally covers negating INT_MAX and
actually checks "did it exit 1". Only 11 distinct literal return values appear
across the entire valid set.

This is the standard remedy from the compiler-testing literature:

  * Csmith (Yang, Chen, Eide, Regehr, PLDI 2011) -- generate random programs and
    differentially test against a reference compiler; programs emit a checksum
    over accumulated state instead of collapsing to one return code, and
    undefined behaviour is excluded by construction so any observed difference
    is a genuine bug rather than a licence the standard grants.
  * YARPGen (Livinskii, Babokin, Regehr, OOPSLA 2020) -- generation policies that
    keep the generator from saturating on the same program shapes.

Two adaptations are forced by the task's language subset, which has no standard
library and no bitwise operators:

  * Width. Below stage 9 the subset cannot express output at all, so resolution
    comes from volume -- many small targeted programs -- rather than from width.
    With --stdout-checksum (stage 10+), programs declare `int putchar(int);` and
    emit the result digit by digit, recovering a wide observable in Csmith's
    spirit. That is opt-in because it requires calling an externally defined
    function, which the standalone-core corpus never exercises.
  * UB freedom. Expressions are generated and evaluated simultaneously under
    32-bit signed semantics; any node that would overflow or divide by zero is
    rejected as it is built, and locals are always initialised. That also gives a
    second independent oracle: this module's own computed value is checked
    against GCC before the candidate is consulted, so a generator bug is
    reported as a skip rather than blamed on the compiler under test.

Usage:
    python3 analysis/fuzz_differential.py --workspace runs/<id>/workspace \\
        --max-stage 10 --count 300
"""

from __future__ import annotations

import argparse
import json
import random
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "studies" / "runtime"))
from fuzz_generator import Generator  # noqa: E402  (shared with the frozen runtime scorer)


TIMEOUT_STATUS = -124


def run(args: list[str], cwd: Path, timeout: int = 20) -> subprocess.CompletedProcess[str]:
    """Run a step; a hang is reported as status TIMEOUT_STATUS instead of aborting the fuzz run.

    A candidate that emits an infinite loop is a wrong-behavior mismatch, not a
    reason to lose the rest of the batch.
    """
    try:
        return subprocess.run(args, cwd=cwd, capture_output=True, text=True, timeout=timeout, check=False)
    except subprocess.TimeoutExpired:
        return subprocess.CompletedProcess(args, TIMEOUT_STATUS, "", f"timed out after {timeout}s")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, required=True, help="candidate repository")
    parser.add_argument("--artifact", default="target/release/picc")
    parser.add_argument(
        "--runner",
        default="",
        help="interpreter prepended to the artifact, e.g. `node` for the JavaScript/TypeScript candidates",
    )
    parser.add_argument("--max-stage", type=int, default=10)
    parser.add_argument("--count", type=int, default=200)
    parser.add_argument("--seed", type=int, default=20260830)
    parser.add_argument(
        "--stdout-checksum",
        action="store_true",
        help="emit the result through putchar for a wide observable (stage 10+)",
    )
    parser.add_argument("--json", type=Path)
    parser.add_argument("--keep-failures", type=Path)
    parser.add_argument(
        "--run-timeout",
        type=int,
        default=20,
        help="seconds allowed for each compiled program to run; a hang is a `timeout` mismatch",
    )
    args = parser.parse_args()

    workspace = args.workspace.resolve()
    compiler = workspace / args.artifact
    if not compiler.exists():
        print(f"candidate artifact not found: {compiler}")
        return 2
    gcc = shutil.which("gcc")
    if gcc is None:
        print("gcc is required as the reference oracle")
        return 2

    generator = Generator(random.Random(args.seed), args.max_stage, args.stdout_checksum)
    mismatches: list[dict[str, object]] = []
    checked = skipped = 0

    with tempfile.TemporaryDirectory(prefix="picc-fuzz-") as temporary:
        temp = Path(temporary)
        for index in range(args.count):
            source, expected_status, expected_stdout = generator.program()
            src = temp / "case.c"
            src.write_text(source, encoding="utf-8")

            # Oracle 1: GCC must agree with this module's own evaluation. A
            # disagreement means the generator is wrong, so skip rather than
            # blame the compiler under test.
            reference = temp / "reference"
            built = run([gcc, "-std=c17", "-O0", "-w", str(src), "-o", str(reference)], temp)
            if built.returncode != 0:
                skipped += 1
                continue
            ref_run = run([str(reference)], temp, timeout=args.run_timeout)
            if ref_run.returncode != expected_status or ref_run.stdout != expected_stdout:
                skipped += 1
                continue

            # Oracle 2: the candidate, through the same assemble/link/run path
            # the evaluator uses.
            assembly = temp / "case.s"
            assembly.unlink(missing_ok=True)
            compiled = run(([args.runner] if args.runner else []) + [str(compiler), str(src), "-o", str(assembly)], temp)
            if compiled.returncode != 0 or not assembly.exists():
                mismatches.append(
                    {
                        "index": index,
                        "kind": "rejected_valid_program",
                        "detail": compiled.stderr[:400],
                        "source": source,
                    }
                )
                continue
            candidate = temp / "candidate"
            linked = run(
                [gcc, "-x", "assembler", "-fno-pie", "-no-pie", str(assembly), "-o", str(candidate)],
                temp,
            )
            if linked.returncode != 0:
                mismatches.append(
                    {
                        "index": index,
                        "kind": "assembly_or_link_failure",
                        "detail": linked.stderr[:400],
                        "source": source,
                    }
                )
                continue

            got = run([str(candidate)], temp, timeout=args.run_timeout)
            checked += 1
            if got.returncode != expected_status or got.stdout != expected_stdout:
                mismatches.append(
                    {
                        "index": index,
                        "kind": "timeout" if got.returncode == TIMEOUT_STATUS else "wrong_behavior",
                        "detail": (
                            f"expected status {expected_status} stdout {expected_stdout!r}; "
                            f"got status {got.returncode} stdout {got.stdout!r}"
                        ),
                        "source": source,
                    }
                )

    print(
        f"generated {args.count}, checked {checked}, skipped {skipped}, "
        f"mismatches {len(mismatches)}"
    )
    by_kind: dict[str, int] = {}
    for row in mismatches:
        key = str(row["kind"])
        by_kind[key] = by_kind.get(key, 0) + 1
    for kind, count in sorted(by_kind.items()):
        print(f"  {kind}: {count}")
    if mismatches:
        first = mismatches[0]
        print("\nsmallest failing case:")
        print(str(first["source"]).rstrip())
        print(first["detail"])
    if args.json:
        args.json.write_text(
            json.dumps({"checked": checked, "skipped": skipped, "mismatches": mismatches}, indent=2)
            + "\n",
            encoding="utf-8",
        )
    if args.keep_failures and mismatches:
        args.keep_failures.mkdir(parents=True, exist_ok=True)
        for row in mismatches:
            (args.keep_failures / f"case-{int(row['index']):04d}.c").write_text(
                str(row["source"]), encoding="utf-8"
            )
    return 1 if mismatches else 0


if __name__ == "__main__":
    raise SystemExit(main())
