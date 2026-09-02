#!/usr/bin/env python3
"""Evaluate one or all saved run snapshots on visible or hidden tests."""

from __future__ import annotations

import argparse
import contextlib
import fcntl
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

from common import (
    ExperimentError,
    REPO_ROOT,
    append_jsonl,
    atomic_write_json,
    docker_image_id,
    docker_mount,
    load_config,
    read_jsonl,
    sanitize_run_id,
)


# Ceiling for one post-hoc snapshot evaluation. Large enough for a full
# hidden or visible pass even when the candidate hangs its per-test timeouts
# on most inputs; reaching it records that snapshot as unevaluatable instead
# of aborting the remaining snapshots.
SNAPSHOT_EVAL_TIMEOUT_SECONDS = 7200


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--partition", choices=["visible", "hidden"], default="hidden")
    parser.add_argument("--all-snapshots", action="store_true")
    parser.add_argument("--max-stage", type=int)
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


def container_base(config: dict[str, str]) -> list[str]:
    args = [
        "docker",
        "run",
        "--rm",
        "--init",
        "--platform",
        config.get("DOCKER_PLATFORM", "linux/amd64"),
        "--read-only",
        "--tmpfs",
        "/tmp:rw,exec,nosuid,nodev,size=2g",
        "--cap-drop",
        "ALL",
        "--security-opt",
        "no-new-privileges",
        "--cpus",
        config.get("AGENT_CPUS", "8"),
        "--memory",
        config.get("AGENT_MEMORY", "16g"),
        "--pids-limit",
        config.get("AGENT_PIDS", "512"),
    ]
    if hasattr(os, "getuid") and hasattr(os, "getgid"):
        args += ["--user", f"{os.getuid()}:{os.getgid()}"]
    return args


def evaluate_snapshot(
    config: dict[str, str],
    workspace: Path,
    tests: Path,
    evaluator: Path,
    artifacts: Path,
    output_name: str,
    max_stage: int,
) -> tuple[int, str, str, Path]:
    output_path = artifacts / "evaluations" / output_name
    container_name = f"picc-peval-{os.getpid()}-{output_name.removesuffix('.json')}"
    command = container_base(config)
    command += ["--name", container_name]
    command += docker_mount(workspace, "/workspace")
    command += docker_mount(tests, "/tests", readonly=True)
    command += docker_mount(evaluator, "/opt/picc-eval", readonly=True)
    command += docker_mount(artifacts, "/run-artifacts")
    command += [
        "-e",
        "CARGO_NET_OFFLINE=true",
        "--workdir",
        "/workspace",
        config["EXPERIMENT_IMAGE"],
        "python3",
        "/opt/picc-eval/evaluate.py",
        "--workspace",
        "/workspace",
        "--tests-root",
        "/tests",
        "--manifest",
        "/tests/manifest.json",
        "--max-stage",
        str(max_stage),
        "--output",
        f"/run-artifacts/evaluations/{output_name}",
        "--summary-json",
    ]
    def captured(value: Any) -> str:
        return value if isinstance(value, str) else (value or b"").decode("utf-8", errors="replace")

    try:
        result = subprocess.run(
            command, check=False, capture_output=True, text=True, timeout=SNAPSHOT_EVAL_TIMEOUT_SECONDS
        )
    except subprocess.TimeoutExpired as error:
        # subprocess.run kills only the docker client; stop the container too,
        # then report a failed evaluation so remaining snapshots still run.
        subprocess.run(["docker", "kill", container_name], check=False, capture_output=True, text=True)
        note = f"snapshot evaluation exceeded {SNAPSHOT_EVAL_TIMEOUT_SECONDS}s and was killed"
        return 124, captured(error.stdout), note + "\n" + captured(error.stderr), output_path
    return result.returncode, result.stdout, result.stderr, output_path


