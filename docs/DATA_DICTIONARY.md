# Data dictionary

Every file a run leaves under `runs/<run-id>/`, written by the harness scripts
in the run's frozen copy (`scripts/run_experiment.py` during the run,
`scripts/evaluate_run.py` and `scripts/summarize_run.py` afterwards). What the
study layer adds (`study-metadata.json`, `study-control/`, the fuzz ledger's
details, study summaries) is in [STUDY_DATA_DICTIONARY.md](STUDY_DATA_DICTIONARY.md).

```text
runs/<run-id>/
├── metadata.json
├── study-metadata.json, study-control/   # see STUDY_DATA_DICTIONARY.md
├── report.json, report.md
├── workspace/, workspace.git.bundle      # the agent's repository and its history
├── control/                              # frozen prompts, Pi settings, extensions, models.json
└── artifacts/
    ├── events/                # Pi's event stream and stderr, per round
    ├── sessions/              # Pi's session file
    ├── evaluations/           # full scorer output per saved version
    ├── tool-evaluations/      # full result of each test_visible call
    ├── home/, pi-global/      # the agent container's home and Pi directories
    ├── rounds.jsonl, snapshots.jsonl
    ├── hidden-scores.jsonl, fuzz-scores.jsonl
    ├── extension-events.jsonl, guard.jsonl
    ├── resume-events.jsonl    # only for a resumed run
    ├── reference-cache/       # only with the reference oracle
    └── state.json
```

## `metadata.json`

One object per run. Important fields:

- `starter_version`, `run_id`, `profile`, `replicate`;
- start/end timestamps and termination reason (below);
- provider, model ID, and Pi thinking setting; for `MODEL_PROVIDER=local` runs,
  `model` additionally records the frozen endpoint shape (`base_url`, `api`,
  `context_window`, `max_tokens`, `reasoning`, `thinking_format`,
  `sampling_params`), which resume revalidates against the frozen
  configuration;
- immutable Docker image ID;
- non-secret effective configuration;
- frozen budget;
- final visible summary;
- `resumed`, `resume_count`, and `protocol_comparable`;
- `execution_attempts`, one lifecycle record for the initial execution and each
  resume;
- `interventions`, the validation and checkpoint record captured when each
  resume starts.

`started_at` remains the start of the original trajectory. `ended_at` is the end
of the latest execution attempt, and top-level `elapsed_seconds` is cumulative
active harness time across all attempts. Paused time between attempts is not
included. Each `execution_attempts` row records its kind, round range, host,
attempt-local elapsed time, prior cumulative elapsed time, status, and
termination reason. Any resume sets `protocol_comparable` to `false`.

`termination_reason` is one of `wall_time_budget`, `max_rounds`,
`visible_complete_after_review`, `round_timeout` (consecutive capped rounds
that changed nothing), `context_overflow` (consecutive rounds whose
compaction failed with no work done), `pi_process_failure`, `human_abort`, or
`harness_exception`. [EXPERIMENT_PROTOCOL.md](EXPERIMENT_PROTOCOL.md) says
when each applies.

No API key is ever written to run artifacts: configuration keys containing
`KEY`, `TOKEN`, `SECRET`, `PASSWORD` or `CREDENTIAL` are left out of the
frozen configuration, and the generated `control/pi/models.json` references
the local endpoint's key only as the environment interpolation
`$LOCAL_API_KEY`.

## `artifacts/events/round-NNN.jsonl`

Raw Pi `--mode json` stream. It includes lifecycle, assistant messages, tool
execution, queue, retry, and compaction events exposed by the pinned Pi version.
`message_end` is the authoritative complete assistant message; streaming update
records contain deltas.

## `artifacts/events/round-NNN.stderr.log`

Pi process diagnostics. Provider transport errors and extension-load failures
may appear here.

## `artifacts/sessions/`

Canonical Pi session JSONL. The complete session history remains here even when
older model-visible context is compacted.

## `artifacts/rounds.jsonl`

One row per outer invocation:

