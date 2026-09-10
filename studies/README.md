# PiCC controlled-study layer

This directory adds controlled factor studies without changing the hardened
single-run harness. `scripts/study.py` creates an isolated materialization for
one condition, overlays only its experimental artifacts, and delegates execution
and reporting to the existing PiCC scripts.

## What is variable

A condition records and freezes:

- Pi context prompts (`AGENTS.md`, initial request, continuation request);
- specification content, delivery location, and provenance;
- visible-test availability, feedback granularity, amount, source, and
  provenance;
- candidate language, framework label, adapter, and optional starting scaffold;
- reference access: none, black-box oracle, or visible source;
- optional environment and budget overrides.

The hidden partition, task interface, model, Pi version, outer harness, and
primary behavioral metric stay fixed unless a condition explicitly changes the
implementation substrate.

## Starter study

`starter/study.json` is a one-factor-at-a-time matrix with a shared baseline:

| Condition | Changed factor |
|---|---|
| `baseline` | None |
| `prompt-minimal` | Workflow/context prompt |
| `spec-brief` | Specification detail |
| `spec-architecture` | Architectural guidance |
| `spec-inline` | Specification delivery |
| `tests-none` | Test availability |
| `tests-aggregate` | Feedback granularity |
| `tests-files` | Test delivery as readable files |
| `tests-quarter` | Visible-test amount |
| `language-python` | Implementation language |
| `scaffold-rust` | Starting framework/scaffold |
| `reference-oracle` | Black-box reference access |

## Static-typing study

`types/study.json` (`picc-types-v1`) reuses the starter defaults and contrasts
two candidate adapters on one Node.js 24 runtime:

| Condition | Role | Candidate |
|---|---|---|
| `js-untyped` | study baseline | plain JavaScript, `node --check` build, `tsc` withheld by the guard |
| `ts-strict` | variant (`candidate`) | TypeScript, `tsc --strict --noEmitOnError` build gate |

```bash
make study-validate STUDY=studies/types/study.json
make study-schedule STUDY=studies/types/study.json REPLICATES=3 PROFILE=main
make study-run STUDY=studies/types/study.json CONDITION=ts-strict PROFILE=main RUN_ID=v4-ts-strict-r1 REPLICATE=1
make study-summary STUDY=studies/types/study.json
```

## Test-availability study (revised oracle)

`tests/study.json` (`picc-tests-v2`) holds the starter's `baseline` and
`tests-none` unchanged, for the v5 replication under the revised harness
(preprocessed candidate inputs, corpus macro and fuzz macro as co-primary
endpoints). It is a separate manifest so the v3 aggregation stays intact.

The starter deliberately does **not** claim to identify the causal effect of
"human-created" versus "LLM-created" specifications/tests. Provenance is
recorded, but creation method is only identifiable when several independently
created, coverage-matched artifacts are compared. Add such artifacts as new
paths/partitions and replicate them as a blocked study.

## Commands

```bash
make study-validate
make study-list
make study-schedule REPLICATES=3 PROFILE=main

make study-run \
  STUDY=studies/starter/study.json \
  CONDITION=baseline \
  PROFILE=pilot \
  RUN_ID=baseline-pilot-r1 \
  REPLICATE=1

# Pilot diagnostics are retained but excluded from the primary aggregate.
make study-hidden-all RUN_ID=baseline-pilot-r1
make study-report RUN_ID=baseline-pilot-r1

make study-run \
  STUDY=studies/starter/study.json \
  CONDITION=baseline \
  PROFILE=main \
  RUN_ID=baseline-main-r1 \
  REPLICATE=1
make study-hidden-all RUN_ID=baseline-main-r1
make study-report RUN_ID=baseline-main-r1
make study-summary STUDY=studies/starter/study.json
```

The primary summary includes only completed, uninterrupted `main` runs with
current study/condition hashes, a positive replicate identifier, verified frozen
assets/runtime fingerprints, and hidden evaluations covering every snapshot. It
lists pilot, resumed, incomplete, stale, and mismatched runs as exclusions;
cohort drift or duplicate condition/replicate cells are hard errors, while
missing planned cells and unmatched baselines are explicit warnings.

Inspect a materialization without running Pi:

```bash
make study-materialize CONDITION=tests-none RUN_ID=inspect-tests-none
find runs/.study-materializations/inspect-tests-none -maxdepth 3 -type f
```

A study run keeps its materialization for audited resume and post-hoc evaluation.
Generated materializations and results remain under ignored `runs/` paths.

## Adding a condition

Add a small overlay to `conditions` in a study manifest. The condition is deep
merged with `defaults`. Paths are repository-relative. Candidate adapters use
`studies/assets/candidates/*.json`; custom visible/hidden partitions must contain
a PiCC manifest with the existing `tests` row format.

For a source-visible reference condition:

```json
{
  "id": "reference-source",
  "factor": "reference",
  "reference": {
    "mode": "source",
    "oracle_limit": 0,
    "source": "studies/assets/references/my-reference"
  }
}
```

For a matched LLM-created specification, add a separate specification file and
truthful provenance:

```json
{
  "id": "spec-llm-a",
  "factor": "specification",
  "specification": {
    "path": "studies/assets/specs/llm-a.md",
    "delivery": "task_file",
    "provenance": {
      "method": "llm-generated-human-reviewed",
      "creator": "researcher",
      "generation_model": "frozen-model-id",
      "source": "frozen-generation-prompt-hash",
      "artifact_family": "coverage-matched-spec-set-1",
      "reviewed_by": "reviewer-id"
    }
  }
}
```

Keep all other fields equal, use more than one artifact per creation method, and
analyze artifact as a random/blocking effect rather than treating one document
as representative of a process.

## Isolation note

The no-test condition uses an empty agent-visible mount. Tool-only versus
readable-file test access is enforced by the Pi guard because the current test
gateway runs in the agent container. This is suitable for non-adversarial
coding-agent experiments but is not a hard sandbox boundary; see the protocol's
containment limitation.

Post-hoc candidate build and compiler processes share the evaluator container
and namespace with the selected visible or hidden partition and the run-local
reference cache. Hidden scores are valid only for policy-compliant,
non-adversarial candidates; these artifacts are auditable, not tamper-resistant.

Candidate source audit scans Rust, Python, and JavaScript/TypeScript source,
including recognized test paths, and rejects symlinks. Committed integration
tests that invoke subprocesses can therefore fail policy audit even when product
behavior is otherwise correct.
