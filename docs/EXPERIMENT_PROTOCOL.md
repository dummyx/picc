# Fixed experiment protocol

## Research question

Under a fixed wall-clock and interaction budget, how much of the specified C
subset can a single Pi coding-agent session using GLM-5.2 Coding Plan implement
from an empty Rust repository without human steering?

## Unit of observation

One complete run is one stochastic model–harness trajectory. It starts from a
fresh empty Git repository and a fresh Pi session. Reusing a partially developed
workspace is not a new independent run.

## Conditions

The starter has one condition:

- Pi `0.84.1`;
- built-in `zai` provider;
- model `glm-5.2`;
- thinking setting `max`;
- stock Pi compaction with explicitly frozen settings;
- project-local test and guard extensions;
- one agent;
- no human steering;
- no web or source retrieval through agent tools;
- standard-library-only Rust implementation.

Selecting the optional local endpoint (`MODEL_PROVIDER=local`, see README) keeps
the same harness and budgets but is a different model condition. Runs made that
way must be labeled and analyzed separately from the `glm-5.2` condition.

## Task

PiCC accepts one C source file and emits x86-64 assembly:

```text
target/release/picc INPUT.c -o OUTPUT.s
```

The required stages are fixed in `prompts/TASK.md`. No optimization is required.

## Feedback

The agent sees the visible partition and compact `test_visible` outcomes. It
never sees hidden tests, hidden scores, or hidden failure diagnostics during a
run.

The outer harness evaluates each round's immutable Git snapshot on visible
tests. Hidden evaluation happens only after the run.

## Budgets

### Pilot

- 2 wall-clock hours;
- at most 6 Pi invocations;
- at most 45 minutes for one invocation;
- Stages 1–6.

Pilot results are infrastructure/feasibility evidence and are excluded from the
main descriptive summary.

### Main

- 12 wall-clock hours;
- at most 30 Pi invocations;
- at most 60 minutes for one invocation;
- Stages 1–10.

The first reached limit terminates the run. Full visible success receives at
most one additional fixed continuation round for review.

An audited resume does not reset either budget. A timed-out or failed Pi
invocation remains a consumed round, and the next invocation receives the next
sequential round number. Remaining time is the frozen total minus cumulative
active harness time from all execution attempts. Time while no harness process
is running is not charged. This recovery accounting is recorded for diagnosis,
but a resumed trajectory is not comparable with an uninterrupted protocol run.

## Primary outcome

Final hidden macro-score:

1. compute a valid-program pass rate and invalid-program pass rate per stage;
2. average the available validity classes within the stage;
3. average equally across included stages.

## Secondary outcomes

- final hidden micro pass rate;
- highest stage reaching a pre-declared threshold;
- visible–hidden gap;
- score-versus-time area under the curve when all snapshots are evaluated;
- buildable snapshot fraction;
- regressions between rounds;
- Rust LOC and churn, as descriptive—not success—metrics;
- Pi model calls, reported token usage, tool calls, retries, and compactions;
- blocked guard events;
- run-to-run variability.

## Repetitions

Use at least three main runs. Coding Plan does not expose deterministic sampling
seeds through Pi, so repetitions use unique IDs and identical configuration but
are not seeded deterministic trials.

Report every run individually, then median and range. Never select only the best
run.

## Allowed interventions

No intervention is permitted after a main run starts. Infrastructure restarts,
prompt changes, manually supplied hints, workspace edits, or quota top-ups make
the trajectory noncomparable and must be recorded.

The harness provides `make resume RUN_ID=...` for audited recovery. Resume is
allowed only when a completed run ended in `round_timeout` or
`pi_process_failure` and both frozen budgets still have capacity. It continues
the same named Pi session with the unchanged continuation prompt. It is not a
new run, does not erase the original outcome, and sets `protocol_comparable` to
false. A resumed main trajectory must be analyzed separately rather than
included among the pre-registered independent repetitions.

Resume is refused unless all of the following still hold:

- the stored model and non-secret configuration agree with metadata, and the
  frozen Docker tag still resolves to the recorded immutable image ID;
- frozen prompt, settings, extension, visible-manifest, and hidden-manifest
  hashes match;
- round and snapshot ledgers are complete, paired, and sequential, and the next
  round's output paths are unused;
- exactly one valid named Pi session exists;
- the workspace is clean and its Git HEAD and tree match the latest snapshot;
- no Pi container or other harness process for the run is active;
- no post-hoc visible or hidden evaluation or report has been generated.

The harness appends resume start/finish audit events and records both the new
execution attempt and the operator intervention in `metadata.json`. Hidden
evaluation remains post-hoc: once postprocessing begins, that run cannot be
resumed.

A run may be excluded only under a pre-registered rule, such as failure before
any successful provider response due to a demonstrable harness defect. Model
errors, bad plans, generated build failures, and ordinary provider throttling
are outcomes, not exclusion reasons.

## Freeze checklist

Record before main runs:

- starter repository Git commit;
- Docker image name and immutable image ID;
- Pi version;
- Rust version;
- prompt and extension hashes;
- visible and hidden manifest hashes;
- upstream test revision;
- effective `.env` overrides, excluding secrets;
- host and Docker platform;
- run IDs and planned number of repetitions.
