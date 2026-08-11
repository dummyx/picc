from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import run_experiment as runner  # noqa: E402


class DetachedVisibleEvaluationTests(unittest.TestCase):
    def test_scores_recorded_commit_in_disposable_worktree(self) -> None:
        with tempfile.TemporaryDirectory(prefix="picc-snapshot-eval-") as temporary:
            root = Path(temporary)
            workspace = root / "workspace"
            visible = root / "visible"
            evaluator = root / "evaluator"
            artifacts = root / "run" / "artifacts"
            for path in (workspace, visible, evaluator, artifacts):
                path.mkdir(parents=True)

            completed = subprocess.CompletedProcess([], 0, "", "")
            expected = {"score": 0.75}
            with (
                mock.patch.object(runner.subprocess, "run", side_effect=[completed, completed]) as run,
                mock.patch.object(
                    runner,
                    "_run_visible_evaluation_in_workspace",
                    return_value=expected,
                ) as evaluate,
            ):
                result = runner.run_visible_evaluation(
                    {"EXPERIMENT_IMAGE": "image"},
                    workspace,
                    visible,
                    evaluator,
                    artifacts,
                    3,
                    6,
                    "a" * 40,
                )

            self.assertEqual(result, expected)
            self.assertEqual(run.call_count, 2)
            add = run.call_args_list[0]
            self.assertEqual(add.args[0][:4], ["git", "worktree", "add", "--detach"])
            self.assertEqual(add.args[0][-1], "a" * 40)
            self.assertEqual(add.kwargs["cwd"], workspace)

            scored_workspace = evaluate.call_args.args[1]
            self.assertNotEqual(scored_workspace, workspace)
            self.assertEqual(scored_workspace.name, "workspace")
            remove = run.call_args_list[1]
            self.assertEqual(
                remove.args[0],
                ["git", "worktree", "remove", "--force", str(scored_workspace)],
            )
            self.assertFalse(scored_workspace.exists())

    def test_refuses_to_score_when_detached_checkout_fails(self) -> None:
        with tempfile.TemporaryDirectory(prefix="picc-snapshot-eval-") as temporary:
            root = Path(temporary)
            workspace = root / "workspace"
            artifacts = root / "run" / "artifacts"
            workspace.mkdir()
            artifacts.mkdir(parents=True)
            failed = subprocess.CompletedProcess([], 1, "", "bad commit")

            with (
                mock.patch.object(runner.subprocess, "run", return_value=failed) as run,
                mock.patch.object(runner, "_run_visible_evaluation_in_workspace") as evaluate,
                self.assertRaisesRegex(runner.ExperimentError, "git worktree failed"),
            ):
                runner.run_visible_evaluation(
                    {}, workspace, root / "visible", root / "evaluator", artifacts, 0, 1, "bad"
                )

            run.assert_called_once()
            evaluate.assert_not_called()
