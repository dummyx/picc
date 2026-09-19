# Experiment plan: v14 (supersedes v13)

Same question and rules as v13. Restarted because the session-breakage
failure that v13 was measuring has been fixed.

## The fix, verified before this run

One assistant message could be 32768 tokens while Pi's whole `keepRecentTokens`
budget was 20000, so every compaction took Pi's split-turn path and had to
summarize a span containing those oversized turns. The summarization request
then exceeded the context window (observed 278625 tokens against 131072), the
provider returned 400, and the session was dead for the rest of the run.

`keepRecentTokens` is now 49152, above the 32768 output cap.
`scripts/common.py:context_budget_problems` refuses to start a run that
violates the relation, with the old configuration as a unit-test case.

Verified empirically in `probe-compaction` (rust, 1.5 h, 25-minute rounds)
before this plan was frozen: the conversation reached 84411 then 92730 tokens
and compaction fired five times with no failure, while tool use rose to 38
calls in the final round. The same path killed `v13-sql-rust-r1` at 65 minutes.

## Question, design, endpoints, decision rule

Unchanged from `docs/EXPERIMENT_PLAN_v13.md`, which this supersedes: SQL task,
`rust` / `python` / `python-typed`, five replicates, full 2-hour budget.
Primary endpoints are session survival and turn shape; score is secondary.

Confirmed if `python-typed` breaks in at least twice as many runs as `python`
and its median turn shape is at least 0.15 below. Not confirmed otherwise.

Study `picc-sql-minimal-v4`, seed 20260920, run ids `v14-sql-<condition>-r<n>`.

## What v13 showed before it was stopped

Four runs, retained and excluded. Two results worth keeping:

- Turn shape does **not** predict breakage. `v13-sql-python-typed-r1` ran at
  0.25 tool calls per turn for fourteen rounds without breaking, while
  `v13-sql-rust-r1` broke at 0.68. The earlier correlation across 27 runs was
  riding on conversation growth, not on the ratio.
- The two failures are distinct. Breakage happens to runs that are *working*
  and filling the context. A separate failure, a run that thinks a full
  capped block every round and acts almost never, leaves the conversation
  almost static (29607 tokens growing by 7 per round) and is invisible to the
  breakage detector.
