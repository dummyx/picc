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

## Analysis

`make study-summary STUDY=studies/sql/study.json`,
`make study-summary STUDY=studies/c18/study.json`, then
`python3 analysis/v19_results.py`.
