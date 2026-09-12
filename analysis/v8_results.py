#!/usr/bin/env python3
"""v8 results (pushed test feedback): both oracles on the last buildable
snapshot (primary) and on the final snapshot (comparability), paired
contrasts, the harness check, pushed-report counts, and the paired resource
and code secondary endpoints (docs/PRE_REGISTRATION_v8.md). v6's baseline
and tests-none rows are printed alongside for the none / on-demand / pushed
gradient, never pooled. Read-only.

Writes analysis/v8-results.md and analysis/v8-results.json.

Usage:
    python3 analysis/v8_results.py
"""
from __future__ import annotations

import contextlib
import io
import json
import statistics
import sys
from collections import Counter
from pathlib import Path

REPO = Path("/home/xie/picc")
OUT = REPO / "analysis"
sys.path.insert(0, str(OUT))
import dimensions  # noqa: E402

BASELINE, VARIANT = "baseline", "tests-pushed"
IDS = [f"v8-{cond}-r{rep}" for rep in (1, 2, 3, 4) for cond in (BASELINE, VARIANT)]
V6_IDS = [f"v6-{cond}-r{rep}" for rep in (1, 2, 3, 4) for cond in ("baseline", "tests-none")]
THRESHOLD = 0.13
SECONDARY = [
    ("out_tokens", "output tokens"), ("in_tokens", "input tokens"), ("active_minutes", "active minutes"),
    ("idle_minutes", "idle minutes"), ("assistant_turns", "assistant turns"), ("tool_calls", "tool calls"),
    ("test_visible_calls", "test_visible calls"), ("pushed_reports", "pushed reports"), ("source_loc", "source LOC"),
    ("functions", "functions"), ("self_test_programs", "self-test programs"), ("self_test_loc", "self-test LOC"),
    ("final_build_seconds", "final build s"), ("median_test_compile_ms", "compile ms/test"),
    ("compactions", "compactions"), ("bash_timeouts", "cut-offs"), ("stalls", "stalls"),
]


def last_buildable(hidden_rows: list[dict]) -> int | None:
    for index in range(len(hidden_rows) - 1, -1, -1):
        summary = hidden_rows[index].get("summary") or {}
        if summary.get("build_ok") is True and not summary.get("audit_blocking") and summary.get("audit_ok") is not False:
            return index
    return None


