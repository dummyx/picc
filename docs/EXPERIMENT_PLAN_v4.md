# Experiment plan: v4 batch (static typing)

Completed and committed before the first v4 main run. The v3 batch has its
own document (`docs/EXPERIMENT_PLAN.md`); this batch uses a separate study
manifest so that the v3 aggregation stays intact.

## Study identity

- Study title: PiCC v4 — static typing at stages 1–10 (`ts-strict` vs `js-untyped`)
- Study manifest: `studies/types/study.json` (`picc-types-v1`, seed 20260907)
- Date frozen: 2026-09-07
- Repository commit: `6ebc1a3e5011e7c0249830a3c1be185f77481d9a` (this experiment plan is committed on
  top; no harness, prompt, partition, adapter, or configuration file changes
  with it)
- Investigator: dummyx

## Research question

Under the frozen harness, budgets, and declared local model, does requiring
explicit static types with a strict type checker as the build gate
(`ts-strict`: TypeScript, `tsc --strict --noEmitOnError`; a snapshot that does
not type-check has no compiler) change hidden behavioral correctness relative
to an untyped implementation of the same task on the same runtime
(`js-untyped`: plain JavaScript on Node.js 24, syntax check only, type checker
withheld by the guard) when the task is stages 1–10 under a 2-hour budget?

No direction is predicted. Static typing could help (the checker reports
mistakes before any test runs; declared token/AST/IR shapes discipline the
design) or hurt (type-error round-trips consume a budget that v3 showed is
stall-dominated, and a final snapshot with a type error scores 0). The
pre-declared threshold therefore applies to the magnitude of the paired
difference.

JavaScript was chosen as the untyped arm, rather than "Python without
annotations", because the absence of annotations is then a property of the
language rather than an instruction the agent may or may not follow (v2/v3
process metrics: prompt instructions are followed roughly half the time).

## Planned runs

- Number of main repetitions: 3 per condition, 6 runs total
- Order: the frozen randomized block order from `study.py schedule` (study seed
  20260907, replicates 1–3, profile `main`). Run IDs are the short aliases
  `v4-<condition>-r<replicate>` of the schedule's
  `picc-types-v1-main-r0N-<condition>` entries; the order is binding:
  1. `v4-ts-strict-r1`
  2. `v4-js-untyped-r1`
  3. `v4-ts-strict-r2`
  4. `v4-js-untyped-r2`
  5. `v4-ts-strict-r3`
  6. `v4-js-untyped-r3`
- Slots run sequentially through one chain driver: endpoint preflight, run,
  `study-hidden-all`, `study-report`, next slot; `study-summary` at the end.
- Pilot runs, excluded from every analysis: `v4-pilot-ts-strict-smoke1` and
  `v4-pilot-js-untyped-smoke1` (pilot profile, 0.4 h wall, 12-minute round
  cap, 2 rounds, stages 1–3), executed before this freeze purely to exercise
  Pi + guard + `tsc` + evaluator end to end on the new image. Their outcomes
  are infrastructure evidence only and are reported in the amendments below.

## Frozen configuration

- Docker image ID: `sha256:02ed179c48680acd707217505409660080a6e68c2022711754e3ba70cb32a71d`
  (`picc-experiment:0.2`). Relative to image 0.1 (`dcff5de5…`, the v3 image)
  the Dockerfile adds only `typescript@5.9.3` and `@types/node@24.13.3`
  installed globally. Disclosure: the base tag `node:24-bookworm-slim` is not
  digest-pinned and resolved to Node.js v24.20.0 / npm 11.19.0 for image 0.2
  (image 0.1 carries v24.19.0 / 11.17.0). Both arms of this batch use image
  0.2, so the difference matters only for descriptive comparison with v3.
