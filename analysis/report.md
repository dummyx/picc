# PiCC prompt/specification trials

Nine comparable runs testing how prompt and specification strategy change the way a coding agent
builds a C compiler from an empty repository.

**Headline:** the result we went looking for did not replicate. The one that did show up is that
*whether the agent used the feedback tool it was given* separated the runs better than which
specification it received.

- Date: 2026-08-24
- Model: local Qwen3.8-27B (UD-Q4_K_XL) via llama.cpp, single RTX 5090
- Profile: pilot — 45-min round cap, 2h wall, stages 1–6
- Config: `LOCAL_MAX_OUTPUT=65536` (all nine runs; earlier runs used 32768 and are not comparable)
- Scoring: hidden-partition macro average — per stage, valid and invalid classes averaged
  separately, then averaged across stages. 59 hidden tests, 124 visible.

## Conditions

Each is one change away from baseline. Task, tooling, budget, model, and evaluator held fixed.

| Condition | What changed |
|---|---|
| `baseline` | Detailed behavioral spec in a persistent `TASK.md`, full workflow prompt |
| `spec-architecture` | Behavioral spec *plus* prescribed lexer/parser/sema/IR/codegen boundaries |
| `spec-brief` | Detailed spec replaced by a short product brief of the same scope |
| `spec-inline` | Same spec, delivered once in the opening request instead of a persistent file |
| `prompt-minimal` | Workflow, progress-memory, sequencing, regression instructions stripped; safety rules kept |

## Results

| Run | Outcome | Hidden | LOC | Turns | `test_visible` calls |
|---|---|---:|---:|---:|---:|
| `spec-architecture` r1 | scored | 0.898 | 2833 | 114 | 10 |
| `spec-brief` r2 | scored | 0.898 | 2872 | 172 | 4 |
| `spec-architecture` r2 | scored | 0.877 | 2829 | 122 | 11 |
| `baseline` r4 | scored | 0.877 | 1687 | 142 | 5 |
| `spec-inline` r1 | scored | 0.863 | 1949 | 81 | 5 |
| `baseline` r2 | scored | 0.819 | 1891 | 95 | 0 |
| `baseline` r3 | scored | 0.771 | 2233 | 57 | 0 |
| `prompt-minimal` r1 | **audit fail** | 0.000 | 2482 | 135 | 0 |
| `spec-architecture` r3 | **crashes** | 0.000 | 4325 | 57 | 0 |

By condition:

| Condition | n | Scores | Median |
|---|---:|---|---:|
| `baseline` | 3 | 0.819, 0.771, 0.877 | 0.819 |
| `spec-architecture` | 3 | 0.898, 0.877, 0.000 | 0.877 |
| `spec-brief` | 1 | 0.898 | 0.898 |
| `spec-inline` | 1 | 0.863 | 0.863 |
| `prompt-minimal` | 1 | 0.000 (0.877 with audit gate removed) | — |

## Findings

### 1. Tool uptake separated the runs better than the specification did

Every run that called the provided test tool at least once scored **0.863 or above**. No run that
ignored it exceeded 0.877, and both catastrophic failures came from runs that never touched it.
Sorting the table by score nearly sorts it by tool use — across conditions, not within them.

This is correlational at n=9 and the causation may run backwards: a run going well may simply have
the composure to reach for the tool. But it is a sharper split than anything the specification
variants produced, and it points somewhere practical — getting an agent to actually consume the
feedback channel you built may matter more than how carefully you word the spec.

### 2. The architecture advantage did not survive replication

On a single run, prescribing component boundaries looked like a clear win: the agent built exactly
the named modules (`lexer.rs`, `parser.rs`, `sema.rs`, `ir.rs`, `codegen.rs`) and posted the best
score in the project. Two more runs undid that reading. Its working runs land at 0.898 and 0.877 —
and baseline's own best run is 0.877, identical. The apparent effect sits entirely inside baseline's
spread of 0.771–0.877.

The third run failed differently and worse: 4,325 lines, roughly 1,500 more than its siblings,
drifting into language features well outside the stages 1–6 target, producing a compiler that builds
cleanly and then crashes on almost every input. Architectural guidance raised the ceiling in two runs
and blew out the floor in the third.

### 3. Two runs scored zero for entirely unrelated reasons

`prompt-minimal` scored 0.000 because of one line — `std::env::var("SIM_TRACE")`, a debug flag —
which trips the source-audit policy. Its compiler builds fine; re-scored with the audit gate removed
it reaches **0.877**, above baseline's median. Taken at face value the run says "stripping workflow
instructions is catastrophic"; what actually happened is a slightly better-than-average compiler plus
one reflexive habit.

`spec-architecture` r3 also scored 0.000, but that zero is real — the compiler crashes. Identical
numbers, opposite meanings.

The agent has now reached for an environment-variable debug flag in two of eleven runs despite an
explicit prohibition present in every prompt variant. That habit is strong enough that instructing
against it does not reliably suppress it.

### 4. An output-token ceiling had been suppressing every earlier run

The per-request output cap was 32768. This model's thinking blocks sometimes exceed that, and when
they do the turn dies mid-thought carrying only reasoning — no tool call, nothing committed. Whole
rounds evaporated; what earlier notes recorded as the agent "musing without acting" was largely this.

Raising the cap to 65536 took the same baseline condition from 5 turns with 3 truncated to 95 turns
with 1, in identical wall time. Truncation still occurs about once per run, so the ceiling is reduced
rather than eliminated.

### 5. One missing lexer feature accounts for most residual failures

Eight of nine independently written compilers fail on the same thing: `unexpected character '#'` at
line 1, column 1. Remaining failures are otherwise dominated by `unexpected_reject` — valid programs
turned away, i.e. missing language coverage rather than broken code generation.

## What this does not show

- Three conditions have a single run each, and baseline's own replicates span 0.11. Any difference
  smaller than that is invisible here — which includes every gap between the specification variants.
- Run length was not fully controlled: three of nine runs stalled on a test binary their own
  half-built compiler produced and idled until the cap. How much time a run gets is therefore partly
  a function of when it happened to hang.
- The behavioral observations — tool uptake, the audit habit, the shared lexer gap, module structure
  following the spec — are sturdier than the score ordering, because they are near-categorical rather
  than differences of degree.

## What follows

1. **Report audit-pass separately from quality.** One reflexive line currently decides an entire
   run's number and can invert a conclusion.
2. **Test the tool-uptake hypothesis directly** rather than inferring it — largest signal in the
   data, most actionable if it holds.
3. **Add replicates before trusting any specification ranking.** Three runs per condition was the
   minimum needed to overturn the first reading; it is not enough to establish the next one.
4. **Bound the self-test hang** so run length stops depending on when the agent deadlocks on its
   own output.

---

Per-run process detail: [`process-report.md`](process-report.md). Raw metrics:
[`process-metrics.json`](process-metrics.json). Regenerate with
`python3 analysis/process_metrics.py --json analysis/process-metrics.json > analysis/process-report.md`.
