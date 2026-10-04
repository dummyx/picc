#!/usr/bin/env python3
"""v20 batch: v19's design with the round check.

The SQL engine (picc-sql-minimal-v10) and the chapters 1-18 C compiler
(picc-c18-minimal-v6): Rust, Python and typed Python, three replicates each,
plus three replicates of Rust under the minimal specification (SQL only).
Every round message after the first carries the harness's check of the last
snapshot: did the specification's build command succeed, and what did the
specification's worked example produce. docs/EXPERIMENT_PLAN_v20.md.

Endpoints and decision rule are v17's, applied to each task separately:

1. produced a working program -- final hidden score above the task's
   constant-output floor and, for the compiler, at least one valid program
   compiled and run correctly, as a count per language;
2. hidden score, python-typed against python, paired by replicate, with the
   0.13 threshold used since v4; and, as its own contrast, rust-minimal-spec
   against rust.

New per-run columns: the first round after which the check passed, and how
many rounds it passed; a run whose check never passed is the finding v20 was
designed to make impossible to miss. The validity gate is v17's.

Read-only over runs/.

    make study-summary STUDY=studies/sql/study.json
    make study-summary STUDY=studies/c18/study.json
    python3 analysis/v20_results.py
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
    ("picc-sql-minimal-v10", "SQL engine", "studies/sql/study.json"),
    ("picc-c18-minimal-v6", "chapters 1-18 compiler", "studies/c18/study.json"),
)
# What a program that prints the same thing for every input scores on each
# task's hidden tests; at or below it the candidate works on nothing.
FLOORS = {"picc-sql-minimal-v10": 0.0503, "picc-c18-minimal-v6": 0.2129}
ORDER = ("rust", "python", "python-typed", "rust-minimal-spec")
TYPED, PLAIN = "python-typed", "python"
# Contrasts reported separately, never pooled; both fixed before any data.
CONTRASTS = ((TYPED, PLAIN, "typing"), ("rust-minimal-spec", "rust", "the minimal specification"))
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


def contract_failures(run_id: str) -> int | None:
    """Hidden scripts the final snapshot lost to the output contract (no
    `ok N` / `error` block where one is due), the failure v18 was stopped for."""
    path = ROOT / "runs" / run_id / "artifacts" / "hidden-scores.jsonl"
    if not path.is_file():
        return None
    lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if not lines:
        return None
    last = json.loads(lines[-1])
    output = ROOT / "runs" / run_id / str(last.get("output", ""))
    if not output.is_file():
        return None
    count = 0
    for test in json.loads(output.read_text(encoding="utf-8")).get("tests") or []:
        detail = str(test.get("detail") or "")
        # A script the engine ran out of time or memory on also has no blocks;
        # that is speed or size, not the contract.
        if test.get("failure_type") == "script_timeout" or (test.get("compiler_returncode") or 0) < 0:
            continue
        if test.get("failure_type") == "malformed_output" or "no output block" in detail:
            count += 1
    return count


def check_history(run_id: str) -> dict[str, object]:
    """The round check across the run's snapshots: after which round it first
    passed (1-based; None if never), how many rounds it passed out of how many
    were checked, and the final snapshot's status."""
    path = ROOT / "runs" / run_id / "artifacts" / "snapshots.jsonl"
    history: dict[str, object] = {"first_pass": None, "passed": 0, "checked": 0, "final": "—"}
    if not path.is_file():
        return history
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        snapshot = json.loads(line)
        check = (snapshot.get("visible") or {}).get("check")
        if not isinstance(check, dict):
            continue
        history["checked"] = int(history["checked"]) + 1
        if check.get("passed"):
            history["passed"] = int(history["passed"]) + 1
            if history["first_pass"] is None:
                history["first_pass"] = int(snapshot.get("round", 0)) + 1
        if not check.get("audit", {}).get("ok", True):
            history["final"] = "forbidden source"
        elif not check.get("build", {}).get("ok"):
            history["final"] = "build failed"
        elif check.get("passed"):
            history["final"] = "passed"
        else:
            example = check.get("example") or {}
            history["final"] = str(example.get("status") or "example failed") if "valid" not in example else (
                "passed" if example.get("passed") else
                f"valid: {example.get('valid', {}).get('status')}, invalid: {example.get('invalid', {}).get('status')}"
            )
    return history


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
    print("| language | rep | hidden | last buildable | working | contract failures | check first passed after round | rounds passed | final check | replies | writes | cut off | stream errors | broken compactions | ended by |")
    print("|---|---:|---:|---:|---|---:|---:|---:|---|---:|---:|---:|---:|---:|---|")
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
            history = check_history(run_id)
            first_pass = history["first_pass"]
            print(f"| {condition} | {replicate} | "
                  + " | ".join("—" if v is None else f"{v:.4f}" for v in (hidden, buildable))
                  + f" | {'yes' if working else 'no'} | {'—' if compiler else contract_failures(run_id)}"
                  + f" | {'never' if first_pass is None else first_pass} | {history['passed']}/{history['checked']}"
                  + f" | {history['final']} | {replies} | {shape.get('writes', 0)}"
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

    for arm, base, label in CONTRASTS:
        if not any(c == arm for c, _ in table):
            continue
        print(f"### Endpoint 2: hidden score, {arm} minus {base}, paired by replicate\n")
        deltas = []
        for replicate in sorted({r for c, r in table if c == arm}):
            top, bottom = table.get((arm, replicate)), table.get((base, replicate))
            if not top or not bottom or not (top["working"] and bottom["working"]):
                continue
            delta = top["hidden"] - bottom["hidden"]  # type: ignore[operator]
            deltas.append(delta)
            print(f"- replicate {replicate}: {delta:+.4f}")
        if len(deltas) < 2:
            verdict = "not measurable (fewer than two replicates with both arms working)"
            if len(deltas) == 1:
                verdict += f"; the one reading is {deltas[0]:+.4f}"
        else:
            median = statistics.median(deltas)
            print(f"\npaired median: {median:+.4f} (threshold ±{THRESHOLD})")
            verdict = (f"{label} helps" if median >= THRESHOLD
                       else f"{label} hurts" if median <= -THRESHOLD
                       else "no effect detected")
        print(f"\n**{verdict}**. At this size this is descriptive, not a test.\n")

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
