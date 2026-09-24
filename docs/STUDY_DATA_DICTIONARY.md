# Study data dictionary

The study files, and what the study layer adds to a run and produces from
runs. The files every run leaves are in [DATA_DICTIONARY.md](DATA_DICTIONARY.md);
the list of studies and tasks is in [studies/README.md](../studies/README.md).

## Study manifest

A study JSON object contains:

- `schema_version`: currently `1`;
- `id`, `description`, and deterministic subset `seed`;
- optional `design` and `baseline_condition`; the starter uses validated
  one-factor-at-a-time overlays;
- `completion_threshold`;
- `defaults`: complete baseline condition;
- `conditions`: deep-merged overlays.

Each resolved condition contains:

### `prompt`

- `agents`: project-context prompt template;
- `initial`: first-request template;
- `continuation`: fixed continuation template;
- `experiment_tools`: optional boolean, default `true`. When `false`, omit the
  experiment tools extension and expose only Pi's built-in tools. Requires
  `tests.access='none'` and `reference.mode='none'`. The access guard remains;
  scaffold setup is included only when needed.

### `specification`

- `path`: specification template;
- `delivery`: `task_file`, `initial_prompt`, `initial_prompt_only`, or
  `workspace_file`. `initial_prompt` leaves a pointer in `TASK.md`;
  `initial_prompt_only` embeds the specification in the initial request and
  leaves `TASK.md` blank;
- `provenance`: at minimum `method`, with optional creator, source,
  generation-model, reviewer, and artifact-family fields.

### `tests`

- `access`: `none`, `tool`, or `files`;
- `feedback`: `none`, `aggregate`, `failures`, or `detailed`;
- `visible_subset_fraction` and `subset_seed`;
- `push_interval_minutes` (default 0): when positive, the harness runs the
  visible tests about that often and sends the report to the agent unasked
  (the v8 `tests-pushed` condition);
- optional `visible_partition` and `hidden_partition` paths;
- `provenance` fields analogous to specification provenance.

### `candidate`

- `adapter`: language-neutral build/invocation/audit adapter;
- `language` and `framework` labels, required to match the adapter;
- optional `scaffold` directory copied into the initial workspace.

### `reference`

- `mode`: `none`, `oracle`, or `source`;
- `oracle_limit` for black-box mode;
- `source` path for source-visible mode.

### `environment` and `budget`

Optional scalar environment overrides and per-profile budget overrides. They are
frozen in the materialized `config/defaults.env`. Do not use them casually in a
one-factor condition because they change compute or tooling.

### `task`

Optional `{id, runtime, max_stage, parameters}`; absent means the chapters 1-10
compiler (`c-compiler-ch1-10`, runtime `c-compiler`, 10 stages). `runtime` is
`c-compiler` or `sql-engine` and selects the scorer files copied into the
materialized `evaluator/`; the budget's `*_max_stage` may not exceed
`max_stage`. The SQL task's `parameters` pin `sqlite_version` and
`script_timeout_seconds`. See "Task studies" below.

## Candidate adapter

`candidate.json` defines:

- `language`, `framework`, and descriptive dependency policy;
- `build.command`, `build.artifact`, and optional timeout;
- `run.command`, with `{artifact}`, `{input}`, `{output}`, and `{workspace}`
  placeholders;
- `source_extensions` used for artifact measurement/audit;
- audit allowlists/patterns; the source audit scans the submitted program
  and rejects symlinks and binaries. For Rust it covers the Cargo package's
  `src/` plus files pulled in by path; for Python, since v10 Amendment 2, the
  entry module (the adapter's build artifact) and its import closure.
  `audit.roots` restricts the per-file scan to the program's own source
  tree (the Node adapters use `src`), and `audit.entry` names the entry
  module whose relative import closure is scanned even when it leaves the
  roots, so agent-authored test drivers elsewhere in the workspace are not
  mistaken for the compiler while a module the compiler actually imports
  cannot escape the scan; `audit.exclude_paths` names build-output
  directories (for example `dist`) that no audit walk inspects;
  `audit.node_builtins_only` and
  `audit.allowed_node_modules` bound Node imports the way
  `python_stdlib_only`/`allowed_python_modules` bound Python imports;
- `agent_notes`: adapter-specific layout or typing rules appended to the
  candidate bullet of the rendered `AGENTS.md`; adapters without notes render
  byte-identically to earlier batches;
- `agent_policy.blocked_bash_patterns`: `{pattern, reason}` rows rendered into
  the condition's Pi guard as additional bash blocks (the untyped JavaScript
  adapter withholds `tsc`, which the shared image contains);
