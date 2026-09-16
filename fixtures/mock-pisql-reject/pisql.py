#!/usr/bin/env python3
"""Evaluator-only deliberately wrong candidate: reports an error for every statement."""
import sys


def count_statements(text):
    count, quote, pending = 0, None, False
    for ch in text:
        if quote:
            if ch == quote:
                quote = None
            continue
        if ch in ("'", '"'):
            quote = ch
            pending = True
        elif ch == ";":
            if pending:
                count += 1
            pending = False
        elif not ch.isspace():
            pending = True
    return count + (1 if pending else 0)


script = open(sys.argv[1], encoding="utf-8", errors="replace").read()
for _ in range(count_statements(script)):
    sys.stdout.write("error unsupported statement\n")
