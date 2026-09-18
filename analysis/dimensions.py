#!/usr/bin/env python3
"""Exploratory cross-batch view of the non-test dimensions: tokens, time, and
code characteristics of every main run (v2–v5), and how they relate to the two
correctness oracles. Descriptive only; nothing here was planned in advance.

Usage: python3 analysis/dimensions.py [--runs runs] [--output analysis]
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import statistics
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import process_metrics  # noqa: E402

BATCH_OF = {"v2": "v2 prompt/spec (stages 1–6)", "v3": "v3 tests (1–10)", "v4": "v4 typing (1–10)", "v5": "v5 tests, revised oracle (1–10)"}
SOURCE_GLOBS = {"rust": ["src/**/*.rs"], "typescript": ["src/**/*.ts"], "javascript": ["src/**/*.js"]}
FN_PATTERNS = {
    "rust": re.compile(r"^\s*(?:pub(?:\([^)]*\))?\s+)?(?:async\s+)?(?:unsafe\s+)?(?:extern\s+\"C\"\s+)?fn\s+[A-Za-z_]\w*"),
    "typescript": re.compile(r"^\s*(?:export\s+)?(?:async\s+)?function\s+[A-Za-z_$]\w*|^\s*(?:public|private|protected|static|readonly|\s)*(?:async\s+)?[A-Za-z_$]\w*\s*\([^;]*\)\s*(?::\s*[^{;=]+)?\{\s*$"),
    "javascript": re.compile(r"^\s*(?:export\s+)?(?:async\s+)?function\s+[A-Za-z_$]\w*|^\s*(?:static\s+)?(?:async\s+)?[A-Za-z_$]\w*\s*\([^;]*\)\s*\{\s*$"),
}
COMMENT_PATTERNS = {"rust": re.compile(r"^\s*//"), "typescript": re.compile(r"^\s*(//|/\*|\*)"), "javascript": re.compile(r"^\s*(//|/\*|\*)")}
BRANCH = re.compile(r"\b(if|else if|match|while|for|loop|case|\?\s|&&|\|\|)\b|\?\?|&&|\|\|")


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    if path.is_file():
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    return rows


def language_of(run_id: str) -> str:
    if "ts-strict" in run_id:
        return "typescript"
    if "js-untyped" in run_id:
        return "javascript"
    return "rust"


def code_characteristics(workspace: Path, language: str) -> dict[str, Any]:
    files: list[Path] = []
    for pattern in SOURCE_GLOBS[language]:
        files += [p for p in workspace.glob(pattern) if p.is_file() and "node_modules" not in p.parts and "dist" not in p.parts]
    files = sorted(set(files))
    fn_re, comment_re = FN_PATTERNS[language], COMMENT_PATTERNS[language]
    loc = comments = blank = functions = branches = unsafe = unwraps = panics = todos = tests = 0
    fn_lengths: list[int] = []
    per_file_loc: list[int] = []
    for path in files:
        text = path.read_text(encoding="utf-8", errors="replace")
        lines = text.splitlines()
        file_loc = 0
        starts: list[int] = []
        for i, line in enumerate(lines):
            if not line.strip():
                blank += 1
                continue
            file_loc += 1
            if comment_re.match(line):
                comments += 1
                continue
            if fn_re.match(line):
                functions += 1
                starts.append(i)
            branches += len(BRANCH.findall(line))
        per_file_loc.append(file_loc)
        loc += file_loc
        for a, b in zip(starts, starts[1:] + [len(lines)]):
            fn_lengths.append(sum(1 for l in lines[a:b] if l.strip()))
        unsafe += len(re.findall(r"\bunsafe\b", text))
        unwraps += len(re.findall(r"\.unwrap\(\)|\.expect\(", text))
        panics += len(re.findall(r"\b(panic!|unreachable!|todo!|unimplemented!)\b|\bthrow new Error\b", text))
        todos += len(re.findall(r"\b(TODO|FIXME|XXX)\b", text))
        tests += len(re.findall(r"#\[test\]|\bdescribe\(|\btest\(|\bit\(", text))
    return {
        "source_files": len(files),
        "source_loc": loc,
        "comment_lines": comments,
        "comment_ratio": round(comments / loc, 3) if loc else None,
        "largest_file_loc": max(per_file_loc) if per_file_loc else 0,
        "functions": functions,
        "mean_function_loc": round(statistics.mean(fn_lengths), 1) if fn_lengths else None,
        "p90_function_loc": sorted(fn_lengths)[int(0.9 * (len(fn_lengths) - 1))] if fn_lengths else None,
        "max_function_loc": max(fn_lengths) if fn_lengths else None,
        "branches_per_100_loc": round(100 * branches / loc, 1) if loc else None,
        "unsafe_blocks": unsafe,
        "unwrap_or_expect": unwraps,
        "panics_or_throws": panics,
        "todo_markers": todos,
        "inline_tests": tests,
    }


def self_test_assets(workspace: Path) -> dict[str, Any]:
    """Files the agent wrote outside the compiler source: test programs, scripts, notes."""
    skip = {".git", "target", "node_modules", "dist", "src"}
    files = [p for p in workspace.rglob("*") if p.is_file() and not (set(p.relative_to(workspace).parts[:-1]) & skip)]
    files = [p for p in files if p.name not in {"AGENTS.md", "TASK.md", "SPEC.md", "Cargo.lock", "Cargo.toml", "package.json", "tsconfig.json", ".gitignore"}]
    c_programs = [p for p in files if p.suffix == ".c"]
    scripts = [p for p in files if p.suffix in {".sh", ".py", ".js", ".ts", ".rs"}]
    notes = [p for p in files if p.suffix == ".md"]
    loc = 0
    for p in scripts + c_programs:
        try:
            loc += sum(1 for l in p.read_text(encoding="utf-8", errors="replace").splitlines() if l.strip())
        except OSError:
            pass
    return {"self_test_programs": len(c_programs), "self_test_scripts": len(scripts), "self_test_loc": loc, "notes_files": len(notes)}


def timing(run: Path, metadata: dict[str, Any]) -> dict[str, Any]:
    snapshots = load_jsonl(run / "artifacts" / "snapshots.jsonl")
    first_build = next((s.get("elapsed_seconds") for s in snapshots if (s.get("visible") or {}).get("build_ok")), None)
    best = max(((s.get("visible") or {}).get("score") or 0.0, s.get("elapsed_seconds") or 0.0) for s in snapshots) if snapshots else (None, None)
    hidden = load_jsonl(run / "artifacts" / "hidden-scores.jsonl")
    build_seconds = compile_ms = binary_kb = None
    if hidden:
        try:
            full = json.load(open(run / hidden[-1]["output"]))
            build = full.get("build") or {}
            build_seconds = round(float(build.get("elapsed_seconds")), 2) if build.get("elapsed_seconds") is not None else None
            compiles = [t["compile_seconds"] for t in full["tests"] if t.get("validity") == "valid" and t.get("passed") and t.get("compile_seconds") is not None]
            compile_ms = round(1000 * statistics.median(compiles), 2) if compiles else None
            artifact = (full.get("candidate") or {}).get("artifact")
            if artifact:
                candidate = run / "workspace" / Path(artifact).relative_to("/workspace") if str(artifact).startswith("/workspace") else None
                if candidate and candidate.is_file():
                    binary_kb = round(candidate.stat().st_size / 1024)
        except (OSError, KeyError, ValueError):
            pass
    return {
        "elapsed_minutes": round(float(metadata.get("elapsed_seconds") or 0) / 60, 1),
        "first_build_minutes": round(first_build / 60, 1) if first_build is not None else None,
        "best_visible_score": round(best[0], 4) if best[0] is not None else None,
        "best_visible_minutes": round(best[1] / 60, 1) if best[1] is not None else None,
        "rounds": len(snapshots),
        "final_build_seconds": build_seconds,
        "median_test_compile_ms": compile_ms,
        "binary_kb": binary_kb,
    }


def fuzz_lookup(run: Path, run_id: str, rescore: dict[str, Any], bridge: dict[str, Any]) -> tuple[float | None, str]:
    own = load_jsonl(run / "artifacts" / "fuzz-scores.jsonl")
    if own:
        return float(own[0]["summary"]["fuzz_macro"]), "in-harness"
    if run_id in bridge and bridge[run_id].get("fuzz_macro") is not None:
        return float(bridge[run_id]["fuzz_macro"]), "bridge re-score"
    for row in rescore.get("runs", []):
        if row.get("run_id") == run_id and row.get("fuzz_macro") is not None:
            return float(row["fuzz_macro"]), "post-hoc re-score"
    return None, "none"


def analyse(run: Path, rescore: dict[str, Any], bridge: dict[str, Any]) -> dict[str, Any] | None:
    run_id = run.name
    metadata = json.load(open(run / "metadata.json"))
    report = json.load(open(run / "report.json")) if (run / "report.json").is_file() else {}
    usage = (report.get("pi_events") or {}).get("usage") or {}
    process = process_metrics.analyse_run(run) or {}
    language = language_of(run_id)
    hidden = load_jsonl(run / "artifacts" / "hidden-scores.jsonl")
    corpus = float(hidden[-1]["summary"]["score"]) if hidden else None
    fuzz, fuzz_source = fuzz_lookup(run, run_id, rescore, bridge)
    batch = run_id.split("-")[0]
    condition = process.get("condition") or re.sub(r"^v\d+-|-r\d+$", "", run_id)
    row = {
        "run_id": run_id,
        "batch": batch,
        "condition": condition,
        "language": language,
        "replicate": metadata.get("replicate"),
        "termination": metadata.get("termination_reason"),
        "corpus_hidden": round(corpus, 4) if corpus is not None else None,
        "fuzz_macro": round(fuzz, 4) if fuzz is not None else None,
        "fuzz_source": fuzz_source,
        "input_tokens": usage.get("input"),
        "output_tokens": usage.get("output"),
        "cache_read_tokens": usage.get("cache_read"),
        "thinking_chars": process.get("thinking_chars"),
        "text_chars": process.get("text_chars"),
        "assistant_turns": process.get("assistant_turns"),
        "tool_calls": process.get("tool_calls"),
        "active_minutes": process.get("active_minutes"),
        "idle_minutes": process.get("idle_minutes"),
        "hangs": process.get("hangs"),
        "compactions": process.get("compactions"),
        "provider_retries": process.get("provider_retries"),
    }
    row.update(timing(run, metadata))
    row.update(code_characteristics(run / "workspace", language))
    row.update(self_test_assets(run / "workspace"))
    out = row.get("output_tokens") or 0
    row["fuzz_per_million_output_tokens"] = round(fuzz / (out / 1e6), 3) if fuzz is not None and out else None
    row["source_loc_per_1k_output_tokens"] = round(row["source_loc"] / (out / 1e3), 2) if out else None
    row["output_tokens_per_active_minute"] = round(out / row["active_minutes"]) if row.get("active_minutes") else None
    row["thinking_share"] = round(row["thinking_chars"] / (row["thinking_chars"] + row["text_chars"]), 3) if row.get("thinking_chars") is not None and (row.get("thinking_chars") or 0) + (row.get("text_chars") or 0) else None
    return row


def ranks(values: list[float]) -> list[float]:
    order = sorted(range(len(values)), key=lambda i: values[i])
    result = [0.0] * len(values)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
            j += 1
        avg = (i + j) / 2 + 1
        for k in range(i, j + 1):
            result[order[k]] = avg
        i = j + 1
    return result


def spearman(xs: list[float], ys: list[float]) -> float | None:
    if len(xs) < 4:
        return None
    rx, ry = ranks(xs), ranks(ys)
    mx, my = statistics.mean(rx), statistics.mean(ry)
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    den = (sum((a - mx) ** 2 for a in rx) * sum((b - my) ** 2 for b in ry)) ** 0.5
    return round(num / den, 2) if den else None


def median_or_none(values: list[Any]) -> Any:
    clean = [v for v in values if isinstance(v, (int, float))]
    if not clean:
        return None
    m = statistics.median(clean)
    return round(m, 3) if isinstance(m, float) else m


def fmt(v: Any) -> str:
    if v is None:
        return "—"
    if isinstance(v, float):
        return f"{v:.3f}" if abs(v) < 10 else f"{v:,.0f}"
    if isinstance(v, int):
        return f"{v:,}"
    return str(v)


DIMS = [
    ("output_tokens", "output tokens"),
    ("thinking_share", "thinking share of generated chars"),
    ("active_minutes", "active minutes"),
    ("idle_minutes", "idle minutes (hangs)"),
    ("assistant_turns", "assistant turns"),
    ("tool_calls", "tool calls"),
    ("first_build_minutes", "minutes to first buildable snapshot (round-quantized)"),
    ("source_loc", "compiler source LOC"),
    ("source_files", "source files"),
    ("functions", "functions"),
    ("mean_function_loc", "mean function LOC"),
    ("max_function_loc", "longest function LOC"),
    ("branches_per_100_loc", "branch points per 100 LOC"),
    ("comment_ratio", "comment ratio"),
    ("unwrap_or_expect", "unwrap/expect calls"),
    ("panics_or_throws", "panic/throw sites"),
    ("self_test_programs", "self-written C test programs"),
    ("self_test_loc", "self-test script + program LOC"),
    ("final_build_seconds", "final build seconds"),
    ("median_test_compile_ms", "median compile ms per hidden test"),
    ("fuzz_per_million_output_tokens", "fuzz macro per M output tokens"),
    ("source_loc_per_1k_output_tokens", "source LOC per k output tokens"),
]


def render(rows: list[dict[str, Any]]) -> str:
    lines = ["# Beyond the tests: tokens, time, and code across every main run", "",
             "Exploratory and descriptive (not planned in advance). One row per completed main run of the v2–v5 batches; ",
             "smoke/pilot runs excluded. Corpus scores are as stored (v2–v4 under the original oracle, v5 revised); fuzz macro is ",
             "the post-hoc re-score for v2–v4 (50 programs per stage) and the in-harness score for v5 (100 per stage). ",
             "Code characteristics are regex approximations over the final `src/` tree; function boundaries are heuristic.", ""]
    lines += ["## Per batch and condition (medians)", ""]
    groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for r in rows:
        groups[(r["batch"], r["condition"])].append(r)
    cols = ["fuzz_macro", "corpus_hidden", "output_tokens", "active_minutes", "idle_minutes", "assistant_turns", "tool_calls", "source_loc", "functions", "mean_function_loc", "self_test_programs", "first_build_minutes"]
    lines.append("| batch | condition | n | " + " | ".join(c.replace("_", " ") for c in cols) + " |")
    lines.append("|---|---|---:|" + "---:|" * len(cols))
    for (batch, condition), rs in sorted(groups.items()):
        lines.append(f"| {batch} | {condition} | {len(rs)} | " + " | ".join(fmt(median_or_none([r.get(c) for r in rs])) for c in cols) + " |")
    lines += ["", "## What moves with correctness (Spearman rank correlation)", "",
              "Pooled over all main runs, and within v5 alone (the only batch scored in-harness by both oracles). ",
              "With n this small treat |rho| below about 0.4 as noise.", ""]
    lines.append("| dimension | pooled n | rho vs fuzz | rho vs corpus | v5 n | v5 rho vs fuzz | v5 rho vs corpus |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|")
    v5 = [r for r in rows if r["batch"] == "v5"]
    for key, label in DIMS:
        def pair(rs: list[dict[str, Any]], outcome: str) -> tuple[int, float | None]:
            xs = [(r[key], r[outcome]) for r in rs if isinstance(r.get(key), (int, float)) and isinstance(r.get(outcome), (int, float))]
            return len(xs), spearman([a for a, _ in xs], [b for _, b in xs])
        n_all, rho_f = pair(rows, "fuzz_macro"); _, rho_c = pair(rows, "corpus_hidden")
        n5, rho5f = pair(v5, "fuzz_macro"); _, rho5c = pair(v5, "corpus_hidden")
        lines.append(f"| {label} | {n_all} | {fmt(rho_f)} | {fmt(rho_c)} | {n5} | {fmt(rho5f)} | {fmt(rho5c)} |")
    lines += ["", "## The same correlations without the hang lottery", "",
              "Runs that lost fewer than five minutes idle (no hang, or a hang so late it cost nothing). ",
              "If a dimension still tracks correctness here, it is not merely 'the run got to work longer'.", ""]
    clean = [r for r in rows if isinstance(r.get("idle_minutes"), (int, float)) and r["idle_minutes"] < 5]
    lines.append(f"{len(clean)} of {len(rows)} main runs never hung. Fuzz macro among them: median "
                 f"{fmt(median_or_none([r['fuzz_macro'] for r in clean]))}, min {fmt(min(r['fuzz_macro'] for r in clean if r.get('fuzz_macro') is not None))}; "
                 f"among the {len(rows) - len(clean)} that hung: median {fmt(median_or_none([r['fuzz_macro'] for r in rows if r not in clean]))}.")
    lines += ["", "| dimension | n | rho vs fuzz | rho vs corpus |", "|---|---:|---:|---:|"]
    for key, label in DIMS:
        xs = [(r[key], r["fuzz_macro"], r["corpus_hidden"]) for r in clean if isinstance(r.get(key), (int, float)) and isinstance(r.get("fuzz_macro"), (int, float)) and isinstance(r.get("corpus_hidden"), (int, float))]
        lines.append(f"| {label} | {len(xs)} | {fmt(spearman([a for a, _, _ in xs], [b for _, b, _ in xs]))} | {fmt(spearman([a for a, _, _ in xs], [c for _, _, c in xs]))} |")
    lines += ["", "## Paired within-batch contrasts (variant minus its baseline, median over replicates)", "",
              "Same replicate number = same block. Positive means the variant used or produced more.", ""]
    pairs = [("v2", "baseline", "prompt-minimal"), ("v2", "baseline", "spec-brief"), ("v2", "baseline", "spec-inline"), ("v2", "baseline", "spec-architecture"),
             ("v3", "baseline", "tests-none"), ("v4", "js-untyped", "ts-strict"), ("v5", "baseline", "tests-none")]
    pcols = ["fuzz_macro", "output_tokens", "active_minutes", "assistant_turns", "tool_calls", "source_loc", "functions", "self_test_loc", "compactions"]
    lines.append("| batch | contrast | pairs | " + " | ".join(c.replace("_", " ") for c in pcols) + " |")
    lines.append("|---|---|---:|" + "---:|" * len(pcols))
    by = {(r["batch"], r["condition"], r["replicate"]): r for r in rows}
    for batch, base, variant in pairs:
        reps = sorted({k[2] for k in by if k[0] == batch and k[1] == base} & {k[2] for k in by if k[0] == batch and k[1] == variant})
        cells = []
        for c in pcols:
            deltas = [by[(batch, variant, rep)][c] - by[(batch, base, rep)][c] for rep in reps
                      if isinstance(by[(batch, variant, rep)].get(c), (int, float)) and isinstance(by[(batch, base, rep)].get(c), (int, float))]
            cells.append(("+" if (median_or_none(deltas) or 0) > 0 else "") + fmt(median_or_none(deltas)) if deltas else "—")
        lines.append(f"| {batch} | {variant} − {base} | {len(reps)} | " + " | ".join(cells) + " |")
    lines += ["", "## Spread of the dimensions (all main runs)", ""]
    lines.append("| dimension | min | median | max |")
    lines.append("|---|---:|---:|---:|")
    for key, label in DIMS:
        vals = [r[key] for r in rows if isinstance(r.get(key), (int, float))]
        if vals:
            lines.append(f"| {label} | {fmt(min(vals))} | {fmt(median_or_none(vals))} | {fmt(max(vals))} |")
    lines += ["", "## Every run", ""]
    every = ["batch", "condition", "replicate", "fuzz_macro", "corpus_hidden", "output_tokens", "thinking_share", "active_minutes", "idle_minutes", "assistant_turns", "tool_calls", "first_build_minutes", "source_loc", "source_files", "functions", "mean_function_loc", "max_function_loc", "branches_per_100_loc", "comment_ratio", "unwrap_or_expect", "self_test_programs", "self_test_loc", "median_test_compile_ms", "binary_kb"]
    lines.append("| run | " + " | ".join(c.replace("_", " ") for c in every) + " |")
    lines.append("|---|" + "---:|" * len(every))
    for r in sorted(rows, key=lambda r: (r["batch"], r["condition"], r["replicate"] or 0)):
        lines.append(f"| {r['run_id']} | " + " | ".join(fmt(r.get(c)) for c in every) + " |")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs", type=Path, default=HERE.parent / "runs")
    parser.add_argument("--output", type=Path, default=HERE)
    args = parser.parse_args()
    rescore = json.load(open(HERE / "fuzz-rescore.json")) if (HERE / "fuzz-rescore.json").is_file() else {}
    bridge = json.load(open(HERE / "v3-bridge.json")) if (HERE / "v3-bridge.json").is_file() else {}
    rows = []
    for run in sorted(args.runs.iterdir()):
        if not re.match(r"^v[2-5]-", run.name) or "pilot" in run.name or not (run / "metadata.json").is_file():
            continue
        if not (run / "artifacts" / "hidden-scores.jsonl").is_file():
            continue
        row = analyse(run, rescore, bridge)
        if row:
            rows.append(row)
    (args.output / "dimensions.json").write_text(json.dumps(rows, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    with open(args.output / "dimensions.csv", "w", newline="", encoding="utf-8") as handle:
        fields = sorted({k for r in rows for k in r})
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    (args.output / "dimensions.md").write_text(render(rows), encoding="utf-8")
    print(f"{len(rows)} runs -> {args.output / 'dimensions.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
