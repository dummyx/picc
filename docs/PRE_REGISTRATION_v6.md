# Pre-registration: v6 cohort (test availability under the bash default timeout)

Completed and committed before the first v6 main run. v5 tested the same
contrast under the revised oracle (`docs/PRE_REGISTRATION_v5.md`) and found no
replicable effect, but its outcome distribution was bimodal and the mode was
set by a condition-blind hazard: an agent bash command that never returned
(a self-test running a program its own compiler had miscompiled into an
infinite loop) blocked the session until the round cap. v6 is a fresh cohort
under a separate study manifest with that hazard removed; it is not additional
replicates of v5.

## Study identity

- Study title: PiCC v6 — test availability at stages 1–10 under the revised
  oracle and the bash default timeout (`tests-none` vs `baseline`)
- Study manifest: `studies/tests/study.json` (`picc-tests-v3`, seed 20260911,
  manifest SHA-256 `fcf03ec77d9dbb82939cbe6840532e40a1ac28d8243727bc53545878a6a17614`);
  both conditions are byte-identical to the starter's `baseline` and
  `tests-none` and to the v5 manifest's; only the manifest id, seed, and
  description changed
- Date frozen: 2026-09-11
- Repository commit: `4703d83f84c7973203f02a5ac83e3710437ddc24` (this
  pre-registration, the manifest version bump, and `analysis/v6_results.py`
  are committed on top; no harness, prompt, partition, adapter, or
  configuration file changes with them)
- Investigator: dummyx

## Research question

Under the frozen harness, budgets, and declared local model, does withholding
all agent-visible tests and scores (`tests-none`) change behavioral
correctness relative to `baseline` (failure-level `test_visible` tool access)
when the task is stages 1–10 under a 2-hour budget, measured by the corpus
(hidden macro score) and by generated programs (fuzz macro), once no single
shell command can consume a round?

Pre-declared from v3 and v5 (`analysis/report.md` §7, §10): v3 found a
candidate effect of −0.136 (corpus, n=3); v5 found paired medians of −0.022
(corpus) and −0.044 (fuzz) with n=4, both inside noise, in a cohort where 5 of
8 runs lost 30–46 minutes to hangs and the three broken compilers were the
three runs that lost the most. The expectation is two-sided: either the v5
null holds with tighter variance, or an effect masked by the hang lottery
appears. A second, pre-declared expectation concerns the harness: with the
default timeout, no run should stall a round, and the outcome distribution
should no longer be bimodal.

## What changed since v5 (the harness revision)

Applied before any v6 run, all frozen in the harness commits `4513e94`,
`7218e06`:

1. **Pi 0.84.1 → 0.85.1** (image 0.3). No change to anything the harness
   parses; the JSON event stream only gained fields. Verified by the
   validation suite, evaluator smoke, live request, and pilot
   `v6-pilot-pi0851-smoke1`.
2. **Bash default timeout** (image 0.4): the community package
   `@cad0p/pi-bash-timeout@0.1.0` (MIT; extension file SHA-256
   `c9e0c20ddeab6e44aae77e69fe932c506c436ce939f4d12be79d6da3323a50e3`) is
   installed in the image and loaded through the frozen `pi/settings.json`
   (`packages`). It re-registers Pi's `bash` tool so a command the agent
   issues without a `timeout` argument is killed after 120 s; an explicit
   timeout always wins. Pi itself ships no default and its maintainer
   declined one (earendil-works/pi#2987). The guard's `tool_result` hook logs
   each cut-off as `bash_timeout_fired`; run reports, the study summary
   (`guard_bash_timeouts`), and the process metrics count them apart from
   guard blocks. Motivation, measured on the 20 v3–v5 main runs: 2670
   completed bash calls with p99 = 5.1 s, versus 18 calls that never returned
   and cost a median 34 minutes each (8.9 of 40 budget hours). The 120 s
   default is the package's; it exceeds the longest legitimate completed
   command (40 s) three-fold.
3. **Tool description:** the package appends "(default timeout: 120s when
   omitted)" to the bash tool's description. This is part of the fixed
   environment, identical in both conditions, and the only prompt-visible
   change since v5.

Everything else is as in v5: prompts, specification, partitions, adapter,
budgets, model, thinking, sampling, oracle, fuzz parameters, preflight.

## Planned runs

