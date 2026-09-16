#!/usr/bin/env python3
"""sqllogictest script parsing and result comparison for the PiSQL task.

The rules here reproduce the reference runner (`sqllogictest.c` and
`slt_sqlite.c` at the pinned sqllogictest revision):

* A script is a sequence of records separated by blank lines.  Lines whose
  first character is ``#`` are comments everywhere, a trailing ``\\r`` is
  dropped, and an all-whitespace line is blank.
* ``skipif <db>`` / ``onlyif <db>`` lines before a record skip it for the
  named engine; this evaluator is ``sqlite``.
* ``statement ok`` / ``statement error`` records must succeed / fail.
* ``query <types> [nosort|rowsort|valuesort] [label]`` records run one query.
  Each result value is rendered by its type letter (``T`` text with ``(empty)``
  for the empty string and ``@`` for bytes outside ``' '``..``'~'``; ``I`` the
  value as a C ``int``; ``R`` the value as ``%.3f``), NULL always renders as
  ``NULL``, rows are flattened row-major, sorted per the mode by byte order,
  and compared with the expected lines.  When a ``hash-threshold N`` is in
  force and more than N values result, the expected line is
  ``<count> values hashing to <md5>`` where the MD5 covers every value
  followed by a newline.  Results sharing a label (first 20 characters) must
  agree with each other.
* ``halt`` stops the script.

Two producers feed the comparison: the candidate's output stream (its own
line protocol, see ``parse_candidate_output``) and the pinned SQLite through
Python's ``sqlite3`` module (``SQLiteReference``), which verifies that the
script's expected results still hold under the evaluator's SQLite so a
disagreement is never charged to the candidate.
"""

from __future__ import annotations

import hashlib
import math
import re
import sqlite3
from dataclasses import dataclass, field
from typing import Any, Iterable, Sequence

DB_ENGINE = "sqlite"
LABEL_LIMIT = 20
# The reference runner's DEFAULT_HASH_THRESHOLD: in force until a
# `hash-threshold` record changes it (select1.test relies on the default).
DEFAULT_HASH_THRESHOLD = 8
INT32_MIN, INT32_MAX = -(1 << 31), (1 << 31) - 1
INT64_MIN, INT64_MAX = -(1 << 63), (1 << 63) - 1
NUMERIC_PREFIX = re.compile(r"\s*([-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?)")
INTEGER_TOKEN = re.compile(r"[-+]?\d+")
HASH_LINE = re.compile(r"^\d+ values hashing to ([0-9a-fA-F]{32})$")


@dataclass
class Record:
    kind: str  # "statement", "query", "halt", "hash-threshold", "invalid"
    line: int
    conditions: list[tuple[str, str]] = field(default_factory=list)
    sql: str = ""
    expect: str = ""  # statement: "ok" | "error"
    types: str = ""
    sort: str = "nosort"
    label: str = ""
    expected: list[str] = field(default_factory=list)
    threshold: int = 0
    detail: str = ""

    @property
    def skipped(self) -> bool:
        for keyword, engine in self.conditions:
            matches = engine.lower() == DB_ENGINE
            if keyword == "skipif" and matches:
                return True
            if keyword == "onlyif" and not matches:
                return True
        return False


def _script_lines(text: str) -> list[tuple[int, str]]:
    """Lines as the reference reader sees them: numbered, comment lines
    removed, ``\\r`` stripped, whitespace-only lines emptied."""
    lines: list[tuple[int, str]] = []
    for number, raw in enumerate(text.split("\n"), 1):
        line = raw[:-1] if raw.endswith("\r") else raw
        if not line.strip():
            line = ""
        if line.startswith("#"):
            continue
        lines.append((number, line))
    return lines


