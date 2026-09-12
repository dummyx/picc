# Essential PiCC factor-study protocol

## Objective

Measure how information and implementation substrate change a coding agent's
ability to construct PiCC. The primary outcomes are hidden behavioral
correctness, completion probability, elapsed active time, and model-reported
token use. Secondary outcomes describe the development trajectory and resulting
artifact.

This is an extension of the existing Pi reproduction harness, not a new
benchmark. The original single-run path remains untouched. Each study condition
is materialized into a private copy of the current harness so that prompt,
specification, test, adapter, and reference artifacts are frozen and hashed.

## Research questions

1. **Prompt and specification:** How do workflow instructions, specification
   detail, architectural guidance, and delivery location affect correctness and
   efficiency?
2. **Tests:** How do availability, amount, feedback granularity, and direct file
   access affect exploration, regression, overfitting, and hidden correctness?
3. **Implementation substrate:** How do language and starting framework/scaffold
   affect completion and artifact characteristics under the same external
   contract?
4. **Reference access:** Does a finite black-box behavioral oracle improve
   progress, and how is it used?
5. **Artifact provenance:** After controlling content coverage and delivery, do
   independently human- and LLM-created specifications/tests yield systematic
   differences?

RQ5 requires additional matched artifacts; provenance metadata alone is not a
causal treatment.

## Fixed components

For the starter study, freeze:

- target behavior and stages;
- upstream corpus revision and hidden partition;
- model/provider, Pi version, thinking level, extensions, and container image;
- active-time and round budgets;
- no human steering during a run;
- post-hoc hidden evaluator and completion threshold;
- independent stochastic repetitions identified by `REPLICATE`.

The harness still evaluates each Git snapshot on visible tests outside the
model context. Conditions determine whether and how the model can access those
tests. Hidden scores are never returned to the model.

## Experimental factors

### Prompt

`prompt-minimal` removes workflow, progress-memory, sequencing, and regression
instructions while retaining the task objective and safety constraints. It is a
prompt-policy treatment, not a shorter-specification treatment.

### Specification content and delivery

- `spec-brief`: concise scope and interface;
- `baseline`: detailed behavioral semantics;
- `spec-architecture`: detailed semantics plus component boundaries/invariants;
- `spec-inline`: the baseline specification appears in the initial request but
  is not duplicated in persistent `TASK.md`.

The three content variants have the same intended feature scope. Exact token
count is recorded through frozen artifacts and should be reported.

### Tests

- `tests-none`: no agent-visible tests or scores;
- `tests-aggregate`: aggregate score/build status only;
- `baseline`: stage scores and representative failure identifiers/types;
- `tests-files`: direct source access with baseline failure feedback;
- `tests-quarter`: deterministic family-grouped 25% subset.

The hidden partition remains unchanged. Test subsets are selected by family
within stage/validity strata to reduce near-duplicate leakage.

### Language/framework/scaffold

`language-python` and `scaffold-rust` preserve the executable contract and
behavioral evaluation but change the implementation substrate. They are best
analyzed as external-validity blocks. Language changes affect syntax,
toolchain speed, available abstractions, and source-size metrics simultaneously;
therefore they are not interchangeable with a prompt ablation.

### Static typing (`studies/types/study.json`, study `picc-types-v1`)

A second one-factor manifest holds every non-candidate block at the starter
baseline and contrasts two candidate adapters on the same Node.js 24 runtime:

- `js-untyped` (the study baseline): plain JavaScript, no type annotations, no
  static checker; the build step is `node --check`. The condition's Pi guard
  withholds `tsc`, which is present in the shared image, so the untyped arm
  cannot opt into checking.
- `ts-strict`: TypeScript with explicit annotations required and
  `tsc --strict --noEmitOnError` as the build gate, mirroring how `cargo build`
  gates the Rust baseline: a snapshot that does not type-check has no compiler
  and scores 0 on that snapshot.

The primary contrast is `ts-strict` − `js-untyped`, paired by replicate, which
the summarizer reports directly because `js-untyped` is the manifest's baseline.
JavaScript was chosen over an "unannotated Python" arm because the absence of
annotations is syntactically guaranteed rather than an instruction the agent may
ignore. Treatment fidelity (annotation density, `any`, suppressions, JSDoc type
tags, `tsc` invocations, guard blocks) is measured post hoc from the final
snapshots and event streams. Both arms run in the same image; the v4 cohort
used `picc-experiment:0.2`, which adds only `typescript@5.9.3` and
`@types/node@24.13.3` to image 0.1 (image 0.3 differs from 0.2 only by the Pi
version, 0.85.1).

### Reference

`reference-oracle` exposes at most 50 small, self-contained queries to an
evaluator-side reference compiler. Each query and observation is logged. It does
not reveal source code. The schema also supports a read-only source reference,
but the starter does not ship one because source provenance and licensing must
be vetted first.

## Minimal execution sequence

### 1. Infrastructure pilot

Run one pilot repetition for:

- `baseline`;
- `spec-brief`;
- `tests-none`;
- `language-python`;
- `reference-oracle`.

