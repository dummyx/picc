# The fixed rules of one run

Every run follows these rules, whatever its task or condition. What a
condition may change (prompt, specification, test access, language,
reference, budget) is in [STUDY_PROTOCOL.md](STUDY_PROTOCOL.md) and
[studies/README.md](../studies/README.md); what a run records is in
[DATA_DICTIONARY.md](DATA_DICTIONARY.md).

## A run

One run is one attempt by one agent: a fresh, empty Git repository and a
fresh Pi session, working on one condition of one study, with no human
input. Continuing a partly built workspace is not a new run. Runs of the
same condition use identical settings but are not identical: the model
samples at random, and no seed is fixed.

A run executes from its condition's frozen copy of the harness
(`runs/.study-materializations/<run-id>/`, built by `scripts/study.py`),
never from the repository, so changing the repository cannot change a run
that exists.

## What is fixed for every run

- **The agent.** Pi 0.85.1 (`PI_VERSION`), one persistent session, started
  with `pi --mode json`; every later round continues the same session.
- **The model.** Declared in `.env` as `MODEL_PROVIDER` and `MODEL_ID`, with
  no default: an empty value stops the harness rather than guessing. The
  campaign uses a local model (`MODEL_PROVIDER=local`, served by SGLang
  since v16 and by llama.cpp before; [INFERENCE_SGLANG.md](INFERENCE_SGLANG.md)).
  The client side of the endpoint (address, context window, output cap,
  sampling settings, thinking budget) is frozen into the run's
  `control/pi/models.json` and `metadata.json`. v17, for example, froze
  `RadixArk/Qwen3.8-27B-NVFP4`, thinking level `high`, a 131,072-token
  context window, a 32,768-token output cap and an 8,192-token thinking
  budget. A different model is a different experiment and is never pooled.
- **The container.** The pinned image `EXPERIMENT_IMAGE`
  (`picc-experiment:0.5`, built by `make image`), recorded by its image ID;
  a resume or a scoring pass refuses an image whose ID changed. The agent
  runs with no added privileges, a read-only root, and limits on CPU (8),
  memory (16 GB) and processes; scoring containers get 8 GB.
- **The agent's tools.** Pi's `read`, `bash`, `edit`, `write`, `grep`,
  `find` and `ls`, plus `test_visible`, `experiment_status` and
  `reference_oracle` where the condition gives them. No skills or prompt
  templates. A bash command the agent starts without its own time limit is
  stopped after 120 seconds (the pinned `@cad0p/pi-bash-timeout` package,
  loaded through `pi/settings.json`).
