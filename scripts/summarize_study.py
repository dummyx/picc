#!/usr/bin/env python3
"""Aggregate completed PiCC factor-study runs using objective measurements."""

from __future__ import annotations

import argparse
import copy
import csv
import hashlib
import json
import math
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable

REPO_ROOT = Path(__file__).resolve().parent.parent
SKIP_PARTS = {".git", ".pi", "target", "node_modules", "__pycache__", ".pytest_cache"}


class SummaryError(RuntimeError):
    pass


def canonical_json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_json(value)).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def is_sha256(value: Any) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdefABCDEF" for character in value)
    )


def require_sha256(value: Any, field: str) -> str:
    if not is_sha256(value):
        raise SummaryError(f"{field} must be a 64-character hexadecimal SHA-256 digest")
    return str(value).lower()


def require_object(value: Any, field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise SummaryError(f"{field} must be an object")
    return value


def require_nonempty_string(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise SummaryError(f"{field} must be a nonempty string")
    return value


def require_hash_map(value: Any, field: str, *, allow_empty: bool = False) -> dict[str, str]:
    if not isinstance(value, dict) or (not value and not allow_empty):
        qualifier = "" if allow_empty else " nonempty"
        raise SummaryError(f"{field} must be a{qualifier} hash map")
    result: dict[str, str] = {}
    for raw_path, raw_digest in value.items():
        if not isinstance(raw_path, str) or not raw_path:
            raise SummaryError(f"{field} contains an invalid path")
        if not isinstance(raw_digest, str) or not raw_digest:
            raise SummaryError(f"{field}[{raw_path!r}] has an invalid digest")
        result[raw_path] = raw_digest.lower() if is_sha256(raw_digest) else raw_digest
    return result


def file_hash_tree(root: Path, field: str, *, allow_missing: bool = False) -> dict[str, str]:
    if not root.exists():
        if allow_missing:
            return {}
        raise SummaryError(f"missing {field}: {root}")
    if root.is_symlink() or not root.is_dir():
        raise SummaryError(f"{field} must be a real directory: {root}")
    result: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root)
        if path.is_symlink():
            raise SummaryError(f"{field} contains a symlink: {relative}")
        if path.is_file():
            result[str(relative)] = sha256_file(path)
        elif not path.is_dir():
            raise SummaryError(f"{field} contains an unsupported entry: {relative}")
    return result


MATERIALIZED_HASH_DIRS = (
    "config",
    "docker",
    "scripts",
    "pi",
    "prompts",
    "evaluator",
    "data/partitions",
    "data/agent-visible",
)
MATERIALIZED_HASH_FILES = ("VERSION", "MANIFEST.sha256")


def materialized_harness_file_hashes(root: Path) -> dict[str, str]:
    ignored_parts = {"__pycache__", ".pytest_cache", "node_modules"}
    result: dict[str, str] = {}
    for relative_name in MATERIALIZED_HASH_DIRS:
        directory = root / relative_name
        if directory.is_symlink() or not directory.is_dir():
            raise SummaryError(f"required materialized directory is missing or unsafe: {relative_name}")
        for path in sorted(directory.rglob("*")):
            relative = path.relative_to(root)
            if any(part in ignored_parts for part in relative.parts) or path.suffix == ".pyc":
                continue
            if path.is_symlink():
                raise SummaryError(f"symlink in frozen materialized harness: {relative}")
            if path.is_dir():
                continue
            if not path.is_file():
                raise SummaryError(f"unsupported frozen materialized entry: {relative}")
            result[str(relative)] = sha256_file(path)
    for relative_name in MATERIALIZED_HASH_FILES:
        path = root / relative_name
        if path.is_symlink() or not path.is_file():
            raise SummaryError(f"required materialized file is missing or unsafe: {relative_name}")
        result[relative_name] = sha256_file(path)
    return result


def deep_merge(base: Any, overlay: Any) -> Any:
    if isinstance(base, dict) and isinstance(overlay, dict):
        result = copy.deepcopy(base)
        for key, value in overlay.items():
            result[key] = deep_merge(result[key], value) if key in result else copy.deepcopy(value)
        return result
    return copy.deepcopy(overlay)


def current_condition_hashes(study: dict[str, Any]) -> dict[str, str]:
    defaults = study.get("defaults")
    conditions = study.get("conditions")
    if not isinstance(defaults, dict) or not isinstance(conditions, list):
        raise SummaryError("Study defaults must be an object and conditions must be an array")
    hashes: dict[str, str] = {}
    for raw in conditions:
        if not isinstance(raw, dict):
            raise SummaryError("Every study condition must be an object")
        condition = deep_merge(defaults, raw)
        condition_id = condition.get("id")
        if not isinstance(condition_id, str) or not condition_id:
            raise SummaryError("Every resolved study condition must have a nonempty id")
        if condition_id in hashes:
            raise SummaryError(f"Duplicate study condition id: {condition_id}")
        hashes[condition_id] = sha256_json(condition)
    return hashes


def load_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise SummaryError(f"Missing file: {path}") from error
    except json.JSONDecodeError as error:
        raise SummaryError(f"Invalid JSON in {path}: {error}") from error
    if not isinstance(value, dict):
        raise SummaryError(f"Expected JSON object: {path}")
    return value


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    for number, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as error:
            raise SummaryError(f"Invalid JSONL at {path}:{number}: {error}") from error
        if isinstance(value, dict):
            rows.append(value)
    return rows


def numeric(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    result = float(value)
    return result if math.isfinite(result) else None


def final_point(points: list[dict[str, Any]]) -> dict[str, Any]:
    return points[-1] if points else {}


def first_threshold_time(points: list[dict[str, Any]], threshold: float) -> float | None:
    for point in sorted(points, key=lambda row: numeric(row.get("elapsed_seconds")) or 0.0):
        score = numeric(point.get("score"))
        elapsed = numeric(point.get("elapsed_seconds"))
        if score is not None and elapsed is not None and score >= threshold:
            return elapsed
    return None


def source_metrics(workspace: Path, extensions: set[str], scaffold: Path | None) -> dict[str, Any]:
    source_files = source_loc = test_files = test_loc = all_files = 0
    for path in sorted(workspace.rglob("*")):
        if not path.is_file() or path.is_symlink():
            continue
        relative = path.relative_to(workspace)
        if any(part in SKIP_PARTS for part in relative.parts):
            continue
        all_files += 1
        if path.suffix not in extensions:
            continue
        try:
            lines = len(path.read_text(encoding="utf-8", errors="replace").splitlines())
        except OSError:
            continue
        source_files += 1
        source_loc += lines
        lower_parts = {part.lower() for part in relative.parts}
        name = relative.name.lower()
        is_test = (
            "tests" in lower_parts
            or "test" in lower_parts
            or name.startswith("test_")
            or name.endswith("_test.py")
            or "_test." in name
        )
        if is_test:
            test_files += 1
            test_loc += lines

    scaffold_files = scaffold_loc = 0
    if scaffold and scaffold.is_dir():
        for path in scaffold.rglob("*"):
            if path.is_file() and path.suffix in extensions:
                scaffold_files += 1
                scaffold_loc += len(path.read_text(encoding="utf-8", errors="replace").splitlines())
    return {
        "artifact_files": all_files,
        "source_files": source_files,
        "source_loc": source_loc,
        "agent_test_files": test_files,
        "agent_test_loc": test_loc,
        "provided_scaffold_source_files": scaffold_files,
        "provided_scaffold_source_loc": scaffold_loc,
        "net_source_loc_over_scaffold": source_loc - scaffold_loc,
    }


def extension_event_metrics(path: Path) -> dict[str, int]:
    counts = Counter(str(row.get("event", "unknown")) for row in read_jsonl(path))
    return {
        "visible_test_calls": counts["test_visible_start"],
        "unavailable_test_calls": counts["test_visible_unavailable"],
        "oracle_calls": counts["reference_oracle_start"],
        "unavailable_oracle_calls": counts["reference_oracle_unavailable"],
        "compactions": counts["session_compact"],
        "provider_errors": counts["provider_response_error"],
        "scaffold_applied": counts["study_scaffold_applied"],
        "pushed_test_reports": counts["test_pushed_end"],
    }


def pi_event_metrics(events_dir: Path) -> tuple[dict[str, int], dict[str, int]]:
    assistant_messages = 0
    tool_calls = 0
    usage: Counter[str] = Counter()
    aliases = {
        "input": ("input", "inputTokens", "prompt_tokens"),
        "output": ("output", "outputTokens", "completion_tokens"),
        "cache_read": ("cacheRead", "cache_read", "cache_read_input_tokens"),
        "cache_write": ("cacheWrite", "cache_write", "cache_creation_input_tokens"),
        "total": ("totalTokens", "total_tokens"),
    }
    for path in sorted(events_dir.glob("round-*.jsonl")):
        for event in read_jsonl(path):
            if event.get("type") == "tool_execution_start":
                tool_calls += 1
            elif event.get("type") == "message_end":
                message = event.get("message")
                if isinstance(message, dict) and message.get("role") == "assistant":
                    assistant_messages += 1
                    message_usage = message.get("usage") or {}
                    if not isinstance(message_usage, dict):
                        message_usage = {}
                    for target, names in aliases.items():
                        for name in names:
                            if name in message_usage:
                                value = numeric(message_usage[name]) or 0.0
                                usage[target] += int(value)
                                break
    return {"model_calls": assistant_messages, "tool_calls": tool_calls}, dict(usage)


def guard_event_metrics(path: Path) -> dict[str, Any]:
    """Same computation as `summarize_run.collect_guard`: blocked calls (rows
    from before the bash default timeout carry no `event` field and are blocks)
    plus the commands the default timeout cut off."""
    rows = read_jsonl(path)
    blocked = [row for row in rows if row.get("event", "blocked_tool_call") == "blocked_tool_call"]
    return {
        "blocked_calls": len(blocked),
        "reasons": dict(Counter(str(row.get("reason", "unknown")) for row in blocked)),
        "tools": dict(Counter(str(row.get("toolName", "unknown")) for row in blocked)),
        "bash_timeouts_fired": sum(1 for row in rows if row.get("event") == "bash_timeout_fired"),
    }


def guard_report_is_stale(report_guard: Mapping[str, Any], guard: Mapping[str, Any]) -> bool:
    """A report written before the bash default timeout lacks the cut-off
    counter; every field it does carry must still reproduce from the ledger."""
    if not {"blocked_calls", "reasons", "tools"} <= set(report_guard):
        return True
    return any(report_guard[key] != value for key, value in guard.items() if key in report_guard)


def snapshot_metrics(snapshots: list[dict[str, Any]]) -> dict[str, Any]:
    if not snapshots:
        return {
            "snapshot_count": 0,
            "visible_regressions": 0,
            "buildable_snapshot_fraction": None,
            "changed_files_total": 0,
            "insertions_total": 0,
            "deletions_total": 0,
        }
    regressions = 0
    prior: float | None = None
    buildable = 0
    for snapshot in snapshots:
        visible = snapshot.get("visible") if isinstance(snapshot.get("visible"), dict) else {}
        score = numeric(visible.get("score"))
        if prior is not None and score is not None and score < prior - 1e-12:
            regressions += 1
        if score is not None:
            prior = score
        buildable += visible.get("build_ok") is True
    return {
        "snapshot_count": len(snapshots),
        "visible_regressions": regressions,
        "buildable_snapshot_fraction": buildable / len(snapshots),
        "changed_files_total": sum(int(row.get("changed_files", 0) or 0) for row in snapshots),
        "insertions_total": sum(int(row.get("insertions", 0) or 0) for row in snapshots),
        "deletions_total": sum(int(row.get("deletions", 0) or 0) for row in snapshots),
    }


def condition_axes(condition: dict[str, Any]) -> dict[str, Any]:
    return {
        "factor": condition.get("factor"),
        "prompt_agents": condition["prompt"]["agents"],
        "prompt_initial": condition["prompt"]["initial"],
        "spec_path": condition["specification"]["path"],
        "spec_delivery": condition["specification"]["delivery"],
        "spec_creation_method": condition["specification"]["provenance"]["method"],
        "spec_artifact_family": condition["specification"]["provenance"].get("artifact_family"),
        "test_access": condition["tests"]["access"],
        "test_feedback": condition["tests"]["feedback"],
        "visible_subset_fraction": condition["tests"].get("visible_subset_fraction", 1.0),
        "test_creation_method": condition["tests"]["provenance"]["method"],
        "test_artifact_family": condition["tests"]["provenance"].get("artifact_family"),
        "language": condition["candidate"]["language"],
        "framework": condition["candidate"]["framework"],
        "scaffold": condition["candidate"].get("scaffold") or "none",
        "reference_mode": condition["reference"]["mode"],
    }


def optional_token_count(usage: dict[str, Any], key: str) -> int | None:
    if key not in usage or usage[key] is None:
        return None
    value = usage[key]
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    if not math.isfinite(float(value)) or value < 0 or int(value) != value:
        return None
    return int(value)


def numbers_equal(left: Any, right: Any) -> bool:
    left_number = numeric(left)
    right_number = numeric(right)
    if left_number is None or right_number is None:
        return left_number is None and right_number is None
    return math.isclose(left_number, right_number, rel_tol=1e-12, abs_tol=1e-12)


def trajectory_auc(points: list[dict[str, Any]]) -> float | None:
    usable: list[tuple[float, float]] = []
    for point in points:
        elapsed = numeric(point.get("elapsed_seconds"))
        score = numeric(point.get("score"))
        if elapsed is None or score is None:
            return None
        usable.append((elapsed, score))
    usable.sort(key=lambda item: item[0])
    if not usable or usable[-1][0] <= 0:
        return None
    area = 0.0
    previous_t = previous_s = 0.0
    for current_t, current_s in usable:
        area += (current_t - previous_t) * (previous_s + current_s) / 2.0
        previous_t, previous_s = current_t, current_s
    return area / usable[-1][0]


def resolve_materialization_root(run_dir: Path, raw_root: Any) -> Path:
    raw = require_nonempty_string(raw_root, "study-metadata.materialization_root")
    relative = Path(raw)
    if relative.is_absolute() or relative == Path(".") or ".." in relative.parts:
        raise SummaryError("study-metadata.materialization_root must be a contained repository-relative path")
    logical = REPO_ROOT / relative
    if logical.is_symlink():
        raise SummaryError("study materialization root must not be a symlink")
    try:
        root = logical.resolve(strict=True)
        repository = REPO_ROOT.resolve(strict=True)
    except (OSError, RuntimeError) as error:
        raise SummaryError(f"could not resolve the frozen study materialization for {run_dir.name}") from error
    if not root.is_relative_to(repository) or not root.is_dir():
        raise SummaryError("study materialization root escapes the repository or is not a directory")
    return root


def verified_provenance(
    run_dir: Path,
    sidecar: dict[str, Any],
    metadata: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    study_control = run_dir / "study-control"
    materialization_record_path = study_control / "materialization.json"
    materialization_record = load_object(materialization_record_path)
    expected_record = dict(sidecar)
    expected_record.pop("materialization_root", None)
    expected_record.pop("frozen_at", None)
    if materialization_record != expected_record:
        raise SummaryError("study-control/materialization.json disagrees with study-metadata.json")

    materialization_root = resolve_materialization_root(run_dir, sidecar.get("materialization_root"))
    live_record_path = materialization_root / "study-materialization.json"
    if not live_record_path.is_file() or live_record_path.is_symlink():
        raise SummaryError("frozen study materialization record is missing or unsafe")
    if sha256_file(live_record_path) != sha256_file(materialization_record_path):
        raise SummaryError("retained materialization record disagrees with study-control")

    materialized_harness = require_object(
        sidecar.get("materialized_harness"), "study-metadata.materialized_harness"
    )
    expected_materialized_hashes = require_hash_map(
        materialized_harness.get("file_hashes"),
        "study-metadata.materialized_harness.file_hashes",
    )
    actual_materialized_hashes = materialized_harness_file_hashes(materialization_root)
    if actual_materialized_hashes != expected_materialized_hashes:
        changed = sorted(
            path
            for path in set(actual_materialized_hashes) | set(expected_materialized_hashes)
            if actual_materialized_hashes.get(path) != expected_materialized_hashes.get(path)
        )
        raise SummaryError("frozen materialized harness files changed: " + ", ".join(changed[:8]))
    materialized_evaluator_sha256 = require_sha256(
        expected_materialized_hashes.get("evaluator/evaluate.py"),
        "materialized_harness.file_hashes[evaluator/evaluate.py]",
    )
    materialized_evaluate_run_sha256 = require_sha256(
        expected_materialized_hashes.get("scripts/evaluate_run.py"),
        "materialized_harness.file_hashes[scripts/evaluate_run.py]",
    )
    materialized_run_experiment_sha256 = require_sha256(
        expected_materialized_hashes.get("scripts/run_experiment.py"),
        "materialized_harness.file_hashes[scripts/run_experiment.py]",
    )
    materialized_summarize_run_sha256 = require_sha256(
        expected_materialized_hashes.get("scripts/summarize_run.py"),
        "materialized_harness.file_hashes[scripts/summarize_run.py]",
    )
    materialized_script_hashes = {
        path: digest for path, digest in expected_materialized_hashes.items() if path.startswith("scripts/")
    }
    materialized_hidden_hashes = {
        path: digest
        for path, digest in expected_materialized_hashes.items()
        if path.startswith("data/partitions/hidden/")
    }
    if not materialized_script_hashes or not materialized_hidden_hashes:
        raise SummaryError("materialized harness provenance omits scripts or the hidden partition")
    source_harness = require_object(sidecar.get("source_harness"), "study-metadata.source_harness")
    source_manifest_sha256 = require_sha256(
        source_harness.get("manifest_sha256"), "study-metadata.source_harness.manifest_sha256"
    )
    source_file_hashes = require_hash_map(
        source_harness.get("file_hashes"), "study-metadata.source_harness.file_hashes"
    )
    release_manifest_path = materialization_root / "MANIFEST.sha256"
    if not release_manifest_path.is_file() or release_manifest_path.is_symlink():
        raise SummaryError("frozen source-harness release manifest is missing or unsafe")
    if sha256_file(release_manifest_path) != source_manifest_sha256:
        raise SummaryError("frozen source-harness release manifest SHA-256 does not match provenance")

    rendered = require_object(sidecar.get("rendered"), "study-metadata.rendered")
    specification_sha256 = require_sha256(
        rendered.get("specification_sha256"), "study-metadata.rendered.specification_sha256"
    )
    prompt_hashes = require_hash_map(rendered.get("prompt_hashes"), "study-metadata.rendered.prompt_hashes")
    extension_hashes = require_hash_map(
        rendered.get("extension_hashes"), "study-metadata.rendered.extension_hashes"
    )
    scaffold_hashes = require_hash_map(
        rendered.get("scaffold_hashes"), "study-metadata.rendered.scaffold_hashes", allow_empty=True
    )
    candidate_adapter_sha256 = require_sha256(
        rendered.get("candidate_adapter_sha256"), "study-metadata.rendered.candidate_adapter_sha256"
    )
    visible_manifest_sha256 = require_sha256(
        rendered.get("visible_manifest_sha256"), "study-metadata.rendered.visible_manifest_sha256"
    )
    hidden_manifest_sha256 = require_sha256(
        rendered.get("hidden_manifest_sha256"), "study-metadata.rendered.hidden_manifest_sha256"
    )

    prompt_roots = [study_control / "prompts", materialization_root / "prompts"]
    for prompt_root in prompt_roots:
        if file_hash_tree(prompt_root, "frozen prompt tree") != prompt_hashes:
            raise SummaryError(f"frozen prompt hashes disagree with provenance: {prompt_root}")
    extension_roots = [run_dir / "control" / "pi" / "extensions", materialization_root / "pi" / "extensions"]
    for extension_root in extension_roots:
        if file_hash_tree(extension_root, "frozen extension tree") != extension_hashes:
            raise SummaryError(f"frozen extension hashes disagree with provenance: {extension_root}")

    candidate_paths = [study_control / "candidate.json", materialization_root / "evaluator" / "candidate.json"]
    for candidate_path in candidate_paths:
        if not candidate_path.is_file() or candidate_path.is_symlink():
            raise SummaryError(f"frozen candidate adapter is missing or unsafe: {candidate_path}")
        if sha256_file(candidate_path) != candidate_adapter_sha256:
            raise SummaryError(f"frozen candidate adapter SHA-256 disagrees with provenance: {candidate_path}")

    manifest_specs = [
        ("visible", visible_manifest_sha256, study_control / "visible-manifest.json", materialization_root / "data" / "partitions" / "visible" / "manifest.json"),
        ("hidden", hidden_manifest_sha256, study_control / "hidden-manifest.json", materialization_root / "data" / "partitions" / "hidden" / "manifest.json"),
    ]
    for label, expected_digest, compact_path, retained_path in manifest_specs:
        for manifest_path in (compact_path, retained_path):
            if not manifest_path.is_file() or manifest_path.is_symlink():
                raise SummaryError(f"frozen {label} manifest is missing or unsafe: {manifest_path}")
            if sha256_file(manifest_path) != expected_digest:
                raise SummaryError(f"frozen {label} manifest SHA-256 disagrees with provenance: {manifest_path}")

    scaffold_root = materialization_root / "data" / "partitions" / "visible" / ".study-scaffold"
    actual_scaffold_hashes = file_hash_tree(scaffold_root, "frozen scaffold tree", allow_missing=True)
    if actual_scaffold_hashes != scaffold_hashes:
        raise SummaryError("frozen scaffold hashes disagree with provenance")

    metadata_control_hashes = require_hash_map(
        metadata.get("prompt_and_extension_hashes"), "metadata.prompt_and_extension_hashes"
    )
    actual_control_hashes = file_hash_tree(run_dir / "control", "run control tree")
    if actual_control_hashes != metadata_control_hashes:
        raise SummaryError("run control tree disagrees with metadata.prompt_and_extension_hashes")
    actual_prompt_hashes = {
        path: digest for path, digest in actual_control_hashes.items() if not path.startswith("pi/")
    }
    if actual_prompt_hashes != prompt_hashes:
        raise SummaryError("run prompt hashes disagree with rendered prompt provenance")
    actual_extension_hashes = {
        path.removeprefix("pi/extensions/"): digest
        for path, digest in actual_control_hashes.items()
        if path.startswith("pi/extensions/")
    }
    if actual_extension_hashes != extension_hashes:
        raise SummaryError("run extension hashes disagree with rendered extension provenance")

    if metadata.get("visible_manifest_sha256") != visible_manifest_sha256:
        raise SummaryError("metadata visible manifest SHA-256 disagrees with study provenance")
    if metadata.get("hidden_manifest_sha256") != hidden_manifest_sha256:
        raise SummaryError("metadata hidden manifest SHA-256 disagrees with study provenance")

    configuration = require_object(metadata.get("configuration"), "metadata.configuration")
    if not configuration:
        raise SummaryError("metadata.configuration must not be empty")
    effective_config = require_object(sidecar.get("effective_config"), "study-metadata.effective_config")
    if not effective_config or not all(isinstance(key, str) and isinstance(value, str) for key, value in effective_config.items()):
        raise SummaryError("study-metadata.effective_config must be a nonempty string map")
    if configuration != effective_config:
        raise SummaryError("metadata.configuration disagrees with the frozen effective configuration")
    budget = require_object(metadata.get("budget"), "metadata.budget")
    wall_hours = numeric(budget.get("wall_hours"))
    if wall_hours is None or wall_hours <= 0:
        raise SummaryError("metadata.budget.wall_hours must be positive")
    for key in ("max_rounds", "round_timeout_minutes", "max_stage"):
        value = budget.get(key)
        if isinstance(value, bool) or not isinstance(value, int) or value < 1:
            raise SummaryError(f"metadata.budget.{key} must be a positive integer")

    model = require_object(metadata.get("model"), "metadata.model")
    model_provider = require_nonempty_string(model.get("provider"), "metadata.model.provider")
    model_id = require_nonempty_string(model.get("id"), "metadata.model.id")
    model_thinking = require_nonempty_string(model.get("thinking"), "metadata.model.thinking")
    model_serving_revision = require_nonempty_string(
        model.get("serving_revision"), "metadata.model.serving_revision"
    )
    docker_image = require_object(metadata.get("docker_image"), "metadata.docker_image")
    docker_image_name = require_nonempty_string(docker_image.get("name"), "metadata.docker_image.name")
    docker_image_id = require_nonempty_string(docker_image.get("id"), "metadata.docker_image.id")
    starter_version = require_nonempty_string(metadata.get("starter_version"), "metadata.starter_version")

    expected_model = {
        "provider": effective_config.get("MODEL_PROVIDER", ""),
        "id": effective_config.get("MODEL_ID", ""),
        "thinking": effective_config.get("MODEL_THINKING", "max"),
    }
    actual_model = {"provider": model_provider, "id": model_id, "thinking": model_thinking}
    if actual_model != expected_model:
        raise SummaryError("metadata.model disagrees with the frozen provider/model/thinking configuration")
    expected_image_name = require_nonempty_string(
        effective_config.get("EXPERIMENT_IMAGE"), "effective_config.EXPERIMENT_IMAGE"
    )
    if docker_image_name != expected_image_name:
        raise SummaryError("metadata.docker_image.name disagrees with the frozen EXPERIMENT_IMAGE")
    expected_starter_version = effective_config.get("STARTER_VERSION", "unknown")
    if starter_version != expected_starter_version:
        raise SummaryError("metadata.starter_version disagrees with the frozen STARTER_VERSION")

    profile_prefix = require_nonempty_string(metadata.get("profile"), "metadata.profile").upper()
    try:
        expected_wall_hours = float(effective_config[f"{profile_prefix}_HOURS"])
        expected_max_rounds = int(effective_config[f"{profile_prefix}_ROUNDS"])
        expected_round_timeout = int(effective_config[f"{profile_prefix}_ROUND_TIMEOUT_MINUTES"])
        expected_max_stage = int(effective_config[f"{profile_prefix}_MAX_STAGE"])
    except (KeyError, TypeError, ValueError) as error:
        raise SummaryError("frozen effective configuration has an invalid selected-profile budget") from error
    if not numbers_equal(budget.get("wall_hours"), expected_wall_hours):
        raise SummaryError("metadata budget wall_hours disagrees with the frozen profile configuration")
    expected_integer_budget = {
        "max_rounds": expected_max_rounds,
        "round_timeout_minutes": expected_round_timeout,
        "max_stage": expected_max_stage,
    }
    for key, expected_value in expected_integer_budget.items():
        if budget.get(key) != expected_value:
            raise SummaryError(f"metadata budget {key} disagrees with the frozen profile configuration")
    harness_groups = {
        prefix: {path: digest for path, digest in source_file_hashes.items() if path.startswith(prefix + "/")}
        for prefix in ("scripts", "pi", "evaluator")
    }
    if any(not hashes for hashes in harness_groups.values()):
        raise SummaryError("source-harness file hashes must cover scripts, pi, and evaluator")

    hidden_manifest = load_object(study_control / "hidden-manifest.json")
    fingerprints = {
        "materialized_harness_sha256": sha256_json(expected_materialized_hashes),
        "materialized_scripts_sha256": sha256_json(materialized_script_hashes),
        "materialized_hidden_partition_sha256": sha256_json(materialized_hidden_hashes),
        "materialized_evaluator_sha256": materialized_evaluator_sha256,
        "materialized_evaluate_run_sha256": materialized_evaluate_run_sha256,
        "materialized_run_experiment_sha256": materialized_run_experiment_sha256,
        "materialized_summarize_run_sha256": materialized_summarize_run_sha256,
        "source_harness_manifest_sha256": source_manifest_sha256,
        "source_harness_sha256": sha256_json(
            {"manifest_sha256": source_manifest_sha256, "file_hashes": source_file_hashes}
        ),
        "source_scripts_sha256": sha256_json(harness_groups["scripts"]),
        "source_pi_sha256": sha256_json(harness_groups["pi"]),
        "source_evaluator_sha256": sha256_json(harness_groups["evaluator"]),
        "rendered_assets_sha256": sha256_json(rendered),
        "specification_sha256": specification_sha256,
        "prompt_hashes_sha256": sha256_json(prompt_hashes),
        "extension_hashes_sha256": sha256_json(extension_hashes),
        "scaffold_hashes_sha256": sha256_json(scaffold_hashes),
        "candidate_adapter_sha256": candidate_adapter_sha256,
        "visible_manifest_sha256": visible_manifest_sha256,
        "hidden_manifest_sha256": hidden_manifest_sha256,
        "runtime_control_sha256": sha256_json(metadata_control_hashes),
        "configuration_sha256": sha256_json(configuration),
        "budget_sha256": sha256_json(budget),
        "model_provider": model_provider,
        "model_id": model_id,
        "model_thinking": model_thinking,
        "model_serving_revision": model_serving_revision,
        "docker_image_name": docker_image_name,
        "docker_image_id": docker_image_id,
        "starter_version": starter_version,
    }
    return fingerprints, hidden_manifest


def snapshot_identities(snapshots: list[dict[str, Any]]) -> list[tuple[int, str, str, float]]:
    identities: list[tuple[int, str, str, float]] = []
    prior_elapsed = -1.0
    for index, snapshot in enumerate(snapshots):
        round_number = snapshot.get("round")
        if isinstance(round_number, bool) or not isinstance(round_number, int) or round_number != index:
            raise SummaryError("report snapshots must have unique sequential rounds starting at zero")
        commit = require_nonempty_string(snapshot.get("git_commit"), f"report.snapshots[{index}].git_commit")
        tree = require_nonempty_string(snapshot.get("git_tree"), f"report.snapshots[{index}].git_tree")
        elapsed = numeric(snapshot.get("elapsed_seconds"))
        if elapsed is None or elapsed < 0 or elapsed < prior_elapsed:
            raise SummaryError("report snapshot elapsed times must be finite, nonnegative, and nondecreasing")
        identities.append((round_number, commit, tree, elapsed))
        prior_elapsed = elapsed
    return identities


def verify_trajectory_identity(
    label: str,
    points: list[dict[str, Any]],
    identities: list[tuple[int, str, str, float]],
) -> None:
    if len(points) != len(identities):
        raise SummaryError(f"{label} trajectory does not cover every frozen snapshot")
    for index, (point, (round_number, commit, _tree, elapsed)) in enumerate(zip(points, identities, strict=True)):
        if point.get("round") != round_number or point.get("git_commit") != commit:
            raise SummaryError(f"{label} trajectory round/commit disagrees with snapshot {index}")
        if not numbers_equal(point.get("elapsed_seconds"), elapsed):
            raise SummaryError(f"{label} trajectory elapsed time disagrees with snapshot {index}")


def hidden_manifest_selection(
    hidden_manifest: dict[str, Any],
    budget_max_stage: int,
) -> tuple[list[tuple[str, int, str]], int]:
    tests = hidden_manifest.get("tests")
    if not isinstance(tests, list) or not tests:
        raise SummaryError("frozen hidden manifest must contain tests")
    available: list[tuple[str, int, str]] = []
    for index, test in enumerate(tests):
        if not isinstance(test, dict):
            raise SummaryError(f"frozen hidden manifest test {index} must be an object")
        test_id = require_nonempty_string(test.get("id"), f"hidden manifest test {index}.id")
        validity = require_nonempty_string(test.get("validity"), f"hidden manifest test {index}.validity")
        stage = test.get("stage")
        if isinstance(stage, bool) or not isinstance(stage, int) or stage < 1:
            raise SummaryError(f"hidden manifest test {index}.stage must be a positive integer")
        available.append((test_id, stage, validity))
    effective_max_stage = min(budget_max_stage, max(row[1] for row in available))
    selected = [row for row in available if row[1] <= effective_max_stage]
    if not selected:
        raise SummaryError("frozen hidden manifest has no tests within the run's max_stage budget")
    return sorted(selected, key=lambda row: (row[1], row[2], row[0])), effective_max_stage


def recomputed_hidden_scores(result_rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_stage: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for index, row in enumerate(result_rows):
        stage = row.get("stage")
        passed = row.get("passed")
        if isinstance(stage, bool) or not isinstance(stage, int):
            raise SummaryError(f"hidden test result {index} has an invalid stage")
        if not isinstance(passed, bool):
            raise SummaryError(f"hidden test result {index} has a non-boolean passed value")
        by_stage[stage].append(row)

    stage_scores: list[float] = []
    for stage_rows in by_stage.values():
        validity_scores: list[float] = []
        for validity in ("valid", "invalid"):
            subset = [row for row in stage_rows if row.get("validity") == validity]
            if subset:
                validity_scores.append(sum(row["passed"] for row in subset) / len(subset))
        if not validity_scores:
            raise SummaryError("hidden test results contain a stage with no valid/invalid rows")
        stage_scores.append(sum(validity_scores) / len(validity_scores))

    passed = sum(row["passed"] for row in result_rows)
    total = len(result_rows)
    return {
        "score": sum(stage_scores) / len(stage_scores),
        "micro_score": passed / total,
        "passed": passed,
        "failed": total - passed,
        "total": total,
    }


def verified_hidden_trajectory(
    run_dir: Path,
    report: dict[str, Any],
    metadata: dict[str, Any],
    hidden_manifest: dict[str, Any],
    candidate_adapter_sha256: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    if report.get("metadata") != metadata:
        raise SummaryError("report metadata is stale or disagrees with metadata.json")
    resume = require_object(report.get("resume"), "report.resume")
    if (
        resume.get("resumed") is not False
        or resume.get("resume_count") != 0
        or resume.get("protocol_comparable") is not True
    ):
        raise SummaryError("report resume metadata disagrees with uninterrupted primary eligibility")

    visible_points = report.get("visible_trajectory")
    hidden_points = report.get("hidden_trajectory")
    snapshots = report.get("snapshots")
    if not isinstance(visible_points, list) or not isinstance(hidden_points, list) or not isinstance(snapshots, list):
        raise SummaryError("report trajectories or snapshots are malformed")
    if not snapshots or not all(isinstance(row, dict) for row in snapshots):
        raise SummaryError("report snapshots must be a nonempty array of objects")
    if not all(isinstance(point, dict) for point in visible_points + hidden_points):
        raise SummaryError("report trajectory contains a non-object entry")

    snapshot_ledger = read_jsonl(run_dir / "artifacts" / "snapshots.jsonl")
    if snapshot_ledger != snapshots:
        raise SummaryError("report snapshots are stale or disagree with artifacts/snapshots.jsonl")
    identities = snapshot_identities(snapshots)
    verify_trajectory_identity("visible", visible_points, identities)
    verify_trajectory_identity("hidden", hidden_points, identities)

    for index, (snapshot, visible_point) in enumerate(zip(snapshots, visible_points, strict=True)):
        visible_summary = snapshot.get("visible")
        if not isinstance(visible_summary, dict):
            raise SummaryError(f"snapshot {index} has no visible evaluation summary")
        for key in ("score", "micro_score"):
            if not numbers_equal(visible_point.get(key), visible_summary.get(key)):
                raise SummaryError(f"visible trajectory {key} disagrees with snapshot {index}")
        for key in ("passed", "total", "build_ok"):
            if visible_point.get(key) != visible_summary.get(key):
                raise SummaryError(f"visible trajectory {key} disagrees with snapshot {index}")

    hidden_rows = read_jsonl(run_dir / "artifacts" / "hidden-scores.jsonl")
    if len(hidden_rows) != len(identities):
        raise SummaryError("hidden evaluation ledger does not cover every frozen snapshot")
    budget = require_object(metadata.get("budget"), "metadata.budget")
    budget_max_stage = int(budget["max_stage"])
    expected_tests, max_stage = hidden_manifest_selection(hidden_manifest, budget_max_stage)
    expected_test_count = len(expected_tests)
    final_full: dict[str, Any] = {}

    expected_docker_image = require_object(metadata.get("docker_image"), "metadata.docker_image")
    for index, (hidden_row, hidden_point, identity) in enumerate(
        zip(hidden_rows, hidden_points, identities, strict=True)
    ):
        round_number, commit, tree, elapsed = identity
        if hidden_row.get("partition") != "hidden":
            raise SummaryError(f"hidden evaluation ledger row {index} has the wrong partition")
        if hidden_row.get("docker_image") != expected_docker_image:
            raise SummaryError(f"hidden evaluation ledger row {index} used a different Docker image")
        if (
            hidden_row.get("round") != round_number
            or hidden_row.get("git_commit") != commit
            or hidden_row.get("git_tree") != tree
        ):
            raise SummaryError(f"hidden evaluation ledger row {index} disagrees with its snapshot")
        if not numbers_equal(hidden_row.get("elapsed_seconds"), elapsed):
            raise SummaryError(f"hidden evaluation ledger row {index} has a stale elapsed time")
        expected_output = f"artifacts/evaluations/hidden-round-{round_number:03d}.json"
        if hidden_row.get("output") != expected_output:
            raise SummaryError(f"hidden evaluation ledger row {index} points at an unexpected output")

        full_path = run_dir / expected_output
        full = load_object(full_path)
        if full.get("docker_image") != expected_docker_image:
            raise SummaryError(f"hidden evaluation {round_number} used a different Docker image")
        full_snapshot = require_object(full.get("snapshot"), f"hidden evaluation {round_number}.snapshot")
        if full_snapshot.get("git_commit") != commit or full_snapshot.get("git_tree") != tree:
            raise SummaryError(f"hidden evaluation {round_number} was produced from a different snapshot")
        if full.get("partition") != hidden_manifest.get("partition"):
            raise SummaryError(f"hidden evaluation {round_number} used the wrong manifest partition")
        candidate = require_object(full.get("candidate"), f"hidden evaluation {round_number}.candidate")
        if candidate.get("adapter_sha256") != candidate_adapter_sha256:
            raise SummaryError(f"hidden evaluation {round_number} used a different candidate adapter")
        selection = require_object(full.get("selection"), f"hidden evaluation {round_number}.selection")
        if (
            selection.get("max_stage") != max_stage
            or selection.get("latest_only") is not False
            or selection.get("test_id") is not None
            or selection.get("count") != expected_test_count
        ):
            raise SummaryError(f"hidden evaluation {round_number} did not use the full frozen selection")
        result_rows = full.get("tests")
        if not isinstance(result_rows, list) or not all(isinstance(row, dict) for row in result_rows):
            raise SummaryError(f"hidden evaluation {round_number} has malformed test results")
        actual_tests = sorted(
            ((str(row.get("id")), row.get("stage"), str(row.get("validity"))) for row in result_rows),
            key=lambda row: (row[1] if isinstance(row[1], int) else -1, row[2], row[0]),
        )
        if actual_tests != expected_tests:
            raise SummaryError(f"hidden evaluation {round_number} does not cover the frozen test manifest")

        full_summary = require_object(full.get("summary"), f"hidden evaluation {round_number}.summary")
        recomputed = recomputed_hidden_scores(result_rows)
        for key in ("score", "micro_score"):
            if not numbers_equal(full_summary.get(key), recomputed[key]):
                raise SummaryError(f"hidden evaluation {round_number} has an inconsistent {key}")
        for key in ("passed", "failed", "total"):
            if full_summary.get(key) != recomputed[key]:
                raise SummaryError(f"hidden evaluation {round_number} has an inconsistent {key}")
        hidden_summary = require_object(hidden_row.get("summary"), f"hidden ledger row {index}.summary")
        if full_summary != hidden_summary:
            raise SummaryError(f"hidden evaluation {round_number} summary disagrees with its ledger")
        if full_summary.get("total") != expected_test_count:
            raise SummaryError(f"hidden evaluation {round_number} summary has the wrong test count")
        if not isinstance(full_summary.get("build_ok"), bool) or not isinstance(full_summary.get("audit_ok"), bool):
            raise SummaryError(f"hidden evaluation {round_number} lacks build/audit status")
        for key in ("score", "micro_score"):
            if numeric(full_summary.get(key)) is None or not numbers_equal(hidden_point.get(key), full_summary.get(key)):
                raise SummaryError(f"hidden trajectory {key} disagrees with evaluation {round_number}")
        for key in ("passed", "total", "build_ok"):
            if hidden_point.get(key) != full_summary.get(key):
                raise SummaryError(f"hidden trajectory {key} disagrees with evaluation {round_number}")
        final_full = full

    calculated_visible_auc = trajectory_auc(visible_points)
    calculated_hidden_auc = trajectory_auc(hidden_points)
    if not (len(visible_points) == 1 and report.get("visible_score_auc") is None) and not numbers_equal(
        report.get("visible_score_auc"), calculated_visible_auc
    ):
        raise SummaryError("reported visible AUC disagrees with the full visible trajectory")
    if not (len(hidden_points) == 1 and report.get("hidden_score_auc") is None) and not numbers_equal(
        report.get("hidden_score_auc"), calculated_hidden_auc
    ):
        raise SummaryError("reported hidden AUC is missing or disagrees with the full hidden trajectory")
    return visible_points, hidden_points, snapshots, final_full


FUZZ_EMPTY = {
    "fuzz_macro": None,
    "fuzz_stage_pass_rates": None,
    "fuzz_programs_per_stage": None,
    "fuzz_mismatches_total": None,
    "fuzz_deadline_hit": None,
    "fuzz_macro_last_buildable": None,
}


def last_buildable_index(hidden_rows: list[dict[str, Any]]) -> int | None:
    """Index of the last hidden-evaluated snapshot that built with no blocking
    audit finding; None when no snapshot did. The final snapshot is whatever the
    workspace held when the round cap fell, so the last buildable snapshot is
    the co-primary that ignores a rewrite cut in half (v8 pre-registration)."""
    for index in range(len(hidden_rows) - 1, -1, -1):
        summary = hidden_rows[index].get("summary")
        if not isinstance(summary, dict):
            continue
        # Built and no *blocking* finding; advisory findings do not disqualify
        # (v9 Amendment 1).
        if summary.get("build_ok") is True and not summary.get("audit_blocking"):
            return index
    return None


def verified_fuzz_row(
    run_dir: Path,
    row: dict[str, Any],
    snapshot: dict[str, Any],
    metadata: dict[str, Any],
    candidate_adapter_sha256: str,
    expected_output: str,
    label: str,
) -> dict[str, Any]:
    """Verify one fuzz ledger row against the snapshot it must describe and
    return its summary."""
    if row.get("partition") != "fuzz":
        raise SummaryError(f"fuzz ledger row ({label}) has the wrong partition")
    if row.get("round") != snapshot.get("round") or row.get("git_commit") != snapshot.get("git_commit") or row.get("git_tree") != snapshot.get("git_tree"):
        raise SummaryError(f"fuzz ledger row ({label}) does not describe the {label} snapshot")
    expected_docker_image = require_object(metadata.get("docker_image"), "metadata.docker_image")
    if row.get("docker_image") != expected_docker_image:
        raise SummaryError(f"fuzz ledger row ({label}) used a different Docker image")
    if row.get("output") != expected_output:
        raise SummaryError(f"fuzz ledger row ({label}) points at an unexpected output")
    full = load_object(run_dir / expected_output)
    full_snapshot = require_object(full.get("snapshot"), "fuzz evaluation snapshot")
    if full_snapshot.get("git_commit") != snapshot.get("git_commit") or full_snapshot.get("git_tree") != snapshot.get("git_tree"):
        raise SummaryError(f"fuzz evaluation ({label}) was produced from a different snapshot")
    if full.get("docker_image") != expected_docker_image:
        raise SummaryError(f"fuzz evaluation ({label}) used a different Docker image")
    candidate = require_object(full.get("candidate"), "fuzz evaluation candidate")
    if candidate.get("adapter_sha256") != candidate_adapter_sha256:
        raise SummaryError(f"fuzz evaluation ({label}) used a different candidate adapter")
    budget = require_object(metadata.get("budget"), "metadata.budget")
    policy = require_object(full.get("policy"), "fuzz evaluation policy")
    if policy.get("max_stage") != int(budget["max_stage"]):
        raise SummaryError(f"fuzz evaluation ({label}) did not use the run's stage budget")
    summary = require_object(full.get("summary"), "fuzz evaluation summary")
    if summary != row.get("summary"):
        raise SummaryError(f"fuzz evaluation ({label}) summary disagrees with its ledger row")
    rates = summary.get("stage_pass_rates")
    if not isinstance(rates, list) or len(rates) != int(budget["max_stage"]) or any(numeric(r) is None for r in rates):
        raise SummaryError(f"fuzz evaluation ({label}) has an inconsistent stage_pass_rates array")
    recomputed = sum(float(r) for r in rates) / len(rates)
    if not numbers_equal(summary.get("fuzz_macro"), recomputed):
        raise SummaryError(f"fuzz evaluation ({label}) fuzz_macro disagrees with its per-stage rates")
    if summary.get("error"):
        raise SummaryError(f"fuzz evaluation ({label}) recorded an error: {str(summary['error'])[:200]}")
    return summary


def verified_fuzz_score(
    run_dir: Path,
    snapshots: list[dict[str, Any]],
    metadata: dict[str, Any],
    candidate_adapter_sha256: str,
    report: dict[str, Any],
    hidden_rows: list[dict[str, Any]] | None = None,
) -> tuple[dict[str, Any], str | None]:
    """The fuzz-oracle columns for a run, verified against the final snapshot
    and, when present, the last buildable snapshot.

    The ledger holds one row for the final snapshot (`role` "final", or no
    role in ledgers from before v8) and optionally one for the last buildable
    snapshot (`role` "last_buildable", written only when the final snapshot
    did not build). A run without a fuzz ledger is still included (its columns
    are None) but is reported as a coverage warning; an inconsistent ledger is
    a provenance failure and raises, excluding the run like a bad hidden
    ledger would. `fuzz_macro_last_buildable` is the final value when the
    final snapshot built, the second row's value when it exists, 0.0 when no
    snapshot built, and None (with a warning) for a pre-v8 ledger that lacks
    the row.
    """
    rows = read_jsonl(run_dir / "artifacts" / "fuzz-scores.jsonl")
    if not rows:
        return dict(FUZZ_EMPTY), f"{run_dir.name}: no fuzz-oracle score (artifacts/fuzz-scores.jsonl missing)"
    roles = [str(row.get("role", "final")) for row in rows]
    if roles.count("final") != 1 or len(rows) > 2 or any(role not in {"final", "last_buildable"} for role in roles):
        raise SummaryError("fuzz ledger must hold one final-snapshot row and at most one last-buildable row")
    row = rows[roles.index("final")]
    final = snapshots[-1]
    summary = verified_fuzz_row(run_dir, row, final, metadata, candidate_adapter_sha256, "artifacts/evaluations/fuzz-final.json", "final")
    if report.get("fuzz_final") != row:
        raise SummaryError("report fuzz_final is stale or disagrees with artifacts/fuzz-scores.jsonl")
    rates = summary["stage_pass_rates"]
    columns = {
        "fuzz_macro": float(summary["fuzz_macro"]),
        "fuzz_stage_pass_rates": json.dumps([round(float(r), 4) for r in rates]),
        "fuzz_programs_per_stage": summary.get("programs_per_stage"),
        "fuzz_mismatches_total": summary.get("mismatches_total"),
        "fuzz_deadline_hit": bool(summary.get("deadline_hit")),
        "fuzz_macro_last_buildable": None,
    }
    warning: str | None = None
    ledger = hidden_rows if hidden_rows is not None else read_jsonl(run_dir / "artifacts" / "hidden-scores.jsonl")
    buildable = last_buildable_index(ledger)
    lb_row = rows[roles.index("last_buildable")] if "last_buildable" in roles else None
    if buildable is not None and buildable == len(snapshots) - 1:
        if lb_row is not None:
            raise SummaryError("fuzz ledger has a last-buildable row although the final snapshot built")
        columns["fuzz_macro_last_buildable"] = columns["fuzz_macro"]
    elif buildable is None:
        if lb_row is not None:
            raise SummaryError("fuzz ledger has a last-buildable row although no snapshot built")
        columns["fuzz_macro_last_buildable"] = 0.0
    elif lb_row is None:
        warning = f"{run_dir.name}: no fuzz-oracle score for the last buildable snapshot (ledger from before v8)"
    else:
        lb_summary = verified_fuzz_row(
            run_dir, lb_row, snapshots[buildable], metadata, candidate_adapter_sha256,
            "artifacts/evaluations/fuzz-last-buildable.json", "last buildable",
        )
        if report.get("fuzz_last_buildable") != lb_row:
            raise SummaryError("report fuzz_last_buildable is stale or disagrees with artifacts/fuzz-scores.jsonl")
        columns["fuzz_macro_last_buildable"] = float(lb_summary["fuzz_macro"])
    return columns, warning


def excluded_run(run_dir: Path, reason: str) -> tuple[None, str]:
    return None, f"{run_dir.name}: excluded from primary analysis: {reason}"


def collect_run(
    run_dir: Path,
    expected_study: str,
    expected_study_sha256: str,
    expected_condition_hashes: dict[str, str],
) -> tuple[dict[str, Any] | None, str | None]:
    sidecar_path = run_dir / "study-metadata.json"
    if not sidecar_path.is_file():
        return None, None
    sidecar = load_object(sidecar_path)
    if sidecar.get("study_id") != expected_study:
        return None, None
    if sidecar.get("run_id") != run_dir.name:
        return excluded_run(run_dir, "study metadata run_id does not match the run directory")
    if sidecar.get("study_sha256") != expected_study_sha256:
        return excluded_run(run_dir, "frozen study SHA-256 does not match the current study manifest")

    condition = sidecar.get("condition")
    if not isinstance(condition, dict):
        return excluded_run(run_dir, "malformed condition metadata")
    condition_id = condition.get("id")
    if not isinstance(condition_id, str) or not condition_id:
        return excluded_run(run_dir, "condition metadata has no valid id")
    recorded_condition_sha256 = sidecar.get("condition_sha256")
    if recorded_condition_sha256 != sha256_json(condition):
        return excluded_run(run_dir, "condition SHA-256 does not match the frozen condition payload")
    current_condition_sha256 = expected_condition_hashes.get(condition_id)
    if current_condition_sha256 is None:
        return excluded_run(run_dir, f"condition {condition_id!r} is absent from the current study manifest")
    if recorded_condition_sha256 != current_condition_sha256:
        return excluded_run(run_dir, "frozen condition SHA-256 does not match the current resolved condition")

    metadata_path = run_dir / "metadata.json"
    if not metadata_path.is_file():
        return excluded_run(run_dir, "missing metadata.json")
    metadata = load_object(metadata_path)
    if metadata.get("run_id") != run_dir.name:
        return excluded_run(run_dir, "run metadata run_id does not match the run directory")
    profile = metadata.get("profile")
    if profile != "main":
        return excluded_run(run_dir, f"profile is {profile!r}, not 'main'")
    if metadata.get("status") != "completed":
        return excluded_run(run_dir, f"status is {metadata.get('status')!r}, not 'completed'")
    if metadata.get("protocol_comparable") is not True:
        return excluded_run(run_dir, "protocol_comparable is not true")
    if metadata.get("resumed") is True or metadata.get("resume_count", 0) != 0:
        return excluded_run(run_dir, "resume metadata conflicts with uninterrupted primary eligibility")
    replicate = metadata.get("replicate")
    if isinstance(replicate, bool) or not isinstance(replicate, int) or replicate < 1:
        return excluded_run(run_dir, "replicate must be a positive integer")

    report_path = run_dir / "report.json"
    if not report_path.is_file():
        return excluded_run(run_dir, "missing report.json; evaluate hidden snapshots and generate the per-run report")
    threshold = numeric(sidecar.get("completion_threshold", 1.0))
    if threshold is None or not 0.0 < threshold <= 1.0:
        return excluded_run(run_dir, "completion_threshold is invalid")

    try:
        provenance, hidden_manifest = verified_provenance(run_dir, sidecar, metadata)
        report = load_object(report_path)
        visible_points, hidden_points, snapshots, final_full = verified_hidden_trajectory(
            run_dir,
            report,
            metadata,
            hidden_manifest,
            str(provenance["candidate_adapter_sha256"]),
        )
    except SummaryError as error:
        return excluded_run(run_dir, str(error))
    hidden_rows = read_jsonl(run_dir / "artifacts" / "hidden-scores.jsonl")
    try:
        fuzz_columns, fuzz_warning = verified_fuzz_score(
            run_dir, snapshots, metadata, str(provenance["candidate_adapter_sha256"]), report, hidden_rows
        )
    except SummaryError as error:
        return excluded_run(run_dir, str(error))

    final_visible = final_point(visible_points)
    final_hidden = final_point(hidden_points)
    hidden_score = numeric(final_hidden.get("score"))
    hidden_micro = numeric(final_hidden.get("micro_score"))
    buildable_index = last_buildable_index(hidden_rows)
    hidden_score_last_buildable = (
        numeric(hidden_points[buildable_index].get("score")) if buildable_index is not None else 0.0
    )
    last_buildable_round = hidden_points[buildable_index].get("round") if buildable_index is not None else None
    hidden_time = first_threshold_time(hidden_points, threshold)
    final_summary = require_object(final_full.get("summary"), "final hidden evaluation summary")
    audit_ok = final_summary.get("audit_ok") is True
    build_ok = final_summary.get("build_ok") is True

    adapter_path = run_dir / "study-control" / "candidate.json"
    adapter = load_object(adapter_path)
    raw_extensions = adapter.get("source_extensions")
    source_extensions = {str(value) for value in raw_extensions} if isinstance(raw_extensions, list) else set()
    materialization_root = resolve_materialization_root(run_dir, sidecar.get("materialization_root"))
    candidate_scaffold = materialization_root / "data" / "partitions" / "visible" / ".study-scaffold"
    scaffold_root = candidate_scaffold if candidate_scaffold.is_dir() else None
    artifact = source_metrics(run_dir / "workspace", source_extensions, scaffold_root)

    pi_events = report.get("pi_events") if isinstance(report.get("pi_events"), dict) else {}
    usage = pi_events.get("usage") if isinstance(pi_events.get("usage"), dict) else {}
    report_guard = report.get("guard") if isinstance(report.get("guard"), dict) else {}
    try:
        calls, ledger_usage = pi_event_metrics(run_dir / "artifacts" / "events")
        guard = guard_event_metrics(run_dir / "artifacts" / "guard.jsonl")
        if usage != ledger_usage:
            raise SummaryError("report Pi usage is stale or disagrees with raw event ledgers")
        if guard_report_is_stale(report_guard, guard):
            raise SummaryError("report guard metrics are stale or disagree with artifacts/guard.jsonl")
    except SummaryError as error:
        return excluded_run(run_dir, str(error))
    extension = extension_event_metrics(run_dir / "artifacts" / "extension-events.jsonl")
    snapshot = snapshot_metrics(snapshots)
    axes = condition_axes(condition)
    rendered = require_object(sidecar.get("rendered"), "study-metadata.rendered")
    prompt_bytes = rendered.get("prompt_bytes") if isinstance(rendered.get("prompt_bytes"), dict) else {}
    finished = bool(hidden_score is not None and hidden_score >= threshold and build_ok and audit_ok)
    input_tokens = optional_token_count(usage, "input")
    output_tokens = optional_token_count(usage, "output")
    total_generation_tokens = (
        input_tokens + output_tokens if input_tokens is not None and output_tokens is not None else None
    )

    row: dict[str, Any] = {
        "study_id": expected_study,
        "study_sha256": expected_study_sha256,
        "condition_id": condition_id,
        "condition_sha256": recorded_condition_sha256,
        "run_id": run_dir.name,
        "profile": profile,
        "replicate": replicate,
        "status": metadata.get("status"),
        "termination_reason": metadata.get("termination_reason"),
        "protocol_comparable": metadata.get("protocol_comparable"),
        "elapsed_seconds": numeric(metadata.get("elapsed_seconds")),
        "visible_score": numeric(final_visible.get("score")),
        "hidden_score": hidden_score,
        "hidden_micro_score": hidden_micro,
        "hidden_score_last_buildable": hidden_score_last_buildable,
        "last_buildable_round": last_buildable_round,
        "completion_threshold": threshold,
        "finished": finished,
        "time_to_completion_seconds": hidden_time,
        "visible_auc": trajectory_auc(visible_points),
        "hidden_auc": trajectory_auc(hidden_points),
        "hidden_evaluation_rounds": len(hidden_points),
        "final_build_ok": build_ok,
        "final_audit_ok": audit_ok,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cache_read_tokens": optional_token_count(usage, "cache_read"),
        "cache_write_tokens": optional_token_count(usage, "cache_write"),
        "hidden_score_per_million_generation_tokens": (
            hidden_score / (total_generation_tokens / 1_000_000)
            if hidden_score is not None and total_generation_tokens is not None and total_generation_tokens > 0
            else None
        ),
        "guard_blocked_calls": int(guard.get("blocked_calls", 0) or 0),
        "guard_bash_timeouts": int(guard.get("bash_timeouts_fired", 0) or 0),
        "specification_bytes": numeric(rendered.get("specification_bytes")),
        "specification_words": numeric(rendered.get("specification_words")),
        "prompt_total_bytes": sum(
            int(value) for value in prompt_bytes.values() if isinstance(value, int) and not isinstance(value, bool)
        ),
        "visible_test_count": numeric(rendered.get("visible_test_count")),
        "agent_visible_test_count": numeric(rendered.get("agent_visible_test_count")),
        "hidden_test_count": numeric(rendered.get("hidden_test_count")),
        **provenance,
        **axes,
        **artifact,
        **extension,
        **calls,
        **snapshot,
        **fuzz_columns,
    }
    return row, fuzz_warning


def reject_duplicate_included_runs(rows: list[dict[str, Any]]) -> None:
    seen: dict[tuple[str, int], str] = {}
    for row in rows:
        key = (str(row.get("condition_id")), int(row["replicate"]))
        prior = seen.get(key)
        if prior is not None:
            raise SummaryError(
                f"Duplicate included runs for condition {key[0]!r}, replicate {key[1]}: {prior}, {row.get('run_id')}"
            )
        seen[key] = str(row.get("run_id"))


def reject_cohort_drift(rows: list[dict[str, Any]]) -> None:
    shared_fields = (
        "source_harness_manifest_sha256",
        "materialized_scripts_sha256",
        "materialized_hidden_partition_sha256",
        "materialized_evaluator_sha256",
        "materialized_evaluate_run_sha256",
        "materialized_run_experiment_sha256",
        "materialized_summarize_run_sha256",
        "source_harness_sha256",
        "source_scripts_sha256",
        "source_pi_sha256",
        "source_evaluator_sha256",
        "hidden_manifest_sha256",
        "hidden_test_count",
        "model_provider",
        "model_id",
        "model_thinking",
        "model_serving_revision",
        "docker_image_name",
        "docker_image_id",
        "starter_version",
    )
    condition_fields = (
        "condition_sha256",
        "materialized_harness_sha256",
        "rendered_assets_sha256",
        "specification_sha256",
        "prompt_hashes_sha256",
        "extension_hashes_sha256",
        "scaffold_hashes_sha256",
        "candidate_adapter_sha256",
        "visible_manifest_sha256",
        "runtime_control_sha256",
        "configuration_sha256",
        "budget_sha256",
    )

    def reject_drift(group: list[dict[str, Any]], fields: tuple[str, ...], scope: str) -> None:
        for field in fields:
            values: dict[str, list[str]] = defaultdict(list)
            for row in group:
                values[json.dumps(row.get(field), sort_keys=True)].append(str(row.get("run_id")))
            if len(values) > 1:
                details = "; ".join(
                    f"{', '.join(run_ids)}={value[:80]}" for value, run_ids in sorted(values.items())
                )
                raise SummaryError(f"Primary cohort drift in {scope} field {field}: {details}")

    reject_drift(rows, shared_fields, "shared")
    by_condition: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_condition[str(row.get("condition_id"))].append(row)
    for condition_id, group in sorted(by_condition.items()):
        reject_drift(group, condition_fields, f"condition {condition_id!r}")


def planned_cell_warnings(study: dict[str, Any], rows: list[dict[str, Any]]) -> list[str]:
    raw_conditions = study.get("conditions")
    if not isinstance(raw_conditions, list):
        raise SummaryError("Study conditions must be an array")
    condition_ids = []
    for raw in raw_conditions:
        if not isinstance(raw, dict) or not isinstance(raw.get("id"), str) or not raw["id"]:
            raise SummaryError("Every study condition must have a nonempty id")
        condition_ids.append(str(raw["id"]))
    replicates = sorted({int(row["replicate"]) for row in rows})
    included = {(str(row["condition_id"]), int(row["replicate"])) for row in rows}
    warnings = [
        f"missing eligible primary cell: condition={condition_id!r}, replicate={replicate}"
        for replicate in replicates
        for condition_id in condition_ids
        if (condition_id, replicate) not in included
    ]

    baseline = study.get("baseline_condition", "baseline")
    if isinstance(baseline, str) and baseline:
        for condition_id, replicate in sorted(included, key=lambda item: (item[1], item[0])):
            if condition_id != baseline and (baseline, replicate) not in included:
                warnings.append(
                    f"unpaired primary variant: condition={condition_id!r}, replicate={replicate} "
                    f"has no eligible {baseline!r} baseline"
                )
    return warnings


def median(values: Iterable[Any]) -> float | None:
    usable = [float(value) for value in values if numeric(value) is not None]
    return statistics.median(usable) if usable else None


def fmt(value: Any, digits: int = 3) -> str:
    number = numeric(value)
    return "-" if number is None else f"{number:.{digits}f}"


def grouped(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_condition: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_condition[str(row["condition_id"])].append(row)
    result: list[dict[str, Any]] = []
    for condition, group in sorted(by_condition.items()):
        completed_times = [row["time_to_completion_seconds"] for row in group if row["finished"]]
        median_elapsed = median(row["elapsed_seconds"] for row in group)
        median_completion = median(completed_times)
        result.append(
            {
                "condition_id": condition,
                "profile": group[0].get("profile"),
                "factor": group[0].get("factor"),
                "n": len(group),
                "finished": sum(bool(row["finished"]) for row in group),
                "finish_rate": sum(bool(row["finished"]) for row in group) / len(group),
                "median_hidden_score": median(row["hidden_score"] for row in group),
                "median_hidden_auc": median(row["hidden_auc"] for row in group),
                "median_elapsed_hours": median_elapsed / 3600 if median_elapsed is not None else None,
                "median_time_to_completion_hours": median_completion / 3600 if median_completion is not None else None,
                "median_input_tokens": median(row["input_tokens"] for row in group),
                "median_output_tokens": median(row["output_tokens"] for row in group),
                "median_model_calls": median(row["model_calls"] for row in group),
                "median_test_calls": median(row["visible_test_calls"] for row in group),
                "median_oracle_calls": median(row["oracle_calls"] for row in group),
                "median_source_loc": median(row["source_loc"] for row in group),
                "median_fuzz_macro": median(row["fuzz_macro"] for row in group if row.get("fuzz_macro") is not None),
                "fuzz_scored": sum(1 for row in group if row.get("fuzz_macro") is not None),
                "median_hidden_score_last_buildable": median(row["hidden_score_last_buildable"] for row in group),
                "median_fuzz_macro_last_buildable": median(
                    row["fuzz_macro_last_buildable"] for row in group if row.get("fuzz_macro_last_buildable") is not None
                ),
                "median_agent_test_loc": median(row["agent_test_loc"] for row in group),
                "median_specification_words": median(row["specification_words"] for row in group),
                "median_prompt_total_bytes": median(row["prompt_total_bytes"] for row in group),
                "median_visible_test_count": median(row["visible_test_count"] for row in group),
                "median_agent_visible_test_count": median(row["agent_visible_test_count"] for row in group),
                "median_visible_regressions": median(row["visible_regressions"] for row in group),
                "median_buildable_snapshot_fraction": median(row["buildable_snapshot_fraction"] for row in group),
            }
        )
    return result


def baseline_deltas(rows: list[dict[str, Any]], baseline: str = "baseline") -> list[dict[str, Any]]:
    bases = {
        row.get("replicate"): row
        for row in rows
        if row.get("condition_id") == baseline and row.get("replicate") is not None
    }
    deltas: list[dict[str, Any]] = []
    for row in rows:
        if row.get("condition_id") == baseline:
            continue
        base = bases.get(row.get("replicate"))
        if not base:
            continue

        def difference(field: str) -> float | None:
            left, right = numeric(row.get(field)), numeric(base.get(field))
            return left - right if left is not None and right is not None else None

        elapsed_delta = difference("elapsed_seconds")
        deltas.append(
            {
                "condition_id": row.get("condition_id"),
                "factor": row.get("factor"),
                "profile": row.get("profile"),
                "replicate": row.get("replicate"),
                "delta_hidden_score": difference("hidden_score"),
                "delta_hidden_auc": difference("hidden_auc"),
                "delta_fuzz_macro": difference("fuzz_macro"),
                "delta_hidden_score_last_buildable": difference("hidden_score_last_buildable"),
                "delta_fuzz_macro_last_buildable": difference("fuzz_macro_last_buildable"),
                "delta_elapsed_hours": elapsed_delta / 3600 if elapsed_delta is not None else None,
                "delta_input_tokens": difference("input_tokens"),
                "delta_output_tokens": difference("output_tokens"),
                "delta_test_calls": difference("visible_test_calls"),
                "delta_oracle_calls": difference("oracle_calls"),
                "finished": row.get("finished"),
                "baseline_finished": base.get("finished"),
            }
        )
    return deltas


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = sorted({key for row in rows for key in row})
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def markdown(study: dict[str, Any], rows: list[dict[str, Any]], groups: list[dict[str, Any]], warnings: list[str]) -> str:
    lines = [
        f"# PiCC study summary: {study['id']}",
        "",
        str(study.get("description", "")),
        "",
        "Primary inclusion: profile `main`, completed, uninterrupted, `protocol_comparable=true`, verified frozen provenance, and hidden evaluation for every snapshot.",
        "",
        "## Condition results",
        "",
        "| Condition | Profile | Factor | n | Finished | Finish rate | Hidden score | Fuzz macro (n scored) | Hidden (last buildable) | Fuzz (last buildable) | Hidden AUC | Hours | Input tokens | Output tokens | Test calls | Oracle calls | Source LOC |",
        "|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for group in groups:
        lines.append(
            f"| `{group['condition_id']}` | `{group.get('profile')}` | `{group.get('factor')}` | {group['n']} | {group['finished']} | "
            f"{fmt(group['finish_rate'])} | {fmt(group['median_hidden_score'])} | "
            f"{fmt(group['median_fuzz_macro'])} ({group['fuzz_scored']}) | "
            f"{fmt(group['median_hidden_score_last_buildable'])} | {fmt(group['median_fuzz_macro_last_buildable'])} | "
            f"{fmt(group['median_hidden_auc'])} | {fmt(group['median_elapsed_hours'], 2)} | "
            f"{fmt(group['median_input_tokens'], 0)} | {fmt(group['median_output_tokens'], 0)} | "
            f"{fmt(group['median_test_calls'], 1)} | {fmt(group['median_oracle_calls'], 1)} | "
            f"{fmt(group['median_source_loc'], 0)} |"
        )

    lines += [
        "",
        "## Interpretation boundary",
        "",
        (
            "- Conditions are a full crossing of the declared factors; every cell is paired with the baseline of its replicate, and interactions are for the per-cohort analysis script."
            if study.get("design") == "factorial"
            else "- Conditions are one-factor variants against a shared baseline; this is not a full factorial design."
        ),
        "- Language, framework, and scaffold conditions are external-validity blocks. Their effects include the implementation substrate and should not be interpreted as pure prompt effects.",
        "- Provenance records how a specification or test suite was created. Creation method is causal only when multiple independently created, coverage-matched artifacts are replicated.",
        "- Artifact quality here is objective behavioral correctness, build/audit status, authored tests, regressions, and size/churn. No LLM-as-judge score is used.",
        "- Hidden score is the corpus oracle (hand-written tests, valid and invalid). Fuzz macro is the generated-program oracle (stage-averaged agreement with GCC on valid programs) of the final snapshot; the two see different defects and are reported side by side.",
        "- LOC and style metrics are descriptive and should not be compared naively across languages.",
    ]
    if warnings:
        lines += ["", "## Exclusions and coverage warnings", ""]
        lines += [f"- {warning}" for warning in warnings]
    lines += ["", f"Included primary runs: {len(rows)}", ""]
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--study", required=True, type=Path)
    parser.add_argument("--runs-root", type=Path, default=REPO_ROOT / "runs")
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    study = load_object(args.study.resolve())
    study_id = str(study.get("id", ""))
    if not study_id:
        raise SummaryError("Study has no id")
    study_sha256 = sha256_file(args.study.resolve())
    condition_hashes = current_condition_hashes(study)
    output = (args.output or (REPO_ROOT / "runs" / "study-results" / study_id)).resolve()

    rows: list[dict[str, Any]] = []
    warnings: list[str] = []
    runs_root = args.runs_root.resolve()
    if runs_root.exists():
        for run_dir in sorted(runs_root.iterdir()):
            if not run_dir.is_dir() or run_dir.name.startswith(".") or run_dir.name == "study-results":
                continue
            row, warning = collect_run(run_dir, study_id, study_sha256, condition_hashes)
            if row is not None:
                rows.append(row)
            if warning:
                warnings.append(warning)
    reject_duplicate_included_runs(rows)
    if not rows:
        detail = "; ".join(warnings[:5])
        suffix = f" Exclusions: {detail}" if detail else ""
        raise SummaryError(f"No eligible primary-analysis runs found for study {study_id!r}.{suffix}")
    reject_cohort_drift(rows)
    warnings.extend(planned_cell_warnings(study, rows))
    for warning in warnings:
        print(f"warning: {warning}", file=sys.stderr)

    groups = grouped(rows)
    deltas = baseline_deltas(rows, baseline=str(study.get("baseline_condition", "baseline")))
    output.mkdir(parents=True, exist_ok=True)
    write_csv(output / "runs.csv", rows)
    write_csv(output / "conditions.csv", groups)
    write_csv(output / "paired-baseline-deltas.csv", deltas)
    payload = {
        "schema_version": 1,
        "study": study,
        "selection": {
            "profile": "main",
            "status": "completed",
            "protocol_comparable": True,
            "study_sha256": study_sha256,
            "replicate": "positive integer",
            "hidden_trajectory": "every frozen snapshot",
            "cohort_drift": "hard error",
            "missing_cells": "warning",
        },
        "runs": rows,
        "conditions": groups,
        "paired_baseline_deltas": deltas,
        "warnings": warnings,
    }
    (output / "summary.json").write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (output / "summary.md").write_text(markdown(study, rows, groups, warnings), encoding="utf-8")
    print(f"Wrote {output / 'summary.md'}")
    print(f"Wrote {output / 'runs.csv'}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SummaryError as error:
        print(f"error: {error}", file=sys.stderr)
        raise SystemExit(1)
