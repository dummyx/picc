#!/usr/bin/env python3
"""v15 batch: python-typed against python on the SQL engine task.

Reads the study summary, prints the per-run table and the paired deltas, and
checks the two things the plan fixed in advance: the 0.13 effect threshold and
that no session broke. Read-only over runs/.

    make study-summary STUDY=studies/sql/study.json
    python3 analysis/v15_results.py
"""

from __future__ import annotations

import csv
import json
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STUDY_ID = "picc-sql-minimal-v5"
ORDER = ("rust", "python", "python-typed")
THRESHOLD = 0.13
# A constant-output SQL engine scores this much; anything at or below it is
# indistinguishable from writing nothing that works.
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


def broken_rounds(run_id: str) -> int:
    """Rounds whose Pi event stream reports a failed compaction.

    Zero for every run is what the v15 plan requires; a non-zero count means
    the compaction bound did not hold and the batch is not analyzable.
    """
    events = ROOT / "runs" / run_id / "artifacts" / "events"
    if not events.is_dir():
        return 0
    broken = 0
    for path in sorted(events.glob("round-*.jsonl")):
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for line in text.splitlines():
            if '"compaction_end"' not in line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if (event.get("errorMessage") or "").strip():
                broken += 1
                break
    return broken


def main() -> int:
    rows = load_rows()
    print(f"## SQL engine ({STUDY_ID}): {len(rows)} included runs\n")
    if not rows:
        print("(no summary yet; run `make study-summary STUDY=studies/sql/study.json`)")
        return 0

    by_cell = {(row["condition_id"], int(row["replicate"])): row for row in rows}
    conditions = sorted(
        {row["condition_id"] for row in rows},
        key=lambda c: ORDER.index(c) if c in ORDER else len(ORDER),
    )

    print("| condition | replicate | hidden score | last buildable | rounds | finished | broken rounds |")
    print("|---|---:|---:|---:|---:|---|---:|")
    table: list[dict[str, object]] = []
    for condition in conditions:
        for replicate in sorted(r for c, r in by_cell if c == condition):
            row = by_cell[(condition, replicate)]
            score = value(row, "hidden_score")
            buildable = value(row, "hidden_score_last_buildable")
            broken = broken_rounds(row["run_id"])
            rounds = row.get("rounds") or row.get("rounds_completed") or ""
            print(
                f"| {condition} | {replicate} | "
                + " | ".join("—" if v is None else f"{v:.4f}" for v in (score, buildable))
                + f" | {rounds} | {row.get('finished', '')} | {broken} |"
            )
            table.append(
                {
                    "condition": condition,
                    "replicate": replicate,
                    "run_id": row["run_id"],
                    "hidden_score": score,
                    "hidden_score_last_buildable": buildable,
                    "broken_rounds": broken,
                    "above_floor": score is not None and score > FLOOR,
                }
            )

    scores = {(r["condition"], r["replicate"]): r["hidden_score"] for r in table}
    deltas = []
    for replicate in sorted({r for c, r in by_cell if c == "python-typed"}):
        typed = scores.get(("python-typed", replicate))
        plain = scores.get(("python", replicate))
        if typed is not None and plain is not None:
            deltas.append(typed - plain)

    verdict = "no effect detected"
    if deltas:
        median = statistics.median(deltas)
        if median >= THRESHOLD:
            verdict = "typing helps"
        elif median <= -THRESHOLD:
            verdict = "typing hurts"
        print(
            f"\npython-typed minus python, paired by replicate: "
            f"{[round(d, 4) for d in deltas]}, median {median:.4f}"
        )
        print(f"decision rule (|median| >= {THRESHOLD}): {verdict} (n={len(deltas)})")

    total_broken = sum(int(r["broken_rounds"]) for r in table)
    print(f"\nsessions with a failed compaction: {total_broken} of {len(table)} runs")
    if total_broken:
        print("The compaction bound did not hold. Per the plan, stop the batch rather than analyze it.")
    above = {c: sum(1 for r in table if r["condition"] == c and r["above_floor"]) for c in conditions}
    print(f"runs above the constant-output floor ({FLOOR}): {above}")

    (ROOT / "analysis" / "v15-results.json").write_text(
        json.dumps(
            {"rows": table, "typed_minus_plain": deltas, "verdict": verdict,
             "broken_runs": total_broken, "above_floor": above},
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