- sequential round number across all execution attempts;
- elapsed process time;
- Pi exit status;
- timeout status;
- paths to raw stdout/stderr logs;
- `message`: the text the round was started with (round 0 the initial
  prompt; later rounds `CONTINUE.txt`, or, under `ROUND_CHECK=build-and-example`,
  the harness's check of the previous snapshot followed by it). Runs before
  v20 have no such field.

## `artifacts/snapshots.jsonl`

One row per harness Git snapshot:

- round and timestamp;
- Git commit/tree hashes;
- diff insertions, deletions, and changed-file count;
- `rust_files` and `rust_loc` (`.rs` files only, whatever the language; the
  study summary measures source size from the adapter's extensions instead);
- elapsed experiment time;
- Pi exit/timeout state;
- `round_evidence`: tool calls started in the round, whether Pi's compaction
  reported an error, and whether the workspace changed (the inputs to the
  stall and `context_overflow` rules);
- visible evaluation summary.

Snapshot `elapsed_seconds` is cumulative active harness time, including prior
execution attempts when a trajectory has been resumed.

## `artifacts/resume-events.jsonl`

Append-only audit records written around each resume. `resume_started` records
the prior lifecycle state, next round, remaining frozen time and round budgets,
workspace commit, Pi session path, and immutable image ID. `resume_finished` records the resulting lifecycle status, termination
reason, cumulative elapsed time, final round, and Git commit.

The start event is written before the new Pi invocation. Its corresponding
metadata entry appears in `interventions`; attempt-level lifecycle details
appear in `execution_attempts`.

## `artifacts/evaluations/*.json`

Full evaluator output, one file per scored version (`visible-round-NNN.json`,
`hidden-round-NNN.json`, and `fuzz-final.json` / `fuzz-last-buildable.json`
for the random-program check), each with its stdout and stderr logs:

- source audit findings (blocking and advisory);
- the adapter's build command and its result;
- selection parameters and the input policy (preprocessing);
- macro and micro summaries;
- per-stage valid/invalid rates (SQL: per-script scores);
- every test result and failure classification;
- when the materialized `evaluator/example/` exists (a study with
  `round_check`), the summary's `check`: the agent-facing build and entry
  commands, the build result (and its output when it failed), blocking source
  audit findings, and `example` — for the SQL task the program's output, the
  required output, the first differing line, exit status and stderr; for the
  compiler task one record per example program (status, exit status, stderr).
  `check.passed` is true when the build succeeded and the example did too.

Common failure types for the compiler tasks include:

- `source_audit_failure`;
- `build_failure`;
- `unexpected_reject`;
- `unexpected_accept`;
- `compiler_crash`;
- `compiler_timeout`;
- `missing_assembly`;
- `assembly_or_link_failure`;
- `wrong_behavior`;
- `execution_timeout`;
- `silent_rejection` (an invalid program rejected without an error message);
- `invalid_output_created` (an invalid program rejected but an assembly file
  left behind).

The SQL scorer records, per script, its records passed and in total and its
fractional `score` (the share of scored records passed), with per-stage and
overall scores in the summary ([studies/sql/README.md](../studies/sql/README.md)).

## `artifacts/tool-evaluations/*.json`

Full result for each `test_visible` call made by the agent. Pi sees only a
compact summary; the complete record is retained for analysis.

## `artifacts/hidden-scores.jsonl`

Created by `evaluate_run.py`. One row per post-hoc hidden snapshot evaluation:
round, Git commit, elapsed time, summary, and full-output path. Rescoring a
run replaces the file.

## `artifacts/fuzz-scores.jsonl`

Chapters 1-10 task only: the random-program check of the final snapshot and,
when it differs, of the last buildable one. Fields are in
[STUDY_DATA_DICTIONARY.md](STUDY_DATA_DICTIONARY.md).

## `artifacts/extension-events.jsonl`

Events logged by the extensions, one JSON object per line with an `event`
field:

- `experiment-tools.ts`: `test_visible_start` / `_end` / `_unavailable`,
  pushed reports (`test_pushed_start` / `_end` / `_error`), `reference_oracle_*`,
  `session_before_compact`, `session_compact`, and `provider_response_error`;
- `study-setup.ts`: `study_scaffold_applied`;
- `compaction-bound.ts`: `compaction_bound_loaded` when Pi loads it, and
  `compaction_bound` for each compaction it handles (sizes before and after,
  messages dropped);
- `truncation-repair.ts`: `truncation_repair_loaded`, and
  `truncation_repaired` for each cut-off reply it replaces.

If the first round of a run, or of a resume, does not log both `*_loaded`
events, the run stops.

## `artifacts/guard.jsonl`

Every obvious tool request blocked by `experiment-guard.ts`
(`blocked_tool_call`, with tool name, reason, and sanitized subject), and every
bash command the 120-second default timeout cut off (`bash_timeout_fired`).
A row without an `event` field, as the guard wrote them before v6, is a block.

## `artifacts/state.json`

Current outer-harness state exposed to the model through `experiment_status`:
round, fixed budget, elapsed/remaining time, maximum stage, last visible
summary, and `fixed_policy`, the sentence describing how the continuation
message is produced (fixed `Continue.`, or the round check followed by it). For resumed runs, elapsed and remaining time are cumulative across
active execution attempts, and the state includes the resume count.

## `workspace.git.bundle`

Portable copy of the complete product Git history. Restore with:

```bash
git clone runs/<id>/workspace.git.bundle restored-workspace
```

## `report.json` and `report.md`

Generated aggregate. The event parser is deliberately tolerant of provider
usage-field differences. Treat missing token fields as unavailable rather than
zero-cost evidence. Reports disclose whether a trajectory was resumed and is
therefore noncomparable with an uninterrupted run.
