# PiCC: prompt and specification strategy

How prompt and specification strategy affect a coding agent building a C compiler
from an empty repository.

**Headline: no specification or prompt strategy separated from baseline.** Fifteen
runs across five conditions, three replicates each, produced a cohort standard
deviation of 0.039 — and no condition's median differs from baseline by more than
that. The instructive results are elsewhere: the harness defects we found while
looking were each large enough to have manufactured a false answer, and the least
instructed condition performed at least as well as the most instructed one.

- Date: 2026-08-25 (§§1–6, the v2 cohort); §7 and §8 added 2026-09-07 for the v3 and v4 cohorts at stages 1–10; §9 added 2026-09-09 (every final re-scored with the fuzz oracle)
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

Cohort: n=15, mean 0.9193, **SD 0.0392**, range 0.8634–0.9583. Seven of fifteen
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

Every condition's median sits within one cohort standard deviation of baseline's.
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
last in the cohort (0.8704, 0.8634) before the third reached the ceiling, so the
effect is not reliable — but no replicate of it ever beat the least prescriptive
conditions, across two different versions of the condition and five runs total.

An earlier single run had made `spec-architecture` look like the clear winner.
Replication reversed that reading entirely, and the reversal is the point: at one
run per condition this cohort's own spread would have supported almost any
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

**Tool uptake.** In the earlier cohort, every run that called the provided test
tool scored ≥ 0.863 and no run that ignored it exceeded 0.877, with both
catastrophic failures coming from runs that never touched it. That was the
strongest signal in the data at the time. It is confounded with run quality and
was not tested directly; it remains the most actionable open hypothesis.

**Compaction always evicts the opening request.** Every compacting run dropped
42–139 leading entries at ~127k tokens, always including the opening request. For
`spec-inline`, whose specification exists *only* there, this means the controlling
document was evicted mid-run — and it still produced the joint-highest median in
the cohort. Specification persistence appears to matter less than expected once
the code exists.

**A shared blind spot.** Eight of nine compilers in the earlier cohort failed on
`unexpected character '#'` at line 1. Independently written compilers converged on
the same missing feature.

**Failure profile at the ceiling.** The three highest-scoring runs failed on
exactly the same two hidden tests, both `unexpected_accept` — invalid programs
accepted rather than rejected. The residual gap is validation strictness, not code
generation.

---

## 5. Limitations

- **Three replicates resolve ~0.13.** The differences of interest are ~0.05. This
  cohort can rule out large effects; it cannot establish small ones.
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

Pre-registered (`docs/PRE_REGISTRATION.md`), run 2026-09-02, main profile: 2 h
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
cohort SD 0.084), and `tests-none` used roughly half the tokens of `baseline`.
Provenance correction recorded 2026-09-07: this cohort ran on the re-downloaded
model file (SHA-256 `3f227079…`), not the file its pre-registration quoted.

---

## 8. v4: static typing — TypeScript strict versus plain JavaScript

**Headline: requiring static types with a strict type-checker as the build gate
did not measurably change hidden correctness.** Paired median +0.026 in favour
of the typed arm, below the pre-declared 0.13 threshold; the largest paired
difference (+0.071) is one agent's handling of a lexer corner case, and the
typed arm's best-scoring compiler cannot compile a call with two arguments.

Pre-registered before the first run (`docs/PRE_REGISTRATION_v4.md`, commits
`6ebc1a3`/`3ff1e68`, amended `5a35741`); run 2026-09-06/07 on the same model
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
(mean +0.018). Cohort n=6, mean 0.859, SD 0.028 — the tightest cohort so far.
Every run ended by two consecutive 45-minute stalls at 1.5 h, every final
snapshot built and passed the audit, and no `ts-strict` snapshot was ever lost
to the type gate: all six typed snapshots type-checked. The visible–hidden gap
is 0.01–0.05 in both arms.

