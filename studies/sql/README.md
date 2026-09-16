# SQL query engine task (`picc-sql-minimal-v1`)

PiSQL: an in-memory SQL engine whose behaviour must match SQLite on an
explicitly documented subset, evaluated with sqllogictest scripts. Runner,
adapters, snapshots, logging, budgets, and reporting are the existing
harness; only the evaluator runtime (`studies/runtime/sql/`) and the task
block of the study manifest are new.

## What the agent gets

The minimal protocol: an empty product repository, the short behavioral
contract in [task.md](task.md) as the only initial message, blank
`AGENTS.md`/`TASK.md`, `Continue.` as the continuation, Pi's built-in tools,
no benchmark tests, scores, or reference. The contract defines the product
interface, the value rendering, and the SQL subset (SQLite semantics); it
names no architecture and prohibits existing database engines, including
SQLite bindings and Node's `node:sqlite`. The same text is used for every
language condition.

Conditions (`study.json`, one-factor-at-a-time on `candidate`), adapters
under `studies/assets/candidates/sql/`:

| Condition | Candidate adapter | Build gate |
|---|---|---|
| `rust` (baseline) | `studies/assets/candidates/sql/rust-std.json` | `cargo build --release --offline` |
| `python` | `studies/assets/candidates/sql/python-untyped.json` | `python3 -m py_compile`; type checkers withheld by the guard |
| `python-typed` | `studies/assets/candidates/sql/python-typed.json` | `mypy --strict` (pinned in image 0.5) must pass; `# type: ignore` is an advisory audit finding |

The adapters add task prohibitions: the guard blocks `sqlite3` invocations
and imports of SQLite modules in agent shell commands; the source audit
blocks the `sqlite3` Python module, the `node:sqlite` built-in, and
references to `rusqlite`, `libsqlite3`, `better-sqlite3`, `DatabaseSync`,
`duckdb`, `libsql`.

## Product contract (candidate side)

`<entry> INPUT.sql`: statements terminated by `;`, executed in order against
an empty in-memory database. Per statement, on stdout: `ok N` then N rows
(tab-separated columns) or `error MESSAGE`; exit 0 after the whole file.
Values: `NULL`; integers in decimal; reals in SQLite's text form (`%!.15g`);
text verbatim with `\t \n \r \\` escapes. The full subset is in `task.md`.

## Tests: selection and exclusions

Corpus: the SQLite sqllogictest suite, git mirror
`gregrahn/sqllogictest` pinned at `SQLLOGICTEST_REF`
(`c67f97bf3ca7e590d12e073408bcacaf2ff0f3a0`). Only the scripts named in
[selection.json](selection.json) are fetched (sparse checkout). Each script
is one test case, copied complete with its setup statements; scripts are
grouped into eight stages by family and split 70/30 with the corpus's
family-grouped, stage-stratified policy (`SQL_SPLIT_SEED=20260916`, each
script its own family). The realized selection is committed in
[selection-record.json](selection-record.json) (30 scripts: 22 visible, 8
hidden, one hidden script per stage) and `make tests-sql` refuses partitions
that differ from it.

| Stage | Family | Scripts | Covers |
|---|---|---|---|
| 1 | evidence-in | `evidence/in1`, `in2` | IN / NOT IN, empty lists, subqueries, NULL |
| 2 | select-single-table | `select1`-`select3` | expressions, CASE, correlated subqueries, aggregates, ORDER BY |
| 3 | select-multi-table | `select4`, `select5` | comma joins, UNION/UNION ALL/INTERSECT/EXCEPT, IN subqueries, text |
| 4 | random-expr | `random/expr/slt_good_0-4` | arithmetic, CAST, COALESCE, NULLIF, CASE, BETWEEN |
| 5 | random-select | `random/select/slt_good_0-4` | CROSS JOIN, DISTINCT, IS NULL |
| 6 | random-aggregates | `random/aggregates/slt_good_0-4` | COUNT/SUM/MIN/MAX/AVG, DISTINCT |
| 7 | random-groupby | `random/groupby/slt_good_0-4` | GROUP BY, HAVING |
| 8 | index-orderby-nosort | `index/orderby_nosort/10/slt_good_0-2` | ORDER BY ASC/DESC, order-sensitive, real and text columns |

