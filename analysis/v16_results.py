#!/usr/bin/env python3
"""v16 batch: does bounding reasoning restore the typed condition?

v15 left one thing unexplained: under `mypy --strict` the agent produced
nothing at all -- zero write or edit calls across 44 rounds -- while 61-64% of
its replies ended on `length`, cut off while still reasoning. Raising the
output cap did not help. v16 runs the same conditions on SGLang with a hard
cap on *reasoning* rather than on the reply.

Endpoints, in the order the plan fixes them:

1. writes -- write and edit calls. The v15 failure is defined by this, and it
   was zero.
2. cut-off rate -- replies ending on `length`.
3. terminated rate -- replies ending on `error`. Not in the original plan; it
   was added after the first v16 run lost 3 of 7 replies to a stream idle
   timeout on buffered tool calls. Zero in every llama.cpp run, so a non-zero
   value here means the fix regressed and the run is not comparable.
4. produced a working engine, then hidden score among those that did.

Read-only over runs/.

    make study-summary STUDY=studies/sql/study.json
    python3 analysis/v16_results.py
"""

from __future__ import annotations

import argparse
import csv
import json
import statistics
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STUDY_ID = "picc-sql-minimal-v6"
ORDER = ("rust", "python", "python-typed")
# A constant-output SQL engine scores this much; at or below it the candidate
# is indistinguishable from one that works on nothing.
FLOOR = 0.0503
# From the plan: the budget helps if the run writes and stays under this.
CUTOFF_LIMIT = 0.20


def load_rows() -> list[dict[str, str]]:
    path = ROOT / "runs" / "study-results" / STUDY_ID / "runs.csv"
    if not path.is_file():
        return []
    with path.open(encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def value(row: dict[str, str], column: str) -> float | None:
    raw = row.get(column)
    try:
        return float(raw) if raw not in (None, "") else None
    except ValueError:
        return None


def reply_shape(run_id: str) -> dict[str, int]:
    """Per-run reply counts, read from Pi's own event streams.

    Counts assistant `message_end` events rather than anything the harness
    derives, so the numbers are the model's behaviour and not the harness's
    interpretation of it.
    """
    events = ROOT / "runs" / run_id / "artifacts" / "events"
    shape = Counter()
    if not events.is_dir():
        return dict(shape)
    for path in sorted(events.glob("round-*.jsonl")):
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for line in text.splitlines():
            if '"message_end"' not in line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            message = event.get("message") or {}
            if event.get("type") != "message_end" or message.get("role") != "assistant":
                continue
            shape["replies"] += 1
            stop = message.get("stopReason")
            if stop == "length":
                shape["cut_off"] += 1
            elif stop == "error":
                shape["terminated"] += 1
            for block in message.get("content") or []:
                if not isinstance(block, dict) or block.get("type") != "toolCall":
                    continue
                name = block.get("name") or ""
                shape["tool_calls"] += 1
                if name in ("write", "edit"):
                    shape["writes"] += 1
    return dict(shape)


def rate(shape: dict[str, int], key: str) -> float | None:
    replies = shape.get("replies", 0)
    return shape.get(key, 0) / replies if replies else None


def pct(fraction: float | None) -> str:
    return "     -" if fraction is None else f"{100 * fraction:5.1f}%"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", action="append", dest="runs",
                        help="report a single run directory by id, before a summary exists")
    args = parser.parse_args()

    if args.runs:
        rows = [{"run_id": r, "condition": "?", "replicate": "-"} for r in args.runs]
        print(f"Ad-hoc report over {len(rows)} run(s); no study summary needed.\n")
    else:
        rows = load_rows()
        if not rows:
            print(f"No summary for {STUDY_ID}. Run: make study-summary STUDY=studies/sql/study.json")
            print("For a single run before then: python3 analysis/v16_results.py --run <run-id>")
            return 1

    print(f"{'run':<30} {'cond':<14} {'writes':>7} {'cutoff':>7} {'termd':>7} {'tools':>7} {'hidden':>8}")
    print("-" * 86)
    by_condition: dict[str, list[float]] = {}
    for row in sorted(rows, key=lambda r: (ORDER.index(r["condition"]) if r.get("condition") in ORDER else 9,
                                           r.get("replicate", ""))):
        run_id = row["run_id"]
        shape = reply_shape(run_id)
        hidden = value(row, "hidden_score")
        if hidden is not None and row.get("condition") in ORDER:
            by_condition.setdefault(row["condition"], []).append(hidden)
        print(f"{run_id:<30} {row.get('condition',''):<14} {shape.get('writes',0):>7} "
              f"{pct(rate(shape,'cut_off')):>7} {pct(rate(shape,'terminated')):>7} "
              f"{shape.get('tool_calls',0):>7} "
              f"{'       -' if hidden is None else f'{hidden:8.3f}'}")

    print()
    print("Decision rule from docs/EXPERIMENT_PLAN_v16.md, per typed run:")
    for row in rows:
        if row.get("condition") not in (None, "?", "python-typed"):
            continue
        shape = reply_shape(row["run_id"])
        cut = rate(shape, "cut_off")
        term = rate(shape, "terminated")
        writes = shape.get("writes", 0)
        if term and term > 0:
            verdict = ("INVALID - replies lost to stream errors; the idle-timeout fix "
                       "regressed and this run is not comparable")
        elif writes > 0 and cut is not None and cut < CUTOFF_LIMIT:
            verdict = "budget helps - writes happened and cut-offs are low; a full batch is justified"
        elif cut is not None and cut < CUTOFF_LIMIT:
            verdict = ("budget does not help - cut-offs fell but nothing was written; "
                       "reasoning length was not the cause")
        else:
            verdict = ("budget is not the mechanism - cut-offs stayed high; check that the "
                       "server enforces it before concluding anything about typing")
        print(f"  {row['run_id']}: {verdict}")

    if by_condition:
        print()
        for condition in ORDER:
            scores = by_condition.get(condition)
            if not scores:
                continue
            working = [s for s in scores if s > FLOOR]
            median = statistics.median(working) if working else None
            print(f"  {condition:<14} produced a working engine {len(working)}/{len(scores)}"
                  + (f", median hidden {median:.3f} among those" if median is not None else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