def run_row(rid: str) -> dict | None:
    run = REPO / "runs" / rid
    if not (run / "artifacts" / "hidden-scores.jsonl").is_file():
        return None
    meta = json.load(open(run / "metadata.json"))
    hidden_rows = [json.loads(l) for l in open(run / "artifacts" / "hidden-scores.jsonl")]
    last = hidden_rows[-1]["summary"]
    full = json.load(open(run / hidden_rows[-1]["output"]))
    valid = [t for t in full["tests"] if t["validity"] == "valid"]
    invalid = [t for t in full["tests"] if t["validity"] == "invalid"]
    fails = Counter(t["failure_type"] for t in full["tests"] if not t["passed"])
    snaps = [json.loads(l) for l in open(run / "artifacts" / "snapshots.jsonl")]
    fuzz_rows = dimensions.load_jsonl(run / "artifacts" / "fuzz-scores.jsonl")
    fuzz_final = next((r for r in fuzz_rows if r.get("role", "final") == "final"), None)
    fuzz_lb_row = next((r for r in fuzz_rows if r.get("role") == "last_buildable"), None)
    lb = last_buildable(hidden_rows)
    hidden_lb = round(float(hidden_rows[lb]["summary"]["score"]), 4) if lb is not None else 0.0
    fuzz = None if fuzz_final is None else round(float(fuzz_final["summary"]["fuzz_macro"]), 4)
    if lb is None:
        fuzz_lb = 0.0
    elif lb == len(hidden_rows) - 1:
        fuzz_lb = fuzz
    elif fuzz_lb_row is not None:
        fuzz_lb = round(float(fuzz_lb_row["summary"]["fuzz_macro"]), 4)
    else:
        fuzz_lb = None
    report = json.load(open(run / "report.json"))
    usage = report.get("pi_events", {}).get("usage", {})
    events = report.get("pi_events", {}).get("tool_counts", {})
    guard = report.get("guard", {})
    ext = dimensions.load_jsonl(run / "artifacts" / "extension-events.jsonl")
    pushed = [e for e in ext if e.get("event") == "test_pushed_end"]
    dims = dimensions.analyse(run, {}, {}) or {}
    return {
        "run_id": rid,
        "condition": VARIANT if VARIANT in rid else ("tests-none" if "tests-none" in rid else BASELINE),
        "replicate": meta.get("replicate"),
        "hours": round(meta["elapsed_seconds"] / 3600, 2),
        "termination": meta["termination_reason"],
        "rounds": len(snaps),
        "stalls": sum(1 for s in snaps if s.get("pi_timed_out")),
        "bash_timeouts": int(guard.get("bash_timeouts_fired", 0) or 0),
        "hangs": list(dims.get("hangs") or []),
        "visible": round((snaps[-1].get("visible") or {}).get("score", 0.0), 4),
        "hidden": round(last["score"], 4),
        "hidden_lb": hidden_lb,
        "last_buildable_round": None if lb is None else hidden_rows[lb]["round"],
        "hidden_passed": f"{last['passed']}/{last['total']}",
        "hidden_valid": f"{sum(t['passed'] for t in valid)}/{len(valid)}",
        "hidden_invalid": f"{sum(t['passed'] for t in invalid)}/{len(invalid)}",
        "hidden_failures": dict(fails),
        "audit_ok": last.get("audit_ok"),
        "build_ok": last.get("build_ok"),
        "fuzz": fuzz,
        "fuzz_lb": fuzz_lb,
        "fuzz_stages": None if fuzz_final is None else [round(x, 2) for x in fuzz_final["summary"]["stage_pass_rates"]],
        "fuzz_kinds": None if fuzz_final is None else fuzz_final["summary"].get("mismatch_kinds"),
        "in_tokens": usage.get("input"),
        "out_tokens": usage.get("output"),
        "test_visible_calls": events.get("test_visible", 0),
        "pushed_reports": len(pushed),
        "pushed_scores": [round(float((e.get("summary") or {}).get("score") or 0.0), 3) for e in pushed],
        "traj": [round(r["summary"].get("score", 0.0), 4) for r in hidden_rows],
        **{k: dims.get(k) for k in ("active_minutes", "idle_minutes", "assistant_turns", "tool_calls", "source_loc", "functions",
                                    "self_test_programs", "self_test_loc", "final_build_seconds", "median_test_compile_ms", "compactions")},
    }


def paired(by: dict, key: str, variant: str = VARIANT) -> list[tuple[int, float]]:
    out = []
    for rep in sorted(set(by.get(BASELINE, {})) & set(by.get(variant, {}))):
        a, b = by[variant][rep].get(key), by[BASELINE][rep].get(key)
        if isinstance(a, (int, float)) and isinstance(b, (int, float)):
            out.append((rep, a - b))
    return out