- specification-rendering variables.

Audit findings are either blocking (delegation or unsafe execution: prohibited
imports, dependencies, vendored `node_modules`, binary artifacts, dynamic
loading) or advisory (environment inspection, `@ts-nocheck`/`@ts-ignore`/
`@ts-expect-error` suppression). Advisory findings set `audit_ok=false` but do
not gate scoring. For JavaScript/TypeScript the blocking text and import checks
run on comment-stripped code so that a comment cannot zero a run.

Every adapter of a task implements the same product contract.

## Fuzz oracle ledger

Chapters 1-10 task only. `runs/<run-id>/artifacts/fuzz-scores.jsonl`, written
by the hidden post-hoc evaluation, holds one row for the final snapshot
(`role: final`) and, since v8, a second row (`role: last_buildable`, output
`fuzz-last-buildable.json`) when the last buildable snapshot is not the final
one; ledgers from before v8 have one row and no `role`. Each row has
`partition` (`fuzz`), `role`,
`round`, `git_commit`, `git_tree`, `docker_image`, `elapsed_seconds`, the frozen
`policy` (`programs_per_stage`, `seed_base`, `run_timeout_seconds`,
`compile_timeout_seconds`, `deadline_seconds`), a `summary` (`fuzz_macro`,
`stage_pass_rates`, `evaluated_total`, `mismatches_total`, `skipped_total`,
`mismatch_kinds`, `stages_complete`, `deadline_hit`, `build_ok`, `audit_ok`),
and `output` (`artifacts/evaluations/fuzz-final.json`, the full per-stage
record with up to three sample failures per stage). The study summary verifies
the row against the final snapshot, image, adapter, and stage budget, recomputes
the macro from the per-stage rates, and exposes `fuzz_macro`,
`fuzz_stage_pass_rates`, `fuzz_programs_per_stage`, `fuzz_mismatches_total`,
and `fuzz_deadline_hit` per run, `median_fuzz_macro` per condition, and
`delta_fuzz_macro` in the paired deltas; `hidden_score_last_buildable`,
`fuzz_macro_last_buildable`, `last_buildable_round`, and the matching
`delta_*_last_buildable` columns score the last snapshot that built and passed
the audit (the final one when it built, 0 when none did; `None` with a
coverage warning when a pre-v8 ledger lacks the second fuzz row).
`pushed_test_reports` counts the visible-test reports the harness pushed to
the agent (`tests.push_interval_minutes` conditions). A run without the ledger is included
with null fuzz columns and a coverage warning.

Corpus evaluations record `input_policy`: the preprocessing command applied
to candidate inputs and any tests that fell back to their raw text.

Configuration keys frozen per materialization: `FUZZ_STAGE_PROGRAMS` (0
disables the oracle), `FUZZ_SEED_BASE`, `FUZZ_RUN_TIMEOUT_SECONDS`,
`FUZZ_COMPILE_TIMEOUT_SECONDS`, and `FUZZ_DEADLINE_SECONDS`.
Local runs record `model.serving_revision` as operator-managed.
`make preflight` checks the model alias and records server-reported metadata.

## `runs/.study-materializations/<run-id>/`

Condition-specific copy of the current harness (`config/`, `docker/`,
`scripts/`, `pi/`, `VERSION`). It adds rendered prompts (`prompts/`),
condition-aware extensions, the task's scorer with the adapter and
`task.json` (`evaluator/`; the fuzz oracle only for the chapters 1-10 task),
the visible subset, the constant hidden partition, the agent-visible folder,
an optional scaffold/reference, and the effective nonsecret configuration
appended to `config/defaults.env`. The per-run scripts refuse to run anywhere
but inside such a copy.

`study-materialization.json` records:

- study/condition identities and the resolved condition;
- completion threshold;
- source-harness version;
- rendered asset settings and effective configuration.

The materialization is retained so resume and post-hoc evaluation use the same
frozen environment.

## `runs/<run-id>/study-metadata.json`

Run-level copy of the resolved study metadata plus the materialization path. It
is the discovery key used by `study.py resume/evaluate/report` and the aggregate
reporter.

## `runs/<run-id>/study-control/`

Compact immutable review set:

- resolved materialization record;
- rendered prompts and specification delivery;
- candidate adapter;
- visible and hidden manifests.

