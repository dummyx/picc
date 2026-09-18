# Experiment plan: v3 batch

Completed and committed before the first v3 run. Earlier batches (the v1
pilots and the v2 stages-1–6 batch) predate this document and are reported
as exploratory; see `analysis/report.md`.

## Study identity

- Study title: PiCC v3 — test availability at stages 1–10 (baseline vs tests-none)
- Date frozen: 2026-09-01
- Starter repository commit: `ab67a7ea9b6fa587a362a876599b23fdfa6961b1`
  (this experiment plan is committed on top; no harness, prompt, partition,
  or configuration file changes with it)
- Investigator: dummyx

## Research question

Under the frozen harness, budgets, and declared local model, does withholding
all agent-visible tests and scores (`tests-none`) change hidden behavioral
correctness relative to `baseline` (failure-level `test_visible` tool access)
when the task is stages 1–10 under a 2-hour budget?

Motivation, pre-declared from the v2 batch before any v3 run: tool uptake was
the strongest observed correlate of outcome, and stages 1–6 saturated. This
batch raises difficulty (report §6.2) and manipulates test availability
directly (§6.3).

## Planned runs

- Number of main repetitions: 3 per condition, 6 runs total
- Run IDs, in the frozen randomized block order (from `study.py schedule`,
  study seed 20260811, filtered to the two conditions):
  1. `v3-tests-none-r1`
  2. `v3-baseline-r1`
  3. `v3-tests-none-r2`
  4. `v3-baseline-r2`
  5. `v3-baseline-r3`
  6. `v3-tests-none-r3`
- Pilot/prior run IDs, excluded from this batch's analysis: all `*-pilot-*`
  runs; the `v2-*` batch (pilot profile, stages 1–6); `baseline-main-r1`
  (prior harness revision and a 24-hour budget; stale fingerprints).

## Frozen configuration

- Docker image ID: `sha256:dcff5de58827829e72a50416ecd8c66923fe4cdc88577f613aa508ffb9dc02af`
  (`picc-experiment:0.1`)
- Pi version: `@earendil-works/pi-coding-agent@0.84.1`
- Provider/model: `local` — llama.cpp `llama-server` build `b1-3cb7ffb` serving
  `unsloth/Qwen3.8-27B-GGUF:UD-Q4_K_XL`
  (GGUF SHA-256 `bee238bbeb3dc0a34bde4d0dedbaee1f98c009e8bb4226f03070054c12fb1372`,
  HF snapshot `f1bfb127c64f7072bdd2cad55f258b9c8b2910fe`; single RTX 5090;
  full endpoint provenance in `runs/local-endpoint-provenance.json`)
- Thinking setting: `high`
- Rust toolchain: `1.88.0`
- Test repository revision: `ae12014d2dec14488f3f80d14df4b6d8e4634d7d`
- Visible manifest SHA-256: `bb5410a9ae1d0cfe904d5316828791b04e77dca4fb459601877ce9e927029a6f` (227 tests)
- Hidden manifest SHA-256: `49960548e8ce2353990fc39bd91536166df37e14c62dd33acd27afccef01faef` (104 tests)
- Prompt/extension hashes location: per run, `runs/<id>/study-metadata.json`
  (`rendered.*` and `materialized_harness.file_hashes`) and `runs/<id>/metadata.json`
- `.env` overrides other than credentials:
  `MODEL_PROVIDER=local`, `MODEL_ID=unsloth/Qwen3.8-27B-GGUF:UD-Q4_K_XL`,
  `MODEL_THINKING=high`, `LOCAL_BASE_URL=http://127.0.0.1:4545/v1`,
  `LOCAL_NETWORK_MODE=host`, `LOCAL_CONTEXT_WINDOW=131072`,
  `LOCAL_MAX_OUTPUT=65536`,
  `LOCAL_SAMPLING_PARAMS={"temperature": 1.0, "top_p": 0.95, "top_k": 20, "min_p": 0}`,
  `MAIN_HOURS=2`, `MAIN_ROUND_TIMEOUT_MINUTES=45`.
  Effective main budget: 2 h wall, 30 rounds, 45-min round cap, stages 1–10,
  two consecutive stalls terminal (`MAX_CONSECUTIVE_ROUND_TIMEOUTS=2` default).

## Primary endpoint

Final hidden macro-score averaged equally across stages and, within each stage,
across valid and invalid test classes. The primary contrast is
`tests-none` − `baseline`, paired by replicate identifier.

## Secondary endpoints

Selected before running:

- [x] final hidden micro score
- [ ] highest stage with at least ___ hidden score
- [x] hidden score/time AUC (all snapshots evaluated)
- [x] visible–hidden gap (overfitting check; expected to differ by condition)
- [x] buildable snapshot fraction
- [x] compaction count
- [x] reported input/output tokens
- [x] tool-call distribution (including `test_visible` and self-test shell use)
- [x] guard-blocked calls
- [x] Rust LOC/churn (descriptive only)
- [x] completion per study manifest: hidden macro ≥ 0.95 with successful build
  and no blocking audit finding

## Feasibility criterion

Pre-declared interpretation rule: report all six runs individually, then
per-condition median and range. A paired median difference with magnitude
greater than 0.13 (the resolution the v2 batch established for n=3) is a
candidate effect warranting replication; smaller differences are reported as
compatible with no detectable effect at this sample size. If four or more of
six runs score below 0.30, stages 1–10 at 2 h is a floor and the budget — not
the conditions — is the finding.

## Exclusion rules

A run may be excluded only if:

- [x] the Docker image or frozen test partition is missing/corrupt before work;
- [x] authentication fails before the first successful model response;
- [x] a confirmed harness implementation defect invalidates measurement;
- [x] other pre-declared rule: the local endpoint is unreachable at the
  chain's preflight, before the run starts — the slot is launched after the
  endpoint returns rather than skipped. An endpoint failure after a run's
  first successful model response is an outcome, not an exclusion.

Do not exclude ordinary model mistakes, compiler build failures, low scores,
compaction failures caused by the trajectory, or documented provider rate
limits.

## Human intervention policy

- No prompts beyond the frozen initial/continuation messages.
- No workspace edits after start.
- No `.env`, configuration, prompt, partition, or script changes for the
  duration of the batch.
- No inspecting hidden results before a run terminates.
- Any unavoidable intervention is logged and the run is analyzed separately.

## Analysis

- Report all runs individually.
- Report median and range; optionally mean and standard deviation.
- Pair each variant run only with the baseline sharing its replicate.
- Do not select the best trajectory as the primary result.
- Qualify claims as task-specific; one model, one task.
- Disclose public-test contamination and the unarchivable local server.
- Post-hoc differential fuzzing (`analysis/fuzz_differential.py`) of final
  snapshots is descriptive follow-up, not part of the frozen primary score.

## Amendments

### 2026-09-02 — harness defect before any completed run; batch restarted

Slot 1 (`v3-tests-none-r1`, launched 2026-09-01T07:20Z) aborted with
`harness_exception` during its round-000 visible evaluation: the in-run
evaluator subprocess had a fixed, uncaught 3600 s ceiling, and a candidate
that hangs the evaluator's 30 s per-test compile timeout on many of the 227
stage-1–10 visible tests legitimately needs longer (the killed evaluation
had processed ~73 tests in its hour). The stages-1–6 batches could not
trigger this. This is exclusion rule 3 (confirmed harness implementation
defect); the aborted run and its materialization are retained under
`runs/.quarantine-v3/` and excluded from all analyses.

Fix, applied before any completed run: the visible-evaluation timeout is now
caught — the evaluator container (now named) is killed and the round is
recorded as unevaluatable (score 0.0 with an explicit error) instead of
aborting the run — and the post-hoc snapshot evaluator gets the same
containment at its 7200 s ceiling, so a timed-out snapshot no longer aborts
the remaining snapshots. No budgets, prompts, partitions, per-test timeouts,
or scoring semantics changed. All six planned in advance slots restart from
scratch under the amended freeze commit so every run in the batch executes
the identical harness. Disclosure: a snapshot whose visible evaluation
exceeds one hour reads as visible 0.0 in trajectory telemetry; the hidden
primary endpoint is evaluated post hoc under the larger ceiling and is
unaffected.

### 2026-09-07 — provenance correction (model file digest)

The GGUF digest and HF snapshot recorded under "Frozen configuration" were
copied from the 2026-08-18 endpoint record. Verified on 2026-09-07: the
llama-server process serving this batch was started on 2026-08-25 10:38 UTC
(after the v2 batch finished) from a re-downloaded snapshot
`4ca720788d1e01f1bff70c033e0d0028fd02e502`, file SHA-256
`3f227079003add2511437e5b1e94812e363385225bf6a9b47b0054a72bc8b01e`
(17,559,178,144 bytes), not `f1bfb127…`/`bee238bb…` (17,923,394,624 bytes).
All six v3 runs and the quarantined attempt executed against the `3f227079…`
file; the server build (`b1-3cb7ffb`) and every client-side setting are as
recorded. Both files are unsloth `UD-Q4_K_XL` quantizations of the same model
but are not byte-identical, so v3 and the v2 batch differ in the served model
file as well as in difficulty. Corrected record:
`runs/local-endpoint-provenance-2026-09-07.json`. No analysis or conclusion in
this document changes; the disclosure is added so that cross-batch
comparisons are qualified correctly.
