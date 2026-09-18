#!/usr/bin/env python3
"""Why a run's Pi session dies: turn shape, not token volume.

A run ends in `context_overflow` when Pi's compaction cannot summarize the
session. Across every v10-v12 run, the predictor is not how much the model
generated but how often it *acted*: the ratio of tool executions to assistant
turns. Runs at roughly one tool call per turn survive; runs below about 0.9
accumulate thinking that is dropped from the prompt but must still be
summarized, and the summarization request outgrows the context window.

    python3 analysis/turn_shape.py
"""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def profile(run_dir: Path) -> dict[str, object] | None:
    events = sorted((run_dir / "artifacts" / "events").glob("round-*.jsonl"))
    if not events:
        return None
    turns = tools = generated = 0
    worst_request = 0
    for path in events:
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if '"tool_execution_start"' in line:
                tools += 1
            if '"compaction_end"' in line:
                match = re.search(r"request \((\d+) tokens\)", line)
                if match:
                    worst_request = max(worst_request, int(match.group(1)))
            if '"message_end"' not in line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            output = int(((event.get("message") or {}).get("usage") or {}).get("output") or 0)
            if output:
                turns += 1
                generated += output
    metadata = json.loads((run_dir / "metadata.json").read_text(encoding="utf-8"))
    return {
        "run": run_dir.name,
        "turns": turns,
        "tools": tools,
        "tools_per_turn": round(tools / turns, 2) if turns else 0.0,
        "generated": generated,
        "worst_compaction_request": worst_request,
        "termination": metadata.get("termination_reason"),
    }


def main() -> int:
    rows = []
    for run_dir in sorted((ROOT / "runs").glob("v1[012]-*")):
        if not (run_dir / "metadata.json").is_file() or "pilot" in run_dir.name:
            continue
        row = profile(run_dir)
        if row:
            rows.append(row)
    rows.sort(key=lambda r: r["tools_per_turn"])
    print(f"{'run':32s} {'turns':>6s} {'tools/turn':>11s} {'generated':>11s} {'worst compaction':>17s}  termination")
    for row in rows:
        print(f"{row['run']:32s} {row['turns']:6d} {row['tools_per_turn']:11.2f} {row['generated']:11,d} "
              f"{row['worst_compaction_request'] or '-':>17}  {row['termination']}")
    died = [r for r in rows if r["termination"] == "context_overflow"]
    lived = [r for r in rows if r["termination"] != "context_overflow"]
    if died and lived:
        print(f"\ndied (n={len(died)}): tools/turn max {max(r['tools_per_turn'] for r in died):.2f}")
        print(f"survived (n={len(lived)}): tools/turn min {min(r['tools_per_turn'] for r in lived):.2f}")
    (ROOT / "analysis" / "turn-shape.json").write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
