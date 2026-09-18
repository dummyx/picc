# Experiment plan: v5 batch (test availability, revised oracle)

Completed and committed before the first v5 main run. The v3 batch tested the
same contrast under the previous oracle (`docs/EXPERIMENT_PLAN.md`); v5 is a
fresh batch under a separate study manifest, not additional replicates of v3,
because the harness revision below changes what the task measures.

## Study identity

- Study title: PiCC v5 — test availability at stages 1–10 under the revised
  oracle (`tests-none` vs `baseline`)
- Study manifest: `studies/tests/study.json` (`picc-tests-v2`, seed 20260910);
  both conditions are byte-identical to the starter's `baseline` and
  `tests-none`
- Date frozen: 2026-09-10
- Repository commit: `e6e79f6102c5190076e8d126b934eedd95156725` (this experiment plan is committed on
  top; no harness, prompt, partition, adapter, or configuration file changes
  with it)
- Investigator: dummyx

## Research question

Under the frozen harness, budgets, and declared local model, does withholding
all agent-visible tests and scores (`tests-none`) change behavioral
correctness relative to `baseline` (failure-level `test_visible` tool access)
when the task is stages 1–10 under a 2-hour budget, measured by two oracles:
the corpus (hidden macro score) and generated programs (fuzz macro)?

Pre-declared from v3 and the 2026-09-09 re-score (`analysis/report.md` §7,
§9): under the corpus oracle v3 found a candidate effect of −0.136 (paired
median, n=3, one replicate reversed); under the fuzz oracle the same finals
gave −0.238, with two of three `tests-none` compilers deeply wrong on ordinary
arithmetic and logic. The pre-declared expectation is therefore directional
(`tests-none` worse), but the interpretation rule below is two-sided.

## What changed since v3 and v4 (the harness revision)

Applied before any v5 run, all frozen in the harness commit:

1. **Candidate inputs are preprocessed** (`gcc -E -P -C -nostdinc`), as the
   upstream test suite's driver does before invoking a compiler. Ten hidden
   and eighteen visible tests begin with `#ifdef SUPPRESS_WARNINGS` blocks
   that the specification never mentions; in v2–v4 they measured an unstated
   rule about `#` lines (five of six v4 compilers lost the same ten tests).
   Verified on all 331 corpus files: every file preprocesses, valid tests keep
   identical reference behavior, invalid tests stay invalid, the tests' own
   comments survive. The GCC reference compile still uses the original file.
2. **The fuzz oracle is part of the frozen harness** and a co-primary
   endpoint: `studies/runtime/fuzz_evaluate.py` runs inside the evaluator
   container on the final snapshot after the hidden evaluation, with the
   generator shared with `analysis/fuzz_differential.py`. Parameters, frozen
   in the materialized configuration: 100 programs per stage, seed
   `20260830 + stage`, 3 s per program run, 10 s per candidate compile, 5400 s
   deadline (a stage not reached scores 0; a stage cut short scores on its
   evaluated programs only if at least 20 were evaluated). The summarizer
   verifies the ledger against the final snapshot, image, adapter, and stage
   budget, recomputes the macro from the per-stage rates, and pairs
   `delta_fuzz_macro` like the corpus delta.
3. **Provenance guards:** the base image is pinned by digest for future builds
   (`node:24.20.0-bookworm-slim@sha256:ba849c60…`; image 0.2 itself is
   unchanged and is the image used here), and `make preflight` hashes the file
   the endpoint reports serving and refuses to proceed unless it matches
   `LOCAL_MODEL_SHA256`; the run's `model.serving_revision` records the digest.
   The chain driver runs the preflight before every slot and aborts the
   batch on a mismatch (a wrong substrate is never an outcome).

Everything else is as in v3: prompts, specification, partitions, adapter,
budgets, model, thinking, sampling.

## Planned runs

- Number of main repetitions: 4 per condition, 8 runs total (the pre-declared
  n=3 resolution of 0.13 did not separate replicate-level noise from the v3
  effect; a fourth replicate is the cheapest improvement).
- Order: the frozen randomized block order from `study.py schedule` (study
  seed 20260910, replicates 1–4, profile `main`). Run IDs are the short
  aliases `v5-<condition>-r<replicate>` of the schedule's
  `picc-tests-v2-main-r0N-<condition>` entries; the order is binding:
  1. `v5-baseline-r1`
  2. `v5-tests-none-r1`
  3. `v5-tests-none-r2`
  4. `v5-baseline-r2`
  5. `v5-tests-none-r3`
  6. `v5-baseline-r3`
  7. `v5-baseline-r4`
  8. `v5-tests-none-r4`
