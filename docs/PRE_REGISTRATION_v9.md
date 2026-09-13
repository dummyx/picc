# Pre-registration: v9 cohort (specification detail x test access, 2x2)

Completed and committed before the first v9 main run. Seven cohorts have
found that no manipulated factor detectably changes behavioral correctness on
this task while every factor changes the process. v9 asks whether the agent
needs *either* of the two external definitions of the task, the behavioral
specification and the visible tests, by crossing them: the first factorial
manifest in the study layer. It is also the first cohort that removes most of
the specification, so it doubles as a measurement of how much of the task the
model brings with it.

## Study identity

- Study title: PiCC v9 — specification detail x test access at stages 1–10
  (`baseline`, `spec-minimal`, `tests-none`, `spec-minimal-tests-none`)
- Study manifest: `studies/spectests/study.json` (`picc-spectests-v1`, seed
  20260914, `design: factorial`, `factors: [specification, tests]`; manifest
  SHA-256 `d23c45c4bac3a3d9295cb0043230f8001ddfca31b23b4b03e21ab4d0e4cb35fd`)
- Date frozen: 2026-09-14
- Repository commit: `f2e81b9` (factorial design, manifest, minimal
  specification, tests, docs); this pre-registration and
  `analysis/v9_results.py` are committed on top with no harness, prompt,
  partition, adapter, or configuration change
- Investigator: dummyx

## Research question

Under the frozen harness, budgets, and declared local model, at stages 1–10
under a 2-hour budget, measured by the corpus and by generated programs on
the last buildable snapshot:

1. Does replacing the behavioral specification with a minimal one (product
   interface, output contract, one line per stage, dependency policy; no
   behavioral detail and no mention of the source book) change correctness,
   when tests are on demand and when they are withheld?
2. Does withholding the visible tests change correctness under the minimal
   specification, as it did not under the full one (v6: −0.017 / 0.000)?
3. Do the two factors interact: is the specification effect larger when the
   agent has no tests to define the task for it?

Pre-declared expectation, two-sided and skeptical on all three: the task is
public (the book and its test suite), so a null on the specification factor
is expected and would mean the specification is redundant with what the model
already knows; the interesting cell is `spec-minimal-tests-none`, where the
agent has only the interface, the feature list, and its own knowledge of C.
The pre-declared readings (§Interpretation rule) cover both outcomes.

## What changed since v8 (commit `f2e81b9`)

1. **Factorial design in the study validator**: `design: "factorial"` with
   `factors` naming the crossed blocks; every non-empty combination must be
   present exactly once; a combined cell must reuse the single-factor
   overlays block for block. One-factor manifests validate as before.
2. **The minimal specification** `studies/assets/specs/minimal.md` (SHA-256
   `e64b3cb3a879cc8baa1648157e476eba3793873bc70df7f8b5a723325e0869a0`, 35
   lines, under a third of the behavioral specification's words): the same
   interface block as the other specifications (build and entry commands,
   dependency policy), a two-sentence output contract, and ten one-line
   stage names. No precedence, associativity, ABI, scoping, rejection, or
   diagnostic rules; no reference to the book or its test suite.
3. **The manifest** `studies/spectests/study.json`: `baseline` and
   `tests-none` byte-identical to the starter's (resolved condition hashes
   as in v6); `spec-minimal` = baseline with the minimal specification;
   `spec-minimal-tests-none` = both overlays.

No change to the image, Pi, the timeout package, prompts, partitions,
adapter, budgets, model, sampling, oracle, fuzz parameters, preflight, audit
scope, or the last-buildable rule. The rendered `AGENTS.md` for the two
`tests-none` cells carries the same withheld-tests guidance as v6.

## Planned runs

