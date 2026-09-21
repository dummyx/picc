# Experiment plan: v16 (does bounding reasoning restore the typed condition?)

Written before the first run. One question.

## Why a new manifest version

`picc-sql-minimal-v6`, not v5. The model is served by different software on a
different compression of the same weights (SGLang 0.5.20 serving
`RadixArk/Qwen3.8-27B-NVFP4`, where v10-v15 used llama.cpp serving a Q4_K_XL
GGUF), and replies now carry a hard cap on reasoning length that did not exist
before. v15 runs and v16 runs must not be pooled, and a new manifest id is what
enforces that.

See `docs/INFERENCE_SGLANG.md` for the serving configuration and its log.

## Question

Under `mypy --strict`, the agent produced nothing: across nine v15 runs the
typed condition made zero write or edit calls in 44 rounds, with 61-64% of its
replies cut off while still reasoning against 3-10% elsewhere. Raising the
output cap from 32768 to 65536 did not help — a fresh run spent the whole
65536 on one reply's reasoning and still called no tool (report section 18).

Does bounding **reasoning** rather than the **reply** restore it?

The mechanism is already demonstrated on this endpoint. Same prompt, same
4096-token output cap:

| thinking budget | reasoning | answer |
|---|---|---|
| none | 17,527 chars | **0 chars**, finish=length |
| 256 | 1,349 chars | 16,952 chars |
| 1024 | 4,841 chars | 13,323 chars |

The first row is the v15 failure in a single request. What is not yet known is
whether removing it is enough to make the typed condition produce a working
engine over a whole run, or whether the typing gate obstructs it some other
way as well.

## Design

- `studies/sql/study.json` (`picc-sql-minimal-v6`), SQL task.
- `LOCAL_THINKING_BUDGET=8192` against `LOCAL_MAX_OUTPUT=32768`, so at most a
  quarter of a reply is reasoning. Server launched with
  `--enable-strict-thinking` or the budget is silently ignored.
- Everything else as v15: `PROFILE=main` (2 h, 30 rounds, 45-minute round
  cap), same prompts, same specification, same conditions.
- Probe first: one `python-typed` run. A full batch only if it justifies one.

## Endpoints

Primary, per run, in this order:

1. **Did it write anything** — count of write and edit calls. This is the
   endpoint the v15 failure is defined by, and it is binary in practice: v15
   typed runs recorded zero.
2. **Cut-off rate** — replies ending on `length`, against v15's 61-64% typed
   and 3-10% elsewhere.
3. **Produced a working engine**, then hidden score among those that did.

## Decision rule, fixed before the data

- **Budget helps**: the run makes write calls and its cut-off rate is below
  20%. Proceed to a full batch of three conditions.
- **Budget does not help**: cut-off rate falls but the run still writes
  nothing. The cause is not reasoning length, and the typing gate itself is
  the next suspect.
- **Budget is not the mechanism**: cut-off rate stays high. The budget is not
  being enforced; check the server before concluding anything about typing.

## What the probe run measured, and a correction

`v16-sql-python-typed-r1` met every clause of the decision rule: 99 write and
edit calls, 0.0% of replies cut off, 0.0% stream errors, hidden score 0.8139
on the final snapshot against 0.0 for all three v15 typed runs and 0.8044 for
the best run anywhere in v15.

The attribution needs care, and a first pass at it was wrong. Reasoning length
per reply, same measurement over both batches:

| run | replies | cut off | median | p90 | max |
|---|---|---|---|---|---|
| v16 typed r1 | 437 | 0.0% | 605 | 4,542 | 31,924 |
| v15 typed r1 | 22 | 63.6% | 1,500 | 1,500 | 62,234 |
| v15 typed r2 | 23 | 60.9% | 1,500 | 1,500 | 96,669 |
| v15 typed r3 | 21 | 61.9% | 1,500 | 1,500 | 96,448 |
| v15 python r1 | 104 | 9.6% | 660 | 3,591 | 68,118 |
| v15 rust r1 | 177 | 2.8% | 678 | 5,277 | 58,304 |

Two things follow.

**The v15 typed medians are an artefact.** 1,500 at both the median and the
p90 is `truncation-repair.ts` replacing a cut-off reply with 1,500 characters
of its reasoning. Over 60% of those replies are repair stubs, not reasoning.

**The budget did not change typical reasoning; it clipped the tail.** v16's
median of 605 is indistinguishable from v15's *untyped* runs at 660 and 678,
which were never the problem. What differs is the maximum: 31,924 against
58,304 to 96,669. Three v16 replies sit within 1,200 characters of each other
just below 32,000, which at roughly 3.9 characters per token for dense
reasoning is the 8,192-token budget binding — on the order of 1% of replies.

### The budget is enforced, and it bound on exactly four replies

Counted, not inferred. `analysis/reasoning_tokens.py` rebuilds each reply's
reasoning from the `thinking_delta` events and tokenizes it with the served
checkpoint's own tokenizer, so these are the numbers the server saw:

| run | replies | cut off | median | p90 | max | at budget | over 8192 |
|---|---|---|---|---|---|---|---|
| v16 typed r1, budget 8192 | 437 | 0 | 160 | 1,339 | **8,192** | **4** | **0** |
| v15 typed r1 | 22 | 14 | **32,766** | 32,768 | 32,769 | 0 | 15 |
| v15 typed r2 | 23 | 14 | **32,766** | 32,768 | 32,769 | 0 | 15 |
| v15 python r1 | 104 | 10 | 190 | 19,910 | 32,770 | 0 | 13 |
| v15 rust r1 | 177 | 5 | 169 | 2,220 | 32,768 | 0 | 8 |

