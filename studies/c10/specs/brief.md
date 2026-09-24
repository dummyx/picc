# PiCC product brief

Implement **PiCC**, a compiler for the core C subset listed below, in
{{LANGUAGE}} using the {{FRAMEWORK}} condition.

Build with:

```text
{{BUILD_COMMAND}}
```

The evaluator invokes:

```text
{{ENTRY_COMMAND}}
```

The compiler receives a C source file and `-o OUTPUT.s`. Valid programs must
produce GNU-compatible x86-64 System V assembly and exit 0. Invalid programs
must exit nonzero and leave no usable output file. The evaluator performs
assembly, linking, and execution. No optimization is required.

Implement these cumulative stages:

1. `int main(void)`, decimal integer constants, `return`.
2. Unary `-`, `~`, `!`.
3. `+`, `-`, `*`, `/`, `%`, precedence, associativity, parentheses.
4. Relational/equality operators and short-circuit `&&`/`||`.
5. Local integer declarations, identifiers, initialization, assignment.
6. `if`, `else`, and `?:`.
7. Compound statements, lexical scopes, shadowing.
8. `while`, `do`, `for`, `break`, `continue`.
9. Function declarations/definitions, integer parameters, returns, and calls
   under the x86-64 System V ABI.
10. File-scope integer objects and the tested `static`/`extern` behavior.

Reject malformed tokens, syntax, and semantic errors covered by the specified
subset. Report concise diagnostics on standard error.

Dependency policy: {{DEPENDENCY_POLICY}}. PiCC may not invoke or embed an
existing compiler, interpreter, LLVM, GCC JIT, TinyCC, or similar implementation,
and may not spawn subprocesses.
