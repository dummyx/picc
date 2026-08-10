#!/usr/bin/env python3
"""Summarize Pi events, Git snapshots, and evaluation trajectories."""

from __future__ import annotations

import argparse
import contextlib
import fcntl
import json
import math
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from common import ExperimentError, REPO_ROOT, atomic_write_json, read_jsonl, sanitize_run_id


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    return parser.parse_args()


@contextlib.contextmanager
def harness_lock(run_dir: Path):
    lock_path = run_dir / ".harness.lock"
    with lock_path.open("a+", encoding="utf-8") as handle:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise ExperimentError(f"Run is already locked by another harness process: {run_dir.name}") from error
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def numeric(value: Any) -> float:
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else 0.0


def collect_events(events_dir: Path) -> dict[str, Any]:
    event_counts: Counter[str] = Counter()
    tool_counts: Counter[str] = Counter()
    usage: Counter[str] = Counter()
    stop_reasons: Counter[str] = Counter()
    malformed = 0

    for path in sorted(events_dir.glob("round-*.jsonl")):
        for raw_line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                event = json.loads(raw_line)
            except json.JSONDecodeError:
                malformed += 1
                continue
            event_type = str(event.get("type", "unknown"))
            event_counts[event_type] += 1
            if event_type == "tool_execution_start":
                tool_counts[str(event.get("toolName", "unknown"))] += 1
            if event_type == "message_end":
                message = event.get("message", {})
                if message.get("role") == "assistant":
                    message_usage = message.get("usage") or {}
                    aliases = {
                        "input": ("input", "inputTokens", "prompt_tokens"),
                        "output": ("output", "outputTokens", "completion_tokens"),
                        "cache_read": ("cacheRead", "cache_read", "cache_read_input_tokens"),
                        "cache_write": ("cacheWrite", "cache_write", "cache_creation_input_tokens"),
                        "total": ("totalTokens", "total_tokens"),
                    }
                    for target, names in aliases.items():
                        for name in names:
                            if name in message_usage:
                                usage[target] += int(numeric(message_usage[name]))
                                break
                    stop_reason = message.get("stopReason") or message.get("stop_reason")
                    if stop_reason:
                        stop_reasons[str(stop_reason)] += 1
    return {
        "event_counts": dict(event_counts),
        "tool_counts": dict(tool_counts),
        "usage": dict(usage),
        "stop_reasons": dict(stop_reasons),
        "malformed_jsonl_lines": malformed,
    }


def collect_extension_events(path: Path) -> dict[str, Any]:
    rows = read_jsonl(path)
    counts = Counter(str(row.get("event", "unknown")) for row in rows)
    return {"event_counts": dict(counts), "count": len(rows)}


def collect_guard(path: Path) -> dict[str, Any]:
    rows = read_jsonl(path)
    reasons = Counter(str(row.get("reason", "unknown")) for row in rows)
    tools = Counter(str(row.get("toolName", "unknown")) for row in rows)
    return {"blocked_calls": len(rows), "reasons": dict(reasons), "tools": dict(tools)}


