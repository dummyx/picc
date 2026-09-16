# Minimal PiCC experiment

`study.json` defines one condition, `minimal`, with a short task-specific input
on the standard Pi coding agent. The initial message is the rendered contents
of [task.md](task.md): compiler scope, build/invocation commands, output contract,
and experiment constraints. It contains no architecture, numbered stages,
implementation order, testing strategy, or progress-memory instructions.

## Agent inputs

- Initial message: the short contract in `task.md`, with the Rust adapter's
  language and commands substituted. No other text is appended.
- Continuation message: `Continue.` in the same Pi session.
- `AGENTS.md` and `TASK.md`: blank mount targets, with no instructions or pointer.
- Starting repository: empty apart from Git and the runner's ignored control
  paths; no implementation scaffold.
- Tools: Pi's `read`, `bash`, `edit`, `write`, `grep`, `find`, and `ls`.
- Benchmark tests, scores, reference oracle, and budget/status tools: unavailable
  to the agent. It can build and write its own tests.

The experiment tools extension is omitted entirely, including its tool
descriptions, prompt guidelines, pushed feedback, and event hooks. The access
guard and configured bash timeout remain. Guard failures can return access
restriction messages. Pi's built-in system prompt, built-in tool descriptions,
and normal session compaction remain; this condition minimizes added experiment
instructions, not the coding agent's own instructions.

The outer harness still enforces the configured time/round limits, snapshots the
repository, and evaluates snapshots without sending those scores to the agent.
Hidden evaluation remains post hoc. Pi JSON session logs remain available;
experiment-tools extension events, including its compaction logging, are absent.

## Use

From the repository root:

```bash
make study-validate STUDY=studies/minimal/study.json
make study-materialize STUDY=studies/minimal/study.json CONDITION=minimal RUN_ID=inspect-minimal
```

Inspect `runs/.study-materializations/inspect-minimal/prompts/INITIAL.txt` before
running. The materialization is a frozen copy; it does not start a model session.

```bash
make study-run STUDY=studies/minimal/study.json CONDITION=minimal PROFILE=main RUN_ID=minimal-main-r1 REPLICATE=1
make study-hidden-all RUN_ID=minimal-main-r1
make study-report RUN_ID=minimal-main-r1
```

Model/provider, image, and budgets come from the normal configuration and are
frozen for each run. This is a separate study (`picc-minimal-v1`): specification
detail, prompting, and feedback all differ from the starter baseline, so their
comparison cannot isolate the effect of workflow instructions alone.

The `spec-minimal` condition of `studies/spectests/study.json` is different
again: it keeps the starter workflow, prompts, and experiment tools and
reduces only the specification document (`studies/assets/specs/minimal.md`).

The starter's former `prompt-minimal` condition is now named `workflow-reduced`.
Its full specification and feedback tools remain. Historical run IDs and
analysis tables retain the original condition name.
