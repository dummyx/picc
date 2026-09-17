#!/usr/bin/env python3
"""v10 cohort: per-replicate hidden scores for the chapters 1-18 compiler and
SQL engine tasks (rust baseline, python, python-typed), read from the study
summaries.  Prints one table per study and the python-typed minus python
paired deltas.  Read-only over runs/study-results/.

    make study-summary STUDY=studies/c18/study.json
    make study-summary STUDY=studies/sql/study.json
    python3 analysis/v10_results.py
"""

from __future__ import annotations

import csv
import json
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STUDIES = {"picc-c18-minimal-v1": "chapters 1-18 compiler", "picc-sql-minimal-v1": "SQL engine"}
FLOORS = {"picc-c18-minimal-v1": 0.2129, "picc-sql-minimal-v1": 0.0503}
COLUMNS = ("hidden_score_last_buildable", "hidden_score_final")


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


def main() -> int:
    output: dict[str, object] = {}
    for study_id, label in STUDIES.items():
        rows = load_rows(study_id)
        print(f"## {label} ({study_id}): {len(rows)} included runs")
        if not rows:
            print("(no summary yet)\n")
            continue
        columns = [c for c in COLUMNS if c in rows[0]] or [c for c in rows[0] if "hidden" in c and "score" in c][:2]
        by_cell = {(row["condition_id"], int(row["replicate"])): row for row in rows}
        conditions = sorted({row["condition_id"] for row in rows}, key=lambda c: ["rust", "python", "python-typed"].index(c) if c in ("rust", "python", "python-typed") else 9)
        print("| condition | replicate | " + " | ".join(columns) + " | above floor |")
        print("|---|---:|" + "---:|" * len(columns) + "---|")
        table = []
        for condition in conditions:
            for replicate in sorted(r for c, r in by_cell if c == condition):
                row = by_cell[(condition, replicate)]
                values = [value(row, c) for c in columns]
                above = values[0] is not None and values[0] > FLOORS[study_id]
                print(f"| {condition} | {replicate} | " + " | ".join("—" if v is None else f"{v:.4f}" for v in values) + f" | {'yes' if above else 'no'} |")
                table.append({"condition": condition, "replicate": replicate, **dict(zip(columns, values)), "above_floor": above})
        deltas = []
        for replicate in sorted({r for c, r in by_cell if c == "python-typed"}):
            typed, plain = by_cell.get(("python-typed", replicate)), by_cell.get(("python", replicate))
            if typed and plain and value(typed, columns[0]) is not None and value(plain, columns[0]) is not None:
                deltas.append(value(typed, columns[0]) - value(plain, columns[0]))
        if deltas:
            print(f"\npython-typed minus python ({columns[0]}), paired by replicate: {[round(d, 4) for d in deltas]}, median {statistics.median(deltas):.4f}")
        feasible = {c: sum(1 for t in table if t["condition"] == c and t["above_floor"]) for c in conditions}
        print(f"runs above the constant-output floor ({FLOORS[study_id]}): {feasible}\n")
        output[study_id] = {"rows": table, "typed_minus_plain": deltas, "above_floor": feasible}
    (ROOT / "analysis" / "v10-results.json").write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
