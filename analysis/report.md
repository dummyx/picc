# PiCC: what changes the compiler a coding agent builds

Eight batches, 71 planned in advance main runs, one model building a C compiler
from an empty repository under a fixed budget. Prompts, specifications, test
access, test feedback, and static typing were each varied one at a time; the
last batch crossed specification detail with test access.

## Summary of the campaign (v2–v9)

**No manipulated factor detectably changed behavioral correctness on the
corpus oracle.** Every contrast sits inside the planned in advance noise band
once the harness stopped manufacturing differences; the one contrast beyond
the band on the fuzz oracle (v9, tests withheld under the full specification)
has an identified mechanism and awaits replication (§15):

| Batch | Factor (variant vs baseline) | n per arm | Corpus, paired median | Fuzz, paired median | Harness state |
|---|---|---:|---:|---:|---|
| v2 (§1–6) | four prompt/specification strategies | 3 | within one sd (0.039) of baseline | all at ceiling | original oracle; hang hazard |
| v3 (§7) | tests withheld | 3 | −0.136 (candidate effect) | −0.238 (re-score) | original oracle; hang hazard |
| v4 (§8) | TypeScript strict vs JavaScript | 3 | +0.026 | 0.000 (re-score) | original oracle; hang hazard |
| v5 (§10) | tests withheld | 4 | −0.022 | −0.044 | revised oracle; hang hazard |
| v6 (§12) | tests withheld | 4 | −0.017 | 0.000 | clean |
| v7 (§13) | TypeScript strict vs JavaScript | 4 | +0.004 | +0.001 | clean |
| v8 (§14) | test reports pushed every 10 min | 4 | −0.025 | −0.002 | clean, last-buildable rule |
| v9 (§15) | minimal specification (with tests / without) | 3 | −0.070 / +0.046 | −0.020 / +0.200 | clean, 2×2 |
| v9 (§15) | tests withheld (full spec / minimal spec) | 3 | −0.104 / −0.067 | **−0.200** / +0.016 | clean, 2×2 |

The v3 candidate effect was the hang lottery (§10.3, §11): in every batch
before v6 the dominant variance was a shell command that never returned,
and once bounded (§12.1) the spread of the corpus score fell from 0.50 to
0.08 and every contrast collapsed to noise.

**What the factors do change is the work, not the product.** A 143-word
specification with no behavioral rules produces a compiler within noise of
the full one on both oracles, but 60–80% larger and with features the task
never asked for (§15.5); withholding
tests costs about 100 more turns and 500 more lines of compiler (§12.5);
pushing test reports halves on-demand test calls and multiplies self-written
tests tenfold (§14.5); strict typing adds 40% more source and an order of
magnitude more self-tests in fewer turns (§13.5); the specification
strategies cost 50–90% more tokens for the same result (§11). Time and
correctness are the same throughout: this model saturates stages 1–10 in
90 active minutes whatever it is told.

**The harness was the experiment.** Eight measurement defects were found and
fixed, each large enough to have produced a false result: an output-token
cap (§3.1), workspace-wide source audits in two languages (§3.2, §8.5,
§12.4), a terminal round timeout (§3.3), the `#ifdef` preprocessing artifact
(§3.5, §9), Pi's shell tool having no default timeout (§12.1), the
round cap falling inside refactors (§13.4, §14.4), an advisory audit note
disqualifying a buildable snapshot (§15.4), and a workspace-wide manifest
audit zeroing a compiler for its developer tooling (§15.4). Each was found by a
planned in advance check, logged as an amendment, and repaired for the next
batch without touching the running one. Analysis code, experiment plans,
and raw ledgers for every batch are in this repository.

- Date: 2026-08-25 (§§1–6, the v2 batch); §7 and §8 added 2026-09-07 for the v3 and v4 batches at stages 1–10; §9 added 2026-09-09 (every final re-scored with the fuzz oracle); §10 added 2026-09-11 (the v5 batch under the revised oracle); §11–12 added 2026-09-12 (tokens/time/code exploration; v6 with the bash default timeout); §13 added 2026-09-12 (v7, static typing on the clean harness); §14 added 2026-09-13 (v8, pushed feedback and the last-buildable rule); §15 added 2026-09-14 (v9, specification detail × test access)
- Model: local Qwen3.8-27B (UD-Q4_K_XL) via llama.cpp, single RTX 5090
- Profile: pilot — 45-min round cap, 2 h wall budget, stages 1–6
- Scoring: hidden-partition macro average over 59 held-out tests, never shown to
  the agent. Per stage, valid and invalid classes are averaged separately, then
  averaged across stages.

---

## 1. Results

Five conditions, each one change away from baseline, three replicates each.

| Condition | What changed from baseline |
|---|---|
| `baseline` | — (detailed behavioral spec in `TASK.md`, 40-line workflow prompt) |
| `prompt-minimal` | Workflow, sequencing, regression and progress-memory instructions removed from every prompt surface |
| `spec-brief` | Detailed spec replaced by a 42-line product brief of the same scope |
| `spec-architecture` | Full behavioral spec **plus** prescribed lexer/parser/sema/IR/codegen boundaries |
| `spec-inline` | Same spec, delivered once in the opening request instead of a persistent file |

### Per condition

| Condition | n | Median | Mean | Range | Reached 0.95 | Perfect visible |
|---|---:|---:|---:|---|---:|---:|
| `spec-inline` | 3 | 0.9583 | 0.9383 | 0.898–0.958 | 2/3 | 2/3 |
| `prompt-minimal` | 3 | 0.9583 | 0.9313 | 0.877–0.958 | 2/3 | 2/3 |
| `baseline` | 3 | 0.8981 | 0.9182 | 0.898–0.958 | 1/3 | 1/3 |
| `spec-brief` | 3 | 0.8981 | 0.9112 | 0.877–0.958 | 1/3 | 1/3 |
| `spec-architecture` | 3 | 0.8704 | 0.8974 | 0.863–0.958 | 1/3 | 1/3 |

Batch: n=15, mean 0.9193, **SD 0.0392**, range 0.8634–0.9583. Seven of fifteen
runs met the study's completion threshold (hidden ≥ 0.95 with a clean build and
audit).

### Every run

| Condition | Rep | Rounds | Min | Visible | Hidden | Termination |
|---|---:|---:|---:|---:|---:|---|
| `baseline` | 1 | 2 | 76 | 1.0000 | 0.9583 | complete after review |
| `baseline` | 2 | 2 | 90 | 0.9429 | 0.8981 | stalled ×2 |
| `baseline` | 3 | 3 | 106 | 0.9373 | 0.8981 | stalled ×2 |
| `prompt-minimal` | 1 | 2 | 90 | 1.0000 | 0.9583 | stalled ×2 |
| `prompt-minimal` | 2 | 2 | 90 | 1.0000 | 0.9583 | stalled ×2 |
| `prompt-minimal` | 3 | 2 | 90 | 0.0000 | 0.8773 \* | stalled ×2 |
| `spec-architecture` | 1 | 2 | 90 | 0.9369 | 0.8704 | stalled ×2 |
| `spec-architecture` | 2 | 2 | 90 | 0.9413 | 0.8634 | stalled ×2 |
| `spec-architecture` | 3 | 2 | 90 | 1.0000 | 0.9583 | stalled ×2 |
| `spec-brief` | 1 | 4 | 120 | 1.0000 | 0.9583 | complete after review |
| `spec-brief` | 2 | 2 | 90 | 0.9429 | 0.8981 | stalled ×2 |
| `spec-brief` | 3 | 2 | 90 | 0.9429 | 0.8770 | stalled ×2 |
| `spec-inline` | 1 | 2 | 90 | 0.9548 | 0.8981 | stalled ×2 |
| `spec-inline` | 2 | 3 | 104 | 1.0000 | 0.9583 | complete after review |
| `spec-inline` | 3 | 2 | 90 | 1.0000 | 0.9583 | stalled ×2 |

\* Recorded as 0.0000 by the evaluator; re-scored after correcting an audit false
positive. See §3.2.

---

## 2. What the results say

### 2.1 No strategy separated from baseline

Every condition's median sits within one batch standard deviation of baseline's.
The two nominally ahead of baseline — `spec-inline` and `prompt-minimal` — are
ahead by 0.06, which is 1.5 SD in a comparison with three observations per cell.
At n=3 this design resolves differences of roughly 0.13; nothing here approaches
that.

This is a real finding, not merely an absence of one, because two of the
conditions are substantial interventions. `prompt-minimal` removes *all*
procedural instruction — increments, stage ordering, regression discipline,
progress memory — and matched or beat the full workflow prompt in every
replicate. Whatever that scaffolding is doing, it is not visible in the outcome
here.

### 2.2 More specification detail did not help; prescribing structure may hurt

Ordering the conditions by how much guidance they supply produces no
corresponding ordering in score. The most prescriptive condition,
`spec-architecture`, has the *lowest* median. Its first two replicates finished
last in the batch (0.8704, 0.8634) before the third reached the ceiling, so the
effect is not reliable — but no replicate of it ever beat the least prescriptive
conditions, across two different versions of the condition and five runs total.

An earlier single run had made `spec-architecture` look like the clear winner.
Replication reversed that reading entirely, and the reversal is the point: at one
run per condition this batch's own spread would have supported almost any
conclusion we cared to draw.

### 2.3 The task saturates

Seven of fifteen runs cleared the completion threshold, and eight of fifteen
scored one of exactly two values — 0.9583 (57/59) or 0.8981 (50/59). With only 59
hidden tests the outcome is not continuous; it is a few discrete rungs. Every
condition reached the top rung at least once.

A measurement whose ceiling is routinely hit cannot rank the things being
measured. Stages 1–6 with a 2-hour budget is now too easy to discriminate between
prompt strategies, which is a consequence of the harness fixes below working.

### 2.4 Where the agent puts its scratch work decides whether extra time compounds

Each round runs in a fresh container: `/workspace` persists, `/tmp` does not.
Agents that built their test scaffolding under `/workspace` (`tests-local/`,
`tests/`) kept it between rounds; agents that used `/tmp` lost it every round and
spent the next one rebuilding.

The consequences are visible directly. `spec-inline-r1` gained **+0.093 hidden**
from its second round because its work persisted. `spec-architecture-r1` gained
nothing: round 0 stalled running its battery from `/tmp/picctest`, and round 1
spent all of its two turns recreating that scaffolding before stalling again.
`baseline-r2` and `spec-brief-r3` show the same zero-progress signature.

Nothing in any prompt tells the agent which paths survive. This is both a cheap
thing to fix and a plausible confound, since a condition that happens to nudge
toward `/workspace` scaffolding gains more from every extra round.

---

## 3. Defects found, and why they matter more than the rankings

Each of these was large enough to change a conclusion. All were found *after*
producing plausible-looking results.

### 3.1 An output ceiling was suppressing every early run

`LOCAL_MAX_OUTPUT` was 32768. This model's thinking sometimes exceeds that, and
when it does the turn dies mid-thought carrying only reasoning — no tool call,
nothing committed. Whole rounds evaporated; what looked like the agent "musing
without acting" was truncation.

Raising it to 65536 took the same baseline condition from 5 turns with 3
truncated to **95 turns with 1**, in identical wall time. Nineteen turns were lost
this way across the earlier runs.

### 3.2 The source audit produced two spurious zeros by two different mechanisms

The audit gated scoring on *any* finding, so a policy slip and a cheating attempt
were indistinguishable — both produced 0.000.

- **Environment inspection.** A run wrote `std::env::var("SIM_TRACE")`, a debug
  flag, and scored 0.000 with a compiler that in fact scores **0.8773** — above
  baseline's median. Findings are now split into *blocking* (delegation to a real
  compiler, subprocess spawning, symlink escape, disallowed dependencies) and
  *advisory*; advisory findings are recorded through `audit_ok` while the
  candidate is still built and scored.
- **A regex false positive.** The pattern `\bexec[lvpe]*\s*\(`, meant to catch C's
  `execl`/`execv` family, permits zero suffix characters and so matches any method
  named `exec(`. An agent's reference interpreter with `fn exec(...)` was
  classified as subprocess invocation, marked blocking, never built, and scored
  0.0000. Its true score is **0.8773**. The pattern now requires a real suffix,
  verified to still match `execl`, `execve`, `execvp`, and `libc::execv`.

Both defects were worth more than any treatment effect measured here. A hard gate
built on regex heuristics, in an experiment whose outcome is a single number, can
silently invert a ranking.

### 3.3 One stalled round used to end the whole run