Use pilot results only to detect infrastructure defects and floor/ceiling
conditions. Do not tune prompts based on which condition appears better.

### 2. Freeze

Before confirmatory runs, run `make preflight`: with `LOCAL_MODEL_SHA256` set
it hashes the file the local endpoint reports serving and refuses a different
one (the served model file changed once between cohorts without anything in
the repository changing). Then freeze and commit:

- study manifest and all artifacts;
- Docker image ID;
- model/Pi configuration;
- visible/hidden manifests;
- budget and completion threshold;
- exclusion rules and analysis script.

### 3. Main repetitions

Use at least three independent repetitions per retained condition; five is
preferable for variance estimates. Run baseline replicate `r` and every variant
replicate `r` in a randomized block. For example, independently shuffle all
conditions within replicate 1, then replicate 2, rather than running every
baseline first.

The harness does not pin a sampling seed, and Pi exposes none for the supported
providers. `REPLICATE` identifies an independent stochastic trajectory; it is
not a bit-reproducible seed.

### 4. Post-hoc evaluation

For every run (`study-hidden-all` also scores the final snapshot with the fuzz
oracle and writes `artifacts/fuzz-scores.jsonl`):

```bash
make study-hidden-all RUN_ID=<id>
make study-report RUN_ID=<id>
```

Then aggregate:

```bash
make study-summary
```

## Candidate inputs

The evaluator hands the candidate each test after the C preprocessor
(`gcc -E -P -C -nostdinc`), the way the upstream test suite's driver hands a
student compiler its input: `#ifdef`/`#pragma` blocks are resolved, the test's
own comments are kept, and nothing is added. The GCC reference compile still
uses the original file. Ten hidden and eighteen visible tests begin with an
`#ifdef SUPPRESS_WARNINGS` block; before this change (cohorts v2–v4) they
measured an unstated rule about `#` lines rather than compilation, and five of
six v4 compilers lost the same ten tests to it. A test whose preprocessing
fails falls back to its raw text and is recorded in the evaluation's
`input_policy`.

## Bash default timeout

