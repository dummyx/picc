# Studies and tasks

A **study** is a file, `study.json`, that lists **conditions**: variants of
one setup that differ in one respect (the language, the prompt, access to
tests). Every run is one condition of one study; the harness runs nothing
that a study does not describe. `scripts/study.py` reads these files.

This folder is organized by task:

| Folder | What is in it |
|---|---|
| [`c10/`](c10/README.md) | **C compiler, chapters 1-10** (the original task): its page, its four specifications, its prompts, the language settings only it uses, a starting scaffold, and its five studies |
| [`c18/`](c18/README.md) | **C compiler, chapters 1-18**: its page, task description, pinned test selection, its Python language settings, and its study |
| [`sql/`](sql/README.md) | **SQL engine**: its page, task description, pinned test selection, its language settings, and its study |
| [`shared/`](shared/) | Used by more than one task: the minimal-protocol prompts (all three tasks) and the plain Rust settings (both compilers) |
| [`runtime/`](runtime/) | The scorers and the agent add-on templates copied into every run |
| [`moved.json`](moved.json) | Where every file moved when this folder was organized by task on 2026-09-24. Runs made before then record the old locations; the study summary and the dashboard translate them through this list, so those runs still count |

## The tasks

A condition's `task` block picks its task; a condition without one is the
chapters 1-10 compiler. The block names the scorer (`runtime`) and the number
of stages, and caps the budget's stage settings.

| Task id | What it is | Stages | Test partitions (fetched by) | Scorer copied into the run |
|---|---|---:|---|---|
| `c-compiler-ch1-10` | C compiler, chapters 1-10 of *Writing a C Compiler* ([c10/README.md](c10/README.md)) | 10 | `data/partitions/` (`make tests`) | [`runtime/evaluate.py`](runtime/evaluate.py), with the random-program check ([`runtime/fuzz_evaluate.py`](runtime/fuzz_evaluate.py)) after the run |
| `c-compiler-ch1-18` | the same, chapters 1-18 ([c18/README.md](c18/README.md)) | 18 | `data/partitions-c18/` (`make tests-c18`), pinned by [`c18/selection.json`](c18/selection.json) | `runtime/evaluate.py`; random-program check off |
| `sql-engine-sqllogictest` | SQLite-compatible SQL engine ([sql/README.md](sql/README.md)) | 8 | `data/partitions-sql/` (`make tests-sql`), pinned by [`sql/selection-record.json`](sql/selection-record.json) | [`runtime/sql/evaluate.py`](runtime/sql/evaluate.py) |

All three share [`runtime/candidate_runtime.py`](runtime/candidate_runtime.py):
building the agent's program, the source rules, and running it under time
limits. A test partition is split once, with a fixed seed, into the part
the agent may see and the hidden part it is scored on; both newer tasks'
fetch scripts refuse a split that differs from the committed selection.

## The studies

| Study file | Task | Conditions | Study ids so far, and the batches that used them |
|---|---|---|---|
| [`c10/starter/study.json`](c10/starter/study.json) | C compiler, ch. 1-10 | `baseline` and one-change variants: `workflow-reduced` (called `prompt-minimal` in v2), `spec-brief`, `spec-architecture`, `spec-inline`, `tests-none`, `tests-aggregate`, `tests-files`, `tests-quarter`, `language-python`, `scaffold-rust`, `reference-oracle` | `picc-essential-v1`: the early trial runs, v2, v3 |
| [`c10/types/study.json`](c10/types/study.json) | C compiler, ch. 1-10 | `js-untyped` (baseline), `ts-strict` | `picc-types-v1`: v4; `picc-types-v2`: v7 |
| [`c10/tests/study.json`](c10/tests/study.json) | C compiler, ch. 1-10 | `baseline`, `tests-none`, `tests-pushed` | `picc-tests-v2`: v5; `-v3`: v6; `-v4`: v8 |
| [`c10/spectests/study.json`](c10/spectests/study.json) | C compiler, ch. 1-10 | `baseline`, `spec-minimal`, `tests-none`, `spec-minimal-tests-none` (every combination of two changes) | `picc-spectests-v1`: v9 |
| [`c10/minimal/study.json`](c10/minimal/README.md) | C compiler, ch. 1-10 | `minimal` | `picc-minimal-v1`: never used in a batch |
| [`c18/study.json`](c18/README.md) | C compiler, ch. 1-18 | `rust` (baseline), `python`, `python-typed` | `picc-c18-minimal-v1`: v10; `-v2`: a v11 trial run; `-v3`: never run; `-v4`: v18 (stopped before this task); `-v5`: v19, current |
| [`sql/study.json`](sql/README.md) | SQL engine | `rust` (baseline), `python`, `python-typed`, `javascript`, `typescript` | `picc-sql-minimal-v1`: v10; `-v2`: v11; `-v3`: v12, v13 and the probe runs; `-v4`: v14; `-v5`: v15; `-v6`: v16; `-v7`: v17; `-v8`: v18, stopped after 6 runs; `-v9`: v19, current (run on `rust`, `python`, `python-typed`) |

