#!/usr/bin/env python3
"""Create deterministic visible/hidden partitions of the C compiler test corpus."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import shutil
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from common import ExperimentError, atomic_write_json

STAGE_PATTERN = re.compile(r"(?:chapter|stage)_(\d+)$")
EXCLUDED_COMPONENTS = {"extra_credit", "libraries", "helper_libs"}


@dataclass(frozen=True)
class TestCase:
    source: Path
    relative: Path
    stage: int
    validity: str
    family: str

    @property
    def test_id(self) -> str:
        return self.relative.as_posix()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True, help="Upstream repository or tests directory")
    parser.add_argument("--output", type=Path, required=True, help="Output directory containing visible/hidden")
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--visible-fraction", type=float, default=0.70)
    parser.add_argument("--max-stage", type=int, default=10)
    parser.add_argument("--source-revision", required=True)
    return parser.parse_args()


def load_properties(source_root: Path) -> tuple[set[str], dict[str, list[str]]]:
    property_file = source_root / "test_properties.json"
    if not property_file.exists():
        return set(), {}
    data = json.loads(property_file.read_text(encoding="utf-8"))
    excluded: set[str] = set()
    reasons: dict[str, list[str]] = defaultdict(list)

    def add(path: str, reason: str) -> None:
        normalized = Path(path).as_posix()
        excluded.add(normalized)
        reasons[normalized].append(reason)

    for path in data.get("extra_credit_tests", {}):
        add(path, "extra_credit")
    for path in data.get("requires_mathlib", []):
        add(path, "requires_mathlib")
    for category in ("assembly_libs", "libs"):
        for path, dependencies in data.get(category, {}).items():
            add(path, category)
            for dependency in dependencies:
                dep = Path(dependency).as_posix()
                if dep.endswith(".c"):
                    add(dep, f"dependency_of_{category}")
    return excluded, dict(reasons)


def stage_from_path(relative: Path) -> int | None:
    for component in relative.parts:
        match = STAGE_PATTERN.fullmatch(component)
        if match:
            return int(match.group(1))
    return None


def validity_from_path(relative: Path) -> str | None:
    for component in relative.parts:
        if component == "valid":
            return "valid"
        if component.startswith("invalid_"):
            return "invalid"
    return None


def family_key(relative: Path) -> str:
    """Keep obvious generated/numeric variants in the same partition."""
    stem = re.sub(r"(?:[_-]?\d+)+$", "_N", relative.stem)
    stem = re.sub(r"\d+", "N", stem)
    return (relative.parent / stem).as_posix()


def collect_tests(source: Path, max_stage: int) -> tuple[Path, list[TestCase], dict[str, int]]:
    source = source.resolve()
    tests_root = source / "tests" if (source / "tests").is_dir() else source
    source_root = tests_root.parent if tests_root.name == "tests" else source
    excluded_property_paths, _ = load_properties(source_root)

    tests: list[TestCase] = []
    exclusions: dict[str, int] = defaultdict(int)
    for path in sorted(tests_root.rglob("*.c")):
        relative = path.relative_to(tests_root)
        stage = stage_from_path(relative)
        validity = validity_from_path(relative)
        if stage is None or validity is None:
            exclusions["unclassified"] += 1
            continue
        if stage > max_stage:
            exclusions["above_max_stage"] += 1
            continue
        if any(component in EXCLUDED_COMPONENTS for component in relative.parts):
            exclusions["excluded_directory"] += 1
            continue
        if relative.as_posix() in excluded_property_paths:
            exclusions["test_properties"] += 1
            continue
        if relative.stem.endswith(("_client", "_lib")):
            exclusions["multi_file_name"] += 1
            continue
        tests.append(
            TestCase(
                source=path,
                relative=relative,
                stage=stage,
                validity=validity,
                family=family_key(relative),
            )
        )
    if not tests:
        raise ExperimentError(f"No eligible tests found under {tests_root}")
    return tests_root, tests, dict(exclusions)


def deterministic_order(seed: int, value: str) -> str:
    return hashlib.sha256(f"{seed}\0{value}".encode("utf-8")).hexdigest()


def split_cases(cases: Iterable[TestCase], seed: int, visible_fraction: float) -> dict[str, str]:
    if not 0.0 < visible_fraction < 1.0:
        raise ExperimentError("--visible-fraction must be strictly between 0 and 1")

    by_stratum: dict[tuple[int, str], dict[str, list[TestCase]]] = defaultdict(lambda: defaultdict(list))
    for case in cases:
        by_stratum[(case.stage, case.validity)][case.family].append(case)

    assignments: dict[str, str] = {}
    for stratum, groups in sorted(by_stratum.items()):
        group_names = sorted(groups, key=lambda value: deterministic_order(seed, f"{stratum}:{value}"))
        if len(group_names) == 1:
            # Always expose singleton strata; the agent needs at least one visible example
            # of every included stage/validity class. Real corpus strata contain many groups.
            visible_count = 1
        else:
            visible_count = round(len(group_names) * visible_fraction)
            visible_count = min(len(group_names) - 1, max(1, visible_count))

        visible_groups = set(group_names[:visible_count])
        for group_name, group_cases in groups.items():
            partition = "visible" if group_name in visible_groups else "hidden"
            for case in group_cases:
                assignments[case.test_id] = partition

    # Avoid pathological tiny-fixture output with one globally empty partition.
    values = set(assignments.values())
    if values != {"visible", "hidden"} and len(assignments) >= 2:
        ordered_ids = sorted(assignments, key=lambda value: deterministic_order(seed, value))
        assignments[ordered_ids[0]] = "visible"
        assignments[ordered_ids[-1]] = "hidden"
    return assignments


def write_partition(
    output_root: Path,
    partition: str,
    cases: list[TestCase],
    source_revision: str,
    seed: int,
    visible_fraction: float,
    source_root: Path,
    exclusions: dict[str, int],
) -> dict[str, object]:
    destination = output_root / partition
    if destination.exists():
        shutil.rmtree(destination)
    destination.mkdir(parents=True)

    manifest_tests: list[dict[str, object]] = []
    for case in sorted(cases, key=lambda item: item.test_id):
        target = destination / case.relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(case.source, target)
        manifest_tests.append(
            {
                "id": case.test_id,
                "relative_path": case.relative.as_posix(),
                "stage": case.stage,
                "validity": case.validity,
                "family": case.family,
            }
        )

    counts: dict[str, int] = defaultdict(int)
    for test in manifest_tests:
        counts[f"stage_{test['stage']}_{test['validity']}"] += 1

    manifest: dict[str, object] = {
        "schema_version": 1,
        "partition": partition,
        "source": {
            "revision": source_revision,
            "tests_root": "tests",
        },
        "split": {
            "seed": seed,
            "visible_fraction": visible_fraction,
            "policy": "family-grouped, stage-and-validity-stratified",
            "scope": "standalone core tests; excludes extra credit, multi-file libraries, assembly helpers, and math-library cases",
        },
        "counts": {"total": len(manifest_tests), **dict(sorted(counts.items()))},
        "excluded_counts": exclusions,
        "tests": manifest_tests,
    }
    atomic_write_json(destination / "manifest.json", manifest)
    return manifest


def main() -> int:
    args = parse_args()
    tests_root, tests, exclusions = collect_tests(args.source, args.max_stage)
    assignments = split_cases(tests, args.seed, args.visible_fraction)
    visible = [test for test in tests if assignments[test.test_id] == "visible"]
    hidden = [test for test in tests if assignments[test.test_id] == "hidden"]

    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    visible_manifest = write_partition(
        output,
        "visible",
        visible,
        args.source_revision,
        args.seed,
        args.visible_fraction,
        tests_root,
        exclusions,
    )
    hidden_manifest = write_partition(
        output,
        "hidden",
        hidden,
        args.source_revision,
        args.seed,
        args.visible_fraction,
        tests_root,
        exclusions,
    )
    summary = {
        "visible": visible_manifest["counts"],
        "hidden": hidden_manifest["counts"],
        "excluded": exclusions,
        "output": str(output),
    }
    atomic_write_json(output / "split-summary.json", summary)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ExperimentError as error:
        raise SystemExit(f"error: {error}")
