# Experiment plan: v18 (both newer tasks, three languages, on the settled setup)

Written before the first run. Harness commit: `80ec10b`.

**Stopped 2026-10-03 04:19Z after 6 of 18 runs** (all SQL: `python-typed-r1`
0.837, `rust-r1` 0.771, `python-r1` 0.595, `python-r2` 0.069, `rust-r2` 0.000,
`python-typed-r2` 0.000; the seventh, `rust-r3`, was killed one hour in).
Three of the six lost everything to the output contract rather than to SQL:
`rust-r2` reads standard input and ignores the named file, `python-typed-r2`
prints rows as `1|x` with no `ok N` line, `python-r2` prints a value where the
`ok N` line goes. The harness held (no reply cut off, no stream error, no failed
summary in 2,739 replies), but with 3 runs per language such zeros make the
comparison meaningless, as the v17 report had already said. The six runs are
summarized under `picc-sql-minimal-v8` (manifest kept as
`studies/sql/study-v8.json`) and are the record of the contract-failure rate
without a worked example. Continued as [v19](EXPERIMENT_PLAN_v19.md).

## Question

Two questions, the same ones v10 asked, on a harness that now holds:

1. How well does the agent build each of the two newer tasks, the SQL engine
   and the chapters 1-18 C compiler, from an empty repository in Rust, in
   Python, and in Python under `mypy --strict`?
2. On each task, does requiring type annotations and `mypy --strict` change
   the result?

v10 ran exactly this design and lost 10 of its 18 runs to four harness
defects. The SQL half was run again in v17 (15 runs, nothing broke). The
chapters 1-18 half has not been run since v10, and never on the current
model server.

## What every run gets: the full specification and the minimal prompt

Unchanged from v10-v17, and the same for every language:

- **The specification** is the task's one specification text, sent whole as
  the first message: `studies/sql/task.md` (output format, how values print,
  the whole SQL subset, error rules) and `studies/c18/task.md` (every type and
  construct, the calling convention, when to reject a program). Only the
  language line and the build and run commands differ between languages.
- **The minimal prompt**: `AGENTS.md` is empty, `TASK.md` is empty, every
  later round gets the one word `Continue.`, and the agent has Pi's seven
  built-in tools and nothing else: no tests, scores, status or reference tool.

**Checked on the wire before this batch.** A defect of this kind has happened
before: in v2 the reduced-prompt variant replaced only `AGENTS.md` while the
first and per-round messages re-sent every instruction it had removed (report
section 3.4). So the requests of one trial run per task were recorded by a
relay that forwards them unchanged to the model server
(`v18-capture-sql-python`, `v18-capture-c18-rust`; see "Trial runs" below).
Every request carried one system message, Pi's own built-in text with its
seven tools and an empty `AGENTS.md` block, and the task specification as the
first user message. No request contained the starter study's working rules,
its longer round messages, another specification, or an experiment tool.

## What changed since v17, all of it verified before this batch

1. **The repository was reorganized** (2026-09-24): one folder per task under
   `studies/`, the harness scripts regrouped. A frozen copy made today has the
   same prompts, scorer, Pi settings and test data, byte for byte, as the one
   `v17-sql-python-r1` ran from. The run loop was restructured but not
   changed in behaviour; the trial runs below are its first real runs.
2. **The rule checker reads commands, not pasted text.** v17 report section
   11, item 1: it blocked 4 legitimate commands in 3 runs because words inside
   code being written to a file looked like forbidden commands. Rules about
   which commands run now read the command as the shell will run it: quoted
   text and here-documents handed to other programs are left out, text handed
   to a shell is kept. Rules about text anywhere (a URL, an import of a
   database module) are unchanged.
   The same change makes every line of a command count. Before it, only the
   first line of a multi-line command was at the start of a command, so a
   forbidden command on a later line ran unblocked.
   Checked against all 4,071 shell commands of the 15 v17 runs and the 9 v10
   chapters 1-18 runs: 4,054 decisions unchanged; 4 no longer blocked, exactly
   the four mistakes; 13 newly blocked, all of them direct uses of `gcc` on a
   later line, in three v10 chapters 1-18 runs (`v10-c18-python-typed-r1` ten
   times, `-r2` twice, `-r3` once). **In v10 the chapters 1-18 agents could
   and did use GCC as a reference; in this batch they cannot.** No v17 SQL
   decision changes other than the four mistakes.
3. **The scorer keeps the error line of a crash.** v17 report section 11,
   item 2: it kept only the start of a program's error output, which for a
   Python traceback loses the line that names the error. It now keeps both
   ends. Scores are not affected; only the stored detail text is.
4. **A batch can schedule some of a study's conditions**
   (`study.py schedule --conditions`, `make experiment CONDITIONS=...`). The
   SQL study lists five languages and this batch runs three. The order is the
   full schedule's order with the others left out.

Server, model, sampling, reasoning budget, context and compaction settings,
image and budgets are v17's, unchanged: SGLang 0.5.20 serving
`RadixArk/Qwen3.8-27B-NVFP4` (every file checked against the Hub's hashes
again on 2026-10-02), `LOCAL_THINKING_BUDGET=8192`, image
`picc-experiment:0.5`.

## Design

