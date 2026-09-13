#!/usr/bin/env python3
"""v9 results (specification x tests, 2x2): both oracles on the last
buildable snapshot (primary) and on the final snapshot (comparability); each
cell paired with its replicate's baseline; the two simple effects of each
factor and the per-replicate interaction; the harness check; and the paired
resource and code secondary endpoints (docs/PRE_REGISTRATION_v9.md).
Read-only.

Writes analysis/v9-results.md and analysis/v9-results.json.

Usage:
    python3 analysis/v9_results.py
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

BASELINE = "baseline"
SPEC, TESTS, BOTH = "spec-minimal", "tests-none", "spec-minimal-tests-none"
CONDITIONS = (BASELINE, SPEC, TESTS, BOTH)
REPLICATES = (1, 2, 3)
IDS = [f"v9-{cond}-r{rep}" for rep in REPLICATES for cond in CONDITIONS]
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
        "condition": next(cond for cond in (BOTH, SPEC, TESTS, BASELINE) if f"-{cond}-" in rid),
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


def paired(by: dict, key: str, variant: str, base: str = BASELINE) -> list[tuple[int, float]]:
    out = []
    for rep in sorted(set(by.get(base, {})) & set(by.get(variant, {}))):
        a, b = by[variant][rep].get(key), by[base][rep].get(key)
        if isinstance(a, (int, float)) and isinstance(b, (int, float)):
            out.append((rep, a - b))
    return out


# (label, variant, base): the pre-registered contrasts, all paired by replicate.
CONTRASTS = [
    ("spec-minimal - baseline (spec effect, tests on demand)", SPEC, BASELINE),
    ("spec-minimal-tests-none - tests-none (spec effect, no tests)", BOTH, TESTS),
    ("tests-none - baseline (tests effect, full spec)", TESTS, BASELINE),
    ("spec-minimal-tests-none - spec-minimal (tests effect, minimal spec)", BOTH, SPEC),
    ("spec-minimal-tests-none - baseline (both factors)", BOTH, BASELINE),
]


def interaction(by: dict, key: str) -> list[tuple[int, float]]:
    """(both - tests-none) - (spec-minimal - baseline) per replicate: does the
    spec effect differ when tests are withheld?"""
    no_tests = dict(paired(by, key, BOTH, TESTS))
    with_tests = dict(paired(by, key, SPEC, BASELINE))
    return [(rep, no_tests[rep] - with_tests[rep]) for rep in sorted(set(no_tests) & set(with_tests))]


def print_deltas(label: str, deltas: list[tuple[int, float]], threshold: float | None = THRESHOLD) -> None:
    for rep, d in deltas:
        print(f"  replicate {rep}: {label} = {d:+.4f}")
    if deltas:
        ds = [d for _, d in deltas]
        line = f"  paired median = {statistics.median(ds):+.4f}"
        if threshold is not None:
            line += (f" (threshold {threshold}); replicates below -{threshold}: {sum(1 for d in ds if d < -threshold)}/{len(ds)}, "
                     f"above +{threshold}: {sum(1 for d in ds if d > threshold)}/{len(ds)}")
        print(line)


def report_rows(ids: list[str], label: str) -> list[dict]:
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
        for title2, variant, base in CONTRASTS:
            print(f"  [{title2}]")
            print_deltas(f"{variant} - {base}", paired(by, endpoint, variant, base))
        print("  [interaction: (both - tests-none) - (spec-minimal - baseline)]")
        print_deltas("interaction", interaction(by, endpoint), threshold=None)
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
        print("--- secondary endpoints (per-condition medians; paired deltas vs baseline for each cell)")
        for key, name in SECONDARY:
            meds = {cond: statistics.median([reps[k][key] for k in reps if isinstance(reps[k].get(key), (int, float))] or [float('nan')]) for cond, reps in sorted(by.items())}
            parts = []
            for variant in (SPEC, TESTS, BOTH):
                ds = [d for _, d in paired(by, key, variant)]
                if ds:
                    parts.append(f"{variant}: {[round(d, 1) for d in ds]} med {statistics.median(ds):+g}")
            print(f"  {name:20s} medians {', '.join(f'{c}={m:g}' for c, m in meds.items())}" + ("; " + "; ".join(parts) if parts else ""))
        print()
    return rows


def main() -> None:
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        rows = report_rows(IDS, "v9")
    text = buffer.getvalue()
    print(text)
    (OUT / "v9-results.md").write_text("# v9 results digest\n\n```\n" + text + "```\n", encoding="utf-8")
    (OUT / "v9-results.json").write_text(json.dumps({"v9": rows}, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
