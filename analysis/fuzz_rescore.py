#!/usr/bin/env python3
"""Aggregate a differential-fuzz re-score of stored cohort finals.

Input: one JSON per run written by `analysis/fuzz_differential.py --json`, named
`<run-id>.json`, in --results-dir. Each run's cohort, condition, replicate, and
corpus hidden score are read from runs/<id>/.

Output: a Markdown report and a JSON table comparing the corpus oracle (hidden
macro score) with the fuzz oracle (share of generated programs on which the
candidate agrees with GCC), including the pre-registered paired contrasts under
both oracles and the within-cohort rank agreement between them. Descriptive
only: the fuzz pass rate is not the pre-registered primary endpoint.

Usage:
    python3 analysis/fuzz_rescore.py --results-dir <dir> \
        --markdown analysis/fuzz-rescore.md --json analysis/fuzz-rescore.json
"""

from __future__ import annotations

import argparse
import json
import statistics
from collections import Counter
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
RUNS_ROOT = REPO_ROOT / "runs"

COHORTS = {
    "v2": {"title": "v2 (pilot profile, stages 1–6, Rust)", "baseline": "baseline", "contrast": None},
    "v3": {"title": "v3 (main profile, stages 1–10, Rust)", "baseline": "baseline", "contrast": ("tests-none", "baseline")},
    "v4": {"title": "v4 (main profile, stages 1–10, TypeScript vs JavaScript)", "baseline": "js-untyped", "contrast": ("ts-strict", "js-untyped")},
}
# Hidden scores recorded as 0.0 by an audit false positive that was later
# corrected in the report (analysis/report.md §3.2). The corrected value is
# used for the corpus column and flagged.
CORPUS_OVERRIDES = {"v2-prompt-minimal-r3": 0.8773}


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def last_hidden_score(run: Path) -> float | None:
    path = run / "artifacts" / "hidden-scores.jsonl"
    if not path.is_file():
        return None
    rows = [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if not rows:
        return None
    summary = json.loads(rows[-1]).get("summary") or {}
    return float(summary.get("score") or 0.0)


def rank(values: list[float]) -> list[float]:
    """Average ranks (1 = smallest), ties averaged."""
    order = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0.0] * len(values)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
            j += 1
        mean_rank = (i + j) / 2 + 1
        for k in range(i, j + 1):
            ranks[order[k]] = mean_rank
        i = j + 1
    return ranks


def spearman(x: list[float], y: list[float]) -> float | None:
    if len(x) < 3 or len(set(x)) < 2 or len(set(y)) < 2:
        return None
    rx, ry = rank(x), rank(y)
    mx, my = statistics.mean(rx), statistics.mean(ry)
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    den = (sum((a - mx) ** 2 for a in rx) * sum((b - my) ** 2 for b in ry)) ** 0.5
    return round(num / den, 3) if den else None


def stage_profile(stages_dir: Path | None, run_id: str, max_stage: int) -> dict[str, Any]:
    """Per-stage fuzz pass rates and their mean, the fuzz analogue of the corpus macro score.

    Each stage's programs use only that stage's cumulative feature subset, so a
    compiler with one broken stage-10 feature still scores on stages 1-9
    instead of failing every stage-10 program.
    """
    if stages_dir is None:
        return {"fuzz_stage_pass": None, "fuzz_macro": None}
    rates: list[float | None] = []
    for stage in range(1, int(max_stage or 0) + 1):
        result = load_json(stages_dir / f"{run_id}.stage{stage}.json")
        if not result:
            rates.append(None)
            continue
        mismatches = result.get("mismatches") or []
        count = int(result.get("checked") or 0) + sum(1 for m in mismatches if m.get("kind") != "wrong_behavior")
        rates.append(round((count - len(mismatches)) / count, 4) if count else None)
    known = [rate for rate in rates if rate is not None]
    return {
        "fuzz_stage_pass": rates,
        "fuzz_macro": round(statistics.mean(known), 4) if known and len(known) == len(rates) else None,
    }


