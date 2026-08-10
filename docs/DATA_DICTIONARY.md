# Data dictionary

## `metadata.json`

One object per run. Important fields:

- `starter_version`, `run_id`, `profile`, `replicate`;
- start/end timestamps and termination reason;
- provider, model ID, and Pi thinking setting;
- immutable Docker image ID;
- non-secret effective configuration;
- prompt, settings, and extension SHA-256 hashes;
- visible and hidden manifest hashes;
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

The Coding Plan key is never written to run artifacts.

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
- paths to raw stdout/stderr logs.

## `artifacts/snapshots.jsonl`

One row per harness Git snapshot:

- round and timestamp;
- Git commit/tree hashes;
- diff insertions, deletions, and changed-file count;
- Rust file and LOC counts;
- elapsed experiment time;
- Pi exit/timeout state;
- visible evaluation summary.

Snapshot `elapsed_seconds` is cumulative active harness time, including prior
execution attempts when a trajectory has been resumed.

## `artifacts/resume-events.jsonl`

Append-only audit records written around each resume. `resume_started` records
the prior lifecycle state, next round, remaining frozen time and round budgets,
workspace commit, Pi session path, immutable image ID, and control/manifest
hashes. `resume_finished` records the resulting lifecycle status, termination
reason, cumulative elapsed time, final round, and Git commit.

The start event is written before the new Pi invocation. Its corresponding
metadata entry appears in `interventions`; attempt-level lifecycle details
appear in `execution_attempts`.

## `artifacts/evaluations/*.json`

Full evaluator output:

- source audit findings;
- Cargo build command/result;
- selection parameters;
- macro and micro summaries;
- per-stage valid/invalid rates;
- every test result and failure classification.

Common failure types include:

- `source_audit_failure`;
- `build_failure`;
- `unexpected_reject`;
- `unexpected_accept`;
- `compiler_crash`;
- `compiler_timeout`;
- `missing_assembly`;
- `assembly_or_link_failure`;
- `wrong_behavior`;
- `execution_timeout`.

## `artifacts/tool-evaluations/*.json`

Full result for each `test_visible` call made by the agent. Pi sees only a
compact summary; the complete record is retained for analysis.

## `artifacts/hidden-scores.jsonl`

Created by `evaluate_run.py`. One row per post-hoc hidden snapshot evaluation:
round, Git commit, elapsed time, summary, and full-output path.

## `artifacts/extension-events.jsonl`

Events emitted by `experiment-tools.ts`, including:

- visible-test starts/completions;
- compaction preparation/completion;
- selected provider HTTP errors.

## `artifacts/guard.jsonl`

Every obvious tool request blocked by `experiment-guard.ts`, with tool name,
reason, and sanitized subject.

## `artifacts/state.json`

Current outer-harness state exposed to the model through `experiment_status`:
round, fixed budget, elapsed/remaining time, maximum stage, and last visible
summary. For resumed runs, elapsed and remaining time are cumulative across
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