## Additional extension events

`artifacts/extension-events.jsonl` may include:

- `test_visible_start`, `test_visible_end`, or
  `test_visible_unavailable`;
- `reference_oracle_start`, `reference_oracle_end`,
  `reference_oracle_unavailable`, and limit events;
- `session_before_compact`, `session_compact` and `provider_response_error`;
- pushed-report events (`test_pushed_start`, `test_pushed_end`,
  `test_pushed_error`);
- `study_scaffold_applied`;
- the repair extensions' events, which every condition logs (listed in
  [DATA_DICTIONARY.md](DATA_DICTIONARY.md)).

Oracle source programs and observations are retained under
`artifacts/oracle-queries/`. Their count is tracked in `oracle-count.json`.

## Aggregate outputs

`runs/study-results/<study-id>/` contains:

- `runs.csv`: one row per eligible primary-analysis run;
- `conditions.csv`: primary median/finish-rate summary by condition;
- `paired-baseline-deltas.csv`: replicate-matched differences from baseline;
- `summary.json`: complete machine-readable aggregate;
- `summary.md`: compact human-readable table and interpretation warnings.

Primary rows require `profile=main`, `status=completed`,
`protocol_comparable=true`, a positive integer `replicate`, a matching study ID,
and a frozen condition matching the current resolved condition. Pilot, resumed, incomplete, stale, or internally
inconsistent runs appear in `warnings` and the Markdown exclusion section.
Duplicate eligible `(condition_id, replicate)` records stop aggregation.

Before inclusion, the reporter checks runtime model/image/configuration and
every hidden snapshot's Git commit and tree. The hidden report, score ledger, full evaluator files, and
frozen manifest selection must agree for every round. Passed/failed totals and
macro/micro scores are recomputed from the per-test results (booleans, or the
SQL scorer's fractional per-script `score`). Raw Pi-event
usage and guard ledgers must also reproduce the report. Shared model, image, version, or test-count drift across the batch stops
aggregation.

Important run columns include `profile`, `replicate`, study/condition IDs,
model/provider/thinking/revision, image,
condition axes, hidden score/AUC, finish status, time-to-completion, elapsed time,
tokens, model/tool/test/oracle calls, compactions, regressions, buildability,
guard events (blocked calls and, from v6, bash commands cut by the default
timeout), source/test/scaffold LOC, and final build/audit status. Missing
provider token fields remain null. A complete one-snapshot early stop receives
the origin-anchored AUC `score / 2`.

`summary.json.selection` records the primary inclusion and integrity policy.
Warnings enumerate excluded runs, every missing condition/replicate cell over the included replicate union, and variants without an eligible same-replicate baseline; paired
deltas never disappear silently.

## Task studies (chapters 1-18 compiler, SQL engine)

Added 2026-09-16; absent from earlier runs.

- `study-materialization.json.task` / `evaluator/task.json` / `study-control/task.json`: `{id, runtime, max_stage, parameters}`. `runtime` is `c-compiler` or `sql-engine`; `parameters.sqlite_version` and `parameters.script_timeout_seconds` for the SQL task. Conditions without a `task` block are the chapters 1-10 compiler task.
- Partition manifest rows (`data/partitions-c18`): optional `fixtures` (`[{relative_path, kind}]`, kind `c` | `assembly` | `header`) and `link_flags` (`["-lm"]`); evaluator-side only.
- Partition manifest rows (`data/partitions-sql`): `validity` is always `valid`; `script` holds record counts and, when built with `--verify-sqlite`, `host_sqlite_version` and `host_reference_disagreements`.
- SQL evaluator output (`evaluations/*.json`): `task` (`sqlite_version`, `script_timeout_seconds`); per test row `score` (share of scored records passed), `records` (`total`, `passed`, `failed`, `executed`, `setup_failures`, `blocks`, `reference_disagreements`), `failures` (first eight failing records with line numbers), `failure_type` in `script_timeout`, `candidate_crash`, `malformed_output`, `wrong_results`, `no_scored_records`, `build_failure`, `source_audit_failure`; `summary.records_total` / `records_passed`; `summary.stages.<n>.valid.score` is the mean script score.
- `summarize_study.py` uses a row's `score` when present (fractional) and `passed` otherwise.
- Selection records: `studies/c18/selection.json`, `studies/sql/selection-record.json` (`scripts/test_sets/pin_selection.py`).

