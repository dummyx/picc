#!/usr/bin/env bash
# Evaluator-only reference-backed candidate: delegates to GCC. It exists to
# test the evaluator pipeline (a candidate that is right by construction on
# valid programs) and would violate the experiment's delegation rule.
set -u
input="$1"; output="$3"
exec gcc -std=c17 -pedantic-errors -Werror -Wno-overflow -O0 -fno-pie -fno-asynchronous-unwind-tables -S -x c "$input" -o "$output"
