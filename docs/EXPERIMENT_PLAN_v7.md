# Experiment plan: v7 batch (static typing under the revised harness)

Completed and committed before the first v7 main run. v4 tested the same
contrast (`docs/EXPERIMENT_PLAN_v4.md`) on image 0.2 under the original
corpus oracle, without the fuzz oracle, and without a bound on the agent's
shell commands; it found no effect at n=3, but two of its six runs lost
34–45 minutes to hangs and five of its six compilers lost the same ten
hidden tests to the `#ifdef` preprocessing artifact (`analysis/report.md`
§8, §9, §10.4b). v7 is a fresh batch under a separate study manifest with
those three defects removed and one more replicate; it is not additional
replicates of v4. It is the first re-test of the project's original question
("does static typing change what the agent builds?") on a harness whose
variance is known to be small (§12).

## Study identity

- Study title: PiCC v7 — static typing at stages 1–10 under the revised
  oracle and the bash default timeout (`ts-strict` vs `js-untyped`)
- Study manifest: `studies/types/study.json` (`picc-types-v2`, seed 20260912,
  manifest SHA-256 `92ca93778d443dd3855d9dd96f2d24bbf6705f207b6634dc8d7c359df41acec4`);
  both conditions are byte-identical to the v4 manifest's (resolved condition
  hashes unchanged); only the manifest id, seed, and description changed
- Date frozen: 2026-09-11
- Repository state: this experiment plan, the manifest version bump, and
  `analysis/v7_results.py` are committed on top; no harness, prompt,
  partition, adapter, or configuration file changes with them
- Investigator: dummyx

## Research question

Under the frozen harness, budgets, and declared local model, does requiring
the agent to build the compiler in TypeScript under `tsc --strict` (a build
that fails on any type error) change behavioral correctness relative to
building it in plain JavaScript on the same Node.js runtime, at stages 1–10
under a 2-hour budget, measured by the corpus (hidden macro score) and by
generated programs (fuzz macro)?

Pre-declared from v4 (§8, §10.4b): paired median +0.026 on the original
corpus and 0.000 under both revised oracles, n=3, with the typed arm costing
+54% source lines and +9% output tokens for the same correctness (§11). No
direction is predicted. The v4 typed compilers rejected two-argument calls at
stage 9 in two of three runs, which the corpus missed and the fuzzer found;
whether that recurs is a pre-declared secondary question.

## What changed since v4 (the harness revision)

All frozen before any v7 run:

1. **Revised oracle** (v5 harness): candidate inputs are
   preprocessed (`gcc -E -P -C -nostdinc`), removing the `#ifdef` artifact that
   cost five of six v4 compilers the same ten hidden tests; the fuzz macro is
   computed in-harness on the final snapshot and is a co-primary endpoint;
   `make preflight` verifies the served model file before every slot.
2. **Pi 0.84.1 → 0.85.1** (image 0.3) and the **bash default timeout**
   (image 0.4, `@cad0p/pi-bash-timeout@0.1.0`, 120 s when the agent sets
   none, loaded from the frozen `pi/settings.json`). In v6 this removed the
   hang hazard completely: eight of eight runs used their full budget, and
   the corpus spread fell from 0.50 to 0.08 (§12.2).
3. **Audit scope**: the Rust audit is now scoped like the
   Node audit already was since v4. Irrelevant to this batch's candidates
   except that both arms' audits are the v4 ones (declared roots `src/`,
   entry-module import closure, `dist/` excluded for TypeScript).

Everything else is as in v4: prompts (typing notes appended per adapter),
specification (language line only), partitions, budgets, model, thinking,
sampling, `tsc --strict --noEmitOnError` build for `ts-strict`,
`node --check` for `js-untyped`, `tsc` withheld by the guard in `js-untyped`.

## Planned runs

- Number of main repetitions: 4 per condition, 8 runs total (v4 had 3).
- Order: the frozen randomized block order from `study.py schedule` (study
  seed 20260912, replicates 1–4, profile `main`). Run IDs are the short
  aliases `v7-<condition>-r<replicate>` of the schedule's
  `picc-types-v2-main-r0N-<condition>` entries; the order is binding:
  1. `v7-ts-strict-r1`
  2. `v7-js-untyped-r1`
  3. `v7-js-untyped-r2`
  4. `v7-ts-strict-r2`
  5. `v7-ts-strict-r3`
  6. `v7-js-untyped-r3`
  7. `v7-ts-strict-r4`
  8. `v7-js-untyped-r4`
- Slots run sequentially through one chain driver: endpoint preflight
  (abort on mismatch), run, `study-hidden-all` (corpus for every snapshot,
  fuzz for the final one), `study-report`, next slot;
  `study-summary STUDY=studies/types/study.json` at the end.
