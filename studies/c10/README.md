# C compiler task, chapters 1-10 (the original task)

PiCC: a compiler for the core of chapters 1-10 of *Writing a C Compiler*
(return values, unary and binary operators, logical and relational operators,
local variables, `if` and conditional expressions, compound statements,
loops, functions, and file-scope variables with storage classes). It reads
one C file and writes x86-64 assembly:

```text
<compiler> INPUT.c -o OUTPUT.s
```

This was the project's first task. The early trial runs and batches v2-v9
used it; what each batch found is in [docs/README.md](../../docs/README.md)
and [analysis/report.md](../../analysis/report.md) §1-15.

## Where its files are

| What | Where |
|---|---|
| The specification, four versions: detailed (the baseline, `behavioral.md`), brief, with architecture guidance, and minimal (143 words) | [specs/](specs/) |
| The prompts: `AGENTS.md`, the first message and the message at the start of each later round, plus the "workflow-reduced" versions | [prompts/](prompts/) |
| Language settings used only by this task: JavaScript, TypeScript under `tsc --strict`, Python, Rust with a starting scaffold | [candidates/](candidates/) |
| Plain Rust settings, shared with the chapters 1-18 task | [../shared/candidates/rust-std.json](../shared/candidates/rust-std.json) |
| The starting code for the `scaffold-rust` variant | [scaffolds/rust-pipeline/](scaffolds/rust-pipeline/) |
| The five studies that ran it | [starter/](starter/study.json), [tests/](tests/study.json), [types/](types/study.json), [spectests/](spectests/study.json), [minimal/](minimal/README.md) |
| The tests | `data/partitions/` (not in git), made by `make tests` |
| The scorer | [../runtime/evaluate.py](../runtime/evaluate.py), with the random-program check in [../runtime/fuzz_evaluate.py](../runtime/fuzz_evaluate.py) |

## The five studies

| Study | What it compares | Study ids, and the batches that used them |
|---|---|---|
| `starter/` | the baseline against eleven variants that each change one thing: shorter workflow instructions, a brief or an architecture-heavy specification, the specification in the first message, no tests, less feedback, readable test files, a quarter of the tests, Python, a starting scaffold, a black-box reference compiler | `picc-essential-v1`: the early trial runs, v2, v3 |
| `tests/` | the baseline against tests withheld, and (v8) test reports sent unasked every 10 minutes | `picc-tests-v2`: v5; `-v3`: v6; `-v4`: v8 |
| `types/` | TypeScript under `tsc --strict` against plain JavaScript | `picc-types-v1`: v4; `-v2`: v7 |
| `spectests/` | the minimal specification crossed with tests withheld, all four combinations | `picc-spectests-v1`: v9 |
| `minimal/` | the minimal protocol: blank `AGENTS.md`, one short request, Pi's own tools only | `picc-minimal-v1`: never used in a batch |

Its short request (`minimal/task.md`) is this task's; the three prompt files
of the minimal protocol are shared with the other two tasks
([../shared/minimal-protocol/](../shared/minimal-protocol/)).

## Tests and scoring

The tests are the upstream `nlsandler/writing-a-c-compiler-tests` suite at
`TEST_REF` (`ae12014d2dec14488f3f80d14df4b6d8e4634d7d`), stages 1-10, the
standalone core only: extra credit, multi-file library tests, helper and
assembly libraries, and tests needing the maths library are left out. The
split is 70% visible and 30% hidden, grouped by test family and balanced by
stage and by valid/invalid (`SPLIT_SEED=20260810`): 227 visible and 104
hidden tests.

- **Hidden tests.** A valid program is compiled by the agent's compiler,
  assembled and linked by GCC, and run; its exit status and output must match
  GCC's own build of it. An invalid program must be rejected with a nonzero
  exit status and an error message, leaving no assembly file. Per stage the
  valid and invalid pass rates are averaged, then the stages are averaged.
  Since v5 every test is handed to the agent's compiler after the C
  preprocessor (`gcc -E -P -C -nostdinc`).
- **Random programs.** Since v5 the final version is also checked on 100
  generated programs per stage against GCC (`FUZZ_*` settings in
  `config/defaults.env`), and since v8 so is the last version that built when
  it differs. The v2-v4 finals were re-scored this way afterwards
  ([analysis/fuzz-rescore.md](../../analysis/fuzz-rescore.md)).

The v2 batch used the trial profile, stages 1-6; from v3 on, main runs had
stages 1-10 and 2 hours of agent time.

## Commands

```bash
make tests                                                 # fetch the pinned suite and split it
make study-validate STUDY=studies/c10/starter/study.json
make study-run STUDY=studies/c10/tests/study.json CONDITION=tests-none PROFILE=main RUN_ID=v18-tests-none-r1 REPLICATE=1
make study-summary STUDY=studies/c10/tests/study.json      # -> runs/study-results/picc-tests-v4/
make evaluator-smoke                                       # the scorer and the random-program check, in the container
```
