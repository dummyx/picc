Implement PiSQL in {{LANGUAGE}} using only the standard library.
Build with `{{BUILD_COMMAND}}`; invoke as `{{ENTRY_COMMAND}}`; both commands
are run from `/workspace` itself.

PiSQL is an in-memory SQL engine that behaves like SQLite. It reads the one
input file named on its command line (nothing from standard input) and prints
one block per statement on standard output: `ok N` followed by the N result
rows, one per line with the values separated by one tab, or `error MESSAGE`.
It must handle `CREATE TABLE`, `CREATE INDEX`, `INSERT`, and `SELECT` with
expressions, `WHERE`, joins, `GROUP BY`/`HAVING`, aggregates, subqueries,
`ORDER BY`, and `UNION`/`INTERSECT`/`EXCEPT`, with SQLite's NULL and type
rules.

Work in `/workspace`, offline. The repository is scored exactly as it stands
when a fixed time budget ends (two hours for a full run). Do not access
harness internals or modify experiment-control files. The engine must
implement SQL itself, without existing database engines or libraries,
subprocesses, or hard-coded test answers.