def git_revision(workspace: Path, revision: str) -> str:
    result = subprocess.run(
        ["git", "rev-parse", revision],
        cwd=workspace,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise ExperimentError(f"git rev-parse {revision} failed: {result.stderr}")
    return result.stdout.strip()


def verified_evaluation_image(config: dict[str, str], metadata: dict[str, Any]) -> dict[str, str]:
    recorded = metadata.get("docker_image")
    if not isinstance(recorded, dict):
        raise ExperimentError("Run metadata has no frozen Docker image")
    recorded_name = recorded.get("name")
    recorded_id = recorded.get("id")
    if not isinstance(recorded_name, str) or not recorded_name:
        raise ExperimentError("Run metadata has no frozen Docker image name")
    if not isinstance(recorded_id, str) or not recorded_id:
        raise ExperimentError("Run metadata has no frozen Docker image ID")

    configured_name = config.get("EXPERIMENT_IMAGE")
    if configured_name != recorded_name:
        raise ExperimentError(
            f"Frozen Docker image name changed: expected {recorded_name!r}, got {configured_name!r}"
        )
    actual_id = docker_image_id(recorded_name)
    if actual_id != recorded_id:
        raise ExperimentError(
            f"Docker image {recorded_name!r} changed: expected {recorded_id}, got {actual_id}"
        )
    return {"name": recorded_name, "id": actual_id}


def evaluate_locked(args: argparse.Namespace, run_id: str, run_dir: Path) -> int:
    metadata_path = run_dir / "metadata.json"
    if not metadata_path.exists():
        raise ExperimentError(f"Unknown run: {run_id}")
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    if metadata.get("status") == "running":
        raise ExperimentError(f"Run {run_id} is still running; evaluate it after the run finishes")

    config = load_config()
    verified_image = verified_evaluation_image(config, metadata)
    evaluation_config = dict(config)
    evaluation_config["EXPERIMENT_IMAGE"] = verified_image["id"]

    workspace = run_dir / "workspace"
    artifacts = run_dir / "artifacts"
    snapshots = read_jsonl(artifacts / "snapshots.jsonl")
    if not snapshots:
        raise ExperimentError(f"No snapshots found for run {run_id}")
    if not args.all_snapshots:
        snapshots = [snapshots[-1]]

    tests = REPO_ROOT / "data" / "partitions" / args.partition
    manifest_path = tests / "manifest.json"
    if not manifest_path.exists():
        raise ExperimentError(f"Missing {args.partition} partition; run `make tests`")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    available_max = max(int(test["stage"]) for test in manifest["tests"])
    profile_max = int(metadata.get("budget", {}).get("max_stage", available_max))
    max_stage = args.max_stage or min(profile_max, available_max)

    output_log = artifacts / f"{args.partition}-scores.jsonl"
    if output_log.exists():
        output_log.unlink()

    for index, snapshot in enumerate(snapshots, start=1):
        round_number = int(snapshot["round"])
        commit = str(snapshot["git_commit"])
        print(
            f"[{index}/{len(snapshots)}] {args.partition}: round {round_number:03d}, {commit[:12]}",
            flush=True,
        )
        with tempfile.TemporaryDirectory(prefix=f".picc-{run_id}-eval-", dir=run_dir) as temporary:
            worktree = Path(temporary) / "workspace"
            result = subprocess.run(
                ["git", "worktree", "add", "--detach", str(worktree), commit],
                cwd=workspace,
                check=False,
                capture_output=True,
                text=True,
            )
            if result.returncode != 0:
                raise ExperimentError(f"git worktree failed: {result.stderr}")
            try:
                output_name = f"{args.partition}-round-{round_number:03d}.json"
                evaluated_commit = git_revision(worktree, "HEAD")
                evaluated_tree = git_revision(worktree, "HEAD^{tree}")
                expected_tree = str(snapshot.get("git_tree", ""))
                if evaluated_commit != commit:
                    raise ExperimentError("Detached evaluation commit does not match the snapshot ledger")
                if not expected_tree or evaluated_tree != expected_tree:
                    raise ExperimentError("Detached evaluation tree does not match the snapshot ledger")
                returncode, stdout, stderr, output_path = evaluate_snapshot(
                    evaluation_config,
                    worktree,
                    tests,
                    REPO_ROOT / "evaluator",
                    artifacts,
                    output_name,
                    max_stage,
                )
                (artifacts / "evaluations" / f"{args.partition}-round-{round_number:03d}.stdout.log").write_text(
                    stdout, encoding="utf-8"
                )
                (artifacts / "evaluations" / f"{args.partition}-round-{round_number:03d}.stderr.log").write_text(
                    stderr, encoding="utf-8"
                )
                full: dict[str, Any] | None = None
                if output_path.exists():
                    loaded = json.loads(output_path.read_text(encoding="utf-8"))
                    if not isinstance(loaded, dict):
                        raise ExperimentError(f"Evaluator output is not a JSON object: {output_path}")
                    loaded["snapshot"] = {
                        "git_commit": evaluated_commit,
                        "git_tree": evaluated_tree,
                    }
                    loaded["docker_image"] = dict(verified_image)
                    atomic_write_json(output_path, loaded)
                    full = loaded
                if returncode != 0 or full is None:
                    summary: dict[str, Any] = {
                        "score": 0.0,
                        "build_ok": False,
                        "error": f"evaluator exit {returncode}: {stderr[-2000:]}",
                    }
                else:
                    summary = dict(full.get("summary", {}))
                row = {
                    "partition": args.partition,
                    "round": round_number,
                    "git_commit": commit,
                    "git_tree": evaluated_tree,
                    "docker_image": dict(verified_image),
                    "elapsed_seconds": snapshot.get("elapsed_seconds"),
                    "summary": summary,
                    "output": str(output_path.relative_to(run_dir)),
                }
                append_jsonl(output_log, row)
                print(
                    f"  score={float(summary.get('score', 0.0)):.4f}, "
                    f"passed={summary.get('passed', 0)}/{summary.get('total', 0)}",
                    flush=True,
                )
            finally:
                subprocess.run(
                    ["git", "worktree", "remove", "--force", str(worktree)],
                    cwd=workspace,
                    check=False,
                    capture_output=True,
                    text=True,
                )
                subprocess.run(
                    ["git", "worktree", "prune"], cwd=workspace, check=False, capture_output=True, text=True
                )

    print(f"Wrote {output_log}")
    return 0



def main() -> int:
    args = parse_args()
    run_id = sanitize_run_id(args.run_id)
    run_dir = REPO_ROOT / "runs" / run_id
    if not run_dir.is_dir():
        raise ExperimentError(f"Unknown run: {run_id}")
    with harness_lock(run_dir):
        return evaluate_locked(args, run_id, run_dir)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ExperimentError, subprocess.TimeoutExpired) as error:
        print(f"error: {error}", file=sys.stderr)
        raise SystemExit(1)