**Why the id changes.** `make study-summary` includes a run only if the run's
study id is the file's current id *and* the condition frozen into the run
equals the condition in the file today (after translating moved files through
`moved.json`). Editing a condition in place would therefore drop every
earlier run from its summary without a word. So any change that touches a
condition gets a new id. The earlier batches' summaries stay in
`runs/study-results/<old-id>/`, and the file as it was is in git history. (A
study's `description` is only a label and can be edited.) To move a file a
study uses, add the move to `moved.json`; `tests/test_moved_paths.py` checks
that every move is complete and that no study still names an old location.

`minimal` and `spec-minimal` are different things. The `minimal` study
strips everything the harness adds: blank `AGENTS.md` and `TASK.md`, one
short request, Pi's built-in tools only, no tests, scores or status tool
([c10/minimal/README.md](c10/minimal/README.md)). The `spec-minimal`
condition of `spectests` keeps the starter's workflow, prompts and tools and
shortens only the specification ([`c10/specs/minimal.md`](c10/specs/minimal.md)).
The chapters 1-18 and SQL studies use the minimal protocol
([`shared/minimal-protocol/`](shared/minimal-protocol/)).

## What a condition sets

A condition is the study's `defaults` with the condition's own entries
merged over them. Its parts:

- `prompt`: the files that become `AGENTS.md`, the first message and the
  message sent at the start of every later round (a task's `prompts/`, or
  `shared/minimal-protocol/`), and
  whether the agent gets the experiment tools (`test_visible`,
  `experiment_status`, `reference_oracle`).
- `specification`: the task description (`c10/specs/`, or a task's own
  `task.md`), where it is delivered (`TASK.md`, the first message, or
  `SPEC.md` in the workspace), and a record of how it was written.
- `tests`: whether the agent can run the visible tests (`none`, through the
  `tool`, or as readable `files`), how detailed the feedback is, what share
  of the visible tests it gets, and whether reports are pushed to it every
  few minutes.
- `candidate`: the language settings file (a task's `candidates/*.json`, or
  `shared/candidates/`: build
  and run commands, which files are its source, what the source may not
  use, which shell commands the agent may not run) and an optional starting
  scaffold (`c10/scaffolds/`).
- `reference`: nothing, a black-box reference compiler with a call limit,
  or readable reference source (C tasks only).
- `environment` and `budget`: overrides of `config/defaults.env` (never
  secrets) and of the time, round and stage limits.
- `task`: the task, above.

`scripts/study.py validate` checks all of it, including that a
one-change study really changes one part per condition and that a
two-factor study contains every combination exactly once.

## One step at a time

`make experiment` runs a whole batch (see the [front page](../README.md)).
Its steps, separately:

```bash
make study-validate STUDY=studies/sql/study.json     # check the file, list conditions
make study-schedule STUDY=studies/sql/study.json REPLICATES=3 PROFILE=main
make study-materialize STUDY=studies/sql/study.json CONDITION=rust RUN_ID=inspect-sql-rust
make study-run STUDY=studies/sql/study.json CONDITION=rust PROFILE=main RUN_ID=v18-sql-rust-r1 REPLICATE=1
make study-hidden-all RUN_ID=v18-sql-rust-r1          # score every saved version on the hidden tests
make study-report RUN_ID=v18-sql-rust-r1              # runs/<id>/report.md
make study-summary STUDY=studies/sql/study.json       # runs/study-results/<study-id>/
make study-resume RUN_ID=...                          # continue a run that stopped early
```

`PROFILE=pilot` is a short trial run that never counts. `study-materialize`
builds a condition's frozen copy without starting the agent, for
inspection. `study-resume` works only for a run that stopped on a round time
limit or a Pi failure, before it was scored, and marks the run as not
comparable (see [docs/EXPERIMENT_PROTOCOL.md](../docs/EXPERIMENT_PROTOCOL.md)).

## What a run's frozen copy holds

`runs/.study-materializations/<run-id>/`:

- `config/`, `docker/`, `scripts/`, `pi/` and `VERSION`, copied from the
  repository; `config/defaults.env` ends with the effective configuration
  frozen for the run;
- `prompts/`: the rendered `AGENTS.md`, `TASK.md`, `INITIAL.txt` and
  `CONTINUE.txt`;
- `evaluator/`: the task's scorer, `candidate.json` (the language settings)
  and `task.json`;
- `pi/extensions/`: the rendered rule checker (`experiment-guard.ts`), the
  experiment tools and setup extension when the condition has them, and the
  two repair extensions;
- `data/partitions/{visible,hidden}/` and `data/agent-visible/` (what the
  agent may read);
- `study-materialization.json`, the record of all of the above, and a
  `runs` link back to the real `runs/`.

`run`, `resume`, `evaluate` and `report` execute this copy's scripts, never
the repository's; the repository's `run_experiment.py`, `evaluate_run.py`
and `summarize_run.py` refuse to run outside such a copy. When a run ends,
`runs/<run-id>/study-metadata.json` and `study-control/` keep a second copy of
the record, the rendered prompts, the language settings and the test
manifests.

## Which runs a summary includes

Only runs with the `main` profile that finished without interruption, were
never resumed, have a positive replicate number, match the current
condition and the study's recorded configuration, and have hidden scores for
every saved version, with per-run reports that agree with their ledgers.
Every other run is listed with the reason it was left out. A difference in
the model, the container image or the number of hidden tests between
included runs stops the summary with an error, as does a condition and
replicate that appears twice. A missing condition or replicate is a warning.
Field definitions are in
[docs/STUDY_DATA_DICTIONARY.md](../docs/STUDY_DATA_DICTIONARY.md).

## Adding a condition

Add an entry to `conditions`, give it a `factor` that names the part it
changes, and give the study a new `id` if any existing condition changes.
Paths are relative to the repository; a file only one task uses goes in that
task's folder, a file several tasks use in `shared/`. For example, a
condition exposing a
reference implementation's source (the path is an example, not a file in
this repository):

