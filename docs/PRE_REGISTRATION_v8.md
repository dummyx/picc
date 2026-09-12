# Pre-registration: v8 cohort (pushed test feedback, last-buildable endpoint)

Completed and committed before the first v8 main run. Three cohorts have now
found no effect of test availability (v3, v5, v6) and one no effect of static
typing (v7) on behavioral correctness; the clean cohorts (v6, v7) found that
conditions change the process (turns, self-tests, code size) rather than the
product. v8 asks the last open question on the test factor: does feedback
change anything when the agent cannot decline it? It also fixes the
measurement hazard v7 exposed, by pre-declaring the last buildable snapshot as
the primary snapshot rule.

## Study identity

- Study title: PiCC v8 — pushed test feedback at stages 1–10
  (`tests-pushed` vs `baseline`), last-buildable snapshot endpoint
- Study manifest: `studies/tests/study.json` (`picc-tests-v4`, seed 20260913,
  manifest SHA-256 `4f9ac1aba8b193eec7826dd4eaf866771a83d2c1f8f2974e624bbf13ba1008ec`);
  `baseline` and `tests-none` are byte-identical to the v6 manifest's
  (resolved condition hashes unchanged); `tests-pushed` is `baseline` plus
  `tests.push_interval_minutes = 10`
- Date frozen: 2026-09-12
- Repository commit: `f87d762` (this pre-registration and
  `analysis/v8_results.py` are committed on top; no harness, prompt,
  partition, adapter, or configuration file changes with them)
- Investigator: dummyx

## Research question

Under the frozen harness, budgets, and declared local model, does delivering
the visible-test failure report to the agent unprompted, about every ten
minutes, in addition to the on-demand `test_visible` tool (`tests-pushed`),
change behavioral correctness relative to the on-demand tool alone
(`baseline`) at stages 1–10 under a 2-hour budget, measured by the corpus and
by generated programs on the last buildable snapshot?

Pre-declared from v6 (`analysis/report.md` §12): on-demand tests versus none
gave −0.017 (corpus) and 0.000 (fuzz), with baseline agents calling the tool
13–27 times per run and `tests-none` agents taking about 100 more turns to
write their own tests. The expectation is two-sided and, given three nulls on
this factor, skeptical: the pre-declared secondary endpoints (self-tests,
turns, on-demand calls) are where a difference is expected to show first.

## What changed since v7 (the harness revision, commit `f87d762`)

1. **Pushed feedback** (`tests.push_interval_minutes`): the tools extension's
   `turn_end` hook runs the full visible evaluation once the interval has
   elapsed since the round started or the last report, at the end of any
   turn that continues (one that produced tool calls), and queues the same
   failure-level report the tool would return as a steering user message
   delivered before the next model call. A turn without tool calls is the
   agent stopping; nothing is pushed then. Each report is logged as
   `test_pushed_start`/`test_pushed_end` and counted (`pushed_test_reports`).
   The agent's guidance gains one sentence saying the reports will arrive.
   Baseline's extension carries the same code with the interval at 0.
2. **Last buildable snapshot**: `study-hidden-all` scores the last frozen
   snapshot that built and passed the audit with the fuzz oracle as well
   (second ledger row, `role: last_buildable`) whenever the final snapshot
   did not build; the summarizer verifies both rows and reports
   `hidden_score_last_buildable` and `fuzz_macro_last_buildable` with paired
   deltas. In v7 the round cap fell inside a rewrite in two of eight runs
   (§13.4); this rule scores the compiler the agent had, not the moment the
   cap fell.

Everything else is as in v6: image 0.4 (Pi 0.85.1, bash default timeout),
prompts, specification, partitions, adapter, budgets, model, thinking,
sampling, oracle, fuzz parameters, preflight, audit scope.

## Planned runs

- Number of main repetitions: 4 per condition, 8 runs total. `tests-none`
  is in the manifest for the none / on-demand / pushed gradient but is not
  run: its v6 runs (same image, same conditions) are reported alongside,
  descriptively, never pooled.
- Order: the frozen randomized block order from `study.py schedule` (study
  seed 20260913, replicates 1–4, profile `main`) with the `tests-none` slots
  omitted. Run IDs are the short aliases `v8-<condition>-r<replicate>`; the
  order is binding:
  1. `v8-baseline-r1`
  2. `v8-tests-pushed-r1`
  3. `v8-baseline-r2`
  4. `v8-tests-pushed-r2`
  5. `v8-baseline-r3`
  6. `v8-tests-pushed-r3`
  7. `v8-baseline-r4`
  8. `v8-tests-pushed-r4`
- Slots run sequentially through one chain driver: endpoint preflight
  (abort on mismatch), run, `study-hidden-all` (corpus for every snapshot,
  fuzz for the final and, if different, the last buildable one),
  `study-report`, next slot; `study-summary` at the end.