In v15's typed runs the *median* reply reasoned 32,766 tokens: more than half
of all replies spent the entire 32,768-token output cap thinking and so
contained nothing. That is the failure, measured. It was present in every v15
condition -- 13 runaway replies in the python run that scored 0.856, 8 in the
rust run that scored 0.811 -- and the typed condition simply had it worst.

In v16 r1 the maximum is exactly 8,192, four replies sit at the budget and
none is over it. Output-token arithmetic says which four: the three whole-file
writes (8,192 reasoning tokens followed by 19,387, 21,114 and 23,390 tokens of
file, at an identical 4.03-4.06 characters per token) and one planning reply
(8,192 followed by a 65-token tool call). Those are the replies that would
have run to the cap.

Direct measurement against the endpoint agrees, same prompt, production
output cap: with no budget 32,768 reasoning tokens and a 0-character answer,
`finish=length`; with a budget of 8192, 8,193 reasoning tokens and a
58,114-character answer, `finish=stop`.

Three earlier readings here were wrong and are superseded: that the budget
caused the improvement (right, but asserted without evidence), that it never
bound, and that it bound on "about 1%". All three divided character counts by
a characters-per-token ratio, and that ratio is not a constant: 2.8 on short
prose, 3.3-3.9 on the agent's code reasoning, 4.3 on a design essay. Reasoning
length in this project should be counted with the tokenizer or read from the
endpoint, never converted.

### Reasoning tokens are not in the run records

SGLang reports them as a top-level `usage.reasoning_tokens`. Pi reads
`usage.completion_tokens_details.reasoning_tokens`, the OpenAI-standard
location, so every reply in a run records `reasoning: 0`. Neither is wrong;
they disagree on where the field lives, and Pi has no compat option for it.
`analysis/reasoning_tokens.py` is the way around it.

## The budget control run

`v16nb-sql-python-typed-r9`: the same typed condition, same budget, same
everything, with `LOCAL_THINKING_BUDGET` empty so no thinking budget is sent.
Replicate 9 so it cannot occupy a cell a real replicate needs, and excluded
from pooling like the probe.

It answers the one question the first run could not. Read it against
`v16-sql-python-typed-r1`:

- **writes, and cut-offs near zero** -> the budget is an unused guard. The
  serving change is what fixed the typed condition, and the full batch should
  run without the budget rather than carry a setting that does nothing.
- **no writes, and cut-offs high** -> the budget matters, the first run simply
  stayed under it, and the batch keeps it.

Either way the batch that follows has one configuration with a reason behind
it, instead of a setting nobody can account for.

## Result of the control, and what the pair of runs shows

Both runs finished on the wall budget. Same server process, byte-identical
prompts, Pi settings and extensions; the only differences on record are the
budget and the scoring containers' memory ceiling (16 GB for r1, 8 GB for the
control), which cannot reach the agent because it never sees scores here.

| | r1, budget 8192 | control, no budget |
|---|---|---|
| rounds | 3 | 7 |
| replies | 437 | 303 |
| writes and edits | 99 | 101 |
| replies cut off | 0 | 5 (1.7%) |
| reasoning tokens: median / p90 / max | 160 / 1,339 / **8,192** | 136 / 1,099 / **32,767** |
| replies reasoning past 8,192 | 0 | 9 |
| visible score by round | 0.427, 0.864, 0.866 | 0, 0, 0, 0, 0, 0, 0.789 |
| hidden score, final snapshot | **0.8139** | **0.7852** |

**The control recovered.** Its first five rounds each ended on a reply that
reasoned through the entire 32,768-token output cap and contained nothing:
48 minutes, 40% of the run, with no tool call that did anything. In round 5
the pattern broke without intervention -- 77 replies, no cut-offs, 24 writes
-- and the last round produced an engine scoring 0.789 visible, 0.7852 hidden.

What that does and does not show, at one run each:

- **The budget is not necessary for a working engine on this stack.** The
  decision rule above expected a control without it to write nothing; it
  wrote 101 times and scored 0.7852. That branch of the rule did not occur.
- **The budget removes the failure it targets.** Nine runaway replies without
  it, none with it; five dead rounds without it, none with it; first non-zero
  score in round 0 with it, round 6 without.
- **No score difference can be claimed.** 0.8139 against 0.7852 is 0.029,
  under a quarter of the 0.13 threshold, from one run per side.
- **Why v15's typed runs never recovered and this one did is not known.** The
  three v15 runs stayed in the dead-round pattern for 44 rounds between them;
  the control left it after five. The serving stack differs, the strict-
  thinking token filter was on, and it may also simply be chance. One run
  cannot separate these.

Typical reasoning is the same in both runs (median 160 against 136). The
difference is confined to the tail, which is where the budget acts.

The v17 batch keeps the budget: it costs nothing measurable (it bound on 4 of
437 replies in r1) and it spares a run the dead rounds. The v17 write-up is to
describe it as a guard against wasted rounds, not as the thing that makes the
typed condition possible.

## Exclusions

The pilot-profile run `v16probe-python-typed-r1` is not part of this. It ran
on the manifest's 0.4-hour / 2-round smoke budget by mistake and is far too
short to address the question; it is kept only for its cut-off rate.