- Number of main repetitions: 3 per cell, 12 runs total.
- Order: the frozen randomized block order from `study.py schedule` (study
  seed 20260914, replicates 1–3, profile `main`). Run IDs are the short
  aliases `v9-<condition>-r<replicate>`; the order is binding:
  1. `v9-spec-minimal-r1`
  2. `v9-spec-minimal-tests-none-r1`
  3. `v9-tests-none-r1`
  4. `v9-baseline-r1`
  5. `v9-spec-minimal-tests-none-r2`
  6. `v9-spec-minimal-r2`
  7. `v9-tests-none-r2`
  8. `v9-baseline-r2`
  9. `v9-baseline-r3`
  10. `v9-spec-minimal-tests-none-r3`
  11. `v9-tests-none-r3`
  12. `v9-spec-minimal-r3`
- Slots run sequentially through one chain driver: endpoint preflight
  (abort on mismatch), run, `study-hidden-all`, `study-report`, next slot;
  `study-summary` at the end.
- Pilot runs, excluded from every analysis:
  `v9-pilot-spec-minimal-tests-none-smoke1` and `v9-pilot-spec-minimal-smoke1`
  (pilot profile, 0.4 h wall, 12-minute round cap, 2 rounds, stages 1–3),
  run on image 0.4 with commit `f2e81b9` before the freeze to exercise the
  two new cells end to end. `baseline` and `tests-none` are the v6/v8 cells
  and were not re-piloted.

## Frozen configuration

- Docker image ID: `sha256:2e4e4dc58548e6566eed393082b9be049cc41422dd36c35f00f576d818d9a555`
  (`picc-experiment:0.4`, unchanged since v6)
- Pi version: `@earendil-works/pi-coding-agent@0.85.1`; bash default timeout
  `@cad0p/pi-bash-timeout@0.1.0`; Rust toolchain `1.88.0`
- Provider/model: `local` — llama.cpp `llama-server` build `b1-3cb7ffb`
  serving `unsloth/Qwen3.8-27B-GGUF:UD-Q4_K_XL`; served GGUF SHA-256
  `3f227079003add2511437e5b1e94812e363385225bf6a9b47b0054a72bc8b01e`
  (the same file as v3–v8; verified by `make preflight` before each slot);
  4 server slots, 131072 context; single RTX 5090
- Thinking setting: `high`; sampling pinned client-side
  (`temperature 1.0, top_p 0.95, top_k 20, min_p 0`); `LOCAL_MAX_OUTPUT=65536`
- Test repository revision: `ae12014d2dec14488f3f80d14df4b6d8e4634d7d`
- Visible manifest SHA-256 (source): `bb5410a9ae1d0cfe904d5316828791b04e77dca4fb459601877ce9e927029a6f`
  (227 tests); hidden: `49960548e8ce2353990fc39bd91536166df37e14c62dd33acd27afccef01faef`
  (104 tests); unchanged since v3
- Candidate adapter: `studies/assets/candidates/rust-std.json`
  (SHA-256 `69aa13ffba00fff0a147a83c36b5fbdceceddd46c41ae89e6bf928c154578588`)
- Specifications: behavioral
  `25c98cf20801d3a128f5c8da11e0710d62d58cf801187ab77c0d6f100343ac7d`,
  minimal `e64b3cb3a879cc8baa1648157e476eba3793873bc70df7f8b5a723325e0869a0`
- Resolved condition SHA-256: `baseline`
  `d9ba1f5e5b28fc185ef2173594cf5b77f9caa7a44f0ac268cb7ca711e7f5e055`
  (identical to v3, v5, v6, v8), `tests-none`
  `98a50811588544a69e00874cb4f07f6bcf803b2a4608e9a85ea6127fd94e86ce`
  (identical to v6), `spec-minimal`
  `90fd0913993bfb2bcb448fb505b359d5a15d5708582323ecc348480e77666598`,
  `spec-minimal-tests-none`
  `9d8763ee360c838ae93c16c16dc18db62b7de73c94ddb57aca44333e60cc951d`
- Prompts: `AGENTS.md`, initial, and continuation prompts rendered from the
  same sources as v6; `TASK.md` is the behavioral or the minimal
  specification per cell