- Pilot runs, excluded from every analysis: `v8-pilot-tests-pushed-smoke1`
  and `v8-pilot-baseline-smoke1` (pilot profile, 0.4 h wall, 12-minute round
  cap, 2 rounds, stages 1–3), run on image 0.4 with this harness before the
  freeze to exercise the push hook, the shared evaluator path, both oracles,
  and the report end to end.

## Frozen configuration

- Docker image ID: `sha256:2e4e4dc58548e6566eed393082b9be049cc41422dd36c35f00f576d818d9a555`
  (`picc-experiment:0.4`, unchanged from v6 and v7)
- Pi version: `@earendil-works/pi-coding-agent@0.85.1`; bash default timeout
  `@cad0p/pi-bash-timeout@0.1.0`; Rust toolchain `1.88.0`
- Provider/model: `local` — llama.cpp `llama-server` build `b1-3cb7ffb`
  serving `unsloth/Qwen3.8-27B-GGUF:UD-Q4_K_XL`; served GGUF SHA-256
  `3f227079003add2511437e5b1e94812e363385225bf6a9b47b0054a72bc8b01e`
  (the same file as v3–v7; verified by `make preflight` before each slot);
  4 server slots, 131072 context; single RTX 5090
- Thinking setting: `high`; sampling pinned client-side
  (`temperature 1.0, top_p 0.95, top_k 20, min_p 0`); `LOCAL_MAX_OUTPUT=65536`
- Test repository revision: `ae12014d2dec14488f3f80d14df4b6d8e4634d7d`
- Visible manifest SHA-256 (source): `bb5410a9ae1d0cfe904d5316828791b04e77dca4fb459601877ce9e927029a6f`
  (227 tests); hidden: `49960548e8ce2353990fc39bd91536166df37e14c62dd33acd27afccef01faef`
  (104 tests); unchanged since v3
- Candidate adapter: `studies/assets/candidates/rust-std.json`
  (SHA-256 `69aa13ffba00fff0a147a83c36b5fbdceceddd46c41ae89e6bf928c154578588`)
- Resolved condition SHA-256: `baseline`
  `d9ba1f5e5b28fc185ef2173594cf5b77f9caa7a44f0ac268cb7ca711e7f5e055` (identical
  to v3, v5, v6), `tests-pushed`
  `d7a1a33c655fefe1955f2de24aa3f51a8c0c496f963b4644a1cfdc65e69aaad3`
- Prompts and specification: byte-identical to v6 for `baseline`; for
  `tests-pushed`, `AGENTS.md` differs only by the sentence announcing the
  pushed reports (rendered from `studies/assets/prompts/agents-baseline.md`)
- Pi settings: `pi/settings.json` as v6
- `.env` overrides other than credentials: as v6; effective main budget 2 h
  wall, 30 rounds, 45-min round cap, stages 1–10, two consecutive stalls
  terminal
- Fuzz-oracle configuration (defaults, frozen per materialization):
  `FUZZ_STAGE_PROGRAMS=100`, `FUZZ_SEED_BASE=20260830`,
  `FUZZ_RUN_TIMEOUT_SECONDS=3`, `FUZZ_COMPILE_TIMEOUT_SECONDS=10`,
  `FUZZ_DEADLINE_SECONDS=5400`

## Primary endpoints (co-primary), on the last buildable snapshot

1. Hidden macro score (corpus oracle) of the last buildable snapshot: the
   last frozen snapshot whose hidden evaluation built and passed the audit;
   the final snapshot when it built; 0 when no snapshot built.
2. Fuzz macro (generated-program oracle) of the same snapshot.

The primary contrast for each is `tests-pushed` − `baseline`, paired by
replicate identifier. Each endpoint is reported with its own paired median and
per-replicate deltas; they are not combined into one number. The same two
oracles on the **final snapshot** (the v6/v7 rule) are reported alongside as
secondary endpoints for comparability; when the two rules disagree for a
run, the run is listed with both values and the reason.

## Secondary endpoints

Selected before running:

- [x] final-snapshot corpus and fuzz scores (comparability with v6/v7), and
  the number of runs whose final snapshot did not build
- [x] final hidden micro score; hidden score/time AUC; visible–hidden gap
- [x] per-stage fuzz pass rates and mismatch kinds
- [x] buildable snapshot fraction; compactions; guard-blocked calls
- [x] **harness check** (v6 form): idle minutes per run (expected below 5),
  bash calls that never returned (expected 0), commands cut by the default
  timeout
- [x] **treatment fidelity:** pushed reports delivered per run (expected
  about 8 per 90-minute run at a 10-minute interval, fewer if evaluations
  are slow), their timing, and the visible score each carried; on-demand
  `test_visible` calls per run in both arms (does pushing displace asking?)
- [x] **resources, paired:** output and input tokens, active and idle
  minutes, assistant turns, tool calls
