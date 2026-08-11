from __future__ import annotations

import argparse
import contextlib
import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import evaluate_run as evaluator  # noqa: E402


RUN_ID = "evaluation-provenance-test"
IMAGE_NAME = "picc-test:frozen"
IMAGE_ID = "sha256:frozen-image"
COMMIT = "a" * 40
TREE = "b" * 40


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True) + "\n", encoding="utf-8")


def evaluation_args() -> argparse.Namespace:
    return argparse.Namespace(partition="hidden", all_snapshots=True, max_stage=None)


class EvaluationProvenanceTests(unittest.TestCase):
    def build_run(self, root: Path) -> tuple[Path, Path]:
        run_dir = root / "runs" / RUN_ID
        artifacts = run_dir / "artifacts"
        (artifacts / "evaluations").mkdir(parents=True)
        write_json(
            run_dir / "metadata.json",
            {
                "run_id": RUN_ID,
                "status": "completed",
                "docker_image": {"name": IMAGE_NAME, "id": IMAGE_ID},
                "budget": {"max_stage": 1},
            },
        )
        return run_dir, artifacts

    def test_image_name_mismatch_fails_before_output_cleanup(self) -> None:
        with tempfile.TemporaryDirectory(prefix="picc-evaluation-provenance-") as temporary:
            root = Path(temporary)
            run_dir, artifacts = self.build_run(root)
            score_ledger = artifacts / "hidden-scores.jsonl"
            score_ledger.write_text("preserve me\n", encoding="utf-8")

            with (
                mock.patch.object(
                    evaluator,
                    "load_config",
                    return_value={"EXPERIMENT_IMAGE": "picc-test:changed"},
                ),
                mock.patch.object(evaluator, "docker_image_id") as inspect_image,
                mock.patch.object(evaluator.subprocess, "run") as run,
                self.assertRaisesRegex(evaluator.ExperimentError, "image name changed"),
            ):
                evaluator.evaluate_locked(evaluation_args(), RUN_ID, run_dir)

            self.assertEqual(score_ledger.read_text(encoding="utf-8"), "preserve me\n")
            inspect_image.assert_not_called()
            run.assert_not_called()

    def test_image_id_mismatch_fails_before_output_cleanup(self) -> None:
        with tempfile.TemporaryDirectory(prefix="picc-evaluation-provenance-") as temporary:
            root = Path(temporary)
            run_dir, artifacts = self.build_run(root)
            score_ledger = artifacts / "hidden-scores.jsonl"
            score_ledger.write_text("preserve me\n", encoding="utf-8")

            with (
                mock.patch.object(
                    evaluator,
                    "load_config",
                    return_value={"EXPERIMENT_IMAGE": IMAGE_NAME},
                ),
                mock.patch.object(
                    evaluator,
                    "docker_image_id",
                    return_value="sha256:changed-image",
                ) as inspect_image,
                mock.patch.object(evaluator.subprocess, "run") as run,
                self.assertRaisesRegex(evaluator.ExperimentError, "Docker image .* changed"),
            ):
                evaluator.evaluate_locked(evaluation_args(), RUN_ID, run_dir)

            self.assertEqual(score_ledger.read_text(encoding="utf-8"), "preserve me\n")
            inspect_image.assert_called_once_with(IMAGE_NAME)
            run.assert_not_called()

    def test_outputs_record_snapshot_and_verified_image(self) -> None:
        with tempfile.TemporaryDirectory(prefix="picc-evaluation-provenance-") as temporary:
            root = Path(temporary)
            run_dir, artifacts = self.build_run(root)
            workspace = run_dir / "workspace"
            workspace.mkdir()
            write_json(
                root / "data" / "partitions" / "hidden" / "manifest.json",
                {"partition": "hidden", "tests": [{"id": "hidden-1", "stage": 1}]},
            )
            (artifacts / "snapshots.jsonl").write_text(
                json.dumps(
                    {
                        "round": 0,
                        "elapsed_seconds": 12.5,
                        "git_commit": COMMIT,
                        "git_tree": TREE,
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            completed = subprocess.CompletedProcess([], 0, "", "")
            seen_config: dict[str, str] = {}

            def fake_evaluate_snapshot(
                config: dict[str, str],
                unused_workspace: Path,
                unused_tests: Path,
                unused_evaluator: Path,
                output_artifacts: Path,
                output_name: str,
                max_stage: int,
            ) -> tuple[int, str, str, Path]:
                seen_config.update(config)
                self.assertEqual(max_stage, 1)
                output_path = output_artifacts / "evaluations" / output_name
                write_json(
                    output_path,
                    {
                        "summary": {
                            "score": 0.75,
                            "passed": 3,
                            "failed": 1,
                            "total": 4,
                            "build_ok": True,
                        }
                    },
                )
                return 0, "summary\n", "", output_path

            with (
                mock.patch.object(evaluator, "REPO_ROOT", root),
                mock.patch.object(
                    evaluator,
                    "load_config",
                    return_value={"EXPERIMENT_IMAGE": IMAGE_NAME},
                ),
                mock.patch.object(
                    evaluator,
                    "docker_image_id",
                    return_value=IMAGE_ID,
                ) as inspect_image,
                mock.patch.object(
                    evaluator.subprocess,
                    "run",
                    return_value=completed,
                ) as run,
                mock.patch.object(
                    evaluator,
                    "git_revision",
                    side_effect=[COMMIT, TREE],
                ),
                mock.patch.object(
                    evaluator,
                    "evaluate_snapshot",
                    side_effect=fake_evaluate_snapshot,
                ),
                contextlib.redirect_stdout(io.StringIO()),
            ):
                result = evaluator.evaluate_locked(evaluation_args(), RUN_ID, run_dir)

            self.assertEqual(result, 0)
            inspect_image.assert_called_once_with(IMAGE_NAME)
            self.assertEqual(run.call_count, 3)
            self.assertEqual(seen_config["EXPERIMENT_IMAGE"], IMAGE_ID)

            full = json.loads(
                (artifacts / "evaluations" / "hidden-round-000.json").read_text(encoding="utf-8")
            )
            self.assertEqual(full["snapshot"], {"git_commit": COMMIT, "git_tree": TREE})
            self.assertEqual(full["docker_image"], {"name": IMAGE_NAME, "id": IMAGE_ID})

            rows = evaluator.read_jsonl(artifacts / "hidden-scores.jsonl")
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["git_commit"], COMMIT)
            self.assertEqual(rows[0]["git_tree"], TREE)
            self.assertEqual(rows[0]["docker_image"], {"name": IMAGE_NAME, "id": IMAGE_ID})


if __name__ == "__main__":
    unittest.main()
