# Experiment plan: v12 batch (supersedes v11, which was aborted)

Status: frozen by the commit that adds this file, 2026-09-19, before the
first main run.

## Why v11 was aborted

v11 ran four SQL runs and was stopped. Two of the four died with
`context_overflow`, and the cause was a configuration defect, not the model
and not the condition:

`LOCAL_MAX_OUTPUT` was 65536 against a `LOCAL_CONTEXT_WINDOW` of 131072,
exactly half, while Pi's compaction reserve (`pi/settings.json`,
`reserveTokens`) was 16384. Pi compacts when the conversation reaches
`n_ctx - reserveTokens`; the reserve is what absorbs the turn that follows.
A turn able to emit four times the reserve can overshoot the window, after
which the summarization request carries more than the context holds. The
observed failing requests were 132902, 152051, and 190530 tokens against a
131072 window; the provider returned 400 and every later round was dead.

The discriminator across both batches is exact:

| Outcome | Turns truncated at the 65536 cap |
|---|---|
| Died (4 runs examined) | 2, 2, 2, 3 |
| Survived (4 runs examined) | 0, 0, 0, 1 |

The v11 fixes (work-conditioned stall rule, context-overflow termination,
hang short-circuit, evaluation outside the budget) were correct and are kept.
They made the failure cheap and legible; they did not remove its cause. v11's
four runs are retained under `runs/` and excluded from every analysis: their
frozen configuration carries the defect.

## What changed since v11

- `LOCAL_MAX_OUTPUT` 65536 -> 32768.
- `pi/settings.json` compaction `reserveTokens` 16384 -> 40960.
  The invariant to satisfy is `max_output <= reserveTokens` and
  `max_output + reserveTokens <= n_ctx`. At 32768 and 40960 against 131072,
  compaction triggers at 90112 and the worst case after a maximal turn is
  122880, leaving 8192 tokens of margin.
- `scripts/common.py:context_budget_problems` encodes that invariant.
  `make preflight` reports `unsafe_context_budget` and exits 2, and
  `run_experiment.py` calls `require_context_budget` before starting any
  container. A configuration that can kill a session can no longer start one.
- Server configuration confirmed rather than assumed: `llama-server -c 131072`
  with four slots, per-slot `n_ctx` 131072 from `/props`, so the declared
  window is the real one.

Mid-turn truncation is now more frequent at 32768 than at 65536. That is the
accepted trade: truncation costs a round, overflow costs the run. If
truncation proves disruptive the next lever is the thinking level, which
changes model behaviour and breaks comparability with v3 onward, so it would
be its own batch.

## Everything else is unchanged from v11

Studies `picc-sql-minimal-v3` and `picc-c18-minimal-v3` (seed 20260919),
three conditions (`rust`, `python`, `python-typed`), three replicates, image
0.5, 2-hour agent budget, 45-minute round cap, the same contracts, adapters,
partitions, and pinned selections. Research question, primary endpoint,
secondary endpoints, interpretation rule, exclusion rules, and intervention
policy are exactly as written in `docs/EXPERIMENT_PLAN_v11.md`, which this
file supersedes.

Order from `make study-schedule`, SQL first then c18, run ids
`v12-<task>-<condition>-r<n>`:
1. `rust-r1` 2. `python-r1` 3. `python-typed-r1` 4. `python-r2`
5. `python-typed-r2` 6. `rust-r2` 7. `rust-r3` 8. `python-r3`
9. `python-typed-r3`

## Analysis

`make study-summary` per study, then `python3 analysis/v12_results.py` (the
v11 script repointed at the v3 manifests). The v10 comparison stays
descriptive: v10, v11, and v12 differ in harness and configuration, so only
the within-batch paired typing contrast is interpreted.

## Pilot evidence

`make preflight` verifies the endpoint and the context budget together. The
invariant is covered by unit tests, including the exact v10/v11 configuration
as a rejection case. No further pilot is run: the control-flow changes were
already exercised by the v11 pilots and by four v11 main runs, and the only
change since is configuration.
