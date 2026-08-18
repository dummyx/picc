#!/usr/bin/env python3
"""Regression tests for resumable experiment runs without Docker/provider calls."""

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


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import run_experiment as runner  # noqa: E402
import evaluate_run as evaluator_runner  # noqa: E402
import summarize_run as summarizer  # noqa: E402


RUN_ID = "resume-test-run"
IMAGE_NAME = "picc-test:0.1"
IMAGE_ID = "sha256:resume-test-image"
ELAPSED_BEFORE = 2700.7868299600086


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def git(workspace: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=workspace,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


class ResumeFixture:
    """A minimal durable run with one completed, timed-out round."""

    def __init__(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="picc-resume-test-")
        self.root = Path(self.temporary.name)
        self.run_dir = self.root / "runs" / RUN_ID
        self.workspace = self.run_dir / "workspace"
        self.control = self.run_dir / "control"
        self.artifacts = self.run_dir / "artifacts"
        self.visible_manifest = self.root / "data" / "partitions" / "visible" / "manifest.json"
        self.hidden_manifest = self.root / "data" / "partitions" / "hidden" / "manifest.json"
        self.image_id = IMAGE_ID

        self._build_workspace()
        self._build_control()
        self._build_manifests()
        self._build_artifacts()
        self._build_metadata()

    def __enter__(self) -> "ResumeFixture":
        return self

    def __exit__(self, *unused: object) -> None:
        self.temporary.cleanup()

    def _build_workspace(self) -> None:
        self.workspace.mkdir(parents=True)
        git(self.workspace, "init", "-b", "main")
        git(self.workspace, "config", "user.name", "Resume test")
        git(self.workspace, "config", "user.email", "resume@example.invalid")
        (self.workspace / "product.txt").write_text("round zero\n", encoding="utf-8")
        git(self.workspace, "add", "product.txt")
        git(self.workspace, "commit", "-m", "round zero")
        self.commit = git(self.workspace, "rev-parse", "HEAD")
        self.tree = git(self.workspace, "rev-parse", "HEAD^{tree}")

    def _build_control(self) -> None:
        files = {
            "AGENTS.md": "frozen agents\n",
            "TASK.md": "frozen task\n",
            "INITIAL.txt": "initial prompt\n",
            "CONTINUE.txt": "continue prompt\n",
            "pi/settings.json": "{}\n",
            "pi/extensions/experiment-guard.ts": "export {};\n",
            "pi/extensions/experiment-tools.ts": "export {};\n",
        }
        for relative, content in files.items():
            path = self.control / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")

    def _build_manifests(self) -> None:
        write_json(self.visible_manifest, {"partition": "visible", "tests": []})
        write_json(self.hidden_manifest, {"partition": "hidden", "tests": []})
        (self.root / "evaluator").mkdir()
        (self.root / "MANIFEST.sha256").write_text("test manifest\n", encoding="utf-8")

    def _build_artifacts(self) -> None:
        for path in (
            self.artifacts / "events",
            self.artifacts / "evaluations",
            self.artifacts / "sessions",
            self.artifacts / "home",
            self.artifacts / "pi-global",
            self.artifacts / "tool-evaluations",
        ):
            path.mkdir(parents=True, exist_ok=True)

        (self.artifacts / "events" / "round-000.jsonl").write_text(
            '{"type":"message_end"}\n', encoding="utf-8"
        )
        (self.artifacts / "events" / "round-000.stderr.log").write_text(
            "timed out\n", encoding="utf-8"
        )
        write_json(self.artifacts / "evaluations" / "visible-round-000.json", {"summary": {}})
        (self.artifacts / "evaluations" / "visible-round-000.stdout.log").write_text(
            "visible summary\n", encoding="utf-8"
        )
        (self.artifacts / "evaluations" / "visible-round-000.stderr.log").write_text(
            "", encoding="utf-8"
        )

        self.rounds: list[dict[str, object]] = [
            {
                "round": 0,
                "started_at": "2026-08-10T06:59:52+00:00",
                "ended_at": "2026-08-10T07:44:52+00:00",
                "elapsed_seconds": 2700.2,
                "returncode": 137,
                "timed_out": True,
            }
        ]
        self.visible = {
            "score": 0.25,
            "micro_score": 0.2,
            "passed": 1,
            "failed": 3,
            "total": 4,
            "build_ok": True,
        }
        self.snapshots: list[dict[str, object]] = [
            {
                "round": 0,
                "timestamp": "2026-08-10T07:44:52+00:00",
                "elapsed_seconds": 2700.7,
                "git_commit": self.commit,
                "git_tree": self.tree,
                "pi_returncode": 137,
                "pi_timed_out": True,
                "visible": self.visible,
            }
        ]
        self.write_ledgers()
        write_jsonl(
            self.artifacts / "sessions" / "session.jsonl",
            [
                {"type": "session", "version": 3, "id": "session-id", "cwd": "/workspace"},
                {"type": "session_info", "id": "info-id", "name": RUN_ID},
                {"type": "message", "message": {"role": "toolResult"}},
            ],
        )

    def _build_metadata(self) -> None:
        self.frozen_config = {
            "AGENT_CPUS": "8",
            "EXPERIMENT_IMAGE": IMAGE_NAME,
            "PERFECT_VISIBLE_REVIEW_ROUNDS": "1",
            "PILOT_HOURS": "2",
            "PILOT_MAX_STAGE": "6",
            "PILOT_ROUNDS": "6",
            "PILOT_ROUND_TIMEOUT_MINUTES": "45",
            "MODEL_ID": "glm-5.2",
            "MODEL_PROVIDER": "zai",
            "MODEL_THINKING": "max",
        }
        self.current_config = dict(self.frozen_config)
        self.current_config.update({"AGENT_CPUS": "99", "ZAI_API_KEY": "test-secret"})
        self.metadata: dict[str, object] = {
            "schema_version": 1,
            "run_id": RUN_ID,
            "profile": "pilot",
            "replicate": None,
            "started_at": "2026-08-10T06:59:52+00:00",
            "ended_at": "2026-08-10T07:44:52+00:00",
            "elapsed_seconds": ELAPSED_BEFORE,
            "status": "completed",
            "termination_reason": "round_timeout",
            "host": {"system": "test"},
            "configuration": self.frozen_config,
            "model": {
                "provider": "zai",
                "id": "glm-5.2",
                "thinking": "max",
            },
            "docker_image": {"name": IMAGE_NAME, "id": self.image_id},
            "prompt_and_extension_hashes": runner.prompt_hashes(self.control),
            "visible_manifest_sha256": runner.sha256_file(self.visible_manifest),
            "hidden_manifest_sha256": runner.sha256_file(self.hidden_manifest),
            "budget": {
                "wall_hours": 2.0,
                "max_rounds": 6,
                "round_timeout_minutes": 45,
                "max_stage": 6,
            },
            "last_visible": self.visible,
        }
        self.write_metadata()

    def write_metadata(self) -> None:
        write_json(self.run_dir / "metadata.json", self.metadata)

    def write_ledgers(self) -> None:
        write_jsonl(self.artifacts / "rounds.jsonl", self.rounds)
        write_jsonl(self.artifacts / "snapshots.jsonl", self.snapshots)

    def run_without_docker(self, active_containers: str = ""):
        real_run = runner.run

        def invoke(args, **kwargs):
            if list(args[:2]) == ["docker", "ps"]:
                return subprocess.CompletedProcess(args, 0, active_containers, "")
            return real_run(args, **kwargs)

        return invoke

    def plan(self, *, active_containers: str = "", image_id: str | None = None):
        with mock.patch.object(runner, "run", side_effect=self.run_without_docker(active_containers)):
            return runner.plan_resume(
                run_id=RUN_ID,
                run_dir=self.run_dir,
                current_config=self.current_config,
                visible_manifest=self.visible_manifest,
                hidden_manifest=self.hidden_manifest,
                current_image_id=self.image_id if image_id is None else image_id,
            )


class ResumePlanningTests(unittest.TestCase):
    def test_plan_restores_round_state_and_frozen_budget(self) -> None:
        with ResumeFixture() as fixture:
            plan = fixture.plan()
            expected_visible = fixture.visible
            expected_commit = fixture.commit

        self.assertEqual(plan["next_round"], 1)
        self.assertEqual(plan["remaining_rounds"], 5)
        self.assertAlmostEqual(plan["elapsed_before"], ELAPSED_BEFORE)
        self.assertAlmostEqual(plan["remaining_seconds"], 7200.0 - ELAPSED_BEFORE)
        self.assertEqual(plan["last_visible"], expected_visible)
        self.assertEqual(plan["workspace_commit"], expected_commit)
        self.assertEqual(plan["config"]["AGENT_CPUS"], "8")
        self.assertEqual(plan["config"]["ZAI_API_KEY"], "test-secret")

    def test_second_resume_accepts_consistent_history_and_rejects_a_broken_link(self) -> None:
        with ResumeFixture() as fixture:
            git(fixture.workspace, "commit", "--allow-empty", "-m", "round one")
            second_commit = git(fixture.workspace, "rev-parse", "HEAD")
            second_tree = git(fixture.workspace, "rev-parse", "HEAD^{tree}")
            second_attempt_elapsed = 100.0
            cumulative_elapsed = ELAPSED_BEFORE + second_attempt_elapsed

            (fixture.artifacts / "events" / "round-001.jsonl").write_text(
                '{"type":"message_end"}\n', encoding="utf-8"
            )
            (fixture.artifacts / "events" / "round-001.stderr.log").write_text(
                "", encoding="utf-8"
            )
            write_json(
                fixture.artifacts / "evaluations" / "visible-round-001.json",
                {"summary": fixture.visible},
            )
            (fixture.artifacts / "evaluations" / "visible-round-001.stdout.log").write_text(
                "visible summary\n", encoding="utf-8"
            )
            (fixture.artifacts / "evaluations" / "visible-round-001.stderr.log").write_text(
                "", encoding="utf-8"
            )
            fixture.rounds.append(
                {
                    "round": 1,
                    "started_at": "2026-08-10T08:00:00+00:00",
                    "ended_at": "2026-08-10T08:01:39+00:00",
                    "elapsed_seconds": 99.0,
                    "returncode": 137,
                    "timed_out": True,
                }
            )
            fixture.snapshots.append(
                {
                    "round": 1,
                    "timestamp": "2026-08-10T08:01:39+00:00",
                    "elapsed_seconds": cumulative_elapsed - 0.1,
                    "git_commit": second_commit,
                    "git_tree": second_tree,
                    "pi_returncode": 137,
                    "pi_timed_out": True,
                    "visible": fixture.visible,
                }
            )
            fixture.write_ledgers()
            fixture.metadata.update(
                {
                    "schema_version": 2,
                    "elapsed_seconds": cumulative_elapsed,
                    "resume_count": 1,
                    "resumed": True,
                    "protocol_comparable": False,
                    "interventions": [{"resume_index": 1, "next_round": 1}],
                    "execution_attempts": [
                        {
                            "index": 0,
                            "kind": "initial",
                            "status": "completed",
                            "first_round": 0,
                            "last_round": 0,
                            "rounds_attempted": 1,
                            "elapsed_seconds_before": 0.0,
                            "elapsed_seconds": ELAPSED_BEFORE,
                            "termination_reason": "round_timeout",
                        },
                        {
                            "index": 1,
                            "kind": "resume",
                            "status": "completed",
                            "first_round": 1,
                            "last_round": 1,
                            "rounds_attempted": 1,
                            "elapsed_seconds_before": ELAPSED_BEFORE,
                            "elapsed_seconds": second_attempt_elapsed,
                            "termination_reason": "round_timeout",
                        },
                    ],
                }
            )
            fixture.write_metadata()
            audit_events = [
                {"event": "resume_started", "resume_index": 1},
                {"event": "resume_finished", "resume_index": 1},
            ]
            audit_path = fixture.artifacts / "resume-events.jsonl"
            write_jsonl(audit_path, audit_events)

            plan = fixture.plan()
            attempts = runner.ensure_execution_attempts(plan["metadata"], plan)
            self.assertEqual(plan["next_round"], 2)
            self.assertEqual(plan["remaining_rounds"], 4)
            self.assertAlmostEqual(plan["elapsed_before"], cumulative_elapsed)
            self.assertEqual(len(attempts), 2)
            self.assertEqual(len(attempts), plan["metadata"]["resume_count"] + 1)

            corrupt_audits = {
                "missing finish": audit_events[:1],
                "out of sequence": list(reversed(audit_events)),
            }
            for name, events in corrupt_audits.items():
                with self.subTest(audit=name):
                    write_jsonl(audit_path, events)
                    with self.assertRaisesRegex(runner.ExperimentError, "incomplete or out of sequence"):
                        fixture.plan()
            write_jsonl(audit_path, audit_events)

            attempts[1]["elapsed_seconds_before"] = ELAPSED_BEFORE + 1.0
            with self.assertRaisesRegex(runner.ExperimentError, "inconsistent prior elapsed"):
                runner.ensure_execution_attempts(plan["metadata"], plan)

    def test_timeout_never_exceeds_remaining_budget(self) -> None:
        self.assertEqual(runner.effective_round_timeout(45, 5000.0), 2700.0)
        self.assertEqual(runner.effective_round_timeout(45, 30.25), 30.25)
        for cap, remaining in ((0, 10.0), (45, 0.0), (-1, 10.0)):
            with self.subTest(cap=cap, remaining=remaining):
                with self.assertRaises(runner.ExperimentError):
                    runner.effective_round_timeout(cap, remaining)

    def test_long_run_ids_have_distinct_bounded_container_names(self) -> None:
        common_prefix = "a" * 90
        names = {
            runner.pi_container_name(common_prefix + suffix, 1)
            for suffix in ("111111", "222222")
        }
        self.assertEqual(len(names), 2)
        for name in names:
            self.assertLessEqual(len(name), 63)
            self.assertTrue(name.endswith("-001"))

    def test_perfect_visible_review_state_uses_only_successful_rounds(self) -> None:
        snapshots = [
            {"round": 0, "pi_returncode": 0, "pi_timed_out": False, "visible": {"score": 1.0}},
            {"round": 1, "pi_returncode": 0, "pi_timed_out": False, "visible": {"score": 1.0}},
        ]
        self.assertEqual(runner.perfect_visible_start(snapshots), 0)
        snapshots.append(
            {"round": 2, "pi_returncode": 137, "pi_timed_out": True, "visible": {"score": 1.0}}
        )
        self.assertIsNone(runner.perfect_visible_start(snapshots))

    def test_rejects_ineligible_status_reason_and_exhausted_budgets(self) -> None:
        cases = {
            "active status": lambda metadata: metadata.update(status="running"),
            "terminal reason": lambda metadata: metadata.update(termination_reason="max_rounds"),
            "unsupported schema": lambda metadata: metadata.update(schema_version=99),
            "wall budget": lambda metadata: metadata.update(elapsed_seconds=7200.0),
            "round budget": lambda metadata: metadata["budget"].update(max_rounds=1),
        }
        for name, mutate in cases.items():
            with self.subTest(name=name), ResumeFixture() as fixture:
                mutate(fixture.metadata)
                fixture.write_metadata()
                with self.assertRaises(runner.ExperimentError):
                    fixture.plan()

    def test_terminal_reason_must_match_the_final_round(self) -> None:
        invalid = (
            ("timeout recorded for success", "round_timeout", 0, False, "round_timeout metadata"),
            (
                "process failure recorded for success",
                "pi_process_failure",
                0,
                False,
                "pi_process_failure metadata",
            ),
        )
        for name, reason, returncode, timed_out, message in invalid:
            with self.subTest(name=name), ResumeFixture() as fixture:
                fixture.metadata["termination_reason"] = reason
                fixture.rounds[-1].update(returncode=returncode, timed_out=timed_out)
                fixture.snapshots[-1].update(
                    pi_returncode=returncode,
                    pi_timed_out=timed_out,
                )
                fixture.write_metadata()
                fixture.write_ledgers()
                with self.assertRaisesRegex(runner.ExperimentError, message):
                    fixture.plan()

        with self.subTest(name="nonzero process failure accepted"), ResumeFixture() as fixture:
            fixture.metadata["termination_reason"] = "pi_process_failure"
            fixture.rounds[-1].update(returncode=1, timed_out=False)
            fixture.snapshots[-1].update(pi_returncode=1, pi_timed_out=False)
            fixture.write_metadata()
            fixture.write_ledgers()
            plan = fixture.plan()
            self.assertEqual(plan["previous_reason"], "pi_process_failure")

    def test_rejects_corrupt_or_nonsequential_ledgers(self) -> None:
        cases = {
            "round gap": lambda fixture: fixture.rounds[0].update(round=1),
            "snapshot gap": lambda fixture: fixture.snapshots[0].update(round=1),
            "return code mismatch": lambda fixture: fixture.snapshots[0].update(pi_returncode=1),
            "missing snapshot": lambda fixture: fixture.snapshots.clear(),
        }
        for name, mutate in cases.items():
            with self.subTest(name=name), ResumeFixture() as fixture:
                mutate(fixture)
                fixture.write_ledgers()
                with self.assertRaises(runner.ExperimentError):
                    fixture.plan()

    def test_rejects_frozen_state_drift(self) -> None:
        with self.subTest("control"), ResumeFixture() as fixture:
            (fixture.control / "CONTINUE.txt").write_text("changed\n", encoding="utf-8")
            with self.assertRaisesRegex(runner.ExperimentError, "Frozen prompt"):
                fixture.plan()

        with self.subTest("injected extension"), ResumeFixture() as fixture:
            (fixture.control / "pi" / "extensions" / "injected.js").write_text(
                "export {};\n", encoding="utf-8"
            )
            with self.assertRaisesRegex(runner.ExperimentError, "Frozen prompt"):
                fixture.plan()

        with self.subTest("manifest"), ResumeFixture() as fixture:
            fixture.visible_manifest.write_text("changed\n", encoding="utf-8")
            with self.assertRaisesRegex(runner.ExperimentError, "Visible manifest"):
                fixture.plan()

        with self.subTest("image"), ResumeFixture() as fixture:
            with self.assertRaisesRegex(runner.ExperimentError, "Docker image"):
                fixture.plan(image_id="sha256:different")

        with self.subTest("model"), ResumeFixture() as fixture:
            fixture.metadata["model"]["id"] = "different"
            fixture.write_metadata()
            with self.assertRaisesRegex(runner.ExperimentError, "MODEL_ID"):
                fixture.plan()

    def test_rejects_postprocessing_and_next_round_collisions(self) -> None:
        paths = (
            lambda fixture: fixture.run_dir / "report.json",
            lambda fixture: fixture.artifacts / "hidden-scores.jsonl",
            lambda fixture: fixture.artifacts / "events" / "round-001.jsonl",
            lambda fixture: fixture.artifacts / "evaluations" / "visible-round-001.stderr.log",
        )
        for make_path in paths:
            with ResumeFixture() as fixture:
                path = make_path(fixture)
                with self.subTest(path=path.name):
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text("occupied\n", encoding="utf-8")
                    with self.assertRaises(runner.ExperimentError):
                        fixture.plan()

    def test_rejects_invalid_session_workspace_and_active_container(self) -> None:
        with self.subTest("extra session"), ResumeFixture() as fixture:
            (fixture.artifacts / "sessions" / "extra.jsonl").write_text("{}\n", encoding="utf-8")
            with self.assertRaisesRegex(runner.ExperimentError, "exactly one Pi session"):
                fixture.plan()

        with self.subTest("dirty workspace"), ResumeFixture() as fixture:
            (fixture.workspace / "untracked.txt").write_text("human edit\n", encoding="utf-8")
            with self.assertRaisesRegex(runner.ExperimentError, "uncommitted or untracked"):
                fixture.plan()

        with self.subTest("wrong HEAD"), ResumeFixture() as fixture:
            (fixture.workspace / "product.txt").write_text("later commit\n", encoding="utf-8")
            git(fixture.workspace, "add", "product.txt")
            git(fixture.workspace, "commit", "-m", "unexpected")
            with self.assertRaisesRegex(runner.ExperimentError, "HEAD"):
                fixture.plan()

        with self.subTest("active container"), ResumeFixture() as fixture:
            container = runner.pi_container_name(RUN_ID, 1)
            with self.assertRaisesRegex(runner.ExperimentError, "still active"):
                fixture.plan(active_containers=container + "\n")

    def test_resume_lock_rejects_a_concurrent_holder(self) -> None:
        with tempfile.TemporaryDirectory(prefix="picc-lock-test-") as temporary:
            run_dir = Path(temporary)
            with runner.resume_lock(run_dir):
                with self.assertRaisesRegex(runner.ExperimentError, "already locked"):
                    with runner.resume_lock(run_dir):
                        self.fail("the second lock acquisition unexpectedly succeeded")


class ResumeLifecycleTests(unittest.TestCase):
    def test_resume_execution_appends_audit_and_preserves_old_artifacts(self) -> None:
        with ResumeFixture() as fixture:
            preserved_paths = [
                *sorted((fixture.artifacts / "events").glob("round-000*")),
                *sorted((fixture.artifacts / "evaluations").glob("visible-round-000*")),
                *sorted((fixture.artifacts / "sessions").glob("*.jsonl")),
                *sorted(path for path in fixture.control.rglob("*") if path.is_file()),
            ]
            preserved = {path: path.read_bytes() for path in preserved_paths}
            captured: dict[str, object] = {}

            def fake_pi_round(**kwargs):
                captured.update(kwargs)
                (fixture.artifacts / "events" / "round-001.jsonl").write_text(
                    '{"type":"message_end"}\n', encoding="utf-8"
                )
                (fixture.artifacts / "events" / "round-001.stderr.log").write_text(
                    "", encoding="utf-8"
                )
                return {
                    "round": 1,
                    "started_at": "2026-08-10T08:00:00+00:00",
                    "ended_at": "2026-08-10T08:00:01+00:00",
                    "elapsed_seconds": 1.0,
                    "returncode": 137,
                    "timed_out": True,
                }

            resumed_visible = dict(fixture.visible, score=0.5, passed=2)

            def fake_visible(
                *,
                config,
                workspace,
                visible_tests,
                evaluator,
                artifacts,
                round_number,
                max_stage,
                commit,
            ):
                captured["visible_call"] = {
                    "config": config,
                    "workspace": workspace,
                    "visible_tests": visible_tests,
                    "evaluator": evaluator,
                    "artifacts": artifacts,
                    "round_number": round_number,
                    "max_stage": max_stage,
                    "commit": commit,
                }
                write_json(
                    artifacts / "evaluations" / "visible-round-001.json",
                    {"summary": resumed_visible},
                )
                (artifacts / "evaluations" / "visible-round-001.stdout.log").write_text(
                    "visible summary\n", encoding="utf-8"
                )
                (artifacts / "evaluations" / "visible-round-001.stderr.log").write_text(
                    "", encoding="utf-8"
                )
                return resumed_visible

            def fake_snapshot(unused_workspace: Path, round_number: int):
                return {
                    "round": round_number,
                    "timestamp": "2026-08-10T08:00:01+00:00",
                    "git_commit": fixture.commit,
                    "git_tree": fixture.tree,
                    "changed_files": 0,
                    "insertions": 0,
                    "deletions": 0,
                    "rust_files": 0,
                    "rust_loc": 0,
                }

            clock = iter(1000.0 + index * 0.25 for index in range(30))
            args = argparse.Namespace(resume=True, profile=None, replicate=None)
            with (
                mock.patch.object(runner, "REPO_ROOT", fixture.root),
                mock.patch.object(runner, "run", side_effect=fixture.run_without_docker()),
                mock.patch.object(runner, "docker_image_id", return_value=fixture.image_id),
                mock.patch.object(runner, "run_pi_round", side_effect=fake_pi_round),
                mock.patch.object(runner, "run_visible_evaluation", side_effect=fake_visible),
                mock.patch.object(runner, "snapshot_workspace", side_effect=fake_snapshot),
                mock.patch.object(runner, "replace_workspace_bundle"),
                mock.patch.object(runner.time, "monotonic", side_effect=lambda: next(clock)),
                mock.patch.object(runner, "utc_now", return_value="2026-08-10T08:00:00+00:00"),
                mock.patch.object(runner, "host_metadata", return_value={"system": "resume-test"}),
                contextlib.redirect_stdout(io.StringIO()),
            ):
                result = runner.execute_run(args, RUN_ID, fixture.run_dir, fixture.current_config)

            self.assertEqual(result, 0)
            self.assertEqual(captured["round_number"], 1)
            visible_call = captured["visible_call"]
            self.assertEqual(visible_call["config"]["EXPERIMENT_IMAGE"], IMAGE_NAME)
            self.assertEqual(visible_call["workspace"], fixture.workspace)
            self.assertEqual(visible_call["visible_tests"], fixture.visible_manifest.parent)
            self.assertEqual(visible_call["evaluator"], fixture.root / "evaluator")
            self.assertEqual(visible_call["artifacts"], fixture.artifacts)
            self.assertEqual(visible_call["round_number"], 1)
            self.assertEqual(visible_call["max_stage"], 6)
            self.assertEqual(visible_call["commit"], fixture.commit)
            self.assertTrue(captured["continuation"])
            self.assertEqual(captured["prompt"], "continue prompt\n")
            self.assertEqual(captured["config"]["AGENT_CPUS"], "8")
            self.assertLessEqual(captured["timeout_seconds"], 7200.0 - ELAPSED_BEFORE)
            for path, old_bytes in preserved.items():
                self.assertEqual(path.read_bytes(), old_bytes, f"overwrote {path}")

            metadata = json.loads((fixture.run_dir / "metadata.json").read_text(encoding="utf-8"))
            self.assertEqual(metadata["schema_version"], 2)
            self.assertEqual(metadata["started_at"], "2026-08-10T06:59:52+00:00")
            self.assertTrue(metadata["resumed"])
            self.assertFalse(metadata["protocol_comparable"])
            self.assertEqual(metadata["resume_count"], 1)
            self.assertEqual(metadata["termination_reason"], "round_timeout")
            self.assertGreater(metadata["elapsed_seconds"], ELAPSED_BEFORE)
            self.assertEqual(len(metadata["interventions"]), 1)
            self.assertEqual(metadata["interventions"][0]["prior_termination_reason"], "round_timeout")
            self.assertEqual(len(metadata["execution_attempts"]), 2)
            self.assertEqual(metadata["execution_attempts"][0]["last_round"], 0)
            self.assertEqual(metadata["execution_attempts"][1]["first_round"], 1)
            self.assertEqual(metadata["execution_attempts"][1]["rounds_attempted"], 1)

            resume_events = runner.read_jsonl(fixture.artifacts / "resume-events.jsonl")
            self.assertEqual([event["event"] for event in resume_events], ["resume_started", "resume_finished"])
            self.assertEqual(resume_events[0]["next_round"], 1)
            self.assertEqual(len(runner.read_jsonl(fixture.artifacts / "rounds.jsonl")), 2)
            snapshots = runner.read_jsonl(fixture.artifacts / "snapshots.jsonl")
            self.assertEqual([snapshot["round"] for snapshot in snapshots], [0, 1])
            self.assertGreater(snapshots[1]["elapsed_seconds"], snapshots[0]["elapsed_seconds"])

    def test_pi_continuation_command_uses_existing_session(self) -> None:
        with ResumeFixture() as fixture:
            captured: dict[str, object] = {}

            class FakeProcess:
                def __init__(self, command, **unused_kwargs):
                    captured["command"] = command

                def wait(self, timeout):
                    captured["timeout"] = timeout
                    return 0

            with (
                mock.patch.object(runner.subprocess, "Popen", FakeProcess),
                mock.patch.object(runner.time, "monotonic", side_effect=[10.0, 11.0]),
                mock.patch.object(runner, "utc_now", return_value="2026-08-10T08:00:00+00:00"),
            ):
                runner.run_pi_round(
                    config=fixture.frozen_config,
                    run_id=RUN_ID,
                    round_number=1,
                    workspace=fixture.workspace,
                    control=fixture.control,
                    artifacts=fixture.artifacts,
                    visible_tests=fixture.visible_manifest.parent,
                    evaluator=fixture.root / "evaluator",
                    prompt="continue prompt\n",
                    continuation=True,
                    timeout_seconds=30.0,
                    api_variable="ZAI_API_KEY",
                    api_key="secret",
                    max_stage=6,
                )

            command = captured["command"]
            pi_index = command.index("pi")
            pi_args = command[pi_index + 1 :]
            self.assertIn("--continue", pi_args)
            self.assertNotIn("--name", pi_args)
            self.assertEqual(pi_args[-1], "continue prompt\n")
            self.assertEqual(captured["timeout"], 30.0)

    def test_resume_cli_is_mutually_exclusive_with_new_run_options(self) -> None:
        with mock.patch.object(sys, "argv", ["run_experiment.py", "--resume", "--run-id", RUN_ID]):
            args = runner.parse_args()
        self.assertTrue(args.resume)
        self.assertIsNone(args.profile)

        with (
            mock.patch.object(
                sys,
                "argv",
                ["run_experiment.py", "--resume", "--profile", "pilot", "--run-id", RUN_ID],
            ),
            contextlib.redirect_stderr(io.StringIO()),
        ):
            with self.assertRaises(SystemExit):
                runner.parse_args()


class PostprocessingGuardTests(unittest.TestCase):
    def test_evaluate_rejects_running_run_before_side_effects(self) -> None:
        with ResumeFixture() as fixture:
            fixture.metadata["status"] = "running"
            fixture.write_metadata()
            output_log = fixture.artifacts / "hidden-scores.jsonl"
            output_log.write_text("preserve this output\n", encoding="utf-8")
            args = argparse.Namespace(
                partition="hidden",
                all_snapshots=False,
                max_stage=None,
            )

            with (
                mock.patch.object(evaluator_runner, "load_config") as load_config,
                mock.patch.object(evaluator_runner, "docker_image_id") as inspect_image,
                mock.patch.object(evaluator_runner, "evaluate_snapshot") as evaluate_snapshot,
            ):
                with self.assertRaisesRegex(runner.ExperimentError, "still running"):
                    evaluator_runner.evaluate_locked(args, RUN_ID, fixture.run_dir)

            load_config.assert_not_called()
            inspect_image.assert_not_called()
            evaluate_snapshot.assert_not_called()
            self.assertEqual(output_log.read_text(encoding="utf-8"), "preserve this output\n")

    def test_summarize_rejects_running_run_before_side_effects(self) -> None:
        with ResumeFixture() as fixture:
            fixture.metadata["status"] = "running"
            fixture.write_metadata()
            report_json = fixture.run_dir / "report.json"
            report_markdown = fixture.run_dir / "report.md"
            report_json.write_text("preserve json\n", encoding="utf-8")
            report_markdown.write_text("preserve markdown\n", encoding="utf-8")

            with mock.patch.object(summarizer, "atomic_write_json") as atomic_write:
                with self.assertRaisesRegex(runner.ExperimentError, "still running"):
                    summarizer.summarize_locked(RUN_ID, fixture.run_dir)

            atomic_write.assert_not_called()
            self.assertEqual(report_json.read_text(encoding="utf-8"), "preserve json\n")
            self.assertEqual(report_markdown.read_text(encoding="utf-8"), "preserve markdown\n")

    def test_evaluate_rejects_held_harness_lock(self) -> None:
        with ResumeFixture() as fixture:
            argv = ["evaluate_run.py", "--run-id", RUN_ID, "--partition", "hidden"]
            with (
                runner.resume_lock(fixture.run_dir),
                mock.patch.object(evaluator_runner, "REPO_ROOT", fixture.root),
                mock.patch.object(sys, "argv", argv),
                mock.patch.object(evaluator_runner, "evaluate_locked") as evaluate_locked,
            ):
                with self.assertRaisesRegex(runner.ExperimentError, "already locked"):
                    evaluator_runner.main()
            evaluate_locked.assert_not_called()

    def test_summarize_rejects_held_harness_lock(self) -> None:
        with ResumeFixture() as fixture:
            argv = ["summarize_run.py", "--run-id", RUN_ID]
            with (
                runner.resume_lock(fixture.run_dir),
                mock.patch.object(summarizer, "REPO_ROOT", fixture.root),
                mock.patch.object(sys, "argv", argv),
                mock.patch.object(summarizer, "summarize_locked") as summarize_locked,
            ):
                with self.assertRaisesRegex(runner.ExperimentError, "already locked"):
                    summarizer.main()
            summarize_locked.assert_not_called()


if __name__ == "__main__":
    unittest.main()
