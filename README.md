# PiCC

An experiment on what changes the software an AI coding agent builds.

One agent (the [Pi coding agent](https://github.com/earendil-works/pi),
running a Qwen3.8-27B model on this machine) is given an empty folder and a
task, and works alone for a fixed time, in rounds. After every round the
harness saves its folder and scores it; at the end, every saved version is
scored on tests the agent never saw. Each batch of runs changes one thing
(the language, the prompt, the specification, access to tests) and repeats
each variant a few times, to see whether that one thing changes the result.

## The three tasks

| Task | What the agent builds | How it is scored | Defined in | Batches |
|---|---|---|---|---|
| C compiler, chapters 1–10 (the original task) | a compiler for a small part of C that writes x86-64 assembly | the hidden part of the *Writing a C Compiler* test suite, plus programs generated at random and checked against GCC | [`studies/c10/`](studies/c10/README.md) (five studies) | v2–v9 |
| C compiler, chapters 1–18 | the same, with much more of C: more integer types, floating point, pointers, arrays, strings, structures | 281 hidden tests from the same suite | [`studies/c18/`](studies/c18/README.md) | v10 |
| SQL engine | an in-memory database whose answers must match SQLite's on a set part of SQL | 8 hidden test scripts from SQLite's own test suite (51,939 checks) | [`studies/sql/`](studies/sql/README.md) | v10–v17 |

Scores run from 0 to 1. A run's score is its last saved version's score on
the hidden tests; since v8, batches also report the last version that built,
in case time ran out halfway through a rewrite.

## What has been found so far

- **On the original task, none of the things varied changed how correct the
  compiler was:** prompts, how detailed the specification is, whether the
  agent could see tests, test reports sent to it unasked, and static
  typing. They changed how the agent worked instead: how much it wrote, how
  many tests it wrote for itself, how many tokens it used. The unchanged
  setup reaches about 0.93–0.97 in about 90 minutes of work, whatever the
  agent is told.
- **Most apparent effects came from problems in the experiment itself.**
  Examples: agents stuck for the rest of a round on a command that never
  returned (fixed by giving every shell command a 2-minute limit unless the
  agent sets its own), and conversation summaries too large for the model
  (fixed by [`pi/extensions/compaction-bound.ts`](pi/extensions/compaction-bound.ts)).
  Each was recorded and fixed before the next batch.
- **The two newer tasks leave room to improve.** The best scores so far are
  0.501 on the chapters 1–18 compiler (v10) and 0.851 on the SQL engine
  (v17).
- **Whether strict type checking helps or hurts is still unanswered.** In
  v17 the runs of one language differ from each other more than the
  languages differ from each other.

Every batch, with what it compared and what it found, is listed in
[docs/README.md](docs/README.md). The full write-up is
[analysis/report.md](analysis/report.md); the latest report is
[docs/REPORT_2026-09-23.md](docs/REPORT_2026-09-23.md).

## Where things are

| Folder | What is in it |
|---|---|
| [`scripts/`](scripts/) | The harness: runs the agent round by round (`run_experiment.py`), scores saved versions (`evaluate_run.py`), writes each run's report (`summarize_run.py`), builds and runs the variants of a study (`study.py`), summarizes a study (`summarize_study.py`), and runs a whole batch unattended (`start_experiment.sh`, `chain_study.sh`) |
| [`scripts/model_server/`](scripts/model_server/) | Installing, downloading, starting and checking the model server |
| [`scripts/test_sets/`](scripts/test_sets/) | Downloading the three tasks' tests and splitting each into the part the agent may see and the hidden part |
| [`scripts/checks/`](scripts/checks/) | Checks of the project itself (`make validate` and the smoke tests that run in the container) |
| [`studies/`](studies/README.md) | One folder per task (`c10/`, `c18/`, `sql/`), each with its own page, task description, prompts, language settings and study files (`study.json`, listing the variants to compare); `shared/` for files several tasks use; the scorers (`studies/runtime/`) |
| [`pi/`](pi/) | The agent's settings, and the two add-ons that repair conversation problems |
| [`config/`](config/) | Every fixed setting: versions, time limits, how the tests are split, the model server's settings |
| [`docker/`](docker/) | The container the agent works in, and the script that builds it |
| `data/`, `runs/` | The downloaded tests and every run's records. Neither is in git |
| [`analysis/`](analysis/README.md) | Each batch's results script and results, the full write-up, and the [results dashboard](docs/DASHBOARD.md) |
| [`docs/`](docs/README.md) | Plans, reports, the rules of the experiment, and descriptions of every record |
| [`fixtures/`](fixtures/), [`tests/`](tests/) | Small fake programs used to check the scorers, and the project's own tests |

## How a run works

1. A study file lists the variants to compare: [`studies/sql/study.json`](studies/sql/study.json),
   for example, lists five languages.
2. For each run, the harness makes a frozen copy of itself with that
   variant's prompts, scorer and language settings
   (`runs/.study-materializations/<run-id>/`). The run only ever uses that
   copy, so later changes to the project cannot affect a run that exists.
3. The agent starts in an empty folder inside a locked-down container and
   works in rounds. A rule checker blocks downloads, calling an existing
   compiler or database, and writing outside its folder. After each round
   the harness saves the folder and scores it on the tests the agent is
   allowed to see.
4. A run stops when its time or its rounds run out, when its visible score
   reaches 1.0 (after one more round to review), or when the agent is stuck.
5. Afterwards every saved version is scored on the hidden tests, and
   `runs/<run-id>/report.md` is written.
6. `make study-summary` collects every eligible run of a study into
   `runs/study-results/<study-id>/`, and the batch's script in `analysis/`
   turns that into the batch's results.

The detailed rules are in [docs/EXPERIMENT_PROTOCOL.md](docs/EXPERIMENT_PROTOCOL.md)
(one run) and [docs/STUDY_PROTOCOL.md](docs/STUDY_PROTOCOL.md) (variants and
batches). What each recorded file holds is in
[docs/DATA_DICTIONARY.md](docs/DATA_DICTIONARY.md).

## Commands

Everything runs through `make`; `make -n <target>` shows what a target
would do. The host needs Docker, Git, Python 3.11 or later, and Make. The
harness's own Python code uses only the standard library; the model server
has its own environment.

```bash
# Once per machine
cp .env.example .env && chmod 600 .env   # then set the model and server address
make setup              # checks, the container, and the three tasks' test sets

# The model server (details: docs/INFERENCE_SGLANG.md)
make sglang-install                      # its own Python environment
scripts/model_server/fetch_model.sh      # download the pinned model
make sglang-start                        # also: sglang-status, sglang-stop
make preflight                           # the served model matches the settings

# A whole batch, unattended: starts the server if needed, checks it, runs
# every scheduled run with its hidden scoring and report, then the summary
make experiment STUDY=studies/sql/study.json PREFIX=v18 REPLICATES=3 PROFILE=main

# Results in a browser, on this machine only: http://localhost:8765
make dashboard-start

# The project's own checks
make validate           # no Docker needed
make evaluator-smoke tasks-smoke extensions-smoke   # in the container
```

The single steps of a batch (one run, its scoring, its report) are in
[studies/README.md](studies/README.md). `.env` holds the model server's
key: keep it private and never commit it.

## Rules that keep runs comparable

- Each batch's plan and results script are committed before its first run.
- Nothing about a running batch is changed. A problem found during a batch
  is recorded in its plan as an amendment and fixed for the next batch.
- Nobody talks to the agent during a run.
- Trial runs never count, and a run that had to be continued after
  stopping is reported separately.
- Scores corrected after a batch are kept beside the originals
  (`analysis/v<N>-rescore/`), never written over them.

## Limits worth knowing

- The C test suite is public and may be in the model's training data.
- Runs are not exactly repeatable: the model samples at random, so every
  repetition is a new attempt.
- The rule checker stops obvious misuse; it is not a security boundary.
- One model and three tasks: the results are about these tasks under this
  setup.

## Sources

- Pi coding agent: <https://github.com/earendil-works/pi>
- *Writing a C Compiler* tests: <https://github.com/nlsandler/writing-a-c-compiler-tests>
- sqllogictest (SQLite's SQL tests), mirror used: <https://github.com/gregrahn/sqllogictest>
- SGLang, the model server: <https://github.com/sgl-project/sglang>

The harness is MIT-licensed. The downloaded tests keep their own licenses,
copied to `data/UPSTREAM_TEST_LICENSE` and
`data/UPSTREAM_SQLLOGICTEST_COPYRIGHT.md`.