def trajectory(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result = []
    for row in rows:
        summary = row.get("summary", {})
        result.append(
            {
                "round": row.get("round"),
                "elapsed_seconds": row.get("elapsed_seconds"),
                "git_commit": row.get("git_commit"),
                "score": numeric(summary.get("score")),
                "micro_score": numeric(summary.get("micro_score")),
                "passed": summary.get("passed"),
                "total": summary.get("total"),
                "build_ok": summary.get("build_ok"),
            }
        )
    return result


def score_auc(points: list[dict[str, Any]]) -> float | None:
    usable = sorted(
        (
            (numeric(point.get("elapsed_seconds")), numeric(point.get("score")))
            for point in points
            if point.get("elapsed_seconds") is not None
        ),
        key=lambda item: item[0],
    )
    if len(usable) < 2 or usable[-1][0] <= 0:
        return None
    area = 0.0
    previous_t, previous_s = 0.0, 0.0
    for current_t, current_s in usable:
        area += (current_t - previous_t) * (previous_s + current_s) / 2.0
        previous_t, previous_s = current_t, current_s
    return area / usable[-1][0]


def markdown_report(report: dict[str, Any]) -> str:
    metadata = report["metadata"]
    resume = report["resume"]
    visible = report["visible_trajectory"]
    hidden = report["hidden_trajectory"]
    final_visible = visible[-1] if visible else {}
    final_hidden = hidden[-1] if hidden else {}
    usage = report["pi_events"]["usage"]
    tool_counts = report["pi_events"]["tool_counts"]

    lines = [
        f"# PiCC experiment report: {metadata.get('run_id')}",
        "",
        "## Run",
        "",
        f"- Profile: `{metadata.get('profile')}`",
        f"- Provider/model: `{metadata.get('model', {}).get('provider')}/{metadata.get('model', {}).get('id')}`",
        f"- Thinking: `{metadata.get('model', {}).get('thinking')}`",
        f"- Termination: `{metadata.get('termination_reason')}`",
        f"- Elapsed: {numeric(metadata.get('elapsed_seconds')) / 3600:.2f} hours",
        f"- Resumed: `{'yes' if resume['resumed'] else 'no'}` ({resume['resume_count']} resume(s))",
        f"- Protocol comparable: `{'yes' if resume['protocol_comparable'] else 'no'}`",
        "",
        "## Final scores",
        "",
        "| Partition | Macro score | Micro score | Passed | Total |",
        "|---|---:|---:|---:|---:|",
        f"| Visible | {numeric(final_visible.get('score')):.4f} | {numeric(final_visible.get('micro_score')):.4f} | {final_visible.get('passed', '—')} | {final_visible.get('total', '—')} |",
        f"| Hidden | {numeric(final_hidden.get('score')):.4f} | {numeric(final_hidden.get('micro_score')):.4f} | {final_hidden.get('passed', '—')} | {final_hidden.get('total', '—')} |",
        "",
        "## Trajectory summary",
        "",
        f"- Visible score/time AUC: {report.get('visible_score_auc') if report.get('visible_score_auc') is not None else 'not available'}",
        f"- Hidden score/time AUC: {report.get('hidden_score_auc') if report.get('hidden_score_auc') is not None else 'not available'}",
        f"- Compaction starts: {report['pi_events']['event_counts'].get('compaction_start', 0)}",
        f"- Compaction completions: {report['pi_events']['event_counts'].get('compaction_end', 0)}",
        f"- Guard-blocked tool calls: {report['guard']['blocked_calls']}",
        "",
        "## Model usage reported by Pi",
        "",
        f"- Input tokens: {usage.get('input', 0)}",
        f"- Output tokens: {usage.get('output', 0)}",
        f"- Cache-read tokens: {usage.get('cache_read', 0)}",
        f"- Cache-write tokens: {usage.get('cache_write', 0)}",
        "",
        "## Tool calls",
        "",
        "| Tool | Calls |",
        "|---|---:|",
    ]
    for tool, count in sorted(tool_counts.items(), key=lambda item: (-item[1], item[0])):
        lines.append(f"| `{tool}` | {count} |")

    attempts = resume["execution_attempts"]
    if attempts:
        lines += [
            "",
            "## Execution attempts",
            "",
            "| # | Kind | Started | Ended | Rounds | Hours | Status | Termination |",
            "|---:|---|---|---|---|---:|---|---|",
        ]
        for attempt in attempts:
            first_round = attempt.get("first_round")
            last_round = attempt.get("last_round")
            if first_round is None:
                rounds = "-"
            elif last_round is None or last_round == first_round:
                rounds = str(first_round)
            else:
                rounds = f"{first_round}-{last_round}"
            lines.append(
                f"| {attempt.get('index', '-')} | {attempt.get('kind', '-')} | "
                f"{attempt.get('started_at') or '-'} | {attempt.get('ended_at') or '-'} | {rounds} | "
                f"{numeric(attempt.get('elapsed_seconds')) / 3600:.2f} | "
                f"{attempt.get('status') or '-'} | {attempt.get('termination_reason') or '-'} |"
            )
    lines += ["", "## Per-round snapshots", "", "| Round | Hours | Rust LOC | Visible score | Build |", "|---:|---:|---:|---:|---|"]
    for snapshot in report["snapshots"]:
        visible_summary = snapshot.get("visible", {})
        lines.append(
            f"| {snapshot.get('round')} | {numeric(snapshot.get('elapsed_seconds')) / 3600:.2f} | "
            f"{snapshot.get('rust_loc', 0)} | {numeric(visible_summary.get('score')):.4f} | "
            f"{visible_summary.get('build_ok', False)} |"
        )
    lines.append("")
    return "\n".join(lines)


def summarize_locked(run_id: str, run_dir: Path) -> int:
    metadata_path = run_dir / "metadata.json"
    if not metadata_path.exists():
        raise ExperimentError(f"Unknown run: {run_id}")
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    if metadata.get("status") == "running":
        raise ExperimentError(f"Run {run_id} is still running; report it after the run finishes")

    raw_resume_count = metadata.get("resume_count", 0)
    resume_count = (
        raw_resume_count
        if isinstance(raw_resume_count, int) and not isinstance(raw_resume_count, bool) and raw_resume_count >= 0
        else 0
    )
    resumed = metadata.get("resumed") is True or resume_count > 0
    raw_comparable = metadata.get("protocol_comparable")
    protocol_comparable = raw_comparable if isinstance(raw_comparable, bool) else not resumed
    raw_attempts = metadata.get("execution_attempts", [])
    execution_attempts = (
        [attempt for attempt in raw_attempts if isinstance(attempt, dict)]
        if isinstance(raw_attempts, list)
        else []
    )
    artifacts = run_dir / "artifacts"
    snapshots = read_jsonl(artifacts / "snapshots.jsonl")

    visible_rows = [
        {
            "round": snapshot.get("round"),
            "git_commit": snapshot.get("git_commit"),
            "elapsed_seconds": snapshot.get("elapsed_seconds"),
            "summary": snapshot.get("visible", {}),
        }
        for snapshot in snapshots
    ]
    hidden_rows = read_jsonl(artifacts / "hidden-scores.jsonl")

    visible_trajectory = trajectory(visible_rows)
    hidden_trajectory = trajectory(hidden_rows)
    report: dict[str, Any] = {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "metadata": metadata,
        "resume": {
            "resume_count": resume_count,
            "resumed": resumed,
            "protocol_comparable": protocol_comparable,
            "execution_attempts": execution_attempts,
        },
        "pi_events": collect_events(artifacts / "events"),
        "extension_events": collect_extension_events(artifacts / "extension-events.jsonl"),
        "guard": collect_guard(artifacts / "guard.jsonl"),
        "snapshots": snapshots,
        "visible_trajectory": visible_trajectory,
        "hidden_trajectory": hidden_trajectory,
        "visible_score_auc": score_auc(visible_trajectory),
        "hidden_score_auc": score_auc(hidden_trajectory),
    }
    atomic_write_json(run_dir / "report.json", report)
    (run_dir / "report.md").write_text(markdown_report(report), encoding="utf-8")
    print(f"Wrote {run_dir / 'report.md'}")
    print(f"Wrote {run_dir / 'report.json'}")
    return 0


def main() -> int:
    args = parse_args()
    run_id = sanitize_run_id(args.run_id)
    run_dir = REPO_ROOT / "runs" / run_id
    if not run_dir.is_dir():
        raise ExperimentError(f"Unknown run: {run_id}")
    with harness_lock(run_dir):
        return summarize_locked(run_id, run_dir)



if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ExperimentError as error:
        print(f"error: {error}", file=sys.stderr)
        raise SystemExit(1)
