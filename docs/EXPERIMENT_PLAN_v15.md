# Experiment plan: v15 (supersedes v13 and v14)

Written before the first run. The question is the one v10 raised and v11-v14
could not answer, because the agent's session kept dying on a harness defect
rather than on anything the conditions did.

## The defect, fixed and verified before this run

Pi summarizes a conversation by serializing it to text and sending that text in
one request. Its serializer truncates tool results and nothing else, so a
reasoning model's thinking blocks and a `write` call's file body go in whole.
The request outgrew the 131,072-token window — 132,716 to 401,158 tokens across
twelve runs — compaction failed, and every later round of that session failed
the same way. Under the smaller reserve used in v6-v9 the same defect appeared
from the output side instead: the summary shares its token budget with the
thinking that precedes it, so nine turn-prefix summaries stopped on length.

`pi/extensions/compaction-bound.ts` takes over compaction through Pi's
`session_before_compact` hook. It caps thinking, assistant text, and tool-call
arguments, drops the oldest messages if the capped text still does not fit, and
hands the bounded work back to Pi's own `compact()` with thinking off for that
one call. Report section 17.7 has the full account.

Verification, which the three earlier attempts lacked: `runs/v14-sql-python-r1`
died at round 10 with a 354,786-token request. Resuming that exact session in
the pinned image reproduces the failure in 60 seconds; resuming it with the
extension compacts on the first attempt and the session then completes 32
further turns and 35 tool calls. This plan rests on the failing case, not on a
healthy run that never reached the failing shape.

`reserveTokens` returns to 40,960, the value the output-cap invariant asks for.
It was at 65,536 only to delay the oversized request.

## Question

Does requiring type annotations and `mypy --strict` change how well the agent
builds an in-memory SQL engine from an empty repository?

## Design

- Study `studies/sql/study.json`, manifest `picc-sql-minimal-v5`. The manifest
  id is new because the harness changed; runs from v11-v14 are not comparable
  and must not pool with these.
- Conditions unchanged: `rust`, `python`, `python-typed`. The two Python arms
  differ only in the type gate; the behavioral requirements are identical.
- Three replicates each, 9 runs, `PROFILE=main`: the carried-over budget of
  2 h agent time with a 45-minute round cap.
- Order from `make study-schedule`, run ids `v15-sql-<condition>-r<n>`.

## Endpoints

Primary: hidden score on the held-out partition, `python-typed` against
`python`, paired by replicate.

Secondary: completion rate at the 0.95 threshold; rounds used; agent time;
termination reason; turn shape from `analysis/turn_shape.py`; session survival
from `compaction_end` events, which should now be zero.

## Decision rule, fixed before the data

- **Typing helps** if the paired median hidden score of `python-typed` exceeds
  `python` by at least 0.13, the threshold used since v4.
- **Typing hurts** if it falls short by at least 0.13.
- **No effect detected** otherwise.

At three replicates this is descriptive, not a test. `rust` is the reference
arm and carries no hypothesis.

## Exclusions

Pilots, resumed runs, and any run whose frozen condition does not match the
manifest. A run whose session breaks is reported as a harness failure and
excluded from the score comparison; if any occur, the fix above is incomplete
and the batch is stopped rather than analyzed.

## Analysis

`make study-summary STUDY=studies/sql/study.json`, plus
`analysis/v15_results.py` for the paired comparison and the survival column.
