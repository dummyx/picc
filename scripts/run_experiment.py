#!/usr/bin/env python3
"""Run a fixed-budget Pi + GLM-5.2 PiCC construction trajectory."""

from __future__ import annotations

import argparse
import contextlib
import fcntl
import hashlib
import json
import math
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from common import (
    ExperimentError,
    REPO_ROOT,
    api_key_for,
    append_jsonl,
    atomic_write_json,
    config_float,
    config_int,
    docker_image_id,
    docker_mount,
    docker_pi_config_mounts,
    docker_secret_env,
    host_metadata,
    load_config,
    read_jsonl,
    run,
    sanitize_run_id,
    sha256_file,
)

METADATA_SCHEMA_VERSION = 2
RESUMABLE_TERMINATION_REASONS = frozenset({"pi_process_failure", "round_timeout"})



def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", choices=["pilot", "main"])
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--replicate", type=int, help="Descriptive replicate index; not a provider seed")
    parser.add_argument("--resume", action="store_true", help="Resume an eligible completed run")
    args = parser.parse_args()
    if args.resume:
        if args.profile is not None or args.replicate is not None:
            parser.error("--resume uses the profile and replicate frozen in metadata")
    elif args.profile is None:
        parser.error("--profile is required for a new run")
    return args


def copy_control_files(run_dir: Path) -> Path:
    control = run_dir / "control"
    (control / "pi" / "extensions").mkdir(parents=True)
    for name in ("AGENTS.md", "TASK.md", "INITIAL.txt", "CONTINUE.txt"):
        shutil.copy2(REPO_ROOT / "prompts" / name, control / name)
    shutil.copy2(REPO_ROOT / "pi" / "settings.json", control / "pi" / "settings.json")
    for extension in sorted((REPO_ROOT / "pi" / "extensions").glob("*.ts")):
        shutil.copy2(extension, control / "pi" / "extensions" / extension.name)
    return control


def initialize_workspace(workspace: Path) -> None:
    workspace.mkdir(parents=True)
    (workspace / ".gitignore").write_text(
        "target/\n*.o\n*.out\n*.tmp\n.DS_Store\nAGENTS.md\nTASK.md\n.pi/\n",
        encoding="utf-8",
    )
    # Pre-create nested bind-mount targets. They remain ignored and are not product artifacts.
    (workspace / ".pi").mkdir()
    (workspace / "AGENTS.md").touch()
    (workspace / "TASK.md").touch()
    run(["git", "init", "-b", "main"], cwd=workspace)
    run(["git", "config", "user.name", "PiCC experiment harness"], cwd=workspace)
    run(["git", "config", "user.email", "harness@example.invalid"], cwd=workspace)
    run(["git", "add", ".gitignore"], cwd=workspace)
    run(["git", "commit", "-m", "harness: initialize empty product repository"], cwd=workspace)


def snapshot_workspace(workspace: Path, round_number: int) -> dict[str, Any]:
    run(["git", "add", "-A"], cwd=workspace)
    run(
        ["git", "commit", "--allow-empty", "-m", f"harness: round {round_number:03d}"],
        cwd=workspace,
    )
    commit = run(["git", "rev-parse", "HEAD"], cwd=workspace).stdout.strip()
    tree = run(["git", "rev-parse", "HEAD^{tree}"], cwd=workspace).stdout.strip()
    parent_result = run(["git", "rev-parse", "HEAD^"], cwd=workspace, check=False)
    insertions = deletions = files = 0
    if parent_result.returncode == 0:
        numstat = run(["git", "diff", "--numstat", "HEAD^", "HEAD"], cwd=workspace).stdout
        for line in numstat.splitlines():
            parts = line.split("\t", 2)
            if len(parts) != 3:
                continue
            files += 1
            if parts[0].isdigit():
                insertions += int(parts[0])
            if parts[1].isdigit():
                deletions += int(parts[1])
    rust_files = [path for path in workspace.rglob("*.rs") if ".git" not in path.parts and "target" not in path.parts]
    rust_loc = 0
    for path in rust_files:
        with contextlib.suppress(OSError):
            rust_loc += len(path.read_text(encoding="utf-8", errors="replace").splitlines())
    return {
        "round": round_number,
        "timestamp": utc_now(),
        "git_commit": commit,
        "git_tree": tree,
        "changed_files": files,
        "insertions": insertions,
        "deletions": deletions,
        "rust_files": len(rust_files),
        "rust_loc": rust_loc,
    }


def base_container_args(config: dict[str, str], *, name: str | None = None) -> list[str]:
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
    if name:
        args += ["--name", name]
    if hasattr(os, "getuid") and hasattr(os, "getgid"):
        args += ["--user", f"{os.getuid()}:{os.getgid()}"]
    return args


