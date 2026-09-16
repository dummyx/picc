#!/usr/bin/env python3
"""Build the SQL task partitions from the pinned sqllogictest checkout.

The selection (``studies/sql/selection.json``) names whole scripts grouped
into stages; each script is one test case and is copied complete, setup
statements included.  Scripts are split into visible and hidden partitions
with the same family-grouped, stage-stratified policy as the compiler corpus
(``split_tests.split_cases``), each script being its own family.  Every
script is parsed with the evaluator's sqllogictest reader; with
``--verify-sqlite`` the host's SQLite re-runs it and the number of records it
does not reproduce is recorded in the manifest (the in-image evaluator
repeats this under the pinned SQLite and excludes such records from scoring).
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "studies" / "runtime" / "sql"))
import sqllogictest as slt  # noqa: E402
from common import ExperimentError, atomic_write_json  # noqa: E402
from split_tests import TestCase, split_cases  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True, help="pinned sqllogictest checkout")
    parser.add_argument("--selection", type=Path, required=True, help="studies/sql/selection.json")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--visible-fraction", type=float, default=0.70)
    parser.add_argument("--source-revision", required=True)
    parser.add_argument("--verify-sqlite", action="store_true")
    return parser.parse_args()


def load_selection(path: Path) -> dict:
    selection = json.loads(path.read_text(encoding="utf-8"))
    if selection.get("schema_version") != 1 or not isinstance(selection.get("stages"), list):
        raise ExperimentError(f"Unsupported selection file: {path}")
    seen: set[str] = set()
    for stage in selection["stages"]:
        if not isinstance(stage.get("stage"), int) or stage["stage"] < 1:
            raise ExperimentError("every selection stage needs a positive integer stage number")
        for script in stage.get("scripts", []):
            if script in seen:
                raise ExperimentError(f"script selected twice: {script}")
            seen.add(script)
    return selection


def main() -> int:
    args = parse_args()
    selection = load_selection(args.selection)
    source = args.source.resolve()
    cases: list[TestCase] = []
    info: dict[str, dict] = {}
    for stage in selection["stages"]:
        for script in stage["scripts"]:
            path = source / script
            if not path.is_file():
                raise ExperimentError(f"selected script missing: {path}")
            relative = Path(script)
            records = slt.parse_script(path.read_text(encoding="utf-8", errors="replace"))
            invalid = [row for row in records if row.kind == "invalid"]
            if invalid:
                raise ExperimentError(f"{script}: unparseable record at line {invalid[0].line}: {invalid[0].detail}")
            executed = slt.statements_of(records)
            row_info = {
                "records": len(executed),
                "statements": sum(1 for row in executed if row.kind == "statement"),
                "queries": sum(1 for row in executed if row.kind == "query"),
                "family_label": stage.get("family"),
            }
            if args.verify_sqlite:
                verification = slt.verify_with_sqlite(records)
                row_info["host_sqlite_version"] = verification["sqlite_version"]
                row_info["host_reference_disagreements"] = len(verification["disagreements"])
            info[relative.as_posix()] = row_info
            cases.append(
                TestCase(
                    source=path,
                    relative=relative,
                    stage=int(stage["stage"]),
                    validity="valid",
                    family=relative.with_suffix("").as_posix(),
                )
            )
    if not cases:
        raise ExperimentError("selection names no scripts")
    assignments = split_cases(cases, args.seed, args.visible_fraction)

    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    summary: dict[str, object] = {}
    for partition in ("visible", "hidden"):
        destination = output / partition
        if destination.exists():
            import shutil

            shutil.rmtree(destination)
        destination.mkdir(parents=True)
        rows = []
        counts: dict[str, int] = defaultdict(int)
        for case in sorted(cases, key=lambda item: item.test_id):
            if assignments[case.test_id] != partition:
                continue
            target = destination / case.relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(case.source.read_bytes())
            rows.append(
                {
                    "id": case.test_id,
                    "relative_path": case.relative.as_posix(),
                    "stage": case.stage,
                    "validity": case.validity,
                    "family": case.family,
                    "script": info[case.test_id],
                }
            )
            counts[f"stage_{case.stage}_{case.validity}"] += 1
        manifest = {
            "schema_version": 1,
            "partition": partition,
            "task": "sql-engine",
            "source": {
                "repository": selection.get("source", {}).get("repository"),
                "revision": args.source_revision,
                "tests_root": "test",
            },
            "split": {
                "seed": args.seed,
                "visible_fraction": args.visible_fraction,
                "policy": "family-grouped, stage-and-validity-stratified",
                "scope": selection.get("scope", "selected sqllogictest scripts, complete with setup statements"),
            },
            "stages": {str(stage["stage"]): stage.get("description", "") for stage in selection["stages"]},
            "counts": {"total": len(rows), **dict(sorted(counts.items()))},
            "excluded_counts": {},
            "tests": rows,
        }
        atomic_write_json(destination / "manifest.json", manifest)
        summary[partition] = manifest["counts"]
    atomic_write_json(output / "split-summary.json", {**summary, "output": str(output)})
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ExperimentError as error:
        raise SystemExit(f"error: {error}")
