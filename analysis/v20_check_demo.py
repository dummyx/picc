"""What the round check (v20) would have told the agents of the v18/v19 runs
that scored 0: today's scorer with --example, in the pinned image, on each
run's final workspace (a scratch copy; nothing under runs/ is touched).
Writes <out-dir>/<run>/message.txt; the messages are kept in
analysis/v20-check-demo/. Read-only over runs/.

    python3 analysis/v20_check_demo.py [out-dir]
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import common  # noqa: E402
import run_experiment  # noqa: E402

RUNS = [
    ("v18-sql-rust-r2", "sql", "read standard input, ignored the file name"),
    ("v18-sql-python-typed-r2", "sql", "printed `1|x` rows, no `ok N` line"),
    ("v18-sql-python-r2", "sql", "printed a value where the `ok N` line goes"),
    ("v19-sql-rust-r3", "sql", "crate built in /workspace/pisql/"),
    ("v19-c18-python-typed-r2", "c18", "mypy never run; type errors"),
    ("v19-c18-rust-r1", "c18", "0 valid programs; panic"),
]
GRAFT = {
    "sql": {"evaluate.py": "sql/evaluate.py", "sqllogictest.py": "sql/sqllogictest.py", "candidate_runtime.py": "candidate_runtime.py"},
    "c18": {"evaluate.py": "evaluate.py", "candidate_runtime.py": "candidate_runtime.py", "fuzz_generator.py": "fuzz_generator.py", "fuzz_evaluate.py": "fuzz_evaluate.py"},
}
CONFIG = {"EXPERIMENT_IMAGE": "picc-experiment:0.5", "EVALUATION_MEMORY": "8g"}

out_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(tempfile.mkdtemp(prefix="picc-v20-check-demo-"))
out_dir.mkdir(parents=True, exist_ok=True)
for run_id, task, why in RUNS:
    scratch = out_dir / run_id
    if scratch.exists():
        shutil.rmtree(scratch)
    source_eval = ROOT / "runs" / ".study-materializations" / run_id / "evaluator"
    evaluator = scratch / "evaluator"
    shutil.copytree(source_eval, evaluator)
    for target, src in GRAFT[task].items():
        shutil.copy2(ROOT / "studies" / "runtime" / src, evaluator / target)
    shutil.copytree(ROOT / "studies" / task / "example", evaluator / "example")
    workspace = scratch / "workspace"
    shutil.copytree(ROOT / "runs" / run_id / "workspace", workspace, symlinks=True, ignore=shutil.ignore_patterns(".git"))
    # One visible test keeps the run short; the check needs only the build and the example.
    tests = ROOT / "runs" / ".study-materializations" / run_id / "data" / "partitions" / "visible"
    manifest = json.loads((tests / "manifest.json").read_text())
    first = sorted(manifest["tests"], key=lambda r: (int(r["stage"]), str(r["id"])))[0]
    artifacts = scratch / "artifacts"
    (artifacts / "evaluations").mkdir(parents=True)
    command = common.evaluation_command(
        CONFIG, container_name=f"picc-demo-{run_id}", workspace=workspace, tests=tests,
        evaluator=evaluator, artifacts=artifacts, output_name="check.json", max_stage=int(first["stage"]),
    )
    command.insert(command.index("--summary-json"), "--test-id")
    command.insert(command.index("--summary-json"), first["id"])
    result = subprocess.run(command, capture_output=True, text=True, timeout=1800)
    output = artifacts / "evaluations" / "check.json"
    if result.returncode != 0 or not output.exists():
        visible = {"score": 0.0, "error": f"evaluator exit {result.returncode}: {result.stderr[-500:]}"}
    else:
        visible = json.loads(output.read_text())["summary"]
    message = run_experiment.round_check_message(visible, "Continue.\n")
    (scratch / "message.txt").write_text(message)
    print(f"\n######## {run_id}  (what the v18/v19 analysis found: {why})\n")
    print(message)