The agent routinely deadlocks running a binary its own half-built compiler
produced, and Pi's shell tool has no timeout. A timed-out round previously
terminated the run, so a single runaway child process ended runs with most of
their budget unspent — and how long a run lived was set by when it happened to
hang, which correlates with how much a condition encourages self-testing.

A stalled round is now snapshotted and followed by another; the run ends after two
consecutive stalls. The effect was decisive:

- `prompt-minimal-r2` scored **0.0000** in round 0, killed mid-refactor with a
  non-compiling tree, then repaired it and reached **1.0000 visible / 0.9583
  hidden** in round 1.
- `spec-inline-r1` went **0.8056 → 0.8981** in the round the fix bought.
- Before the fix, no run in the project had ever reached completion. Seven of
  fifteen now do.

The fix is partial: run length still depends on stall luck, because a run that
yields voluntarily resets the counter and keeps going while one that stalls twice
stops. `spec-brief` got four rounds in one replicate and two in the next.

### 3.4 Two conditions were not testing what they claimed

- **`prompt-minimal`** overrode only `AGENTS.md`. The initial and continuation
  requests are shared across conditions, and they re-supplied every instruction it
  removed — "smallest end-to-end vertical slice first", "work on the
  lowest-numbered incomplete or regressed stage", "update `PROGRESS.md`", "do not
  only summarize status". It now has its own stripped request prompts.
- **`spec-architecture`** contained 210 words of behavioral content against
  baseline's 695 — essentially `spec-brief`'s level of detail — so comparing it to
  baseline conflated *added structure* with *removed detail*. It is now the full
  behavioral spec plus the architecture sections, differing from baseline by one
  thing.

Results in §1 use the corrected conditions. Earlier runs are not comparable to
them.

### 3.5 The corpus verifies semantics through a single byte

Raised in review and confirmed. For valid programs the evaluator is genuine
differential testing against GCC — it compares exit status, stdout and stderr —
but **224 of the 227 valid tests produce no stdout**. They are
`int main(void) { …; return <int>; }`, so the only compared observable is the
process exit status: one byte. `chapter_2/valid/negate_int_max.c` returns
-2147483647, which masks to exit status 1; the test nominally covers negating
`INT_MAX` and actually checks "did it exit 1". Only 11 distinct literal return
values appear across the whole valid set.

The invalid class was weaker still: it checked nonzero exit and no output file,
so a compiler rejecting for entirely the wrong reason scored identically to one
diagnosing correctly, and a compiler rejecting *everything* passed the class
outright. It now also requires a non-empty diagnostic (`silent_rejection`).

The corpus is thin here partly by construction: the split excludes `libraries`
and `helper_libs`, which are exactly the multi-file tests that check
cross-translation-unit behaviour and ABI argument passing against real values.

`analysis/fuzz_differential.py` implements the standard remedy — Csmith-style
random generation with differential testing against GCC (Yang et al., PLDI 2011),
undefined behaviour excluded at generation time, and generation policies in the
spirit of YARPGen (OOPSLA 2020). Programs are generated and evaluated
simultaneously under 32-bit semantics, so the tool's own computed value acts as a
second oracle checked against GCC before the candidate is consulted; a generator
error is reported as a skip rather than blamed on the compiler. Where the subset
permits calls, `--stdout-checksum` emits the result through `putchar` to recover
a wide observable; below that, resolution comes from volume.

It discriminates, and it finds what the corpus cannot:

| Candidate | Corpus hidden | Fuzz result |
|---|---:|---|
| `v2-baseline-r1` | 0.9583 | 0 mismatches in 3,600 programs |
| `v2-spec-architecture-r2` | 0.8634 | 21/300 miscompilations at stage 6; **600/600 link failures at stage 10** |

The stage-10 failure is a single concrete bug: that compiler emits file-scope
objects as bare `g0` lines instead of `g0:` labels, so the assembler rejects them
as unknown instructions. Every run in this study used stages 1–6, so no scoring
in the entire project could have detected it.

Read the other way, the exercise also *confirms* a corpus verdict: the compiler
the corpus called complete survived 3,600 randomly generated programs without a
single disagreement. The corpus is low-resolution, not wrong.

---

## 4. Secondary observations

**Tool uptake.** In the earlier batch, every run that called the provided test
tool scored ≥ 0.863 and no run that ignored it exceeded 0.877, with both
catastrophic failures coming from runs that never touched it. That was the
strongest signal in the data at the time. It is confounded with run quality and
was not tested directly; it remains the most actionable open hypothesis.

**Compaction always evicts the opening request.** Every compacting run dropped
42–139 leading entries at ~127k tokens, always including the opening request. For
`spec-inline`, whose specification exists *only* there, this means the controlling
document was evicted mid-run — and it still produced the joint-highest median in
the batch. Specification persistence appears to matter less than expected once
the code exists.

**A shared blind spot.** Eight of nine compilers in the earlier batch failed on
`unexpected character '#'` at line 1. Independently written compilers converged on
the same missing feature.

**Failure profile at the ceiling.** The three highest-scoring runs failed on
exactly the same two hidden tests, both `unexpected_accept` — invalid programs
accepted rather than rejected. The residual gap is validation strictness, not code
generation.

---

## 5. Limitations

- **Three replicates resolve ~0.13.** The differences of interest are ~0.05. This
  batch can rule out large effects; it cannot establish small ones.
- **The measure saturates.** Seven of fifteen runs hit the completion threshold and
  the outcome takes only a few discrete values.
- **Run length is not controlled.** Rounds per run varied 2–4 depending on stall
  luck, and that interacts with condition.
- **One model, one task.** A single local 27B checkpoint on a compiler task with an
  unusually crisp oracle. Conclusions about specification strategy may travel
  poorly to work with fuzzy requirements.
- **Scores here predate the semantic-verification work (§3.5).** They measure
  agreement with GCC's exit byte on 59 programs. The reported ceiling is partly
  the measure's, not the task's — a one-byte oracle saturates sooner than the
  underlying problem does.
- **The server is not archived.** Client configuration is frozen; `llama-server`'s
  own behavior during runs is not captured.

---

## 6. What follows

1. **Fold differential fuzzing into scoring.** `analysis/fuzz_differential.py`
   already discriminates between candidates the corpus rates similarly, and it
   reaches stages the corpus never ran. Making it a scored component replaces a
   1-byte, 59-sample oracle with an unbounded one and directly addresses the
   ceiling.
2. **Raise the difficulty.** Stages 1–10 (main profile), or a tighter budget, so
   conditions have headroom to differ in. Ranking is impossible against a ceiling.
3. **Test tool uptake directly.** It is the largest signal observed and the most
   actionable if it holds.
4. **Tell the agent which paths persist**, and record where it scaffolds. Cheap to
   do, removes a confound, and is itself a finding about agent usage.
5. **Capture tool-call durations.** No timing exists on tool events, so "where did
   the time go" is unanswerable and the data is unrecoverable after the fact.
6. **Report audit-pass separately from quality** in all analyses, and treat every
   audit pattern as a hypothesis until a human has read the match.
7. **Reconsider end-state scoring.** A run is scored on its final snapshot, so
   being killed mid-refactor reads as total failure.

---

## 7. v3: withholding tests at stages 1–10 (summary)

Planned in advance (`docs/EXPERIMENT_PLAN.md`), run 2026-09-02, main profile: 2 h
wall, 45-min round cap, stages 1–10, hidden partition of 104 tests. Three
replicates of `baseline` (Rust, failure-level `test_visible`) against
`tests-none` (no agent-visible tests or scores).

| Rep | `baseline` hidden | `tests-none` hidden | Δ (none − baseline) |
|---:|---:|---:|---:|
| 1 | 0.8188 | 0.8458 | +0.027 |
| 2 | 0.9306 | 0.7492 | −0.181 |
| 3 | 0.8194 | 0.6839 | −0.136 |

Paired median −0.136 against the pre-declared 0.13 threshold: a candidate
effect warranting replication, not a confirmed one (one replicate reversed).
At this difficulty the saturation of §2.3 is gone (no run reached 0.95;
batch SD 0.084), and `tests-none` used roughly half the tokens of `baseline`.
Provenance correction recorded 2026-09-07: this batch ran on the re-downloaded
model file (SHA-256 `3f227079…`), not the file its experiment plan quoted.

---

## 8. v4: static typing — TypeScript strict versus plain JavaScript

**Headline: requiring static types with a strict type-checker as the build gate
did not measurably change hidden correctness.** Paired median +0.026 in favour
of the typed arm, below the pre-declared 0.13 threshold; the largest paired
difference (+0.071) is one agent's handling of a lexer corner case, and the
typed arm's best-scoring compiler cannot compile a call with two arguments.

Planned in advance before the first run (`docs/EXPERIMENT_PLAN_v4.md`, amended
during the batch); run 2026-09-06/07 on the same model
file, prompts, specification, tests, and budgets as v3.

### 8.1 Design

Two candidate adapters on the same Node.js 24 runtime, everything else held at
the v3 baseline (the initial and continuation prompts are byte-identical to v3;
`TASK.md` and `AGENTS.md` differ only in the language, build, entry, and
dependency-policy slots):

| Condition | Language | Build gate | Type checker |
|---|---|---|---|
| `js-untyped` (study baseline) | plain JavaScript | `node --check src/picc.js` (syntax only) | withheld: `tsc` is in the image but the condition's guard blocks it |
| `ts-strict` | TypeScript, explicit annotations required | `tsc --strict --noEmitOnError` — a snapshot with a type error has no compiler and scores 0 | available and mandatory |

JavaScript, rather than "Python without annotations", was the untyped arm
because in JavaScript the absence of annotations is a property of the language
rather than an instruction — and §4 showed prompt instructions are followed
about half the time. Image `picc-experiment:0.2` adds only `typescript@5.9.3`
and `@types/node@24.13.3` to the v3 image. Order: randomized blocks from the
study seed, six 2-hour runs in sequence.

### 8.2 Results

| Rep | Condition | Rounds | Min | Visible | Hidden macro | Hidden micro | `tsc` calls | `test_visible` | Out tokens | LOC |
|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | `ts-strict` | 2 | 91 | 0.8602 | **0.8389** | 0.8365 | 19 | 3 | 297k | 2096 |
| 1 | `js-untyped` | 2 | 90 | 0.8930 | **0.8833** | 0.8654 | 0 | 137 | 278k | 1423 |
| 2 | `ts-strict` | 2 | 90 | 0.8709 | **0.8653** | 0.8462 | 24 | 8 | 302k | 2113 |
| 2 | `js-untyped` | 2 | 90 | 0.8641 | **0.8389** | 0.8365 | 0 | 0 | 143k | 1678 |
| 3 | `ts-strict` | 2 | 90 | 0.9202 | **0.8986** | 0.9038 | 14 | 7 | 186k | 1514 |
| 3 | `js-untyped` | 2 | 90 | 0.8736 | **0.8278** | 0.8173 | 0 | 6 | 223k | 1274 |

| Condition | n | Median | Mean | Range | SD | Hidden AUC (median) |
|---|---:|---:|---:|---|---:|---:|
| `ts-strict` | 3 | 0.8653 | 0.8676 | 0.839–0.899 | 0.030 | 0.654 |
| `js-untyped` | 3 | 0.8389 | 0.8500 | 0.828–0.883 | 0.029 | 0.629 |

Paired differences (typed − untyped): −0.044, +0.026, +0.071; **median +0.026**
(mean +0.018). Batch n=6, mean 0.859, SD 0.028 — the tightest batch so far.
Every run ended by two consecutive 45-minute stalls at 1.5 h, every final
snapshot built and passed the audit, and no `ts-strict` snapshot was ever lost
to the type gate: all six typed snapshots type-checked. The visible–hidden gap
is 0.01–0.05 in both arms.

Under the planned in advance rule the contrast is compatible with no detectable
effect at this sample size. Two further observations make it weaker than that
number suggests.

**The variance is one lexer corner case.** Ten hidden tests (chapters 4–7)
begin with `#ifdef SUPPRESS_WARNINGS` preprocessor lines. Five of the six
compilers reject them at line 1 ("unexpected character '#'", each in its own
wording); only `ts-strict` replicate 3 skips such lines. That single feature is
the entire +0.071 of replicate 3 and most of the spread between arms. Three
tests fail in all six runs (a block-scope function declaration, an assignment to
a conditional expression that every compiler accepts, and a `#`-prefixed
chapter-9 file); four of six reject block-scope `static`. If only the tests
that every run fails had failed, the macro score would be 0.971; the batch's
0.83–0.90 range is a handful of shared gaps plus the `#` lottery. The same gap
appeared in eight of nine v2 runs (§2.3).

