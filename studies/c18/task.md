Implement PiCC in {{LANGUAGE}} using only the standard library.
Build with `{{BUILD_COMMAND}}`; invoke as `{{ENTRY_COMMAND}}`.

PiCC compiles one preprocessed C translation unit (no preprocessor
directives remain) with C17 semantics for x86-64 Linux. Support: the types
`int`, `long`, `unsigned int`, `unsigned long`, `double`, `char`,
`signed char`, `unsigned char`, `void`, pointers (including `void *`),
arrays (multidimensional, pointer decay, subscripting and pointer
arithmetic), and structures (tags, members of any supported type, nesting,
`.` and `->`, passing and returning by value); integer constants with `l`/`u`
suffixes, floating constants, character constants and string literals with
escape sequences; the usual arithmetic, comparison, logical, unary (`-`, `~`,
`!`, `&`, `*`), assignment, and conditional operators with the standard
implicit conversions and explicit casts; `sizeof`; blocks and lexical scope,
`if`/`else`, `while`/`do`/`for`, `break`/`continue`, `return`; local and
file-scope objects with `static`/`extern`, scalar, compound, and string
initializers; function declarations and definitions with parameters and
return values of any supported type, following the System V x86-64 calling
convention so that calls into other translation units and the C standard
library work.

For valid input, emit GNU-compatible x86-64 System V assembly to the
requested path and exit 0; the unit may reference functions and objects
defined elsewhere, which are linked in externally. For invalid input
(lexical, syntactic, or semantic errors such as type mismatches, undeclared,
conflicting, or incomplete-type uses), exit nonzero, report diagnostics on
stderr, and leave no usable assembly file. Assembly and linking are handled
externally.

Work in `/workspace`, offline. Do not access harness internals or modify
experiment-control files. The compiler must implement the translation itself,
without existing compiler/interpreter implementations, subprocesses, or
hard-coded test answers.