Excluded (see `selection.json`): the `evidence/slt_lang_*` scripts (views,
triggers, indexes, REINDEX, REPLACE, UPDATE, DROP, `total()`,
`group_concat()`), the other `index/*` families (DELETE-heavy or
order-insensitive), and the remaining random/orderby files (same generators;
capped to bound per-round evaluation time: about 10k records per script).
Records conditioned on other engines (`onlyif mysql`, `skipif sqlite`, ...)
are skipped exactly as the reference runner skips them. Persistence,
concurrency, and performance are out of scope; the only performance
requirement is the per-script timeout (`script_timeout_seconds`, 120 s; the
reference candidate needs at most 1.5 s per script).

## Evaluation and scoring

`studies/runtime/sql/evaluate.py` with `sqllogictest.py`, which reproduces
the reference runner's rules (`sqllogictest.c`, `slt_sqlite.c` at the pinned
revision): comment and blank-line handling, `skipif`/`onlyif`, `halt`,
`hash-threshold` (default 8), the `T`/`I`/`R` value rendering (`(empty)`,
`@` for non-printable bytes, C `int` truncation, `%.3f`), `nosort`/`rowsort`/
`valuesort` byte-order sorting, `N values hashing to <md5>`, and label
agreement. The candidate's printed values are converted with the same rules.

The pinned SQLite is the `sqlite3` library of the pinned image's `python3`
(`SQLITE_VERSION=3.40.1`, frozen in each materialization's
`evaluator/task.json`); the evaluator refuses to score under any other
version. Before scoring, it re-runs every script through that SQLite and
excludes any record whose expected result it does not reproduce
(`reference_disagreements`; zero for the whole selection under both 3.40.1
and the host's 3.45.1).

Scored records are `query` records and `statement error` records; `statement
ok` records are prerequisites (their failure cascades but earns nothing). A
script's `score` is its share of scored records passed; it `passed` only at
1.0. The stage score is the mean of its scripts' scores; the corpus score
the mean over stages. `summarize_study.py` recomputes this from the
per-script `score` field. No fuzz oracle exists for this task.

## Commands

```bash
make tests-sql                                     # sparse fetch + partitions + check against selection-record.json
make study-validate STUDY=studies/sql/study.json
make study-materialize STUDY=studies/sql/study.json CONDITION=rust RUN_ID=inspect-sql
make study-run STUDY=studies/sql/study.json CONDITION=rust PROFILE=main RUN_ID=sql-rust-r1 REPLICATE=1
make study-hidden-all RUN_ID=sql-rust-r1
make study-report RUN_ID=sql-rust-r1
make study-summary STUDY=studies/sql/study.json    # -> runs/study-results/picc-sql-minimal-v1/
make tasks-smoke                                   # evaluator smoke in the pinned image (Docker)
```

## Evaluator verification (2026-09-16)

Evaluator-only candidates under `fixtures/` (test fixtures, not admissible
experiment candidates):

| Candidate | Hidden (8 scripts, 51 939 records) | Visible (22 scripts, 187 239 records) |
|---|---|---|
| `mock-pisql-sqlite` (delegates to Python `sqlite3`) | 1.0000 | 1.0000 |
| `mock-pisql-reject` (`error` for every statement) | 0.0000 | 0.0102 (only the four `statement error` records) |
| `mock-pisql-constant` (`ok 1` / `0` for every statement) | 0.0503 | 0.0089 |

The same three run in the pinned image through `make tasks-smoke`, which
also checks the SQLite version pin.
