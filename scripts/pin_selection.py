#!/usr/bin/env python3
"""Record or check the pinned test selection of a task's partitions.

A selection record freezes, in the repository, exactly which upstream cases a
task's visible and hidden partitions hold: source revision, split policy,
per-partition test ids, and exclusion counts.  ``--write`` creates it from
generated partitions; ``--check`` (used by the fetch scripts and the study
validator) fails when regenerated partitions differ from the record, so a
selection cannot drift silently after it was planned in advance.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import ExperimentError, atomic_write_json  # noqa: E402

SCHEMA_VERSION = 1


def load_manifest(partitions: Path, partition: str) -> dict:
    path = partitions / partition / "manifest.json"
    if not path.is_file():
        raise ExperimentError(f"Missing partition manifest: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def selection_from_partitions(partitions: Path) -> dict:
    visible = load_manifest(partitions, "visible")
    hidden = load_manifest(partitions, "hidden")
    for key in ("source", "split"):
        if visible.get(key) != hidden.get(key):
            raise ExperimentError(f"visible and hidden manifests disagree on {key}")
    record = {
        "schema_version": SCHEMA_VERSION,
        "source": visible.get("source"),
        "split": visible.get("split"),
        "excluded_counts": visible.get("excluded_counts", {}),
        "partitions": {},
    }
    for name, manifest in (("visible", visible), ("hidden", hidden)):
        rows = manifest.get("tests", [])
        record["partitions"][name] = {
            "count": len(rows),
            "tests": sorted(
                (
                    {
                        "id": row["id"],
                        "stage": row["stage"],
                        "validity": row["validity"],
                        "family": row.get("family"),
                        "fixtures": [f["relative_path"] for f in row.get("fixtures", [])],
                        "link_flags": list(row.get("link_flags", [])),
                    }
                    for row in rows
                ),
                key=lambda item: item["id"],
            ),
        }
    return record


def differences(expected: dict, actual: dict) -> list[str]:
    problems: list[str] = []
    for key in ("source", "split", "excluded_counts"):
        if expected.get(key) != actual.get(key):
            problems.append(f"{key}: recorded {expected.get(key)!r}, generated {actual.get(key)!r}")
    for name in ("visible", "hidden"):
        want = expected["partitions"].get(name, {})
        have = actual["partitions"].get(name, {})
        want_ids = {row["id"]: row for row in want.get("tests", [])}
        have_ids = {row["id"]: row for row in have.get("tests", [])}
        missing = sorted(set(want_ids) - set(have_ids))
        extra = sorted(set(have_ids) - set(want_ids))
        if missing:
            problems.append(f"{name}: {len(missing)} recorded tests are missing, e.g. {missing[:3]}")
        if extra:
            problems.append(f"{name}: {len(extra)} generated tests are not recorded, e.g. {extra[:3]}")
        changed = [tid for tid in want_ids if tid in have_ids and want_ids[tid] != have_ids[tid]]
        if changed:
            problems.append(f"{name}: {len(changed)} tests changed stage/validity/family/fixtures, e.g. {changed[:3]}")
    return problems


def check(record_path: Path, partitions: Path) -> list[str]:
    if not record_path.is_file():
        return [f"selection record missing: {record_path}"]
    expected = json.loads(record_path.read_text(encoding="utf-8"))
    if expected.get("schema_version") != SCHEMA_VERSION:
        return [f"unsupported selection record schema in {record_path}"]
    return differences(expected, selection_from_partitions(partitions))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--record", type=Path, required=True)
    parser.add_argument("--partitions", type=Path, required=True)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if args.write:
        atomic_write_json(args.record, selection_from_partitions(args.partitions))
        print(f"Wrote selection record {args.record}")
        return 0
    problems = check(args.record, args.partitions)
    if problems:
        for problem in problems:
            print(f"selection mismatch: {problem}", file=sys.stderr)
        return 1
    record = json.loads(args.record.read_text(encoding="utf-8"))
    counts = {name: part["count"] for name, part in record["partitions"].items()}
    print(f"Selection record {args.record} matches generated partitions: {counts}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ExperimentError as error:
        print(f"error: {error}", file=sys.stderr)
        raise SystemExit(1)