- Number of main repetitions: 4 per condition, 8 runs total (as v5).
- Order: the frozen randomized block order from `study.py schedule` (study
  seed 20260911, replicates 1–4, profile `main`). Run IDs are the short
  aliases `v6-<condition>-r<replicate>` of the schedule's
  `picc-tests-v3-main-r0N-<condition>` entries; the order is binding:
  1. `v6-tests-none-r1`
  2. `v6-baseline-r1`
  3. `v6-tests-none-r2`
  4. `v6-baseline-r2`
  5. `v6-baseline-r3`
  6. `v6-tests-none-r3`
  7. `v6-tests-none-r4`
  8. `v6-baseline-r4`
- Slots run sequentially through one chain driver: endpoint preflight
  (`make preflight`, abort on mismatch), run, `study-hidden-all` (corpus for
  every snapshot, fuzz for the final one), `study-report`, next slot;
  `study-summary STUDY=studies/tests/study.json` at the end.
- Pilot runs, excluded from every analysis: `v6-pilot-pi0851-smoke1`
  (image 0.3) and `v6-pilot-pkg-smoke1` (image 0.4), both pilot profile,
  0.4 h wall, 12-minute round cap, 2 rounds, stages 1–3, `baseline`
  condition, run under the previous manifest id before this freeze.

## Frozen configuration

- Docker image ID: `sha256:2e4e4dc58548e6566eed393082b9be049cc41422dd36c35f00f576d818d9a555`
  (`picc-experiment:0.4`; = image 0.3 + `@cad0p/pi-bash-timeout@0.1.0`;
  Node.js v24.20.0, TypeScript 5.9.3 present and unused by this cohort's
  Rust candidates; base image `node:24.20.0-bookworm-slim@sha256:ba849c60…`)
- Pi version: `@earendil-works/pi-coding-agent@0.85.1`; Rust toolchain `1.88.0`
- Provider/model: `local` — llama.cpp `llama-server` build `b1-3cb7ffb`
  serving `unsloth/Qwen3.8-27B-GGUF:UD-Q4_K_XL`; served GGUF SHA-256
  `3f227079003add2511437e5b1e94812e363385225bf6a9b47b0054a72bc8b01e`
  (HF snapshot `4ca720788d1e01f1bff70c033e0d0028fd02e502`; the same file as
  v3–v5; verified by `make preflight` on 2026-09-11 and pinned as
  `LOCAL_MODEL_SHA256`); 4 server slots, 131072 context; single RTX 5090
- Thinking setting: `high`; sampling pinned client-side
  (`temperature 1.0, top_p 0.95, top_k 20, min_p 0`); `LOCAL_MAX_OUTPUT=65536`
- Test repository revision: `ae12014d2dec14488f3f80d14df4b6d8e4634d7d`
- Visible manifest SHA-256 (source): `bb5410a9ae1d0cfe904d5316828791b04e77dca4fb459601877ce9e927029a6f`
  (227 tests); hidden: `49960548e8ce2353990fc39bd91536166df37e14c62dd33acd27afccef01faef`
  (104 tests); both unchanged since v3
- Candidate adapter: `studies/assets/candidates/rust-std.json`
  (SHA-256 `69aa13ffba00fff0a147a83c36b5fbdceceddd46c41ae89e6bf928c154578588`,
  unchanged since v3)
- Resolved condition SHA-256: `baseline`
  `d9ba1f5e5b28fc185ef2173594cf5b77f9caa7a44f0ac268cb7ca711e7f5e055`, `tests-none`
  `98a50811588544a69e00874cb4f07f6bcf803b2a4608e9a85ea6127fd94e86ce` (identical to
  v3 and v5)
- Prompts and specification: byte-identical to v3 and v5 for both conditions
- Pi settings: `pi/settings.json` as v5 plus
  `"packages": ["/usr/local/lib/node_modules/@cad0p/pi-bash-timeout"]`
- `.env` overrides other than credentials: as v5; effective main budget 2 h
  wall, 30 rounds, 45-min round cap, stages 1–10, two consecutive stalls
  terminal (the round cap is kept at 45 minutes deliberately, so that the
  timeout is the only change against v5)
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

Selected before running. The first group is the v5 list; the second group
adds the resource and code dimensions that `analysis/dimensions.py`
(`analysis/report.md` §11) showed were dominated by the hang lottery in v2–v5
and can now be read as outcomes of the conditions:

- [x] final hidden micro score
- [x] hidden score/time AUC (all snapshots evaluated)
- [x] visible–hidden gap
- [x] per-stage fuzz pass rates and mismatch kinds
- [x] buildable snapshot fraction
- [x] compaction count, truncated thinking turns
- [x] tool-call distribution (including `test_visible` and self-test shell use)
- [x] guard-blocked calls
- [x] completion per study manifest: hidden macro ≥ 0.95 with successful build
  and no blocking audit finding
- [x] **harness check** (operationalized per Amendment 1): idle minutes per
  run (time between the agent's last turn and the round kill, summed over
  rounds; expected below 5 in every run) and bash calls that never returned
  (expected 0), alongside bash commands cut by the default timeout
  (`guard_bash_timeouts`; expected > 0 in some runs); a run that still idles
  is reported with the command that blocked it
- [x] **resources, paired like the primary endpoints:** reported output tokens
  (and input tokens), active minutes (time between the first and last agent
  turn) and idle minutes, assistant turns, tool calls
- [x] **code, paired like the primary endpoints, descriptive:** compiler source
  LOC and function count (`analysis/dimensions.py` measures), self-written
  test programs and their LOC, source churn (insertions/deletions/changed
  files), final build time and median per-test compile time
- [x] **distribution shape:** the number of runs with fuzz macro below 0.9
  (v5: 3 of 8; v3: 2 of 6), as the test of whether bimodality collapsed

## Interpretation rule

Report all eight runs individually, then per-condition median and range for
both endpoints. For each endpoint separately: a paired median difference with
magnitude greater than 0.13 is a candidate effect warranting replication; a
smaller difference is compatible with no detectable effect at this sample
size. The fuzz macro is bimodal in earlier cohorts (a compiler is either
perfect or broken on a stage), so its paired median is reported alongside the
number of replicates whose difference exceeds 0.13 in the same direction;
three of four in one direction is treated as consistent with the corpus
verdict, two of four as unresolved. If six or more of eight runs score below
0.30 on the corpus oracle, the budget rather than the conditions is the
finding. Resource and code secondary endpoints are reported as paired medians
with per-replicate values and no threshold; they describe cost at a given
correctness, not correctness. If any run idles for five minutes or more, the harness
check failed for that run and the reason is reported before any contrast is
read.

## Exclusion rules

A run may be excluded only if:

- [x] the Docker image or frozen test partition is missing/corrupt before work;
- [x] authentication fails before the first successful model response;
- [x] a confirmed harness implementation defect invalidates measurement;
- [x] the preflight reports the endpoint unreachable before the run starts —
  the slot is launched after the endpoint returns rather than skipped. A
  preflight *mismatch* (a different model file) aborts the cohort instead; it
  cannot produce an includable run. An endpoint failure after a run's first
  successful model response is an outcome, not an exclusion.

Do not exclude ordinary model mistakes, compiler build failures, low scores,
fuzz failures, compaction failures caused by the trajectory, guard blocks, or
commands cut by the default timeout.

## Human intervention policy

- No prompts beyond the frozen initial/continuation messages.
- No workspace edits after start.
- No `.env`, configuration, prompt, partition, adapter, settings, image, or
  script changes for the duration of the cohort.
- No inspecting hidden or fuzz results before a run terminates.
- Any unavoidable intervention is logged and the run is analyzed separately.

## Analysis

- `analysis/v6_results.py`: all runs individually, both endpoints, paired
  contrasts, the harness check, and the paired resource/code secondary
  endpoints; `make study-summary STUDY=studies/tests/study.json` for the
  provenance-checked aggregation.
- Report median and range; optionally mean and standard deviation.
- Pair each `tests-none` run only with the `baseline` run sharing its replicate.
- Do not select the best trajectory as the primary result.
- v5 is reported next to v6 as the comparison for the harness check
  (stalls, bimodality); the two cohorts are never pooled for the contrast.
- Qualify claims as task-specific; one model, one task.
- Disclose public-test contamination and the unarchivable local server.

## Pilot evidence (before the freeze)

Both pilots ran to their 0.4 h budget on 2026-09-11 under the `baseline`
condition (two 12-minute rounds, stages 1–3), after the validation suite,
evaluator smoke, model preflight, and a live model request through each
image passed. They are excluded from every analysis; what they establish:

- `v6-pilot-pi0851-smoke1` (image 0.3, Pi 0.85.1): the run path, session
  continue, hidden and fuzz evaluation, and report work unchanged under Pi
  0.85.1 (no malformed events, empty stderr); the compiler did not build
  within 24 minutes (corpus 0.0, fuzz 0.0 with `build_failure`), the
  no-compiler path.
- `v6-pilot-pkg-smoke1` (image 0.4): same path with the package loaded from
  the frozen settings; visible 47/47, hidden 1.0 (19/19), fuzz 1.0 at stages
  1–3 in 24 minutes. **The default timeout fired once, on the agent's own
  test script running a program its compiler had miscompiled into an
  infinite loop**; the command returned "Command timed out after 120
  seconds", the ledger recorded `bash_timeout_fired`, and the agent's next
  turn read "t8 hangs — infinite loop. Let me inspect the emitted assembly"
  before fixing it. That is the hang class that cost 45 minutes per
  occurrence in v3–v5. The run report shows one guard block and one cut-off.
- A separate real-Pi session (not a harness run) with a non-terminating
  self-test confirmed the cut-off at 121 s wall time, and the mocked-API and
  strict type checks of both guards and the package extension passed.

No harness change followed the pilots.

## Amendments

1. **2026-09-11 09:20Z, during run 1 of 8, before any hidden or fuzz result
   was viewed.** The harness check was mis-operationalized. `stalls` counts
   rounds ended by the 45-minute round cap, which is how every round of a
   working agent ends under this budget (all eight v5 runs show 2 of 2), not
   a hang. The pre-declared expectation "stalled rounds = 0" is replaced by:
   idle minutes per run below 5 in every run (v5: five of eight runs idled
   30–46 minutes), and zero bash calls without a result (`hangs` in the
   process metrics). Cut-offs (`guard_bash_timeouts`) are unchanged.
   `analysis/v6_results.py` reports the corrected check. No harness,
   configuration, prompt, or image change; the running cohort is unaffected.

2. **2026-09-11 17:50Z, after run 6 of 8 (`v6-tests-none-r3`) terminated and
   before runs 7–8 started producing results; no hidden or fuzz result of any
   unfinished run viewed.** A confirmed harness defect (exclusion rule 3),
   logged with its pre-declared handling:
   - **Defect.** The frozen study evaluator's blocking source audit scans
     every `.rs` file in the workspace for the Rust adapter
     (`studies/assets/candidates/rust-std.json` declares no `audit.roots`, so
     `iter_source_files` defaults to the whole workspace), although
     `cargo build --release` compiles only `src/`. The v4 incident
     (`analysis/report.md` §8.5) established that a blocking audit must be
     scoped to the artifact actually submitted, and the Node adapters were
     scoped accordingly; the Rust adapter was not.
   - **Effect so far.** `v6-tests-none-r3`'s final snapshot was zeroed on
     both oracles (`audit_blocking`, four "subprocess invocation" findings,
     all in `tests/fuzz.rs`, a differential fuzzer the agent wrote that
     assembles and links its compiler's output with `as`/`ld` and runs the
     binary; `src/` has no finding and the same run's round-0 snapshot built
     and scored). No earlier Rust run (v3, v5) had a blocking audit; runs 1–5
     of v6 passed the audit. The affected run's agent could not have seen
     the finding (`tests-none` exposes no scores), so its behavior is
     unaffected; a `baseline` agent would see a blocked `test_visible`
     result, so the contamination check below is part of the record.
   - **Handling, fixed before the result is known.** The primary contrast is
     computed on every final snapshot re-scored, after the cohort ends, by
     the evaluator with the audit scoped to the Cargo package's `src/`
     (plus any `#[path]`/`include!` file that `src/` pulls in), both oracles,
     same image, same parameters, applied identically to all eight runs. The
     audit is a gate, not a score, so this can change only runs with a
     blocking finding outside `src/`; every other run's re-scored values
     must reproduce its frozen ones, and the report shows both columns. The
     frozen-protocol values remain in the study summary. The corrected
     evaluator is committed only after `CHAIN COMPLETE`; nothing in the
     running cohort changes. This is the §10.4 bridge method applied to the
     cohort's own finals, not a new rule invented after seeing an outcome:
     the affected run's corrected score is unknown at the time of writing.
   - **Contamination check.** For each run, whether any in-run visible
     evaluation (`test_visible` results, round snapshots) reported a blocking
     audit; a `baseline` run with such a result is reported separately as
     behaviorally affected. Runs 1–6: none.
