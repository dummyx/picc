#!/usr/bin/env python3
"""Extract process metrics from completed PiCC runs.

Answers "how did the agent work?" rather than "what did it score", by reading
the Pi event streams, ledgers, and evaluator output that every run already
produces. Read-only: it never touches a run directory.

This lives outside scripts/ on purpose. scripts/ is fingerprinted by the study
layer (MATERIALIZED_HASH_DIRS), so adding a file there would change the harness
hash and break comparability with already-materialized runs.

Usage:
    python3 analysis/process_metrics.py                 # all runs under runs/
    python3 analysis/process_metrics.py --json out.json
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
RUNS_ROOT = REPO_ROOT / "runs"

# Affordances the conditions hand the agent, as opposed to generic file/shell tools.
AFFORDANCE_TOOLS = ("test_visible", "experiment_status", "reference_oracle")

# Rough intent buckets for shell commands. First match wins, so order matters:
# a command that both builds and runs a test is counted as a self-test.
BASH_INTENTS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("self_test", re.compile(r"\./[\w./-]*test|run_test|\btests?-local\b|\./t\d|\.bin\b|/target/release/picc\s+\S|python3?\s+picc\.py\s+\S|\bnode\s+(?:\S*/)?(?:src|dist)/picc\.[jt]s\s+\S|\bnode\s+--test\b")),
    ("build", re.compile(r"\bcargo\s+(build|check|clippy)\b|py_compile|\brustc\b|(^|[;&|]\s*)(?:\S*/)?(?:npx\s+)?tsc(?=\s|$)|\bnode\s+--check\b")),
    ("inspect", re.compile(r"^\s*(ls|cat|head|tail|wc|find|grep|rg|file|pwd|which|tree|stat|diff)\b")),
    ("write_via_shell", re.compile(r"\bcat\s*>|\bsed\s+-i\b|\btee\b|>>?\s*\S+\.(c|rs|py|js|ts|sh|md)\b")),
    ("vcs", re.compile(r"\bgit\b")),
)


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.is_file():
        return rows
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            rows.append(value)
    return rows


def classify_bash(command: str) -> str:
    for label, pattern in BASH_INTENTS:
        if pattern.search(command):
            return label
    return "other"


def analyse_events(run: Path) -> dict[str, Any]:
    """Walk every round's Pi event stream and summarise agent behaviour."""
    tools: Counter[str] = Counter()
    bash_intents: Counter[str] = Counter()
    edited_paths: Counter[str] = Counter()
    turns = assistant_msgs = thinking_blocks = truncated = 0
    thinking_chars = text_chars = 0
    planning_only_turns = 0  # assistant spoke/thought but called no tool
    retries = errored_turns = 0
    input_tokens = output_tokens = 0
    per_round: list[dict[str, Any]] = []
    hangs: list[dict[str, str]] = []
    first_ts: int | None = None
    last_ts: int | None = None
    turn_stamps: list[int] = []

    for path in sorted((run / "artifacts" / "events").glob("round-*.jsonl")):
        rows = load_jsonl(path)
        starts: dict[str, dict[str, Any]] = {}
        round_tools: Counter[str] = Counter()
        round_turns = 0
        for event in rows:
            kind = event.get("type")
            if kind == "auto_retry_start":
                retries += 1
            elif kind == "tool_execution_start":
                starts[str(event.get("toolCallId"))] = event
            elif kind == "tool_execution_end":
                starts.pop(str(event.get("toolCallId")), None)
            elif kind == "turn_end":
                message = event.get("model") and {} or event.get("message", {})
                usage = message.get("usage", {}) or {}
                input_tokens += int(usage.get("input", 0) or 0)
                output_tokens += int(usage.get("output", 0) or 0)
                stamp = message.get("timestamp")
                if isinstance(stamp, int):
                    turn_stamps.append(stamp)
                    first_ts = stamp if first_ts is None else min(first_ts, stamp)
                    last_ts = stamp if last_ts is None else max(last_ts, stamp)
                turns += 1
            elif kind == "message_end":
                message = event.get("message", {})
                if message.get("role") != "assistant":
                    continue
                if message.get("stopReason") == "error":
                    errored_turns += 1
                    continue
                # Hit the output ceiling mid-turn: the thinking is kept but no
                # tool call is emitted, so the turn produces nothing.
                if message.get("stopReason") == "length":
                    truncated += 1
                assistant_msgs += 1
                round_turns += 1
                called_tool = False
                for item in message.get("content", []):
                    if not isinstance(item, dict):
                        continue
                    itype = item.get("type")
                    if itype == "thinking":
                        thinking_blocks += 1
                        thinking_chars += len(str(item.get("thinking", "")))
                    elif itype == "text":
                        text_chars += len(str(item.get("text", "")))
                    elif itype == "toolCall":
                        called_tool = True
                        name = str(item.get("name", "?"))
                        tools[name] += 1
                        round_tools[name] += 1
                        args = item.get("arguments") or {}
                        if name == "bash":
                            bash_intents[classify_bash(str(args.get("command", "")))] += 1
                        elif name in {"write", "edit"}:
                            edited_paths[Path(str(args.get("path", "?"))).name] += 1
                if not called_tool:
                    planning_only_turns += 1

        # A tool call that never returned is where the session stalled.
        for event in starts.values():
            args = event.get("args") or {}
            hangs.append(
                {
                    "round": path.stem,
                    "tool": str(event.get("toolName")),
                    "command": str(args.get("command", ""))[:300],
                }
            )
        per_round.append(
            {
                "round": path.stem,
                "assistant_turns": round_turns,
                "tool_calls": sum(round_tools.values()),
                "tools": dict(round_tools),
            }
        )

    active_minutes = round((last_ts - first_ts) / 60000, 1) if first_ts and last_ts else 0.0
    # Only turn_end carries a timestamp, so the gap between consecutive turns is
    # the finest time resolution available. It still localises a stall: a long
    # gap is the agent blocked inside one tool call.
    gaps = [(b - a) / 60000 for a, b in zip(turn_stamps, turn_stamps[1:])]
    return {
        "max_turn_gap_minutes": round(max(gaps), 1) if gaps else 0.0,
        "median_turn_gap_seconds": round(sorted(gaps)[len(gaps) // 2] * 60, 1) if gaps else 0.0,
        "assistant_turns": assistant_msgs,
        "truncated_turns": truncated,
        "errored_turns": errored_turns,
        "provider_retries": retries,
        "planning_only_turns": planning_only_turns,
        "thinking_blocks": thinking_blocks,
        "thinking_chars": thinking_chars,
        "text_chars": text_chars,
        "tool_calls": sum(tools.values()),
        "tools": dict(tools.most_common()),
        "bash_intents": dict(bash_intents.most_common()),
        "top_edited_files": dict(edited_paths.most_common(8)),
        "affordance_calls": {name: tools.get(name, 0) for name in AFFORDANCE_TOOLS},
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "active_minutes": active_minutes,
        "hangs": hangs,
        "per_round": per_round,
    }


def analyse_compaction(run: Path) -> dict[str, Any]:
    """How much conversation each compaction dropped.

    Matters for the inline-specification condition, where the spec lives only in
    the opening request: if compaction evicts it, the agent loses the controlling
    document mid-run. `firstKeptEntryId` resolves against the session log, so the
    eviction boundary is recoverable exactly.
    """
    events = [
        row
        for row in load_jsonl(run / "artifacts" / "extension-events.jsonl")
        if "compact" in str(row.get("event"))
    ]
    sessions = sorted((run / "artifacts" / "sessions").glob("*.jsonl"))
    entry_ids: list[str] = []
    if sessions:
        entry_ids = [str(row.get("id", "")) for row in load_jsonl(sessions[-1])]

    evictions: list[dict[str, Any]] = []
    for event in events:
        kept = str(event.get("firstKeptEntryId") or "")
        if not kept:
            continue
        index = next((i for i, value in enumerate(entry_ids) if value.startswith(kept)), None)
        evictions.append(
            {
                "tokens_before": event.get("tokensBefore"),
                "entries_evicted": index,
                "entries_total": len(entry_ids) or None,
                "opening_request_evicted": None if index is None else index > 0,
            }
        )
    return {"compaction_count": len(events) // 2 or len(events), "compaction_evictions": evictions}


def analyse_trajectory(run: Path) -> dict[str, Any]:
    snapshots = load_jsonl(run / "artifacts" / "snapshots.jsonl")
    scores: list[float] = []
    buildable = 0
    for snapshot in snapshots:
        visible = snapshot.get("visible") or {}
        scores.append(float(visible.get("score") or 0.0))
        if visible.get("build_ok"):
            buildable += 1
    regressions = sum(1 for a, b in zip(scores, scores[1:]) if b < a - 1e-9)
    hidden_rows = load_jsonl(run / "artifacts" / "hidden-scores.jsonl")
    hidden_final = (hidden_rows[-1].get("summary") if hidden_rows else {}) or {}
    failures = Counter(f.get("failure_type") for f in hidden_final.get("failures", []))
    return {
        "rounds": len(snapshots),
        "visible_scores": [round(s, 4) for s in scores],
        "score_regressions": regressions,
        "buildable_snapshots": f"{buildable}/{len(snapshots)}" if snapshots else "0/0",
        "hidden_final_score": round(float(hidden_final.get("score") or 0.0), 4),
        "hidden_audit_ok": hidden_final.get("audit_ok"),
        "hidden_failure_types": dict(failures.most_common()),
        "final_loc": final_source_loc(run, snapshots),
    }


def final_source_loc(run: Path, snapshots: list[dict[str, Any]]) -> int | None:
    """LOC of the final workspace by the adapter's source extensions.

    The runner's snapshot ledger only counts `*.rs`, so Python and JS/TS runs
    would otherwise read as 0 LOC. Falls back to that ledger value for runs
    without a study adapter.
    """
    adapter_path = run / "study-control" / "candidate.json"
    workspace = run / "workspace"
    if not adapter_path.is_file() or not workspace.is_dir():
        return snapshots[-1].get("rust_loc") if snapshots else None
    adapter = json.loads(adapter_path.read_text(encoding="utf-8"))
    extensions = {str(item) for item in adapter.get("source_extensions", [])}
    excluded = [Path(str(item)).parts for item in (adapter.get("audit") or {}).get("exclude_paths", [])]
    total = 0
    for path in workspace.rglob("*"):
        if not path.is_file() or path.is_symlink() or path.suffix not in extensions:
            continue
        parts = path.relative_to(workspace).parts
        if any(part in {".git", ".pi", "target", "node_modules", "__pycache__"} for part in parts):
            continue
        if any(parts[: len(prefix)] == prefix for prefix in excluded):
            continue
        total += len(path.read_text(encoding="utf-8", errors="replace").splitlines())
    return total


def analyse_run(run: Path) -> dict[str, Any] | None:
    metadata_path = run / "metadata.json"
    if not metadata_path.is_file():
        return None
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    if metadata.get("status") == "running":
        # Still executing: no snapshots, no scores, and its condition is only
        # frozen when the run finishes. Including it would skew the aggregate.
        return None
    study_path = run / "study-metadata.json"
    condition = "(base workflow)"
    factor = "-"
    # Which affordances this condition actually exposes. Counting an unused tool
    # as "declined" would be wrong when the condition never offered it.
    offered = {"test_visible": True, "experiment_status": True, "reference_oracle": False}
    if study_path.is_file():
        declared = json.loads(study_path.read_text(encoding="utf-8")).get("condition") or {}
        condition = declared.get("id", condition)
        factor = declared.get("factor", factor)
        offered["test_visible"] = (declared.get("tests") or {}).get("access") == "tool"
        offered["reference_oracle"] = (declared.get("reference") or {}).get("mode") == "oracle"

    workspace = run / "workspace"
    workspace_files = sorted(p.name for p in workspace.iterdir()) if workspace.is_dir() else []
    guard = load_jsonl(run / "artifacts" / "guard.jsonl")
    extension = load_jsonl(run / "artifacts" / "extension-events.jsonl")

    events = analyse_events(run)
    elapsed_minutes = round(float(metadata.get("elapsed_seconds") or 0.0) / 60, 1)
    return {
        "run_id": run.name,
        "condition": condition,
        "factor": factor,
        "replicate": metadata.get("replicate"),
        # Runs are only comparable within one output cap: 32768 truncated long
        # thinking blocks mid-turn, wasting whole rounds.
        "output_cap": (metadata.get("model") or {}).get("max_tokens"),
        "affordances_offered": offered,
        "affordance_uptake": {
            name: ("declined" if offered[name] and not count else "used" if count else "n/a")
            for name, count in events["affordance_calls"].items()
        },
        "profile": metadata.get("profile"),
        "max_stage": (metadata.get("budget") or {}).get("max_stage"),
        "termination": metadata.get("termination_reason"),
        "elapsed_minutes": elapsed_minutes,
        "idle_minutes": round(max(0.0, elapsed_minutes - events["active_minutes"]), 1),
        "kept_progress_file": "PROGRESS.md" in workspace_files,
        "self_authored_tests": [
            name for name in workspace_files if "test" in name.lower()
        ],
        "guard_blocks": sum(1 for row in guard if row.get("event", "blocked_tool_call") == "blocked_tool_call"),
        "guard_reasons": dict(
            Counter(
                row.get("reason") for row in guard if row.get("event", "blocked_tool_call") == "blocked_tool_call"
            ).most_common()
        ),
        # Bash commands the default timeout cut off (0 for cohorts before v6).
        "bash_timeouts": sum(1 for row in guard if row.get("event") == "bash_timeout_fired"),
        "compactions": sum(1 for row in extension if "compact" in str(row.get("event"))),
        **events,
        **analyse_compaction(run),
        **analyse_trajectory(run),
    }


def render_condition_summary(reports: list[dict[str, Any]]) -> list[str]:
    """Per-condition aggregate, restricted to runs that share an output cap.

    Runs under different caps are not comparable — 32768 truncated long thinking
    blocks mid-turn — so they are grouped separately rather than pooled. Quality
    is summarised over audit-passing runs only, with compliance reported beside
    it, so one policy violation cannot masquerade as a bad compiler.
    """
    lines = ["## By condition", ""]
    caps = sorted({r["output_cap"] for r in reports if r["output_cap"]}, reverse=True)
    for cap in caps:
        cohort = [r for r in reports if r["output_cap"] == cap]
        lines.append(f"Output cap `{cap}` — {len(cohort)} run(s)")
        lines.append("")
        lines.append(
            "| Condition | n | Scores (audit-passing) | Median | Spread | Audit pass | Declined tool |"
        )
        lines.append("|---|---:|---|---:|---:|---:|---:|")
        by: dict[str, list[dict[str, Any]]] = {}
        for report in cohort:
            by.setdefault(report["condition"], []).append(report)
        for condition in sorted(by):
            runs = sorted(by[condition], key=lambda r: r["replicate"] or 0)
            clean = [r for r in runs if r["hidden_audit_ok"]]
            scores = [r["hidden_final_score"] for r in clean]
            median = f"{sorted(scores)[len(scores) // 2]:.4f}" if scores else "—"
            spread = f"{max(scores) - min(scores):.3f}" if len(scores) > 1 else "—"
            declined = sum(
                1 for r in runs if r["affordance_uptake"].get("test_visible") == "declined"
            )
            lines.append(
                f"| `{condition}` | {len(runs)} | "
                f"{', '.join(f'{s:.3f}' for s in scores) or '—'} | {median} | {spread} | "
                f"{len(clean)}/{len(runs)} | {declined}/{len(runs)} |"
            )
        lines.append("")
    return lines


def render(reports: list[dict[str, Any]]) -> str:
    lines: list[str] = ["# PiCC process metrics", ""]
    lines.append(
        "Descriptive only: one run per condition, and run length was set by when the "
        "agent hung or was killed rather than by the condition, so cross-condition "
        "differences are not yet attributable to the treatments."
    )
    lines.append("")
    lines += render_condition_summary(reports)

    header = (
        "| Run | Cond | Rep | Cap | Rounds | Active/Elapsed min | Turns | Tools | "
        "Truncated | Offered-but-declined | Hidden |"
    )
    lines += [header, "|" + "---|" * 10]
    for report in reports:
        declined = sorted(k for k, v in report["affordance_uptake"].items() if v == "declined")
        afford = ", ".join(f"{k}=0" for k in declined) or "all used / none offered"
        lines.append(
            f"| {report['run_id']} | {report['condition']} | {report['replicate']} | "
            f"{report['output_cap']} | "
            f"{report['rounds']} | {report['active_minutes']}/{report['elapsed_minutes']} | "
            f"{report['assistant_turns']} | {report['tool_calls']} | "
            f"{report['truncated_turns']} | {afford} | {report['hidden_final_score']} |"
        )
    lines.append("")

    for report in reports:
        lines.append(f"## {report['run_id']}  (condition `{report['condition']}`, factor `{report['factor']}`)")
        lines.append("")
        lines.append(f"- termination: `{report['termination']}`, visible trajectory: {report['visible_scores']}")
        lines.append(
            f"- regressions: {report['score_regressions']}, buildable snapshots: "
            f"{report['buildable_snapshots']}, final LOC: {report['final_loc']}"
        )
        lines.append(f"- tools: {report['tools']}")
        lines.append(f"- shell intent: {report['bash_intents']}")
        lines.append(
            "- affordances: "
            + ", ".join(
                f"{name}={report['affordance_calls'][name]} "
                f"({'offered' if report['affordances_offered'][name] else 'not offered'})"
                for name in AFFORDANCE_TOOLS
            )
        )
        lines.append(
            f"- PROGRESS.md kept: {report['kept_progress_file']}; "
            f"self-authored test artifacts: {report['self_authored_tests'] or 'none'}"
        )
        lines.append(
            f"- thinking {report['thinking_chars']:,} chars vs prose {report['text_chars']:,} chars; "
            f"output tokens {report['output_tokens']:,}"
        )
        lines.append(
            f"- guard blocks: {report['guard_blocks']} {report['guard_reasons'] or ''}; bash timeouts: {report['bash_timeouts']}; "
            f"compactions: {report['compactions']}; provider retries: {report['provider_retries']}"
        )
        lines.append(f"- hidden failure types: {report['hidden_failure_types'] or 'none'}")
        for hang in report["hangs"]:
            lines.append(f"- **stalled** in {hang['round']} on `{hang['tool']}`: `{hang['command'][:160]}`")
        lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs-root", type=Path, default=RUNS_ROOT)
    parser.add_argument("--json", type=Path, help="also write the raw metrics here")
    args = parser.parse_args()

    reports = []
    for run in sorted(p for p in args.runs_root.iterdir() if p.is_dir() and not p.name.startswith(".")):
        report = analyse_run(run)
        if report:
            reports.append(report)
    if not reports:
        print("No completed runs found.")
        return 1
    print(render(reports))
    if args.json:
        args.json.write_text(json.dumps(reports, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