- Studies `studies/sql/study.json`, manifest `picc-sql-minimal-v8`, and
  `studies/c18/study.json`, manifest `picc-c18-minimal-v4`. New ids, so these
  runs can never be pooled with v17's (`-v7`) or v10's (`-v1`). No condition
  changed.
- Conditions on each task: `rust`, `python`, `python-typed`. The SQL study's
  `javascript` and `typescript` are not run in this batch.
- Three replicates each, 18 runs, `PROFILE=main`: 2 h agent time, 30 rounds,
  45-minute round cap. About 40 hours.
- The SQL study runs first, then chapters 1-18, each in the order
  `study.py schedule` gives; run ids `v18-sql-<condition>-r<n>` and
  `v18-c18-<condition>-r<n>`.
- Launched with `scripts/start_experiment.sh` once per study, which verifies
  the endpoint and measures that the reasoning budget is enforced before the
  first run, and may relaunch the pinned server once if it dies between runs.

## Endpoints

v17's, applied to each task separately.

1. **Produced a working program**: the run's final hidden score is above the
   task's constant-output floor (SQL 0.0503, chapters 1-18 0.2129) and, on
   the compiler task, at least one valid test program compiles and runs
   correctly. The second part is needed because a compiler that rejects every
   program scores 0.5 on that task's metric. A count per language.
2. **Hidden score among runs that did**, `python-typed` against `python`,
   paired by replicate.

Secondary: writes, cut-off rate, rounds used, termination reason, the
commands the rule checker blocked (by reason), and reasoning tokens per reply
from `analysis/reasoning_tokens.py`.

## Validity gate

v17's. A run is not comparable if any reply ended in a stream error or any
compaction failed. If either appears, the batch is stopped and the defect
fixed, not analyzed around. `analysis/v18_results.py` reports both per run.

## Decision rule, fixed before the data

Per task. On endpoint 1: report the counts. With three replicates a
difference of 3 to 0 is worth stating and anything smaller is not.

On endpoint 2, among replicates where both Python arms produced a working
program:

- **Typing helps** if the paired median hidden score of `python-typed`
  exceeds `python` by at least 0.13, the threshold used since v4.
- **Typing hurts** if it falls short by at least 0.13.
- **No effect detected** otherwise.
- **Not measurable** if fewer than two replicates have both arms working.

At three replicates this is descriptive, not a test. v17's Python arms spanned
0.134 to 0.851 within one condition, so the expected outcome is again a
measurement of the spread, and the write-up leads with the spread. `rust` is
the reference arm and carries no hypothesis.

**Comparing with earlier batches.** SQL: v17 is the comparison (same task,
same settings; the rule checker differs only in the four mistaken blocks).
Chapters 1-18: v10 is not a clean comparison. Its harness had four defects,
it ran on llama.cpp without a reasoning budget, and its agents could use GCC.

## Exclusions

Pilots (the two trial runs below), resumed runs, and any run whose frozen
condition does not match the manifest.

## Trial runs

Two runs on the pilot profile (0.4 h, two 12-minute rounds), 2026-10-02, on the
pinned server through `make study-run`. Each went through a relay on loopback
that forwards every request unchanged to the model server and saves it, which
is how the requests were read. They are excluded from every analysis.

| run | replies | file writes | cut off | stream errors | requests recorded | commands blocked | hidden score |
|---|---:|---:|---:|---:|---:|---:|---:|
| `v18-capture-sql-python` | 9 | 4 | 0 | 0 | 11 | 0 | 0.019 |
| `v18-capture-c18-rust` | 19 | 11 | 0 | 0 | 21 | 2 | 0.000 |

- **The whole path works after the reorganization**: both repair extensions
  loaded, each round was saved and scored on the visible tests, every saved
  version was scored on the hidden tests afterwards, and the report was
  written. These were the first real runs of the restructured run loop.
- **The requests are the minimal prompt and the one specification.** In all
  32 requests the system message was the same 376 words of Pi's own text
  (identical for the two tasks), the first user message was the task
  specification (419 words for SQL in Python, 268 for the compiler in Rust),
  every later round's message was `Continue.`, the tools were Pi's seven, and
  the sampling settings and the 8,192-token reasoning budget were on every
  request.
- **Both commands the rule checker blocked were real**: `gcc --version` and
  `ls /run-artifacts`, in the compiler run.
- **The scores say nothing about the batch.** Twenty-four minutes is not
  enough for either program: the SQL run ended with a 2,130-line engine that
  crashes on some statements, the compiler run with 2,377 lines of Rust and a
  module not yet written. Earlier pilots ended the same way.
- Neither run was long enough to need a conversation summary. That path is
  unchanged since v17, where 259 of 259 summaries succeeded.
- `v18-capture-sql-python` was started before the scorer change and the new
  study ids were written, so it carries the old scorer and the id
  `picc-sql-minimal-v7`. `v18-capture-c18-rust` ran on the files of the
  harness commit above.

## Analysis

`make study-summary STUDY=studies/sql/study.json`,
`make study-summary STUDY=studies/c18/study.json`, then
`python3 analysis/v18_results.py`, then
`.venv-sglang/bin/python analysis/reasoning_tokens.py <run ids>`.
