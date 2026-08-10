# PiCC task specification

Implement **PiCC**, a compiler for a substantial subset of C, written in Rust.
The product repository initially contains no implementation.

## Command-line contract

PiCC must build with:

```bash
cargo build --release
```

The resulting compiler must run as:

```bash
target/release/picc INPUT.c -o OUTPUT.s
```

For valid input, PiCC must emit GNU-compatible x86-64 System V assembly to the
requested path and exit with status 0. The external evaluator assembles and
links that assembly.

For invalid input, PiCC must exit nonzero and must not leave a usable output
file.

PiCC must not invoke an existing C compiler, C interpreter, LLVM, GCC JIT,
TinyCC, libclang, or another language implementation. The submitted compiler
must not spawn subprocesses and must use only the Rust standard library; the
frozen environment intentionally provides no third-party Cargo dependencies.
No optimization is required.

## Required stages

Implement the stages incrementally. Later stages include all earlier stages.

1. `int main(void)`, decimal integer constants, and `return` statements.
2. Unary `-`, `~`, and `!`.
3. Binary `+`, `-`, `*`, `/`, `%`, precedence, associativity, and parentheses.
4. Relational and equality operators; `&&` and `||` with short-circuiting.
5. Local integer declarations, identifiers, initialization, and assignment.
6. `if`, `else`, and the conditional expression `?:`.
7. Compound statements, lexical block scopes, and shadowing rules.
8. `while`, `do`, `for`, `break`, and `continue`.
9. Function declarations and definitions, integer parameters, return values,
   and calls under the x86-64 System V ABI.
10. File-scope integer objects, internal/external linkage, `static`, and
    `extern` for the tested subset.

The implementation must reject the lexical, syntactic, and semantic errors in
the visible invalid-input tests. It should report concise diagnostics to
standard error.

## Suggested internal pipeline, not a required architecture

A conventional implementation is likely to need:

- tokenizer;
- parser and AST;
- identifier resolution and semantic validation;
- an intermediate representation or structured code-generation layer;
- x86-64 assembly generation.

Choose and evolve the architecture based on evidence from compilation and
behavioral tests. Do not special-case individual tests.

## Experiment tools

Use the Pi extension tools rather than calling an external C compiler:

- `test_visible({})`: run all visible tests through the configured maximum stage;
- `test_visible({"stage": 4})`: run tests through Stage 4;
- `test_visible({"stage": 4, "latestOnly": true})`: run only Stage 4;
- `test_visible({"testId": "..."})`: run one visible test by its manifest ID;
- `experiment_status({})`: inspect the fixed run budget and last harness score.

Begin with a minimal, end-to-end Stage 1 compiler. Progress sequentially while
preserving previously passing behavior.
