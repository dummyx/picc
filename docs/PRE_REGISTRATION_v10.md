# Pre-registration: v10 cohort (new tasks, language baseline) — DRAFT

Status: draft, not frozen. Decision points are marked **[decide]**. Freeze
by committing this file with the marks resolved, after one pilot per task.

## Study identity

- Studies: `studies/c18/study.json` (`picc-c18-minimal-v1`) and
  `studies/sql/study.json` (`picc-sql-minimal-v1`), reported separately.
- Harness commit: `e02c8b7` (task infrastructure). Image `picc-experiment:0.4`
  (`sha256:2e4e4dc5…`), Pi 0.85.1, model and endpoint as frozen in `.env`.
- Test selections: `studies/c18/selection.json` (668 visible / 281 hidden),
  `studies/sql/selection-record.json` (22 / 8). `make tests-c18 tests-sql`
  refuses any deviation.

## Research question

Is either task feasible for the current model under the minimal protocol, and
how does the hidden score distribute across replicates? This cohort is a
baseline, not a contrast: it establishes the floor and variance that later
language or test-access contrasts on these tasks would be measured against.

## Planned runs

- Condition `rust` of each study, `PROFILE=main`, replicates 1–3
  **[decide: 3 replicates; add `python` for a language contrast?]**.
- Budget as configured: `MAIN_HOURS=2`, 45-minute round cap, 30 rounds;
  c18 stages 1–18, SQL stages 1–8 **[decide: 2 h is the chapters 1–10
  budget; the chapters 1–18 task may need more]**.
- Run IDs `v10-c18-rust-r<n>`, `v10-sql-rust-r<n>`; order from
  `make study-schedule` with seed 20260916.
- One pilot per task before the freeze (`PROFILE=pilot`); pilots are never
  counted.

## Primary endpoint

Hidden corpus macro score on the last buildable snapshot, with the final
snapshot as co-primary, per task. No fuzz oracle exists for either task.
Reported as the per-replicate values and their median.

Known floors of the metric (evaluator-only candidates, `studies/*/README.md`):
c18 reject-all 0.50, constant-output 0.21; SQL reject-all 0.00–0.01,
constant-output 0.01–0.05. A run is "above floor" when its last-buildable
score exceeds the constant-output value and, for c18, its valid-program pass
rate is nonzero.

## Secondary endpoints

Per-stage hidden pass rates; visible-score trajectory; rounds used; guard
blocks; source lines; whether the agent wrote its own tests.

## Interpretation rule

Descriptive. Feasibility is claimed for a task when at least two of three
replicates are above floor. No between-task comparison is made.

## Exclusion rules

As in v9: pilots, resumed runs, and runs whose frozen condition no longer
matches the manifest are excluded and listed; duplicate cells are errors.

## Human intervention policy

None during a run. Defects found mid-cohort become numbered amendments here
and fixes for the next manifest version.

## Analysis

`make study-summary` per study; a short `analysis/v10_results.py` that reads
`runs/study-results/<id>/runs.csv` and prints the per-replicate table
**[write before the first main run]**.

## Pilot evidence

**[fill after the two pilots: build success, rounds, hidden score, per-round
visible evaluation time on the SQL task]**