Under the pre-registered rule the contrast is compatible with no detectable
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
that every run fails had failed, the macro score would be 0.971; the cohort's
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
Under the fuzz oracle the typed arm has the only broken compiler in the cohort
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
and the disagreement is not noise.** All 27 cohort finals (v2, v3, v4) were rebuilt
from their committed snapshots and fuzzed against GCC. The v3 result gets stronger
under the fuzz oracle, the v4 null stays null with its best typed run becoming its
worst, and thirteen v2 compilers that the corpus spreads over 0.877–0.958 are
indistinguishable at the fuzzer's resolution. Full tables:
[`fuzz-rescore.md`](fuzz-rescore.md); regenerate with `analysis/fuzz_rescore.py`.

### 9.1 Method

Each final snapshot is exported from its run workspace, built inside the pinned image
exactly as the evaluator builds it, and run through `analysis/fuzz_differential.py`
on the host, which generates UB-free C programs from the cohort's cumulative feature
subset, compiles them with GCC as the reference, and compares exit status and stdout.
Two views: **full scope** (300 programs using every feature of the cohort's task at
once, one seed) and **fuzz macro** (100 programs at each of stages 1..K, seeded per
stage, averaged with equal stage weights like the corpus macro score). A single broken
feature fails every full-scope program; the stage average grades it. Rejecting a valid
program, failing to assemble, crashing, hanging, and wrong results all count as
failures. No score here changes any pre-registered primary endpoint.

### 9.2 What the fuzzer found that the corpus did not

| Final | Corpus hidden | Fuzz macro | Defect (stages affected) |
|---|---:|---:|---|
| `v3-tests-none-r3` | 0.684 | 0.228 | SIGFPE on nested `%`/`/` and wrong results from stage 3; invalid register forms at stages 9–10 |
| `v3-tests-none-r2` | 0.749 | 0.715 | wrong `&&`/`\|\|` results with bitwise operands from stage 4; loops that hang from stage 8 (47 of 100 programs time out); invalid assembly at stage 9; cannot parse an initialized file-scope variable (stage 10: 0.00) |
| `v3-baseline-r2` | **0.931** (cohort best) | 0.953 | segfaults on calls with seven or more arguments (stages 9–10: 0.72, 0.81) |
| `v3-baseline-r3` | 0.819 | 0.956 | wrong results in nested conditionals from stage 6 |
| `v4-ts-strict-r3` | **0.899** (cohort best) | 0.806 | rejects every call with two or more arguments (stages 9–10: 0.04, 0.02) |
| `v2-spec-architecture-r1` | 0.870 | 0.820 | wrong results from stage 2 (unary/binary nesting) |
| `v2-spec-architecture-r2` | 0.863 | 0.968 | wrong results from stage 4 |

Every other final (20 of 27) agrees with GCC on every generated program at every
stage. The corpus's residual spread among those twenty is the `#ifdef` lexer gap
(§8.2), invalid-program rejection, and a few shared parse gaps; none of it is
codegen quality.

### 9.3 Cohort conclusions under both oracles

| Cohort | Pre-registered contrast | Corpus paired median | Fuzz macro paired median | Rank agreement (Spearman ρ, corpus vs fuzz macro) |
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
compilers to the top of two cohorts, and the fuzzer cannot see a compiler that
accepts every invalid program. The scoring change proposed in §6.1 should therefore
add the fuzz macro as a co-primary endpoint alongside the corpus macro rather than
replace it, with the stage-averaged form so that one broken feature does not zero a
compiler, and it should be pre-registered before the next cohort. Two mechanical
follow-ups: the fuzzer now records a hanging program as a `timeout` mismatch instead
of aborting the batch (it lost two stage cells on the first pass), and the
preprocessor-prefixed test files (§8.2) should be handled at the corpus or
specification level so that the corpus measures compilation rather than an
unstated rule.

---

Per-run process detail: [`process-report.md`](process-report.md). Raw metrics:
[`process-metrics.json`](process-metrics.json). Regenerate with
`python3 analysis/process_metrics.py --json analysis/process-metrics.json > analysis/process-report.md`.
