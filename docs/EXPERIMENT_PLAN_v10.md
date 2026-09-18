# Experiment plan: v10 batch (new tasks; Python untyped vs typed)

Status: frozen by the commit that adds this section (harness at `bd3f686`),
2026-09-16 15:11 UTC, immediately before the first main run (chain started 15:11:27 UTC). Pilot evidence below.

## Study identity

- Studies: `studies/c18/study.json` (`picc-c18-minimal-v1`) and
  `studies/sql/study.json` (`picc-sql-minimal-v1`), seed 20260916, analyzed
  and reported separately.
- Harness: task infrastructure `e02c8b7`, typed-Python condition and image
  0.5 `bd3f686`. Image `picc-experiment:0.5` `sha256:9fb66bd28dcf036578e244e5e6c1df5392a793cfb46379e099be1667961da6ed` = image 0.4
  plus mypy 2.3.1 in `/opt/mypy`; Pi 0.85.1; `@cad0p/pi-bash-timeout@0.1.0`;
  Rust 1.88.0; SQLite 3.40.1 (image python3).
- Provider/model as in v7-v9: `local`, llama.cpp serving
  `unsloth/Qwen3.8-27B-GGUF:UD-Q4_K_XL` (GGUF SHA-256 `3f227079…`, verified by
  `make preflight` before each slot), thinking `high`, sampling pinned,
  `LOCAL_MAX_OUTPUT=65536`.
- Test selections: `studies/c18/selection.json` (668 visible / 281 hidden,
  upstream `ae12014d…`), `studies/sql/selection-record.json` (22 / 8,
  sqllogictest mirror `c67f97bf…`). `make tests-c18 tests-sql` refuses drift.

## Research question

On each task, does requiring static typing (Python under `mypy --strict` as
the build gate) change hidden behavioral correctness relative to plain
Python, under the minimal protocol? The `rust` condition is the task
baseline for the study design and gives the feasibility floor for a
compiled language; it is not part of the typing contrast.

## Conditions

Per study, one-factor-at-a-time on `candidate`:

| Condition | Adapter | Build gate |
|---|---|---|
| `rust` (baseline) | `rust-std.json` | `cargo build --release --offline` |
| `python` | `python-untyped.json` | `python3 -m py_compile`; type checkers withheld by the guard |
| `python-typed` | `python-typed.json` | `mypy --strict --no-error-summary --cache-dir /tmp/mypy-cache <entry>` |

Everything else is identical across arms: the contract text (language line
and build command substituted), blank `AGENTS.md`/`TASK.md`, `Continue.`,
built-in tools only, no tests, scores, or reference exposed. The adapters'
`agent_notes` are not rendered under the minimal protocol, so the typed
arm's only instruction to annotate is the build command itself.

## Planned runs

- 3 replicates per condition per study: 18 main runs, `PROFILE=main`
  (`MAIN_HOURS=2`, 45-minute round cap, 30 rounds, carried over from v6-v9;
  c18 stages 1-18, SQL stages 1-8).
- Order: `make study-schedule` with seed 20260916, run ids
  `v10-<task>-<condition>-r<n>`; the SQL study runs first, then c18:
  1. `v10-sql-python-r1` 2. `v10-sql-rust-r1` 3. `v10-sql-python-typed-r1`
  4. `v10-sql-python-typed-r2` 5. `v10-sql-rust-r2` 6. `v10-sql-python-r2`
  7. `v10-sql-python-r3` 8. `v10-sql-rust-r3` 9. `v10-sql-python-typed-r3`
  10. `v10-c18-python-r1` 11. `v10-c18-rust-r1` 12. `v10-c18-python-typed-r1`
  13. `v10-c18-python-typed-r2` 14. `v10-c18-rust-r2` 15. `v10-c18-python-r2`
  16. `v10-c18-python-r3` 17. `v10-c18-rust-r3` 18. `v10-c18-python-typed-r3`
- Chain: `scripts/chain_study.sh` per study (preflight, run,
  `study-hidden-all`, `study-report`; `study-summary` at the end), run
  sequentially and unattended.
- Pilots (excluded from every analysis): `v10-pilot-sql-python-typed` and
  `v10-pilot-c18-python`, pilot profile 0.4 h / 12-minute cap / 2 rounds.

## Primary endpoint

Hidden corpus macro score on the last buildable snapshot (final snapshot as
co-primary), per study. Neither task has a fuzz oracle. The typing contrast
is `python-typed` minus `python`, paired by replicate: per-replicate deltas
and their median, no threshold claimed at n = 3 (v7's 0.13 is quoted for
scale only). The c18 metric counts invalid-program rejection, so
reject-everything scores 0.50 there; evaluator floors from the fixture
candidates are c18 constant-output 0.21, SQL constant-output 0.05.

## Secondary endpoints

Per-stage hidden pass rates; visible-score trajectory; rounds used; guard
blocks (in particular type-checker blocks in `python`); build failures per
snapshot (mypy rejections in `python-typed`); source lines; annotation share
(`analysis/typing_metrics.py` adapted if needed); whether the agent wrote
its own tests.

## Interpretation rule