def run_pi_round(
    *,
    config: dict[str, str],
    run_id: str,
    round_number: int,
    workspace: Path,
    control: Path,
    artifacts: Path,
    visible_tests: Path,
    evaluator: Path,
    prompt: str,
    continuation: bool,
    timeout_seconds: float,
    api_variable: str,
    api_key: str,
    max_stage: int,
) -> dict[str, Any]:
    events = artifacts / "events"
    events.mkdir(parents=True, exist_ok=True)
    stdout_path = events / f"round-{round_number:03d}.jsonl"
    stderr_path = events / f"round-{round_number:03d}.stderr.log"
    container_name = pi_container_name(run_id, round_number)

    command = base_container_args(config, name=container_name)
    with docker_secret_env(api_variable, api_key) as env_file:
        command += ["--env-file", str(env_file)]
        for key, value in {
            "PI_OFFLINE": "1",
            "PI_SKIP_VERSION_CHECK": "1",
            "PI_TELEMETRY": "0",
            "HOME": "/run-artifacts/home",
            "PI_CODING_AGENT_DIR": "/run-artifacts/pi-global",
            "CARGO_NET_OFFLINE": "true",
            "RUST_BACKTRACE": "1",
            "PICC_WORKSPACE": "/workspace",
            "PICC_VISIBLE_TESTS": "/visible-tests",
            "PICC_ARTIFACTS": "/run-artifacts",
            "PICC_RUN_STATE": "/run-artifacts/state.json",
            "PICC_GUARD_LOG": "/run-artifacts/guard.jsonl",
            "PICC_MAX_STAGE": str(max_stage),
        }.items():
            command += ["-e", f"{key}={value}"]

        command += docker_mount(workspace, "/workspace")
        command += docker_mount(control / "AGENTS.md", "/workspace/AGENTS.md", readonly=True)
        command += docker_mount(control / "TASK.md", "/workspace/TASK.md", readonly=True)
        command += docker_pi_config_mounts(control / "pi", "/workspace/.pi")
        command += docker_mount(visible_tests, "/visible-tests", readonly=True)
        command += docker_mount(evaluator, "/opt/picc-eval", readonly=True)
        command += docker_mount(artifacts, "/run-artifacts")
        command += ["--workdir", "/workspace", config["EXPERIMENT_IMAGE"], "pi"]
        if continuation:
            command.append("--continue")
        command += [
            "--mode",
            "json",
            "--approve",
            "--provider",
            config.get("ZAI_PROVIDER", "zai"),
            "--model",
            config.get("ZAI_MODEL", "glm-5.2"),
            "--thinking",
            config.get("ZAI_THINKING", "max"),
            "--session-dir",
            "/run-artifacts/sessions",
            "--tools",
            "read,bash,edit,write,grep,find,ls,test_visible,experiment_status",
            "--no-skills",
            "--no-prompt-templates",
            "--no-themes",
        ]
        if not continuation:
            command += ["--name", run_id]
        command.append(prompt)

        started_at = utc_now()
        started = time.monotonic()
        timed_out = False
        with stdout_path.open("w", encoding="utf-8") as stdout, stderr_path.open("w", encoding="utf-8") as stderr:
            process = subprocess.Popen(command, stdout=stdout, stderr=stderr, text=True)
            try:
                returncode = process.wait(timeout=timeout_seconds)
            except subprocess.TimeoutExpired:
                timed_out = True
                subprocess.run(["docker", "kill", container_name], check=False, capture_output=True, text=True)
                returncode = process.wait(timeout=30)
        elapsed = time.monotonic() - started

    return {
        "round": round_number,
        "started_at": started_at,
        "ended_at": utc_now(),
        "elapsed_seconds": elapsed,
        "returncode": returncode,
        "timed_out": timed_out,
        "events": str(stdout_path),
        "stderr": str(stderr_path),
    }


def run_visible_evaluation(
    config: dict[str, str],
    workspace: Path,
    visible_tests: Path,
    evaluator: Path,
    artifacts: Path,
    round_number: int,
    max_stage: int,
) -> dict[str, Any]:
    output_host = artifacts / "evaluations" / f"visible-round-{round_number:03d}.json"
    output_host.parent.mkdir(parents=True, exist_ok=True)
    command = base_container_args(config)
    command += docker_mount(workspace, "/workspace")
    command += docker_mount(visible_tests, "/tests", readonly=True)
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
        f"/run-artifacts/evaluations/{output_host.name}",
        "--summary-json",
    ]
    result = subprocess.run(command, check=False, capture_output=True, text=True, timeout=3600)
    (artifacts / "evaluations" / f"visible-round-{round_number:03d}.stdout.log").write_text(result.stdout, encoding="utf-8")
    (artifacts / "evaluations" / f"visible-round-{round_number:03d}.stderr.log").write_text(result.stderr, encoding="utf-8")
    if result.returncode != 0 or not output_host.exists():
        return {
            "score": 0.0,
            "micro_score": 0.0,
            "passed": 0,
            "failed": 0,
            "total": 0,
            "build_ok": False,
            "error": f"evaluator exit {result.returncode}: {result.stderr[-2000:]}",
        }
    full = json.loads(output_host.read_text(encoding="utf-8"))
    return dict(full.get("summary", {}))


def prompt_hashes(control: Path) -> dict[str, str]:
    entries = sorted(control.rglob("*"))
    unsupported = [
        path for path in entries if path.is_symlink() or not (path.is_dir() or path.is_file())
    ]
    if unsupported:
        relative = ", ".join(str(path.relative_to(control)) for path in unsupported)
        raise ExperimentError(f"Frozen control tree contains unsupported entries: {relative}")
    paths = [path for path in entries if path.is_file()]
    if not paths:
        raise ExperimentError("Frozen control tree contains no files")
    return {str(path.relative_to(control)): sha256_file(path) for path in paths}

def pi_container_name(run_id: str, round_number: int) -> str:
    suffix = f"-{round_number:03d}"
    prefix = f"picc-{run_id}".lower().replace("_", "-")
    max_prefix_length = 63 - len(suffix)
    if len(prefix) > max_prefix_length:
        digest = hashlib.sha256(run_id.encode("utf-8")).hexdigest()[:8]
        prefix = f"{prefix[: max_prefix_length - len(digest) - 1]}-{digest}"
    return prefix + suffix


def effective_round_timeout(cap_minutes: int, remaining_seconds: float) -> float:
    if cap_minutes <= 0 or remaining_seconds <= 0:
        raise ExperimentError("Round timeout and remaining budget must be positive")
    return min(float(cap_minutes * 60), remaining_seconds)