def collect(results_dir: Path, stages_dir: Path | None = None) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in sorted(results_dir.glob("*.json")):
        run_id = path.stem
        run = RUNS_ROOT / run_id
        study = load_json(run / "study-metadata.json")
        metadata = load_json(run / "metadata.json")
        if not study or not metadata:
            continue
        result = load_json(path)
        condition = study.get("condition") or {}
        cohort = run_id.split("-", 1)[0]
        count = int(result.get("count") or result.get("generated") or 0)
        mismatches = result.get("mismatches") or []
        if not count and isinstance(mismatches, list):
            count = int(result.get("checked") or 0) + sum(1 for m in mismatches if m.get("kind") != "wrong_behavior")
        kinds = Counter(str(m.get("kind")) for m in mismatches)
        crashes = sum(
            1
            for m in mismatches
            if m.get("kind") == "wrong_behavior" and ("status -" in str(m.get("detail", "")) or "status 139" in str(m.get("detail", "")))
        )
        failed = bool(result.get("build_failed") or result.get("fuzz_failed"))
        passed = None if failed or not count else count - len(mismatches)
        corpus = last_hidden_score(run)
        rows.append(
            {
                "run_id": run_id,
                "cohort": cohort,
                "condition": condition.get("id"),
                "language": (condition.get("candidate") or {}).get("language"),
                "replicate": metadata.get("replicate"),
                "max_stage": (metadata.get("budget") or {}).get("max_stage"),
                "corpus_hidden": corpus,
                "corpus_hidden_reported": CORPUS_OVERRIDES.get(run_id, corpus),
                "corpus_override": run_id in CORPUS_OVERRIDES,
                "fuzz_count": count,
                "fuzz_passed": passed,
                "fuzz_pass_rate": None if passed is None else round(passed / count, 4),
                "fuzz_mismatch_kinds": dict(kinds),
                "fuzz_crashes": crashes,
                "fuzz_failed": failed,
                **stage_profile(stages_dir, run_id, int((metadata.get("budget") or {}).get("max_stage") or 0)),
            }
        )
    return rows


def median(values: list[float]) -> float | None:
    return round(statistics.median(values), 4) if values else None


def fmt(value: Any, digits: int = 4) -> str:
    if value is None:
        return "-"
    if isinstance(value, float):
        return f"{value:.{digits}f}"
    return str(value)


