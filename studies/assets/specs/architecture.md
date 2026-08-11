# PiCC behavioral and architecture specification

Implement the same PiCC behavior and command contract described below in
{{LANGUAGE}}, using the {{FRAMEWORK}} condition.

Build with `{{BUILD_COMMAND}}`. The evaluator invokes `{{ENTRY_COMMAND}}`.
Accepted input must produce GNU-compatible x86-64 System V assembly and exit 0;
rejected input must exit nonzero without a usable output. Dependency policy:
{{DEPENDENCY_POLICY}}. Do not invoke or embed an existing compiler/interpreter,
spawn subprocesses, or use network access.

## Required language behavior

Implement the following cumulative C subset:

1. `int main(void)`, decimal constants, `return`.
2. Unary `-`, `~`, `!`.
3. Arithmetic `+`, `-`, `*`, `/`, `%` with C precedence and associativity.
4. Relational/equality operators and short-circuit `&&`/`||`.
5. Local `int` declarations, initialization, identifiers, and assignment.
6. `if`, `else`, `?:`.
7. Compound statements, lexical scope, duplicate-declaration rejection, and
   nested shadowing.
8. `while`, `do`, `for`, `break`, `continue` with context validation.
9. Function declarations/definitions/calls, integer parameters and results, and
   x86-64 System V register/stack argument passing.
10. File-scope integer objects, tentative/initialized definitions, `static`, and
    `extern` in the evaluated subset.

Use longest-token matching, reject unknown tokens, enforce expression
precedence, require modifiable assignment targets, resolve each identifier to
the nearest valid declaration, reject incompatible declarations and duplicate
definitions, preserve stack alignment at calls, and implement observable
short-circuit behavior. Diagnostics go to standard error. No optimization is
required.

## Required component boundaries

Use these logical components, with equivalent files/modules when the language
requires different naming:

- `lexer`: source text to a token stream with source locations;
- `parser`: token stream to a syntax tree, without code generation side effects;
- `sema`: name resolution and semantic checks, producing a resolved tree or
  explicit semantic information;
- `ir`: a simple, target-independent representation with explicit temporaries,
  labels, jumps, calls, loads/stores, and returns;
- `codegen`: IR to x86-64 System V assembly;
- `driver`: CLI validation and orchestration only.

Keep the dependency direction `driver -> lexer -> parser -> sema -> ir ->
codegen`; lower layers must not import the CLI. Parsing must not allocate stack
slots or emit assembly. Semantic analysis must be complete before target code
emission for a function.

## Recommended interfaces and invariants

- Tokens carry kind, lexeme/value, and byte or line/column location.
- The parser owns one cursor and exposes deterministic `peek`, `consume`, and
  `expect` operations. Use precedence climbing or recursive-descent levels for
  expressions.
- AST nodes distinguish declarations, statements, and expressions. Assignment
  is represented explicitly rather than as an arbitrary binary operator.
- Semantic resolution assigns each local declaration a stable unique symbol ID;
  code generation must not use raw source names as local storage identities.
- Maintain lexical scope as a stack of maps. Enter and exit scopes with compound
  statements and function bodies.
- Maintain loop context as a stack containing break and continue labels.
- Lower each function to explicit control flow before assembly emission.
- Represent local variables and temporaries independently of physical registers;
  a stack-slot backend is acceptable and preferred initially.
- Centralize ABI argument classification, stack alignment, function prologue,
  epilogue, and symbol visibility. Do not duplicate ABI logic across AST cases.
- Every failed compilation removes or avoids creating the requested output.
- Driver errors, lexical errors, parse errors, and semantic errors use one
  structured diagnostic path and produce nonzero exit status.

## Milestones

Implement and verify one vertical slice at a time: tokenize, parse, resolve,
lower, emit, then execute a Stage-1 program. Extend the existing representations
for later stages rather than adding test-specific paths. Keep earlier stages
working at every milestone.