Descriptive at this size. A task is called feasible for a condition when at
least two of three replicates end above the constant-output floor with a
nonzero valid-program pass rate. The typing delta is reported with its
per-replicate signs; a claim of an effect requires all three replicates to
agree in sign and the median to exceed 0.13.

## Exclusion rules

As in v9: pilots, resumed runs, and runs whose frozen condition no longer
matches the manifest are excluded and listed; duplicate cells are errors.

## Human intervention policy

None during a run. Defects found mid-batch become numbered amendments here
and fixes for the next manifest version.

## Analysis

`make study-summary` per study, then `python3 analysis/v10_results.py`
(committed before the first main run).

## Pilot evidence

Both pilots ran on image 0.5 (`sha256:9fb66bd2…`) through `make study-run`,
`study-hidden-all`, and `study-report`, 2026-09-16 14:22-15:10 UTC:

- `v10-pilot-sql-python-typed` (SQL, typed Python): 2 rounds, both cut at
  the 12-minute pilot cap (`round_timeout`), status `completed`. Round 0 was
  thinking only (no tool call); round 1 made 19 tool calls (`bash`, `read`,
  `write`) and left `microdb/{lexer,parser,ast_nodes,values}.py` without the
  `pisql.py` entry, so both snapshots are `build_failure` with mypy's
  "Cannot read file 'pisql.py'" as the detail. Visible (22 scripts) and
  hidden (8) evaluations ran in seconds; the ledger holds one hidden row per
  snapshot; the guard blocked two commands (environment inspection; an
  attempt to use an existing database engine).
- `v10-pilot-c18-python` (chapters 1-18, plain Python, stages 1-3): 2 rounds,
  both cut at the cap; 3 tool calls in round 0, none in round 1; empty
  workspace; visible (48 tests) and hidden (18) evaluations recorded as
  `build_failure`; no guard blocks.

Infrastructure evidence only: the pipeline (materialization with
`task.json`, agent container on image 0.5, snapshots, both evaluators,
ledgers, reports) works end to end for both tasks and the typed gate. The
whole-round thinking at a 12-minute cap is the known long-think behaviour;
main rounds are capped at 45 minutes.

## Amendments

### Amendment 1 (2026-09-16 20:35 UTC, during run 3 of 18): context-overflow recovery failure; no configuration change

Observation, recorded before any result of the affected run was analyzed.
Runs 1 and 2 (`v10-sql-python-r1`, `v10-sql-rust-r1`) worked in ordinary
short assistant turns (112 and 169 tool calls in their second rounds) and
were ended by the frozen stall rule (`MAX_CONSECUTIVE_ROUND_TIMEOUTS=2`)
after two consecutive 45-minute rounds, at 91 minutes of the 2-hour budget.
Run 3 (`v10-sql-python-typed-r1`) instead produced thinking blocks that hit
the 65,536-token output cap (`stopReason=length`) in each of its first three
rounds with 0, 5, and 0 tool calls, then Pi's context-overflow compaction
failed in every later round ("Summarization failed: 400: request (176392
tokens) exceeds the context"), after which each round yields a ~14k-token
truncated thinking block, no tool call, and no file. The run keeps
consuming its wall budget in such rounds.

Both behaviours are consequences of the frozen configuration (thinking
`high`, 131,072 context, `LOCAL_MAX_OUTPUT=65536`, the stall rule, Pi
0.85.1 compaction) applied identically to every condition. Nothing is
changed for this batch. Consequences for analysis: (1) effective budgets
are heterogeneous, 91 minutes for runs ended by the stall rule versus up to
2 hours for runs that yield short turns; elapsed time and round counts are
reported per run; (2) a run that enters the overflow mode is included as a
completed run and scored on its last buildable snapshot (0 when none
exists); the report lists per run whether compaction failed
(`compaction_end` events with `errorMessage`) and how many rounds ended
with `stopReason=length`. A fix for the next manifest version is left to
the report (candidates: treat a failed overflow recovery as terminal, or a
lower thinking level).

### Amendment 2 (2026-09-17 02:00 UTC, after run 6 of 18): workspace-wide Python audit zeroes a run for its own test driver; post-hoc re-score

Observation. `v10-sql-python-r2` built a 3,060-line `pisql.py` (212 tool
calls in round 1) and eight SQL test scripts with a driver
`tests/run_tests.py` that spawns the candidate with `subprocess`. The
Python source audit scans the whole workspace (a documented limitation:
Rust and Node audits were scoped to the built artifact after the v4 and v6
incidents, `analysis/report.md` §8.5 and §12; Python was not), so every
snapshot from round 1 on is `source_audit_failure` and the run scores 0 on
both partitions although the product itself contains no prohibited code
(`pisql.py` has no finding; the two blocking findings are in
`tests/run_tests.py`).

Decision. The materialized evaluators of this batch are not touched, so
runs 7-18 are scored exactly like runs 1-6. After the last run, the Python
audit is scoped to the entry module's import closure (the Node rule) in
the repository evaluator, and every v10 run is re-scored with it on the
hidden partition under `analysis/v10-rescore/`, following the re-score
procedure of `docs/STUDY_PROTOCOL.md`; the report presents the re-scored
values as primary and the frozen ledgers alongside. Same class of defect
as v6 Amendment 2 and v9 Amendment 2.