def render(rows: list[dict[str, Any]]) -> tuple[str, dict[str, Any]]:
    lines = [
        "# Fuzz re-score of stored cohort finals",
        "",
        "Every cohort final snapshot was exported from its run workspace, rebuilt inside the pinned",
        "image exactly as the evaluator builds it, and fuzzed on the host against GCC with",
        "`analysis/fuzz_differential.py` (seed 20260830, stage limit = the cohort's task scope).",
        "**Fuzz pass rate** = share of generated programs on which the candidate's compiled output",
        "agrees with GCC's exit status and stdout; rejecting a valid program, failing to assemble,",
        "crashing, and wrong results all count as failures. **Full scope** = 300 programs using the",
        "cohort's whole feature set at once, so one broken feature fails every program. **Fuzz macro**",
        "= mean over stages 1..K of the pass rate on 100 programs restricted to that stage's cumulative",
        "subset, the fuzz analogue of the corpus macro score. The corpus column is the pre-registered",
        "hidden macro score. This is a descriptive re-score, not a change to any primary endpoint.",
        "",
    ]
    summary: dict[str, Any] = {"cohorts": {}, "runs": rows}
    for cohort, spec in COHORTS.items():
        group = [row for row in rows if row["cohort"] == cohort]
        if not group:
            continue
        group.sort(key=lambda r: (str(r["condition"]), r["replicate"] or 0))
        lines += [f"## {spec['title']}", "", "| Run | Condition | Rep | Corpus hidden | Fuzz macro (mean over stages) | Per-stage fuzz pass (stage 1→K) | Full-scope fuzz pass | Failure kinds at full scope |", "|---|---|---:|---:|---:|---|---:|---|"]
        for row in group:
            corpus = fmt(row["corpus_hidden_reported"]) + (" \\*" if row["corpus_override"] else "")
            kinds = ", ".join(f"{k}={v}" for k, v in sorted(row["fuzz_mismatch_kinds"].items())) or ("failed" if row["fuzz_failed"] else "none")
            if row["fuzz_crashes"]:
                kinds += f" (crashes={row['fuzz_crashes']})"
            profile = " ".join("-" if r is None else f"{r:.2f}" for r in row["fuzz_stage_pass"]) if row["fuzz_stage_pass"] else "-"
            lines.append(f"| `{row['run_id']}` | `{row['condition']}` | {row['replicate']} | {corpus} | {fmt(row['fuzz_macro'])} | {profile} | {fmt(row['fuzz_pass_rate'])} | {kinds} |")
        lines.append("")

        by_condition: dict[str, list[dict[str, Any]]] = {}
        for row in group:
            by_condition.setdefault(str(row["condition"]), []).append(row)
        def fuzz_key(row: dict[str, Any]) -> float | None:
            return row["fuzz_macro"] if row["fuzz_macro"] is not None else row["fuzz_pass_rate"]

        lines += ["| Condition | n | Corpus median | Fuzz macro median | Fuzz macro range | Full-scope fuzz median |", "|---|---:|---:|---:|---|---:|"]
        cohort_summary: dict[str, Any] = {"conditions": {}, "contrast": None, "spearman_corpus_vs_fuzz_macro": None, "spearman_corpus_vs_fuzz_full": None}
        for condition, crow in sorted(by_condition.items()):
            corpus_values = [r["corpus_hidden_reported"] for r in crow if r["corpus_hidden_reported"] is not None]
            macro_values = [fuzz_key(r) for r in crow if fuzz_key(r) is not None]
            full_values = [r["fuzz_pass_rate"] for r in crow if r["fuzz_pass_rate"] is not None]
            cohort_summary["conditions"][condition] = {
                "n": len(crow),
                "corpus_median": median(corpus_values),
                "fuzz_macro_median": median(macro_values),
                "fuzz_macro_range": [min(macro_values), max(macro_values)] if macro_values else None,
                "fuzz_full_median": median(full_values),
            }
            rng = f"{min(macro_values):.3f}–{max(macro_values):.3f}" if macro_values else "-"
            lines.append(f"| `{condition}` | {len(crow)} | {fmt(median(corpus_values))} | {fmt(median(macro_values))} | {rng} | {fmt(median(full_values))} |")
        lines.append("")

        paired = [r for r in group if r["corpus_hidden_reported"] is not None and fuzz_key(r) is not None]
        rho_macro = spearman([r["corpus_hidden_reported"] for r in paired], [fuzz_key(r) for r in paired])
        paired_full = [r for r in group if r["corpus_hidden_reported"] is not None and r["fuzz_pass_rate"] is not None]
        rho_full = spearman([r["corpus_hidden_reported"] for r in paired_full], [r["fuzz_pass_rate"] for r in paired_full])
        cohort_summary["spearman_corpus_vs_fuzz_macro"] = rho_macro
        cohort_summary["spearman_corpus_vs_fuzz_full"] = rho_full
        lines.append(f"Rank agreement with the corpus across the cohort's {len(paired)} finals (Spearman ρ): fuzz macro {fmt(rho_macro, 3)}, full-scope fuzz {fmt(rho_full, 3)}.")
        lines.append("")

        contrast = spec["contrast"]
        if contrast:
            variant, base = contrast
            deltas = []
            lines += [f"Pre-registered contrast `{variant}` − `{base}`, paired by replicate:", "", "| Rep | Corpus Δ | Fuzz macro Δ | Full-scope fuzz Δ |", "|---:|---:|---:|---:|"]
            for rep in sorted({r["replicate"] for r in group}):
                v = next((r for r in group if r["condition"] == variant and r["replicate"] == rep), None)
                b = next((r for r in group if r["condition"] == base and r["replicate"] == rep), None)
                if not v or not b or fuzz_key(v) is None or fuzz_key(b) is None:
                    continue
                corpus_delta = v["corpus_hidden_reported"] - b["corpus_hidden_reported"]
                macro_delta = fuzz_key(v) - fuzz_key(b)
                full_delta = (v["fuzz_pass_rate"] or 0.0) - (b["fuzz_pass_rate"] or 0.0)
                deltas.append({"replicate": rep, "corpus_delta": round(corpus_delta, 4), "fuzz_macro_delta": round(macro_delta, 4), "fuzz_full_delta": round(full_delta, 4)})
                lines.append(f"| {rep} | {corpus_delta:+.4f} | {macro_delta:+.4f} | {full_delta:+.4f} |")
            if deltas:
                cm = statistics.median([d["corpus_delta"] for d in deltas])
                mm = statistics.median([d["fuzz_macro_delta"] for d in deltas])
                fm = statistics.median([d["fuzz_full_delta"] for d in deltas])
                lines.append(f"| median | {cm:+.4f} | {mm:+.4f} | {fm:+.4f} |")
                cohort_summary["contrast"] = {"variant": variant, "baseline": base, "deltas": deltas, "corpus_median": round(cm, 4), "fuzz_macro_median": round(mm, 4), "fuzz_full_median": round(fm, 4)}
            lines.append("")
        summary["cohorts"][cohort] = cohort_summary

    lines += [
        "\\* Corpus score recorded as 0.0 by an audit false positive and corrected post hoc (report §3.2).",
        "",
    ]
    return "\n".join(lines), summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results-dir", type=Path, required=True)
    parser.add_argument("--stages-dir", type=Path, help="per-stage results named <run-id>.stage<N>.json")
    parser.add_argument("--markdown", type=Path)
    parser.add_argument("--json", type=Path)
    args = parser.parse_args()
    rows = collect(args.results_dir, args.stages_dir)
    markdown, summary = render(rows)
    if args.markdown:
        args.markdown.write_text(markdown, encoding="utf-8")
    if args.json:
        args.json.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(markdown)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