- Pi settings: `pi/settings.json` as v6
- `.env` overrides other than credentials: as v6; effective main budget 2 h
  wall, 30 rounds, 45-min round cap, stages 1–10, two consecutive stalls
  terminal
- Fuzz-oracle configuration (defaults, frozen per materialization):
  `FUZZ_STAGE_PROGRAMS=100`, `FUZZ_SEED_BASE=20260830`,
  `FUZZ_RUN_TIMEOUT_SECONDS=3`, `FUZZ_COMPILE_TIMEOUT_SECONDS=10`,
  `FUZZ_DEADLINE_SECONDS=5400`

## Primary endpoints (co-primary), on the last buildable snapshot

1. Hidden macro score (corpus oracle) of the last buildable snapshot (the v8
   rule: the last frozen snapshot whose hidden evaluation built and passed
   the audit; the final snapshot when it built; 0 when none built).
2. Fuzz macro (generated-program oracle) of the same snapshot.

Primary contrasts, each paired by replicate identifier and reported per
endpoint with its own paired median and per-replicate deltas:

- **Specification effect**, two simple effects:
  `spec-minimal` − `baseline` (tests on demand) and
  `spec-minimal-tests-none` − `tests-none` (tests withheld).
- **Tests effect**, two simple effects:
  `tests-none` − `baseline` (full specification, the v6 contrast) and
  `spec-minimal-tests-none` − `spec-minimal` (minimal specification).
- **Interaction**, per replicate:
  (`spec-minimal-tests-none` − `tests-none`) − (`spec-minimal` − `baseline`).

The same endpoints on the final snapshot are reported alongside for
comparability with v6–v8.

## Secondary endpoints

Selected before running:

- [x] final-snapshot corpus and fuzz scores; runs whose final did not build
- [x] final hidden micro score; hidden score/time AUC; visible–hidden gap
  (cells with tests)
- [x] per-stage fuzz pass rates and mismatch kinds, and per-stage corpus
  pass rates: with a minimal specification, **which stages** and which
  failure types (unexpected accept / unexpected reject / wrong behavior)
  separate the cells is the substantive secondary question
- [x] buildable snapshot fraction; compactions; guard-blocked calls
- [x] **harness check** (v6 form): idle minutes per run (expected below 5),
  bash calls that never returned (expected 0), commands cut by the default
  timeout, finals cut by the cap
- [x] **treatment fidelity:** `TASK.md` of every materialization matches the
  cell's specification hash; `test_visible` calls per run (expected 0 in the
  `tests-none` cells); whether the agent names the book, its chapters, or
  its test-suite layout in the session (evidence of recall in the minimal
  cells, descriptive)
- [x] **resources, paired:** output and input tokens, active and idle
  minutes, assistant turns, tool calls
- [x] **code, paired, descriptive:** source LOC and function count,
  self-written test programs and their LOC, source churn, final build time,
  median per-test compile time
- [x] **distribution shape:** runs with fuzz macro below 0.9 on each rule
- [x] completion per study manifest: hidden macro ≥ 0.95 with successful
  build and no blocking audit finding (final-snapshot rule)

## Interpretation rule

Report all twelve runs individually, then per-cell median and range for both
primary endpoints. For each contrast and endpoint separately: a paired median
difference with magnitude greater than 0.13 is a candidate effect warranting
replication; a smaller difference is compatible with no detectable effect at
this sample size (three replicates resolve less than four did; the threshold
is kept at 0.13 for comparability and the per-replicate deltas are always
shown). The interaction is reported as a paired median with per-replicate
values and no threshold. For the fuzz macro the paired median is reported
alongside the number of replicates whose difference exceeds 0.13 in the same
direction; three of three in one direction is treated as consistent with the
corpus verdict, two of three as unresolved.

Two readings are declared in advance:

- **All four specification and tests contrasts inside the band**: the task
  is defined for the model by its training exposure rather than by the
  specification or the tests; on this task the specification factor cannot
  be studied further, and the next cohort must change the task (altered
  semantics or an unseen language).
