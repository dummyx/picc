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

## Exclusions

The pilot-profile run `v16probe-python-typed-r1` is not part of this. It ran
on the manifest's 0.4-hour / 2-round smoke budget by mistake and is far too
short to address the question; it is kept only for its cut-off rate.