**The corpus and the fuzzer disagree about the best typed compiler.**
Differential fuzzing of each final snapshot against GCC (200 generated programs,
stage-10 features, seed 20260830; `analysis/fuzz_differential.py --runner node`):

| Final snapshot | Corpus hidden | Fuzz mismatches / 200 |
|---|---:|---:|
| `v4-ts-strict-r1` | 0.8389 | 0 |
| `v4-ts-strict-r2` | 0.8653 | 0 |
| `v4-ts-strict-r3` | 0.8986 | **190** (rejects every call with ≥2 arguments) |
| `v4-js-untyped-r1` | 0.8833 | 0 |
| `v4-js-untyped-r2` | 0.8389 | 0 |
| `v4-js-untyped-r3` | 0.8278 | 0 |
| `v3-baseline-r1` (Rust) | 0.8188 | 0 |
| `v3-baseline-r2` (Rust) | 0.9306 | 43 (wrong results, crashes) |
| `v3-baseline-r3` (Rust) | 0.8194 | 26 (wrong results, crashes) |

`v4-ts-strict-r3`'s round-1 edit added comma-separated file-scope declarators
and broke argument-list parsing: `f(1, 2)` now fails with "expects 2, got 1".
Round 0 had passed the chapter-9 multi-argument tests; the final snapshot fails
the two hidden tests that exercise them and is otherwise the corpus's favourite.
A strict type-checker is silent on this kind of regression, and the visible
corpus exercises multi-argument calls too rarely for `test_visible` to flag it.
Under the fuzz oracle the typed arm has the only broken compiler in the batch
and the paired contrast for replicate 3 reverses sign. §6.1's recommendation to
fold the fuzzer into scoring stands; here it would have changed the ranking.

### 8.3 Was the treatment delivered?

Yes, cleanly in both directions (`analysis/typing-metrics.md`):

- `ts-strict`: `tsc` invoked 14–24 times per run; every function parameter
  annotated (share 1.0 in all three runs); explicit return types on 15/16,
  38/38, 8/8 declared functions; 5–28 interfaces and 9–10 type aliases per run;
  `any` used 0, 5, and 0 times; no `@ts-nocheck`/`@ts-ignore`/`@ts-expect-error`
  anywhere; no `.js` source in `src/`.
- `js-untyped`: zero JSDoc type tags, zero `.ts` files, zero attempts to run
  `tsc` (the typing guard never fired); `node --check` used 2–12 times per run.

So the null is not "the agent ignored the types". The typed agents wrote fully
annotated, strictly checked code and paid for it: median output tokens 297k
versus 223k, median tool calls 261 versus 171, median 2096 versus 1423 lines,
hidden score per million generation tokens 1.67 versus 1.96. The extra work
bought no measurable hidden correctness and, in one run, coincided with a
regression the checker could not see.

### 8.4 Process notes

- Every run ended by double stall at 1.5 h (as in v3): the stall-dominated regime
  is now the default at this difficulty. Compactions 1–3 per run, truncated
  thinking turns 2–5 per run, in both arms.
- `test_visible` uptake stays erratic: 137 calls in `js-untyped` replicate 1
  (the highest-scoring untyped run) against 0 and 6 in its siblings, 3–8 in the
  typed arm. The tool-uptake correlation of §2 does not appear here at n=6.
- The JavaScript agents self-test by spawning their own compiler from JavaScript
  drivers (`.scratch/`, `dev/`); the TypeScript agents self-test from bash. That
  difference produced the harness incident below.
- `js-untyped` replicate 2 committed ~3,000 scratch files (fuzz outputs), so its
  churn metrics are meaningless; source LOC is unaffected.
- Against the v3 Rust baseline (same prompts, tests, budget, and model file;
  different image patch level and harness revision, so descriptive only): Rust
  median 0.819, both Node arms 0.839–0.865. The best single run remains Rust
  replicate 2 (0.931), which the fuzzer rates as broken.

### 8.5 A harness incident, and what it says about audits

The first launch was aborted after 2.6 hours and restarted under an amendment.
The untyped agent's fuzz driver (`.scratch/fuzz2.js`) spawned the compiler via
`child_process`, and the source audit — which scanned every `.js` file in the
workspace — zeroed the snapshot as a blocking "subprocess" finding although
`src/picc.js` was clean. Because JavaScript agents write JavaScript drivers and
the typed adapter never scans a TypeScript agent's `.js` helpers, the rule cut
the arms asymmetrically: a run ending with such a driver would have scored 0 on
the primary endpoint by artifact, inverting the contrast for reasons unrelated
to typing — the §3.2 failure mode again, in a new language. The audit now scans
the adapter's declared source root plus the entry module's import closure, so a
module the compiler imports is still audited while test drivers are not; the two
affected runs are quarantined (`runs/.quarantine-v4/`). General lesson: a
blocking audit must be scoped to the artifact actually submitted, never to the
workspace, or it measures the agent's testing habits.

### 8.6 Limitations

- Three replicates resolve ~0.13; the observed difference is ~0.03.
- Both arms are the same model's competence in one language family; the result
  says nothing about a language the model knows less well, or about a project
  large enough for types to matter as documentation.
- The type gate never bound. A task that stresses data-structure invariants
  more than this parser-to-assembly pipeline might behave differently.
- The typed treatment bundles "annotate everything" with "the checker must
  pass"; this design cannot separate them.
- The corpus samples multi-argument calls and preprocessor-prefixed files
  thinly; §8.2 shows both distorting the ranking. Fuzz-based scoring (§6.1) is
  the remedy and is still descriptive here.

---

## 9. Every final re-scored with the fuzz oracle

**Headline: the corpus and the fuzz oracle disagree about which compilers are good,
and the disagreement is not noise.** All 27 batch finals (v2, v3, v4) were rebuilt
from their committed snapshots and fuzzed against GCC. The v3 result gets stronger
under the fuzz oracle, the v4 null stays null with its best typed run becoming its
worst, and thirteen v2 compilers that the corpus spreads over 0.877–0.958 are
indistinguishable at the fuzzer's resolution. Full tables:
[`fuzz-rescore.md`](fuzz-rescore.md); regenerate with `analysis/fuzz_rescore.py`.

### 9.1 Method

Each final snapshot is exported from its run workspace, built inside the pinned image
exactly as the evaluator builds it, and run through `analysis/fuzz_differential.py`
on the host, which generates UB-free C programs from the batch's cumulative feature
subset, compiles them with GCC as the reference, and compares exit status and stdout.
Two views: **full scope** (300 programs using every feature of the batch's task at
once, one seed) and **fuzz macro** (100 programs at each of stages 1..K, seeded per
stage, averaged with equal stage weights like the corpus macro score). A single broken
feature fails every full-scope program; the stage average grades it. Rejecting a valid
program, failing to assemble, crashing, hanging, and wrong results all count as
failures. No score here changes any planned in advance primary endpoint.

### 9.2 What the fuzzer found that the corpus did not

| Final | Corpus hidden | Fuzz macro | Defect (stages affected) |
|---|---:|---:|---|
| `v3-tests-none-r3` | 0.684 | 0.228 | SIGFPE on nested `%`/`/` and wrong results from stage 3; invalid register forms at stages 9–10 |
| `v3-tests-none-r2` | 0.749 | 0.715 | wrong `&&`/`\|\|` results with bitwise operands from stage 4; loops that hang from stage 8 (47 of 100 programs time out); invalid assembly at stage 9; cannot parse an initialized file-scope variable (stage 10: 0.00) |
| `v3-baseline-r2` | **0.931** (batch best) | 0.953 | segfaults on calls with seven or more arguments (stages 9–10: 0.72, 0.81) |
| `v3-baseline-r3` | 0.819 | 0.956 | wrong results in nested conditionals from stage 6 |
| `v4-ts-strict-r3` | **0.899** (batch best) | 0.806 | rejects every call with two or more arguments (stages 9–10: 0.04, 0.02) |
| `v2-spec-architecture-r1` | 0.870 | 0.820 | wrong results from stage 2 (unary/binary nesting) |
| `v2-spec-architecture-r2` | 0.863 | 0.968 | wrong results from stage 4 |

Every other final (20 of 27) agrees with GCC on every generated program at every
stage. The corpus's residual spread among those twenty is the `#ifdef` lexer gap
(§8.2), invalid-program rejection, and a few shared parse gaps; none of it is
codegen quality.

### 9.3 Batch conclusions under both oracles

| Batch | Planned in advance contrast | Corpus paired median | Fuzz macro paired median | Rank agreement (Spearman ρ, corpus vs fuzz macro) |
|---|---|---:|---:|---:|
| v3 | `tests-none` − `baseline` | −0.136 | −0.238 (per-replicate 0.000, −0.238, −0.728) | 0.55 |
| v4 | `ts-strict` − `js-untyped` | +0.026 | 0.000 (per-replicate 0.000, 0.000, −0.193) | −0.17 |
| v2 | five conditions vs `baseline` | no separation (§2.1) | no separation: 13/15 finals at 1.000 | 0.62 |

- **v3 gets stronger.** Two of the three compilers built without test access have
  deep semantic defects that the corpus priced at 0.68 and 0.75 but that break
  most generated programs from stage 3 or 4 onward. Withholding tests did not
  merely lower scores; it produced compilers that are wrong on ordinary arithmetic
  and logic. The candidate effect of §7 is, if anything, understated by the
  corpus. (n=3, one replicate at zero difference under both oracles.)
- **v4 stays null, and the typed arm's best run is its worst compiler.** Under
  the fuzz oracle the two arms are identical in two replicates and the third
  reverses sign. Nothing in the re-score suggests a typing effect hiding behind
  the corpus.
- **v2's ranking dissolves.** Thirteen of fifteen finals are perfect at the
  fuzzer's stage-6 resolution; the corpus spread them across 0.877–0.958 and
  ranked conditions by it. The two imperfect ones are both `spec-architecture`,
  which §2.2 already flagged as the condition with the blown-out floor.

### 9.4 What this means for scoring

The two oracles see different things. The corpus checks invalid-program rejection,
diagnostics, and a fixed set of valid programs with shallow expressions; the fuzzer
checks deep, composed valid programs and never touches rejection. Neither alone
ranks these compilers correctly: the corpus promotes crashing and argument-blind
compilers to the top of two batches, and the fuzzer cannot see a compiler that
accepts every invalid program. The scoring change proposed in §6.1 should therefore
add the fuzz macro as a co-primary endpoint alongside the corpus macro rather than
replace it, with the stage-averaged form so that one broken feature does not zero a
compiler, and it should be planned in advance before the next batch. Two mechanical
follow-ups: the fuzzer now records a hanging program as a `timeout` mismatch instead
of aborting the batch (it lost two stage cells on the first pass), and the
preprocessor-prefixed test files (§8.2) should be handled at the corpus or
specification level so that the corpus measures compilation rather than an
unstated rule.

---

## 10. v5: test availability under the revised oracle

**Headline: the v3 candidate effect did not replicate.** Four replicates per arm
under the revised harness give paired medians of −0.022 (corpus) and −0.044
(fuzz macro), with one replicate past the 0.13 threshold in each direction on
both oracles. What the batch shows instead is a bimodal outcome: five of eight
compilers are near-perfect and three are broken on every valid program, and the
broken ones are the runs that hung early on their own self-tests, in either arm.

Planned in advance (`docs/EXPERIMENT_PLAN_v5.md`),
run 2026-09-10, main profile (2 h, 45-min round cap, stages 1–10), same
prompts, partitions, adapter, budgets, and model file as v3.

### 10.1 What changed from v3

The harness revision of §9.4, applied and frozen before any v5 run: candidate
inputs are preprocessed the way the upstream suite's driver does it (the ten
hidden `#ifdef`-prefixed tests no longer measure an unstated rule), the
stage-averaged fuzz macro runs inside the frozen harness on every final
snapshot as a co-primary endpoint (100 generated programs per stage, verified
by the summarizer like the corpus ledger), and the chain verifies the served
model file's digest before each slot. Both pilots exercised the whole path.

### 10.2 Results