- [x] **code, paired, descriptive:** source LOC and function count,
  self-written test programs and their LOC, source churn, final build time,
  median per-test compile time
- [x] **distribution shape:** runs with fuzz macro below 0.9 on each rule
- [x] completion per study manifest: hidden macro ≥ 0.95 with successful
  build and no blocking audit finding (final-snapshot rule, as before)

## Interpretation rule

Report all eight runs individually, then per-condition median and range for
both primary endpoints. For each endpoint separately: a paired median
difference with magnitude greater than 0.13 is a candidate effect warranting
replication; a smaller difference is compatible with no detectable effect at
this sample size. For the fuzz macro the paired median is reported alongside
the number of replicates whose difference exceeds 0.13 in the same direction;
three of four in one direction is treated as consistent with the corpus
verdict, two of four as unresolved. If six or more of eight runs score below
0.30 on the corpus oracle, the budget rather than the conditions is the
finding. Resource, fidelity, and code endpoints are reported as paired
medians with per-replicate values and no threshold. If any run idles for
five minutes or more, or if a `tests-pushed` run received no pushed report,
the harness check failed for that run and the reason is reported before any
contrast is read.

## Exclusion rules

A run may be excluded only if:

- [x] the Docker image or frozen test partition is missing/corrupt before work;
- [x] authentication fails before the first successful model response;
- [x] a confirmed harness implementation defect invalidates measurement
  (handled, as in v6 Amendment 2, by a logged amendment and an identical
  post-hoc re-score of every affected snapshot rather than by exclusion
  wherever the defect is in the measurement layer);
- [x] the preflight reports the endpoint unreachable before the run starts —
  the slot is launched after the endpoint returns rather than skipped. A
  preflight *mismatch* aborts the cohort instead.

Do not exclude ordinary model mistakes, build failures, low scores, fuzz
failures, compaction failures caused by the trajectory, guard blocks,
commands cut by the default timeout, or a final snapshot cut by the cap
(that is what the primary snapshot rule is for).

## Human intervention policy

- No prompts beyond the frozen initial/continuation messages and the pushed
  reports the condition itself generates.
- No workspace edits after start.
- No `.env`, configuration, prompt, partition, adapter, settings, image, or
  script changes for the duration of the cohort.
- No inspecting hidden or fuzz results before a run terminates.
- Any unavoidable intervention is logged and the run is analyzed separately.

## Analysis

- `analysis/v8_results.py`: all runs individually, both snapshot rules and
  both oracles, paired contrasts, the harness check, pushed-report counts,
  and the paired resource/code secondary endpoints, with the v6 `baseline`
  and `tests-none` rows alongside for the gradient (never pooled);
  `make study-summary STUDY=studies/tests/study.json` for the
  provenance-checked aggregation.
- Report median and range; optionally mean and standard deviation.
- Pair each `tests-pushed` run only with the `baseline` run sharing its
  replicate.
- Do not select the best trajectory as the primary result.
- Qualify claims as task-specific; one model, one task, one language.
- Disclose public-test contamination and the unarchivable local server.

## Pilot evidence (before the freeze)

Both pilots ran to their 0.4 h budget on 2026-09-12 (12:37–13:01 UTC and
13:01–13:25 UTC) on image 0.4 with this harness (commit `f87d762`), two
12-minute rounds each, stages 1–3, after the validation suite (163 tests,
including the new two-row ledger, stray-row, legacy-ledger, interval, and
rendering cases) and the evaluator smoke passed. They are excluded from every
analysis; what they establish:

- `v8-pilot-tests-pushed-smoke1`: two pushed reports were delivered, one per
  round, at a turn boundary once ten minutes had elapsed (12:48:11, build
  failing, score 0; 12:59:30, score 1.0); each appears in the session as a
  user message and the agent's next turn acted on it ("Build is failing (no
  `main.rs` yet…). Let me clean those up and add the driver"). The agent also
  called `test_visible` once on its own. Hidden 1.0 (19/19), fuzz 1.0 at
  stages 1–3 in 24 minutes; two commands cut by the default timeout and
  recovered; one guard block; no malformed events. The fuzz ledger carries
  the `role: final` row and the report the new fields.
- `v8-pilot-baseline-smoke1`: the same extension with the interval at 0
  pushed nothing; the agent never called `test_visible` in its 24 minutes
  (21 bash calls, all self-testing); hidden 1.0 (19/19), fuzz 0.88 (stages
  1.00 / 0.83 / 0.81); one command cut by the default timeout and one guard
  block (a direct `gcc` attempt); no malformed events. (Corrected on
  2026-09-12 13:30 UTC, during run 1, from a draft that had said the agent
  called the tool and needed no cut-off; the numbers above are from the
  run's report.)
- The last-buildable path with a second ledger row cannot be forced in a
  pilot (both finals built); it is covered by the summarizer tests and will
  first exercise on a real cap-cut run.

No harness change followed the pilots.

## Amendments

(none yet)