def parse_script(text: str) -> list[Record]:
    lines = _script_lines(text)
    records: list[Record] = []
    index = 0
    total = len(lines)
    while index < total:
        number, line = lines[index]
        if not line:
            index += 1
            continue
        conditions: list[tuple[str, str]] = []
        tokens = line.split()
        while tokens and tokens[0] in ("skipif", "onlyif"):
            conditions.append((tokens[0], tokens[1] if len(tokens) > 1 else ""))
            index += 1
            if index >= total or not lines[index][1]:
                tokens = []
                break
            number, line = lines[index]
            tokens = line.split()
        if not tokens:
            records.append(Record("invalid", number, conditions, detail="conditions without a record"))
            continue
        record = Record(tokens[0], number, conditions)
        index += 1
        if tokens[0] == "statement":
            record.expect = tokens[1] if len(tokens) > 1 else ""
            sql_lines: list[str] = []
            while index < total and lines[index][1]:
                sql_lines.append(lines[index][1])
                index += 1
            record.sql = "\n".join(sql_lines)
            if record.expect not in ("ok", "error"):
                record.kind, record.detail = "invalid", f"statement expects {record.expect!r}"
        elif tokens[0] == "query":
            record.types = tokens[1] if len(tokens) > 1 else ""
            record.sort = tokens[2] if len(tokens) > 2 and tokens[2] else "nosort"
            record.label = tokens[3][:LABEL_LIMIT] if len(tokens) > 3 else ""
            sql_lines = []
            while index < total and lines[index][1] and lines[index][1] != "----":
                sql_lines.append(lines[index][1])
                index += 1
            record.sql = "\n".join(sql_lines)
            if index < total and lines[index][1] == "----":
                index += 1
                while index < total and lines[index][1]:
                    record.expected.append(lines[index][1])
                    index += 1
            if not record.types or any(ch not in "TIR" for ch in record.types):
                record.kind, record.detail = "invalid", f"bad type string {record.types!r}"
            elif record.sort not in ("nosort", "rowsort", "valuesort"):
                record.kind, record.detail = "invalid", f"unknown sort method {record.sort!r}"
        elif tokens[0] == "hash-threshold":
            try:
                record.threshold = int(tokens[1])
            except (IndexError, ValueError):
                record.kind, record.detail = "invalid", "hash-threshold needs an integer"
        elif tokens[0] == "halt":
            pass
        else:
            record.kind, record.detail = "invalid", f"unknown record type {tokens[0]!r}"
        # Skip anything else in this record (the reference reader does the same).
        while index < total and lines[index][1]:
            index += 1
        records.append(record)
    return records


# --- value rendering ---------------------------------------------------------


def wrap_int32(value: int) -> int:
    return ((value + (1 << 31)) % (1 << 32)) - (1 << 31)


def double_to_int64(value: float) -> int:
    """SQLite's doubleToInt64: saturate outside the int64 range."""
    if value != value:  # NaN
        return 0
    if value <= INT64_MIN:
        return INT64_MIN
    if value >= INT64_MAX:
        return INT64_MAX
    return int(value)


def text_to_number(text: str) -> int | float:
    """Numeric prefix of a text, as SQLite's text-to-number conversion sees it
    (leading whitespace and sign allowed; no numeric prefix yields 0)."""
    match = NUMERIC_PREFIX.match(text)
    if not match:
        return 0
    token = match.group(1)
    if INTEGER_TOKEN.fullmatch(token):
        number = int(token)
        return max(INT64_MIN, min(INT64_MAX, number))
    try:
        return float(token)
    except ValueError:
        return 0


def as_c_int(value: Any) -> int:
    """sqlite3_column_int: int64 value truncated to a C int."""
    if isinstance(value, bool):
        value = int(value)
    if isinstance(value, int):
        return wrap_int32(max(INT64_MIN, min(INT64_MAX, value)))
    if isinstance(value, float):
        return wrap_int32(double_to_int64(value))
    if isinstance(value, bytes):
        value = value.decode("latin-1")
    number = text_to_number(str(value))
    return as_c_int(number)


def as_double(value: Any) -> float:
    if isinstance(value, bool):
        value = int(value)
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, bytes):
        value = value.decode("latin-1")
    return float(text_to_number(str(value)))


def sqlite_real_text(value: float) -> str:
    """SQLite's ``%!.15g`` rendering of a REAL (its text conversion)."""
    if value != value:
        return "NULL"
    if math.isinf(value):
        return "Inf" if value > 0 else "-Inf"
    text = "%.15g" % value
    if "e" in text:
        mantissa, exponent = text.split("e", 1)
        if "." not in mantissa:
            mantissa += ".0"
        return f"{mantissa}e{exponent}"
    if "." not in text:
        text += ".0"
    return text


def printable(text_bytes: bytes) -> str:
    """The T rule on raw bytes: everything outside ' '..'~' becomes '@'."""
    return "".join(chr(b) if 32 <= b <= 126 else "@" for b in text_bytes)


def render_typed(value: Any, type_char: str) -> str:
    """Render one SQLite value (Python's sqlite3 representation) by its type letter."""
    if value is None:
        return "NULL"
    if type_char == "I":
        return str(as_c_int(value))
    if type_char == "R":
        return "%.3f" % as_double(value)
    if isinstance(value, bytes):
        raw = value
    elif isinstance(value, bool):
        raw = str(int(value)).encode()
    elif isinstance(value, int):
        raw = str(value).encode()
    elif isinstance(value, float):
        raw = sqlite_real_text(value).encode()
    else:
        raw = str(value).encode("utf-8", errors="replace")
    if not raw:
        return "(empty)"
    return printable(raw)


