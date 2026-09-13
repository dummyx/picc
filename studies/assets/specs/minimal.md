# PiCC

Implement **PiCC**, a compiler for a subset of C, in {{LANGUAGE}} under the
{{FRAMEWORK}} condition.

Build with:

```text
{{BUILD_COMMAND}}
```

The evaluator invokes:

```text
{{ENTRY_COMMAND}}
```

The input is one C source file. The output is x86-64 assembly, which the
evaluator assembles, links, and runs. Accept valid programs and exit 0. Reject
invalid programs with a nonzero exit.

Feature stages, cumulative:

1. A program that returns an integer constant.
2. Unary operators.
3. Binary arithmetic.
4. Comparisons and logical operators.
5. Local variables.
6. `if` and conditional expressions.
7. Blocks and scopes.
8. Loops.
9. Functions.
10. File-scope variables, `static`, and `extern`.

Dependency policy: {{DEPENDENCY_POLICY}}. PiCC may not invoke or embed an
existing compiler, interpreter, or similar implementation, and may not spawn
subprocesses.