| Rep | Condition | Rounds | Min | Turns | `test_visible` | Visible | Hidden macro | Fuzz macro | Per-stage fuzz |
|---:|---|---:|---:|---:|---:|---:|---:|---:|---|
| 1 | `baseline` | 2 | 90 | 342 | 27 | 0.9830 | **0.9667** | **1.000** | all 1.00 |
| 1 | `tests-none` | 2 | 90 | 141 | 0 | 0.9251 | **0.9038** | **0.912** | 1 1 1 .80 .91 .93 .84 .93 .84 .87 |
| 2 | `baseline` | 2 | 90 | 336 | 17 | 0.9618 | **0.9556** | **1.000** | all 1.00 |
| 2 | `tests-none` | 2 | 90 | 158 | 0 | 0.9445 | **0.9736** | **1.000** | all 1.00 |
| 3 | `baseline` | 2 | 90 | 131 | 0 | 0.7863 | **0.7222** | **0.392** | 1 1 1 .47 .24 .08 .07 .05 .01 0 |
| 3 | `tests-none` | 2 | 91 | 72 | 0 | 0.5152 | **0.4764** | **0.000** | all 0.00 |
| 4 | `baseline` | 2 | 92 | 32 | 0 | 0.5898 | **0.5847** | **0.019** | 0 .19 0 0 0 0 0 0 0 0 |
| 4 | `tests-none` | 2 | 90 | 307 | 0 | 0.9322 | **0.9181** | **1.000** | all 1.00 |

| Endpoint | `baseline` median (range) | `tests-none` median (range) | Paired Δ by replicate | Paired median | Past ±0.13 |
|---|---|---|---|---:|---|
| Hidden macro (corpus) | 0.839 (0.585–0.967) | 0.911 (0.476–0.974) | −0.063, +0.018, −0.246, +0.333 | −0.022 | 1 below, 1 above |
| Fuzz macro | 0.696 (0.019–1.000) | 0.956 (0.000–1.000) | −0.088, 0.000, −0.392, +0.981 | −0.044 | 1 below, 1 above |

Under the planned in advance rule both endpoints are compatible with no detectable
effect, and the "three of four in one direction" reading does not apply. Three
runs met the completion threshold (hidden ≥ 0.95 with a clean build and audit):
`baseline` replicates 1 and 2 and `tests-none` replicate 2, the first
completions at stages 1–10 in the project. Every run again ended by two
consecutive 45-minute stalls; all eight final snapshots built and passed the
audit.

### 10.3 The batch is bimodal, and the mode is set by hangs, not by tests

The eight finals split cleanly: five score ≥ 0.90 on the corpus and ≥ 0.91 on
the fuzzer, three are broken on valid programs. The three defects:

- `tests-none` replicate 3 emits `ret` before restoring the stack frame, so
  every compiled program segfaults: hidden valid 0/57, fuzz 0.000. Its corpus
  score of 0.476 is entirely invalid-program rejections (44/47).
- `baseline` replicate 4 stores the return value to a stack slot and never
  loads it into `%eax`, so every program exits 0: hidden valid 15/57, fuzz
  0.019 (the 0.19 at stage 2 is programs whose expected result happens to be 0).
- `baseline` replicate 3 names local labels `.0`, `.1`, … which the assembler
  treats as undefined symbols, and mixes operand sizes, so anything needing a
  jump (stage 4 on) fails to assemble: hidden valid 24/57, fuzz 0.392.

None of these is a test-availability effect; two of the three are in the arm
that *had* tests. What the three share is the process signature of §3.3 and
§4: they are the three runs with the fewest assistant turns (131, 32, 72
against 141–342 for the rest) because both of their rounds hung inside a
self-authored test or build command until the 45-minute cap, leaving the
round-0 snapshot, already broken, as the final one. `baseline` replicate 4 made
39 tool calls in 92 minutes. The two `baseline` runs that called
`test_visible` (27 and 17 times) are the two perfect baseline compilers; the
two that never called it are the two broken ones. That is the tool-uptake
pattern of §2 again, at n=4 and still correlational, but it is now the only
structure in the data: test *availability* moved nothing, test *use* and
hang-free execution went together with success.

The corpus gives a compiler that rejects every invalid program and crashes on
every valid one about 0.47, because invalid classes count for half of each
stage; the fuzzer gives it 0. Under the revised oracle the two endpoints now
rank the eight finals alike (the same three at the bottom, the same five at the
top), which is what the §9 disagreement predicted once the `#ifdef` noise was
removed: the corpus spread of §8.2 was measurement, and this spread is
outcome.

### 10.4 The v3 bridge

The six v3 finals re-scored under the revised oracle (`analysis/v3-bridge.json`;
descriptive only, never pooled with v5):

| v3 final | Corpus, original → preprocessed | Fuzz macro |
|---|---:|---:|
| `baseline` r1 / r2 / r3 | 0.819 → 0.901 / 0.931 → 0.931 / 0.819 → 0.910 | 1.000 / 0.953 / 0.956 |
| `tests-none` r1 / r2 / r3 | 0.846 → 0.936 / 0.749 → 0.809 / 0.684 → 0.746 | 1.000 / 0.680 / 0.228 |

Preprocessing raises every compiler that lacked `#`-line handling by
0.06–0.09 and leaves the v3 paired median at −0.122 (from −0.136); the fuzz
paired median is −0.273. So the v3 batch, re-read with the better oracle,
still leans negative, and v5 does not. Taken together (seven replicate pairs
across two harness revisions, so a reading rather than a test) the paired
deltas on the preprocessed corpus are −0.246, −0.163, −0.122, −0.063, +0.018,
+0.035, +0.333: a weak negative lean with two large positive exceptions, both
of which are a broken `baseline` run rather than a strong `tests-none` one.

### 10.4b The typing experiment under the revised oracle

The six v4 finals re-scored the same way (`analysis/v3-bridge.json` also
carries them):

| Rep | `ts-strict` corpus original → preprocessed / fuzz | `js-untyped` corpus original → preprocessed / fuzz | Δ preprocessed | Δ fuzz |
|---:|---|---|---:|---:|
| 1 | 0.839 → 0.929 / 1.000 | 0.883 → 0.974 / 1.000 | −0.044 | 0.000 |
| 2 | 0.865 → 0.956 / 1.000 | 0.839 → 0.929 / 1.000 | +0.026 | 0.000 |
| 3 | 0.899 → 0.899 / 0.806 | 0.828 → 0.918 / 0.999 | −0.019 | −0.193 |

Condition medians are identical on the preprocessed corpus (0.929 each) and
on the fuzz oracle (1.000 each); paired medians −0.019 and 0.000. The +0.071
of replicate 3 in §8 was the `#ifdef` quirk in its entirety; with it removed
the typed arm's replicate 3 is the worse compiler, by its argument-list bug.
Five of the six compilers are within 0.05 of each other on the corpus and
perfect on the fuzzer. The §8 verdict stands with less residual doubt: strict
static typing changed nothing measurable, at roughly a third more tokens.

### 10.5 What this changes

- **The v3 claim is retracted to "not replicated."** With the oracle fixed and
  four fresh replicates, withholding the visible tests produced compilers as
  good as the baseline's in three replicates and a broken one in the fourth,
  while the baseline arm produced two broken compilers of its own.
- **The dominant variance is the hang hazard, and it is condition-blind.** A
  round that blocks inside a self-test until the cap costs 45 minutes and
  leaves whatever snapshot preceded it; a run that does this twice ends with
  its round-0 compiler. That happened to three of eight runs here and to one
  of six in v3. Bounding the agent's shell commands in the fixed environment
  layer (a per-command timeout the guard extension can enforce; §6.5 asked for
  the timing this would need) is now the harness change most likely to reduce
  noise, ahead of more replicates.
- **The revised oracle behaves.** Corpus and fuzz agree on the ranking, the
  fuzz macro separates broken from working compilers unambiguously, and the
  preprocessing fix removed a systematic ten-test penalty. Three compilers
  reached the completion threshold at stages 1–10 for the first time.

### 10.6 Limitations

- Four replicates per arm resolve about 0.13 on a bimodal outcome; the
  observed medians are within noise, and the exceptions are single broken runs.
- The stall-dominated regime means "2 hours" is really "until the second
  hang"; effective budgets varied from 32 to 342 assistant turns.
- Tool-use and hang-free execution are correlated with success but are
  behaviors of the run, not manipulated factors.
- One model, one task, one language.

## 11. Beyond the tests: tokens, time, and code shape (exploratory)

`analysis/dimensions.py` puts every main run of v2–v5 (35 runs) on one table:
generation tokens, active and idle minutes, turns and tool calls, compiler
source size and shape (files, functions, function length, branch density,
comment ratio, `unwrap`/`panic` sites), self-written tests, build time, and
per-test compile time, next to both oracles. Full tables:
[`dimensions.md`](dimensions.md); raw rows: `dimensions.json`/`.csv`. Nothing
here was planned in advance; the code-shape metrics are regex approximations.

- **Almost all generation is thinking.** Between 96.2% and 99.6% of generated
  characters (median 98.1%) are reasoning; visible text and tool calls are the
  remaining 2–4%. "Output tokens" measures deliberation, not code.
- **The process variables that track correctness are the hang lottery.**
  Pooled over 35 runs, output tokens, active minutes, turns, and tool calls all
  correlate about +0.55 with both oracles and idle minutes −0.58; within v5
  the magnitudes reach 0.8–0.9. Restricted to the 17 runs that never hung, the
  same correlations fall to 0.04–0.24. Those 17 runs have a fuzz macro of at
  least 0.953 (median 1.000); the 18 that hung include all seven compilers
  below 0.9. Once a run keeps working it reaches the ceiling, and no amount of
  extra tokens, time, or code distinguishes the survivors.
- **Code shape does not predict fuzz correctness either.** Among hang-free
  runs, source LOC (median 2,406 for Rust), function count, function length,
  branch density, and comment ratio are all within ±0.3 of zero against the
  fuzz macro. Several correlate with the *corpus* score (LOC +0.50, comment
  ratio +0.60, `unwrap`/`expect` calls +0.61, build seconds +0.62): the corpus
  rewards invalid-program rejection, which costs error-handling code; the fuzz
  oracle rewards only translation of valid programs. Which oracle one reads
  changes what "better code" appears to mean.
- **The null contrasts had a resource side.** Paired by replicate, the v2
  specification conditions cost +76k to +142k output tokens (+50–90%) and
  14–43 more active minutes for the same fuzz macro; `ts-strict` cost +19k
  tokens and +619 LOC (+54%) over `js-untyped` for the same fuzz macro;
  `tests-none` used 35–45% fewer output tokens than baseline in both v3 and v5
  with 117–124 fewer turns, and in v3 wrote +432 LOC of its own tests. Cost
  for equal correctness is a finding the primary endpoints do not show.
- **Self-testing is the norm and its size varies 1000-fold.** 22 of 35 runs
  left C test programs in the workspace (median 61 among those; one wrote
  999); test-script size ranges from 0 to 29,867 LOC. Among hang-free runs it
  correlates +0.35 with the fuzz macro, the only code-side dimension that
  keeps a positive sign after the hang confound is removed.
- **Compilers differ by language, not by condition, in speed.** Median compile
  time per hidden test is 7.2 ms for every Rust compiler and 18–20 ms for the
  Node-hosted ones; final builds take under a second. Within a language the
  spread is negligible.

These dimensions are cheap to carry as planned in advance secondary endpoints in
the next batch (tokens, active minutes, turns, source LOC and function count,
self-test LOC, cut-off count), where the per-command timeout removes the
confound that dominates them here.

## 12. v6: test availability with the hang hazard removed

### 12.1 What changed from v5

Two harness changes, both applied before any v6 run and planned in advance in
`docs/EXPERIMENT_PLAN_v6.md` (manifest `picc-tests-v3`, conditions
byte-identical to v3 and v5):

- **Pi 0.84.1 → 0.85.1** (image 0.3), verified by a pilot to change nothing
  the harness parses.