def render_candidate_token(token: str, type_char: str) -> str:
    """Render one value from the candidate's textual protocol by its type letter.

    The candidate prints NULL as ``NULL``, integers in decimal, reals like
    SQLite's text conversion, and text verbatim (escaped); the numeric rules
    below parse the text back the way SQLite converts a value of that text.
    """
    if token == "NULL":
        return "NULL"
    if type_char == "I":
        return str(as_c_int(text_to_number(token)))
    if type_char == "R":
        return "%.3f" % float(text_to_number(token))
    raw = token.encode("latin-1", errors="replace")
    if not raw:
        return "(empty)"
    return printable(raw)


# --- comparison ----------------------------------------------------------------


def sort_values(values: list[str], mode: str, columns: int) -> list[str]:
    if mode == "rowsort" and columns > 0:
        rows = [values[i : i + columns] for i in range(0, len(values), columns)]
        rows.sort(key=lambda row: [item.encode("latin-1", errors="replace") for item in row])
        return [item for row in rows for item in row]
    if mode == "valuesort":
        return sorted(values, key=lambda item: item.encode("latin-1", errors="replace"))
    return list(values)


def md5_of_values(values: Sequence[str]) -> str:
    digest = hashlib.md5()
    for value in values:
        digest.update(value.encode("latin-1", errors="replace"))
        digest.update(b"\n")
    return digest.hexdigest()


def hash_line(values: Sequence[str]) -> str:
    return f"{len(values)} values hashing to {md5_of_values(values)}"


def expected_hash(expected: Sequence[str]) -> str:
    """The MD5 the reference runner associates with an expected block (the
    literal hash when the block is a hash line, else the hash of its lines)."""
    if len(expected) == 1:
        match = HASH_LINE.match(expected[0])
        if match:
            return match.group(1).lower()
    return md5_of_values(expected)


class LabelRegistry:
    """Results sharing a label must agree (the reference runner's checkValue)."""

    def __init__(self) -> None:
        self.hashes: dict[str, str] = {}

    def check(self, label: str, digest: str) -> bool:
        if not label:
            return True
        previous = self.hashes.setdefault(label, digest)
        return previous == digest


def compare_query(
    record: Record,
    values: list[str] | None,
    threshold: int,
    labels: LabelRegistry,
) -> tuple[bool, str | None]:
    """Compare rendered values against the record's expected block.

    ``values`` is None when the query failed.  Returns (passed, detail).
    """
    if values is None:
        return False, "query failed"
    columns = len(record.types)
    if columns and len(values) % columns != 0:
        return False, f"result has {len(values)} values, not a multiple of {columns} columns"
    ordered = sort_values(values, record.sort, columns)
    digest = md5_of_values(ordered)
    label_ok = labels.check(record.label, digest)
    if threshold > 0 and len(ordered) > threshold:
        actual = hash_line(ordered)
        if record.expected != [actual]:
            return False, f"wrong result hash: expected {record.expected[:1]!r} got {actual!r}"
    else:
        if ordered != record.expected:
            if len(ordered) != len(record.expected):
                return False, f"expected {len(record.expected)} values, got {len(ordered)}"
            for index, (want, got) in enumerate(zip(record.expected, ordered, strict=True)):
                if want != got:
                    return False, f"value {index}: expected {want!r} got {got!r}"
    if not label_ok:
        return False, f"labeled result [{record.label}] does not agree with previous values"
    return True, None


# --- candidate protocol ---------------------------------------------------------

_UNESCAPE = {"\\": "\\", "t": "\t", "n": "\n", "r": "\r"}


def unescape_value(token: str) -> str:
    if "\\" not in token:
        return token
    out: list[str] = []
    i = 0
    while i < len(token):
        ch = token[i]
        if ch == "\\" and i + 1 < len(token) and token[i + 1] in _UNESCAPE:
            out.append(_UNESCAPE[token[i + 1]])
            i += 2
        else:
            out.append(ch)
            i += 1
    return "".join(out)


@dataclass
class Block:
    ok: bool
    rows: list[list[str]] = field(default_factory=list)
    message: str = ""
    malformed: str | None = None


