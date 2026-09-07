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
import operator
import random
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

INT_MIN = -(2**31)
INT_MAX = 2**31 - 1

# Keep generated magnitudes far below the 32-bit boundary so composing a few
# operators cannot overflow. Anything that still would is rejected at build time.
LEAF_MAX = 60

# Normalising modulus: prime, and below 256 so the value survives an 8-bit exit
# status intact rather than being truncated by it.
NORM = 251

COMPARISONS = {
    "<": operator.lt,
    "<=": operator.le,
    ">": operator.gt,
    ">=": operator.ge,
    "==": operator.eq,
    "!=": operator.ne,
}


@dataclass(frozen=True)
class Expr:
    text: str
    value: int


def fits(value: int) -> bool:
    return INT_MIN <= value <= INT_MAX


def c_div(left: int, divisor: int) -> int:
    """C truncates toward zero; Python floors."""
    quotient = abs(left) // divisor
    return quotient if left >= 0 else -quotient


def normalise(value: int) -> int:
    """Fold any int into 0..NORM-1, matching the emitted C expression."""
    remainder = value % NORM if value >= 0 else -((-value) % NORM)
    return (remainder + NORM) % NORM


class Generator:
    """Emits UB-free programs restricted to the cumulative stage subset."""

    def __init__(self, rng: random.Random, max_stage: int, stdout_checksum: bool) -> None:
        self.rng = rng
        self.max_stage = max_stage
        self.stdout_checksum = stdout_checksum and max_stage >= 10

    # ---- expressions -------------------------------------------------------

    def leaf(self, scope: dict[str, int]) -> Expr:
        if scope and self.rng.random() < 0.45:
            name = self.rng.choice(sorted(scope))
            return Expr(name, scope[name])
        value = self.rng.randint(0, LEAF_MAX)
        return Expr(str(value), value)

    def expr(self, depth: int, scope: dict[str, int]) -> Expr:
        if depth <= 0:
            return self.leaf(scope)

        choices: list[str] = ["leaf"]
        if self.max_stage >= 2:
            choices.append("unary")
        if self.max_stage >= 3:
            choices += ["arith", "arith"]
        if self.max_stage >= 4:
            choices += ["compare", "logical"]
        if self.max_stage >= 6:
            choices.append("ternary")

        kind = self.rng.choice(choices)
        if kind == "leaf":
            return self.leaf(scope)
        if kind == "unary":
            return self.unary(depth, scope)
        if kind == "arith":
            return self.arith(depth, scope)
        if kind == "compare":
            left = self.expr(depth - 1, scope)
            right = self.expr(depth - 1, scope)
            op = self.rng.choice(sorted(COMPARISONS))
            return Expr(f"({left.text} {op} {right.text})", int(COMPARISONS[op](left.value, right.value)))
        if kind == "logical":
            left = self.expr(depth - 1, scope)
            right = self.expr(depth - 1, scope)
            op = self.rng.choice(["&&", "||"])
            truth = (left.value and right.value) if op == "&&" else (left.value or right.value)
            return Expr(f"({left.text} {op} {right.text})", 1 if truth else 0)

        condition = self.expr(depth - 1, scope)
        yes = self.expr(depth - 1, scope)
        no = self.expr(depth - 1, scope)
        return Expr(
            f"({condition.text} ? {yes.text} : {no.text})",
            yes.value if condition.value else no.value,
        )

    def unary(self, depth: int, scope: dict[str, int]) -> Expr:
        operand = self.expr(depth - 1, scope)
        op = self.rng.choice(["-", "~", "!"])
        if op == "-":
            value = -operand.value
        elif op == "~":
            value = ~operand.value
        else:
            value = 0 if operand.value else 1
        if not fits(value):
            return operand
        return Expr(f"({op}{operand.text})", value)

    def arith(self, depth: int, scope: dict[str, int]) -> Expr:
        left = self.expr(depth - 1, scope)
        op = self.rng.choice(["+", "-", "*", "/", "%"])
        if op in {"/", "%"}:
            # Division by zero and INT_MIN / -1 are both undefined; a positive
            # literal divisor sidesteps each of them.
            divisor = self.rng.randint(1, 20)
            quotient = c_div(left.value, divisor)
            value = quotient if op == "/" else left.value - quotient * divisor
            return Expr(f"({left.text} {op} {divisor})", value)

        right = self.expr(depth - 1, scope)
        if op == "+":
            value = left.value + right.value
        elif op == "-":
            value = left.value - right.value
        else:
            value = left.value * right.value
        if not fits(value):
            return left
        return Expr(f"({left.text} {op} {right.text})", value)

    # ---- programs ----------------------------------------------------------

    def program(self) -> tuple[str, int, str]:
        """Return (source, expected_exit_status, expected_stdout)."""
        if self.max_stage < 5:
            return self.straight_line_program()
        return self.full_program()

    def straight_line_program(self) -> tuple[str, int, str]:
        """Stages 1-4: no locals, so the whole program is one return."""
        expr = self.expr(3, {})
        if self.max_stage >= 3:
            text = f"((({expr.text}) % {NORM}) + {NORM}) % {NORM}"
            expected = normalise(expr.value)
        elif 0 <= expr.value < NORM:
            text, expected = expr.text, expr.value
        else:
            # Without `%` there is no way to fold a stray value into range.
            expected = self.rng.randint(0, NORM - 1)
            text = str(expected)
        return f"int main(void) {{\n    return {text};\n}}\n", expected, ""

    def functions(self) -> tuple[list[str], list[tuple[str, list[int]]]]:
        """Helper functions with 1-8 int parameters.

        The parameter counts straddle six deliberately: the x86-64 System V ABI
        passes the first six integer arguments in registers and the rest on the
        stack, so this is where argument-passing bugs live. The corpus cannot
        reach it -- the multi-file `libraries` tests that exercise the ABI are
        excluded from the standalone core.
        """
        declarations: list[str] = []
        signatures: list[tuple[str, list[int]]] = []
        for index in range(self.rng.randint(1, 3)):
            arity = self.rng.randint(1, 8)
            coefficients = [self.rng.randint(1, 5) for _ in range(arity)]
            params = [f"p{position}" for position in range(arity)]
            terms = " + ".join(f"{c} * {p}" for c, p in zip(coefficients, params))
            declarations.append(
                f"int f{index}({', '.join('int ' + p for p in params)}) {{\n    return {terms};\n}}"
            )
            signatures.append((f"f{index}", coefficients))
        return declarations, signatures

    def full_program(self) -> tuple[str, int, str]:
        lines: list[str] = []
        if self.stdout_checksum:
            lines += ["int putchar(int c);", ""]

        scope: dict[str, int] = {}
        body: list[str] = []

        if self.max_stage >= 10:
            # File-scope objects: read and written from main, so storage and
            # symbol emission are exercised rather than just locals.
            for index in range(self.rng.randint(1, 2)):
                value = self.rng.randint(0, LEAF_MAX)
                lines.append(f"int g{index} = {value};")
                scope[f"g{index}"] = value
            if lines:
                lines.append("")

        if self.max_stage >= 9:
            declarations, signatures = self.functions()
            lines += [declaration + "\n" for declaration in declarations]
            for name, coefficients in signatures:
                arguments: list[Expr] = []
                for _ in coefficients:
                    argument = self.expr(1, scope)
                    if not 0 <= argument.value <= 40:
                        # Bound each argument so the weighted sum cannot overflow.
                        literal = self.rng.randint(0, 40)
                        argument = Expr(str(literal), literal)
                    arguments.append(argument)
                total = sum(c * a.value for c, a in zip(coefficients, arguments))
                variable = f"c{name}"
                body.append(f"    int {variable} = {name}({', '.join(a.text for a in arguments)});")
                scope[variable] = total
        for index in range(self.rng.randint(1, 4)):
            init = self.expr(2, scope)
            name = f"v{index}"
            body.append(f"    int {name} = {init.text};")
            scope[name] = init.value

        if self.max_stage >= 8 and self.rng.random() < 0.5:
            # Counted loop with a literal bound: always terminates, and the
            # accumulator stays small enough that it cannot overflow.
            start = self.expr(1, scope)
            bound = self.rng.randint(1, 8)
            step = self.rng.randint(1, 5)
            body += [
                f"    int acc = {start.text};",
                "    int i = 0;",
                f"    while (i < {bound}) {{",
                f"        acc = acc + {step};",
                "        i = i + 1;",
                "    }",
            ]
            scope["acc"] = start.value + bound * step
            scope["i"] = bound

        final = self.expr(3, scope)
        expected = normalise(final.value)
        body += [
            f"    int result = {final.text};",
            f"    int norm = ((result % {NORM}) + {NORM}) % {NORM};",
        ]

        expected_stdout = ""
        if self.stdout_checksum:
            body += [
                "    putchar(48 + norm / 100);",
                "    putchar(48 + (norm / 10) % 10);",
                "    putchar(48 + norm % 10);",
                "    putchar(10);",
            ]
            expected_stdout = f"{expected // 100}{(expected // 10) % 10}{expected % 10}\n"

        body.append("    return norm;")
        lines += ["int main(void) {", *body, "}"]
        return "\n".join(lines) + "\n", expected, expected_stdout


def run(args: list[str], cwd: Path, timeout: int = 20) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=cwd, capture_output=True, text=True, timeout=timeout, check=False)


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
            ref_run = run([str(reference)], temp)
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

            got = run([str(candidate)], temp)
            checked += 1
            if got.returncode != expected_status or got.stdout != expected_stdout:
                mismatches.append(
                    {
                        "index": index,
                        "kind": "wrong_behavior",
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
