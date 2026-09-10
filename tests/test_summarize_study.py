from __future__ import annotations

import argparse
import hashlib
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


def text_sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


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
    study_sha256: str,
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
    extension_contents = {"experiment-tools.ts": "export const fixture = true;\n"}
    for name, content in prompt_contents.items():
        write_text(materialization / "prompts" / name, content)
        write_text(run_dir / "study-control" / "prompts" / name, content)
        write_text(run_dir / "control" / name, content)
    for name, content in extension_contents.items():
        write_text(materialization / "pi" / "extensions" / name, content)
        write_text(run_dir / "control" / "pi" / "extensions" / name, content)
    settings = {"schema_version": 1, "fixture": True}
    write_json(materialization / "pi" / "settings.json", settings)
    write_json(run_dir / "control" / "pi" / "settings.json", settings)

    candidate = {"schema_version": 1, "source_extensions": [".rs"]}
    candidate_paths = [
        materialization / "evaluator" / "candidate.json",
        run_dir / "study-control" / "candidate.json",
    ]
    for path in candidate_paths:
        write_json(path, candidate)
    candidate_sha256 = summarize_study.sha256_file(candidate_paths[0])

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

    write_text(materialization / "MANIFEST.sha256", "fixture release manifest\n")
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
    write_text(materialization / "VERSION", "summary-fixture-v1\n")
    write_text(
        materialization / "config" / "defaults.env",
        "".join(f"{key}={value}\n" for key, value in sorted(configuration.items())),
    )
    write_text(materialization / "docker" / "Dockerfile", "FROM scratch\n")
    write_text(materialization / "scripts" / "evaluate_run.py", "# frozen evaluate runner\n")
    write_text(materialization / "scripts" / "run_experiment.py", "# frozen experiment runner\n")
    write_text(materialization / "scripts" / "summarize_run.py", "# frozen report runner\n")
    write_text(materialization / "evaluator" / "evaluate.py", "# frozen study evaluator\n")
    write_json(
        materialization / "data" / "agent-visible" / "manifest.json",
        {"schema_version": 1, "partition": "agent-visible", "tests": visible_tests},
    )
    source_file_hashes = {
        "scripts/run_experiment.py": text_sha256("runner"),
        "scripts/summarize_run.py": text_sha256("reporter"),
        "pi/extensions/base.ts": text_sha256("extension"),
        "evaluator/evaluate.py": text_sha256("evaluator"),
    }
    rendered = {
        "specification_sha256": text_sha256("Fixture specification\n"),
        "specification_bytes": len("Fixture specification\n".encode()),
        "specification_words": 2,
        "prompt_hashes": summarize_study.file_hash_tree(materialization / "prompts", "fixture prompts"),
        "prompt_bytes": {name: len(content.encode()) for name, content in prompt_contents.items()},
        "extension_hashes": summarize_study.file_hash_tree(
            materialization / "pi" / "extensions", "fixture extensions"
        ),
        "candidate_adapter_sha256": candidate_sha256,
        "visible_manifest_sha256": summarize_study.sha256_file(
            materialization / "data" / "partitions" / "visible" / "manifest.json"
        ),
        "hidden_manifest_sha256": summarize_study.sha256_file(
            materialization / "data" / "partitions" / "hidden" / "manifest.json"
        ),
        "visible_test_count": 2,
        "agent_visible_test_count": 2,
        "hidden_test_count": 2,
        "scaffold_hashes": {},
    }
    materialization_record = {
        "schema_version": 1,
        "created_at": "2026-01-01T00:00:00Z",
        "study_id": study["id"],
        "study_path": "study.json",
        "study_sha256": study_sha256,
        "condition": condition,
        "condition_sha256": summarize_study.sha256_json(condition),
        "run_id": run_id,
        "effective_config": configuration,
        "completion_threshold": study["completion_threshold"],
        "source_harness": {
            "repo_root": str(summarize_study.REPO_ROOT),
            "manifest_sha256": summarize_study.sha256_file(materialization / "MANIFEST.sha256"),
            "file_hashes": source_file_hashes,
        },
        "materialized_harness": {
            "file_hashes": summarize_study.materialized_harness_file_hashes(materialization),
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
        "prompt_and_extension_hashes": summarize_study.file_hash_tree(run_dir / "control", "fixture control"),
        "visible_manifest_sha256": rendered["visible_manifest_sha256"],
        "hidden_manifest_sha256": rendered["hidden_manifest_sha256"],
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
        hidden_results = [
            evaluator_result(hidden_tests[0], True),
            evaluator_result(hidden_tests[1], round_number > 0),
        ]
        hidden_summary = {
            "score": score,
            "micro_score": score,
            "passed": passed,
            "failed": 2 - passed,
            "total": 2,
            "build_ok": True,
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
                "build_ok": True,
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
            "candidate": {"adapter_sha256": candidate_sha256},
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
            "candidate": {"adapter_sha256": candidate_sha256},
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
        write_jsonl(run_dir / "artifacts" / "fuzz-scores.jsonl", [fuzz_row])
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
        self.study_sha256 = summarize_study.sha256_file(self.study_path)
        self.condition_hashes = summarize_study.current_condition_hashes(self.study)

    def tearDown(self) -> None:
        self.repo_patch.stop()
        self.temporary.cleanup()

    def collect(self, run_dir: Path):
        return summarize_study.collect_run(
            run_dir,
            str(self.study["id"]),
            self.study_sha256,
            self.condition_hashes,
        )

    def test_eligible_main_run_exposes_profile_and_fingerprints(self) -> None:
        run_dir = make_run(self.runs, "main-r1", self.study, self.study_sha256)
        row, warning = self.collect(run_dir)
        self.assertIsNone(warning)
        self.assertIsNotNone(row)
        assert row is not None
        self.assertEqual(row["profile"], "main")
        self.assertEqual(row["replicate"], 1)
        self.assertEqual(row["study_sha256"], self.study_sha256)
        self.assertEqual(row["model_provider"], "zai")
        self.assertEqual(row["hidden_evaluation_rounds"], 2)
        self.assertRegex(row["source_harness_sha256"], r"^[0-9a-f]{64}$")
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
                    self.study_sha256,
                    **overrides,
                )
                row, warning = self.collect(run_dir)
                self.assertIsNone(row)
                self.assertIn(expected, warning or "")

    def test_study_and_condition_hash_drift_are_excluded(self) -> None:
        stale_study = make_run(self.runs, "stale-study", self.study, "0" * 64)
        row, warning = self.collect(stale_study)
        self.assertIsNone(row)
        self.assertIn("study SHA-256", warning or "")

        corrupt_condition = make_run(self.runs, "corrupt-condition", self.study, self.study_sha256)
        sidecar_path = corrupt_condition / "study-metadata.json"
        sidecar = summarize_study.load_object(sidecar_path)
        sidecar["condition"]["description"] = "tampered"
        write_json(sidecar_path, sidecar)
        row, warning = self.collect(corrupt_condition)
        self.assertIsNone(row)
        self.assertIn("frozen condition payload", warning or "")

        stale_condition = make_run(self.runs, "stale-condition", self.study, self.study_sha256)
        sidecar_path = stale_condition / "study-metadata.json"
        sidecar = summarize_study.load_object(sidecar_path)
        sidecar["condition"]["description"] = "old condition"
        sidecar["condition_sha256"] = summarize_study.sha256_json(sidecar["condition"])
        write_json(sidecar_path, sidecar)
        row, warning = self.collect(stale_condition)
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
        partial = make_run(self.runs, "partial-hidden", self.study, self.study_sha256)
        report_path = partial / "report.json"
        report = summarize_study.load_object(report_path)
        report["hidden_trajectory"] = report["hidden_trajectory"][-1:]
        write_json(report_path, report)
        row, warning = self.collect(partial)
        self.assertIsNone(row)
        self.assertIn("does not cover every frozen snapshot", warning or "")

        tampered = make_run(self.runs, "tampered-score", self.study, self.study_sha256)
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
        run_dir = make_run(self.runs, "missing-usage", self.study, self.study_sha256, usage={})
        row, warning = self.collect(run_dir)
        self.assertIsNone(warning)
        assert row is not None
        for field in ("input_tokens", "output_tokens", "cache_read_tokens", "cache_write_tokens"):
            self.assertIsNone(row[field])
        self.assertIsNone(row["hidden_score_per_million_generation_tokens"])

    def test_runtime_and_report_provenance_mismatches_are_excluded(self) -> None:
        materialized = make_run(self.runs, "changed-evaluator", self.study, self.study_sha256)
        sidecar = summarize_study.load_object(materialized / "study-metadata.json")
        root = summarize_study.REPO_ROOT / sidecar["materialization_root"]
        write_text(root / "evaluator" / "evaluate.py", "# changed evaluator\n")
        row, warning = self.collect(materialized)
        self.assertIsNone(row)
        self.assertIn("materialized harness files changed", warning or "")

        config = make_run(self.runs, "changed-config", self.study, self.study_sha256)
        metadata_path = config / "metadata.json"
        metadata = summarize_study.load_object(metadata_path)
        metadata["configuration"]["AGENT_CPUS"] = "4"
        write_json(metadata_path, metadata)
        row, warning = self.collect(config)
        self.assertIsNone(row)
        self.assertIn("frozen effective configuration", warning or "")

        image = make_run(self.runs, "changed-image", self.study, self.study_sha256)
        full_path = image / "artifacts" / "evaluations" / "hidden-round-000.json"
        full = summarize_study.load_object(full_path)
        full["docker_image"]["id"] = "sha256:different"
        write_json(full_path, full)
        row, warning = self.collect(image)
        self.assertIsNone(row)
        self.assertIn("different Docker image", warning or "")

        usage = make_run(self.runs, "changed-usage", self.study, self.study_sha256)
        report_path = usage / "report.json"
        report = summarize_study.load_object(report_path)
        report["pi_events"]["usage"]["input"] = 999
        write_json(report_path, report)
        row, warning = self.collect(usage)
        self.assertIsNone(row)
        self.assertIn("raw event ledgers", warning or "")

        guard = make_run(self.runs, "changed-guard", self.study, self.study_sha256)
        report_path = guard / "report.json"
        report = summarize_study.load_object(report_path)
        report["guard"]["blocked_calls"] = 1
        write_json(report_path, report)
        row, warning = self.collect(guard)
        self.assertIsNone(row)
        self.assertIn("guard metrics", warning or "")

    def test_one_snapshot_early_stop_is_included_with_origin_auc(self) -> None:
        run_dir = make_run(
            self.runs,
            "early-stop",
            self.study,
            self.study_sha256,
            round_count=1,
        )
        row, warning = self.collect(run_dir)
        self.assertIsNone(warning)
        assert row is not None
        self.assertEqual(row["hidden_evaluation_rounds"], 1)
        self.assertAlmostEqual(row["hidden_auc"], 0.25)

    def test_cohort_drift_is_hard_error_but_declared_condition_config_may_vary(self) -> None:
        first_dir = make_run(self.runs, "cohort-r1", self.study, self.study_sha256, replicate=1)
        second_dir = make_run(self.runs, "cohort-r2", self.study, self.study_sha256, replicate=2)
        first, _ = self.collect(first_dir)
        second, _ = self.collect(second_dir)
        assert first is not None and second is not None

        drifted = dict(second)
        drifted["hidden_manifest_sha256"] = "f" * 64
        with self.assertRaisesRegex(summarize_study.SummaryError, "hidden_manifest_sha256"):
            summarize_study.reject_cohort_drift([first, drifted])

        drifted = dict(second)
        drifted["rendered_assets_sha256"] = "e" * 64
        with self.assertRaisesRegex(summarize_study.SummaryError, "rendered_assets_sha256"):
            summarize_study.reject_cohort_drift([first, drifted])

        variant = dict(second)
        variant["condition_id"] = "budget-variant"
        variant["condition_sha256"] = "d" * 64
        variant["configuration_sha256"] = "c" * 64
        variant["budget_sha256"] = "b" * 64
        summarize_study.reject_cohort_drift([first, variant])

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
        run_dir = make_run(self.runs, "nofuzz-r1", self.study, self.study_sha256, fuzz=None)
        row, warning = self.collect(run_dir)
        self.assertIsNotNone(row)
        self.assertIsNone(row["fuzz_macro"])
        self.assertIn("no fuzz-oracle score", warning)

        run_dir = make_run(self.runs, "fuzz-r2", self.study, self.study_sha256, replicate=2, fuzz={"rates": [1.0]})
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
                run_dir = make_run(self.runs, f"tampered-{label.replace(' ', '-')}", self.study, self.study_sha256, replicate=3, fuzz=tampering)
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
        make_run(self.runs, "main-r1", self.study, self.study_sha256)
        make_run(self.runs, "pilot-r1", self.study, self.study_sha256, profile="pilot")
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
