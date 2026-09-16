from __future__ import annotations

import argparse
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import summarize_study  # noqa: E402


DEFAULT_USAGE = {"input": 10, "output": 5, "cache_read": 2}


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8")


def study_payload() -> dict[str, object]:
    return {
        "schema_version": 1,
        "id": "summary-test",
        "description": "Summary inclusion test",
        "baseline_condition": "baseline",
        "completion_threshold": 0.95,
        "defaults": {
            "prompt": {"agents": "agents.md", "initial": "initial.txt", "continuation": "continue.txt"},
            "specification": {
                "path": "spec.md",
                "delivery": "task_file",
                "provenance": {"method": "unit"},
            },
            "tests": {
                "access": "tool",
                "feedback": "failures",
                "visible_subset_fraction": 1.0,
                "provenance": {"method": "unit"},
            },
            "candidate": {
                "adapter": "candidate.json",
                "language": "rust",
                "framework": "standard-library",
                "scaffold": None,
            },
            "reference": {"mode": "none", "oracle_limit": 0, "source": None},
            "environment": {"overrides": {}},
            "budget": {},
        },
        "conditions": [
            {
                "id": "baseline",
                "factor": "baseline",
                "description": "Unit baseline",
            }
        ],
    }


def resolved_condition(study: dict[str, object]) -> dict[str, object]:
    return summarize_study.deep_merge(study["defaults"], study["conditions"][0])


def evaluator_result(test: dict[str, object], passed: bool) -> dict[str, object]:
    return {
        "id": test["id"],
        "stage": test["stage"],
        "validity": test["validity"],
        "passed": passed,
        "failure_type": None if passed else "wrong_output",
        "detail": None if passed else "fixture failure",
        "compile_seconds": 0.1,
        "execute_seconds": 0.1,
        "compiler_returncode": 0,
    }