def parse_candidate_output(text: str) -> tuple[list[Block], str | None]:
    """Parse the candidate's per-statement blocks.

    Protocol: for each statement in order, ``ok <N>`` followed by N rows
    (columns separated by one tab; ``\\t``, ``\\n``, ``\\r`` and ``\\\\`` are
    escapes), or ``error <message>``.  Parsing stops at the first malformed
    line; the blocks read so far stand and the remaining statements have no
    block (they fail).
    """
    lines = text.split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    blocks: list[Block] = []
    index = 0
    while index < len(lines):
        line = lines[index][:-1] if lines[index].endswith("\r") else lines[index]
        index += 1
        if line.startswith("error"):
            if line != "error" and not line.startswith("error "):
                return blocks, f"line {index}: malformed block header {line[:80]!r}"
            blocks.append(Block(False, message=line[6:]))
            continue
        head = line.split(" ")
        if len(head) != 2 or head[0] != "ok" or not head[1].isdigit():
            return blocks, f"line {index}: malformed block header {line[:80]!r}"
        count = int(head[1])
        if index + count > len(lines):
            return blocks, f"line {index}: block announces {count} rows but the output ends early"
        rows = []
        for row_line in lines[index : index + count]:
            row_line = row_line[:-1] if row_line.endswith("\r") else row_line
            rows.append([unescape_value(cell) for cell in row_line.split("\t")])
        index += count
        blocks.append(Block(True, rows=rows))
    return blocks, None


def statements_of(records: Iterable[Record]) -> list[Record]:
    """The records the candidate must execute, in order: every non-skipped
    statement or query up to a non-skipped halt."""
    executed: list[Record] = []
    for record in records:
        if record.skipped or record.kind in ("hash-threshold", "invalid"):
            continue
        if record.kind == "halt":
            break
        executed.append(record)
    return executed


def script_input(records: Sequence[Record]) -> str:
    """The SQL script handed to the candidate: one statement per record,
    terminated by a semicolon, blank-line separated.  Records already ending
    in a semicolon are not double-terminated."""
    parts = []
    for record in records:
        sql = record.sql.rstrip()
        if not sql.endswith(";"):
            sql += ";"
        parts.append(sql)
    return "\n\n".join(parts) + "\n"


# --- pinned SQLite reference -----------------------------------------------------


class SQLiteReference:
    """Runs a script through Python's sqlite3 (the pinned library) and renders
    results with the reference rules, to verify the script's expectations."""

    def __init__(self) -> None:
        self.connection = sqlite3.connect(":memory:", isolation_level=None)
        self.connection.text_factory = lambda raw: raw.decode("utf-8", errors="surrogateescape")

    def close(self) -> None:
        self.connection.close()

    def statement(self, sql: str) -> bool:
        try:
            self.connection.execute(sql)
            return True
        except sqlite3.Error:
            return False

    def query(self, sql: str, types: str) -> list[str] | None:
        try:
            cursor = self.connection.execute(sql)
            rows = cursor.fetchall()
        except sqlite3.Error:
            return None
        if cursor.description is None or len(cursor.description) != len(types):
            return None
        values: list[str] = []
        for row in rows:
            for value, type_char in zip(row, types, strict=True):
                if isinstance(value, str):
                    value = value.encode("utf-8", errors="surrogateescape")
                values.append(render_typed(value, type_char))
        return values


def verify_with_sqlite(records: Sequence[Record]) -> dict[str, Any]:
    """Run the script on the pinned SQLite; report records whose expectation
    it does not reproduce.  ``disagreements`` lists record line numbers."""
    reference = SQLiteReference()
    labels = LabelRegistry()
    threshold = DEFAULT_HASH_THRESHOLD
    disagreements: list[dict[str, Any]] = []
    executed = 0
    try:
        for record in records:
            if record.skipped or record.kind == "invalid":
                continue
            if record.kind == "halt":
                break
            if record.kind == "hash-threshold":
                threshold = record.threshold
                continue
            executed += 1
            if record.kind == "statement":
                ok = reference.statement(record.sql)
                if ok != (record.expect == "ok"):
                    disagreements.append({"line": record.line, "detail": f"statement {record.expect} but sqlite {'succeeded' if ok else 'failed'}"})
                continue
            values = reference.query(record.sql, record.types)
            passed, detail = compare_query(record, values, threshold, labels)
            if not passed:
                disagreements.append({"line": record.line, "detail": detail})
    finally:
        reference.close()
    return {
        "sqlite_version": sqlite3.sqlite_version,
        "executed": executed,
        "disagreements": disagreements,
    }
