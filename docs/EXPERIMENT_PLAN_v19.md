# Experiment plan: v19 (v18 again, with a contract the agent can check)

Written before the first run. Harness commit: `54f52a6`. Everything
not stated here is as in [v18](EXPERIMENT_PLAN_v18.md): the same two tasks,
the same three languages, three replicates each, the same budgets, server,
model, endpoints, validity gate, decision rule and exclusions.

## Why v18 was stopped

Six SQL runs in, three had scored 0 on the hidden tests for reasons that have
nothing to do with the language: `rust-r2` read standard input and ignored
the file name it was given; `python-typed-r2` printed rows as `1|x` with no
`ok N` line and nothing for `CREATE TABLE` or `INSERT`; `python-r2` printed a
value where the `ok N` line goes. All three engines otherwise worked. The v17
report had named this exact failure ("scores are decided by a few
all-or-nothing mistakes ... the agents cannot see these mistakes") and v18 ran
the same design regardless. With three runs per language, one such zero per
arm leaves nothing to compare. The six runs are kept as `picc-sql-minimal-v8`
and summarized in the v18 plan.

## What changes, and why each is a design fix rather than a patch

The cause is that the output contract was stated in prose only, in a message
the agent sees once, and nothing lets the agent check its reading of it.

1. **A worked example in each specification.** For SQL, an input file of
   seven statements and the exact output they must produce (`ok 0` for
   `CREATE TABLE` and `INSERT`, rows with one tab between values, `NULL`,
   `3.0`, an `error` line), verified against the evaluator's own
   reference-backed engine. For the compiler, one valid program (exit status
   5 after assembling and linking) and one invalid program (nonzero exit, a
   diagnostic, no output file), verified against GCC.
2. **The input rule stated outright.** The program is started with the one
   file name, reads nothing from standard input, and (compiler) writes only
   the named output file. Every v17 and v18 contract zero violated one of
   these.
3. **The specification stays in view.** It is the first message, as before,
   and also `AGENTS.md`, which Pi puts into every request. Before, a run's
   first conversation summary (after about 6 minutes; v17 runs had 16 of
   them) reduced the 400-word subset list to one paraphrased line and the
   agent worked the remaining 110 minutes from memory. `AGENTS.md` carries
   nothing but the specification; `TASK.md` stays empty and every later round
   is still `Continue.`
4. **The deadline rule stated.** "The repository is scored exactly as it
   stands when a fixed time budget ends (two hours for a full run), in
   whatever state it is in, so keep the program building and behaving
   correctly at all times." A snapshot taken mid-edit scored 0 in v17
   (`python-r2` round 1) and v18 (`python-r2` round 1); the agent did not
   know there was a clock.

The text is the same for all three languages apart from the language line
and the build and run commands, so the comparison stays one-factor. Both
study files have new ids, `picc-sql-minimal-v9` and `picc-c18-minimal-v5`;
the specification provenance records the change.

**Checked before the batch:** `make validate` (297 tests, including one that
pins `AGENTS.md` equal to the first message, `TASK.md` empty, the round
message `Continue.`, and the example present), the SQL example's output
reproduced by the reference engine byte for byte, the compiler example's two
programs run through GCC, and a frozen copy of each task inspected.

## What this batch can and cannot show

Endpoint 1 (produced a working program) now has a second reading: a run that
still fails the contract with the example in front of it is a finding about
the agent, not a gap in the specification. `analysis/v19_results.py` counts,
per run, the hidden scripts lost to the output contract.

Three replicates per language remain three. v17's Python arms spanned 0.134
to 0.851 within one condition; if the contract zeros were most of that
spread, this batch will show it, and if not, the typing question stays
descriptive at this size.

## Runs

Run ids `v19-sql-<condition>-r<n>` then `v19-c18-<condition>-r<n>`, launched
by `runs/v19-chain.sh` the way v18 was. About 40 hours.

## Amendment 1, 2026-10-03 19:14Z: where the commands run

Found after run 7 of 18 (`v19-sql-rust-r3`) had put its crate in
`/workspace/pisql/`: `cargo build --release --offline` runs in `/workspace`
and found no `Cargo.toml`, so every snapshot scored 0 while the engine itself
was being built normally (4,836 lines of Rust). Nothing in the specification
said where the build and run commands execute. The same gap exists for the
compiler task. One sentence was added to both specifications before run 8 was
set up: "Both commands are run from `/workspace` itself, so the project root
is `/workspace`, not a subdirectory of it, and the paths they name are
relative to `/workspace`." Harness commit `3569f27`.

How this is handled, decided before any run 8 data:

- Runs 1-7 ran without the sentence; runs 8-18 run with it. Runs 1-6 all
  placed their files at the root, so the sentence could not have changed what
  they built; `v19-sql-rust-r3` is reported as it is, 0, with this cause.
- The study ids do not change (the condition objects are unchanged; only the
  specification text grew by one sentence), so the summary includes both
  groups. `analysis/v19_results.py` marks each run with whether its frozen
  specification carries the sentence, and the write-up reports the Rust arm
  both with and without `rust-r3`.
- The decision rule is unchanged. Whether to pool the two groups is a
  judgement the report must make openly; the alternative, stopping and
  discarding six good runs (14 hours) to restart with the sentence, was not
  taken because the sentence cannot have affected those six.

## Amendment 2, 2026-10-04: the full prompt against the minimal prompt

Added at the project owner's direction after the SQL half had reported. The
batch so far varies only the language; every run has the minimal prompt. This
adds the other arm of a prompt comparison: `rust-full-prompt`, Rust with the
original task's working rules (`studies/shared/full-protocol/`: the twelve
rules in `AGENTS.md` ahead of the same specification, the longer first
message, the longer per-round message in place of `Continue.`). Everything
else is `rust`'s. Defined for both tasks; run first as one SQL run,
`v19-sql-rust-full-prompt-r1`, queued behind the compiler runs, with more
replicates or the compiler task addable the same way
(`start_experiment.sh --single --condition rust-full-prompt --replicate N`).

**Decision rule, fixed before its first run:** `rust-full-prompt` minus
`rust`, paired by replicate, on the hidden score among pairs where both arms
produced a working program; the same ±0.13 line. One replicate is a reading,
not a measurement; the write-up says so. The arm is not blind to v19's
numbers and is reported as its own contrast, never pooled.

## Analysis

`make study-summary STUDY=studies/sql/study.json`,
`make study-summary STUDY=studies/c18/study.json`, then
`python3 analysis/v19_results.py`.
