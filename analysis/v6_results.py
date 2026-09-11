#!/usr/bin/env python3
"""v6 results: both pre-registered endpoints per run, paired contrasts, the
harness check (idle time, unanswered calls, cut-offs), and the paired resource
and code secondary endpoints (docs/PRE_REGISTRATION_v6.md).

Per Amendment 2 the primary contrast uses every final snapshot re-scored by
the evaluator with the Rust audit scoped to src/ (both oracles, same image and
parameters); the frozen-protocol values are reported alongside. Read-only.

Writes analysis/v6-results.md, analysis/v6-results.json, and a compact
analysis/v6-rescore.json.

Usage:
    python3 analysis/v6_results.py [--rescore-dir DIR]
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
RESCORE = Path("/tmp/claude-1003/-home-xie-picc/8b7aadf0-3d32-4755-86ac-4fecb9f08861/scratchpad/v6-rescore")
sys.path.insert(0, str(OUT))
import dimensions  # noqa: E402  (analysis/dimensions.py: tokens, time, code shape)

IDS = [f"v6-{cond}-r{rep}" for rep in (1, 2, 3, 4) for cond in ("baseline", "tests-none")]
V5_IDS = [f"v5-{cond}-r{rep}" for rep in (1, 2, 3, 4) for cond in ("baseline", "tests-none")]
THRESHOLD = 0.13
SECONDARY = [
    ("out_tokens", "output tokens"), ("in_tokens", "input tokens"), ("active_minutes", "active minutes"),
    ("idle_minutes", "idle minutes"), ("assistant_turns", "assistant turns"), ("tool_calls", "tool calls"),
    ("test_visible_calls", "test_visible calls"), ("source_loc", "source LOC"), ("functions", "functions"),
    ("self_test_programs", "self-test programs"), ("self_test_loc", "self-test LOC"),
    ("final_build_seconds", "final build s"), ("median_test_compile_ms", "compile ms/test"),
    ("compactions", "compactions"), ("bash_timeouts", "cut-offs"), ("stalls", "stalls"),
]


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
    fuzz_path = run / "artifacts" / "fuzz-scores.jsonl"
    fuzz = json.loads(open(fuzz_path).readline())["summary"] if fuzz_path.is_file() else None
    report = json.load(open(run / "report.json"))
    usage = report.get("pi_events", {}).get("usage", {})
    events = report.get("pi_events", {}).get("tool_counts", {})
    guard = report.get("guard", {})
    guard_rows = dimensions.load_jsonl(run / "artifacts" / "guard.jsonl")
    cut = [r for r in guard_rows if r.get("event") == "bash_timeout_fired"]
    dims = dimensions.analyse(run, {}, {}) or {}
    rescored_hidden = rescored_fuzz = None
    rescore_audit = None
    hp, fp = RESCORE / f"{rid}.hidden.json", RESCORE / f"{rid}.fuzz.json"
    if hp.is_file():
        rh = json.load(open(hp))
        rescored_hidden = round(float(rh["summary"]["score"]), 4)
        rescore_audit = {"passed": rh["source_audit"].get("passed"), "findings": len(rh["source_audit"].get("findings") or [])}
    if fp.is_file():
        rf = json.load(open(fp))["summary"]
        rescored_fuzz = round(float(rf["fuzz_macro"]), 4)
        rescored_stages = [round(x, 2) for x in rf["stage_pass_rates"]]
    else:
        rescored_stages = None
    return {
        "run_id": rid,
        "condition": "tests-none" if "tests-none" in rid else "baseline",
        "hidden_rescored": rescored_hidden,
        "fuzz_rescored": rescored_fuzz,
        "fuzz_rescored_stages": rescored_stages,
        "rescore_audit": rescore_audit,
        "replicate": meta.get("replicate"),
        "hours": round(meta["elapsed_seconds"] / 3600, 2),
        "termination": meta["termination_reason"],
        "rounds": len(snaps),
        "stalls": sum(1 for s in snaps if s.get("pi_timed_out")),
        "bash_timeouts": int(guard.get("bash_timeouts_fired", len(cut)) or 0),
        "cut_commands": [str(r.get("subject", ""))[:100] for r in cut],
        "visible": round((snaps[-1].get("visible") or {}).get("score", 0.0), 4),
        "hidden": round(last["score"], 4),
        "hidden_passed": f"{last['passed']}/{last['total']}",
        "hidden_valid": f"{sum(t['passed'] for t in valid)}/{len(valid)}",
        "hidden_invalid": f"{sum(t['passed'] for t in invalid)}/{len(invalid)}",
        "hidden_failures": dict(fails),
        "audit_ok": last.get("audit_ok"),
        "build_ok": last.get("build_ok"),
        "fuzz": None if fuzz is None else round(fuzz["fuzz_macro"], 4),
        "fuzz_stages": None if fuzz is None else [round(x, 2) for x in fuzz["stage_pass_rates"]],
        "fuzz_kinds": None if fuzz is None else fuzz.get("mismatch_kinds"),
        "in_tokens": usage.get("input"),
        "out_tokens": usage.get("output"),
        "test_visible_calls": events.get("test_visible", 0),
        "traj": [round(r["summary"].get("score", 0.0), 4) for r in hidden_rows],
        "hangs": list(dims.get("hangs") or []),  # process_metrics: one record per bash call without a result
        **{k: dims.get(k) for k in ("active_minutes", "idle_minutes", "assistant_turns", "tool_calls", "source_loc", "functions",
                                    "self_test_programs", "self_test_loc", "final_build_seconds", "median_test_compile_ms", "compactions")},
    }


def paired(by: dict, key: str) -> list[tuple[int, float]]:
    out = []
    for rep in sorted(set(by.get("baseline", {})) & set(by.get("tests-none", {}))):
        a, b = by["tests-none"][rep].get(key), by["baseline"][rep].get(key)
        if isinstance(a, (int, float)) and isinstance(b, (int, float)):
            out.append((rep, a - b))
    return out


def report_rows(ids: list[str], label: str) -> list[dict]:
    rows = [r for r in (run_row(rid) for rid in ids) if r]
    print(f"=== {label} runs ({len(rows)}/{len(ids)} complete)")
    for r in rows:
        print(f"{r['run_id']:18s} rep={r['replicate']} h={r['hours']} rounds={r['rounds']} stalls={r['stalls']} cut-offs={r['bash_timeouts']} "
              f"vis={r['visible']:.4f} hidden={r['hidden']:.4f} ({r['hidden_passed']}; valid {r['hidden_valid']}, invalid {r['hidden_invalid']}) "
              f"fuzz={r['fuzz']} {r['fuzz_stages']} kinds={r['fuzz_kinds']} build_ok={r['build_ok']} audit_ok={r['audit_ok']} "
              f"tokens in/out={r['in_tokens']}/{r['out_tokens']} active/idle={r['active_minutes']}/{r['idle_minutes']} turns={r['assistant_turns']} "
              f"tools={r['tool_calls']} test_visible={r['test_visible_calls']} loc={r['source_loc']} fns={r['functions']} self-tests={r['self_test_programs']}/{r['self_test_loc']} "
              f"traj={r['traj']} fails={r['hidden_failures']}")
        for c in r["cut_commands"]:
            print(f"    cut off: {c!r}")
    print()
    by: dict = {}
    for r in rows:
        by.setdefault(r["condition"], {})[r["replicate"]] = r
    endpoints = []
    if rows and all(r.get("hidden_rescored") is not None and r.get("fuzz_rescored") is not None for r in rows):
        endpoints += [("hidden_rescored", "hidden (PRIMARY: Amendment 2 re-score, audit scoped to src/)"),
                      ("fuzz_rescored", "fuzz (PRIMARY: Amendment 2 re-score)")]
        changed = [(r["run_id"], r["hidden"], r["hidden_rescored"], r["fuzz"], r["fuzz_rescored"]) for r in rows
                   if r["hidden"] != r["hidden_rescored"] or r["fuzz"] != r["fuzz_rescored"]]
        print(f"--- Amendment 2 re-score: {len(rows) - len(changed)}/{len(rows)} runs reproduce their frozen values exactly; changed: "
              + (", ".join(f"{rid} hidden {h}->{hr} fuzz {f}->{fr}" for rid, h, hr, f, fr in changed) if changed else "none"))
        print()
    endpoints += [("hidden", "hidden (frozen protocol)"), ("fuzz", "fuzz (frozen protocol)")]
    for endpoint, title in endpoints:
        print(f"--- endpoint: {title}")
        for cond, reps in sorted(by.items()):
            vals = [reps[k][endpoint] for k in sorted(reps) if reps[k][endpoint] is not None]
            if vals:
                print(f"  {cond:12s} n={len(vals)} median={statistics.median(vals):.4f} mean={statistics.mean(vals):.4f} range=[{min(vals):.4f}, {max(vals):.4f}]"
                      + (f" sd={statistics.stdev(vals):.4f}" if len(vals) > 1 else ""))
        deltas = paired(by, endpoint)
        for rep, d in deltas:
            print(f"  replicate {rep}: tests-none - baseline = {d:+.4f}")
        if deltas:
            ds = [d for _, d in deltas]
            print(f"  paired median = {statistics.median(ds):+.4f} (threshold {THRESHOLD}); "
                  f"replicates below -{THRESHOLD}: {sum(1 for d in ds if d < -THRESHOLD)}/{len(ds)}, above +{THRESHOLD}: {sum(1 for d in ds if d > THRESHOLD)}/{len(ds)}")
        print()
    if rows:
        print("--- harness check (Amendment 1: idle minutes and unanswered bash calls, not round-cap stalls)")
        idle = [(r['run_id'], r['idle_minutes']) for r in rows if isinstance(r.get('idle_minutes'), (int, float))]
        print(f"  runs idling >= 5 min: {sum(1 for _, m in idle if m >= 5)}/{len(idle)} {[(rid, round(m, 1)) for rid, m in idle if m >= 5]}")
        print(f"  runs with an unanswered bash call: {sum(1 for r in rows if r.get('hangs'))}/{len(rows)}; total {sum(len(r.get('hangs') or []) for r in rows)}")
        print(f"  runs with a cut-off: {sum(1 for r in rows if r['bash_timeouts'])}/{len(rows)}; total cut-offs {sum(r['bash_timeouts'] for r in rows)}")
        print(f"  rounds ended by the 45-min cap (normal for a working agent): {sum(r['stalls'] for r in rows)} of {sum(r['rounds'] for r in rows)}")
        key_f = "fuzz_rescored" if all(r.get("fuzz_rescored") is not None for r in rows) else "fuzz"
        key_h = "hidden_rescored" if all(r.get("hidden_rescored") is not None for r in rows) else "hidden"
        fz = [r[key_f] for r in rows if r[key_f] is not None]
        print(f"  runs with fuzz macro < 0.9 ({key_f}): {sum(1 for x in fz if x < 0.9)}/{len(fz)}; corpus < 0.30 ({key_h}): {sum(1 for r in rows if r[key_h] < 0.3)}/{len(rows)}")
        print()
        print("--- secondary endpoints (tests-none - baseline, paired by replicate; per-condition medians)")
        for key, name in SECONDARY:
            deltas = paired(by, key)
            meds = {cond: statistics.median([reps[k][key] for k in reps if isinstance(reps[k].get(key), (int, float))] or [float('nan')]) for cond, reps in sorted(by.items())}
            if deltas:
                ds = [d for _, d in deltas]
                print(f"  {name:20s} medians {', '.join(f'{c}={m:g}' for c, m in meds.items())}; paired deltas {[round(d, 1) for d in ds]} median {statistics.median(ds):+g}")
        print()
    return rows


def main() -> None:
    global RESCORE
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rescore-dir", type=Path, default=RESCORE)
    RESCORE = parser.parse_args().rescore_dir
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        rows = report_rows(IDS, "v6")
        print("=== v5 for the harness check (same contrast, no default timeout; never pooled with v6)")
        v5 = report_rows(V5_IDS, "v5")
    text = buffer.getvalue()
    print(text)
    (OUT / "v6-results.md").write_text("# v6 results digest\n\n```\n" + text + "```\n", encoding="utf-8")
    (OUT / "v6-results.json").write_text(json.dumps({"v6": rows, "v5": v5}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    compact = {r["run_id"]: {"hidden_frozen": r["hidden"], "hidden_rescored": r["hidden_rescored"], "fuzz_frozen": r["fuzz"],
                             "fuzz_rescored": r["fuzz_rescored"], "fuzz_rescored_stages": r["fuzz_rescored_stages"],
                             "rescore_audit": r["rescore_audit"]} for r in rows}
    if compact:
        (OUT / "v6-rescore.json").write_text(json.dumps(compact, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
