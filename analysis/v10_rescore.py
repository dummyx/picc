#!/usr/bin/env python3
"""Re-score v10 runs under the corrected Python source audit (Amendment 2).

The batch's evaluators are frozen inside each run's materialization, so the
scoped audit cannot be applied through `study.py evaluate`. This follows the
re-score procedure of `docs/STUDY_PROTOCOL.md`: copy the materialization to a
scratch directory, point its `runs` entry at a copy of the run directory so
the frozen ledgers are never touched, drop the corrected evaluator in, and run
the hidden evaluation over every snapshot with the run's frozen configuration.

Only runs whose frozen hidden ledger contains a blocking audit finding can
change; for every other run the corrected evaluator produces the same output,
so they are listed as unchanged rather than re-run. Outputs land in
`analysis/v10-rescore/<run>/`; `runs/` is read-only here.

    python3 analysis/v10_rescore.py            # re-score the affected runs
    python3 analysis/v10_rescore.py --list     # show what would be re-scored
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "analysis" / "v10-rescore"
CORRECTED = {
    "evaluator/evaluate.py": "studies/runtime/sql/evaluate.py",
    "evaluator/sqllogictest.py": "studies/runtime/sql/sqllogictest.py",
    "evaluator/candidate_runtime.py": "studies/runtime/candidate_runtime.py",
    "scripts/evaluate_run.py": "scripts/evaluate_run.py",
}
COMPILER_CORRECTED = {
    "evaluator/evaluate.py": "studies/runtime/evaluate.py",
    "evaluator/candidate_runtime.py": "studies/runtime/candidate_runtime.py",
    "scripts/evaluate_run.py": "scripts/evaluate_run.py",
}


def hidden_rows(run_dir: Path) -> list[dict]:
    path = run_dir / "artifacts" / "hidden-scores.jsonl"
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def affected_runs() -> list[tuple[Path, list[int]]]:
    rows: list[tuple[Path, list[int]]] = []
    for run_dir in sorted((ROOT / "runs").glob("v10-*")):
        if not (run_dir / "metadata.json").is_file() or "pilot" in run_dir.name:
            continue
        blocked = [int(r["round"]) for r in hidden_rows(run_dir) if r["summary"].get("audit_blocking")]
        if blocked:
            rows.append((run_dir, blocked))
    return rows


def rescore(run_dir: Path, scratch_root: Path) -> dict:
    run_id = run_dir.name
    materialization = ROOT / "runs" / ".study-materializations" / run_id
    record = json.loads((materialization / "study-materialization.json").read_text(encoding="utf-8"))
    scratch = scratch_root / run_id
    print(f"[{run_id}] copying materialization", flush=True)
    shutil.copytree(materialization, scratch, symlinks=True, ignore=shutil.ignore_patterns("__pycache__"))
    # Replace the symlink to the real runs/ with a scratch copy of this run.
    link = scratch / "runs"
    if link.is_symlink() or link.exists():
        link.unlink() if link.is_symlink() else shutil.rmtree(link)
    (scratch / "runs").mkdir()
    print(f"[{run_id}] copying run directory", flush=True)
    shutil.copytree(run_dir, scratch / "runs" / run_id, symlinks=True)
    for stale in ("hidden-scores.jsonl", "fuzz-scores.jsonl"):
        (scratch / "runs" / run_id / "artifacts" / stale).unlink(missing_ok=True)

    corrected = CORRECTED if record["task"]["runtime"] == "sql-engine" else COMPILER_CORRECTED
    for target, source in corrected.items():
        destination = scratch / target
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / source, destination)

    env = {k: str(v) for k, v in record["effective_config"].items()}
    env.update({k: os.environ[k] for k in ("PATH", "HOME", "LANG", "TERM") if k in os.environ})
    print(f"[{run_id}] evaluating hidden partition, every snapshot", flush=True)
    result = subprocess.run(
        [sys.executable, str(scratch / "scripts" / "evaluate_run.py"), "--run-id", run_id,
         "--partition", "hidden", "--all-snapshots"],
        cwd=scratch, env=env, capture_output=True, text=True,
    )
    destination = OUTPUT / run_id
    destination.mkdir(parents=True, exist_ok=True)
    artifacts = scratch / "runs" / run_id / "artifacts"
    if (artifacts / "hidden-scores.jsonl").is_file():
        shutil.copy2(artifacts / "hidden-scores.jsonl", destination / "hidden-scores.jsonl")
    if (artifacts / "evaluations").is_dir():
        shutil.copytree(artifacts / "evaluations", destination / "evaluations", dirs_exist_ok=True)
    (destination / "rescore.log").write_text(result.stdout + "\n" + result.stderr, encoding="utf-8")

    frozen = hidden_rows(run_dir)
    updated = [json.loads(l) for l in (destination / "hidden-scores.jsonl").read_text().splitlines() if l.strip()] \
        if (destination / "hidden-scores.jsonl").is_file() else []
    summary = {
        "run_id": run_id,
        "returncode": result.returncode,
        "frozen_final": frozen[-1]["summary"]["score"] if frozen else None,
        "frozen_best": max((r["summary"]["score"] for r in frozen), default=None),
        "rescored_final": updated[-1]["summary"]["score"] if updated else None,
        "rescored_best": max((r["summary"]["score"] for r in updated), default=None),
        "snapshots": len(updated),
    }
    print(f"[{run_id}] frozen final {summary['frozen_final']} -> rescored final {summary['rescored_final']}", flush=True)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--list", action="store_true", help="show the affected runs and exit")
    args = parser.parse_args()

    rows = affected_runs()
    print(f"runs with a blocking audit finding in the frozen ledger: {len(rows)}")
    for run_dir, blocked in rows:
        print(f"  {run_dir.name}: rounds {blocked}")
    if args.list:
        return 0

    OUTPUT.mkdir(parents=True, exist_ok=True)
    summaries = []
    with tempfile.TemporaryDirectory(prefix="picc-v10-rescore-", dir="/tmp") as temporary:
        for run_dir, _ in rows:
            summaries.append(rescore(run_dir, Path(temporary)))
    (OUTPUT / "summary.json").write_text(json.dumps(summaries, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUTPUT / 'summary.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