def strict_read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        raise ExperimentError(f"Missing JSONL artifact: {path}")
    try:
        nonempty_lines = sum(
            1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
        )
        rows = read_jsonl(path)
    except (OSError, json.JSONDecodeError) as error:
        raise ExperimentError(f"Invalid JSONL artifact: {path}") from error
    if len(rows) != nonempty_lines:
        raise ExperimentError(f"JSONL artifact contains a non-object row: {path}")
    return rows


def finite_float(value: Any, field: str) -> float:
    if isinstance(value, bool):
        raise ExperimentError(f"{field} must be a finite number")
    try:
        result = float(value)
    except (TypeError, ValueError) as error:
        raise ExperimentError(f"{field} must be a finite number") from error
    if not math.isfinite(result):
        raise ExperimentError(f"{field} must be a finite number")
    return result


def positive_int(value: Any, field: str) -> int:
    if isinstance(value, bool):
        raise ExperimentError(f"{field} must be a positive integer")
    try:
        result = int(value)
    except (TypeError, ValueError) as error:
        raise ExperimentError(f"{field} must be a positive integer") from error
    if result <= 0 or str(result) != str(value):
        raise ExperimentError(f"{field} must be a positive integer")
    return result


def budget_values(metadata: dict[str, Any]) -> tuple[float, int, int, int]:
    budget = metadata.get("budget")
    if not isinstance(budget, dict):
        raise ExperimentError("Run metadata has no valid frozen budget")
    hours = finite_float(budget.get("wall_hours"), "budget.wall_hours")
    if hours <= 0:
        raise ExperimentError("budget.wall_hours must be positive")
    max_rounds = positive_int(budget.get("max_rounds"), "budget.max_rounds")
    round_timeout = positive_int(budget.get("round_timeout_minutes"), "budget.round_timeout_minutes")
    max_stage = positive_int(budget.get("max_stage"), "budget.max_stage")
    return hours, max_rounds, round_timeout, max_stage


def perfect_visible_start(snapshots: list[dict[str, Any]]) -> int | None:
    first: int | None = None
    for snapshot in snapshots:
        visible = snapshot.get("visible")
        successful = (
            isinstance(visible, dict)
            and not bool(snapshot.get("pi_timed_out"))
            and snapshot.get("pi_returncode") == 0
            and finite_float(visible.get("score", 0.0), "snapshot.visible.score") >= 1.0 - 1e-12
        )
        if successful:
            if first is None:
                first = int(snapshot["round"])
        else:
            first = None
    return first


def frozen_resume_config(metadata: dict[str, Any], current_config: dict[str, str]) -> dict[str, str]:
    stored = metadata.get("configuration")
    if not isinstance(stored, dict) or not stored:
        raise ExperimentError("Run metadata has no frozen configuration")
    if not all(isinstance(key, str) and isinstance(value, str) for key, value in stored.items()):
        raise ExperimentError("Frozen configuration must contain only string keys and values")
    config = dict(stored)

    model = metadata.get("model")
    image = metadata.get("docker_image")
    if not isinstance(model, dict) or not isinstance(image, dict):
        raise ExperimentError("Run metadata has no valid model or Docker image record")
    expected = {
        "ZAI_PROVIDER": model.get("provider"),
        "ZAI_MODEL": model.get("id"),
        "ZAI_THINKING": model.get("thinking"),
        "EXPERIMENT_IMAGE": image.get("name"),
    }
    for key, value in expected.items():
        if not isinstance(value, str) or config.get(key) != value:
            raise ExperimentError(f"Frozen configuration disagrees with metadata field {key}")

    for key in ("ZAI_API_KEY", "ZAI_CODING_CN_API_KEY"):
        value = current_config.get(key, "").strip()
        if value:
            config[key] = value
    return config


def _assert_postprocessing_absent(run_dir: Path, artifacts: Path) -> None:
    paths = [
        run_dir / "report.json",
        run_dir / "report.md",
        artifacts / "visible-scores.jsonl",
        artifacts / "hidden-scores.jsonl",
    ]
    paths += list((artifacts / "evaluations").glob("hidden-round-*"))
    existing = [str(path) for path in paths if path.exists()]
    if existing:
        raise ExperimentError(
            "Cannot resume after post-hoc evaluation or reporting. Existing: " + ", ".join(sorted(existing))
        )


def _assert_round_slots_free(artifacts: Path, round_number: int) -> None:
    paths = [
        artifacts / "events" / f"round-{round_number:03d}.jsonl",
        artifacts / "events" / f"round-{round_number:03d}.stderr.log",
        artifacts / "evaluations" / f"visible-round-{round_number:03d}.json",
        artifacts / "evaluations" / f"visible-round-{round_number:03d}.stdout.log",
        artifacts / "evaluations" / f"visible-round-{round_number:03d}.stderr.log",
    ]
    existing = [str(path) for path in paths if path.exists()]
    if existing:
        raise ExperimentError("Next round would overwrite existing artifacts: " + ", ".join(existing))


@contextlib.contextmanager
def resume_lock(run_dir: Path):
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