def make_run(
    runs_root: Path,
    run_id: str,
    study: dict[str, object],
    *,
    profile: object = "main",
    status: object = "completed",
    protocol_comparable: object = True,
    resumed: object = False,
    resume_count: object = 0,
    replicate: object = 1,
    usage: object = DEFAULT_USAGE,
    round_count: int = 2,
    fuzz: object = "default",
    final_unbuildable: bool = False,
    last_buildable_fuzz: object = "default",
) -> Path:
    # A complete run carries a fuzz-oracle ledger for its final snapshot; pass
    # fuzz=None to build a run without one (older cohorts) and a dict to tamper.
    if fuzz == "default":
        fuzz = {"rates": [1.0]}
    run_dir = runs_root / run_id
    materialization = summarize_study.REPO_ROOT / "runs" / ".study-materializations" / run_id
    condition = resolved_condition(study)

    prompt_contents = {
        "AGENTS.md": "Fixture agents\n",
        "TASK.md": "Fixture specification\n",
        "INITIAL.txt": "Build the fixture\n",
        "CONTINUE.txt": "Continue the fixture\n",
    }
    write_json(run_dir / "study-control" / "candidate.json", {"schema_version": 1, "source_extensions": [".rs"]})

    visible_tests = [
        {"id": "visible-valid", "stage": 1, "validity": "valid"},
        {"id": "visible-invalid", "stage": 1, "validity": "invalid"},
    ]
    hidden_tests = [
        {"id": "hidden-valid", "stage": 1, "validity": "valid"},
        {"id": "hidden-invalid", "stage": 1, "validity": "invalid"},
    ]
    visible_manifest = {"schema_version": 1, "partition": "visible", "tests": visible_tests}
    hidden_manifest = {"schema_version": 1, "partition": "hidden", "tests": hidden_tests}
    manifest_specs = [
        ("visible", visible_manifest),
        ("hidden", hidden_manifest),
    ]
    for label, manifest in manifest_specs:
        write_json(materialization / "data" / "partitions" / label / "manifest.json", manifest)
        write_json(run_dir / "study-control" / f"{label}-manifest.json", manifest)

    configuration = {
        "AGENT_CPUS": "8",
        "EXPERIMENT_IMAGE": "picc-study@sha256:fixture",
        "MAIN_HOURS": "1.0",
        "MAIN_MAX_STAGE": "1",
        "MAIN_ROUNDS": str(max(2, round_count)),
        "MAIN_ROUND_TIMEOUT_MINUTES": "30",
        "STARTER_VERSION": "summary-fixture-v1",
        "MODEL_ID": "example/hosted-model",
        "MODEL_PROVIDER": "zai",
        "MODEL_THINKING": "max",
    }
    rendered = {
        "specification_bytes": len("Fixture specification\n".encode()),
        "specification_words": 2,
        "prompt_bytes": {name: len(content.encode()) for name, content in prompt_contents.items()},
        "visible_test_count": 2,
        "agent_visible_test_count": 2,
        "hidden_test_count": 2,
    }
    materialization_record = {
        "schema_version": 1,
        "created_at": "2026-01-01T00:00:00Z",
        "study_id": study["id"],
        "study_path": "study.json",
        "condition": condition,
        "condition_id": condition["id"],
        "run_id": run_id,
        "effective_config": configuration,
        "completion_threshold": study["completion_threshold"],
        "source_harness": {
            "repo_root": str(summarize_study.REPO_ROOT),
            "version": "summary-fixture-v1",
        },
        "rendered": rendered,
    }
    write_json(materialization / "study-materialization.json", materialization_record)
    write_json(run_dir / "study-control" / "materialization.json", materialization_record)
    sidecar = {
        **materialization_record,
        "materialization_root": str(materialization.relative_to(summarize_study.REPO_ROOT)),
        "frozen_at": "2026-01-01T01:00:00Z",
    }
    write_json(run_dir / "study-metadata.json", sidecar)

    metadata = {
        "schema_version": 2,
        "starter_version": "summary-fixture-v1",
        "run_id": run_id,
        "profile": profile,
        "replicate": replicate,
        "status": status,
        "protocol_comparable": protocol_comparable,
        "resumed": resumed,
        "resume_count": resume_count,
        "termination_reason": "max_rounds",
        "elapsed_seconds": float(round_count * 50),
        "configuration": dict(configuration),
        "budget": {
            "wall_hours": 1.0,
            "max_rounds": max(2, round_count),
            "round_timeout_minutes": 30,
            "max_stage": 1,
        },
        "model": {
            "provider": "zai",
            "id": "example/hosted-model",
            "thinking": "max",
            "serving_revision": "provider-managed",
        },
        "docker_image": {"name": "picc-study@sha256:fixture", "id": "sha256:fixture"},
    }
    write_json(run_dir / "metadata.json", metadata)

    snapshots: list[dict[str, object]] = []
    visible_points: list[dict[str, object]] = []
    hidden_points: list[dict[str, object]] = []
    hidden_rows: list[dict[str, object]] = []
    for round_number in range(round_count):
        commit = chr(ord("a") + round_number) * 40
        tree = str(round_number + 1) * 40
        elapsed = float((round_number + 1) * 50)
        passed = 1 if round_number == 0 else 2
        score = passed / 2
        visible_summary = {
            "score": score,
            "micro_score": score,
            "passed": passed,
            "total": 2,
            "build_ok": True,
        }
        snapshot = {
            "round": round_number,
            "elapsed_seconds": elapsed,
            "git_commit": commit,
            "git_tree": tree,
            "changed_files": 1,
            "insertions": 3,
            "deletions": 0,
            "visible": visible_summary,
        }
        point = {
            "round": round_number,
            "elapsed_seconds": elapsed,
            "git_commit": commit,
            **visible_summary,
        }
        unbuildable = final_unbuildable and round_number == round_count - 1
        if unbuildable:
            passed, score = 0, 0.0
        hidden_results = [
            evaluator_result(hidden_tests[0], not unbuildable),
            evaluator_result(hidden_tests[1], round_number > 0 and not unbuildable),
        ]
        hidden_summary = {
            "score": score,
            "micro_score": score,
            "passed": passed,
            "failed": 2 - passed,
            "total": 2,
            "build_ok": not unbuildable,
            "audit_ok": True,
        }
        hidden_point = {**point, **{key: hidden_summary[key] for key in point if key in hidden_summary}}
        hidden_point.update(
            {
                "round": round_number,
                "elapsed_seconds": elapsed,
                "git_commit": commit,
                "score": score,
                "micro_score": score,
                "passed": passed,
                "total": 2,
                "build_ok": not unbuildable,
            }
        )
        output = f"artifacts/evaluations/hidden-round-{round_number:03d}.json"
        hidden_row = {
            "partition": "hidden",
            "docker_image": dict(metadata["docker_image"]),
            "round": round_number,
            "git_commit": commit,
            "git_tree": tree,
            "elapsed_seconds": elapsed,
            "summary": hidden_summary,
            "output": output,
        }
        full_evaluation = {
            "schema_version": 1,
            "partition": "hidden",
            "docker_image": dict(metadata["docker_image"]),
            "snapshot": {"git_commit": commit, "git_tree": tree},
            "selection": {"max_stage": 1, "latest_only": False, "test_id": None, "count": 2},
            "summary": hidden_summary,
            "tests": hidden_results,
        }
        write_json(run_dir / output, full_evaluation)
        snapshots.append(snapshot)
        visible_points.append(point)
        hidden_points.append(hidden_point)
        hidden_rows.append(hidden_row)

    write_jsonl(run_dir / "artifacts" / "snapshots.jsonl", snapshots)
    write_jsonl(run_dir / "artifacts" / "hidden-scores.jsonl", hidden_rows)
    fuzz_row: dict[str, object] | None = None
    ledger_rows: list[dict[str, object]] = []
    if isinstance(fuzz, dict):
        # `fuzz` describes the fuzz-oracle ledger for the final snapshot; keys
        # override the consistent default so tests can inject tampering.
        final = snapshots[-1]
        rates = fuzz.get("rates", [1.0])
        fuzz_summary = {
            "fuzz_macro": sum(rates) / len(rates),
            "stage_pass_rates": rates,
            "max_stage": len(rates),
            "programs_per_stage": 5,
            "evaluated_total": 5 * len(rates),
            "passed_total": int(round(sum(rates) * 5)),
            "mismatches_total": 5 * len(rates) - int(round(sum(rates) * 5)),
            "skipped_total": 0,
            "mismatch_kinds": {},
            "stages_complete": len(rates),
            "deadline_hit": False,
            "build_ok": True,
            "audit_ok": True,
            "audit_blocking": False,
        }
        fuzz_summary.update(fuzz.get("summary_overrides", {}))
        fuzz_full = {
            "schema_version": 1,
            "snapshot": {"git_commit": fuzz.get("commit", final["git_commit"]), "git_tree": final["git_tree"]},
            "docker_image": dict(metadata["docker_image"]),
            "policy": {"max_stage": fuzz.get("policy_max_stage", len(rates)), "programs_per_stage": 5},
            "summary": fuzz_summary,
            "stages": {},
        }
        write_json(run_dir / "artifacts" / "evaluations" / "fuzz-final.json", fuzz_full)
        fuzz_row = {
            "partition": "fuzz",
            "round": final["round"],
            "git_commit": final["git_commit"],
            "git_tree": final["git_tree"],
            "docker_image": dict(metadata["docker_image"]),
            "elapsed_seconds": final["elapsed_seconds"],
            "policy": {"programs_per_stage": 5},
            "summary": fuzz_summary,
            "output": "artifacts/evaluations/fuzz-final.json",
        }
        ledger_rows = [fuzz_row]
        if final_unbuildable and isinstance(last_buildable_fuzz, dict) and round_count > 1:
            # v8: a second row for the last snapshot that built (role last_buildable).
            previous = snapshots[-2]
            lb_rates = last_buildable_fuzz.get("rates", [1.0])
            lb_summary = {**fuzz_summary, "fuzz_macro": sum(lb_rates) / len(lb_rates), "stage_pass_rates": lb_rates}
            lb_full = {**fuzz_full, "snapshot": {"git_commit": previous["git_commit"], "git_tree": previous["git_tree"]}, "summary": lb_summary}
            write_json(run_dir / "artifacts" / "evaluations" / "fuzz-last-buildable.json", lb_full)
            lb_row = {
                **fuzz_row,
                "role": "last_buildable",
                "round": previous["round"],
                "git_commit": previous["git_commit"],
                "git_tree": previous["git_tree"],
                "elapsed_seconds": previous["elapsed_seconds"],
                "summary": lb_summary,
                "output": "artifacts/evaluations/fuzz-last-buildable.json",
            }
            fuzz_row = {**fuzz_row, "role": "final"}
            ledger_rows = [fuzz_row, lb_row]
        write_jsonl(run_dir / "artifacts" / "fuzz-scores.jsonl", ledger_rows)
    event_rows: list[dict[str, object]] = []
    if isinstance(usage, dict) and usage:
        event_rows.append(
            {
                "type": "message_end",
                "message": {"role": "assistant", "usage": dict(usage)},
            }
        )
    write_jsonl(run_dir / "artifacts" / "events" / "round-000.jsonl", event_rows)
    write_jsonl(run_dir / "artifacts" / "guard.jsonl", [])
    canonical_visible_auc = summarize_study.trajectory_auc(visible_points) if round_count > 1 else None
    canonical_hidden_auc = summarize_study.trajectory_auc(hidden_points) if round_count > 1 else None
    report = {
        "schema_version": 1,
        "metadata": metadata,
        "resume": {
            "resume_count": resume_count,
            "resumed": resumed,
            "protocol_comparable": protocol_comparable,
            "execution_attempts": [],
        },
        "visible_trajectory": visible_points,
        "hidden_trajectory": hidden_points,
        "snapshots": snapshots,
        "visible_score_auc": canonical_visible_auc,
        "hidden_score_auc": canonical_hidden_auc,
        "pi_events": {"usage": dict(usage) if isinstance(usage, dict) else usage},
        "guard": {"blocked_calls": 0, "reasons": {}, "tools": {}},
        "fuzz_final": None if not isinstance(fuzz, dict) else (fuzz.get("report_row", fuzz_row)),
        "fuzz_last_buildable": (ledger_rows[1] if isinstance(fuzz, dict) and len(ledger_rows) > 1 else None) if isinstance(fuzz, dict) else None,
    }
    write_json(run_dir / "report.json", report)
    write_text(run_dir / "workspace" / "main.rs", "fn main() {}\n")
    (run_dir / "artifacts" / "events").mkdir(parents=True, exist_ok=True)
    return run_dir


class PrimarySummaryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="picc-summary-test-")
        self.root = Path(self.temporary.name)
        self.repo_patch = mock.patch.object(summarize_study, "REPO_ROOT", self.root)
        self.repo_patch.start()
        self.runs = self.root / "runs"
        self.runs.mkdir()
        self.study = study_payload()
        self.study_path = self.root / "study.json"
        write_json(self.study_path, self.study)
        self.conditions = summarize_study.current_conditions(self.study)

    def tearDown(self) -> None:
        self.repo_patch.stop()
        self.temporary.cleanup()

    def collect(self, run_dir: Path):
        return summarize_study.collect_run(
            run_dir,
            str(self.study["id"]),
            self.conditions,
        )

    def test_eligible_main_run_exposes_profile_and_model(self) -> None:
        run_dir = make_run(self.runs, "main-r1", self.study)
        row, warning = self.collect(run_dir)
        self.assertIsNone(warning)
        self.assertIsNotNone(row)
        assert row is not None
        self.assertEqual(row["profile"], "main")
        self.assertEqual(row["replicate"], 1)
        self.assertEqual(row["model_provider"], "zai")
        self.assertEqual(row["hidden_evaluation_rounds"], 2)
        groups = summarize_study.grouped([row])
        self.assertEqual(groups[0]["profile"], "main")
        self.assertIn("| `baseline` | `main` |", summarize_study.markdown(self.study, [row], groups, []))

    def test_ineligible_runs_are_excluded_with_reasons(self) -> None:
        cases = [
            ({"profile": "pilot"}, "profile"),
            ({"status": "running"}, "status"),
            ({"protocol_comparable": False}, "protocol_comparable"),
            ({"resumed": True}, "resume metadata"),
            ({"replicate": None}, "positive integer"),
            ({"replicate": True}, "positive integer"),
            ({"replicate": 0}, "positive integer"),
            ({"replicate": -1}, "positive integer"),
        ]
        for index, (overrides, expected) in enumerate(cases):
            with self.subTest(overrides=overrides):
                run_dir = make_run(
                    self.runs,
                    f"excluded-{index}",
                    self.study,
                    **overrides,
                )
                row, warning = self.collect(run_dir)
                self.assertIsNone(row)
                self.assertIn(expected, warning or "")

    def test_condition_drift_is_excluded(self) -> None:
        run_dir = make_run(self.runs, "stale-condition", self.study)
        sidecar_path = run_dir / "study-metadata.json"
        sidecar = summarize_study.load_object(sidecar_path)
        sidecar["condition"]["description"] = "old condition"
        write_json(sidecar_path, sidecar)
        row, warning = self.collect(run_dir)
        self.assertIsNone(row)
        self.assertIn("current resolved condition", warning or "")

    def test_duplicate_condition_replicate_is_a_hard_error(self) -> None:
        rows = [
            {"condition_id": "baseline", "replicate": 1, "run_id": "first"},
            {"condition_id": "baseline", "replicate": 1, "run_id": "second"},
        ]
        with self.assertRaisesRegex(summarize_study.SummaryError, "first, second"):
            summarize_study.reject_duplicate_included_runs(rows)

    def test_partial_hidden_trajectory_and_tampered_scores_are_excluded(self) -> None:
        partial = make_run(self.runs, "partial-hidden", self.study)
        report_path = partial / "report.json"
        report = summarize_study.load_object(report_path)
        report["hidden_trajectory"] = report["hidden_trajectory"][-1:]
        write_json(report_path, report)
        row, warning = self.collect(partial)
        self.assertIsNone(row)
        self.assertIn("does not cover every frozen snapshot", warning or "")

        tampered = make_run(self.runs, "tampered-score", self.study)
        full_path = tampered / "artifacts" / "evaluations" / "hidden-round-000.json"
        full = summarize_study.load_object(full_path)
        full["summary"]["score"] = 1.0
        write_json(full_path, full)
        hidden_rows = summarize_study.read_jsonl(tampered / "artifacts" / "hidden-scores.jsonl")
        hidden_rows[0]["summary"]["score"] = 1.0
        write_jsonl(tampered / "artifacts" / "hidden-scores.jsonl", hidden_rows)
        report_path = tampered / "report.json"
        report = summarize_study.load_object(report_path)
        report["hidden_trajectory"][0]["score"] = 1.0
        report["hidden_score_auc"] = summarize_study.trajectory_auc(report["hidden_trajectory"])
        write_json(report_path, report)
        row, warning = self.collect(tampered)
        self.assertIsNone(row)
        self.assertIn("inconsistent score", warning or "")

    def test_missing_usage_stays_missing(self) -> None:
        run_dir = make_run(self.runs, "missing-usage", self.study, usage={})
        row, warning = self.collect(run_dir)
        self.assertIsNone(warning)
        assert row is not None
        for field in ("input_tokens", "output_tokens", "cache_read_tokens", "cache_write_tokens"):
            self.assertIsNone(row[field])
        self.assertIsNone(row["hidden_score_per_million_generation_tokens"])

    def test_runtime_and_report_provenance_mismatches_are_excluded(self) -> None:
        config = make_run(self.runs, "changed-config", self.study)
        metadata_path = config / "metadata.json"
        metadata = summarize_study.load_object(metadata_path)
        metadata["configuration"]["AGENT_CPUS"] = "4"
        write_json(metadata_path, metadata)
        row, warning = self.collect(config)
        self.assertIsNone(row)
        self.assertIn("frozen effective configuration", warning or "")

        image = make_run(self.runs, "changed-image", self.study)
        full_path = image / "artifacts" / "evaluations" / "hidden-round-000.json"
        full = summarize_study.load_object(full_path)
        full["docker_image"]["id"] = "sha256:different"
        write_json(full_path, full)
        row, warning = self.collect(image)
        self.assertIsNone(row)
        self.assertIn("different Docker image", warning or "")

        usage = make_run(self.runs, "changed-usage", self.study)
        report_path = usage / "report.json"
        report = summarize_study.load_object(report_path)
        report["pi_events"]["usage"]["input"] = 999
        write_json(report_path, report)
        row, warning = self.collect(usage)
        self.assertIsNone(row)
        self.assertIn("raw event ledgers", warning or "")

        guard = make_run(self.runs, "changed-guard", self.study)
        report_path = guard / "report.json"
        report = summarize_study.load_object(report_path)
        report["guard"]["blocked_calls"] = 1
        write_json(report_path, report)
        row, warning = self.collect(guard)
        self.assertIsNone(row)
        self.assertIn("guard metrics", warning or "")

    def test_last_buildable_snapshot_scores_when_the_final_does_not_build(self) -> None:
        # The v7 case: the final snapshot is a rewrite cut by the round cap.
        run_dir = make_run(self.runs, "cut-r1", self.study, round_count=3,
                           fuzz={"rates": [0.0]}, final_unbuildable=True, last_buildable_fuzz={"rates": [1.0]})
        row, warning = self.collect(run_dir)
        self.assertIsNone(warning)
        assert row is not None
        self.assertEqual(row["hidden_score"], 0.0)
        self.assertEqual(row["hidden_score_last_buildable"], 1.0)
        self.assertEqual(row["last_buildable_round"], 1)
        self.assertEqual(row["fuzz_macro"], 0.0)
        self.assertEqual(row["fuzz_macro_last_buildable"], 1.0)
        self.assertFalse(row["final_build_ok"])

    def test_final_snapshot_that_builds_is_its_own_last_buildable(self) -> None:
        run_dir = make_run(self.runs, "built-r1", self.study)
        row, warning = self.collect(run_dir)
        self.assertIsNone(warning)
        assert row is not None
        self.assertEqual(row["hidden_score_last_buildable"], row["hidden_score"])
        self.assertEqual(row["fuzz_macro_last_buildable"], row["fuzz_macro"])
        self.assertEqual(row["last_buildable_round"], 1)

    def test_pre_v8_ledger_without_the_second_row_warns_instead_of_excluding(self) -> None:
        run_dir = make_run(self.runs, "legacy-cut-r1", self.study, round_count=3,
                           fuzz={"rates": [0.0]}, final_unbuildable=True, last_buildable_fuzz=None)
        row, warning = self.collect(run_dir)
        assert row is not None
        self.assertIn("last buildable", warning or "")
        self.assertEqual(row["hidden_score_last_buildable"], 1.0)
        self.assertIsNone(row["fuzz_macro_last_buildable"])

    def test_last_buildable_row_for_a_building_final_is_a_provenance_failure(self) -> None:
        run_dir = make_run(self.runs, "stray-r1", self.study, round_count=3,
                           fuzz={"rates": [1.0]}, final_unbuildable=True, last_buildable_fuzz={"rates": [1.0]})
        # Flip the final hidden row back to buildable without touching the ledger: the second row is now stray.
        ledger_path = run_dir / "artifacts" / "hidden-scores.jsonl"
        rows = [json.loads(line) for line in ledger_path.read_text(encoding="utf-8").splitlines()]
        rows[-1]["summary"]["build_ok"] = True
        write_jsonl(ledger_path, rows)
        full_path = run_dir / rows[-1]["output"]
        full = summarize_study.load_object(full_path)
        full["summary"]["build_ok"] = True
        write_json(full_path, full)
        report_path = run_dir / "report.json"
        report = summarize_study.load_object(report_path)
        report["hidden_trajectory"][-1]["build_ok"] = True
        write_json(report_path, report)
        row, warning = self.collect(run_dir)
        self.assertIsNone(row)
        self.assertIn("last-buildable row although the final snapshot built", warning or "")

    def test_bash_timeouts_are_counted_apart_from_guard_blocks(self) -> None:
        run_dir = make_run(self.runs, "timeouts-r1", self.study)
        write_jsonl(
            run_dir / "artifacts" / "guard.jsonl",
            [
                {"event": "blocked_tool_call", "toolName": "bash", "reason": "network/download command is prohibited"},
                {"event": "bash_timeout_fired", "toolName": "bash", "timeout": 120},
                {"event": "bash_timeout_fired", "toolName": "bash", "timeout": 120},
            ],
        )
        report_path = run_dir / "report.json"
        report = summarize_study.load_object(report_path)
        report["guard"] = summarize_study.guard_event_metrics(run_dir / "artifacts" / "guard.jsonl")
        write_json(report_path, report)
        row, warning = self.collect(run_dir)
        self.assertIsNone(warning)
        assert row is not None
        self.assertEqual(row["guard_blocked_calls"], 1)
        self.assertEqual(row["guard_bash_timeouts"], 2)

    def test_one_snapshot_early_stop_is_included_with_origin_auc(self) -> None:
        run_dir = make_run(
            self.runs,
            "early-stop",
            self.study,
            round_count=1,
        )
        row, warning = self.collect(run_dir)
        self.assertIsNone(warning)
        assert row is not None
        self.assertEqual(row["hidden_evaluation_rounds"], 1)
        self.assertAlmostEqual(row["hidden_auc"], 0.25)

    def test_model_cohort_drift_is_a_hard_error(self) -> None:
        first_dir = make_run(self.runs, "cohort-r1", self.study, replicate=1)
        second_dir = make_run(self.runs, "cohort-r2", self.study, replicate=2)
        first, _ = self.collect(first_dir)
        second, _ = self.collect(second_dir)
        assert first is not None and second is not None
        summarize_study.reject_cohort_drift([first, second])

        second["model_id"] = "different-model"
        with self.assertRaisesRegex(summarize_study.SummaryError, "model_id"):
            summarize_study.reject_cohort_drift([first, second])

    def test_paired_deltas_use_the_declared_baseline_condition(self) -> None:
        rows = [
            {"condition_id": "js-untyped", "replicate": 1, "hidden_score": 0.8, "elapsed_seconds": 3600, "finished": False},
            {"condition_id": "ts-strict", "replicate": 1, "hidden_score": 0.9, "elapsed_seconds": 5400, "finished": False},
        ]
        self.assertEqual(summarize_study.baseline_deltas(rows), [])
        deltas = summarize_study.baseline_deltas(rows, baseline="js-untyped")
        self.assertEqual(len(deltas), 1)
        self.assertEqual(deltas[0]["condition_id"], "ts-strict")
        self.assertAlmostEqual(deltas[0]["delta_hidden_score"], 0.1)
        self.assertAlmostEqual(deltas[0]["delta_elapsed_hours"], 0.5)

    def test_fuzz_oracle_columns_are_verified_against_the_final_snapshot(self) -> None:
        # Without a fuzz ledger the run is included, with None columns and a coverage warning.
        run_dir = make_run(self.runs, "nofuzz-r1", self.study, fuzz=None)
        row, warning = self.collect(run_dir)
        self.assertIsNotNone(row)
        self.assertIsNone(row["fuzz_macro"])
        self.assertIn("no fuzz-oracle score", warning)

        run_dir = make_run(self.runs, "fuzz-r2", self.study, replicate=2, fuzz={"rates": [1.0]})
        row, warning = self.collect(run_dir)
        self.assertIsNone(warning)
        self.assertEqual(row["fuzz_macro"], 1.0)
        self.assertEqual(json.loads(row["fuzz_stage_pass_rates"]), [1.0])
        self.assertEqual(row["fuzz_programs_per_stage"], 5)
        self.assertFalse(row["fuzz_deadline_hit"])

        # A ledger for a different commit, a stale report, or an inconsistent macro excludes the run.
        for label, tampering in (
            ("commit", {"rates": [1.0], "commit": "f" * 40}),
            ("stale report", {"rates": [1.0], "report_row": {"partition": "fuzz", "summary": {}}}),
            ("macro", {"rates": [1.0], "summary_overrides": {"fuzz_macro": 0.5}}),
            ("stage budget", {"rates": [1.0], "policy_max_stage": 3}),
        ):
            with self.subTest(label=label):
                run_dir = make_run(self.runs, f"tampered-{label.replace(' ', '-')}", self.study, replicate=3, fuzz=tampering)
                row, warning = self.collect(run_dir)
                self.assertIsNone(row)
                self.assertIn("fuzz", str(warning))

    def test_fuzz_macro_is_aggregated_and_paired(self) -> None:
        study = dict(self.study)
        study["conditions"] = [
            {"id": "baseline", "factor": "baseline", "description": "b"},
            {"id": "variant", "factor": "tests", "description": "v", "tests": {"access": "none", "feedback": "none"}},
        ]
        rows = [
            {"condition_id": "baseline", "replicate": 1, "profile": "main", "factor": "baseline", "hidden_score": 0.8, "hidden_auc": 0.5, "fuzz_macro": 1.0, "elapsed_seconds": 10, "finished": False, "source_loc": 1, "input_tokens": 1, "output_tokens": 1, "visible_test_calls": 0, "oracle_calls": 0},
            {"condition_id": "variant", "replicate": 1, "profile": "main", "factor": "tests", "hidden_score": 0.7, "hidden_auc": 0.4, "fuzz_macro": 0.25, "elapsed_seconds": 10, "finished": False, "source_loc": 1, "input_tokens": 1, "output_tokens": 1, "visible_test_calls": 0, "oracle_calls": 0},
        ]
        deltas = summarize_study.baseline_deltas(rows)
        self.assertAlmostEqual(deltas[0]["delta_fuzz_macro"], -0.75)
        self.assertAlmostEqual(deltas[0]["delta_hidden_score"], -0.1)

    def test_planned_cells_and_unpaired_baselines_are_warned(self) -> None:
        study = dict(self.study)
        study["conditions"] = [
            {"id": "baseline"},
            {"id": "variant"},
        ]
        warnings = summarize_study.planned_cell_warnings(
            study,
            [
                {"condition_id": "baseline", "replicate": 1},
                {"condition_id": "variant", "replicate": 2},
            ],
        )
        self.assertIn("condition='variant', replicate=1", warnings[0])
        self.assertTrue(any("condition='baseline', replicate=2" in warning for warning in warnings))
        self.assertTrue(any("unpaired primary variant" in warning for warning in warnings))

    def test_cli_output_contains_only_eligible_primary_rows_and_warnings(self) -> None:
        make_run(self.runs, "main-r1", self.study)
        make_run(self.runs, "pilot-r1", self.study, profile="pilot")
        output = self.root / "output"
        args = argparse.Namespace(study=self.study_path, runs_root=self.runs, output=output)
        with mock.patch.object(summarize_study, "parse_args", return_value=args):
            self.assertEqual(summarize_study.main(), 0)
        summary = summarize_study.load_object(output / "summary.json")
        self.assertEqual(summary["selection"]["profile"], "main")
        self.assertEqual(summary["selection"]["hidden_trajectory"], "every frozen snapshot")
        self.assertEqual([row["run_id"] for row in summary["runs"]], ["main-r1"])
        self.assertEqual(summary["runs"][0]["profile"], "main")
        self.assertEqual(len(summary["warnings"]), 1)
        self.assertIn("pilot-r1", summary["warnings"][0])
        markdown = (output / "summary.md").read_text(encoding="utf-8")
        self.assertIn("Included primary runs: 1", markdown)
        self.assertIn("Exclusions and coverage warnings", markdown)


if __name__ == "__main__":
    unittest.main()
