Implement PiSQL in {{LANGUAGE}} using only the standard library.
Build with `{{BUILD_COMMAND}}`; invoke as `{{ENTRY_COMMAND}}`.

PiSQL is an in-memory SQL engine whose observable behaviour matches SQLite
on the subset below. The input file holds SQL statements, each terminated by
`;`. Execute them in order against a database that starts empty and print,
for each statement, one block on standard output: `ok N` followed by the N
result rows (one row per line, column values separated by one tab), or
`error MESSAGE` on one line when the statement is rejected. A statement that
returns no rows prints `ok 0`. Continue after an error and exit 0 once the
whole file has been processed. Values print as `NULL` for NULL, decimal for
integers, SQLite's text form for reals (up to 15 significant digits, always
with a decimal point or exponent, e.g. `2.5`, `3.0`, `1.0e+20`), and text
verbatim with tab, newline, carriage return, and backslash written as `\t`,
`\n`, `\r`, `\\`.

PiSQL is started as `{{ENTRY_COMMAND}}`: it reads that one file and nothing
from standard input, and every statement, `CREATE TABLE` and `INSERT`
included, prints exactly one block. For example, an input file containing

    CREATE TABLE t(a INTEGER, b TEXT, c REAL);
    INSERT INTO t VALUES(1, 'x', 2.5);
    INSERT INTO t VALUES(2, NULL, 3);
    SELECT a, b, c FROM t ORDER BY a DESC;
    SELECT COUNT(*), SUM(a) FROM t WHERE c > 1;
    SELECT a FROM missing;
    SELECT 'done';

must produce exactly this output, the values of a row separated by one tab
character (the text of an error message is free):

    ok 0
    ok 0
    ok 0
    ok 2
    2	NULL	3.0
    1	x	2.5
    ok 1
    2	3
    error no such table: missing
    ok 1
    done

Subset, with SQLite semantics: `CREATE TABLE` with column names, optional
declared types (`INTEGER`, `FLOAT`/`REAL`, `TEXT`/`VARCHAR(n)`, applying
SQLite's type affinity) and `PRIMARY KEY`, `UNIQUE`, `NOT NULL` constraints;
`CREATE INDEX` (accepted, no observable effect); `INSERT INTO t [(cols)]
VALUES (...)` and `INSERT INTO t SELECT ...`; values of storage class NULL,
64-bit INTEGER, REAL, TEXT, and BLOB literals `x'..'`, compared and ordered
as SQLite does (NULL, then numbers, then text, then blobs), integer
arithmetic that overflows to REAL, integer `/` and `%` with NULL on division
by zero; operators `+ - * /`, comparisons `= == != <> < <= > >=`,
`AND`/`OR`/`NOT` with three-valued logic, `IS NULL`/`IS NOT NULL`,
`BETWEEN`, `IN`/`NOT IN` with a value list (possibly empty), a subquery, or a
table name, `EXISTS`, `CASE`, `CAST(... AS INTEGER|REAL|TEXT)`, `COALESCE`,
`NULLIF`, `ABS`; `SELECT` with `ALL`/`DISTINCT`, `*`, `t.*`, expressions and
aliases, `FROM` with comma-separated and `CROSS JOIN` tables and aliases,
`WHERE`, `GROUP BY` with `HAVING`, the aggregates `COUNT(*)`, `COUNT`,
`SUM`, `AVG`, `MIN`, `MAX` (with `DISTINCT`), scalar and correlated
subqueries, `ORDER BY` with expressions or positional references and
`ASC`/`DESC`, and `UNION`, `UNION ALL`, `INTERSECT`, `EXCEPT`. Without
`ORDER BY`, rows come in insertion order, and joined tables are combined
left to right with the leftmost table outermost. Malformed statements,
unknown tables or columns, and multi-column expressions where one value is
required are errors.

Work in `/workspace`, offline. The repository is scored exactly as it stands
when a fixed time budget ends (two hours for a full run), in whatever state it
is in, so keep the program building and behaving correctly at all times. Do
not access harness internals or modify experiment-control files. The engine must implement SQL itself, without
existing database engines or libraries (including SQLite bindings and
Node's `node:sqlite`), subprocesses, or hard-coded test answers.
