# Experiment plan: v11 batch (replication of v10 on the corrected harness)

Status: frozen by the commit that adds this file, 2026-09-18 08:20 UTC,
before the first main run. Pilot evidence below.

## Study identity

- Studies: `studies/sql/study.json` (`picc-sql-minimal-v2`) and
  `studies/c18/study.json` (`picc-c18-minimal-v2`), seed 20260918, analyzed
  and reported separately. New manifest ids: v10 runs are never pooled with
  these.
- Harness: the four fixes below, on top of the v10 results and the scoped
  Python audit. The exact code each run used is frozen in its own
  materialization under `runs/.study-materializations/<run-id>/`. Image `picc-experiment:0.5`
  (`sha256:9fb66bd28dcf036578e244e5e6c1df5392a793cfb46379e099be1667961da6ed`),
  unchanged from v10: Pi 0.85.1, mypy 2.3.1, Rust 1.88.0, SQLite 3.40.1.
- Provider/model unchanged from v7-v10: `local`, llama.cpp serving
  `unsloth/Qwen3.8-27B-GGUF:UD-Q4_K_XL` (GGUF SHA-256 `3f227079…`, verified by
  `make preflight` before each slot), thinking `high`, sampling pinned,
  `LOCAL_MAX_OUTPUT=65536`.
- Test selections unchanged and still pinned: `studies/c18/selection.json`
  (668 visible / 281 hidden), `studies/sql/selection-record.json` (22 / 8).

## Research question

Same as v10: on each task, does requiring static typing (`mypy --strict` as
the build gate) change hidden behavioral correctness relative to plain
Python? v10 met its effect criterion on the SQL task but ten of eighteen runs
scored zero for reasons unrelated to their condition, so the estimate is
confounded. v11 repeats the design on a harness where those four causes are
removed, to see whether the contrast survives.

Secondary question, answered by comparing batches descriptively: how much of
v10's zero rate was harness rather than model?

## What changed since v10

1. **Context-overflow termination.** A round whose compaction reported an
   error, with no tool call and no workspace change, is dead;
   `MAX_CONSECUTIVE_DEAD_ROUNDS=2` such rounds end the run with reason
   `context_overflow`. v10 lost five runs to this mode.
2. **Stall rule conditioned on work.** A capped round counts toward
   `MAX_CONSECUTIVE_ROUND_TIMEOUTS=2` only when its snapshot shows no change.
   v10 ended twelve runs at about 91 of 120 minutes while they were building.
3. **Hanging-candidate short-circuit.** After 25 consecutive compiler timeouts
   (3 script timeouts for SQL) the remaining cases are recorded as timeouts
   without being run. v10 lost one run entirely to an evaluation that exceeded
   its 7200 s ceiling.
4. **Evaluation time outside the agent budget.** The round loop gates on
   `agent_deadline()`, so the 2 hours is agent time. v10 charged evaluation to
   the run, penalising slow-to-evaluate candidates twice.

The scoped Python audit (v10 Amendment 2) is already in the evaluator.
Conditions, prompts, contracts, adapters, budgets, partitions, model, and
image are otherwise identical to v10.

Consequence for comparability: v11 runs may use more agent time than v10 runs
(up to the full 2 hours rather than 91 minutes), so a v11-versus-v10
difference confounds the fixes with effort. The batches are compared only
descriptively; the typing contrast is within-batch and paired, as before.

## Conditions

Per study, one-factor-at-a-time on `candidate`:

| Condition | Adapter | Build gate |
|---|---|---|
| `rust` (baseline) | `rust-std.json` | `cargo build --release --offline` |
| `python` | `python-untyped.json` | `python3 -m py_compile`; type checkers withheld by the guard |
| `python-typed` | `python-typed.json` | `mypy --strict` |

Everything else is held constant: the minimal protocol (empty repository, one
short behavioral contract as the initial message, blank `AGENTS.md`/`TASK.md`,
`Continue.`, built-in tools only, no tests, scores, or reference).

## Planned runs

