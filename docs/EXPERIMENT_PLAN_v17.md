# Experiment plan: v17 (the batch v15 was meant to be)

Written before the first run. Harness commit: `238dab0`.

## Question

Unchanged from v15: does requiring type annotations and `mypy --strict` change
how well the agent builds an in-memory SQL engine from an empty repository?

v15 could not answer it. All three typed runs wrote nothing, and v16 found
why: the model's reasoning ran away. Counted with the checkpoint's own
tokenizer, the *median* typed reply in v15 reasoned 32,766 tokens against a
32,768-token output cap, so more than half of all replies were spent entirely
on thinking and contained no answer and no tool call. The same runaway replies
were in every v15 condition (13 in the python run that scored 0.856, 8 in the
rust run that scored 0.811); the typed condition had them worst.

## What changed since v15, all of it verified before this batch

1. **The model is served by SGLang** (0.5.20, `RadixArk/Qwen3.8-27B-NVFP4`,
   revision pinned and every file checked against the Hub's hashes) instead of
   llama.cpp on a Q4_K_XL GGUF. `docs/INFERENCE_SGLANG.md` has the
   configuration and its log; this batch runs on configuration #4.
2. **A budget on reasoning**, `LOCAL_THINKING_BUDGET=8192`, enforced by the
   server (`--enable-strict-thinking`). At the budget the server ends the
   reasoning and the reply continues with the output budget that remains,
   where the output cap alone ends the whole reply with nothing in it.
   Verified three ways: against the endpoint (no budget: 32,768 reasoning
   tokens, 0-character answer; budget: 8,193 tokens, 58,114-character answer);
   on `v16-sql-python-typed-r1` (99 writes, 0.0% cut off, hidden 0.8139,
   reasoning maximum exactly 8,192 with four replies at the budget and none
   over); and against the control `v16nb-sql-python-typed-r9`, identical but
   for the budget. When this plan was written the control was three rounds in
   and failing the v15 way -- no writes, 40% of replies cut off, reasoning to
   32,767 tokens, score 0.0 -- and its final result is recorded in
   `docs/EXPERIMENT_PLAN_v16.md`. The batch is launched when the control
   finishes, whichever way it ends, at the project owner's direction
   (2026-09-21). Should the control recover, the budget stays -- v16 r1 ran
   with it and scored 0.8139, so it is not harmful -- but the write-up must
   then say it was not shown to be necessary.
3. **`httpIdleTimeoutMs` raised to 1,800,000.** SGLang buffers a tool call
   instead of streaming it, so a long file write is silent for minutes and
   Pi's 300-second default killed it mid-call: 3 of 7 replies on the first
   SGLang run. Zero since.
4. **Scoring containers get 8 GB, not the agent's 16.** The agent never sees
   scores in this study, so this cannot change what it does; it stops a
   candidate with a runaway query from taking a host it shares with the
   model server.

The budget applies to every condition, not just the typed one. v17 is
therefore not comparable with v15 in *any* condition, and the manifest id
changes so the two can never be pooled.

## Design

- Study `studies/sql/study.json`, manifest `picc-sql-minimal-v7`. v6 holds
  the v16 probe and its control, which ran on earlier harness commits and must
  not count as replicates here.
- Conditions unchanged: `rust`, `python`, `python-typed`. The two Python arms
  differ only in the type gate.
- Three replicates each, 9 runs, `PROFILE=main`: 2 h agent time, 30 rounds,
  45-minute round cap. About 18 hours.
- Order from `make study-schedule`; run ids `v17-sql-<condition>-r<n>`.
- Launched with `make experiment`, which verifies the endpoint and measures
  that the budget is enforced before the first run, and may relaunch the
  pinned server once if it dies between runs.

## Amendment, 2026-09-22: JavaScript and TypeScript added

Added at the project owner's direction while the batch was running, after 7 of
its 9 runs had reported. Recorded here as an amendment rather than folded into
the text above, because the distinction matters when the results are read.

**What was added.** Two conditions on the same SQL task, `javascript`
(`node --check` as the build gate) and `typescript` (`tsc --strict
--noEmitOnError`), using the adapters that already existed at
`studies/assets/candidates/sql/`. Three replicates each, same `main` profile.

**Why.** The typed-against-untyped contrast has been run twice in this
project, both times as TypeScript against JavaScript on the chapters 1-10
compiler task, and both times null: v4 paired median +0.026 (n=3), v7 +0.004
on the corpus and +0.001 on the fuzzer (n=4), with six of eight v7 finals
between 0.954 and 0.968. That task was saturated, so it could not show an
effect in either direction. This task is not: v17's completed runs span 0.134
to 0.851. Running the TS/JS pair here separates "static typing does not
matter" from "the compiler task was too easy to tell", which neither earlier
batch could do.

**What this does not do.** It does not disturb the nine runs already
scheduled. The running chain works from `runs/v17-sql-schedule.json`, frozen
at launch with those nine slots. The three existing conditions resolve
byte-identically before and after the edit, and each finished run's frozen
condition still matches the manifest, so none is excluded from the summary;
this was verified before the manifest was written.

**How to read the result.** The six new runs are a *later addition to a batch
whose partial results were already visible*, and they are not blind to them.
The Python comparison in this plan was fixed before any data; the TS/JS
comparison was not. It is therefore reported as its own contrast with its own
decision rule below, and the two are not pooled.

**Decision rule for the added contrast**, fixed before its first run and the
same one used in v4 and v7: among replicates where both arms produced a
working engine, `typescript` minus `javascript`, paired by replicate,
**typing helps** at +0.13 or more, **typing hurts** at -0.13 or less, **no
effect detected** in between, **not measurable** below two usable pairs. At
three replicates this is descriptive.

**The question it is actually able to answer.** Given v17's Python arms span
0.134 to 0.851 across three replicates of one condition, a three-replicate
median is unlikely to resolve a difference smaller than that spread. The
honest expected outcome is a variance measurement, and the write-up should
lead with the spread rather than the median.

## Endpoints

v15's, unchanged.

1. **Produced a working engine**: the run's hidden score is above the
   constant-output floor (0.0503). A count per condition.
2. **Hidden score among runs that did**, `python-typed` against `python`,
   paired by replicate.

Secondary: writes, cut-off rate, rounds used, termination reason, and
reasoning tokens per reply from `analysis/reasoning_tokens.py` (how many
replies reach the budget, per condition -- the budget binding more often under
typing would itself be a finding).

## Validity gate

A run is not comparable if any reply ended in a stream error or any
compaction failed; both are harness defects with fixes that are supposed to
hold. If either appears, the batch is stopped and the defect fixed, not
analyzed around. `analysis/v17_results.py` reports both per run and says so.

## Decision rule, fixed before the data

On endpoint 1: report the counts. With three replicates a difference of 3 to
0 is worth stating and anything smaller is not.

On endpoint 2, among replicates where both Python arms produced a working
engine:

- **Typing helps** if the paired median hidden score of `python-typed`
  exceeds `python` by at least 0.13, the threshold used since v4.
- **Typing hurts** if it falls short by at least 0.13.
- **No effect detected** otherwise.
- **Not measurable** if fewer than two replicates have both arms working.

At three replicates this is descriptive, not a test. `rust` is the reference
arm and carries no hypothesis.

## Exclusions

Pilots, resumed runs, and any run whose frozen condition does not match the
manifest. The v16 runs (`v16probe-…`, `v16-sql-python-typed-r1`,
`v16nb-sql-python-typed-r9`, and the quarantined first attempt) carry a
different manifest id and cannot enter the summary.

## Analysis

`make study-summary STUDY=studies/sql/study.json`, then
`python3 analysis/v17_results.py`, then
`.venv-sglang/bin/python analysis/reasoning_tokens.py <run ids>`.
