# Experiment plan: v13 (completion rate, not score)

Written before the first run. Short by intent: one question, one endpoint.

## Question

Does requiring `mypy --strict` reduce the rate at which the agent *completes*
a working engine, by changing how often it acts per turn?

This replaces the score contrast that v10-v12 could not measure. Section 17.4
of `analysis/report.md` reports the reason: when a run completes, all three
conditions reach comparable scores (0.825 / 0.795 / 0.757), but the typed arm
completes far less often.

## Design

- Study `studies/sql/study.json` (`picc-sql-minimal-v3`), SQL task only. The
  effect is concentrated there; the compiler task showed nothing at n=3, which
  may be lack of power and is left for later.
- Conditions unchanged: `rust`, `python`, `python-typed`.
- Five replicates each, 15 runs, `PROFILE=main` (2 h agent time, 45-minute
  round cap). Full length is required: runs that collapse look healthy early
  and degrade later (1.00 -> 0.39, 0.83 -> 0.43, 0.75 -> 0.35), so a short run
  samples the healthy phase and misses the effect.
- Order from `make study-schedule`, run ids `v13-sql-<condition>-r<n>`.

## Endpoints

Primary, per run:

1. **Session survived**: no compaction failure, from the `compaction_end`
   events with an error message.
2. **Turn shape**: tool executions per assistant turn over the whole run.

Secondary: hidden score where a run completes; rounds used; agent time;
termination reason; `round_evidence` per snapshot.

Score is explicitly *not* the primary endpoint. Scoring a completion against a
non-completion is what produced the contradictory v10 and v11/v12 results.

## Decision rule, fixed before the data

Compare `python-typed` against `python`, paired by replicate where both exist,
and report the breakage counts per condition.

- **Confirmed** if `python-typed` breaks in at least twice as many runs as
  `python` and its median turn shape is at least 0.15 below.
- **Not confirmed** otherwise.

No claim either way is made from the score column; it is reported for context.
At five replicates this is descriptive, not a test.

## Exclusions

Pilots and any run whose frozen condition does not match the manifest.
Runs that break their session are *included*: breakage is the endpoint here,
not a reason to drop a run.

## Analysis

`analysis/turn_shape.py` for the profile, `make study-summary` for scores.