- 3 replicates per condition per study: 18 main runs, `PROFILE=main`,
  `MAIN_HOURS=2`, 45-minute round cap, 30 rounds; c18 stages 1-18, SQL 1-8.
- Order from `make study-schedule` with seed 20260918, SQL first, then c18;
  run ids `v11-<task>-<condition>-r<n>`. Both studies use the same order:
  1. `python-r1` 2. `rust-r1` 3. `python-typed-r1` 4. `rust-r2` 5. `python-r2`
  6. `python-typed-r2` 7. `python-r3` 8. `python-typed-r3` 9. `rust-r3`
- Chain: `scripts/chain_study.sh` per study, sequential and unattended.
- Pilots, excluded from every analysis: `v11-pilot-sql-python-typed` and
  `v11-pilot-c18-rust`, pilot profile, run before this freeze to exercise the
  new control flow.

## Primary endpoint

Hidden corpus macro on the last buildable snapshot (final snapshot as
co-primary), per study. No fuzz oracle exists for either task. The typing
contrast is `python-typed` minus `python`, paired by replicate: per-replicate
deltas and their median.

Floors, from the evaluator-only fixture candidates: SQL constant-output 0.050,
reject-all 0.000; chapters 1-18 constant-output 0.213, reject-all 0.500.

## Secondary endpoints

Per-stage hidden pass rates; rounds used and termination reason; agent time
used (now excluding evaluation); `round_evidence` per snapshot (tool calls,
failed overflow recovery, workspace change); build-gate failures and mypy
error counts for the typed arm; source lines; guard blocks; short-circuited
evaluations.

## Interpretation rule

Unchanged from v10, applied per study: a claim of a typing effect requires all
three replicates to agree in sign and the median to exceed 0.13. A task is
called feasible for a condition when at least two of three replicates end
above the constant-output floor with a nonzero valid-program pass rate.

Pre-specified so it cannot be chosen afterwards: if v11 meets the criterion on
the SQL task in the same direction as v10, the typing effect is reported as
replicated on that task, with the build gate as its stated mechanism. If it
does not, v10's result is reported as not replicated and attributed to the
harness interactions.

## Exclusion rules

As in v9 and v10: pilots, resumed runs, and runs whose frozen condition no
longer matches the manifest are excluded and listed; duplicate cells are hard
errors. A run whose hidden evaluation cannot complete is excluded and named,
as `v10-c18-python-typed-r3` was.

## Human intervention policy

None during a run. Defects found mid-batch become numbered amendments here
and fixes for the next manifest version.

## Analysis

`make study-summary` per study, then `python3 analysis/v11_results.py`
(committed before the first main run; it reuses the v10 script's table and
criterion, and adds the v10-versus-v11 zero-rate comparison).

## Pilot evidence

Both pilots ran on image 0.5 through `make study-run`, `study-hidden-all`,
and `study-report`, 2026-09-18 07:29-08:17 UTC, pilot profile (0.4 h,
12-minute round cap). They exercise the changed control flow; neither is an
outcome.

- `v11-pilot-sql-python-typed`: 2 rounds, ended `wall_time_budget` at 24.0
  minutes of agent time. Round 0 was capped with no tool call and no
  workspace change and counted as a stall (1/2); round 1 was capped with 22
  tool calls and 5 changed files and did **not** count, so the run continued
  to its budget. Under the v10 rule it would have ended at round 1 with
  `round_timeout`.
- `v11-pilot-c18-rust`: 2 rounds, ended `wall_time_budget` at 24.0 minutes.
  Both rounds were capped and productive (14 and 9 tool calls, 1 and 4
  changed files); neither counted as a stall.

Both runs used exactly their 24 minutes of agent time with the visible
evaluations excluded, confirming the budget accounting. Every snapshot
carries the new `round_evidence` field (`tool_calls`,
`overflow_recovery_failed`, `changed_workspace`). The context-overflow
termination path was not reached by either pilot; it is covered by unit
tests (`tests/test_v11_fixes.py`), as is the evaluator short-circuit against
a deliberately hanging candidate.
