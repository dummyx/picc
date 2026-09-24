Implement PiCC in {{LANGUAGE}} using only the standard library.
Build with `{{BUILD_COMMAND}}`; invoke as `{{ENTRY_COMMAND}}`.

Support integer-only C with decimal constants, local and file-scope `int`
objects, arithmetic/comparison/logical operators, unary `-`/`~`/`!`, assignment, `?:`, blocks and
lexical scope, `if`/`else`, `while`/`do`/`for`, `break`/`continue`, `return`,
function declarations/definitions/calls with integer parameters, and `static`/`extern`.

For valid input, emit GNU-compatible x86-64 System V assembly to the requested
path and exit 0. For invalid input, exit nonzero, report diagnostics on stderr,
and leave no usable assembly file. Assembly and linking are handled externally.

Work in `/workspace`, offline. Do not access harness internals or modify
experiment-control files. The compiler must implement the translation itself,
without existing compiler/interpreter implementations, subprocesses, or
hard-coded test answers.