def plan_resume(
    *,
    run_id: str,
    run_dir: Path,
    current_config: dict[str, str],
    visible_manifest: Path,
    hidden_manifest: Path,
    current_image_id: str | None = None,
) -> dict[str, Any]:
    metadata_path = run_dir / "metadata.json"
    if not metadata_path.is_file():
        raise ExperimentError(f"Unknown run: {run_id}")
    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ExperimentError(f"Invalid run metadata: {metadata_path}") from error
    if not isinstance(metadata, dict):
        raise ExperimentError(f"Invalid run metadata object: {metadata_path}")
    schema_version = metadata.get("schema_version")
    if isinstance(schema_version, bool) or schema_version not in {1, METADATA_SCHEMA_VERSION}:
        raise ExperimentError(f"Unsupported metadata schema version: {schema_version!r}")
    if metadata.get("run_id") != run_id:
        raise ExperimentError("Run ID disagrees with metadata")
    if metadata.get("status") != "completed":
        raise ExperimentError(f"Run status must be completed to resume, got {metadata.get('status')!r}")
    previous_reason = metadata.get("termination_reason")
    if previous_reason not in RESUMABLE_TERMINATION_REASONS:
        allowed = ", ".join(sorted(RESUMABLE_TERMINATION_REASONS))
        raise ExperimentError(f"Run termination {previous_reason!r} is not resumable; allowed: {allowed}")

    profile = metadata.get("profile")
    if profile not in {"pilot", "main"}:
        raise ExperimentError(f"Invalid frozen profile: {profile!r}")
    hours, max_rounds, round_timeout_minutes, max_stage = budget_values(metadata)
    elapsed_before = finite_float(metadata.get("elapsed_seconds"), "metadata.elapsed_seconds")
    if elapsed_before < 0:
        raise ExperimentError("metadata.elapsed_seconds must not be negative")

    workspace = run_dir / "workspace"
    control = run_dir / "control"
    artifacts = run_dir / "artifacts"
    for path in (workspace, control, artifacts):
        if not path.is_dir():
            raise ExperimentError(f"Missing run directory: {path}")
    _assert_postprocessing_absent(run_dir, artifacts)

    rounds = strict_read_jsonl(artifacts / "rounds.jsonl")
    snapshots = strict_read_jsonl(artifacts / "snapshots.jsonl")
    if not rounds or len(rounds) != len(snapshots):
        raise ExperimentError("Round and snapshot ledgers must be nonempty and have equal lengths")
    expected_rounds = list(range(len(rounds)))
    if [row.get("round") for row in rounds] != expected_rounds:
        raise ExperimentError("Round ledger must be unique and sequential from zero")
    if [row.get("round") for row in snapshots] != expected_rounds:
        raise ExperimentError("Snapshot ledger must be unique and sequential from zero")

    for round_number, (round_row, snapshot) in enumerate(zip(rounds, snapshots)):
        returncode = round_row.get("returncode")
        snapshot_returncode = snapshot.get("pi_returncode")
        timed_out = round_row.get("timed_out")
        snapshot_timed_out = snapshot.get("pi_timed_out")
        if (
            isinstance(returncode, bool)
            or not isinstance(returncode, int)
            or isinstance(snapshot_returncode, bool)
            or not isinstance(snapshot_returncode, int)
        ):
            raise ExperimentError(f"Round {round_number} has an invalid Pi return code")
        if not isinstance(timed_out, bool) or not isinstance(snapshot_timed_out, bool):
            raise ExperimentError(f"Round {round_number} has an invalid timeout state")
        if snapshot_returncode != returncode:
            raise ExperimentError(f"Round {round_number} return code disagrees with its snapshot")
        if snapshot_timed_out != timed_out:
            raise ExperimentError(f"Round {round_number} timeout state disagrees with its snapshot")
        required = [
            artifacts / "events" / f"round-{round_number:03d}.jsonl",
            artifacts / "events" / f"round-{round_number:03d}.stderr.log",
            artifacts / "evaluations" / f"visible-round-{round_number:03d}.json",
            artifacts / "evaluations" / f"visible-round-{round_number:03d}.stdout.log",
            artifacts / "evaluations" / f"visible-round-{round_number:03d}.stderr.log",
        ]
        missing = [str(path) for path in required if not path.is_file()]
        if missing:
            raise ExperimentError(f"Round {round_number} is missing artifacts: " + ", ".join(missing))

    latest_round = rounds[-1]
    if previous_reason == "round_timeout" and latest_round["timed_out"] is not True:
        raise ExperimentError("round_timeout metadata disagrees with the final round")
    if previous_reason == "pi_process_failure" and (
        latest_round["timed_out"] is not False or latest_round["returncode"] == 0
    ):
        raise ExperimentError("pi_process_failure metadata disagrees with the final round")

    next_round = len(rounds)
    if next_round >= max_rounds:
        raise ExperimentError("Run has exhausted its frozen round budget")
    total_seconds = hours * 3600.0
    remaining_seconds = total_seconds - elapsed_before
    if remaining_seconds <= 0:
        raise ExperimentError("Run has exhausted its frozen active-time budget")
    latest_elapsed = finite_float(snapshots[-1].get("elapsed_seconds"), "latest snapshot elapsed_seconds")
    process_elapsed = sum(finite_float(row.get("elapsed_seconds"), "round elapsed_seconds") for row in rounds)
    if latest_elapsed > elapsed_before + 1e-6 or process_elapsed > elapsed_before + 1e-6:
        raise ExperimentError("Cumulative elapsed time is inconsistent with round artifacts")

    frozen_config = frozen_resume_config(metadata, current_config)
    profile_prefix = str(profile).upper()
    config_budget = (
        config_float(frozen_config, f"{profile_prefix}_HOURS"),
        config_int(frozen_config, f"{profile_prefix}_ROUNDS"),
        config_int(frozen_config, f"{profile_prefix}_ROUND_TIMEOUT_MINUTES"),
        config_int(frozen_config, f"{profile_prefix}_MAX_STAGE"),
    )
    if (
        not math.isclose(config_budget[0], hours, rel_tol=0.0, abs_tol=1e-12)
        or config_budget[1:] != (max_rounds, round_timeout_minutes, max_stage)
    ):
        raise ExperimentError("Frozen profile configuration disagrees with the recorded budget")
    image_name = frozen_config["EXPERIMENT_IMAGE"]
    actual_image_id = current_image_id if current_image_id is not None else docker_image_id(image_name)
    recorded_image_id = metadata["docker_image"].get("id")
    if actual_image_id != recorded_image_id:
        raise ExperimentError(
            f"Docker image {image_name!r} changed: expected {recorded_image_id}, got {actual_image_id}"
        )
    if prompt_hashes(control) != metadata.get("prompt_and_extension_hashes"):
        raise ExperimentError("Frozen prompt, settings, or extension hashes changed")
    if sha256_file(visible_manifest) != metadata.get("visible_manifest_sha256"):
        raise ExperimentError("Visible manifest hash changed")
    if sha256_file(hidden_manifest) != metadata.get("hidden_manifest_sha256"):
        raise ExperimentError("Hidden manifest hash changed")

    sessions = sorted((artifacts / "sessions").glob("*.jsonl"))
    if len(sessions) != 1:
        raise ExperimentError(f"Resume requires exactly one Pi session, found {len(sessions)}")
    session_rows = strict_read_jsonl(sessions[0])
    if not session_rows or session_rows[0].get("type") != "session" or session_rows[0].get("cwd") != "/workspace":
        raise ExperimentError("Pi session has an invalid header")
    if not any(
        row.get("type") == "session_info" and row.get("name") == run_id
        for row in session_rows
    ):
        raise ExperimentError("Pi session does not contain the frozen run name")

    head = run(["git", "rev-parse", "HEAD"], cwd=workspace).stdout.strip()
    tree = run(["git", "rev-parse", "HEAD^{tree}"], cwd=workspace).stdout.strip()
    status = run(["git", "status", "--porcelain", "--untracked-files=all"], cwd=workspace).stdout
    if status.strip():
        raise ExperimentError("Workspace has uncommitted or untracked changes")
    if head != snapshots[-1].get("git_commit") or tree != snapshots[-1].get("git_tree"):
        raise ExperimentError("Workspace HEAD does not match the latest frozen snapshot")
    for index, snapshot in enumerate(snapshots):
        commit = str(snapshot.get("git_commit", ""))
        expected_tree = str(snapshot.get("git_tree", ""))
        actual_tree = run(["git", "rev-parse", f"{commit}^{{tree}}"], cwd=workspace).stdout.strip()
        if actual_tree != expected_tree:
            raise ExperimentError(f"Snapshot {index} Git tree is invalid")
        if index:
            parent = str(snapshots[index - 1].get("git_commit", ""))
            ancestry = run(["git", "merge-base", "--is-ancestor", parent, commit], cwd=workspace, check=False)
            if ancestry.returncode != 0:
                raise ExperimentError(f"Snapshot {index} is not descended from snapshot {index - 1}")

    active = set(
        run(["docker", "ps", "--format", "{{.Names}}"], check=True).stdout.splitlines()
    )
    expected_names = {pi_container_name(run_id, index) for index in range(max_rounds)}
    if active & expected_names:
        raise ExperimentError("A Pi container for this run is still active")
    _assert_round_slots_free(artifacts, next_round)

    last_visible = snapshots[-1].get("visible")
    if not isinstance(last_visible, dict):
        raise ExperimentError("Latest snapshot has no visible evaluation summary")
    plan = {
        "metadata": metadata,
        "config": frozen_config,
        "profile": profile,
        "hours": hours,
        "max_rounds": max_rounds,
        "round_timeout_minutes": round_timeout_minutes,
        "max_stage": max_stage,
        "elapsed_before": elapsed_before,
        "remaining_seconds": remaining_seconds,
        "remaining_rounds": max_rounds - next_round,
        "next_round": next_round,
        "last_visible": last_visible,
        "perfect_first_round": perfect_visible_start(snapshots),
        "workspace_commit": head,
        "session": sessions[0],
        "snapshots": snapshots,
        "previous_reason": previous_reason,
    }
    validate_resume_history(metadata, artifacts, plan)
    return plan


