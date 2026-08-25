# PiCC: prompt and specification strategy

How prompt and specification strategy affect a coding agent building a C compiler
from an empty repository.

**Headline: no specification or prompt strategy separated from baseline.** Fifteen
runs across five conditions, three replicates each, produced a cohort standard
deviation of 0.039 — and no condition's median differs from baseline by more than
that. The instructive results are elsewhere: the harness defects we found while
looking were each large enough to have manufactured a false answer, and the least
instructed condition performed at least as well as the most instructed one.

- Date: 2026-08-25
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
- **The server is not archived.** Client configuration is frozen; `llama-server`'s
  own behavior during runs is not captured.

---

## 6. What follows

1. **Raise the difficulty.** Stages 1–10 (main profile), or a tighter budget, so
   conditions have headroom to differ in. Ranking is impossible against a ceiling.
2. **Test tool uptake directly.** It is the largest signal observed and the most
   actionable if it holds.
3. **Tell the agent which paths persist**, and record where it scaffolds. Cheap to
   do, removes a confound, and is itself a finding about agent usage.
4. **Capture tool-call durations.** No timing exists on tool events, so "where did
   the time go" is unanswerable and the data is unrecoverable after the fact.
5. **Report audit-pass separately from quality** in all analyses, and treat every
   audit pattern as a hypothesis until a human has read the match.
6. **Reconsider end-state scoring.** A run is scored on its final snapshot, so
   being killed mid-refactor reads as total failure.

---

Per-run process detail: [`process-report.md`](process-report.md). Raw metrics:
[`process-metrics.json`](process-metrics.json). Regenerate with
`python3 analysis/process_metrics.py --json analysis/process-metrics.json > analysis/process-report.md`.