Pi's bash tool has no default timeout and its maintainer declined one
(earendil-works/pi#2987), so before this change (cohorts v2–v5) a program the
candidate miscompiled into an infinite loop blocked the session until the
round cap: 18 of the 20 v3–v5 main runs lost a median 34 minutes to one such
call (8.9 of 40 budget hours), condition-blind but unevenly distributed, while
99% of completed commands finished within 5 s. The image now pins the
community package `@cad0p/pi-bash-timeout@0.1.0`, loaded through the frozen
`pi/settings.json` in every condition: it re-registers the bash tool so a
command without an agent-set timeout is killed after 120 s (an explicit
timeout always wins). Each cut-off is logged as `bash_timeout_fired` and
counted in the run report and study summary (`guard_bash_timeouts`). Runs
with and without the default are not comparable; a cohort under it needs its
own manifest version.

## Outcomes

### Co-primary

Each oracle is scored on two snapshots: the **final snapshot** (whatever the
workspace held when the last round ended) and the **last buildable snapshot**
(the last frozen snapshot whose hidden evaluation built and passed the audit;
the final one when it built, 0 when none did). The round cap is blind to what
the agent is doing, and in v7 it fell inside a rewrite in two of eight runs,
turning a 0.92 compiler into a final snapshot that does not build. The
summarizer reports `hidden_score` / `fuzz_macro` for the final snapshot and
`hidden_score_last_buildable` / `fuzz_macro_last_buildable`; `study-hidden-all`
scores the last buildable snapshot with the fuzz oracle as well (a second
row, `role: last_buildable`, in `artifacts/fuzz-scores.jsonl`) when it differs
from the final one. A pre-registration names which snapshot rule is primary.

1. Final hidden macro score, equally averaging stages and valid/invalid classes
   (the corpus oracle).
2. Final-snapshot **fuzz macro**: for each stage 1..K the share of generated
   valid programs (restricted to that stage's cumulative feature subset) on
   which the candidate agrees with GCC, averaged over stages with equal weight
   (`studies/runtime/fuzz_evaluate.py`, frozen parameters `FUZZ_*` in the
   materialized configuration). Rejecting a valid program, a compiler hang,
   assembly that does not assemble, and a wrong, crashing, or hanging result
   all count against the candidate; a stage not reached within the deadline
   scores 0. The two oracles see different defects: the corpus checks
   invalid-program rejection and shallow hand-written programs, the fuzzer
   deep composed programs and the calling convention. Re-scoring the v2–v4
   finals showed each oracle promoting compilers the other rates as broken
   (`analysis/report.md` §9), so both are reported and pre-registered
   thresholds apply to each.
3. Hidden-score area under active-time trajectory.
4. Completion: hidden macro score at or above 0.95 with successful build and
   source audit.

Report finish rate and time-to-completion among completed runs. Do not replace
unfinished runs with the time limit in analyses that assume observed completion
unless explicitly using survival/censoring methods.

### Efficiency

- active elapsed seconds;
- input/output/cache tokens as reported by Pi/provider;
- model calls and tool calls;
- visible-test and reference-oracle calls;
- hidden score per million generation tokens;
- time/tokens to prespecified score thresholds when available.

Missing provider usage fields are missing data, not zero-cost evidence.

### Trajectory and artifact

- visible-score regressions;
- buildable snapshot fraction;
- insertions, deletions, and changed files;
- source files/LOC and agent-authored test files/LOC;
- compactions, provider errors, and guard-blocked calls;
- final build and anti-delegation audit;
- failure-type distribution from hidden tests.

LOC is descriptive, especially across languages. Do not treat more code as
higher quality.

## Analysis

The automated primary aggregate accepts only completed, uninterrupted `main`
runs with `protocol_comparable=true`, a positive integer replicate, and current
study/resolved-condition SHA-256 values. It verifies the retained materialization,
frozen prompt/extension/control trees, candidate adapter, visible/hidden
manifests, model/provider/thinking/revision, Docker image, and effective runtime
configuration. Pilot, resumed, incomplete, stale, or internally inconsistent
runs remain audited artifacts and appear as exclusions rather than entering a
condition summary.

Every hidden trajectory must cover every frozen snapshot in round order. The
snapshot ledger, hidden score ledger, report, and full evaluator output must
agree on the Git commit and tree, elapsed time, adapter, frozen test selection,
and per-test identities. Aggregate scores are recomputed from per-test boolean
results before inclusion. A complete one-snapshot early stop remains an outcome;
its origin-anchored trapezoid AUC is `score / 2` rather than being dropped from
condition medians.

A duplicate eligible `(condition, replicate)` is a protocol error and stops
aggregation. Shared hidden-partition, source-harness/evaluator, model, image, and
starter fingerprints must be constant across the cohort. Rendered assets and
effective configuration/budget must be constant across replicates of a
condition; declared configuration or budget conditions may differ from other
conditions. Drift stops aggregation instead of silently pooling incompatible
runs.

The reporter lists every missing condition-by-replicate cell over the included
replicate union and calls out variants lacking their same-replicate baseline.
These are coverage warnings, not silently omitted pairs. The starter is
one-factor-at-a-time: report all raw rows and pair each variant only with the
baseline sharing its replicate identifier. Use paired bootstrap/permutation
intervals when the repetition count supports it, and do not pool
language/scaffold variants into a prompt/spec treatment estimate.

A later factorial experiment should be limited to interactions justified by the
first study, such as specification detail x test feedback. Running all factors
as a full factorial initially would be expensive and difficult to interpret.

## Creation-method studies

"How the specification/test was created" cannot be separated from the artifact
by attaching a label to one document. A defensible extension should:

1. define a coverage/requirement rubric before artifact creation;
2. create several human and several LLM artifacts independently;
3. normalize delivery format and, when relevant, length bands;
4. blind reviewers to source and reject artifacts that change task scope;
5. use artifact identity as a blocking/random effect;
6. retain generation prompts, model revision, edits, reviewers, hashes, and
   creation time in provenance;
7. keep the same hidden evaluator across all artifacts.

Apply the same method to test suites. Compare both exposed-test pass rate and
hidden generalization; a generated suite that merely makes the task easier is
not evidence that its creation method is intrinsically superior.

## Exclusions and interventions

Exclude a run only for prespecified infrastructure failures that prevent the
frozen condition from being delivered, such as an extension load failure before
any model response. Model/tool mistakes, guard blocks, timeouts, build failures,
and inability to finish are outcomes, not exclusions.

Any resume is already marked noncomparable by the base harness. Report it, and
do not silently mix resumed and uninterrupted runs in the primary analysis.

## Containment limitation

`tests-none` is physically mounted with an empty agent-visible partition while
the outer harness retains the full visible evaluator. Other test conditions use
the existing in-container test tool, so the distinction between tool-only and
readable-file access is enforced by the Pi tool guard. Likewise, GCC remains in
the evaluator image and direct use is guard-blocked. The guard is an audit and
accident-prevention layer, not a security boundary against an adversarial model.

Post-hoc candidate build and compiler processes share the evaluator container and
namespace with the selected visible or hidden partition and the run-local
reference cache. Hidden scores are therefore valid only for policy-compliant,
non-adversarial candidates; they are auditable but not tamper-resistant.

Candidate source audit is scoped to the artifact actually submitted: for
Rust the Cargo package's `src/` tree plus any file it pulls in by path
(`#[path]`, `include!`), for JavaScript/TypeScript the adapter's declared
roots plus the entry module's import closure; symlinks and vendored binaries
are policy failures everywhere. Test drivers and fuzzers the agent keeps
outside those roots are its own tooling and are not audited. Until v6 this
paragraph said the opposite for Rust ("treat that result as an outcome") while
the Node audit had already been scoped after the v4 incident; v6 Amendment 2
records the conflict and its resolution. Python candidates are still scanned
workspace-wide.

Treat bypass attempts as protocol violations and report them. A stronger later
study should move tests/reference compilation into a separate service and mount
no corpus or compiler in the agent container.