def ensure_execution_attempts(metadata: dict[str, Any], plan: dict[str, Any]) -> list[dict[str, Any]]:
    attempts = metadata.get("execution_attempts")
    if attempts is None:
        if metadata.get("schema_version") not in (None, 1):
            raise ExperimentError("Current metadata schema requires execution_attempts")
        attempts = [
            {
                "index": 0,
                "kind": "initial",
                "started_at": metadata.get("started_at"),
                "ended_at": metadata.get("ended_at"),
                "status": metadata.get("status"),
                "first_round": 0,
                "last_round": plan["next_round"] - 1,
                "rounds_attempted": plan["next_round"],
                "elapsed_seconds_before": 0.0,
                "elapsed_seconds": plan["elapsed_before"],
                "termination_reason": metadata.get("termination_reason"),
                "host": metadata.get("host"),
            }
        ]
        metadata["execution_attempts"] = attempts
    if not isinstance(attempts, list) or not all(isinstance(row, dict) for row in attempts):
        raise ExperimentError("metadata.execution_attempts must be a list of objects")
    if not attempts:
        raise ExperimentError("metadata.execution_attempts must not be empty")
    cumulative_attempt_elapsed = 0.0
    for index, attempt in enumerate(attempts):
        if attempt.get("index") != index:
            raise ExperimentError("Execution attempt indexes must be sequential from zero")
        expected_kind = "initial" if index == 0 else "resume"
        if attempt.get("kind") != expected_kind:
            raise ExperimentError(f"Execution attempt {index} must have kind {expected_kind!r}")
        if attempt.get("status") not in {"completed", "aborted"}:
            raise ExperimentError(f"Execution attempt {index} is not finalized")
        elapsed_before = finite_float(
            attempt.get("elapsed_seconds_before"),
            f"execution_attempts[{index}].elapsed_seconds_before",
        )
        if not math.isclose(elapsed_before, cumulative_attempt_elapsed, rel_tol=0.0, abs_tol=1e-6):
            raise ExperimentError(f"Execution attempt {index} has inconsistent prior elapsed time")
        elapsed = finite_float(
            attempt.get("elapsed_seconds"),
            f"execution_attempts[{index}].elapsed_seconds",
        )
        if elapsed < 0:
            raise ExperimentError(f"Execution attempt {index} elapsed time must not be negative")
        cumulative_attempt_elapsed += elapsed
    if not math.isclose(
        cumulative_attempt_elapsed,
        finite_float(plan["elapsed_before"], "metadata.elapsed_seconds"),
        rel_tol=0.0,
        abs_tol=1e-6,
    ):
        raise ExperimentError("Execution attempt times disagree with cumulative metadata elapsed time")
    if attempts[-1].get("status") != metadata.get("status"):
        raise ExperimentError("Latest execution attempt status disagrees with metadata")
    if attempts[-1].get("termination_reason") != metadata.get("termination_reason"):
        raise ExperimentError("Latest execution attempt termination disagrees with metadata")
    recorded_resume_count = metadata.get("resume_count", len(attempts) - 1)
    if recorded_resume_count != len(attempts) - 1:
        raise ExperimentError("metadata.resume_count disagrees with execution_attempts")
    return attempts


