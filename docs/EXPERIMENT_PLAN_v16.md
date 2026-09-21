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

That is a coherent mechanism: a reply reasoning to 96,669 characters is
spending about 24,800 of its 32,768 output tokens before it writes anything,
so any further thinking ends the reply with nothing in it. Clipping the tail
removes exactly that. It is not proof. The serving stack changed in the same
step, and SGLang reports reasoning tokens as 0 in the usage Pi records, so the
budget cannot be observed firing directly -- only inferred from where the
distribution stops.

An earlier note here claimed the budget never bound at all. That used 4.7-5.3
characters per token, measured on short generations, where long code-heavy
reasoning runs nearer 3.9.

**Open for the full batch**: whether the budget or the serving change is doing
the work. Running one typed condition with `LOCAL_THINKING_BUDGET` empty would
separate them, and costs one run.

## Exclusions

The pilot-profile run `v16probe-python-typed-r1` is not part of this. It ran
on the manifest's 0.4-hour / 2-round smoke budget by mistake and is far too
short to address the question; it is kept only for its cut-off rate.