- **The extensions loaded into Pi** (`pi/extensions/` in the run's copy):
  - `experiment-guard.ts`, the rule checker. It blocks downloads, running an
    existing compiler or database engine, reading credentials or the
    harness's own records, editing `AGENTS.md`, `TASK.md` or `SPEC.md`, and
    writing outside `/workspace`, and logs each block to
    `artifacts/guard.jsonl`. Rules about which commands run read the command
    as the shell will run it, on every line of it, and leave out quoted text
    and here-documents handed to other programs (code being written to a
    file); rules about text anywhere, such as a URL or an import of a
    database module, read all of it. Until v18 every rule read the whole
    text and only its first line counted as a command. It is an audit layer,
    not a sandbox.
  - `experiment-tools.ts` and `study-setup.ts`, when the condition has
    experiment tools or a starting scaffold.
  - `compaction-bound.ts` and `truncation-repair.ts`, in every run. The
    first keeps a conversation summary request within the context window
    (Pi's own summary sent whole thinking and whole file bodies and could
    outgrow it, which killed sessions in v10–v14). The second replaces a
    reply that hit the output cap while still thinking, and so contains
    nothing, with the start of its thinking and a note that it was cut off
    (left in place, such a reply made the next one far likelier to be cut
    off too). A run whose first round did not load both stops at once.

## The task

The condition's prompts and specification describe the task; the product
interface is fixed per task:

| Task | The agent's program is run as |
|---|---|
| C compiler (chapters 1–10 and 1–18) | `<program> INPUT.c -o OUTPUT.s`, writing x86-64 assembly |
| SQL engine | `<program> INPUT.sql`, printing each statement's result |

The exact command comes from the condition's language settings
(each task's `candidates/` folder under `studies/`). A C test is handed to the agent's compiler
after the C preprocessor (`gcc -E -P -C -nostdinc`), as the test suite's own
driver does.

## Rounds, time and stopping

A round is one Pi invocation. Round 0 gets the first message (`INITIAL.txt`);
every later round gets the same continuation message (`CONTINUE.txt`).
After each round the harness commits the whole workspace to its own Git
history (a saved version) and scores that version on the visible tests; the
agent sees the result only if its condition allows. Scoring time is not
charged to the agent (since v11).

Budgets come from `config/defaults.env`, overridden by `.env` and by the
condition's `budget` block, and are frozen per run in `metadata.json`. The
`pilot` profile is a short trial that never counts. Recent `main` runs had 2
hours of agent time, at most 30 rounds, at most 45 minutes per round, and
the task's full stage range.

A run stops at the first of:

| Reason recorded | When |
|---|---|
| `wall_time_budget` | the agent's time is used up |
| `max_rounds` | the rounds are used up |
| `visible_complete_after_review` | the visible score reached 1.0 and the one review round that follows is done |
| `round_timeout` | two rounds in a row (`MAX_CONSECUTIVE_ROUND_TIMEOUTS`) hit the round time limit without changing the workspace; a round that hit the limit while still changing files is work, not a stall (since v11) |
| `context_overflow` | two rounds in a row (`MAX_CONSECUTIVE_DEAD_ROUNDS`) in which Pi's summary failed and the agent did nothing |
| `pi_process_failure` | Pi exited with an error |
| `human_abort`, `harness_exception` | an operator interrupted, or the harness failed |

## Scoring

After the run, every saved version is scored on the hidden tests
(`make study-hidden-all`), in a separate container with the scorer frozen
into the run's copy (`evaluator/`). The hidden tests are never mounted into
the agent's container.

- **C compiler tasks.** A valid test program is compiled by the agent's
  compiler, linked by GCC, and run; its exit status and output must match
  GCC's own build of the program. An invalid test program must be rejected:
  a nonzero exit status, an error message, and no assembly file. Per stage,
  the pass rates of
  valid and invalid programs are averaged separately and then together;
  the score is the mean over stages, so a compiler that rejects everything
  cannot score well on the invalid programs alone.
- **Random programs (chapters 1–10 only).** The final saved version, and the
  last one that built if that is different, are also checked on 100
  generated programs per stage against GCC (`FUZZ_*` settings).
- **SQL engine.** Each hidden test script is run whole; its score is the
  share of its checked records the engine gets right, compared by the rules
  of SQLite's own test runner. A stage's score is the mean of its scripts;
  the score is the mean over stages. The expected answers come from the
  pinned SQLite 3.40.1, and the scorer refuses any other version.
- **Source rules.** Before scoring, the agent's program is checked against
  its language's rules (no third-party packages, no calls to an existing
  compiler or database engine, no links or binaries). A blocking finding
  scores that version 0; an advisory one is reported and does not.
- **Last version that built.** Since v8 every batch also reports the last
  saved version whose hidden scoring built with no blocking finding, so
  that a run cut off halfway through a rewrite is not judged only by its
  broken last version.

## Continuing a run that stopped (resume)

`make study-resume RUN_ID=...` continues a run, from its frozen copy, only
when all of these hold:

- it stopped with `round_timeout` or `pi_process_failure`, and has time and
  rounds left;
- it has not been scored on hidden tests or reported yet;
- its frozen model and settings still agree with its metadata, and the
  image ID is unchanged;
- its round and saved-version records are complete and in sequence, and
  the next round's files do not exist yet;
- it has exactly one Pi session, and its workspace is clean and at the last
  saved version;
- no container or harness process for the run is active.

A resumed run continues the same session with the unchanged continuation
message and the next round number; time and rounds already used are not
given back, and time while nothing ran is not charged. It records every
attempt in `metadata.json` and `artifacts/resume-events.jsonl`, and sets
`protocol_comparable` to false: it is reported separately and never counted
as one of a batch's runs.

## Interventions and exclusions

No one intervenes in a run once it starts: no messages to the agent, no
workspace edits, no prompt changes. Any intervention makes the run
noncomparable and is recorded. A run may be excluded only by a rule written
in the batch's plan before the batch, such as a demonstrable harness defect
before the first model reply. Model errors, bad plans, programs that do not
build and ordinary slowdowns are results, not reasons to exclude.

## What is recorded before a batch

The batch's plan (`docs/EXPERIMENT_PLAN_v<N>.md`), committed before the
first run, names the repository commit, the study file and id, the
conditions, the number of runs, the budgets, what will be measured, and the
rules for exclusions. Every run records the rest itself: the effective
configuration except secrets, the model and endpoint settings, the image ID,
the Pi version, the host, and the test manifests
([DATA_DICTIONARY.md](DATA_DICTIONARY.md)). `make preflight` checks, before
any run, that the served model and its usable context match the frozen
settings.
