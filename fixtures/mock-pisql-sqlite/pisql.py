#!/usr/bin/env python3
"""Evaluator-only reference-backed PiSQL candidate: delegates to Python's
sqlite3 module and prints the PiSQL block protocol. It tests the evaluator
(right by construction under the pinned SQLite) and would violate the
experiment's delegation rule."""
import sqlite3
import sys


def split_statements(text):
    statements, current, quote, i = [], [], None, 0
    while i < len(text):
        ch = text[i]
        if quote:
            current.append(ch)
            if ch == quote:
                if i + 1 < len(text) and text[i + 1] == quote:
                    current.append(quote)
                    i += 1
                else:
                    quote = None
        elif ch in ("'", '"'):
            quote = ch
            current.append(ch)
        elif ch == "-" and text.startswith("--", i):
            end = text.find("\n", i)
            i = len(text) if end < 0 else end
            continue
        elif ch == ";":
            statement = "".join(current).strip()
            if statement:
                statements.append(statement)
            current = []
        else:
            current.append(ch)
        i += 1
    tail = "".join(current).strip()
    if tail:
        statements.append(tail)
    return statements


def render(value):
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return str(int(value))
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        if value != value:
            return "NULL"
        text = "%.15g" % value
        if "e" in text:
            mantissa, exponent = text.split("e", 1)
            if "." not in mantissa:
                mantissa += ".0"
            return f"{mantissa}e{exponent}"
        return text if "." in text or "inf" in text.lower() else text + ".0"
    if isinstance(value, bytes):
        text = value.decode("latin-1")
    else:
        text = str(value)
    return text.replace("\\", "\\\\").replace("\t", "\\t").replace("\n", "\\n").replace("\r", "\\r")


def main():
    script = open(sys.argv[1], encoding="utf-8", errors="replace").read()
    connection = sqlite3.connect(":memory:", isolation_level=None)
    out = sys.stdout
    for statement in split_statements(script):
        try:
            cursor = connection.execute(statement)
            rows = cursor.fetchall() if cursor.description else []
        except sqlite3.Error as error:
            out.write(f"error {str(error).splitlines()[0] if str(error) else 'error'}\n")
            continue
        out.write(f"ok {len(rows)}\n")
        for row in rows:
            out.write("\t".join(render(v) for v in row) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