- **A specification contrast beyond the band**, in either cell: the first
  factor to move correctness on the clean harness; report which stages and
  failure types carry the difference, and whether the effect is larger
  without tests (interaction) before any causal wording.

If nine or more of twelve runs score below 0.30 on the corpus oracle, the
budget rather than the conditions is the finding. If any run idles for five
minutes or more, or a `tests-none` cell run called `test_visible`, the
harness or fidelity check failed for that run and the reason is reported
before any contrast is read.

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
commands cut by the default timeout, or a final snapshot cut by the cap.

## Human intervention policy

- No prompts beyond the frozen initial/continuation messages.
- No workspace edits after start.
- No `.env`, configuration, prompt, specification, partition, adapter,
  settings, image, or script changes for the duration of the cohort.
- No inspecting hidden or fuzz results before a run terminates.
- Any unavoidable intervention is logged and the run is analyzed separately.

## Analysis

- `analysis/v9_results.py`: all runs individually, both snapshot rules and
  both oracles, the five paired contrasts and the interaction, the harness
  check, and the paired resource/code secondary endpoints;
  `make study-summary STUDY=studies/spectests/study.json` for the
  provenance-checked aggregation (each cell paired with its replicate's
  baseline).
- Report median and range; optionally mean and standard deviation.
- Pair only runs sharing a replicate identifier; never pool cells.
- Do not select the best trajectory as the primary result.
- Qualify claims as task-specific; one model, one task, one language.
- Disclose public-test contamination and the unarchivable local server; in
  this cohort contamination is part of the question, not only a caveat.

## Pilot evidence (before the freeze)

Both pilots ran to their 0.4 h budget on 2026-09-13 (15:45–16:09 UTC and
16:09–16:33 UTC) on image 0.4 with commit `f2e81b9`, two 12-minute rounds
each, stages 1–3, after the validation suite (171 tests) passed. They are
excluded from every analysis; what they establish:

- **Rendering and fidelity.** Both materializations carry the minimal
  specification as `TASK.md` (143 words, the same rendered hash in both
  cells, no reference to the book); the `tests-none` cell's `AGENTS.md`
  carries the withheld-tests guidance and its agent never called
  `test_visible` (tool counts: bash 17, write 5, edit 2, ls 2, read 1,
  experiment_status 1); the `spec-minimal` cell's agent had the tool and
  did not call it either in 24 minutes (bash 13, edit 13, write 7). Neither
  session mentions the book, its author, or its chapters.
- **Measurement paths.** Each run terminated on the two-stall rule, was
  snapshotted after each round, evaluated on the hidden corpus for every
  snapshot and by the fuzz oracle on the final one, and reported; no
  malformed events; no commands cut by the default timeout; one guard block
  (`spec-minimal-tests-none`, a direct `gcc` attempt in round 0).
- **Both finals did not build**, so the pilots exercised the build-failure
  path rather than a scored compiler: `spec-minimal-tests-none` had a lexer,
  AST, and parser (1951 lines) but no `main.rs` when the cap fell, after
  spending its whole first round probing the assembler with hand-written
  snippets to discover the accepted x86-64 syntax (the full specification
  states this; the minimal one does not); `spec-minimal` had five modules
  (2407 lines, with unsigned and long handling the task does not ask for)
  and two type errors at the cap. Under the v8 pilots with the full
  specification, both cells reached hidden 1.0 at stages 1–3 in the same
  24 minutes. This is a difference in what the agent does under the minimal
  specification within a 12-minute round, which is the treatment, not a
  harness defect; the main runs have 45-minute rounds and the last-buildable
  rule. It is recorded here so that a null on the primary endpoints can be
  read against it, and the pre-declared secondary endpoints (first buildable
  snapshot time, self-tests, source size, which stages fail) will show
  whether the effect survives the full budget.

No harness change followed the pilots.

## Amendments

(none yet)
