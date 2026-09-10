#!/usr/bin/env python3
"""v5 results: both pre-registered endpoints per run, paired contrasts, and the v3 bridge.

Reads the v5 runs under runs/ and, if present, the bridge re-score of the v3
finals (produced by rebuilding each v3 final and running the revised study
evaluator and the in-harness fuzz oracle on it). Writes analysis/v5-results.md,
analysis/v5-results.json, and a compact analysis/v3-bridge.json. Read-only.

Usage:
    python3 analysis/v5_results.py [--bridge-dir DIR]
"""
import json
import statistics
from collections import Counter
from pathlib import Path

REPO = Path("/home/xie/picc")
import argparse
import sys
BRIDGE = Path("/tmp/claude-1003/-home-xie-picc/8b7aadf0-3d32-4755-86ac-4fecb9f08861/scratchpad/bridge")
OUT = REPO / "analysis"
IDS = [f"v5-{cond}-r{rep}" for rep in (1, 2, 3, 4) for cond in ("baseline", "tests-none")]
THRESHOLD = 0.13


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
    usage = json.load(open(run / "report.json")).get("pi_events", {}).get("usage", {})
    events = json.load(open(run / "report.json")).get("pi_events", {}).get("tool_counts", {})
    return {
        "run_id": rid,
        "condition": "tests-none" if "tests-none" in rid else "baseline",
        "replicate": meta.get("replicate"),
        "hours": round(meta["elapsed_seconds"] / 3600, 2),
        "termination": meta["termination_reason"],
        "rounds": len(snaps),
        "stalls": sum(1 for s in snaps if s.get("pi_timed_out")),
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
    }


def main() -> None:
    global BRIDGE
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bridge-dir", type=Path, default=BRIDGE)
    args = parser.parse_args()
    BRIDGE = args.bridge_dir
    import io, contextlib
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        rows = report_rows()
    text = buffer.getvalue()
    print(text)
    (OUT / "v5-results.md").write_text("# v5 results digest\n\n```\n" + text + "```\n", encoding="utf-8")
    (OUT / "v5-results.json").write_text(json.dumps(rows, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def report_rows() -> list:
    rows = [r for r in (run_row(rid) for rid in IDS) if r]
    print(f"=== v5 runs ({len(rows)}/8 complete)")
    for r in rows:
        print(f"{r['run_id']:18s} rep={r['replicate']} h={r['hours']} rounds={r['rounds']} stalls={r['stalls']} vis={r['visible']:.4f} "
              f"hidden={r['hidden']:.4f} ({r['hidden_passed']}; valid {r['hidden_valid']}, invalid {r['hidden_invalid']}) "
              f"fuzz={r['fuzz']} {r['fuzz_stages']} kinds={r['fuzz_kinds']} audit_ok={r['audit_ok']} build_ok={r['build_ok']} "
              f"tokens in/out={r['in_tokens']}/{r['out_tokens']} test_visible={r['test_visible_calls']} traj={r['traj']} fails={r['hidden_failures']}")
    print()
    by = {}
    for r in rows:
        by.setdefault(r["condition"], {})[r["replicate"]] = r
    for endpoint in ("hidden", "fuzz"):
        print(f"--- endpoint: {endpoint}")
        for cond, reps in sorted(by.items()):
            vals = [reps[k][endpoint] for k in sorted(reps) if reps[k][endpoint] is not None]
            if vals:
                print(f"  {cond:12s} n={len(vals)} median={statistics.median(vals):.4f} mean={statistics.mean(vals):.4f} range=[{min(vals):.4f}, {max(vals):.4f}]"
                      + (f" sd={statistics.stdev(vals):.4f}" if len(vals) > 1 else ""))
        deltas = []
        for rep in sorted(set(by.get("baseline", {})) & set(by.get("tests-none", {}))):
            a, b = by["tests-none"][rep][endpoint], by["baseline"][rep][endpoint]
            if a is None or b is None:
                continue
            deltas.append(a - b)
            print(f"  replicate {rep}: tests-none - baseline = {a - b:+.4f}")
        if deltas:
            consistent = sum(1 for d in deltas if d < -THRESHOLD)
            reversed_ = sum(1 for d in deltas if d > THRESHOLD)
            print(f"  paired median = {statistics.median(deltas):+.4f} (threshold {THRESHOLD}); "
                  f"replicates below -{THRESHOLD}: {consistent}/{len(deltas)}, above +{THRESHOLD}: {reversed_}/{len(deltas)}")
        print()

    print("=== v3 bridge (v3 finals re-scored under the revised oracle; descriptive only)")
    v3 = {}
    for rid in ["v3-baseline-r1", "v3-baseline-r2", "v3-baseline-r3", "v3-tests-none-r1", "v3-tests-none-r2", "v3-tests-none-r3"]:
        hp, fp = BRIDGE / f"{rid}.hidden.json", BRIDGE / f"{rid}.fuzz.json"
        if not hp.is_file():
            continue
        old = [json.loads(l) for l in open(REPO / "runs" / rid / "artifacts" / "hidden-scores.jsonl")][-1]["summary"]["score"]
        new = json.load(open(hp))["summary"]["score"]
        fz = json.load(open(fp))["summary"] if fp.is_file() else None
        v3[rid] = (old, new, None if fz is None else fz["fuzz_macro"])
        print(f"{rid:18s} corpus old={old:.4f} new(preprocessed)={new:.4f} fuzz={'-' if fz is None else round(fz['fuzz_macro'], 4)} {'' if fz is None else [round(x, 2) for x in fz['stage_pass_rates']]}")
    for label, idx in (("corpus new", 1), ("fuzz", 2)):
        deltas = []
        for rep in (1, 2, 3):
            a, b = v3.get(f"v3-tests-none-r{rep}"), v3.get(f"v3-baseline-r{rep}")
            if a and b and a[idx] is not None and b[idx] is not None:
                deltas.append(a[idx] - b[idx])
        if deltas:
            print(f"  v3 {label}: paired deltas {[round(d, 4) for d in deltas]} median {statistics.median(deltas):+.4f}")
    if v3:
        compact = {}
        for rid, (old, new, fz) in v3.items():
            stages = None
            fp = BRIDGE / f"{rid}.fuzz.json"
            if fp.is_file():
                s = json.load(open(fp))["summary"]
                stages = {"stage_pass_rates": s["stage_pass_rates"], "mismatch_kinds": s.get("mismatch_kinds")}
            compact[rid] = {"corpus_original": old, "corpus_preprocessed": new, "fuzz_macro": fz, **(stages or {})}
        (OUT / "v3-bridge.json").write_text(json.dumps(compact, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return rows


if __name__ == "__main__":
    main()
