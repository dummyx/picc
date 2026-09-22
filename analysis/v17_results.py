#!/usr/bin/env python3
"""v17 batch: python-typed against python on the SQL engine task, again.

v15 asked this and could not answer it: under `mypy --strict` the agent wrote
nothing, because more than half of its replies spent the whole output cap
reasoning. v16 found the cause and the fix (a budget on reasoning, enforced by
the server) on one run and confirmed it against a control. v17 is the batch
v15 was meant to be, on the fixed harness.

Endpoints and decision rule are v15's, unchanged, so the question has not
moved while the harness was being repaired:

1. produced a working engine -- best hidden score above the constant-output
   floor, as a count per condition;
2. hidden score among runs that did, python-typed against python, paired by
   replicate, with the 0.13 threshold used since v4.

Plus a validity gate the earlier batches did not have. A run is not comparable
if any reply ended in a stream error (the idle-timeout defect: zero in every
llama.cpp run, 3 of 7 on the first SGLang run before the fix) or any
compaction failed. If either appears the batch is stopped, not analyzed.

Reasoning length is not in the run records (Pi and SGLang disagree on where
the field lives); count it with the tokenizer:

    .venv-sglang/bin/python analysis/reasoning_tokens.py RUN_ID ...

Read-only over runs/.

    make study-summary STUDY=studies/sql/study.json
    python3 analysis/v17_results.py
"""

from __future__ import annotations

import csv
import json
import statistics
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# Hardcoded on purpose: this script belongs to one batch, and must keep
# reading that batch's summary after the manifest moves on.
STUDY_ID = "picc-sql-minimal-v7"
ORDER = ("rust", "python", "python-typed", "javascript", "typescript")
# The two typed/untyped contrasts, reported separately and never pooled: the
# Python one was fixed before any data, the TS/JS one was added mid-batch.
CONTRASTS = (("python-typed", "python"), ("typescript", "javascript"))
THRESHOLD = 0.13
# A constant-output SQL engine scores this much; at or below it the candidate
# is indistinguishable from one that works on nothing.
FLOOR = 0.0503


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
    """Reply counts from Pi's own event streams, not from anything derived."""
    events = ROOT / "runs" / run_id / "artifacts" / "events"
    shape: Counter[str] = Counter()
    if not events.is_dir():
        return dict(shape)
    for path in sorted(events.glob("round-*.jsonl")):
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if '"message_end"' not in line and '"compaction_end"' not in line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if event.get("type") == "compaction_end":
                if (event.get("errorMessage") or "").strip():
                    shape["broken_compactions"] += 1
                continue
            message = event.get("message") or {}
            if event.get("type") != "message_end" or message.get("role") != "assistant":
                continue
            shape["replies"] += 1
            stop = message.get("stopReason")
            shape["cut_off"] += stop == "length"
            shape["stream_errors"] += stop == "error"
            for block in message.get("content") or []:
                if isinstance(block, dict) and block.get("type") == "toolCall":
                    shape["tool_calls"] += 1
                    shape["writes"] += (block.get("name") or "") in ("write", "edit")
    return dict(shape)


def pct(part: int, whole: int) -> str:
    return "    —" if not whole else f"{100 * part / whole:4.1f}%"


def main() -> int:
    rows = load_rows()
    print(f"## SQL engine ({STUDY_ID}): {len(rows)} included runs\n")
    if not rows:
        print("(no summary yet; run `make study-summary STUDY=studies/sql/study.json`)")
        return 0

    by_cell = {(row["condition_id"], int(row["replicate"])): row for row in rows}
    print("| condition | rep | hidden | last buildable | replies | writes | cut off | stream errors | broken compactions |")
    print("|---|---:|---:|---:|---:|---:|---:|---:|---:|")
    table: dict[tuple[str, int], dict[str, object]] = {}
    invalid: list[str] = []
    for condition in ORDER:
        for replicate in sorted(r for c, r in by_cell if c == condition):
            row = by_cell[(condition, replicate)]
            shape = reply_shape(row["run_id"])
            hidden = value(row, "hidden_score")
            buildable = value(row, "hidden_score_last_buildable")
            replies = shape.get("replies", 0)
            print(f"| {condition} | {replicate} | "
                  + " | ".join("—" if v is None else f"{v:.4f}" for v in (hidden, buildable))
                  + f" | {replies} | {shape.get('writes', 0)} | {pct(shape.get('cut_off', 0), replies)}"
                  + f" | {pct(shape.get('stream_errors', 0), replies)} | {shape.get('broken_compactions', 0)} |")
            if shape.get("stream_errors", 0) or shape.get("broken_compactions", 0):
                invalid.append(row["run_id"])
            table[(condition, replicate)] = {
                "hidden": hidden,
                "above_floor": hidden is not None and hidden > FLOOR,
            }

    print()
    if invalid:
        print("**VALIDITY GATE FAILED** — these runs lost replies to stream errors or broke a")
        print("compaction, so the harness fixes did not hold and the batch is not analyzable:")
        for run_id in invalid:
            print(f"  - {run_id}")
        print()

    print("### Endpoint 1: produced a working engine\n")
    for condition in ORDER:
        cells = [v for (c, _), v in table.items() if c == condition]
        if cells:
            working = sum(1 for v in cells if v["above_floor"])
            print(f"- {condition}: {working}/{len(cells)}")
    print("\nWith three replicates a difference of 3 to 0 is worth stating; anything smaller is not.\n")

    print("### Endpoint 2: hidden score, typed minus untyped, paired by replicate\n")
    for typed_id, plain_id in CONTRASTS:
        if not any(c == typed_id for c, _ in table):
            continue
        print(f"**{typed_id} against {plain_id}**"
              + ("  *(added mid-batch; see the amendment in the plan)*"
                 if typed_id == "typescript" else "") + "\n")
        deltas = []
        for replicate in sorted({r for c, r in table if c == typed_id}):
            typed, plain = table.get((typed_id, replicate)), table.get((plain_id, replicate))
            if not typed or not plain or not (typed["above_floor"] and plain["above_floor"]):
                continue
            delta = typed["hidden"] - plain["hidden"]  # type: ignore[operator]
            deltas.append(delta)
            print(f"- replicate {replicate}: {delta:+.4f}")
        if len(deltas) < 2:
            verdict = "not measurable (fewer than two replicates with both arms working)"
        else:
            median = statistics.median(deltas)
            print(f"\npaired median: {median:+.4f} (threshold ±{THRESHOLD})")
            verdict = ("typing helps" if median >= THRESHOLD
                       else "typing hurts" if median <= -THRESHOLD
                       else "no effect detected")
        print(f"\n**{verdict}**. At three replicates this is descriptive, not a test.\n")

    # A median is only worth reading against the noise it sits in. When one
    # condition's own replicates span more than the threshold, the contrast
    # cannot resolve the threshold and the spread is the finding.
    print("### Within-condition spread\n")
    for condition in ORDER:
        vals = [v["hidden"] for (c, _), v in table.items() if c == condition and v["hidden"] is not None]
        if len(vals) >= 2:
            spread = max(vals) - min(vals)
            flag = "  <- exceeds the ±%.2f threshold" % THRESHOLD if spread > THRESHOLD else ""
            print(f"- {condition}: n={len(vals)}, median {statistics.median(vals):.4f}, "
                  f"range {min(vals):.4f}-{max(vals):.4f}, spread {spread:.4f}{flag}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
