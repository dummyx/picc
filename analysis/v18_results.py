#!/usr/bin/env python3
"""v18 batch: Rust, Python and typed Python on both newer tasks.

The SQL engine (picc-sql-minimal-v8) and the chapters 1-18 C compiler
(picc-c18-minimal-v4), three replicates per language, on the harness as it
stands after v17: SGLang with the reasoning budget, the reorganized scripts,
the rule checker that reads commands rather than pasted text, and the scorer
that keeps the error line of a crash.

It is the v10 design run again. v10 lost 10 of its 18 runs to harness defects
and its chapters 1-18 half has never been repeated; the SQL half has (v17).

Endpoints and decision rule are v17's, applied to each task separately:

1. produced a working program -- final hidden score above the task's
   constant-output floor and, for the compiler, at least one valid program
   compiled and run correctly (a compiler that rejects everything scores 0.5
   on that task's metric without compiling anything), as a count per language;
2. hidden score among runs that did, python-typed against python, paired by
   replicate, with the 0.13 threshold used since v4.

The validity gate is v17's: a run is not comparable if any reply ended in a
stream error or any compaction failed.

Read-only over runs/.

    make study-summary STUDY=studies/sql/study.json
    make study-summary STUDY=studies/c18/study.json
    python3 analysis/v18_results.py
"""

from __future__ import annotations

import csv
import json
import statistics
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# Hardcoded on purpose: this script belongs to one batch, and must keep
# reading that batch's summaries after the manifests move on.
STUDIES = (
    ("picc-sql-minimal-v8", "SQL engine", "studies/sql/study.json"),
    ("picc-c18-minimal-v4", "chapters 1-18 compiler", "studies/c18/study.json"),
)
# What a program that prints the same thing for every input scores on each
# task's hidden tests; at or below it the candidate works on nothing.
FLOORS = {"picc-sql-minimal-v8": 0.0503, "picc-c18-minimal-v4": 0.2129}
ORDER = ("rust", "python", "python-typed")
TYPED, PLAIN = "python-typed", "python"
THRESHOLD = 0.13


def load_rows(study_id: str) -> list[dict[str, str]]:
    path = ROOT / "runs" / "study-results" / study_id / "runs.csv"
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
                    shape["writes"] += (block.get("name") or "") in ("write", "edit")
    return dict(shape)


def valid_programs_passed(run_id: str) -> int | None:
    """Valid test programs the final snapshot compiled and ran correctly
    (compiler task only; the SQL scorer has no valid/invalid split)."""
    path = ROOT / "runs" / run_id / "artifacts" / "hidden-scores.jsonl"
    if not path.is_file():
        return None
    lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if not lines:
        return None
    stages = (json.loads(lines[-1]).get("summary") or {}).get("stages") or {}
    counts = [stage.get("valid", {}).get("passed") for stage in stages.values() if isinstance(stage, dict)]
    counts = [count for count in counts if isinstance(count, int)]
    return sum(counts) if counts else None


def blocked_by_reason(run_id: str) -> Counter[str]:
    path = ROOT / "runs" / run_id / "artifacts" / "guard.jsonl"
    reasons: Counter[str] = Counter()
    if path.is_file():
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if row.get("event") == "blocked_tool_call":
                reasons[str(row.get("reason"))] += 1
    return reasons


def pct(part: int, whole: int) -> str:
    return "    —" if not whole else f"{100 * part / whole:4.1f}%"


def report(study_id: str, label: str, study_path: str) -> None:
    rows = load_rows(study_id)
    print(f"## {label} ({study_id}): {len(rows)} included runs\n")
    if not rows:
        print(f"(no summary yet; run `make study-summary STUDY={study_path}`)\n")
        return
    compiler = "c18" in study_id
    by_cell = {(row["condition_id"], int(row["replicate"])): row for row in rows}
    print("| language | rep | hidden | last buildable | working | replies | writes | cut off | stream errors | broken compactions | ended by |")
    print("|---|---:|---:|---:|---|---:|---:|---:|---:|---:|---|")
    table: dict[tuple[str, int], dict[str, object]] = {}
    invalid: list[str] = []
    blocks: Counter[str] = Counter()
    for condition in ORDER:
        for replicate in sorted(r for c, r in by_cell if c == condition):
            row = by_cell[(condition, replicate)]
            run_id = row["run_id"]
            shape = reply_shape(run_id)
            hidden = value(row, "hidden_score")
            buildable = value(row, "hidden_score_last_buildable")
            working = hidden is not None and hidden > FLOORS[study_id]
            if compiler:
                working = working and (valid_programs_passed(run_id) or 0) > 0
            replies = shape.get("replies", 0)
            print(f"| {condition} | {replicate} | "
                  + " | ".join("—" if v is None else f"{v:.4f}" for v in (hidden, buildable))
                  + f" | {'yes' if working else 'no'} | {replies} | {shape.get('writes', 0)}"
                  + f" | {pct(shape.get('cut_off', 0), replies)} | {pct(shape.get('stream_errors', 0), replies)}"
                  + f" | {shape.get('broken_compactions', 0)} | {row.get('termination_reason', '')} |")
            if shape.get("stream_errors", 0) or shape.get("broken_compactions", 0):
                invalid.append(run_id)
            blocks.update(blocked_by_reason(run_id))
            table[(condition, replicate)] = {"hidden": hidden, "working": working}

    print()
    if invalid:
        print("**VALIDITY GATE FAILED** — these runs lost replies to stream errors or broke a")
        print("compaction, so the harness fixes did not hold and the batch is not analyzable:")
        for run_id in invalid:
            print(f"  - {run_id}")
        print()

    print("### Endpoint 1: produced a working program\n")
    for condition in ORDER:
        cells = [v for (c, _), v in table.items() if c == condition]
        if cells:
            print(f"- {condition}: {sum(1 for v in cells if v['working'])}/{len(cells)}")
    print("\nWith three replicates a difference of 3 to 0 is worth stating; anything smaller is not.\n")

    print(f"### Endpoint 2: hidden score, {TYPED} minus {PLAIN}, paired by replicate\n")
    deltas = []
    for replicate in sorted({r for c, r in table if c == TYPED}):
        typed, plain = table.get((TYPED, replicate)), table.get((PLAIN, replicate))
        if not typed or not plain or not (typed["working"] and plain["working"]):
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

    # A median is only worth reading against the noise it sits in.
    print("### Spread within each language\n")
    for condition in ORDER:
        vals = [v["hidden"] for (c, _), v in table.items() if c == condition and v["hidden"] is not None]
        if len(vals) >= 2:
            spread = max(vals) - min(vals)
            flag = "  <- exceeds the ±%.2f threshold" % THRESHOLD if spread > THRESHOLD else ""
            print(f"- {condition}: n={len(vals)}, median {statistics.median(vals):.4f}, "
                  f"range {min(vals):.4f}-{max(vals):.4f}, spread {spread:.4f}{flag}")

    # The rule checker changed for this batch; what it blocked is part of the record.
    print("\n### Commands the rule checker blocked\n")
    if not blocks:
        print("- none")
    for reason, count in blocks.most_common():
        print(f"- {count} × {reason}")
    print()


def main() -> int:
    for study_id, label, study_path in STUDIES:
        report(study_id, label, study_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