```json
{
  "id": "reference-source",
  "factor": "reference",
  "reference": {
    "mode": "source",
    "oracle_limit": 0,
    "source": "studies/c10/references/my-reference"
  }
}
```

Or a specification written by a model rather than a person, with a truthful
record of how it was made (again an example path):

```json
{
  "id": "spec-llm-a",
  "factor": "specification",
  "specification": {
    "path": "studies/c10/specs/llm-a.md",
    "delivery": "task_file",
    "provenance": {
      "method": "llm-generated-human-reviewed",
      "creator": "researcher",
      "generation_model": "frozen-model-id",
      "source": "frozen-generation-prompt-hash",
      "artifact_family": "coverage-matched-spec-set-1",
      "reviewed_by": "reviewer-id"
    }
  }
}
```

One document per method shows nothing about the method: compare several
documents made each way, each covering the same ground.

## Limits of the isolation

With `tests.access` set to `none` the agent's test folder is empty. Whether
it may read test files or only run them through the tool is enforced by the
rule checker in the agent's container, which is enough for an agent that is
not trying to cheat, not a hard boundary. After the run, the agent's program
is built and run in the same scoring container as the test partition it is
scored on; hidden scores are valid for programs that follow the rules, and
every artifact is kept for checking, not made tamper-proof.

The source rules apply to the program actually submitted: for Rust, the
Cargo package's `src/` plus any file it includes by path; for JavaScript and
TypeScript, the language settings' source folders plus everything the entry
module imports; for Python, since v10's second amendment, the entry module
and everything it imports. Test drivers and helpers the agent keeps
elsewhere are not checked (the v4 and v6 incidents,
[analysis/report.md](../analysis/report.md) §8.5 and §12). Links and
compiled binaries are refused everywhere.
