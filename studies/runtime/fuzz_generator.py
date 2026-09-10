#!/usr/bin/env python3
"""Program generator for the PiCC differential-fuzz oracle.

Emits UB-free C programs restricted to a cumulative stage subset of the PiCC
task, together with the exit status and stdout GCC will produce for them. The
stage limit gates both operators and program shape: stages 1-4 are a single
`return` of an expression, stage 5 adds locals, 6 the conditional operator, 8
counted loops, 9 helper functions with 1-8 parameters (so register and stack
argument passing are both exercised), and 10 initialized file-scope objects.

This module is pure and deterministic given its `random.Random`; the runtime
scorer (`fuzz_evaluate.py`) and the host-side `analysis/fuzz_differential.py`
both import it, so the frozen harness and the descriptive analysis generate
identical programs for identical seeds.
"""

from __future__ import annotations

import operator
import random
from dataclasses import dataclass

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