- **A default timeout on the agent's bash tool** (image 0.4): the community
  package `@cad0p/pi-bash-timeout@0.1.0`, pinned in the image and loaded from
  the frozen settings, re-registers Pi's `bash` tool so a command without an
  agent-set timeout is killed after 120 s. Pi ships no default and its
  maintainer declined one (earendil-works/pi#2987). The choice followed the
  measurement in §11: across the 20 v3–v5 main runs, 2670 completed bash calls
  had p99 = 5.1 s, while 18 calls that never returned cost a median 34
  minutes each, 8.9 of 40 budget hours.

Same budget (two 45-minute rounds), model, prompts, partitions, adapter,
oracles, and fuzz parameters as v5; eight runs in the frozen block order.

### 12.2 The harness check

The pre-declared expectation was that no run would lose time to a hang and
that the v5 bimodality would collapse. Both held:

| | v5 | v6 |
|---|---|---|
| runs idling ≥ 5 min | 5 of 8 (30–46 min each) | 0 of 8 (max 2.4 min) |
| commands cut by the default timeout | — | 3 (in 3 runs) |
| fuzz macro below 0.9 | 3 of 8 | 1 of 8 |
| corpus range | 0.476–0.974 | 0.897–0.975 |
| active minutes, median | 57–68 by arm | 88.5–88.8 by arm |

All three cut-offs were the agent's own test loops running a program its
compiler had miscompiled into an infinite loop; each run continued and
finished at the ceiling or near it. Every round still ends at the 45-minute
cap (Amendment 1 corrected the check from "stalls", which count that, to
idle time). Assistant turns per run now range 187–395, against 32–342 in v5.

### 12.3 Results

Primary endpoints per Amendment 2 (below); the frozen-protocol values are
in `analysis/v6-results.md` and `runs/study-results/picc-tests-v3/`.

| Run | Corpus | Fuzz | Active / idle min | Cut-offs | Output tokens | Turns | Source LOC | Self-tests |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| baseline r1 | 0.932 | 1.000 | 89.6 / 0.4 | 0 | 260,210 | 308 | 1,883 | 181 |
| tests-none r1 | 0.923 | 1.000 | 89.8 / 0.3 | 0 | 299,569 | 244 | 2,575 | 92 |
| baseline r2 | 0.950 | 1.000 | 88.8 / 1.3 | 0 | 295,812 | 187 | 2,080 | 1 |
| tests-none r2 | 0.924 | 1.000 | 87.9 / 2.2 | 0 | 287,118 | 297 | 2,716 | 169 |
| baseline r3 | 0.975 | 1.000 | 88.8 / 1.3 | 1 | 286,084 | 235 | 2,788 | 194 |
| tests-none r3 | 0.911 | 1.000 | 88.6 / 1.5 | 0 | 289,850 | 395 | 1,821 | 142 |
| baseline r4 | 0.904 | 1.000 | 87.7 / 2.4 | 1 | 243,185 | 193 | 2,301 | 0 |
| tests-none r4 | 0.897 | 0.756 | 88.4 / 1.9 | 1 | 268,609 | 279 | 2,777 | 50 |

Paired `tests-none` − `baseline`:

| Endpoint | r1 | r2 | r3 | r4 | Paired median | Beyond ±0.13 |
|---|---:|---:|---:|---:|---:|---|
| Corpus (hidden macro) | −0.008 | −0.026 | −0.064 | −0.007 | **−0.017** | 0 of 4 |
| Fuzz macro | 0.000 | 0.000 | 0.000 | −0.244 | **0.000** | 1 of 4 below |

Per arm: corpus median 0.941 (baseline, sd 0.030) vs 0.917 (`tests-none`, sd
0.012); fuzz 1.000 in all four baseline runs and in three of four
`tests-none` runs. Two baseline runs reached the planned in advance completion
threshold (0.95 with a clean build and audit); no `tests-none` run did (best
0.924). Under the interpretation rule this is no detectable effect on either
endpoint at n=4, now with the variance that v3 and v5 lacked: every paired
corpus difference is negative and every one is inside the noise band.

The one imperfect compiler, `tests-none` r4, is the §9 pattern again: the
corpus rates it 0.897 (93 of 104), the fuzzer 0.756, with 86 assembly
failures and 158 wrong results concentrated at stage 3 and stages 9–10.

### 12.4 A second audit incident, and the re-score

`tests-none` r3's final snapshot scored 0 on both oracles under the frozen
protocol: the agent had written a differential fuzzer under `tests/` that
assembles, links, and runs its compiler's output with `std::process::Command`,
and the study evaluator's blocking audit scanned every `.rs` file in the
workspace for the Rust adapter, although `cargo build` never compiles
`tests/`. `src/` had no finding; the same run's round-0 snapshot built and
scored 0.694. This is the §8.5 defect, fixed for the Node adapters after v4
and left in place for Rust; the rule the agent was given binds "the
submitted compiler", which the fuzzer obeyed, and two protocol documents
still described the workspace-wide scan as intended. Amendment 2, logged
after the run terminated and before its corrected score was known, fixed
the handling: every final snapshot re-scored by the evaluator with the Rust
audit scoped to `src/` plus its `#[path]`/`include!` closure, same image and
parameters, applied to all eight runs. Seven of eight reproduce their frozen
values exactly; r3 becomes 0.911 / 1.000. The evaluator fix, its tests, and
the corrected documents are committed after the batch; raw re-score
outputs are in `analysis/v6-rescore/`.

Had the frozen values stood, the fuzz endpoint would have read a paired
median of −0.122 with two of four replicates below −0.13, "unresolved" under
the rule, manufactured by an audit finding on a test helper. The measurement
layer, not the agent, produced the only large difference in the batch.

### 12.5 What withholding the tests costs

The paired resource and code endpoints (secondary, descriptive):

| Endpoint | baseline median | tests-none median | Paired deltas (r1–r4) | Median delta |
|---|---:|---:|---|---:|
| output tokens | 273,147 | 288,484 | +39k, −9k, +4k, +25k | +14.6k |
| active minutes | 88.8 | 88.5 | +0.2, −0.9, −0.2, +0.7 | 0.0 |
| assistant turns | 214 | 288 | −64, +110, +160, +86 | +98 |
| tool calls | 252 | 301 | −75, +94, +127, +83 | +89 |
| `test_visible` calls | 16.5 | 0 | | −16.5 |
| compiler source LOC | 2,191 | 2,646 | +692, +636, −967, +476 | +556 |
| functions | 74 | 70 | +26, −6, −19, −2 | −4 |
| self-written test programs | 91 | 117 | −89, +168, −52, +50 | −1 |
| compile ms per hidden test | 7.31 | 7.37 | | +0.06 |

Agents without the test tool take about a hundred more turns and tool calls
in the same 88 active minutes, replacing the 13–24 `test_visible` calls a
baseline agent makes with their own test scripts, and end with about 500 more
lines of compiler for a slightly lower corpus score. Baseline agents used the
tool in every run this time (v5: not always), which is itself a change: with
no hang eating the second round, the tool gets used. Speed and build time do
not differ. Token cost is within replicate noise either way; the v3
observation that `tests-none` used 45% fewer tokens does not survive the
hang fix.

### 12.6 What this settles

- **The hang hazard was the dominant variance in v3–v5, and it is gone.**
  Eight of eight runs used their full budget; the spread of the corpus score
  fell from 0.50 to 0.08. This is the harness change that made the contrast
  readable, ahead of any additional replicate.
- **Test availability does not detectably change behavioral correctness at
  stages 1–10 under this budget.** Third batch, first clean one: −0.017 on
  the corpus, 0.000 on the fuzzer, no replicate beyond the threshold on the
  corpus. The v3 candidate effect of −0.136 is not reproduced.
- **What it changes is process, not product:** more turns, more self-written
  tests, more code, same time, same correctness.
- **Audits must be scoped to the artifact submitted.** The same measurement
  defect has now appeared in two languages; the v6 fix closes it for Rust
  and Node, and the protocol text finally says so.

### 12.7 Limitations

- Four replicates resolve about 0.13; the consistent small negative corpus
  differences (−0.007 to −0.064) are below that and may be a real small
  effect or noise.
- The corpus score has a ceiling around 0.95–0.97 for these compilers
  (invalid-program rejection tests), which compresses differences near the
  top; the fuzzer is at 1.000 for seven of eight runs and cannot separate
  them at all.
- The 120 s default is the package's constant; an agent-set timeout still
  wins, so a model that asks for a long timeout can still stall a round.
  It did not happen here.
- One model, one task, one language.

## 13. v7: static typing on the clean harness

### 13.1 Design

The v4 contrast re-run under everything that changed since: preprocessed
inputs, the fuzz macro as co-primary, Pi 0.85.1, the bash default timeout,
and one more replicate. `ts-strict` (TypeScript, `tsc --strict
--noEmitOnError` as the build gate) versus `js-untyped` (plain JavaScript,
`node --check`, `tsc` withheld by the guard), same Node.js 24 runtime, same
prompts apart from the adapter's typing notes, 4 replicates in the frozen
block order (`docs/EXPERIMENT_PLAN_v7.md`, manifest `picc-types-v2`,
conditions byte-identical to v4). Eight runs, 2026-09-11 21:33 to
2026-09-12 09:28 UTC, no amendments.

### 13.2 The harness check and treatment fidelity

No run idled five minutes or more (maximum 1.6); no bash call went
unanswered; five commands were cut by the default timeout, all in
`js-untyped` runs, all recovered. `ts-strict` r4 is the first run in any
batch to finish by the perfect-visible rule (227 of 227, held through the
review round) at 77 minutes rather than at the budget.

The treatment was delivered: every typed run invoked `tsc` 21–27 times,
declared 11–31 interfaces, annotated 94–100% of parameters, and used no
`any` and no suppression; no untyped run wrote a JSDoc type, enabled
`@ts-check`, or attempted `tsc` (`analysis/typing-metrics-v7.md`).

### 13.3 Results

| Run | Corpus | Last buildable | Fuzz | Active / idle min | Cut-offs | Output tokens | Turns | `tsc` calls | Source LOC | Self-tests |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| ts-strict r1 | 0.967 | 0.967 | 1.000 | 88.6 / 1.6 | 0 | 304,636 | 234 | 27 | 1,877 | 208 |
| js-untyped r1 | 0.958 | 0.958 | 1.000 | 88.9 / 1.3 | 1 | 282,030 | 218 | 0 | 1,591 | 1 |
| ts-strict r2 | 0.000 | 0.917 | 0.000 | 89.0 / 1.1 | 0 | 299,860 | 217 | 22 | 2,081 | 48 |
| js-untyped r2 | 0.954 | 0.954 | 0.993 | 89.5 / 0.7 | 3 | 262,092 | 233 | 0 | 1,134 | 37 |
| ts-strict r3 | 0.965 | 0.965 | 1.000 | 89.9 / 0.3 | 0 | 265,603 | 181 | 21 | 1,824 | 133 |
| js-untyped r3 | 0.500 | 0.845 | 0.000 | 89.3 / 0.8 | 1 | 269,602 | 230 | 0 | 1,208 | 0 |
| ts-strict r4 | 0.967 | 0.967 | 1.000 | 77.0 / 0.4 | 0 | 255,517 | 225 | 27 | 1,891 | 122 |
| js-untyped r4 | 0.968 | 0.968 | 0.999 | 89.2 / 1.0 | 0 | 297,690 | 272 | 0 | 1,469 | 17 |

"Last buildable" is the corpus score of the last snapshot that built
(`analysis/typing_metrics.py`), a pre-declared descriptive column.

Paired `ts-strict` − `js-untyped`:

| Endpoint | r1 | r2 | r3 | r4 | Paired median | Beyond ±0.13 |
|---|---:|---:|---:|---:|---:|---|
| Corpus (hidden macro) | +0.009 | −0.954 | +0.465 | −0.001 | **+0.004** | 1 below, 1 above |
| Fuzz macro | 0.000 | −0.993 | +1.000 | +0.001 | **+0.001** | 1 below, 1 above |

No detectable effect on either endpoint, and the conclusion does not depend
on the two outliers: the six runs whose final snapshot builds and runs sit
between 0.954 and 0.968 on the corpus and between 0.993 and 1.000 on the
fuzzer, with the typed arm at 0.965–0.967 and the untyped arm at
0.954–0.968. Three of four runs in each arm reached the completion
threshold. The v4 finding (§8, §10.4b: +0.026 on the original corpus,
0.000 under the revised oracles, n=3) is reproduced with tighter data. The
v4 typed compilers' stage-9 defect (rejecting two-argument calls) did not
recur: all four typed compilers are perfect on the fuzzer.

### 13.4 The cap now falls inside refactors

With hangs gone, the largest differences in the batch come from a new
place: the 45-minute round cap landing in the middle of a rewrite. It
happened once per arm. `ts-strict` r2 was rewriting `semantics.ts` when the
cap hit; `tsc --strict` rejects the final snapshot on one arity error, so it
scores 0 on both oracles although its previous snapshot scored 0.917.
`js-untyped` r3 was applying an "all-or-nothing" refactor of `picc.js` that
left a reference to an undefined variable; `node --check` accepts the file,
every valid program is rejected at runtime, and the corpus scores it 0.500
by crediting the rejection of every invalid program (the §9 floor) while
the fuzzer scores 0. The event is condition-blind in occurrence and
arm-asymmetric in how the two build gates score it; in this batch the two
cancel. Both were pre-declared outcomes (the type-gate loss is a listed
secondary endpoint), and the primary endpoint stands as scored. Two of
eight finals is a hazard of the same order as the hangs were (five of eight
in v5), and the obvious remedies are endpoint-level, not harness-level: a
planned in advance co-primary "last buildable snapshot", or a graceful wrap-up
signal before the cap, either of which must be declared before the next
batch rather than applied to this one.

### 13.5 What typing costs

Paired resource and code endpoints (`ts-strict` − `js-untyped`, medians of
per-replicate deltas):

| Endpoint | js-untyped median | ts-strict median | Median delta |
|---|---:|---:|---:|
| output tokens | 275,816 | 282,732 | +9,304 (+23k, +38k, −4k, −42k) |
| active minutes | 89.3 | 88.8 | −0.4 |
| assistant turns | 232 | 221 | −32 |
| tool calls | 240 | 232 | −31 |
| `tsc` invocations | 0 | 24.5 | +24.5 |
| compiler source LOC | 1,339 | 1,884 | +519 (+39%) |
| functions | 163 | 226 | +58 |
| self-written test programs | 9 | 128 | +119 |
| self-test LOC | 129 | 959 | +958 |
| final build seconds | 0.01 | 0.37 | +0.36 |
| compile ms per hidden test | 19.2 | 19.5 | +0.1 |
| commands cut by the timeout | 1 | 0 | −1 (all five in the untyped arm) |

The typed arm writes about 40% more compiler source and, unexpectedly,
an order of magnitude more self-tests (median 128 programs vs 9), in
slightly fewer turns and the same time, for the same correctness; the v4
observation of +54% lines and +9% tokens holds on lines and is within
replicate noise on tokens. All five timeout cut-offs happened to untyped
agents running their own test loops; none to typed agents. At n=4 that is a
lead, not a finding.

### 13.6 What this settles

- **Static typing does not detectably change behavioral correctness on this
  task**, in a second batch and now without the hang and preprocessing
  confounds: +0.004 corpus, +0.001 fuzz, six clean finals within 0.014 of
  each other across the two arms.
- **It changes what gets written:** more source, many more self-tests, a
  type-checker invoked two dozen times per run, fewer turns.
- **The harness is now limited by its snapshot rule, not by hangs.** The cap
  cut a refactor in two of eight runs; the next experiment plan should
  carry a last-buildable co-primary or a wrap-up signal.

### 13.7 Limitations

- Four replicates; two finals are cap artifacts, so the effective n for the
  final-snapshot endpoint is three pairs plus two discordant ones.
- Function and LOC counts are regex approximations and the two languages'
  function syntax is counted alike.
- The corpus ceiling (invalid-program tests) compresses differences near
  0.96; the fuzzer is at 1.000 for six of eight runs.
- One model, one task, two languages on one runtime.

## 14. v8: pushed test feedback, and the last-buildable snapshot rule

### 14.1 Design

The last open question on the test factor: does feedback change anything
when the agent cannot decline it? `tests-pushed` is `baseline` (on-demand
`test_visible`, failure-level feedback) plus a harness-pushed report: at the
end of any turn that continues, once ten minutes have elapsed since the round
started or the last report, the tools extension runs the full visible
evaluation and queues the same failure-level report the tool returns as a
user message delivered before the next model call. The agent's guidance
carries one sentence announcing it. Four replicates per arm in the frozen
block order, image 0.4, same budget as v6/v7
(`docs/EXPERIMENT_PLAN_v8.md`, manifest `picc-tests-v4`; baseline's
resolved condition hash is unchanged since v3).

The batch also introduced the snapshot rule §13.4 asked for. The primary
endpoints are both oracles on the **last buildable snapshot** (the last
frozen snapshot whose hidden evaluation built and passed the audit); the
harness scores that snapshot with the fuzz oracle as a second ledger row
whenever the final one did not build, and the final-snapshot values are
reported alongside for comparability.

### 14.2 The harness check and treatment fidelity

No run idled five minutes or more (maximum 0.7); the one "unanswered" bash
call is the call in flight when baseline r1's cap fell (0.2 idle minutes);
two commands were cut by the default timeout and recovered. Every
`tests-pushed` run received exactly eight reports, at 10–13-minute
spacing, carrying the visible score at that moment (for r4: 0, 0.88, 0.91,
0.93, 0.93, 0.95, 0.98, 0.98). The pushed agents still called the tool
themselves, less often (median 10.5 calls vs 16).

### 14.3 Results

| Run | Corpus (last buildable) | Fuzz (last buildable) | Corpus (final) | Fuzz (final) | Active / idle | Cut-offs | Output tokens | Turns | `test_visible` calls | Pushed | Source LOC | Self-tests |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| baseline r1 | 0.974 | 1.000 | 0.974 | 1.000 | 89.9 / 0.2 | 0 | 278,641 | 260 | 15 | 0 | 2,573 | 0 |
| tests-pushed r1 | 0.940 | 0.996 | 0.940 | 0.996 | 89.3 / 0.7 | 0 | 282,709 | 283 | 8 | 8 | 2,240 | 0 |
| baseline r2 | 0.961 | 1.000 | 0.961 | 1.000 | 89.5 / 0.6 | 0 | 292,619 | 267 | 11 | 0 | 2,657 | 0 |
| tests-pushed r2 | 0.944 | 1.000 | 0.944 | 1.000 | 89.5 / 0.6 | 1 | 267,541 | 298 | 13 | 8 | 2,616 | 179 |
| baseline r3 | 0.939 | 1.000 | 0.939 | 1.000 | 90.0 / 0.1 | 0 | 295,945 | 273 | 23 | 0 | 2,165 | 0 |
| tests-pushed r3 | 0.951 | 1.000 | 0.951 | 1.000 | 89.5 / 0.6 | 0 | 295,139 | 301 | 13 | 8 | 2,454 | 173 |
| baseline r4 | 0.950 | 1.000 | 0.950 | 1.000 | 89.8 / 0.3 | 0 | 301,838 | 297 | 17 | 0 | 2,282 | 227 |
| tests-pushed r4 | 0.894 | 0.932 | 0.000 | 0.000 | 89.4 / 0.7 | 1 | 276,086 | 195 | 5 | 8 | 2,596 | 41 |

Paired `tests-pushed` − `baseline`:

| Endpoint | r1 | r2 | r3 | r4 | Paired median | Beyond ±0.13 |
|---|---:|---:|---:|---:|---:|---|
| Corpus, last buildable (primary) | −0.033 | −0.017 | +0.012 | −0.056 | **−0.025** | 0 of 4 |
| Fuzz, last buildable (primary) | −0.004 | 0.000 | 0.000 | −0.068 | **−0.002** | 0 of 4 |
| Corpus, final snapshot | −0.033 | −0.017 | +0.012 | −0.950 | −0.025 | 1 below |
| Fuzz, final snapshot | −0.004 | 0.000 | 0.000 | −1.000 | −0.002 | 1 below |

No detectable effect on either primary endpoint. Baseline medians 0.956
(corpus, sd 0.015) and 1.000 (fuzz); pushed 0.942 (sd 0.026) and 0.998.
Three of four corpus differences are small and negative, one small and
positive; the fuzzer is at or within 0.07 of the ceiling everywhere. This is
the fourth batch on the test factor and the fourth null: none, on demand,
and pushed feedback produce the same compilers.

### 14.4 The snapshot rule did its job

`tests-pushed` r4 was mid-edit of `parser.rs` when the cap fell (a struct
field added on one side of a refactor and not the other), so its final
snapshot does not build. Under the v6/v7 rule the replicate reads −0.950 on
the corpus and −1.000 on the fuzzer, and the batch's fuzz endpoint would
have shown one replicate beyond the threshold. Under the planned in advance rule
the run scores its round-0 snapshot, 0.894 / 0.932, and the contrast reads
as the other three replicates do. Its own pushed reports show what the cap
discarded: a compiler at 0.98 on the visible tests two minutes before the
snapshot. That is the remaining limitation of round-end snapshots; the
pushed condition's report trail is a finer trajectory the harness could
snapshot on in a later batch.

### 14.5 What pushing changes

Paired resource and code endpoints (`tests-pushed` − `baseline`, medians of
per-replicate deltas):

| Endpoint | baseline median | tests-pushed median | Median delta |
|---|---:|---:|---:|
| pushed reports | 0 | 8 | +8 |
| `test_visible` calls | 16 | 10.5 | −8.5 |
| assistant turns | 270 | 291 | +26 |
| tool calls | 286 | 302 | +26 |
| output tokens | 294,282 | 279,398 | −12,942 |
| active minutes | 89.9 | 89.5 | −0.5 |
| compiler source LOC | 2,428 | 2,471 | +83 |
| functions | 72 | 62 | −12 |
| self-written test programs | 0 | 107 | +87 |
| self-test LOC | 134 | 907 | +742 |
| compile ms per hidden test | 7.4 | 7.4 | 0.0 |

Pushed reports partly displace asking (about half as many on-demand calls)
and, unexpectedly, produce far more self-written test programs: three of
four pushed agents left 41–179 C programs behind, against none in three of
four baseline runs. The report names failing test ids (`chapter_5/valid/…`)
but not their contents, and the agents reconstruct the cases they cannot
see. Turns rise by about 10%, tokens and time do not.

### 14.6 What this settles

- **Test feedback, in any form this harness can deliver, does not change
  behavioral correctness on this task.** Withheld (v3, v5, v6), on demand
  (every batch), or pushed every ten minutes (v8): the compilers are the
  same within noise, with the clean batches' variance.
- **It changes the work again, in a new direction:** pushed agents ask
  less, test more by hand, and take more turns for the same result.
- **The last-buildable rule removes the cap artifact without touching the
  harness.** It caught the one cap-cut final in this batch; with it, no
  run in v8 is a measurement accident.

### 14.7 Limitations

- Four replicates resolve about 0.13; three small negative corpus
  differences at n=4 are not evidence of a small harmful effect.
- The round-end snapshot rule still discards work done after the last
  buildable commit (up to 45 minutes; here about 2 minutes of a 0.98
  compiler).
- The pushed report is failure-level; a detailed or aggregate variant was
  not tested.
- One model, one task, one language.

---

Per-run process detail: [`process-report.md`](process-report.md). Raw metrics:
[`process-metrics.json`](process-metrics.json). Regenerate with
`python3 analysis/process_metrics.py --json analysis/process-metrics.json > analysis/process-report.md`.

---

## 15. The v9 batch: specification detail × test access (2×2)

Planned in advance in `docs/EXPERIMENT_PLAN_v9.md`, with two amendments during
the batch and fixes applied after it. Twelve runs, 2026-09-13 16:35 to 09-14 10:42
UTC, image 0.4, the same model, budget, and oracles as v6–v8. Four cells,
three replicates each, in the frozen block order: `baseline` (full
behavioral specification, tests on demand), `spec-minimal` (a 143-word
specification: interface, output contract, ten one-line stage names,
dependency policy; no behavioral rules, no mention of the book),
`tests-none`, and `spec-minimal-tests-none`. Digest:
`analysis/v9-results.md`; script: `analysis/v9_results.py`; corrected
ledgers for the two amended runs: `analysis/v9-rescore/`.

### 15.1 Every run

Primary endpoints on the last buildable snapshot; the final-snapshot values
differ only for `spec-minimal` r1 (final cut mid-rewrite, 0 / 0).

| Cell | Rep | Corpus | Fuzz | Turns | Source LOC | Own tests | `as`/`ld` calls | Note |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| baseline | 1 | 0.974 | 1.000 | 292 | 2012 | 72 | 18 | |
| baseline | 2 | 0.955 | 0.996 | 291 | 2159 | 1 | — | |
| baseline | 3 | 0.971 | 1.000 | 199 | 2159 | 10 | — | |
| spec-minimal | 1 | 0.784 | 0.727 | 334 | 2964 | 0 | — | round-0 snapshot; final did not build (Amendment 1) |
| spec-minimal | 2 | 0.946 | 1.000 | 302 | 4351 | 0 | — | |
| spec-minimal | 3 | 0.901 | 0.980 | 338 | 3529 | 0 | — | |
| tests-none | 1 | 0.869 | 0.800 | 258 | 2016 | 0 | 0 | own simulator crate; frozen 0 / 0 (Amendment 2) |
| tests-none | 2 | 0.924 | 1.000 | 336 | 2346 | 137 | 54 | |
| tests-none | 3 | 0.682 | 0.200 | 276 | 2100 | 0 | 0 | own interpreter; 800 fuzz programs fail to assemble |
| spec-minimal-tests-none | 1 | 0.915 | 1.000 | 241 | 3545 | 34 | 7 | |
| spec-minimal-tests-none | 2 | 0.879 | 0.996 | 210 | 4268 | 12 | 2 | |
| spec-minimal-tests-none | 3 | 0.825 | 0.996 | 190 | 3918 | 13 | 34 | |

Per cell, corpus median (range): baseline 0.971 (0.955–0.974),
spec-minimal 0.901 (0.784–0.946), tests-none 0.869 (0.682–0.924),
spec-minimal-tests-none 0.879 (0.825–0.915). Fuzz: 1.000, 0.980, 0.800,
0.996.

### 15.2 The planned in advance contrasts

Paired by replicate, median with the per-replicate deltas; threshold 0.13.

| Contrast | Corpus | Fuzz |
|---|---|---|
| specification: `spec-minimal` − `baseline` (tests on demand) | −0.070 (−0.190, −0.010, −0.070); 1 of 3 beyond | −0.020 (−0.273, +0.004, −0.020); 1 of 3 beyond |
| specification: both − `tests-none` (tests withheld) | +0.046 (+0.046, −0.045, +0.142); 1 of 3 beyond | **+0.200** (+0.200, −0.004, +0.796); 2 of 3 above |
| tests: `tests-none` − `baseline` (full specification) | −0.104 (−0.104, −0.032, −0.289); 1 of 3 beyond | **−0.200** (−0.200, +0.004, −0.800); 2 of 3 below |
| tests: both − `spec-minimal` (minimal specification) | −0.067 (+0.131, −0.067, −0.077); 1 of 3 beyond | +0.016 (+0.273, −0.004, +0.016); 1 of 3 beyond |
| both − `baseline` | −0.076 (−0.059, −0.076, −0.146); 1 of 3 beyond | 0.000 (0, 0, −0.004); 0 of 3 |
| interaction (both − `tests-none`) − (`spec-minimal` − `baseline`) | +0.212 (+0.236, −0.035, +0.212) | +0.473 (+0.473, −0.008, +0.816) |

**Specification.** On the corpus, both simple effects of the minimal
specification are inside the band, negative with tests on demand (−0.070)
and positive without tests (+0.046). On the fuzz oracle the minimal
specification costs nothing with tests (−0.020, one replicate beyond, the
cap-cut r1) and is *ahead* by +0.200 without tests, two of three above the
threshold, because the cell it is compared with (`tests-none` under the
full specification) contains the two worst compilers of the batch. So the
first pre-declared reading applies to the specification factor: the
behavioral specification is redundant with what the model brings, and the
agent with the 143-word version builds a compiler that agrees with GCC on
random programs as often as the agent with the 114-line one. What the
minimal specification does lose is the rejection conventions of the test
suite (§15.3).

**Tests.** Under the full specification, withholding tests reads −0.104 on
the corpus (inside the band) and **−0.200 on the fuzz oracle, two of three
replicates below the threshold**: by the planned in advance fuzz rule an
unresolved verdict, and by the corpus rule a candidate effect warranting
replication. This is the first tests contrast in five batches (v3, v5, v6,
v8, v9) with a mechanism rather than a lottery behind it (§15.4). Under the
minimal specification the same contrast is null (−0.067 / +0.016).

**Interaction.** Positive on both oracles in two of three replicates: the
specification effect is more favorable, and the tests effect less
favorable, under the full specification than under the minimal one. Both
are the same two runs.

### 15.3 What the minimal specification costs: rejection conventions

The minimal-specification cells lose their corpus points on invalid
programs the compiler accepts: 6, 6, 8 (with tests) and 6, 7, 11 (without)
wrongly accepted per run, against 2, 4, 4 in `baseline` and 3, 4, 4 in
`tests-none`. Which malformed programs must be rejected, and how strictly,
is a convention of this test suite that the full specification states and
the minimal one does not; the fuzz oracle, which only generates valid
programs, does not see it. Valid-program behavior is the same in all four
cells (fuzz within 0.02 for every buildable final except the two simulator
runs).

### 15.4 What withholding tests costs: the self-oracle substitution

Two of the three `tests-none` runs under the full specification never
invoked the system assembler. Both wrote their own model of the machine and
tested the compiler against that:

- r1 built a separate `devtools/` crate (an x86-64 simulator, assembler
  checker, and fuzzer, 1500 lines) after the guard blocked its
  `which gcc cc as ld …` probe and it concluded no assembler existed. Its
  compiler builds and scores 0.869 / 0.800; 200 fuzz programs fail to
  assemble.
- r3 wrote a 1492-line interpreter "that understands exactly the
  instruction subset PiCC emits" under `tests/` and used it for 143 shell
  commands without once calling `as`. Its compiler scores 0.682 / 0.200;
  800 of 1000 fuzz programs fail to assemble from stage 3 on.

The third run (r2) called `as`/`ld` 54 times, wrote 137 C programs, and
scores 0.924 / 1.000, like the v6 `tests-none` runs (42–63 assembler calls
each; one also wrote a simulator, alongside the assembler). No
minimal-specification run substituted a simulator; all six called the
assembler (2–34 times) and all six agree with GCC on at least 99.6% of
random programs. The pilots showed why: the minimal specification says
nothing about the assembly dialect, so the agent goes to the assembler to
find out; the full specification describes GNU-compatible x86-64 System V
output in enough detail that an agent can convince itself it knows the
target without checking. The agent is a reliable oracle for C semantics,
which it knows, and an unreliable one for assembler syntax, which it must
check empirically; when it replaces the empirical check with its own model,
it validates its compiler against its own misunderstanding.

Two measurement defects surfaced on these runs and were handled by
amendment before any corrected value was known:

- **Amendment 1** (`spec-minimal` r1): the final snapshot did not build;
  the round-0 snapshot built at 0.784 with one *advisory* audit finding
  (`std::env::var("PICC_DEBUG")`, a debug switch). All three
  implementations of the last-buildable rule required `audit_ok`, which is
  false for advisory findings too, so the run would have read 0 / 0 by
  artifact. Rule declared: "passed the audit" means no blocking finding,
  as for a final. Corrected: 0.784 / 0.727.
- **Amendment 2** (`tests-none` r1): the dependency audit walked every
  `Cargo.toml` in the workspace and flagged the `devtools/` crate's path
  dependency on the compiler, zeroing both snapshots although the product
  crate's dependency table is empty and the crate is never built. Rule
  declared: the dependency audit applies to the manifests the frozen build
  compiles. Corrected: 0.869 / 0.800 (frozen 0 / 0).

Both fixes, with unit tests for each case and the Node analogue, were applied after the twelfth run, and every v9 run was re-scored with the
corrected evaluator from a scratch copy of its frozen materialization: 9 of
12 reproduce their frozen corpus and fuzz values exactly, the two amended
runs change as declared, and one unaffected run
(`spec-minimal-tests-none` r2) moves from 0.996 to 0.997 because one of
1000 fuzz programs flips between wrong behavior and pass across executions
(a nondeterministic candidate, not the evaluator); its frozen value is kept.
The frozen ledgers are untouched; the corrected ones are in
`analysis/v9-rescore/` and are primary only for the two amended runs. The
study summarizer (`runs/study-results/picc-spectests-v1/`) still reads the
frozen ledgers and therefore shows the pre-amendment zeros for those two
runs. The re-score procedure (scratch copy with the `runs` symlink replaced,
outputs under `analysis/vN-rescore/`) is recorded in `docs/STUDY_PROTOCOL.md`
under "Re-scoring after an amendment".

### 15.5 Secondary endpoints

Per-cell medians, paired deltas against `baseline` in brackets:

| | baseline | spec-minimal | tests-none | spec-minimal-tests-none |
|---|---:|---:|---:|---:|
| output tokens | 290k | 290k [−3k] | 280k [−12k] | 282k [−9k] |
| active minutes | 89.0 | 90.3 [+1.1] | 88.8 [−0.2] | 89.2 [0.0] |
| assistant turns | 291 | 334 [+42] | 276 [+45] | 210 [−51] |
| `test_visible` calls | 18 | 19 [−6] | 0 | 0 |
| source LOC | 2159 | 3529 [+1370] | 2100 [+4] | 3918 [+1759] |
| functions | 61 | 108 [+45] | 67 [+4] | 124 [+61] |
| self-written test programs | 10 | 0 [−10] | 0 [−10] | 13 [+3] |
| self-test LOC | 55 | 0 | 1303 [+1300] | 306 [+303] |

Time and tokens are flat, as in every batch. The minimal specification
adds 60–80% more compiler source and 70–100% more functions in the same
time: the agents implement shifts, pointers, unsigned and long integers,
and other features the stage list never names (the self-written test files
are named `03_types.c`, `06_shift.c`, `s11_ptr.c`). With the minimal
specification *and* the test tool, no run wrote a single test program of
its own; the tool was called 19 times per run and did all the checking.

Fidelity and harness check: every materialization's `TASK.md` is the cell's
specification; the `tests-none` cells made one `test_visible` call in
twelve runs (r1, answered "withheld", no information returned); no session
in the `tests-none` cells names the book, its author, or its chapters,
except one design-pattern reference to "the writing a C compiler blog" in
`spec-minimal-tests-none` r3 (the with-tests cells see `chapter_N` test ids
in the tool's reports). No run had an unanswered shell call; five commands
were cut by the default timeout and all recovered; one run
(`spec-minimal-tests-none` r1) is flagged at 5.7 idle minutes, which is a
14-minute first turn plus the turn in progress when the cap fell, not a
hang; one final snapshot was cut by the cap and scored by the
last-buildable rule.

### 15.6 Reading

The question the batch was built to answer, whether the agent needs the
specification or the tests, has a two-part answer. It does not need the
specification: on this task the language itself is the specification, the
model knows it, and the written document's only measurable contribution is
the test suite's rejection conventions, worth about 0.05 on the corpus and
nothing on the fuzz oracle. It does need *an* oracle for the parts it
cannot derive: when the visible tests are withheld under a specification
that describes the target in detail, two of three agents replaced the
assembler with a model of the assembler and shipped compilers whose output
does not assemble. That is a candidate effect with a mechanism, not a
lottery, and the natural replication is a `tests-none` batch with four or
more replicates that records assembler use as a pre-declared mediator.

The batch also closes the specification factor on this task: no wording of
a C specification can test whether specifications matter for a model that
already has C. The next task has to carry rules the model cannot recall
(altered semantics, or an unseen language), which the v2 and v9 results
together now justify.


## 16. The v10 batch: two new tasks, and Python with and without a strict type gate

Planned in advance in `docs/EXPERIMENT_PLAN_v10.md`, with two amendments
during the batch. Eighteen runs, 2026-09-16 15:11 to 09-18 03:00 UTC, on image 0.5
(image 0.4 plus mypy 2.3.1), the same model, provider, and 2-hour budget as
v6-v9. Two studies, reported separately and never pooled:

- **`picc-sql-minimal-v1`** — PiSQL, an in-memory SQLite-compatible engine
  scored on 30 whole sqllogictest scripts in eight stages
  (`studies/sql/README.md`).
- **`picc-c18-minimal-v1`** — the chapters 1-18 C compiler, 949 upstream
  tests with evaluator-side fixtures (`studies/c18/README.md`).

Both use the minimal protocol of `studies/minimal`: an empty repository, one
short behavioral contract as the initial message, blank `AGENTS.md`/`TASK.md`,
built-in tools only, no tests, scores, or reference exposed. Conditions vary
only the candidate: `rust` (baseline), `python` (plain, type checkers withheld
by the guard), `python-typed` (`mypy --strict` as the build gate). Three
replicates each. Digest: `analysis/v10-results.json`; script:
`analysis/v10_results.py`; corrected ledgers: `analysis/v10-rescore/`.

### 16.1 Every run

Primary is the hidden corpus macro on the last buildable snapshot, re-scored
under the corrected Python audit where Amendment 2 applies.

**SQL engine** (floor: constant-output 0.050, reject-all 0.000)

| Cell | Rep | Primary | Frozen | Rounds | Hours | LOC | End | Note |
|---|---:|---:|---:|---:|---:|---:|---|---|
| rust | 1 | 0.818 | 0.818 | 2 | 1.5 | 3840 | stall rule | |
| rust | 2 | 0.000 | 0.000 | 14 | 2.0 | 3463 | wall budget | 48 compile errors |
| rust | 3 | 0.000 | 0.000 | 2 | 1.5 | 8111 | stall rule | 6 compile errors |
| python | 1 | 0.754 | 0.754 | 2 | 1.5 | 2406 | stall rule | |
| python | 2 | 0.756 | 0.015 | 2 | 1.5 | 3092 | stall rule | re-scored (Amendment 2) |
| python | 3 | 0.795 | 0.795 | 3 | 1.8 | 2430 | stall rule | re-scored final |
| python-typed | 1 | 0.000 | 0.000 | 10 | 2.0 | 0 | wall budget | no code (overflow mode) |
| python-typed | 2 | 0.098 | 0.098 | 14 | 2.0 | 2713 | wall budget | |
| python-typed | 3 | 0.000 | 0.000 | 30 | 1.9 | 2689 | round cap | 71 mypy errors |

**Chapters 1-18 compiler** (floor: constant-output 0.213, reject-all 0.500)

| Cell | Rep | Primary | Rounds | Hours | LOC | End | Note |
|---|---:|---:|---:|---:|---:|---|---|
| rust | 1 | 0.000 | 2 | 1.5 | 4134 | stall rule | no `src/main.rs` |
| rust | 2 | 0.000 | 2 | 1.5 | 5484 | stall rule | no `src/main.rs` |
| rust | 3 | 0.000 | 2 | 1.5 | 3934 | stall rule | no `src/main.rs` |
| python | 1 | 0.426 | 3 | 1.8 | 6640 | stall rule | |
| python | 2 | 0.000 | 3 | 1.8 | 2645 | stall rule | no entry module |
| python | 3 | 0.501 | 2 | 2.5 | 4848 | stall rule | visible eval hit its cap |
| python-typed | 1 | 0.000 | 9 | 2.0 | 752 | wall budget | 13 mypy errors |
| python-typed | 2 | 0.000 | 4 | 2.0 | 2684 | stall rule | 27 mypy errors |
| python-typed | 3 | — | 3 | 2.0 | — | stall rule | excluded: hidden eval hit its 7200 s cap |

### 16.2 Both tasks have headroom; the chapters 1-10 task does not

This is the batch's most useful result. Chapters 1-10 has sat at 0.93-0.97
for the baseline since v6, so it cannot resolve an improvement. The best runs
here reach **0.795 on SQL** and **0.501 on chapters 1-18**, both far above
their floors and far below saturation. The harder task lever that v8 called
for now exists, in two independent flavours.

Plain Python on SQL is also the first tight cell of the campaign on a new
task: 0.754, 0.756, 0.795 across three replicates.

### 16.3 The strict type gate is binding at this difficulty, unlike in v7

The planned in advance criterion for claiming an effect (all replicates agree in
sign, |median| > 0.13) is **met on the SQL task**: `python-typed` minus
`python` is -0.754, -0.659, -0.795, median -0.754. On chapters 1-18 it is not
met (one pair is exactly zero and a third is missing).

The mechanism is the gate itself, not annotation quality. Of the six typed
runs across both tasks, three wrote substantial programs that `mypy --strict`
rejected (13, 27, and 71 errors), one produced no code at all, one passed the
gate and scored 0.098, and one passed the gate but was lost to an evaluation
timeout. The model writes plausible annotated Python and cannot make it
type-clean inside the budget.

This differs from v7, where `ts-strict` cleared an equivalent `tsc --strict`
gate routinely (0.839-0.899) and matched `js-untyped`. The difference between
the batches is task difficulty, so the reading is: **a strict type gate is
free when the task is easy and binding when it is hard**, at a fixed budget.
It is not evidence that annotations reduce correctness. The contrast is also
confounded, as 16.4 explains, and three replicates cannot separate the two.

### 16.4 Four harness interactions dominated the outcome

Ten of the eighteen runs scored zero, and mostly for reasons unrelated to
their condition. In decreasing order of damage:

1. **Context-overflow recovery failure (Amendment 1).** Cap-length thinking
   blocks (`stopReason=length`, 65 536 tokens) fill the 131 072-token context;
   Pi's compaction then fails permanently ("Summarization failed: 400 ...
   exceeds the context") and every later round is a truncated thinking block
   with no tool call. Five runs spent most of their budget this way. It hit
   both Rust and typed Python, so it is not condition-specific.
2. **The stall rule.** `MAX_CONSECUTIVE_ROUND_TIMEOUTS=2` ends a run after two
   consecutive capped rounds. On these tasks a capped round usually means
   *working*, not hung, so twelve runs ended at about 91 minutes with 29
   minutes unspent. All three Rust compiler runs were cut with a complete
   module tree (lexer, parser, AST, semantics) and no `src/main.rs`; the
   agent writes the entry point last.
3. **Workspace-wide Python audit (Amendment 2).** Two plain-Python SQL runs
   were zeroed for their own `subprocess`-based test drivers. The corrected
   audit scopes Python to the entry module's import closure, as Node has done
   since v4. Re-scoring moved `python` r2 from 0.015 to 0.756 and confirmed
   the other two affected runs. Without this correction the SQL typing
   contrast would have looked like noise rather than an effect.
4. **Evaluation cost on chapters 1-18.** The 668-test visible partition took
   longer than its 3600 s cap on two runs, and one hidden evaluation exceeded
   7200 s, which excluded `python-typed` r3 from the study. Evaluation time is
   charged to the run's wall budget, so a slow candidate is penalised twice.

### 16.5 What to change before the next batch

- Treat a failed context-overflow recovery as terminal, or lower the thinking
  level, or cut the per-turn output cap. Any of the three ends the wasted
  rounds; the first is the smallest change.
- Make the stall rule condition on evidence of work (tool calls or workspace
  changes in the round) rather than on the round being capped.
- Keep the scoped Python audit (already in the repository evaluator).
- Bound evaluation cost on chapters 1-18: a per-round subset, a shorter
  per-test compile timeout, or evaluation outside the wall budget.

Each needs a new manifest id and a fresh experiment plan. Until then, the
typing result of 16.3 should be treated as a hypothesis with a plausible
mechanism, not a settled effect.

## 17. The v11 and v12 attempts: why they were stopped, and what they showed

Neither batch completed. Both were stopped deliberately, and the reason is
worth more than the runs would have been.

### 17.1 What was tried

v11 (`docs/EXPERIMENT_PLAN_v11.md`) repeated the v10 design on a harness with
the four section-16.5 fixes applied. It was stopped after four SQL runs when
two died with the new `context_overflow` termination.

v12 (`docs/EXPERIMENT_PLAN_v12.md`) repeated it again after correcting a
configuration defect: `LOCAL_MAX_OUTPUT` had been 65536 against a 131072
window, exactly half, while Pi's compaction reserve was 16384, so one turn
could overshoot the compaction trigger. The cap went to 32768, the reserve to
40960, and `scripts/common.py:context_budget_problems` now refuses to start a
run whose output cap exceeds its compaction reserve. v12 was stopped after
five SQL runs, four of them zero, when the same deaths reappeared.

### 17.2 The real predictor: turn shape, not token volume

`analysis/turn_shape.py` profiles every v10-v12 run. Compaction failure does
not track how much the model generated; the survivors generated more. It
tracks how often the model *acted*:

| Tool calls per assistant turn | Runs | Compaction failed |
|---|---:|---:|
| 0.35 to 0.83 | 10 | 9 |
| 0.99 to 1.08 | 17 | 0 |

A run that acts on essentially every turn is fine. A run that thinks without
acting on a quarter of its turns accumulates a transcript that is dropped from
the prompt but must still be summarized: in `v12-sql-python-typed-r1` the
visible prompt was 127052 tokens while the summarization request was 278625,
more than twice the window. Once that request exceeds the context the provider
returns 400 and the session cannot recover.

Halving the output cap did not remove this. It doubled the number of rounds
before it happened: those runs died at round 2-3 under the old cap and at
round 7-8 under the new one. The cap change was correct and insufficient.

### 17.3 Consequence

No setting available in this harness removes the cause. The levers are the
thinking level, which changes model behaviour and breaks comparison with v3
onward, or incremental summarization inside Pi, which is upstream. Until one
of them moves, a two-hour session on these tasks is a lottery over whether the
model happens to think in acted or unacted turns, and a typing contrast run
across it measures that lottery.

The v10 result of section 16 stands as reported, with the confounds named
there. It has not been reproduced, and on the evidence here it should not be
treated as established.

### 17.4 What the three attempts did measure

Treating "the runs did not finish" as a null result throws away the finding.
Across all 27 main runs of v10-v12, pooled because the endpoint here is
behavioural rather than a score (`analysis/condition-shape.json`):

| Condition | n | Median tool calls per turn | Sessions broken | Best hidden |
|---|---:|---:|---:|---:|
| `rust` | 9 | 1.02 | 2/9 | 0.825 |
| `python` | 10 | 1.00 | 2/10 | 0.795 |
| `python-typed` | 8 | 0.79 | 5/8 | 0.757 |

Two things follow.

**When a run completes, the conditions are comparable.** Best hidden scores
are 0.825, 0.795, and 0.757. There is no sign that annotated Python produces a
worse engine than plain Python or Rust.

**The strict type gate changes how the agent works, and that is what costs
it.** Requiring `mypy --strict` moves the median turn shape from about one
action per turn to 0.79, and sessions break in five of eight runs against two
of nine and two of ten. The agent deliberates more and acts less, and on a
two-hour session that is what exhausts the context.

So the honest statement of the v10 result is not "strict typing scores worse".
It is: **strict typing lowers the completion rate, not the quality of what
gets completed**, and the mechanism is a measurable shift in turn shape. That
also explains why v10 met its effect criterion while v11 and v12 pointed the
other way: the criterion was scoring completions against non-completions.

This is a weaker claim than a score contrast and it rests on 27 runs that were
never designed to test it, so it is a hypothesis with a mechanism and a
predictor, not a settled effect. It is testable cheaply: turn shape is visible
within two rounds, so a batch designed around completion rate rather than
score would need far less compute than the ones that failed.

### 17.5 The thinking level is not the lever (ruled out)

Before concluding, four short probes on the SQL task varied `MODEL_THINKING`
while holding everything else fixed (`runs/probe-{medium,low}-{rust,python-typed}`):

| Level | `python-typed` | `rust` |
|---|---:|---:|
| high (baseline, full runs) | 0.76 | 1.04 |
| medium | 0.67 | 1.14 |
| low | 0.86 | 0.67 |

No consistent direction: low helps the typed arm and ruins Rust, medium does
the reverse, and every probe still produced at least one cap-length turn.
Lowering the thinking level is therefore not a fix for the session breakdown,
and it is not worth spending a batch on. The probes are pilots and excluded
from every summary.

### 17.6 Task difficulty, which was the original point

| Task | Runs | Scoring zero | Best hidden |
|---|---:|---:|---:|
| SQL engine | 18 | 10 | 0.825 |
| Chapters 1-18 compiler | 9 | 7 | 0.501 |

Both sit far below the chapters 1-10 task, which has been saturated at
0.93-0.97 since v6. The two new tasks give the campaign the headroom it asked
for after v8, and that result does not depend on any of the above.

### 17.7 Why the session breakage cannot be fixed from this repository

Three configuration fixes were tried and measured. All three are improvements
and all three are committed; none solves the problem, and the reason is now
precise.

Pi decides *when* to compact from the prompt size, but what it must summarize
is the session history. For a thinking-heavy run these diverge, because
thinking is dropped from the prompt and retained in the history:

| Run | Prompt at first compaction | Accumulated history | Summarization request | Window |
|---|---:|---:|---:|---:|
| `v14-sql-python-r1` | 69,139 | ~448,000 | 322,007 | 131,072 |

Moving the trigger changes the prompt size at which compaction starts and does
nothing about the history it must swallow. In `v14-sql-python-r1` compaction
fired exactly at the intended point and failed immediately, then failed on
every retry.

The three attempts and what each showed:

1. `LOCAL_MAX_OUTPUT` 65536 -> 32768. A single turn could fill half the window.
   Real defect, but deaths moved from round 2-3 to round 7-8 rather than
   stopping.
2. `keepRecentTokens` 20000 -> 49152, so one turn cannot exceed the keep
   budget and force Pi's split-turn path. Verified at 92,730 tokens; the next
   full run still died at 117,537.
3. `reserveTokens` 40960 -> 65536, triggering compaction earlier. Verified
   over 150 minutes with 21 successful compactions on an *active* run; the
   next low-action run died at round 11.

The probes passed because active runs keep history close to prompt (about one
action per turn). The runs that die generate a capped thinking block per round
and almost never act, so history grows roughly 32,768 tokens per round while
the prompt stays near 30,000. After ten such rounds the first compaction is
already impossible.

The fix belongs upstream, in bounding what Pi sends to be summarized. Until
then a long session on these tasks fails whenever the model settles into
thinking without acting, and lowering the output cap only changes how many
rounds that takes.

### 17.8 Retained artifacts

`runs/v11-sql-*` (four runs) and `runs/v12-sql-*` (five runs) are kept as
evidence of the failure and excluded from every summary: their manifests
(`picc-sql-minimal-v2`, `-v3`) are not the manifests of any completed batch.
`analysis/turn-shape.json` holds the profile table.