- Pi version: `@earendil-works/pi-coding-agent@0.84.1`
- TypeScript compiler: `5.9.3`; Node type declarations `@types/node@24.13.3`;
  Rust toolchain `1.88.0` (present, unused by this batch's candidates)
- Provider/model: `local` — llama.cpp `llama-server` build `b1-3cb7ffb`
  (commit 3cb7ffb) serving `unsloth/Qwen3.8-27B-GGUF:UD-Q4_K_XL`; served GGUF
  SHA-256 `3f227079003add2511437e5b1e94812e363385225bf6a9b47b0054a72bc8b01e`
  (HF snapshot `4ca720788d1e01f1bff70c033e0d0028fd02e502`, 17,559,178,144
  bytes; verified 2026-09-07; the same file the v3 batch ran on — see the
  2026-09-07 amendment in `docs/EXPERIMENT_PLAN.md`); single RTX 5090; full
  endpoint provenance in `runs/local-endpoint-provenance-2026-09-07.json`
- Thinking setting: `high`; sampling pinned client-side
  (`temperature 1.0, top_p 0.95, top_k 20, min_p 0`)
- Test repository revision: `ae12014d2dec14488f3f80d14df4b6d8e4634d7d`
- Visible manifest SHA-256 (source): `bb5410a9ae1d0cfe904d5316828791b04e77dca4fb459601877ce9e927029a6f`
  (227 tests; materialized copy `eeb797f7…`, identical to the v3 runs)
- Hidden manifest SHA-256 (source): `49960548e8ce2353990fc39bd91536166df37e14c62dd33acd27afccef01faef`
  (104 tests; materialized copy `5542c1fa…`, identical to the v3 runs)
- Candidate adapters: `studies/assets/candidates/typescript-strict.json`
  (SHA-256 `0bf9652631ab831b73be4340732bbbe0ed1dd538a602ac2803b7be17cb3a80f1`)
  and `studies/assets/candidates/javascript-node.json`
  (SHA-256 `a2a97ec47e6fd459c8a144112162669cf277d36efa94f54a7619e4bd03fe1c70`)
- Resolved condition SHA-256: `ts-strict`
  `d722f7516eda006501cfff9a3f87eaa6ce98822b7f63198c4eddbcfaeb4c9457`,
  `js-untyped` `35b58f1cccfeec87951781038acf27ec68575126cfcb882afb18b3e724b783e7`
- Prompts: `INITIAL.txt` and `CONTINUE.txt` are byte-identical to v3;
  `AGENTS.md` differs from v3 only in the candidate bullet of the frozen
  condition section (language, build/entry commands, dependency policy, and the
  adapter's layout/typing notes); `TASK.md` differs only in the language line,
  the build and entry command blocks, and the dependency-policy sentence. The
  two arms differ from each other only in those same slots.
- Prompt/extension hashes location: per run, `runs/<id>/study-metadata.json`
  (`rendered.*` and `materialized_harness.file_hashes`) and `runs/<id>/metadata.json`
- `.env` overrides other than credentials, unchanged from v3:
  `MODEL_PROVIDER=local`, `MODEL_ID=unsloth/Qwen3.8-27B-GGUF:UD-Q4_K_XL`,
  `MODEL_THINKING=high`, `LOCAL_BASE_URL=http://127.0.0.1:4545/v1`,
  `LOCAL_NETWORK_MODE=host`, `LOCAL_CONTEXT_WINDOW=131072`,
  `LOCAL_MAX_OUTPUT=65536`,
  `LOCAL_SAMPLING_PARAMS={"temperature": 1.0, "top_p": 0.95, "top_k": 20, "min_p": 0}`,
  `MAIN_HOURS=2`, `MAIN_ROUND_TIMEOUT_MINUTES=45`.
  Effective main budget: 2 h wall, 30 rounds, 45-min round cap, stages 1–10,
  two consecutive stalls terminal (`MAX_CONSECUTIVE_ROUND_TIMEOUTS=2` default).
- Harness revision relative to the v3 freeze, all applied before
  any v4 run: the study evaluator audits JavaScript/TypeScript candidates
  (imports, `package.json` dependencies, vendored `node_modules`, binary
  artifacts, dynamic loading, all on comment-stripped code; `process.env` and
  `@ts-nocheck`/`@ts-ignore`/`@ts-expect-error` are advisory), adapters may
  append layout/typing notes to
  the candidate bullet of `AGENTS.md` and declare extra guard bash blocks (the
  JavaScript adapter withholds `tsc`), the workspace `.gitignore` also ignores
  `dist/` and `node_modules/`, and a build failure's per-test detail falls back
  to the build's stdout when stderr is empty (`tsc` reports on stdout). Rust
  and Python scoring semantics are unchanged.

## Primary endpoint

Final hidden macro-score averaged equally across stages and, within each stage,
across valid and invalid test classes. The primary contrast is
`ts-strict` − `js-untyped`, paired by replicate identifier.

## Secondary endpoints

Selected before running:

- [x] final hidden micro score
- [ ] highest stage with at least ___ hidden score
- [x] hidden score/time AUC (all snapshots evaluated)
- [x] visible–hidden gap (overfitting check)
- [x] buildable snapshot fraction, and for `ts-strict` the fraction of
  unbuildable snapshots whose build output carries TypeScript diagnostics
  (`error TS`), i.e. snapshots lost to the type gate rather than to a missing
  entry file
- [x] compaction count
- [x] reported input/output tokens
- [x] tool-call distribution (including `test_visible` and self-test shell use)
- [x] guard-blocked calls, separately counting `tsc` attempts in `js-untyped`
- [x] treatment fidelity, descriptive, from the final snapshot and event
  streams (`analysis/typing_metrics.py`): in `ts-strict`, counts of `any`,
  `unknown`, `as` casts, non-null assertions, `@ts-*` suppressions, and
  declared interfaces/type aliases, plus the share of function declarations
  with explicit return types; in `js-untyped`, JSDoc type tags, `// @ts-check`,
  and `.ts` files; in both arms, bash invocations of `tsc`, `node --check`,
  and direct compiler runs
- [x] source LOC by adapter extension (descriptive only; not comparable to
  Rust LOC)
- [x] completion per study manifest: hidden macro ≥ 0.95 with successful build
  and no blocking audit finding

## Feasibility criterion

Pre-declared interpretation rule, carried over from v3: report all six runs
individually, then per-condition median and range. A paired median difference
with magnitude greater than 0.13 is a candidate effect warranting replication;
smaller differences are reported as compatible with no detectable effect at
this sample size. If four or more of six runs score below 0.30, the budget —
not the conditions — is the finding for this substrate. A `ts-strict` run whose
final snapshot fails the type gate (hidden 0.0 with `build_ok=false`) is an
outcome, not an exclusion; it enters the primary contrast as 0.0, and the
contrast recomputed on each run's last buildable snapshot is reported as a
secondary sensitivity analysis.

## Exclusion rules

A run may be excluded only if:

- [x] the Docker image or frozen test partition is missing/corrupt before work;
- [x] authentication fails before the first successful model response;
- [x] a confirmed harness implementation defect invalidates measurement;
- [x] other pre-declared rule: the local endpoint is unreachable at the
  chain's preflight, before the run starts — the slot is launched after the
  endpoint returns rather than skipped. An endpoint failure after a run's
  first successful model response is an outcome, not an exclusion.

Do not exclude ordinary model mistakes, type errors, build failures, low
scores, compaction failures caused by the trajectory, or guard blocks.

## Human intervention policy

- No prompts beyond the frozen initial/continuation messages.
- No workspace edits after start.
- No `.env`, configuration, prompt, partition, adapter, or script changes for
  the duration of the batch.
- No inspecting hidden results before a run terminates.
- Any unavoidable intervention is logged and the run is analyzed separately.

## Analysis

- Report all runs individually.
- Report median and range; optionally mean and standard deviation.
- Pair each `ts-strict` run only with the `js-untyped` run sharing its
  replicate (`make study-summary STUDY=studies/types/study.json` does this
  because `js-untyped` is the manifest's baseline).
- Do not select the best trajectory as the primary result.
- Qualify claims as task-specific; one model, one task, one language pair.
- Comparison with the v3 Rust baseline is descriptive external validity only:
  prompts, specification scope, tests, budgets, and the served model file are
  the same, but the image (Node patch level, added npm packages), harness
  revision, and language differ.
- Disclose public-test contamination and the unarchivable local server.
- Post-hoc differential fuzzing (`analysis/fuzz_differential.py`) of final
  snapshots is descriptive follow-up, not part of the frozen primary score.

## Pilot evidence (before the freeze)

Both infrastructure pilots ran to their 0.4 h budget on image 0.2 with the
final harness (`v4-pilot-ts-strict-smoke1` 15:47–16:11 UTC,
`v4-pilot-js-untyped-smoke1` 16:11–16:35 UTC on 2026-09-06), two rounds each,
stages 1–3, and were evaluated post hoc. They are excluded from every
analysis; what they establish is that the treatment is delivered and measured
as designed:

- `ts-strict`: the agent invoked the exact frozen `tsc` build command seven
  times and iterated on type errors; round 0 had no `src/picc.ts` yet and was
  scored 0 as a build failure (`TS6053`, classified as a missing entry, not a
  type error); round 1 built, passed the audit, and scored visible 0.924 /
  hidden 0.958 at stages 1–3. Final workspace: 6 `.ts` files, 1705 LOC, 10
  interfaces, 9 type aliases, 14/14 function declarations with return types,
  no `any`, no suppressions. Self-testing produced `.o` files under `tests/`,
  which the audit ignores by design.
- `js-untyped`: `node --check` builds passed in both rounds; the agent called
  `test_visible` four times, never attempted `tsc` (zero typing guard blocks;
  the two guard events were an existing-rule `gcc` block and a write outside
  `/workspace`), wrote no JSDoc type tags or `.ts` files, and scored visible
  0.985 / hidden 1.0 at stages 1–3 with 1503 LOC.
- Post-hoc `study-hidden-all` and `study-report` completed for both, with the
  image ID verified; `analysis/typing_metrics.py` reads both runs.

No harness change followed the pilots; the only edits after the first pilot
started (removing an advisory stray-extension audit rule, dropping `.o`/`.a`
from the binary-artifact rule, and stripping comments before the blocking
JavaScript/TypeScript checks) were made before the second pilot materialized
and are part of the frozen commit.

## Amendments

### 2026-09-06 — audit scope defect found on the first JavaScript run; batch restarted

Slot 2 (`v4-js-untyped-r1`, launched 18:25 UTC) had its round-0 snapshot
scored 0.0 by a **blocking** source-audit finding: the agent had written a
fuzz-test driver, `.scratch/fuzz2.js`, that spawns its own compiler through
`child_process`. The compiler itself (`src/picc.js` and its imports) was
clean. The frozen audit scanned every file of the adapter's source
extensions anywhere in the workspace, so an agent-authored test driver was
treated as the "submitted compiler" that the specification forbids from
spawning subprocesses. Slot 1 (`v4-ts-strict-r1`) had completed under the
same harness (hidden 0.7587, advisory `process.env` finding only).

Why this is a harness defect under exclusion rule 3 rather than an outcome:
the rule interacts with the treatment asymmetrically. A JavaScript agent's
natural self-test tooling is JavaScript, which the untyped adapter scans; a
TypeScript agent's quick helpers are bash or `.js` files, which the typed
adapter does not scan. A run that ends with such a driver present scores 0
on the primary endpoint by artifact, which would invert the typed-vs-untyped
contrast for reasons unrelated to typing (the v2 batch's audit-gate failure
mode). The v3 Rust runs never triggered the equivalent Rust rule because
those agents self-tested through bash.

Fix, applied before any further run and frozen in this commit: the Node
adapters declare `audit.roots = ["src"]` and `audit.entry` (`src/picc.js` /
`src/picc.ts`); the evaluator's per-file scan (prohibited/non-built-in
imports, blocking and advisory text patterns) covers the roots plus the
entry module's relative import closure, so a module the compiler actually
imports from outside `src/` is still audited, while test drivers elsewhere
are not. Workspace-wide checks (symlinks, binary artifacts, `package.json`
dependencies, vendored `node_modules`) are unchanged, as are the Rust and
Python adapters. Re-auditing the two affected workspaces and both pilots
with the fixed rule: the stopped JavaScript workspace passes (4 files scanned, all under
`src/`), the others are unchanged. No budgets,
prompts, partitions, per-test timeouts, or scoring semantics changed.

Disposition: both runs executed so far (`v4-ts-strict-r1`, complete;
`v4-js-untyped-r1`, stopped during round 1 at 19:13 UTC) and their
materializations are retained under `runs/.quarantine-v4/` and excluded from
all analyses; all six planned in advance slots restart from scratch, in the same
order, under the amended freeze commit so every run in the batch executes
the identical harness. Cost: about 3.5 hours of runs redone. Observations
from the quarantined runs are not used for any decision beyond this fix.