- Slots run sequentially through one chain driver: endpoint preflight
  (`make preflight`, abort on mismatch), run, `study-hidden-all` (corpus for
  every snapshot, fuzz for the final one), `study-report`, next slot;
  `study-summary STUDY=studies/tests/study.json` at the end.
- Pilot runs, excluded from every analysis: `v5-pilot-baseline-smoke1` and
  `v5-pilot-tests-none-smoke1` (pilot profile, 0.4 h wall, 12-minute round
  cap, 2 rounds, stages 1–3), executed before this freeze to exercise
  preprocessing, the in-harness fuzz oracle, and the summarizer end to end.
  Their outcomes are infrastructure evidence only (see below).

## Frozen configuration

- Docker image ID: `sha256:02ed179c48680acd707217505409660080a6e68c2022711754e3ba70cb32a71d`
  (`picc-experiment:0.2`, unchanged from v4; Node.js v24.20.0, TypeScript
  5.9.3 present and unused by this batch's Rust candidates)
- Pi version: `@earendil-works/pi-coding-agent@0.84.1`; Rust toolchain `1.88.0`
- Provider/model: `local` — llama.cpp `llama-server` build `b1-3cb7ffb`
  serving `unsloth/Qwen3.8-27B-GGUF:UD-Q4_K_XL`; served GGUF SHA-256
  `3f227079003add2511437e5b1e94812e363385225bf6a9b47b0054a72bc8b01e`
  (HF snapshot `4ca720788d1e01f1bff70c033e0d0028fd02e502`; the same file as
  v3 and v4; verified by `make preflight` on 2026-09-10 and pinned as
  `LOCAL_MODEL_SHA256`); single RTX 5090
- Thinking setting: `high`; sampling pinned client-side
  (`temperature 1.0, top_p 0.95, top_k 20, min_p 0`)
- Test repository revision: `ae12014d2dec14488f3f80d14df4b6d8e4634d7d`
- Visible manifest SHA-256 (source): `bb5410a9ae1d0cfe904d5316828791b04e77dca4fb459601877ce9e927029a6f`
  (227 tests); hidden: `49960548e8ce2353990fc39bd91536166df37e14c62dd33acd27afccef01faef`
  (104 tests); both unchanged since v3 (preprocessing happens at evaluation
  time, the partitions themselves are untouched)
- Candidate adapter: `studies/assets/candidates/rust-std.json`
  (SHA-256 `69aa13ffba00fff0a147a83c36b5fbdceceddd46c41ae89e6bf928c154578588`,
  unchanged since v3)
- Resolved condition SHA-256: `baseline`
  `d9ba1f5e5b28fc185ef2173594cf5b77f9caa7a44f0ac268cb7ca711e7f5e055`, `tests-none`
  `98a50811588544a69e00874cb4f07f6bcf803b2a4608e9a85ea6127fd94e86ce` (identical to
  the v3 runs' resolved conditions)
- Prompts and specification: byte-identical to v3 for both conditions
- `.env` overrides other than credentials: as v3 plus
  `LOCAL_MODEL_SHA256=3f227079…`; effective main budget 2 h wall, 30 rounds,
  45-min round cap, stages 1–10, two consecutive stalls terminal
- Fuzz-oracle configuration (defaults, frozen per materialization):
  `FUZZ_STAGE_PROGRAMS=100`, `FUZZ_SEED_BASE=20260830`,
  `FUZZ_RUN_TIMEOUT_SECONDS=3`, `FUZZ_COMPILE_TIMEOUT_SECONDS=10`,
  `FUZZ_DEADLINE_SECONDS=5400`

## Primary endpoints (co-primary)

1. Final hidden macro score (corpus oracle), averaged equally across stages
   and, within each stage, across valid and invalid classes.
2. Final-snapshot fuzz macro (generated-program oracle), the equal-weight mean
   over stages 1–10 of the per-stage agreement rate with GCC.

The primary contrast for each is `tests-none` − `baseline`, paired by
replicate identifier. Each endpoint is reported with its own paired median and
per-replicate deltas; they are not combined into one number.

## Secondary endpoints

Selected before running:

- [x] final hidden micro score
- [x] hidden score/time AUC (all snapshots evaluated)
- [x] visible–hidden gap
- [x] per-stage fuzz pass rates and mismatch kinds (which stages break, and how)
- [x] buildable snapshot fraction
- [x] compaction count, truncated thinking turns
- [x] reported input/output tokens
- [x] tool-call distribution (including `test_visible` and self-test shell use)
- [x] guard-blocked calls
- [x] Rust LOC/churn (descriptive only)
- [x] completion per study manifest: hidden macro ≥ 0.95 with successful build
  and no blocking audit finding
- [x] descriptive bridge to v3: the six v3 finals re-scored under the revised
  corpus oracle (preprocessed inputs) and the in-harness fuzz oracle, reported
  next to v5 but never pooled with it

## Interpretation rule

Report all eight runs individually, then per-condition median and range for
both endpoints. For each endpoint separately: a paired median difference with
magnitude greater than 0.13 is a candidate effect warranting replication; a
smaller difference is compatible with no detectable effect at this sample
size. The fuzz macro is bimodal in the re-score (a compiler is either perfect
or broken on a stage), so its paired median is reported alongside the number of
replicates whose difference exceeds 0.13 in the same direction; three of four
in one direction is treated as consistent with the corpus verdict, two of four
as unresolved. If six or more of eight runs score below 0.30 on the corpus
oracle, the budget rather than the conditions is the finding.

## Exclusion rules

A run may be excluded only if:

- [x] the Docker image or frozen test partition is missing/corrupt before work;
- [x] authentication fails before the first successful model response;
- [x] a confirmed harness implementation defect invalidates measurement;
- [x] the preflight reports the endpoint unreachable before the run starts —
  the slot is launched after the endpoint returns rather than skipped. A
  preflight *mismatch* (a different model file) aborts the batch instead; it
  cannot produce an includable run. An endpoint failure after a run's first
  successful model response is an outcome, not an exclusion.

Do not exclude ordinary model mistakes, compiler build failures, low scores,
fuzz failures, compaction failures caused by the trajectory, or guard blocks.

## Human intervention policy

- No prompts beyond the frozen initial/continuation messages.
- No workspace edits after start.
- No `.env`, configuration, prompt, partition, adapter, or script changes for
  the duration of the batch.
- No inspecting hidden or fuzz results before a run terminates.
- Any unavoidable intervention is logged and the run is analyzed separately.

## Analysis

- Report all runs individually, both endpoints.
- Report median and range; optionally mean and standard deviation.
- Pair each `tests-none` run only with the `baseline` run sharing its replicate
  (`make study-summary STUDY=studies/tests/study.json`).
- Do not select the best trajectory as the primary result.
- Qualify claims as task-specific; one model, one task.
- Disclose public-test contamination and the unarchivable local server.

## Pilot evidence (before the freeze)

Both pilots ran to their 0.4 h budget on 2026-09-10 (04:53–05:17 UTC and
05:17–05:41 UTC), two rounds each, stages 1–3, under the final harness, after
the Docker smoke test passed its five checks (Rust, TypeScript, and JavaScript
mocks through the study evaluator with a `#ifdef`-prefixed fixture, the type
gate, and the fuzz oracle). They are excluded from every analysis; what they
establish:

- The preflight verified the served model file (SHA-256 `3f227079…`, hashed in
  7 s, cached thereafter) before each pilot, and each run's metadata records
  `model.serving_revision = gguf-sha256:3f227079…`.
- Every corpus evaluation (in-run visible and post-hoc hidden) records
  `input_policy` with the preprocessing command and zero raw fallbacks.
- `v5-pilot-baseline-smoke1`: hidden 1.0 (19/19 at stages 1–3), clean audit;
  the fuzz oracle ran on the final snapshot in 7.6 s and scored 0.913
  (stages 1.00 / 1.00 / 0.74; 26 wrong results at stage 3, all SIGFPE on
  nested `%`/`/`), i.e. a compiler the stage-1–3 corpus rates perfect and the
  fuzzer already faults, the pattern the 2026-09-09 re-score found in v3.
- `v5-pilot-tests-none-smoke1`: the agent wrote a lexer but no `main.rs`
  within the budget, so no snapshot built; corpus 0.0 and fuzz 0.0 with
  reason `build_failure` on every stage, consistently. This is the
  no-compiler path of both oracles, not a defect.
- `study-hidden-all`, `study-report` (with the new fuzz section), and the
  single-row fuzz ledger verified by the summarizer's checks were exercised;
  `study-summary` correctly reports both pilots as excluded by profile.

No harness change followed the pilots.

## Amendments

(none yet)
