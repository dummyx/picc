# Pre-registration template

Complete and commit this file before starting reportable main runs.

## Study identity

- Study title:
- Date frozen:
- Starter repository commit:
- Investigator:

## Research question

Under the frozen Pi and declared-model condition, what hidden behavioral
correctness can the agent reach on PiCC within the main budget?

## Planned runs

- Number of main repetitions:
- Run IDs:
- Pilot run ID(s), excluded from main analysis:

## Frozen configuration

- Docker image ID:
- Pi version:
- Provider/model:
- Thinking setting:
- Rust toolchain:
- Test repository revision:
- Visible manifest SHA-256:
- Hidden manifest SHA-256:
- Prompt/extension hashes location:
- Any `.env` overrides other than credentials:

## Primary endpoint

Final hidden macro-score averaged equally across stages and, within each stage,
across valid and invalid test classes.

## Secondary endpoints

Select before running:

- [ ] final hidden micro score
- [ ] highest stage with at least ___ hidden score
- [ ] hidden score/time AUC
- [ ] visible–hidden gap
- [ ] buildable snapshot fraction
- [ ] compaction count
- [ ] reported input/output tokens
- [ ] tool-call distribution
- [ ] guard-blocked calls
- [ ] Rust LOC/churn (descriptive only)

## Feasibility criterion

Pre-declare a criterion, for example:

- median final hidden macro-score at least: ___
- and/or at least ___ of ___ runs reach Stage ___ at score ___

## Exclusion rules

A run may be excluded only if:

- [ ] the Docker image or frozen test partition is missing/corrupt before work;
- [ ] authentication fails before the first successful model response;
- [ ] a confirmed harness implementation defect invalidates measurement;
- [ ] other pre-declared rule: ___

Do not exclude ordinary model mistakes, compiler build failures, low scores,
compaction failures caused by the trajectory, or documented provider rate
limits unless rate-limit exclusion was explicitly pre-registered.

## Human intervention policy

- No prompts beyond the frozen initial/continuation messages.
- No workspace edits after start.
- No inspecting hidden results before run termination.
- Any unavoidable intervention is logged and the run is analyzed separately.

## Analysis

- Report all runs individually.
- Report median and range; optionally mean and standard deviation.
- Do not select the best trajectory as the primary result.
- Qualify claims as task-specific.
- Disclose public-test contamination and hosted-model drift.
