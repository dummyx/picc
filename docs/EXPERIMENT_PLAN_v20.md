# Experiment plan: v20 (v19 again, with the round check)

Written before the first run. Harness commit: `ea94797`, plus `118d288`
(the wording for a snapshot that does not parse; found by the trial run). Everything not stated here is as in [v19](EXPERIMENT_PLAN_v19.md):
the same two tasks, the same specifications (v19's text, Amendment 1
included, unchanged), the same three languages, the same budgets, server,
model, endpoints, validity gate, decision rule and exclusions.

## Why v19 is not enough

v19 fixed the specification: a worked example, the input rule, the deadline
rule, the specification kept in `AGENTS.md`, then (Amendment 1) where the
commands run. It still lost runs to the same kind of mistake:
`v19-sql-rust-r3` built its crate in `/workspace/pisql/` (hidden score 0);
`v19-c18-python-typed-r2` never ran `mypy` in 380 commands and its program
had type errors, so the build command failed on every snapshot (hidden score
0). v17 and v18 had lost nine runs the same way before (stdin instead of the
named file, a `1|x` row where `ok 1` belongs, a value where the `ok` line
goes, a snapshot taken mid-edit).

These are one defect, not several. The agent never sees the result of the
harness's own build-and-run step. Every round the harness builds the snapshot
with the official command and runs it; the agent is told nothing, so the only
check it has is its own, and whatever it misreads stays misread for two
hours. Each v19 sentence closed the hole the last run had found; the next run
found the next one. No sentence can close them all.

## What changes

One thing. After every round, the scorer that already builds the snapshot
also runs the specification's worked example on it, and the next round's
message is the result instead of the bare `Continue.`:

- the build command failed → the command and its output (for typed Python,
  the `mypy` output);
- built, but the example's output differs → what the program printed, what
  the specification requires, and the first line where they differ (SQL), or
  what each of the two example programs did (compiler);
- both fine → one line saying so;

followed by `Continue.` in every case. The exact wording is in
`scripts/run_experiment.py:round_check_message`; six real v18/v19 workspaces
that scored 0 were run through it before this was written up, and each
message names the problem (`analysis/v20-check-demo/`, made by
`analysis/v20_check_demo.py`).

What the check uses is already in the specification: the build command, the
entry command, the example input and output. No visible or hidden test, no
score, no round number and no hint reaches the agent through it. The wording
is the same for every language and both tasks. It is switched on by one
block in the study manifest (`round_check`), frozen into each run like every
other factor; the scorer records the check in every snapshot's summary
(`check`), and `rounds.jsonl` records the message each round was started
with.

The study ids are new, `picc-sql-minimal-v10` and `picc-c18-minimal-v6`.
Apart from the id, the description and the `round_check` block, the manifests
are v19's (a test pins this).

**Checked before the batch:** `make validate` (unit tests incl.
`tests/test_round_check.py`: the example files equal the specification text
byte for byte; the reference-backed mock engine passes the check and the
reject-all and constant engines fail it with the right detail; the GCC-backed
mock compiler passes both example programs and the reject-all and constant
compilers fail one each; the message for every case; the manifest validation;
a frozen copy of each v20 condition carries the example and the switch), `make tasks-smoke` (both scorers in the pinned image), and the six zero
workspaces above through the pinned image. No separate trial run: the owner
asked for v20 to start the moment v19 ends, so the first check message of the
first run (`runs/v20-sql-*/artifacts/rounds.jsonl`, round 1, `message`) is
read as soon as it exists, and the batch is stopped if it is not what
`round_check_message` is tested to produce.

**Trial run** (`v20-trial-python-r1`, pilot profile, 2026-10-04 22:05Z, not
counted): the message reached Pi exactly as composed. Its content showed one
wording defect: the 12-minute first snapshot was mid-edit, `pisql.py` did not
parse, the source audit reported that before the build, and the message
called it "what the specification forbids". Fixed before the first main run:
findings whose kind is a parse or read failure are reported as "a source file
could not be read", forbidden-use findings as before, each with file and
line; the scorer passes the finding kind through.

## Runs

Twenty-one, two hours each, about 46 hours:

- `v20-sql-<condition>-r<1..3>` for `rust`, `python`, `python-typed`,
  `rust-minimal-spec`;
- `v20-c18-<condition>-r<1..3>` for `rust`, `python`, `python-typed`.

`rust-minimal-spec` (v19 Amendment 2's arm: Rust with the 170-word
specification, no example, no subset detail, no semantics) gets the same
round check as every other arm, so the only difference between it and
`rust` is the specification text. Consequence, stated here so it is read
into the result: the minimal-spec agent sees the example's required output
only through the check, and only when its own output differs from it. Its
one v19 run (`v19-sql-rust-minimal-spec-r1`) is under v19's protocol and is
not pooled with these.

## What this batch can and cannot show

A zero now means the program is bad, which is what a zero should mean. A run
whose check never passes is a finding about the agent, not a gap in the
specification. With three replicates per language the typing question stays
descriptive at this size (v19's SQL half put the typing difference at −0.008
with spreads of 0.05–0.09); what v20 adds is that the spread is no longer
made of contract zeros.

## Analysis

`make study-summary STUDY=studies/sql/study.json`,
`make study-summary STUDY=studies/c18/study.json`, then
`python3 analysis/v20_results.py`, which adds per run the round after which
the check first passed, how many rounds it passed, and the final snapshot's
check status.
