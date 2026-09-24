# PiCC behavioral specification

Implement **PiCC**, a compiler for a substantial, cumulative subset of C, in
{{LANGUAGE}} under the {{FRAMEWORK}} condition.

## Product interface

Build the repository with:

```text
{{BUILD_COMMAND}}
```

The evaluator invokes the compiler through:

```text
{{ENTRY_COMMAND}}
```

`INPUT.c` is one translation unit. `OUTPUT.s` is the exact requested assembly
path. On accepted input, PiCC must emit nonempty GNU-compatible x86-64 assembly
for the System V ABI and exit status 0. On rejected input, it must exit nonzero
and must not leave a usable output file. Diagnostics go to standard error. The
evaluator, not PiCC, assembles, links, and executes emitted assembly. No
optimization is required.

Dependency policy: {{DEPENDENCY_POLICY}}. The implementation must not invoke,
wrap, embed, dynamically load, or copy an existing C compiler/interpreter,
LLVM, libclang, GCC JIT, TinyCC, or another C-to-assembly implementation. The
submitted compiler must not spawn subprocesses or use network access.

## Lexical behavior

Recognize identifiers, decimal integer constants, the keywords and punctuation
needed by the stages below, whitespace, and C block and line comments when they
occur in the evaluated subset. Use longest-token matching for multi-character
operators such as `==`, `!=`, `<=`, `>=`, `&&`, and `||`. Reject unknown or
malformed tokens rather than silently skipping them.

## Expressions

Implement integer constants, variables, assignment, unary `-`, `~`, and `!`,
binary arithmetic `+`, `-`, `*`, `/`, `%`, comparisons `<`, `<=`, `>`, `>=`,
`==`, `!=`, logical `&&` and `||`, and the conditional expression `?:`.
Parentheses override precedence. Multiplicative operators bind tighter than
additive operators, followed by relational, equality, logical-and,
logical-or, conditional, then assignment. Assignment and conditional
expressions are right-associative; ordinary binary arithmetic and comparison
operators are left-associative. `&&` and `||` must short-circuit and normalize
their result to integer 0 or 1. `!` also yields 0 or 1. Integer division and
remainder follow the target machine's signed integer behavior for evaluated
inputs.

An assignment target must be a declared modifiable object. Reject uses of
undeclared identifiers and invalid assignment targets.

## Declarations, scopes, and statements

Support local `int` declarations with optional initializers. A declaration
enters its identifier in the current lexical scope. Reject duplicate local
declarations in the same scope, while permitting shadowing in nested scopes as
required by the tests. A use resolves to the nearest enclosing declaration.

Support expression statements, null statements, `return`, compound blocks,
`if`/`else`, `while`, `do`/`while`, and `for`. `else` associates with the nearest
unmatched `if`. Loop conditions use zero as false and nonzero as true. `break`
and `continue` are valid only in a loop; `continue` in a `for` loop proceeds to
the post expression before rechecking the condition. Reject control-flow
statements used outside their valid context.

Every evaluated function returns an integer. Falling off the end may be treated
consistently with the tested subset, but explicit `return` behavior must be
correct.

## Functions and ABI

Support function declarations, definitions, calls, integer parameters, and
integer return values. Check duplicate and incompatible declarations within the
scope of the evaluated subset. Reject calls to undeclared functions where the
subset requires a prior declaration, duplicate function definitions, and
argument-count mismatches.

Follow the x86-64 System V ABI for integer arguments and results. Handle calls
with enough arguments to require both register and stack passing in the tested
subset. Preserve stack alignment at call boundaries and preserve values across
calls according to the ABI. Multiple functions in one translation unit must be
emitted with distinct symbols and correct control flow.

## File-scope objects and linkage

Support tested file-scope `int` objects, tentative and initialized definitions,
internal linkage with `static`, and external declarations with `extern`.
Resolve local declarations separately from file-scope symbols. Emit storage and
symbol visibility consistent with the tested subset, reject conflicting
linkage/type declarations, and allow functions to read and write applicable
file-scope objects.

## Cumulative stages

1. `int main(void)`, integer constants, `return`.
2. Unary operators.
3. Arithmetic expressions.
4. Comparisons and short-circuit logic.
5. Local declarations and assignment.
6. Conditionals and `?:`.
7. Blocks and lexical scope.
8. Loops, `break`, and `continue`.
9. Functions and calls.
10. File-scope objects, `static`, and `extern`.

Later stages include all earlier behavior. Preserve previously correct behavior
while extending the compiler. Reject lexical, syntactic, and semantic errors in
the supplied subset; do not accept invalid input merely because code generation
could proceed.
