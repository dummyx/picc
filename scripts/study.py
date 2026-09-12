#!/usr/bin/env python3
"""Materialize and run controlled PiCC factor-study conditions.

This layer is deliberately additive.  It copies the currently checked-out,
hardened single-run harness into a condition-specific materialization, overlays
only the selected prompts/spec/tests/candidate adapter/reference policy, and
then delegates execution, resume, evaluation, and per-run reporting to the
existing scripts.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import os
import re
import random
import shutil
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from common import (
    ExperimentError,
    REPO_ROOT,
    atomic_write_json,
    load_config,
    sanitize_run_id,
    sha256_file,
)

SCHEMA_VERSION = 1
MATERIALIZATION_SCHEMA_VERSION = 1
VALID_DELIVERIES = {"task_file", "initial_prompt", "workspace_file"}
VALID_TEST_ACCESS = {"none", "tool", "files"}
VALID_FEEDBACK = {"none", "aggregate", "failures", "detailed"}
VALID_REFERENCE_MODES = {"none", "oracle", "source"}
RUNTIME_COPY_DIRS = ("config", "docker", "scripts", "pi", "prompts", "evaluator")
RUNTIME_COPY_FILES = ("VERSION", "MANIFEST.sha256")
SECRET_MARKERS = ("KEY", "TOKEN", "SECRET", "PASSWORD", "CREDENTIAL")
RUN_ID_MAX_LENGTH = 96
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
SIDECAR_ONLY_FIELDS = frozenset({"materialization_root", "frozen_at"})


class StudyError(ExperimentError):
    """A malformed study or condition materialization."""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def canonical_json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_json(value)).hexdigest()


def load_json_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise StudyError(f"Missing JSON file: {path}") from error
    except json.JSONDecodeError as error:
        raise StudyError(f"Invalid JSON in {path}: {error}") from error
    if not isinstance(value, dict):
        raise StudyError(f"Expected a JSON object: {path}")
    return value


def deep_merge(base: Any, overlay: Any) -> Any:
    if isinstance(base, dict) and isinstance(overlay, dict):
        result = copy.deepcopy(base)
        for key, value in overlay.items():
            result[key] = deep_merge(result[key], value) if key in result else copy.deepcopy(value)
        return result
    return copy.deepcopy(overlay)


def require_string(value: Any, field: str, *, allow_empty: bool = False) -> str:
    if not isinstance(value, str) or (not allow_empty and not value.strip()):
        raise StudyError(f"{field} must be a nonempty string")
    return value


def require_number(value: Any, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise StudyError(f"{field} must be numeric")
    result = float(value)
    if not (result == result and abs(result) != float("inf")):
        raise StudyError(f"{field} must be finite")
    return result


def require_int(value: Any, field: str, *, minimum: int | None = None) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise StudyError(f"{field} must be an integer")
    if minimum is not None and value < minimum:
        raise StudyError(f"{field} must be at least {minimum}")
    return value


def resolve_repo_path(value: Any, field: str, *, must_exist: bool = True) -> Path:
    raw = require_string(value, field)
    path = (REPO_ROOT / raw).resolve() if not Path(raw).is_absolute() else Path(raw).resolve()
    try:
        path.relative_to(REPO_ROOT.resolve())
    except ValueError:
        raise StudyError(f"{field} must resolve inside the repository: {raw}")
    if must_exist and not path.exists():
        raise StudyError(f"{field} does not exist: {raw}")
    return path


def require_partition_relative_path(value: Any, field: str) -> Path:
    raw = require_string(value, field)
    if "\0" in raw:
        raise StudyError(f"{field} contains a null byte")
    relative = Path(raw)
    if relative.is_absolute() or relative == Path(".") or ".." in relative.parts:
        raise StudyError(f"{field} must be a nonempty relative path without '..': {raw!r}")
    return relative


def require_sha256(value: Any, field: str) -> str:
    digest = require_string(value, field)
    if not re.fullmatch(r"[0-9A-Fa-f]{64}", digest):
        raise StudyError(f"{field} must be a 64-character hexadecimal SHA-256 digest")
    return digest.lower()


def resolve_contained_path(root: Path, path: Path, field: str) -> Path:
    try:
        resolved_root = root.resolve()
        resolved = path.resolve()
    except (OSError, RuntimeError) as error:
        raise StudyError(f"Could not resolve {field}: {path}") from error
    try:
        resolved.relative_to(resolved_root)
    except ValueError as error:
        raise StudyError(f"{field} must resolve inside {resolved_root}: {path}") from error
    return resolved


def validate_provenance(value: Any, field: str) -> None:
    if not isinstance(value, dict):
        raise StudyError(f"{field} must be an object")
    require_string(value.get("method"), f"{field}.method")
    for key in ("creator", "source", "artifact_family", "generation_model", "reviewed_by"):
        if key in value and value[key] is not None and not isinstance(value[key], str):
            raise StudyError(f"{field}.{key} must be a string or null")


def validate_adapter(path: Path, condition_id: str) -> dict[str, Any]:
    adapter = load_json_object(path)
    if adapter.get("schema_version") != 1:
        raise StudyError(f"{condition_id}: unsupported candidate adapter schema")
    require_string(adapter.get("language"), f"{condition_id}.candidate.adapter.language")
    require_string(adapter.get("framework"), f"{condition_id}.candidate.adapter.framework")
    build = adapter.get("build")
    run_config = adapter.get("run")
    if not isinstance(build, dict) or not isinstance(build.get("command"), list):
        raise StudyError(f"{condition_id}: adapter build.command must be an array")
    if not all(isinstance(item, str) and item for item in build["command"]):
        raise StudyError(f"{condition_id}: adapter build.command entries must be strings")
    require_string(build.get("artifact"), f"{condition_id}.candidate.adapter.build.artifact")
    if not isinstance(run_config, dict) or not isinstance(run_config.get("command"), list):
        raise StudyError(f"{condition_id}: adapter run.command must be an array")
    if not all(isinstance(item, str) and item for item in run_config["command"]):
        raise StudyError(f"{condition_id}: adapter run.command entries must be strings")
    extensions = adapter.get("source_extensions")
    if not isinstance(extensions, list) or not extensions or not all(
        isinstance(item, str) and item.startswith(".") for item in extensions
    ):
        raise StudyError(f"{condition_id}: adapter source_extensions must be a nonempty extension array")
    notes = adapter.get("agent_notes")
    if notes is not None and not isinstance(notes, str):
        raise StudyError(f"{condition_id}: adapter agent_notes must be a string")
    audit = adapter.get("audit", {})
    if not isinstance(audit, dict):
        raise StudyError(f"{condition_id}: adapter audit must be an object")
    for key in ("roots",):
        values = audit.get(key, [])
        if not isinstance(values, list) or not all(
            isinstance(item, str) and item and not item.startswith("/") and ".." not in Path(item).parts
            for item in values
        ):
            raise StudyError(f"{condition_id}: adapter audit.{key} must be relative paths without '..'")
    entry = audit.get("entry")
    if entry is not None and (
        not isinstance(entry, str) or not entry or entry.startswith("/") or ".." in Path(entry).parts
    ):
        raise StudyError(f"{condition_id}: adapter audit.entry must be a relative path without '..'")
    excluded = audit.get("exclude_paths", [])
    if not isinstance(excluded, list) or not all(
        isinstance(item, str) and item and not item.startswith("/") and ".." not in Path(item).parts
        for item in excluded
    ):
        raise StudyError(f"{condition_id}: adapter audit.exclude_paths must be relative paths without '..'")
    agent_policy = adapter.get("agent_policy", {})
    if not isinstance(agent_policy, dict):
        raise StudyError(f"{condition_id}: adapter agent_policy must be an object")
    blocked = agent_policy.get("blocked_bash_patterns", [])
    if not isinstance(blocked, list):
        raise StudyError(f"{condition_id}: adapter agent_policy.blocked_bash_patterns must be an array")
    for row in blocked:
        if (
            not isinstance(row, dict)
            or not isinstance(row.get("pattern"), str)
            or not row["pattern"]
            or not isinstance(row.get("reason"), str)
            or not row["reason"].strip()
        ):
            raise StudyError(f"{condition_id}: each blocked bash pattern needs a nonempty pattern and reason")
        try:
            re.compile(row["pattern"])
        except re.error as error:
            raise StudyError(f"{condition_id}: invalid blocked bash pattern {row['pattern']!r}: {error}") from error
    return adapter


def validate_condition(condition: dict[str, Any], study: dict[str, Any]) -> None:
    condition_id = require_string(condition.get("id"), "condition.id")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}", condition_id):
        raise StudyError(f"Invalid condition id: {condition_id!r}")
    require_string(condition.get("factor"), f"{condition_id}.factor")

    prompt = condition.get("prompt")
    if not isinstance(prompt, dict):
        raise StudyError(f"{condition_id}.prompt must be an object")
    for name in ("agents", "initial", "continuation"):
        path = resolve_repo_path(prompt.get(name), f"{condition_id}.prompt.{name}")
        if not path.is_file():
            raise StudyError(f"{condition_id}.prompt.{name} must be a file")

    specification = condition.get("specification")
    if not isinstance(specification, dict):
        raise StudyError(f"{condition_id}.specification must be an object")
    spec_path = resolve_repo_path(specification.get("path"), f"{condition_id}.specification.path")
    if not spec_path.is_file():
        raise StudyError(f"{condition_id}.specification.path must be a file")
    delivery = specification.get("delivery")
    if delivery not in VALID_DELIVERIES:
        raise StudyError(f"{condition_id}.specification.delivery must be one of {sorted(VALID_DELIVERIES)}")
    validate_provenance(specification.get("provenance"), f"{condition_id}.specification.provenance")

    tests = condition.get("tests")
    if not isinstance(tests, dict):
        raise StudyError(f"{condition_id}.tests must be an object")
    access = tests.get("access")
    feedback = tests.get("feedback")
    if access not in VALID_TEST_ACCESS:
        raise StudyError(f"{condition_id}.tests.access must be one of {sorted(VALID_TEST_ACCESS)}")
    if feedback not in VALID_FEEDBACK:
        raise StudyError(f"{condition_id}.tests.feedback must be one of {sorted(VALID_FEEDBACK)}")
    if access == "none" and feedback != "none":
        raise StudyError(f"{condition_id}: tests.feedback must be 'none' when tests.access is 'none'")
    if access != "none" and feedback == "none":
        raise StudyError(f"{condition_id}: tests.feedback='none' is only valid with tests.access='none'")
    fraction = require_number(tests.get("visible_subset_fraction", 1.0), f"{condition_id}.tests.visible_subset_fraction")
    if not 0.0 < fraction <= 1.0:
        raise StudyError(f"{condition_id}.tests.visible_subset_fraction must be in (0, 1]")
    push = tests.get("push_interval_minutes", 0)
    if not isinstance(push, int) or isinstance(push, bool) or push < 0:
        raise StudyError(f"{condition_id}.tests.push_interval_minutes must be a non-negative integer")
    if push > 0 and access == "none":
        raise StudyError(f"{condition_id}: tests.push_interval_minutes requires tests.access other than 'none'")
    require_int(tests.get("subset_seed", study.get("seed", 0)), f"{condition_id}.tests.subset_seed")
    validate_provenance(tests.get("provenance"), f"{condition_id}.tests.provenance")
    for source_key in ("visible_partition", "hidden_partition"):
        if tests.get(source_key) is not None:
            source_path = resolve_repo_path(tests[source_key], f"{condition_id}.tests.{source_key}")
            if not (source_path / "manifest.json").is_file():
                raise StudyError(f"{condition_id}.tests.{source_key} must contain manifest.json")

    candidate = condition.get("candidate")
    if not isinstance(candidate, dict):
        raise StudyError(f"{condition_id}.candidate must be an object")
    adapter_path = resolve_repo_path(candidate.get("adapter"), f"{condition_id}.candidate.adapter")
    adapter = validate_adapter(adapter_path, condition_id)
    language = require_string(candidate.get("language"), f"{condition_id}.candidate.language")
    framework = require_string(candidate.get("framework"), f"{condition_id}.candidate.framework")
    if language != adapter["language"] or framework != adapter["framework"]:
        raise StudyError(
            f"{condition_id}: candidate language/framework must match the selected adapter "
            f"({adapter['language']}/{adapter['framework']})"
        )
    scaffold = candidate.get("scaffold")
    if scaffold is not None:
        scaffold_path = resolve_repo_path(scaffold, f"{condition_id}.candidate.scaffold")
        if not scaffold_path.is_dir():
            raise StudyError(f"{condition_id}.candidate.scaffold must be a directory")

    reference = condition.get("reference")
    if not isinstance(reference, dict):
        raise StudyError(f"{condition_id}.reference must be an object")
    mode = reference.get("mode")
    if mode not in VALID_REFERENCE_MODES:
        raise StudyError(f"{condition_id}.reference.mode must be one of {sorted(VALID_REFERENCE_MODES)}")
    limit = require_int(reference.get("oracle_limit", 0), f"{condition_id}.reference.oracle_limit", minimum=0)
    if mode == "oracle" and limit <= 0:
        raise StudyError(f"{condition_id}: oracle reference requires a positive oracle_limit")
    if mode != "oracle" and limit != 0:
        raise StudyError(f"{condition_id}: oracle_limit must be zero unless mode='oracle'")
    source = reference.get("source")
    if mode == "source":
        if source is None:
            raise StudyError(f"{condition_id}: source reference requires reference.source")
        resolve_repo_path(source, f"{condition_id}.reference.source")
    elif source is not None:
        raise StudyError(f"{condition_id}: reference.source is only valid for source mode")

    environment = condition.get("environment", {})
    if not isinstance(environment, dict) or not isinstance(environment.get("overrides", {}), dict):
        raise StudyError(f"{condition_id}.environment.overrides must be an object")
    for key, value in environment.get("overrides", {}).items():
        if not isinstance(key, str) or not re.fullmatch(r"[A-Z][A-Z0-9_]*", key):
            raise StudyError(f"{condition_id}: invalid environment override key {key!r}")
        if any(marker in key.upper() for marker in SECRET_MARKERS):
            raise StudyError(f"{condition_id}: secret environment override {key} is prohibited")
        if not isinstance(value, (str, int, float, bool)):
            raise StudyError(f"{condition_id}: environment override {key} must be scalar")
        if isinstance(value, str) and ("'" in value or any(char in value for char in "\n\r\0")):
            raise StudyError(f"{condition_id}: environment override {key} cannot be serialized safely")
        if isinstance(value, float) and not math.isfinite(value):
            raise StudyError(f"{condition_id}: environment override {key} must be finite")

    budget = condition.get("budget", {})
    if not isinstance(budget, dict):
        raise StudyError(f"{condition_id}.budget must be an object")
    allowed_budget = {
        "pilot_hours",
        "pilot_rounds",
        "pilot_round_timeout_minutes",
        "pilot_max_stage",
        "main_hours",
        "main_rounds",
        "main_round_timeout_minutes",
        "main_max_stage",
    }
    unknown_budget = set(budget) - allowed_budget
    if unknown_budget:
        raise StudyError(f"{condition_id}: unknown budget keys: {sorted(unknown_budget)}")
    for key, value in budget.items():
        field = f"{condition_id}.budget.{key}"
        if key.endswith("_hours"):
            hours = require_number(value, field)
            if hours <= 0:
                raise StudyError(f"{field} must be greater than zero")
        elif key.endswith("_max_stage"):
            stage = require_int(value, field, minimum=1)
            if stage > 10:
                raise StudyError(f"{field} must be at most 10")
        else:
            require_int(value, field, minimum=1)


def load_study(path: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    path = path.resolve()
    study = load_json_object(path)
    if study.get("schema_version") != SCHEMA_VERSION:
        raise StudyError(f"Unsupported study schema in {path}: {study.get('schema_version')!r}")
    study_id = require_string(study.get("id"), "study.id")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}", study_id):
        raise StudyError(f"Invalid study id: {study_id!r}")
    require_string(study.get("description", ""), "study.description", allow_empty=True)
    require_int(study.get("seed", 0), "study.seed")
    threshold = require_number(study.get("completion_threshold", 1.0), "study.completion_threshold")
    if not 0.0 < threshold <= 1.0:
        raise StudyError("study.completion_threshold must be in (0, 1]")
    defaults = study.get("defaults")
    raw_conditions = study.get("conditions")
    if not isinstance(defaults, dict):
        raise StudyError("study.defaults must be an object")
    if not isinstance(raw_conditions, list) or not raw_conditions:
        raise StudyError("study.conditions must be a nonempty array")

    resolved: list[dict[str, Any]] = []
    ids: set[str] = set()
    for raw in raw_conditions:
        if not isinstance(raw, dict):
            raise StudyError("Every condition must be an object")
        condition = deep_merge(defaults, raw)
        condition_id = str(condition.get("id", ""))
        if condition_id in ids:
            raise StudyError(f"Duplicate condition id: {condition_id}")
        validate_condition(condition, study)
        ids.add(condition_id)
        resolved.append(condition)
    validate_design(study, resolved)
    return study, resolved


def validate_design(study: dict[str, Any], conditions: list[dict[str, Any]]) -> None:
    design = study.get("design")
    if design is None:
        return
    if design != "one-factor-at-a-time":
        raise StudyError(f"Unsupported study design: {design!r}")
    baseline_id = require_string(study.get("baseline_condition"), "study.baseline_condition")
    baseline = next((row for row in conditions if row["id"] == baseline_id), None)
    if baseline is None:
        raise StudyError(f"Baseline condition not found: {baseline_id}")
    blocks = {"prompt", "specification", "tests", "candidate", "reference", "environment", "budget"}
    for condition in conditions:
        if condition["id"] == baseline_id:
            continue
        factor = condition["factor"]
        if factor not in blocks:
            raise StudyError(
                f"{condition['id']}: OFAT factor must name one condition block; got {factor!r}"
            )
        changed = {block for block in blocks if condition.get(block) != baseline.get(block)}
        if changed != {factor}:
            raise StudyError(
                f"{condition['id']}: OFAT condition declares factor {factor!r} but changes {sorted(changed)}"
            )
        if condition["tests"].get("hidden_partition") != baseline["tests"].get("hidden_partition"):
            raise StudyError(
                f"{condition['id']}: hidden_partition must remain constant in an OFAT study"
            )


def find_condition(study: dict[str, Any], conditions: list[dict[str, Any]], condition_id: str) -> dict[str, Any]:
    for condition in conditions:
        if condition["id"] == condition_id:
            return condition
    available = ", ".join(condition["id"] for condition in conditions)
    raise StudyError(f"Unknown condition {condition_id!r}; available: {available}")


def render_template(text: str, variables: Mapping[str, str], source: str) -> str:
    rendered = text
    for key, value in variables.items():
        rendered = rendered.replace("{{" + key + "}}", value)
    unresolved = sorted(set(re.findall(r"\{\{([A-Z0-9_]+)\}\}", rendered)))
    if unresolved:
        raise StudyError(f"Unresolved template variables in {source}: {', '.join(unresolved)}")
    return rendered


def adapter_variables(adapter: dict[str, Any], condition: dict[str, Any]) -> dict[str, str]:
    variables = {str(key): str(value) for key, value in adapter.get("spec_variables", {}).items()}
    build_command = " ".join(adapter["build"]["command"])
    entry_command = " ".join(adapter["run"]["command"])
    variables.setdefault("LANGUAGE", str(condition["candidate"]["language"]))
    variables.setdefault("FRAMEWORK", str(condition["candidate"]["framework"]))
    variables.setdefault("BUILD_COMMAND", build_command)
    variables.setdefault("ENTRY_COMMAND", entry_command)
    variables.setdefault("DEPENDENCY_POLICY", str(adapter.get("dependency_policy", "only preinstalled dependencies")))
    return variables


def operational_guidance(condition: dict[str, Any], adapter: dict[str, Any]) -> dict[str, str]:
    tests = condition["tests"]
    if tests["access"] == "none":
        test_guidance = (
            "Visible tests and scores are intentionally unavailable. Use local builds and tests you author yourself; "
            "do not repeatedly call `test_visible`."
        )
    elif tests["access"] == "tool":
        test_guidance = (
            f"Visible tests are available only through `test_visible`; direct test files are withheld. "
            f"The tool returns {tests['feedback']} feedback."
        )
    else:
        test_guidance = (
            f"Visible test files may be inspected under `/visible-tests`, and `test_visible` returns "
            f"{tests['feedback']} feedback."
        )
    push = int(tests.get("push_interval_minutes", 0) or 0)
    if push > 0:
        test_guidance += (
            f" In addition, the harness runs the visible tests automatically about every {push} minutes and "
            f"delivers the same {tests['feedback']} report to you as a message, whether or not you asked."
        )

    reference = condition["reference"]
    if reference["mode"] == "none":
        reference_guidance = "No reference implementation or behavioral oracle is available."
    elif reference["mode"] == "oracle":
        reference_guidance = (
            f"A black-box `reference_oracle` tool is available for at most {reference['oracle_limit']} small, "
            "self-contained C programs. It reveals observable behavior only."
        )
    else:
        reference_guidance = (
            "A reference implementation is available read-only under `/visible-tests/reference`. "
            "Its provenance is recorded by the harness."
        )

    candidate_guidance = (
        f"Implement PiCC in {condition['candidate']['language']} using the "
        f"{condition['candidate']['framework']} framework setting. Build with `{' '.join(adapter['build']['command'])}`. "
        f"The evaluator invokes `{' '.join(adapter['run']['command'])}`. "
        f"Dependency policy: {adapter.get('dependency_policy', 'preinstalled dependencies only')}."
    )
    # Adapter-specific layout or typing rules travel with the candidate factor;
    # adapters without notes render byte-identically to earlier cohorts.
    notes = str(adapter.get("agent_notes") or "").strip()
    if notes:
        candidate_guidance += " " + notes
    return {
        "TEST_GUIDANCE": test_guidance,
        "REFERENCE_GUIDANCE": reference_guidance,
        "CANDIDATE_GUIDANCE": candidate_guidance,
    }


def copy_tree(source: Path, destination: Path) -> None:
    if destination.exists() or destination.is_symlink():
        if destination.is_symlink() or destination.is_file():
            destination.unlink()
        else:
            shutil.rmtree(destination)
    shutil.copytree(
        source,
        destination,
        symlinks=True,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".pytest_cache", "node_modules"),
    )


def copy_runtime_root(destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=False)
    for name in RUNTIME_COPY_DIRS:
        source = REPO_ROOT / name
        if not source.is_dir():
            raise StudyError(f"Required harness directory is missing: {source}")
        copy_tree(source, destination / name)
    for name in RUNTIME_COPY_FILES:
        source = REPO_ROOT / name
        if not source.is_file():
            raise StudyError(f"Required harness file is missing: {source}")
        shutil.copy2(source, destination / name)
    runs_link = destination / "runs"
    runs_link.symlink_to((REPO_ROOT / "runs").resolve(), target_is_directory=True)


def hash_tree(root: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    if not root.exists():
        return result
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root)
        if any(part in {"__pycache__", ".pytest_cache", "node_modules"} for part in relative.parts):
            continue
        if path.is_symlink():
            result[str(relative)] = "symlink:" + os.readlink(path)
        elif path.is_file() and path.suffix != ".pyc":
            result[str(relative)] = sha256_file(path)
    return result


def prefixed_hash_tree(prefix: str, root: Path) -> dict[str, str]:
    return {f"{prefix}/{path}": digest for path, digest in hash_tree(root).items()}


def materialized_harness_file_hashes(root: Path) -> dict[str, str]:
    root = root.resolve()
    result: dict[str, str] = {}
    ignored_parts = {"__pycache__", ".pytest_cache", "node_modules"}
    for relative_name in MATERIALIZED_HASH_DIRS:
        logical_directory = root / relative_name
        if logical_directory.is_symlink() or not logical_directory.is_dir():
            raise StudyError(f"Required materialized directory is missing or unsafe: {logical_directory}")
        directory = resolve_contained_path(root, logical_directory, f"materialized {relative_name}")
        for path in sorted(directory.rglob("*")):
            relative = path.relative_to(root)
            if any(part in ignored_parts for part in relative.parts) or path.suffix == ".pyc":
                continue
            if path.is_symlink():
                raise StudyError(f"Symlinks are prohibited in frozen materialized files: {path}")
            if path.is_dir():
                continue
            if not path.is_file():
                raise StudyError(f"Unsupported file type in frozen materialization: {path}")
            resolved = resolve_contained_path(root, path, f"materialized file {relative}")
            result[str(resolved.relative_to(root))] = sha256_file(resolved)

    for relative_name in MATERIALIZED_HASH_FILES:
        logical_file = root / relative_name
        if logical_file.is_symlink() or not logical_file.is_file():
            raise StudyError(f"Required materialized file is missing or unsafe: {logical_file}")
        resolved = resolve_contained_path(root, logical_file, f"materialized file {relative_name}")
        result[relative_name] = sha256_file(resolved)
    return result


def family_order(seed: int, stratum: tuple[int, str], family: str) -> str:
    return hashlib.sha256(f"{seed}\0{stratum[0]}\0{stratum[1]}\0{family}".encode("utf-8")).hexdigest()


def schedule_run_id(study_id: str, profile: str, replicate: int, condition_id: str) -> str:
    if profile not in {"pilot", "main"}:
        raise StudyError(f"Invalid schedule profile: {profile!r}")
    if isinstance(replicate, bool) or not isinstance(replicate, int) or replicate < 1:
        raise StudyError("Schedule replicate must be a positive integer")
    for field, value in (("study id", study_id), ("condition id", condition_id)):
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}", value):
            raise StudyError(f"Invalid {field}: {value!r}")

    candidate = f"{study_id}-{profile}-r{replicate:02d}-{condition_id}"
    if len(candidate) <= RUN_ID_MAX_LENGTH:
        return sanitize_run_id(candidate)

    digest = hashlib.sha256(candidate.encode("ascii")).hexdigest()[:16]
    prefix_length = RUN_ID_MAX_LENGTH - len(digest) - 1
    prefix = candidate[:prefix_length].rstrip("._-")
    return sanitize_run_id(f"{prefix}-{digest}")


def select_visible_tests(manifest: dict[str, Any], fraction: float, seed: int) -> list[dict[str, Any]]:
    tests = manifest.get("tests")
    if not isinstance(tests, list) or not tests:
        raise StudyError("Visible manifest contains no tests")
    by_stratum: dict[tuple[int, str], dict[str, list[dict[str, Any]]]] = {}
    for row in tests:
        if not isinstance(row, dict):
            raise StudyError("Visible manifest has a non-object test row")
        stage = int(row["stage"])
        validity = str(row["validity"])
        family = str(row.get("family") or row["id"])
        by_stratum.setdefault((stage, validity), {}).setdefault(family, []).append(row)

    selected: list[dict[str, Any]] = []
    for stratum, groups in sorted(by_stratum.items()):
        ordered = sorted(groups, key=lambda family: family_order(seed, stratum, family))
        count = len(ordered) if fraction >= 1.0 else max(1, math.ceil(len(ordered) * fraction))
        count = min(len(ordered), count)
        for family in ordered[:count]:
            selected.extend(groups[family])
    return sorted(selected, key=lambda row: (int(row["stage"]), str(row["validity"]), str(row["id"])))


def copy_partition(source: Path, destination: Path, *, fraction: float = 1.0, seed: int = 0) -> None:
    if source.is_symlink():
        raise StudyError(f"Partition source must not be a symlink: {source}")
    source_root = source.resolve()
    manifest_path = resolve_contained_path(source_root, source_root / "manifest.json", "partition manifest")
    manifest = load_json_object(manifest_path)
    tests = manifest.get("tests")
    if not isinstance(tests, list):
        raise StudyError("Partition manifest tests must be an array")
    selected = select_visible_tests(manifest, fraction, seed) if fraction < 1.0 else list(tests)

    if destination.is_symlink() or destination.is_file():
        raise StudyError(f"Partition destination must be a directory path: {destination}")
    if destination.exists():
        shutil.rmtree(destination)
    destination.mkdir(parents=True)
    destination_root = destination.resolve()
    for index, row in enumerate(selected):
        if not isinstance(row, dict):
            raise StudyError(f"Partition manifest test {index} must be an object")
        field = f"partition manifest test {index}.relative_path"
        relative = require_partition_relative_path(row.get("relative_path"), field)
        digest_field = f"partition manifest test {index}.sha256"
        expected_sha256 = require_sha256(row.get("sha256"), digest_field)
        source_file = resolve_contained_path(
            source_root,
            source_root / relative,
            field,
        )
        if not source_file.is_file():
            raise StudyError(f"Partition file missing: {source_file}")
        if sha256_file(source_file) != expected_sha256:
            raise StudyError(f"Partition file SHA-256 mismatch for {relative}")
        target = resolve_contained_path(
            destination_root,
            destination_root / relative,
            f"copy target for {field}",
        )
        target.parent.mkdir(parents=True, exist_ok=True)
        target = resolve_contained_path(destination_root, target, f"copy target for {field}")
        shutil.copy2(source_file, target)
        if sha256_file(target) != expected_sha256:
            raise StudyError(f"Copied partition file SHA-256 mismatch for {relative}")

    copied_manifest = copy.deepcopy(manifest)
    copied_manifest["tests"] = selected
    counts: dict[str, int] = {"total": len(selected)}
    for row in selected:
        key = f"stage_{int(row['stage'])}_{row['validity']}"
        counts[key] = counts.get(key, 0) + 1
    copied_manifest["counts"] = counts
    copied_manifest.setdefault("study_subset", {})
    copied_manifest["study_subset"] = {
        "source_manifest_sha256": sha256_file(manifest_path),
        "visible_subset_fraction": fraction,
        "subset_seed": seed,
        "policy": "family-grouped, stage-and-validity-stratified, deterministic",
    }
    atomic_write_json(destination / "manifest.json", copied_manifest)


def source_partitions(condition: dict[str, Any]) -> tuple[Path, Path]:
    tests = condition["tests"]
    visible = (
        resolve_repo_path(tests["visible_partition"], "tests.visible_partition")
        if tests.get("visible_partition")
        else resolve_repo_path("data/partitions/visible", "tests.visible_partition", must_exist=False)
    )
    hidden = (
        resolve_repo_path(tests["hidden_partition"], "tests.hidden_partition")
        if tests.get("hidden_partition")
        else resolve_repo_path("data/partitions/hidden", "tests.hidden_partition", must_exist=False)
    )
    for name, path in (("visible", visible), ("hidden", hidden)):
        if not (path / "manifest.json").is_file():
            raise StudyError(f"Missing {name} partition at {path}; run `make tests` first or configure a partition")
    return visible, hidden


def render_extension(template_path: Path, destination: Path, replacements: Mapping[str, Any]) -> None:
    text = template_path.read_text(encoding="utf-8")
    for key, value in replacements.items():
        if isinstance(value, bool):
            rendered = "true" if value else "false"
        elif isinstance(value, (int, float)):
            rendered = str(value)
        else:
            rendered = json.dumps(value, ensure_ascii=False)
        text = text.replace("__" + key + "__", rendered)
    unresolved = sorted(set(re.findall(r"__([A-Z0-9_]+)__", text)))
    if unresolved:
        raise StudyError(f"Unresolved extension placeholders in {template_path}: {', '.join(unresolved)}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(text, encoding="utf-8")


def patch_runner(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    if "reference_oracle" not in text:
        old_tools = "read,bash,edit,write,grep,find,ls,test_visible,experiment_status"
        new_tools = "read,bash,edit,write,grep,find,ls,test_visible,reference_oracle,experiment_status"
        if old_tools not in text:
            raise StudyError("Could not locate the Pi tool allowlist in the copied runner; update study.py for this harness revision")
        text = text.replace(old_tools, new_tools, 1)

    declaration = 'visible_tests = partitions_root / "visible"'
    if 'agent_visible_tests = REPO_ROOT / "data" / "agent-visible"' not in text:
        if declaration not in text:
            raise StudyError("Could not locate visible-test partition declaration in the copied runner")
        text = text.replace(
            declaration,
            declaration + '\n    agent_visible_tests = REPO_ROOT / "data" / "agent-visible"',
            1,
        )
    keyword = "visible_tests=visible_tests,"
    if keyword in text:
        text = text.replace(keyword, "visible_tests=agent_visible_tests,", 1)
    elif "visible_tests=agent_visible_tests," not in text:
        raise StudyError("Could not route the Pi container to the condition-specific agent-visible partition")

    gitignore_prefix = r'"target/\n*.o\n'
    if "__pycache__/" not in text:
        if gitignore_prefix not in text:
            raise StudyError("Could not extend the copied workspace .gitignore for Python candidates")
        text = text.replace(
            gitignore_prefix,
            r'"target/\n__pycache__/\n*.py[cod]\n*.o\n',
            1,
        )
    path.write_text(text, encoding="utf-8")


def effective_config_overrides(condition: dict[str, Any]) -> dict[str, str]:
    config = load_config()
    overrides: dict[str, str] = {}
    for key, value in config.items():
        if not any(marker in key.upper() for marker in SECRET_MARKERS):
            overrides[key] = str(value)
    for key, value in condition.get("environment", {}).get("overrides", {}).items():
        if any(marker in key.upper() for marker in SECRET_MARKERS):
            raise StudyError(f"Secret environment override {key} is prohibited")
        overrides[key] = str(value).lower() if isinstance(value, bool) else str(value)
    budget_map = {
        "pilot_hours": "PILOT_HOURS",
        "pilot_rounds": "PILOT_ROUNDS",
        "pilot_round_timeout_minutes": "PILOT_ROUND_TIMEOUT_MINUTES",
        "pilot_max_stage": "PILOT_MAX_STAGE",
        "main_hours": "MAIN_HOURS",
        "main_rounds": "MAIN_ROUNDS",
        "main_round_timeout_minutes": "MAIN_ROUND_TIMEOUT_MINUTES",
        "main_max_stage": "MAIN_MAX_STAGE",
    }
    for key, value in condition.get("budget", {}).items():
        overrides[budget_map[key]] = str(value)
    return overrides


def append_env_overrides(path: Path, overrides: Mapping[str, str]) -> None:
    rendered: list[str] = []
    for key, value in sorted(overrides.items()):
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key):
            raise StudyError(f"Invalid configuration key: {key!r}")
        if not isinstance(value, str):
            raise StudyError(f"Configuration value for {key} must be a string")
        if "\n" in value or "\r" in value or "\0" in value:
            raise StudyError(f"Configuration value for {key} contains a prohibited control character")
        if "'" in value:
            raise StudyError(f"Configuration value for {key} contains a single quote")
        rendered.append(f"{key}='{value}'\n")

    with path.open("a", encoding="utf-8") as handle:
        handle.write("\n# Effective configuration frozen by scripts/study.py\n")
        handle.writelines(rendered)


def _materialize_direct(
    study_path: Path,
    study: dict[str, Any],
    condition: dict[str, Any],
    run_id: str,
    *,
    replace: bool = False,
) -> Path:
    repo_root = REPO_ROOT.resolve()
    logical_runs = REPO_ROOT / "runs"
    logical_materializations = logical_runs / ".study-materializations"
    for label, path in (
        ("runs directory", logical_runs),
        ("study materializations directory", logical_materializations),
    ):
        if path.is_symlink():
            raise StudyError(f"{label} must not be a symlink: {path}")

    runs_root = resolve_contained_path(repo_root, logical_runs, "runs directory")
    if not runs_root.is_dir():
        raise StudyError(f"Runs directory is missing: {runs_root}")
    materializations_root = resolve_contained_path(
        runs_root,
        logical_materializations,
        "study materializations directory",
    )
    if materializations_root.exists() and not materializations_root.is_dir():
        raise StudyError(f"Study materializations path is not a directory: {materializations_root}")

    logical_run = logical_runs / run_id
    if logical_run.is_symlink():
        raise StudyError(f"Run directory must not be a symlink: {logical_run}")
    run_dir = resolve_contained_path(runs_root, logical_run, "run directory")
    if run_dir.exists():
        raise StudyError(f"Cannot materialize over an existing run: {run_dir}")

    logical_materialization = logical_materializations / run_id
    if logical_materialization.is_symlink():
        raise StudyError(f"Study materialization must not be a symlink: {logical_materialization}")
    materialization_root = resolve_contained_path(
        materializations_root,
        logical_materialization,
        "study materialization",
    )
    if materialization_root.exists():
        if not replace:
            raise StudyError(f"Materialization already exists: {materialization_root}")
        if not materialization_root.is_dir():
            raise StudyError(f"Materialization path is not a directory: {materialization_root}")
        shutil.rmtree(materialization_root)
    materialization_root.parent.mkdir(parents=True, exist_ok=True)
    copy_runtime_root(materialization_root)

    adapter_source = resolve_repo_path(condition["candidate"]["adapter"], "candidate.adapter")
    adapter = load_json_object(adapter_source)
    variables = adapter_variables(adapter, condition)
    variables.update(operational_guidance(condition, adapter))

    spec_source = resolve_repo_path(condition["specification"]["path"], "specification.path")
    rendered_spec = render_template(spec_source.read_text(encoding="utf-8"), variables, str(spec_source))
    delivery = condition["specification"]["delivery"]
    spec_location = {
        "task_file": "`TASK.md`",
        "initial_prompt": "the full specification embedded in the initial request",
        "workspace_file": "`SPEC.md` in the product workspace",
    }[delivery]
    variables["SPEC_LOCATION"] = spec_location

    prompt_sources = {
        name: resolve_repo_path(condition["prompt"][name], f"prompt.{name}")
        for name in ("agents", "initial", "continuation")
    }
    prompt_dir = materialization_root / "prompts"
    agents = render_template(prompt_sources["agents"].read_text(encoding="utf-8"), variables, str(prompt_sources["agents"]))
    initial_variables = dict(variables)
    initial_variables["INITIAL_SPEC_BLOCK"] = rendered_spec if delivery == "initial_prompt" else ""
    initial = render_template(prompt_sources["initial"].read_text(encoding="utf-8"), initial_variables, str(prompt_sources["initial"]))
    continuation = render_template(
        prompt_sources["continuation"].read_text(encoding="utf-8"), variables, str(prompt_sources["continuation"])
    )
    if delivery == "task_file":
        task = rendered_spec
    elif delivery == "initial_prompt":
        task = (
            "# PiCC task pointer\n\nThe full, controlling task specification was supplied in the initial request. "
            "Continue implementing that specification. The harness intentionally does not duplicate it here.\n"
        )
    else:
        task = "# PiCC task pointer\n\nRead and implement the controlling specification in `SPEC.md`.\n"

    (prompt_dir / "AGENTS.md").write_text(agents.rstrip() + "\n", encoding="utf-8")
    (prompt_dir / "INITIAL.txt").write_text(initial.rstrip() + "\n", encoding="utf-8")
    (prompt_dir / "CONTINUE.txt").write_text(continuation.rstrip() + "\n", encoding="utf-8")
    (prompt_dir / "TASK.md").write_text(task.rstrip() + "\n", encoding="utf-8")

    evaluator_dir = materialization_root / "evaluator"
    for name in ("evaluate.py", "fuzz_generator.py", "fuzz_evaluate.py"):
        shutil.copy2(REPO_ROOT / "studies" / "runtime" / name, evaluator_dir / name)
    shutil.copy2(adapter_source, evaluator_dir / "candidate.json")

    visible_source, hidden_source = source_partitions(condition)
    partitions_root = materialization_root / "data" / "partitions"
    fraction = float(condition["tests"].get("visible_subset_fraction", 1.0))
    subset_seed = int(condition["tests"].get("subset_seed", study.get("seed", 0)))
    copy_partition(visible_source, partitions_root / "visible", fraction=fraction, seed=subset_seed)
    copy_partition(hidden_source, partitions_root / "hidden", fraction=1.0, seed=subset_seed)

    scaffold = condition["candidate"].get("scaffold")
    has_scaffold = scaffold is not None or delivery == "workspace_file"
    scaffold_destination = partitions_root / "visible" / ".study-scaffold"
    if scaffold is not None:
        copy_tree(resolve_repo_path(scaffold, "candidate.scaffold"), scaffold_destination)
    elif has_scaffold:
        scaffold_destination.mkdir(parents=True, exist_ok=True)
    if delivery == "workspace_file":
        scaffold_destination.mkdir(parents=True, exist_ok=True)
        (scaffold_destination / "SPEC.md").write_text(rendered_spec.rstrip() + "\n", encoding="utf-8")

    reference = condition["reference"]
    if reference["mode"] == "source":
        reference_source = resolve_repo_path(reference["source"], "reference.source")
        target = partitions_root / "visible" / "reference"
        if reference_source.is_dir():
            copy_tree(reference_source, target)
        else:
            target.mkdir(parents=True, exist_ok=True)
            shutil.copy2(reference_source, target / reference_source.name)

    agent_visible = materialization_root / "data" / "agent-visible"
    if condition["tests"]["access"] == "none":
        agent_visible.mkdir(parents=True, exist_ok=True)
        atomic_write_json(
            agent_visible / "manifest.json",
            {
                "schema_version": 1,
                "partition": "agent-visible-withheld",
                "counts": {"total": 0},
                "tests": [],
            },
        )
        if scaffold_destination.is_dir():
            copy_tree(scaffold_destination, agent_visible / ".study-scaffold")
        reference_directory = partitions_root / "visible" / "reference"
        if reference_directory.is_dir():
            copy_tree(reference_directory, agent_visible / "reference")
    else:
        copy_tree(partitions_root / "visible", agent_visible)

    extensions = materialization_root / "pi" / "extensions"
    if extensions.exists():
        shutil.rmtree(extensions)
    extensions.mkdir(parents=True)
    replacements = {
        "TEST_ACCESS": condition["tests"]["access"],
        "FEEDBACK_MODE": condition["tests"]["feedback"],
        "PUSH_INTERVAL_MINUTES": int(condition["tests"].get("push_interval_minutes", 0) or 0),
        "REFERENCE_MODE": reference["mode"],
        "ORACLE_LIMIT": int(reference.get("oracle_limit", 0)),
        "ALLOW_TEST_FILES": condition["tests"]["access"] == "files",
        "ALLOW_REFERENCE_FILES": reference["mode"] == "source",
        "HAS_SCAFFOLD": has_scaffold,
        "CANDIDATE_BLOCKED_BASH_PATTERNS": [
            {"pattern": str(row["pattern"]), "reason": str(row["reason"])}
            for row in adapter.get("agent_policy", {}).get("blocked_bash_patterns", [])
        ],
    }
    runtime = REPO_ROOT / "studies" / "runtime"
    render_extension(runtime / "experiment-tools.ts.in", extensions / "experiment-tools.ts", replacements)
    render_extension(runtime / "experiment-guard.ts.in", extensions / "experiment-guard.ts", replacements)
    render_extension(runtime / "study-setup.ts.in", extensions / "study-setup.ts", replacements)
    patch_runner(materialization_root / "scripts" / "run_experiment.py")
    effective_config = effective_config_overrides(condition)
    append_env_overrides(materialization_root / "config" / "defaults.env", effective_config)

    resolved_payload = {
        "schema_version": MATERIALIZATION_SCHEMA_VERSION,
        "created_at": utc_now(),
        "study_id": study["id"],
        "study_path": (
            str(study_path.resolve().relative_to(REPO_ROOT.resolve()))
            if study_path.resolve().is_relative_to(REPO_ROOT.resolve())
            else str(study_path.resolve())
        ),
        "study_sha256": sha256_file(study_path.resolve()),
        "condition": condition,
        "condition_sha256": sha256_json(condition),
        "run_id": run_id,
        "effective_config": effective_config,
        "completion_threshold": study.get("completion_threshold", 1.0),
        "source_harness": {
            "repo_root": str(REPO_ROOT),
            "manifest_sha256": sha256_file(materialization_root / "MANIFEST.sha256"),
            "file_hashes": {
                **prefixed_hash_tree("scripts", REPO_ROOT / "scripts"),
                **prefixed_hash_tree("pi", REPO_ROOT / "pi"),
                **prefixed_hash_tree("evaluator", REPO_ROOT / "evaluator"),
            },
        },
        "materialized_harness": {
            "file_hashes": materialized_harness_file_hashes(materialization_root),
        },
        "rendered": {
            "specification_sha256": hashlib.sha256(rendered_spec.encode("utf-8")).hexdigest(),
            "specification_bytes": len(rendered_spec.encode("utf-8")),
            "specification_words": len(re.findall(r"\S+", rendered_spec)),
            "prompt_hashes": hash_tree(prompt_dir),
            "prompt_bytes": {
                path.name: len(path.read_bytes()) for path in sorted(prompt_dir.glob("*")) if path.is_file()
            },
            "extension_hashes": hash_tree(extensions),
            "candidate_adapter_sha256": sha256_file(evaluator_dir / "candidate.json"),
            "visible_manifest_sha256": sha256_file(partitions_root / "visible" / "manifest.json"),
            "hidden_manifest_sha256": sha256_file(partitions_root / "hidden" / "manifest.json"),
            "visible_test_count": len(load_json_object(partitions_root / "visible" / "manifest.json").get("tests", [])),
            "agent_visible_test_count": len(load_json_object(agent_visible / "manifest.json").get("tests", [])),
            "hidden_test_count": len(load_json_object(partitions_root / "hidden" / "manifest.json").get("tests", [])),
            "scaffold_hashes": hash_tree(scaffold_destination),
        },
    }
    atomic_write_json(materialization_root / "study-materialization.json", resolved_payload)
    return materialization_root


def cleanup_unstarted_materialization(run_id: str, materialization_root: Path) -> None:
    run_id = sanitize_run_id(run_id)
    logical_runs = REPO_ROOT / "runs"
    logical_parent = logical_runs / ".study-materializations"
    expected = logical_parent / run_id
    run_dir = logical_runs / run_id
    if run_dir.exists() or run_dir.is_symlink() or not materialization_root.exists():
        return
    if any(path.is_symlink() for path in (logical_runs, logical_parent, expected, materialization_root)):
        return
    try:
        parent = logical_parent.resolve()
        actual = materialization_root.resolve()
        expected_resolved = expected.resolve()
        parent.relative_to(logical_runs.resolve())
        actual.relative_to(parent)
    except (OSError, RuntimeError, ValueError):
        return
    if actual != expected_resolved or not actual.is_dir():
        return
    shutil.rmtree(actual)


def materialize(
    study_path: Path,
    study: dict[str, Any],
    condition: dict[str, Any],
    run_id: str,
    *,
    replace: bool = False,
) -> Path:
    run_id = sanitize_run_id(run_id)
    target = REPO_ROOT / "runs" / ".study-materializations" / run_id
    existed_before = target.exists() or target.is_symlink()
    try:
        return _materialize_direct(study_path, study, condition, run_id, replace=replace)
    except BaseException:
        if not existed_before:
            cleanup_unstarted_materialization(run_id, target)
        raise


def safe_environment(materialization_root: Path) -> dict[str, str]:
    record = load_json_object(materialization_root / "study-materialization.json")
    raw_frozen = record.get("effective_config")
    if not isinstance(raw_frozen, dict):
        raise StudyError("Study materialization has no frozen effective_config")

    frozen: dict[str, str] = {}
    for key, value in raw_frozen.items():
        if not isinstance(key, str) or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key):
            raise StudyError(f"Invalid frozen configuration key: {key!r}")
        if not isinstance(value, str):
            raise StudyError(f"Frozen configuration value for {key} must be a string")
        if any(marker in key.upper() for marker in SECRET_MARKERS):
            raise StudyError(f"Frozen effective_config must not contain secret key {key}")
        frozen[key] = value

    stale = sorted(set(frozen) & {"ZAI_PROVIDER", "ZAI_MODEL", "ZAI_THINKING"})
    if stale:
        raise StudyError(
            "Study materialization predates the MODEL_* configuration rename and "
            "cannot be executed by this harness revision: " + ", ".join(stale)
        )
    provider = (frozen.get("MODEL_PROVIDER", "") or "").strip()
    secret_by_provider = {
        "zai": "ZAI_API_KEY",
        "zai-coding-cn": "ZAI_CODING_CN_API_KEY",
        "local": "LOCAL_API_KEY",
    }
    if provider not in secret_by_provider:
        raise StudyError(
            f"Frozen materialization declares no usable provider: {provider!r}"
            if not provider
            else f"Unsupported frozen provider: {provider!r}"
        )

    current = load_config()
    secret_name = secret_by_provider[provider]
    secret_value = current.get(secret_name)
    env = dict(os.environ)
    for key in list(env):
        if key in frozen or any(marker in key.upper() for marker in SECRET_MARKERS):
            env.pop(key, None)
    scrubbed = (
        "MODEL_PROVIDER",
        "MODEL_ID",
        "MODEL_THINKING",
        # Legacy names: the materialized runner refuses them, so host drift
        # using the old spelling must not reach the frozen execution.
        "ZAI_PROVIDER",
        "ZAI_MODEL",
        "ZAI_THINKING",
        "ZAI_API_KEY",
        "ZAI_CODING_CN_API_KEY",
        "LOCAL_API_KEY",
    )
    for key in scrubbed:
        env.pop(key, None)
    env.update(frozen)
    if secret_value:
        env[secret_name] = secret_value
    return env


def freeze_run_study_metadata(run_id: str, materialization_root: Path) -> None:
    run_dir = REPO_ROOT / "runs" / run_id
    if not run_dir.is_dir():
        return
    payload = load_json_object(materialization_root / "study-materialization.json")
    payload["materialization_root"] = str(materialization_root.relative_to(REPO_ROOT))
    payload["frozen_at"] = utc_now()
    atomic_write_json(run_dir / "study-metadata.json", payload)
    control = run_dir / "study-control"
    if control.exists():
        shutil.rmtree(control)
    control.mkdir(parents=True)
    shutil.copy2(materialization_root / "study-materialization.json", control / "materialization.json")
    shutil.copytree(materialization_root / "prompts", control / "prompts")
    shutil.copy2(materialization_root / "evaluator" / "candidate.json", control / "candidate.json")
    shutil.copy2(materialization_root / "data" / "partitions" / "visible" / "manifest.json", control / "visible-manifest.json")
    shutil.copy2(materialization_root / "data" / "partitions" / "hidden" / "manifest.json", control / "hidden-manifest.json")


def subprocess_checked(command: list[str], *, cwd: Path, env: Mapping[str, str] | None = None) -> int:
    result = subprocess.run(command, cwd=cwd, env=dict(env) if env else None, check=False)
    return result.returncode


def study_for_run(run_id: str) -> tuple[Path, dict[str, Any]]:
    repo_root = REPO_ROOT.resolve()
    logical_runs = REPO_ROOT / "runs"
    logical_run = logical_runs / run_id
    logical_sidecar = logical_run / "study-metadata.json"
    for label, path in (
        ("runs directory", logical_runs),
        ("run directory", logical_run),
        ("study metadata", logical_sidecar),
    ):
        if path.is_symlink():
            raise StudyError(f"{label} must not be a symlink: {path}")

    runs_root = resolve_contained_path(repo_root, logical_runs, "runs directory")
    run_root = resolve_contained_path(runs_root, logical_run, "run directory")
    sidecar = resolve_contained_path(run_root, logical_sidecar, "study metadata")
    payload = load_json_object(sidecar)

    raw_root = require_string(payload.get("materialization_root"), "study-metadata.materialization_root")
    relative_root = Path(raw_root)
    expected_relative = Path("runs") / ".study-materializations" / run_id
    if relative_root.is_absolute() or relative_root != expected_relative:
        raise StudyError(
            "study-metadata.materialization_root must be exactly "
            f"{expected_relative}, got {raw_root!r}"
        )

    logical_materializations = logical_runs / ".study-materializations"
    logical_root = logical_materializations / run_id
    for label, path in (
        ("study materializations directory", logical_materializations),
        ("study materialization", logical_root),
    ):
        if path.is_symlink():
            raise StudyError(f"{label} must not be a symlink: {path}")

    materializations_root = resolve_contained_path(
        runs_root,
        logical_materializations,
        "study materializations directory",
    )
    root = resolve_contained_path(materializations_root, logical_root, "study materialization")
    logical_record = logical_root / "study-materialization.json"
    if logical_record.is_symlink():
        raise StudyError(f"Study materialization record must not be a symlink: {logical_record}")
    record_path = resolve_contained_path(root, logical_record, "study materialization record")
    if not record_path.is_file():
        raise StudyError(f"Study materialization is missing for run {run_id}: {root}")
    materialization = load_json_object(record_path)
    if materialization.get("run_id") != run_id:
        raise StudyError("Study materialization run ID does not match the requested run")

    source_harness = materialization.get("source_harness")
    if not isinstance(source_harness, dict):
        raise StudyError("Study materialization has no source_harness provenance")
    expected_manifest_sha256 = require_sha256(
        source_harness.get("manifest_sha256"),
        "study-materialization.source_harness.manifest_sha256",
    )
    logical_manifest = logical_root / "MANIFEST.sha256"
    if logical_manifest.is_symlink():
        raise StudyError(f"Frozen release manifest must not be a symlink: {logical_manifest}")
    manifest_path = resolve_contained_path(root, logical_manifest, "frozen release manifest")
    if not manifest_path.is_file():
        raise StudyError(f"Frozen release manifest is missing: {manifest_path}")
    if sha256_file(manifest_path) != expected_manifest_sha256:
        raise StudyError("Frozen release manifest SHA-256 does not match study provenance")

    missing_sidecar_fields = set(materialization) - set(payload)
    sidecar_only_fields = set(payload) - set(materialization)
    if missing_sidecar_fields or sidecar_only_fields != SIDECAR_ONLY_FIELDS:
        raise StudyError(
            "Study metadata must contain the exact frozen materialization plus only "
            f"{sorted(SIDECAR_ONLY_FIELDS)}; missing={sorted(missing_sidecar_fields)}, "
            f"extra={sorted(sidecar_only_fields)}"
        )
    require_string(payload.get("frozen_at"), "study-metadata.frozen_at")
    for field, value in materialization.items():
        if payload.get(field) != value:
            raise StudyError(f"Study metadata {field} disagrees with the materialization")

    logical_control = logical_run / "study-control"
    logical_control_record = logical_control / "materialization.json"
    for label, path in (
        ("study control directory", logical_control),
        ("study control materialization", logical_control_record),
    ):
        if path.is_symlink():
            raise StudyError(f"{label} must not be a symlink: {path}")
    control_root = resolve_contained_path(run_root, logical_control, "study control directory")
    control_record_path = resolve_contained_path(
        control_root,
        logical_control_record,
        "study control materialization",
    )
    if not control_record_path.is_file():
        raise StudyError(f"Frozen study control materialization is missing: {control_record_path}")
    if load_json_object(control_record_path) != materialization:
        raise StudyError("Study control materialization disagrees with the materialized record")

    materialized_harness = materialization.get("materialized_harness")
    if not isinstance(materialized_harness, dict):
        raise StudyError("Study materialization has no materialized_harness provenance")
    expected_file_hashes = materialized_harness.get("file_hashes")
    if not isinstance(expected_file_hashes, dict) or not all(
        isinstance(path, str) and isinstance(digest, str)
        for path, digest in expected_file_hashes.items()
    ):
        raise StudyError("Study materialization has an invalid critical file-hash map")
    actual_file_hashes = materialized_harness_file_hashes(root)
    if actual_file_hashes != expected_file_hashes:
        changed = sorted(
            path
            for path in set(actual_file_hashes) | set(expected_file_hashes)
            if actual_file_hashes.get(path) != expected_file_hashes.get(path)
        )
        detail = ", ".join(changed[:8])
        raise StudyError(f"Frozen materialized harness files changed: {detail}")
    return root, payload


def command_validate(args: argparse.Namespace) -> int:
    study, conditions = load_study(args.study)
    print(f"Study `{study['id']}` is valid: {len(conditions)} conditions")
    for condition in conditions:
        print(
            f"  {condition['id']:<24} factor={condition['factor']:<18} "
            f"spec={condition['specification']['delivery']:<14} "
            f"tests={condition['tests']['access']}/{condition['tests']['feedback']} "
            f"candidate={condition['candidate']['language']}/{condition['candidate']['framework']} "
            f"reference={condition['reference']['mode']}"
        )
    return 0


def command_list(args: argparse.Namespace) -> int:
    study, conditions = load_study(args.study)
    print(f"{study['id']}: {study.get('description', '')}")
    for condition in conditions:
        print(f"{condition['id']}\t{condition['factor']}\t{condition.get('description', '')}")
    return 0


def command_schedule(args: argparse.Namespace) -> int:
    if args.replicates < 1:
        raise StudyError("--replicates must be at least 1")
    study, conditions = load_study(args.study)
    rows: list[dict[str, Any]] = []
    sequence = 0
    for replicate in range(1, args.replicates + 1):
        ordered = [condition["id"] for condition in conditions]
        random.Random(int(study.get("seed", 0)) + replicate).shuffle(ordered)
        for condition_id in ordered:
            sequence += 1
            run_id = schedule_run_id(study["id"], args.profile, replicate, condition_id)
            rows.append(
                {
                    "sequence": sequence,
                    "replicate": replicate,
                    "condition": condition_id,
                    "profile": args.profile,
                    "run_id": run_id,
                    "command": (
                        f"make study-run STUDY={args.study} CONDITION={condition_id} "
                        f"PROFILE={args.profile} RUN_ID={run_id} REPLICATE={replicate}"
                    ),
                }
            )
    payload = {
        "schema_version": 1,
        "study_id": study["id"],
        "study_sha256": sha256_file(args.study.resolve()),
        "seed": int(study.get("seed", 0)),
        "replicates": args.replicates,
        "profile": args.profile,
        "rows": rows,
    }
    if args.output:
        atomic_write_json(args.output.resolve(), payload)
        print(args.output.resolve())
    else:
        print("sequence\treplicate\tcondition\trun_id\tcommand")
        for row in rows:
            print(
                f"{row['sequence']}\t{row['replicate']}\t{row['condition']}\t"
                f"{row['run_id']}\t{row['command']}"
            )
    return 0


def command_materialize(args: argparse.Namespace) -> int:
    study, conditions = load_study(args.study)
    condition = find_condition(study, conditions, args.condition)
    run_id = sanitize_run_id(args.run_id)
    root = materialize(args.study, study, condition, run_id, replace=args.replace)
    print(root)
    return 0


def command_run(args: argparse.Namespace) -> int:
    study, conditions = load_study(args.study)
    if args.replicate is not None and args.replicate < 1:
        raise StudyError("--replicate must be at least 1")
    condition = find_condition(study, conditions, args.condition)
    run_id = sanitize_run_id(args.run_id)
    if (REPO_ROOT / "runs" / run_id).exists():
        raise StudyError(f"Run already exists: {run_id}")
    root = materialize(args.study, study, condition, run_id, replace=False)
    command = [
        sys.executable,
        str(root / "scripts" / "run_experiment.py"),
        "--profile",
        args.profile,
        "--run-id",
        run_id,
    ]
    if args.replicate is not None:
        command += ["--replicate", str(args.replicate)]
    run_dir = REPO_ROOT / "runs" / run_id
    try:
        return subprocess_checked(command, cwd=root, env=safe_environment(root))
    finally:
        if run_dir.is_dir() and not run_dir.is_symlink():
            freeze_run_study_metadata(run_id, root)
        else:
            cleanup_unstarted_materialization(run_id, root)


def command_resume(args: argparse.Namespace) -> int:
    run_id = sanitize_run_id(args.run_id)
    root, _ = study_for_run(run_id)
    return subprocess_checked(
        [sys.executable, str(root / "scripts" / "run_experiment.py"), "--resume", "--run-id", run_id],
        cwd=root,
        env=safe_environment(root),
    )


def command_evaluate(args: argparse.Namespace) -> int:
    run_id = sanitize_run_id(args.run_id)
    root, _ = study_for_run(run_id)
    command = [
        sys.executable,
        str(root / "scripts" / "evaluate_run.py"),
        "--run-id",
        run_id,
        "--partition",
        args.partition,
    ]
    if args.all_snapshots:
        command.append("--all-snapshots")
    if args.max_stage is not None:
        command += ["--max-stage", str(args.max_stage)]
    return subprocess_checked(command, cwd=root, env=safe_environment(root))


def command_report(args: argparse.Namespace) -> int:
    run_id = sanitize_run_id(args.run_id)
    root, _ = study_for_run(run_id)
    return subprocess_checked(
        [sys.executable, str(root / "scripts" / "summarize_run.py"), "--run-id", run_id],
        cwd=root,
        env=safe_environment(root),
    )


def command_summarize(args: argparse.Namespace) -> int:
    study, _ = load_study(args.study)
    output = args.output or (REPO_ROOT / "runs" / "study-results" / study["id"])
    command = [
        sys.executable,
        str(REPO_ROOT / "scripts" / "summarize_study.py"),
        "--study",
        str(args.study.resolve()),
        "--runs-root",
        str(REPO_ROOT / "runs"),
        "--output",
        str(output.resolve()),
    ]
    return subprocess_checked(command, cwd=REPO_ROOT)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    def study_arg(subparser: argparse.ArgumentParser) -> None:
        subparser.add_argument("--study", type=Path, required=True)

    validate = subparsers.add_parser("validate", help="Validate a study manifest and its artifacts")
    study_arg(validate)
    validate.set_defaults(func=command_validate)

    listing = subparsers.add_parser("list", help="List resolved study conditions")
    study_arg(listing)
    listing.set_defaults(func=command_list)

    schedule = subparsers.add_parser("schedule", help="Generate a deterministic randomized-block run order")
    study_arg(schedule)
    schedule.add_argument("--replicates", type=int, default=3)
    schedule.add_argument("--profile", choices=["pilot", "main"], default="main")
    schedule.add_argument("--output", type=Path)
    schedule.set_defaults(func=command_schedule)

    materialize_parser = subparsers.add_parser("materialize", help="Build an inspectable condition-specific harness")
    study_arg(materialize_parser)
    materialize_parser.add_argument("--condition", required=True)
    materialize_parser.add_argument("--run-id", required=True)
    materialize_parser.add_argument("--replace", action="store_true")
    materialize_parser.set_defaults(func=command_materialize)

    run_parser = subparsers.add_parser("run", help="Materialize and execute one condition")
    study_arg(run_parser)
    run_parser.add_argument("--condition", required=True)
    run_parser.add_argument("--profile", choices=["pilot", "main"], required=True)
    run_parser.add_argument("--run-id", required=True)
    run_parser.add_argument("--replicate", type=int)
    run_parser.set_defaults(func=command_run)

    resume = subparsers.add_parser("resume", help="Resume a study run through its frozen materialization")
    resume.add_argument("--run-id", required=True)
    resume.set_defaults(func=command_resume)

    evaluate = subparsers.add_parser("evaluate", help="Evaluate one study run post hoc")
    evaluate.add_argument("--run-id", required=True)
    evaluate.add_argument("--partition", choices=["visible", "hidden"], default="hidden")
    evaluate.add_argument("--all-snapshots", action="store_true")
    evaluate.add_argument("--max-stage", type=int)
    evaluate.set_defaults(func=command_evaluate)

    report = subparsers.add_parser("report", help="Generate the existing per-run report")
    report.add_argument("--run-id", required=True)
    report.set_defaults(func=command_report)

    summarize = subparsers.add_parser("summarize", help="Aggregate all completed runs in a study")
    study_arg(summarize)
    summarize.add_argument("--output", type=Path)
    summarize.set_defaults(func=command_summarize)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (StudyError, ExperimentError) as error:
        print(f"error: {error}", file=sys.stderr)
        raise SystemExit(1)