- Pilot runs, excluded from every analysis: `v7-pilot-ts-strict-smoke1` and
  `v7-pilot-js-untyped-smoke1` (pilot profile, 0.4 h wall, 12-minute round
  cap, 2 rounds, stages 1–3), run on image 0.4 before this freeze to
  exercise Pi 0.85.1 + the timeout package + `tsc` + the Node audit +
  both oracles end to end. Their outcomes are infrastructure evidence only.

## Frozen configuration

- Docker image ID: `sha256:2e4e4dc58548e6566eed393082b9be049cc41422dd36c35f00f576d818d9a555`
  (`picc-experiment:0.4`; Node.js v24.20.0, TypeScript 5.9.3,
  `@types/node@24.13.3`, Pi 0.85.1, `@cad0p/pi-bash-timeout@0.1.0`; Rust
  1.88.0 present, unused; base image `node:24.20.0-bookworm-slim@sha256:ba849c60…`)
- Provider/model: `local` — llama.cpp `llama-server` build `b1-3cb7ffb`
  serving `unsloth/Qwen3.8-27B-GGUF:UD-Q4_K_XL`; served GGUF SHA-256
  `3f227079003add2511437e5b1e94812e363385225bf6a9b47b0054a72bc8b01e`
  (the same file as v3–v6; verified by `make preflight` before each slot and
  pinned as `LOCAL_MODEL_SHA256`); 4 server slots, 131072 context; single
  RTX 5090
- Thinking setting: `high`; sampling pinned client-side
  (`temperature 1.0, top_p 0.95, top_k 20, min_p 0`); `LOCAL_MAX_OUTPUT=65536`
- Test repository revision: `ae12014d2dec14488f3f80d14df4b6d8e4634d7d`
- Visible manifest SHA-256 (source): `bb5410a9ae1d0cfe904d5316828791b04e77dca4fb459601877ce9e927029a6f`
  (227 tests); hidden: `49960548e8ce2353990fc39bd91536166df37e14c62dd33acd27afccef01faef`
  (104 tests); unchanged since v3
- Candidate adapters: `studies/assets/candidates/typescript-strict.json`
  (SHA-256 `973886d5f6c3217a75b4de6d99241e99c80072391f3ee32db395146ebc9a6aaa`)
  and `studies/assets/candidates/javascript-node.json`
  (SHA-256 `6484a419dc82bbdaf918d7ac1b68588935b216c601008d6c58f39f34454c520d`),
  unchanged since the v4 restart
- Resolved condition SHA-256: `ts-strict`
  `d722f7516eda006501cfff9a3f87eaa6ce98822b7f63198c4eddbcfaeb4c9457`, `js-untyped`
  `35b58f1cccfeec87951781038acf27ec68575126cfcb882afb18b3e724b783e7` (identical
  to v4)
- Pi settings: `pi/settings.json` as v6 (`packages` entry for the timeout
  package)
- `.env` overrides other than credentials: as v6; effective main budget 2 h
  wall, 30 rounds, 45-min round cap, stages 1–10, two consecutive stalls
  terminal
- Fuzz-oracle configuration (defaults, frozen per materialization):
  `FUZZ_STAGE_PROGRAMS=100`, `FUZZ_SEED_BASE=20260830`,
  `FUZZ_RUN_TIMEOUT_SECONDS=3`, `FUZZ_COMPILE_TIMEOUT_SECONDS=10`,
  `FUZZ_DEADLINE_SECONDS=5400`

## Primary endpoints (co-primary)

1. Final hidden macro score (corpus oracle), averaged equally across stages
   and, within each stage, across valid and invalid classes.
2. Final-snapshot fuzz macro (generated-program oracle), the equal-weight mean
   over stages 1–10 of the per-stage agreement rate with GCC.

The primary contrast for each is `ts-strict` − `js-untyped`, paired by
replicate identifier. Each endpoint is reported with its own paired median and
per-replicate deltas; they are not combined into one number.

## Secondary endpoints

Selected before running:

- [x] final hidden micro score; hidden score/time AUC; visible–hidden gap
- [x] per-stage fuzz pass rates and mismatch kinds; in particular whether
  `ts-strict` compilers again reject valid multi-argument calls at stage 9
- [x] buildable snapshot fraction, and for `ts-strict` the fraction of
  unbuildable snapshots whose build output carries TypeScript diagnostics
  (`error TS`), i.e. snapshots lost to the type gate
- [x] compaction count; guard-blocked calls, separately counting `tsc`
  attempts in `js-untyped`
- [x] treatment fidelity, descriptive (`analysis/typing_metrics.py`): in
  `ts-strict`, counts of `any`, `unknown`, `as` casts, non-null assertions,
  `@ts-*` suppressions, declared interfaces/type aliases, share of function
  declarations with explicit return types; in `js-untyped`, JSDoc type tags,
  `// @ts-check`, `.ts` files; in both arms, bash invocations of `tsc`,
  `node --check`, and direct compiler runs
