# Chapters 1-18 C compiler task (`picc-c18-minimal-v1`)

A second, separate compiler task: the core of *Writing a C Compiler*
chapters 1-18 (integer types, unsigned, doubles, pointers, arrays,
characters and strings, `void`/`sizeof`, structures). The chapters 1-10 task
(`data/partitions`, `studies/minimal`, `studies/starter`, ...) is unchanged;
this task has its own split, seed, prompt, and study id.

## What the agent gets

The minimal protocol: an empty product repository, the short behavioral
contract in [task.md](task.md) as the only initial message (language, build
and invocation commands substituted from the adapter), blank `AGENTS.md` and
`TASK.md`, `Continue.` as the continuation, Pi's built-in tools, no benchmark
tests, scores, reference implementation, or status tool. The contract is the
same text for every language condition; it names behaviour only, not
architecture, and prohibits delegation to an existing compiler.

Conditions (`study.json`, one-factor-at-a-time on `candidate`):

| Condition | Candidate adapter | Build gate |
|---|---|---|
| `rust` (baseline) | `studies/assets/candidates/rust-std.json` | `cargo build --release --offline` |
| `python` | `studies/assets/candidates/python-untyped.json` | `python3 -m py_compile`; type checkers withheld by the guard |
| `python-typed` | `studies/assets/candidates/python-typed.json` | `mypy --strict` (pinned in image 0.5) must pass; `# type: ignore` is an advisory audit finding |

The entry contract is the existing PiCC one: `<entry> INPUT.c -o OUTPUT.s`. The two Python arms differ only in the build gate and the guard; the contract text is identical apart from the language line and build command.

## Tests: selection and exclusions

Upstream corpus `nlsandler/writing-a-c-compiler-tests` at the same pinned
revision as the chapters 1-10 task (`TEST_REF`), split by
`scripts/split_tests.py --scope core-with-fixtures --max-stage 18` with seed
`C18_SPLIT_SEED=20260916` and the usual 70/30 family-grouped,
stage-and-validity-stratified policy. The exact selection is committed in
[selection.json](selection.json) (949 tests: 668 visible, 281 hidden) and
`make tests-c18` refuses partitions that differ from it.

Included, beyond the chapters 1-10 scope:

- **Multi-file library tests** (`valid/libraries/*`): each `.c` file is its
  own test, as upstream runs them. The candidate compiles the file under
  test; the partner half (`<name>_client.c` or `<name>.c`) is a fixture the
  evaluator compiles with GCC (`-D SUPPRESS_WARNINGS`) and links in. Both
  halves share one family, so they land in the same partition.
- **Assembly helpers** (`assembly_libs` in `test_properties.json`): the
  `*_linux.s` helper is a fixture assembled by GCC at link time.
- **Quoted-include headers** (`#include "x.h"`, chapter 18): copied next to
  the test as header fixtures so GCC's preprocessing of the candidate input
  and the reference build resolve them.
- **Math-library tests** (`requires_mathlib`): linked with `-lm` on both the
  reference and the candidate side (`link_flags`).

Excluded, with counts from the split summary:

- `extra_credit` directories (bitwise, compound assignment, increment,
  `goto`, `switch`, NaN, unions): 435 files under `excluded_directory`
  together with `helper_libs` (`nan.c`, used by extra credit only).
- Chapters 19-20 (optimization passes; no `valid`/`invalid` classification):
  246 files, `unclassified`.
- The `_osx.s` helper variants are never used (Linux image).

Assembly and linking stay evaluator-side; the candidate only ever sees one
preprocessed translation unit (`gcc -E -P -C -nostdinc`), never a fixture.

## Evaluation

`studies/runtime/evaluate.py` (the language-neutral C evaluator, copied into
each materialization with `candidate_runtime.py`) with the GCC behavioural
oracle: expected exit status and stdout come from GCC compiling the test with
its fixtures; the candidate's assembly is linked with the same fixtures. The
score is unchanged from the chapters 1-10 task: per stage the mean of the
valid-program and invalid-program pass rates, averaged over stages 1-18.
Invalid programs must be rejected with a diagnostic and no assembly file.

The fuzz oracle covers chapter 1-10 features only and is disabled for this
task (`FUZZ_STAGE_PROGRAMS=0` in the manifest), so the corpus macro is the
single primary endpoint. Reject-everything-with-a-diagnostic scores 0.5 on
this metric (as on the chapters 1-10 task); see the smoke results below.

## Commands

```bash
make tests-c18                                     # fetch + split + check against selection.json
make study-validate STUDY=studies/c18/study.json
make study-materialize STUDY=studies/c18/study.json CONDITION=rust RUN_ID=inspect-c18
make study-run STUDY=studies/c18/study.json CONDITION=rust PROFILE=main RUN_ID=c18-rust-r1 REPLICATE=1
make study-hidden-all RUN_ID=c18-rust-r1
make study-report RUN_ID=c18-rust-r1
make study-summary STUDY=studies/c18/study.json    # -> runs/study-results/picc-c18-minimal-v1/
make tasks-smoke                                   # evaluator smoke in the pinned image (Docker)
```

## Evaluator verification (host GCC 13, 2026-09-16)

Evaluator-only candidates under `fixtures/` (they are test fixtures, not
admissible experiment candidates):

| Candidate | Hidden (281) | Visible (668) | Notes |
|---|---|---|---|
| `mock-picc-gcc` (delegates to `gcc -S -pedantic-errors -Werror -Wno-overflow`) | 0.9980 (280/281; invalid 140/140) | 0.9948 (665/668; invalid 323/323) | the 4 misses are GCC warnings-as-errors on valid programs (pointer/int casts, pointer compare, `sizeof` array argument) |
| `mock-picc-reject` (rejects everything with a diagnostic) | 0.5000 | – | property of the macro metric |
| `mock-picc-constant` (always emits `main` returning 0) | 0.2129 | – | 140 `unexpected_accept`, 56 `wrong_behavior`, 17 link failures |

All 117 fixture-bearing tests pass with the GCC-backed candidate except the
two `-Werror` overflow cases before `-Wno-overflow` was added.