def report_rows(ids: list[str], label: str, variant: str) -> list[dict]:
    rows = [r for r in (run_row(rid) for rid in ids) if r]
    print(f"=== {label} runs ({len(rows)}/{len(ids)} complete)")
    for r in rows:
        print(f"{r['run_id']:20s} rep={r['replicate']} h={r['hours']} rounds={r['rounds']} cut-offs={r['bash_timeouts']} "
              f"vis={r['visible']:.4f} hidden={r['hidden']:.4f} lb={r['hidden_lb']:.4f}@r{r['last_buildable_round']} ({r['hidden_passed']}; valid {r['hidden_valid']}, invalid {r['hidden_invalid']}) "
              f"fuzz={r['fuzz']} lb={r['fuzz_lb']} {r['fuzz_stages']} kinds={r['fuzz_kinds']} build_ok={r['build_ok']} audit_ok={r['audit_ok']} "
              f"tokens in/out={r['in_tokens']}/{r['out_tokens']} active/idle={r['active_minutes']}/{r['idle_minutes']} turns={r['assistant_turns']} "
              f"tools={r['tool_calls']} test_visible={r['test_visible_calls']} pushed={r['pushed_reports']} {r['pushed_scores']} loc={r['source_loc']} fns={r['functions']} "
              f"self-tests={r['self_test_programs']}/{r['self_test_loc']} traj={r['traj']} fails={r['hidden_failures']}")
    print()
    by: dict = {}
    for r in rows:
        by.setdefault(r["condition"], {})[r["replicate"]] = r
    for endpoint, title in (("hidden_lb", "corpus, last buildable snapshot (PRIMARY)"), ("fuzz_lb", "fuzz, last buildable snapshot (PRIMARY)"),
                            ("hidden", "corpus, final snapshot"), ("fuzz", "fuzz, final snapshot")):
        print(f"--- endpoint: {title}")
        for cond, reps in sorted(by.items()):
            vals = [reps[k][endpoint] for k in sorted(reps) if reps[k][endpoint] is not None]
            if vals:
                print(f"  {cond:12s} n={len(vals)} median={statistics.median(vals):.4f} mean={statistics.mean(vals):.4f} range=[{min(vals):.4f}, {max(vals):.4f}]"
                      + (f" sd={statistics.stdev(vals):.4f}" if len(vals) > 1 else ""))
        deltas = paired(by, endpoint, variant)
        for rep, d in deltas:
            print(f"  replicate {rep}: {variant} - {BASELINE} = {d:+.4f}")
        if deltas:
            ds = [d for _, d in deltas]
            print(f"  paired median = {statistics.median(ds):+.4f} (threshold {THRESHOLD}); "
                  f"replicates below -{THRESHOLD}: {sum(1 for d in ds if d < -THRESHOLD)}/{len(ds)}, above +{THRESHOLD}: {sum(1 for d in ds if d > THRESHOLD)}/{len(ds)}")
        print()
    if rows:
        print("--- harness check (idle minutes, unanswered bash calls, cut-offs, cap-cut finals)")
        idle = [(r['run_id'], r['idle_minutes']) for r in rows if isinstance(r.get('idle_minutes'), (int, float))]
        print(f"  runs idling >= 5 min: {sum(1 for _, m in idle if m >= 5)}/{len(idle)} {[(rid, round(m, 1)) for rid, m in idle if m >= 5]}")
        print(f"  runs with an unanswered bash call: {sum(1 for r in rows if r.get('hangs'))}/{len(rows)}")
        print(f"  runs with a cut-off: {sum(1 for r in rows if r['bash_timeouts'])}/{len(rows)}; total cut-offs {sum(r['bash_timeouts'] for r in rows)}")
        print(f"  finals that did not build (last buildable differs): {sum(1 for r in rows if r['last_buildable_round'] != r['rounds'] - 1)}/{len(rows)}")
        fz = [r['fuzz_lb'] for r in rows if r['fuzz_lb'] is not None]
        print(f"  runs with fuzz macro < 0.9 (last buildable): {sum(1 for x in fz if x < 0.9)}/{len(fz)}; corpus < 0.30: {sum(1 for r in rows if r['hidden_lb'] < 0.3)}/{len(rows)}")
        print()
        print(f"--- secondary endpoints ({variant} - {BASELINE}, paired by replicate; per-condition medians)")
        for key, name in SECONDARY:
            deltas = paired(by, key, variant)
            meds = {cond: statistics.median([reps[k][key] for k in reps if isinstance(reps[k].get(key), (int, float))] or [float('nan')]) for cond, reps in sorted(by.items())}
            if deltas:
                ds = [d for _, d in deltas]
                print(f"  {name:20s} medians {', '.join(f'{c}={m:g}' for c, m in meds.items())}; paired deltas {[round(d, 1) for d in ds]} median {statistics.median(ds):+g}")
        print()
    return rows


def main() -> None:
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        rows = report_rows(IDS, "v8", VARIANT)
        print("=== v6 for the gradient (baseline vs tests-none on the same image; last-buildable fuzz absent in pre-v8 ledgers; never pooled)")
        v6 = report_rows(V6_IDS, "v6", "tests-none")
    text = buffer.getvalue()
    print(text)
    (OUT / "v8-results.md").write_text("# v8 results digest\n\n```\n" + text + "```\n", encoding="utf-8")
    (OUT / "v8-results.json").write_text(json.dumps({"v8": rows, "v6": v6}, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