def validate_resume_history(
    metadata: dict[str, Any],
    artifacts: Path,
    plan: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    attempts = ensure_execution_attempts(metadata, plan)
    resume_count = len(attempts) - 1
    interventions = metadata.get("interventions")
    if interventions is None:
        interventions = []
        metadata["interventions"] = interventions
    if not isinstance(interventions, list) or not all(
        isinstance(row, dict) for row in interventions
    ):
        raise ExperimentError("metadata.interventions must be a list of objects")
    if len(interventions) != resume_count:
        raise ExperimentError("metadata.interventions disagrees with execution_attempts")
    if resume_count and (
        metadata.get("resumed") is not True or metadata.get("protocol_comparable") is not False
    ):
        raise ExperimentError("Resumed metadata must disclose protocol noncomparability")

    events_path = artifacts / "resume-events.jsonl"
    if resume_count == 0:
        if events_path.exists() and strict_read_jsonl(events_path):
            raise ExperimentError("Unexpected resume audit records for a run with no resume attempts")
        return attempts, interventions

    events = strict_read_jsonl(events_path)
    expected = [
        (event, index)
        for index in range(1, resume_count + 1)
        for event in ("resume_started", "resume_finished")
    ]
    actual = [(row.get("event"), row.get("resume_index")) for row in events]
    if actual != expected:
        raise ExperimentError("Resume audit records are incomplete or out of sequence")
    for index, intervention in enumerate(interventions, start=1):
        if intervention.get("resume_index") != index:
            raise ExperimentError("Resume intervention indexes are out of sequence")
    return attempts, interventions


def replace_workspace_bundle(run_dir: Path, workspace: Path) -> None:
    bundle = run_dir / "workspace.git.bundle"
    temporary = run_dir / ".workspace.git.bundle.tmp"
    with contextlib.suppress(FileNotFoundError):
        temporary.unlink()
    result = subprocess.run(
        ["git", "bundle", "create", str(temporary), "--all"],
        cwd=workspace,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        with contextlib.suppress(FileNotFoundError):
            temporary.unlink()
        print(f"warning: git bundle failed: {result.stderr[-2000:]}", file=sys.stderr)
        return
    os.replace(temporary, bundle)


def execute_run(args: argparse.Namespace, run_id: str, run_dir: Path, current_config: dict[str, str]) -> int:
    partitions_root = REPO_ROOT / "data" / "partitions"
    visible_tests = partitions_root / "visible"
    hidden_tests = partitions_root / "hidden"
    visible_manifest = visible_tests / "manifest.json"
    hidden_manifest = hidden_tests / "manifest.json"
    missing = [
        str(path.relative_to(REPO_ROOT))
        for path in (visible_manifest, hidden_manifest)
        if not path.exists()
    ]
    if missing:
        raise ExperimentError(
            "Test partitions are incomplete. Run `make tests` first. Missing: " + ", ".join(missing)
        )

    workspace = run_dir / "workspace"
    artifacts = run_dir / "artifacts"
    control = run_dir / "control"
    attempt_started_at = utc_now()
    manifest_path = REPO_ROOT / "MANIFEST.sha256"
    harness_manifest_sha256 = sha256_file(manifest_path) if manifest_path.is_file() else None

    if args.resume:
        plan = plan_resume(
            run_id=run_id,
            run_dir=run_dir,
            current_config=current_config,
            visible_manifest=visible_manifest,
            hidden_manifest=hidden_manifest,
        )
        metadata = plan["metadata"]
        config = plan["config"]
        profile = str(plan["profile"])
        hours = float(plan["hours"])
        max_rounds = int(plan["max_rounds"])
        round_timeout_minutes = int(plan["round_timeout_minutes"])
        max_stage = int(plan["max_stage"])
        elapsed_before = float(plan["elapsed_before"])
        start_round = int(plan["next_round"])
        last_visible = plan["last_visible"]
        perfect_first_round = plan["perfect_first_round"]
        image_id = str(metadata["docker_image"]["id"])
        api_variable, api_key = api_key_for(config)
        review_rounds = config_int(config, "PERFECT_VISIBLE_REVIEW_ROUNDS")

        prior_status = metadata.get("status")
        prior_reason = metadata.get("termination_reason")
        prior_ended_at = metadata.get("ended_at")
        attempts = ensure_execution_attempts(metadata, plan)
        interventions = metadata.get("interventions")
        if interventions is None:
            interventions = []
            metadata["interventions"] = interventions
        if not isinstance(interventions, list) or not all(isinstance(row, dict) for row in interventions):
            raise ExperimentError("metadata.interventions must be a list of objects")
        resume_index = len(attempts)
        audit = {
            "schema_version": 1,
            "event": "resume_started",
            "resume_index": resume_index,
            "timestamp": attempt_started_at,
            "prior_status": prior_status,
            "prior_termination_reason": prior_reason,
            "prior_ended_at": prior_ended_at,
            "elapsed_seconds_before": elapsed_before,
            "remaining_seconds_before": plan["remaining_seconds"],
            "remaining_rounds_before": plan["remaining_rounds"],
            "next_round": start_round,
            "workspace_git_commit": plan["workspace_commit"],
            "session": str(plan["session"].relative_to(run_dir)),
            "docker_image_id": image_id,
            "prompt_and_extension_hashes": metadata["prompt_and_extension_hashes"],
            "visible_manifest_sha256": metadata["visible_manifest_sha256"],
            "hidden_manifest_sha256": metadata["hidden_manifest_sha256"],
            "harness_manifest_sha256": harness_manifest_sha256,
        }
        interventions.append({key: value for key, value in audit.items() if key != "event"})
        current_attempt = {
            "index": resume_index,
            "kind": "resume",
            "started_at": attempt_started_at,
            "ended_at": None,
            "status": "running",
            "first_round": start_round,
            "last_round": None,
            "rounds_attempted": 0,
            "elapsed_seconds_before": elapsed_before,
            "elapsed_seconds": None,
            "termination_reason": None,
            "host": host_metadata(),
            "harness_manifest_sha256": harness_manifest_sha256,
        }
        attempts.append(current_attempt)
        metadata["schema_version"] = METADATA_SCHEMA_VERSION
        metadata["resume_count"] = resume_index
        metadata["resumed"] = True
        metadata["protocol_comparable"] = False
        metadata["status"] = "running"
        metadata["termination_reason"] = None
        metadata["ended_at"] = None
        atomic_write_json(run_dir / "metadata.json", metadata)
        append_jsonl(artifacts / "resume-events.jsonl", audit)
    else:
        config = current_config
        profile = str(args.profile)
        profile_prefix = profile.upper()
        hours = config_float(config, f"{profile_prefix}_HOURS")
        max_rounds = config_int(config, f"{profile_prefix}_ROUNDS")
        round_timeout_minutes = config_int(config, f"{profile_prefix}_ROUND_TIMEOUT_MINUTES")
        max_stage = config_int(config, f"{profile_prefix}_MAX_STAGE")
        image_id = docker_image_id(config["EXPERIMENT_IMAGE"])
        api_variable, api_key = api_key_for(config)
        review_rounds = config_int(config, "PERFECT_VISIBLE_REVIEW_ROUNDS")
        if run_dir.exists():
            raise ExperimentError(f"Run directory already exists: {run_dir}. Use a new run ID.")
        run_dir.mkdir(parents=True)
        for path in (
            artifacts / "events",
            artifacts / "evaluations",
            artifacts / "sessions",
            artifacts / "home",
            artifacts / "pi-global",
            artifacts / "tool-evaluations",
        ):
            path.mkdir(parents=True, exist_ok=True)
        control = copy_control_files(run_dir)
        initialize_workspace(workspace)

        elapsed_before = 0.0
        start_round = 0
        last_visible: dict[str, Any] | None = None
        perfect_first_round: int | None = None

        nonsecret_config = {
            key: value
            for key, value in config.items()
            if "KEY" not in key.upper() and "TOKEN" not in key.upper() and "SECRET" not in key.upper()
        }
        current_attempt = {
            "index": 0,
            "kind": "initial",
            "started_at": attempt_started_at,
            "ended_at": None,
            "status": "running",
            "first_round": 0,
            "last_round": None,
            "rounds_attempted": 0,
            "elapsed_seconds_before": 0.0,
            "elapsed_seconds": None,
            "termination_reason": None,
            "host": host_metadata(),
            "harness_manifest_sha256": harness_manifest_sha256,
        }
        metadata = {
            "schema_version": METADATA_SCHEMA_VERSION,
            "starter_version": config.get("STARTER_VERSION", "unknown"),
            "run_id": run_id,
            "profile": profile,
            "replicate": args.replicate,
            "replicate_note": "GLM Coding Plan does not expose a deterministic sampling seed through Pi; this is an independent stochastic repetition.",
            "started_at": attempt_started_at,
            "ended_at": None,
            "status": "running",
            "host": host_metadata(),
            "configuration": nonsecret_config,
            "model": {
                "provider": config.get("ZAI_PROVIDER", "zai"),
                "id": config.get("ZAI_MODEL", "glm-5.2"),
                "thinking": config.get("ZAI_THINKING", "max"),
                "serving_revision": "provider-managed and not exposed by Coding Plan",
            },
            "docker_image": {"name": config["EXPERIMENT_IMAGE"], "id": image_id},
            "prompt_and_extension_hashes": prompt_hashes(control),
            "visible_manifest_sha256": sha256_file(visible_manifest),
            "hidden_manifest_sha256": sha256_file(hidden_manifest),
            "budget": {
                "wall_hours": hours,
                "max_rounds": max_rounds,
                "round_timeout_minutes": round_timeout_minutes,
                "max_stage": max_stage,
            },
            "resume_count": 0,
            "resumed": False,
            "protocol_comparable": True,
            "interventions": [],
            "execution_attempts": [current_attempt],
        }
        atomic_write_json(run_dir / "metadata.json", metadata)

    started_monotonic = time.monotonic()
    total_budget_seconds = hours * 3600.0
    deadline = started_monotonic + (total_budget_seconds - elapsed_before)
    termination_reason = "max_rounds"
    last_round_attempted = start_round - 1

    def cumulative_elapsed() -> float:
        return elapsed_before + (time.monotonic() - started_monotonic)

    try:
        for round_number in range(start_round, max_rounds):
            remaining_seconds = max(0.0, deadline - time.monotonic())
            if remaining_seconds <= 0:
                termination_reason = "wall_time_budget"
                break
            _assert_round_slots_free(artifacts, round_number)
            state = {
                "run_id": run_id,
                "profile": profile,
                "round": round_number,
                "max_rounds": max_rounds,
                "elapsed_seconds": cumulative_elapsed(),
                "remaining_seconds": remaining_seconds,
                "max_stage": max_stage,
                "last_visible": last_visible,
                "resume_count": metadata.get("resume_count", 0),
                "fixed_policy": "No human steering; continuation prompt is unchanged across rounds.",
            }
            atomic_write_json(artifacts / "state.json", state)
            prompt_file = control / ("INITIAL.txt" if round_number == 0 else "CONTINUE.txt")
            prompt = prompt_file.read_text(encoding="utf-8")
            effective_timeout = effective_round_timeout(round_timeout_minutes, remaining_seconds)
            print(
                f"[{run_id}] round {round_number:03d}: Pi ({effective_timeout / 60:.1f} min cap)",
                flush=True,
            )
            round_result = run_pi_round(
                config=config,
                run_id=run_id,
                round_number=round_number,
                workspace=workspace,
                control=control,
                artifacts=artifacts,
                visible_tests=visible_tests,
                evaluator=REPO_ROOT / "evaluator",
                prompt=prompt,
                continuation=round_number > 0,
                timeout_seconds=effective_timeout,
                api_variable=api_variable,
                api_key=api_key,
                max_stage=max_stage,
            )
            snapshot = snapshot_workspace(workspace, round_number)
            print(f"[{run_id}] round {round_number:03d}: visible evaluation", flush=True)
            visible = run_visible_evaluation(
                config,
                workspace,
                visible_tests,
                REPO_ROOT / "evaluator",
                artifacts,
                round_number,
                max_stage,
            )
            last_visible = visible
            snapshot.update(
                {
                    "elapsed_seconds": cumulative_elapsed(),
                    "pi_returncode": round_result["returncode"],
                    "pi_timed_out": round_result["timed_out"],
                    "visible": visible,
                }
            )
            append_jsonl(artifacts / "rounds.jsonl", round_result)
            append_jsonl(artifacts / "snapshots.jsonl", snapshot)
            last_round_attempted = round_number
            print(
                f"[{run_id}] round {round_number:03d}: score={float(visible.get('score', 0.0)):.4f}, "
                f"passed={visible.get('passed', 0)}/{visible.get('total', 0)}, rust_loc={snapshot['rust_loc']}",
                flush=True,
            )

            if round_result["timed_out"]:
                termination_reason = "round_timeout"
                break
            if round_result["returncode"] != 0:
                termination_reason = "pi_process_failure"
                break

            if float(visible.get("score", 0.0)) >= 1.0 - 1e-12:
                if perfect_first_round is None:
                    perfect_first_round = round_number
                elif round_number - perfect_first_round >= review_rounds:
                    termination_reason = "visible_complete_after_review"
                    break
            else:
                perfect_first_round = None

            if time.monotonic() >= deadline:
                termination_reason = "wall_time_budget"
                break
    except KeyboardInterrupt:
        termination_reason = "human_abort"
        print("Interrupted; finalizing run metadata.", file=sys.stderr)
    except Exception:
        termination_reason = "harness_exception"
        raise
    finally:
        ended_at = utc_now()
        attempt_elapsed = time.monotonic() - started_monotonic
        final_status = "completed" if termination_reason not in {"harness_exception", "human_abort"} else "aborted"
        current_attempt.update(
            {
                "ended_at": ended_at,
                "status": final_status,
                "last_round": last_round_attempted if last_round_attempted >= start_round else None,
                "rounds_attempted": max(0, last_round_attempted - start_round + 1),
                "elapsed_seconds": attempt_elapsed,
                "termination_reason": termination_reason,
            }
        )
        metadata["ended_at"] = ended_at
        metadata["elapsed_seconds"] = elapsed_before + attempt_elapsed
        metadata["status"] = final_status
        metadata["termination_reason"] = termination_reason
        metadata["last_visible"] = last_visible
        atomic_write_json(run_dir / "metadata.json", metadata)

        if args.resume:
            final_commit = run(["git", "rev-parse", "HEAD"], cwd=workspace, check=False).stdout.strip()
            append_jsonl(
                artifacts / "resume-events.jsonl",
                {
                    "schema_version": 1,
                    "event": "resume_finished",
                    "resume_index": current_attempt["index"],
                    "timestamp": ended_at,
                    "status": final_status,
                    "termination_reason": termination_reason,
                    "cumulative_elapsed_seconds": metadata["elapsed_seconds"],
                    "last_round": current_attempt["last_round"],
                    "final_git_commit": final_commit,
                },
            )
        replace_workspace_bundle(run_dir, workspace)

    print(f"Run finished: {run_id} ({termination_reason})")
    print(f"Artifacts: {run_dir}")
    return 0


def main() -> int:
    args = parse_args()
    run_id = sanitize_run_id(args.run_id)
    run_dir = REPO_ROOT / "runs" / run_id
    current_config = load_config()
    if args.resume:
        if not run_dir.is_dir():
            raise ExperimentError(f"Unknown run: {run_id}")
        with resume_lock(run_dir):
            return execute_run(args, run_id, run_dir, current_config)
    return execute_run(args, run_id, run_dir, current_config)



if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ExperimentError as error:
        print(f"error: {error}", file=sys.stderr)
        raise SystemExit(1)
