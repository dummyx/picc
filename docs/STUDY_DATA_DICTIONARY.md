# Controlled-study data dictionary

This document covers the additive study layer. Existing per-run files remain
defined in `docs/DATA_DICTIONARY.md`.

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

## Candidate adapter

`candidate.json` defines:

- `language`, `framework`, and descriptive dependency policy;
- `build.command`, `build.artifact`, and optional timeout;
- `run.command`, with `{artifact}`, `{input}`, `{output}`, and `{workspace}`
  placeholders;
- `source_extensions` used for artifact measurement/audit;
- audit allowlists/patterns; source audit covers Rust, Python, and
  JavaScript/TypeScript files, including test paths, and rejects symlinks.
  `audit.roots` restricts the per-file scan to the compiler's own source
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
  byte-identically to earlier cohorts;
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

The evaluator requires the same external PiCC contract for every adapter.

## Fuzz oracle ledger

`runs/<run-id>/artifacts/fuzz-scores.jsonl` holds exactly one row, written by
the hidden post-hoc evaluation for the final snapshot: `partition` (`fuzz`),
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

Condition-specific copy of the current harness. It contains rendered prompts,
condition-aware extensions, generic evaluator, fuzz-oracle runtime, adapter, visible subset,
constant hidden partition, optional scaffold/reference, and effective nonsecret
configuration.

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
- compaction/provider events inherited from the base extension;
- `study_scaffold_applied`.

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
macro/micro scores are recomputed from per-test boolean results. Raw Pi-event
usage and guard ledgers must also reproduce the report. Shared model, image, version, or test-count drift across the cohort stops
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