- [x] **harness check** (as v6, Amendment 1 form): idle minutes per run
  (expected below 5 in every run; v4: two of six idled 34–45) and bash calls
  that never returned, alongside commands cut by the default timeout
- [x] **resources, paired like the primary endpoints:** output and input
  tokens, active and idle minutes, assistant turns, tool calls
- [x] **code, paired, descriptive:** source LOC by adapter extension and
  function count (not comparable to Rust; comparable between the two arms
  only with the §11 caveat that the regexes count TypeScript and JavaScript
  functions alike), self-written test programs and their LOC, source churn,
  final build time and median per-test compile time
- [x] **distribution shape:** number of runs with fuzz macro below 0.9
  (v4 under the re-score: 1 of 6)
- [x] completion per study manifest: hidden macro ≥ 0.95 with successful build
  and no blocking audit finding

## Interpretation rule

Report all eight runs individually, then per-condition median and range for
both endpoints. For each endpoint separately: a paired median difference with
magnitude greater than 0.13 is a candidate effect warranting replication; a
smaller difference is compatible with no detectable effect at this sample
size. For the fuzz macro the paired median is reported alongside the number
of replicates whose difference exceeds 0.13 in the same direction; three of
four in one direction is treated as consistent with the corpus verdict, two
of four as unresolved. If six or more of eight runs score below 0.30 on the
corpus oracle, the budget rather than the conditions is the finding. Resource
and code secondary endpoints are reported as paired medians with
per-replicate values and no threshold; they describe cost at a given
correctness, not correctness. If any run idles for five minutes or more, the
harness check failed for that run and the reason is reported before any
contrast is read.

## Exclusion rules

A run may be excluded only if:

- [x] the Docker image or frozen test partition is missing/corrupt before work;
- [x] authentication fails before the first successful model response;
- [x] a confirmed harness implementation defect invalidates measurement
  (handled, as in v6 Amendment 2, by a logged amendment and an identical
  post-hoc re-score of every final snapshot rather than by exclusion
  wherever the defect is in the measurement layer);
- [x] the preflight reports the endpoint unreachable before the run starts —
  the slot is launched after the endpoint returns rather than skipped. A
  preflight *mismatch* aborts the batch instead.

Do not exclude ordinary model mistakes, type-gate build failures, low scores,
fuzz failures, compaction failures caused by the trajectory, guard blocks, or
commands cut by the default timeout.

## Human intervention policy

- No prompts beyond the frozen initial/continuation messages.
- No workspace edits after start.
- No `.env`, configuration, prompt, partition, adapter, settings, image, or
  script changes for the duration of the batch.
- No inspecting hidden or fuzz results before a run terminates.
- Any unavoidable intervention is logged and the run is analyzed separately.

## Analysis

- `analysis/v7_results.py`: all runs individually, both endpoints, paired
  contrasts, the harness check, `tsc` fidelity counts, and the paired
  resource/code secondary endpoints, with v4 alongside for the harness check
  (never pooled); `analysis/typing_metrics.py` for treatment fidelity;
  `make study-summary STUDY=studies/types/study.json` for the
  provenance-checked aggregation.
- Report median and range; optionally mean and standard deviation.
- Pair each `ts-strict` run only with the `js-untyped` run sharing its
  replicate.
- Do not select the best trajectory as the primary result.
- Qualify claims as task-specific; one model, one task, two languages on one
  runtime.
- Disclose public-test contamination and the unarchivable local server.

## Pilot evidence (before the freeze)

Both pilots ran to their 0.4 h budget on 2026-09-11 (20:44–21:08 UTC and
21:08–21:32 UTC) on image 0.4, two 12-minute rounds each, stages 1–3, after
the validation suite (151 tests), evaluator smoke (five checks including the
TypeScript and JavaScript mocks and the type gate), model preflight, and a
live request through the image passed. They are excluded from every
analysis; what they establish:

- `v7-pilot-ts-strict-smoke1`: the `tsc --strict --noEmitOnError` build
  gate, the Node audit (7 source files under `src/` scanned, `dist/`
  excluded, clean), preprocessing, both oracles, and the report work under
  Pi 0.85.1 with the timeout package loaded; hidden 0.847 (16/19) and fuzz
  0.837 (stages 1.00 / 0.91 / 0.60; 26 valid programs rejected, 23 wrong
  results) at stages 1–3 in 24 minutes; one guard block (an evaluator-path
  probe); no cut-off needed; no malformed events.
- `v7-pilot-js-untyped-smoke1`: the `node --check` build, the JavaScript
  audit (1 source file, clean), both oracles, and the report likewise;
  hidden 0.750 (14/19) and fuzz 0.827 (1.00 / 0.85 / 0.63; 52 assembly
  failures); one guard block (a write outside `/workspace`); no `tsc`
  attempt; no cut-off needed; no malformed events.
- Both agents worked to the cap in both rounds (no idle time), as in v6.

No harness change followed the pilots.

## Amendments

(none yet)
