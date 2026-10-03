Implement PiCC in {{LANGUAGE}} using only the standard library.
Build with `{{BUILD_COMMAND}}`; invoke as `{{ENTRY_COMMAND}}`. Both commands
are run from `/workspace` itself, so the project root is `/workspace`, not a
subdirectory of it, and the paths they name are relative to `/workspace`.

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

PiCC is started as `{{ENTRY_COMMAND}}`: it reads that one source file, writes
the assembly to the named output path only (never to standard output), and
reads nothing from standard input. For example, with `INPUT.c` containing

    int main(void) { return 2 + 3; }

it must write to `OUTPUT.s` x86-64 assembly for a `main` that returns 5 and
exit 0; assembled and linked, the program then exits with status 5. With
`INPUT.c` containing

    int main(void) { return 2 + ; }

it must exit nonzero, print a diagnostic on standard error, and leave no
`OUTPUT.s`.

Work in `/workspace`, offline. The repository is scored exactly as it stands
when a fixed time budget ends (two hours for a full run), in whatever state it
is in, so keep the compiler building and behaving correctly at all times. Do
not access harness internals or modify experiment-control files. The compiler must implement the translation itself,
without existing compiler/interpreter implementations, subprocesses, or
hard-coded test answers.
