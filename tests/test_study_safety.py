from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import common  # noqa: E402
import study  # noqa: E402


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def write_partition_manifest(
    source: Path,
    relative_path: object,
    *,
    content: bytes = b"int main(void) { return 0; }\n",
    digest: object | None = None,
    create_file: bool = False,
) -> None:
    if create_file:
        path = source / str(relative_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    write_json(
        source / "manifest.json",
        {
            "schema_version": 1,
            "partition": "test",
            "tests": [
                {
                    "id": "case",
                    "relative_path": relative_path,
                    "stage": 1,
                    "validity": "valid",
                    "family": "case",
                    "sha256": sha256_bytes(content) if digest is None else digest,
                }
            ],
        },
    )


class PartitionContainmentTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="picc-study-safety-")
        self.root = Path(self.temporary.name)
        self.source = self.root / "source"
        self.destination = self.root / "destination"
        self.source.mkdir()

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_valid_nested_file_is_copied_and_verified(self) -> None:
        content = b"int main(void) { return 7; }\n"
        digest = sha256_bytes(content).upper()
        write_partition_manifest(
            self.source,
            "nested/case.c",
            content=content,
            digest=digest,
            create_file=True,
        )

        study.copy_partition(self.source, self.destination)

        copied = self.destination / "nested" / "case.c"
        self.assertEqual(copied.read_bytes(), content)
        copied_manifest = json.loads((self.destination / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(copied_manifest["tests"][0]["sha256"], digest)

    def test_rejects_empty_dot_absolute_and_parent_paths(self) -> None:
        unsafe_paths = [
            "",
            ".",
            "..",
            "../secret.c",
            "nested/../../secret.c",
            str((self.root / "outside.c").resolve()),
        ]
        for relative_path in unsafe_paths:
            with self.subTest(relative_path=relative_path):
                write_partition_manifest(self.source, relative_path)
                with self.assertRaises(study.StudyError):
                    study.copy_partition(self.source, self.destination)

    def test_rejects_source_symlink_that_escapes_partition(self) -> None:
        outside = self.root / "outside.c"
        content = b"outside\n"
        outside.write_bytes(content)
        (self.source / "leak.c").symlink_to(outside)
        write_partition_manifest(
            self.source,
            "leak.c",
            content=content,
            digest=sha256_bytes(content),
        )

        with self.assertRaises(study.StudyError):
            study.copy_partition(self.source, self.destination)
        self.assertFalse((self.destination / "leak.c").exists())

    def test_rejects_manifest_symlink_that_escapes_partition(self) -> None:
        outside_manifest = self.root / "outside-manifest.json"
        write_json(outside_manifest, {"tests": []})
        (self.source / "manifest.json").symlink_to(outside_manifest)

        with self.assertRaises(study.StudyError):
            study.copy_partition(self.source, self.destination)

    def test_rejects_malformed_and_mismatched_digests(self) -> None:
        content = b"content\n"
        for digest in ("0" * 63, "x" * 64, None):
            with self.subTest(digest=digest):
                write_partition_manifest(
                    self.source,
                    "case.c",
                    content=content,
                    digest=digest,
                    create_file=True,
                )
                if digest is None:
                    payload = json.loads((self.source / "manifest.json").read_text(encoding="utf-8"))
                    payload["tests"][0]["sha256"] = None
                    write_json(self.source / "manifest.json", payload)
                with self.assertRaises(study.StudyError):
                    study.copy_partition(self.source, self.destination)

        write_partition_manifest(
            self.source,
            "case.c",
            content=content,
            digest="0" * 64,
            create_file=True,
        )
        with self.assertRaisesRegex(study.StudyError, "SHA-256 mismatch"):
            study.copy_partition(self.source, self.destination)

    def test_verifies_copied_bytes_after_copy(self) -> None:
        content = b"content\n"
        write_partition_manifest(
            self.source,
            "case.c",
            content=content,
            create_file=True,
        )

        def corrupt_copy(_source: Path, target: Path) -> None:
            Path(target).write_bytes(b"corrupted\n")

        with mock.patch.object(study.shutil, "copy2", side_effect=corrupt_copy):
            with self.assertRaisesRegex(study.StudyError, "Copied partition file SHA-256 mismatch"):
                study.copy_partition(self.source, self.destination)


class FrozenEnvironmentTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="picc-study-env-")
        self.root = Path(self.temporary.name)
        (self.root / "config").mkdir()
        self.env_file = self.root / "config" / "defaults.env"
        self.env_file.write_text("BASE=base\n", encoding="utf-8")

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_quotes_values_for_shell_and_python_parsers_without_expansion(self) -> None:
        sentinel = self.root / "should-not-exist"
        values = {
            "STUDY_TEST_DANGEROUS": f"value with spaces # ; $(touch {sentinel}) $HOME",
            "STUDY_TEST_EMPTY": "",
            "STUDY_TEST_SIMPLE": "plain-value",
        }

        study.append_env_overrides(self.env_file, values)

        with (
            mock.patch.object(common, "REPO_ROOT", self.root),
            mock.patch.dict(os.environ, {}, clear=True),
        ):
            parsed = common.load_config()
        for key, value in values.items():
            self.assertEqual(parsed[key], value)

        script = (
            'set -a; source "$1"; '
            'printf "%s\\0%s\\0%s" "$STUDY_TEST_DANGEROUS" "$STUDY_TEST_EMPTY" "$STUDY_TEST_SIMPLE"'
        )
        result = subprocess.run(
            ["bash", "-c", script, "bash", str(self.env_file)],
            check=False,
            capture_output=True,
            env={"PATH": os.environ.get("PATH", "")},
        )
        self.assertEqual(result.returncode, 0, result.stderr.decode())
        self.assertEqual(result.stdout.split(b"\0"), [values[key].encode() for key in (
            "STUDY_TEST_DANGEROUS",
            "STUDY_TEST_EMPTY",
            "STUDY_TEST_SIMPLE",
        )])
        self.assertFalse(sentinel.exists())

    def test_rejects_unsafe_values_before_modifying_file(self) -> None:
        original = self.env_file.read_bytes()
        for value in ("line\nnext", "carriage\rreturn", "single'quote", "null\0byte"):
            with self.subTest(value=value):
                with self.assertRaises(study.StudyError):
                    study.append_env_overrides(self.env_file, {"STUDY_TEST_BAD": value})
                self.assertEqual(self.env_file.read_bytes(), original)


class FrozenExecutionEnvironmentTests(unittest.TestCase):
    def test_host_drift_cannot_override_frozen_config_or_inject_other_secrets(self) -> None:
        with tempfile.TemporaryDirectory(prefix="picc-study-frozen-env-") as temporary:
            root = Path(temporary)
            frozen = {
                "EXPERIMENT_IMAGE": "frozen-image",
                "PILOT_HOURS": "2",
                "MODEL_ID": "frozen-model",
                "MODEL_PROVIDER": "zai",
                "MODEL_THINKING": "max",
            }
            write_json(root / "study-materialization.json", {"effective_config": frozen})
            host = {
                "EXPERIMENT_IMAGE": "host-image",
                "PILOT_HOURS": "99",
                "MODEL_ID": "host-model",
                "MODEL_PROVIDER": "zai-coding-cn",
                "MODEL_THINKING": "off",
                "ZAI_API_KEY": "host-zai-secret",
                "ZAI_CODING_CN_API_KEY": "host-cn-secret",
                "GITHUB_TOKEN": "unrelated-secret",
                "UNRELATED": "preserved",
            }
            current = {
                "ZAI_API_KEY": "current-zai-secret",
                "ZAI_CODING_CN_API_KEY": "current-cn-secret",
            }

            with (
                mock.patch.dict(os.environ, host, clear=True),
                mock.patch.object(study, "load_config", return_value=current),
            ):
                environment = study.safe_environment(root)

            for key, value in frozen.items():
                self.assertEqual(environment[key], value)
            self.assertEqual(environment["ZAI_API_KEY"], "current-zai-secret")
            self.assertNotIn("ZAI_CODING_CN_API_KEY", environment)
            self.assertNotIn("GITHUB_TOKEN", environment)
            self.assertEqual(environment["UNRELATED"], "preserved")


class ConditionValidationSafetyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.study_payload, conditions = study.load_study(ROOT / "studies" / "starter" / "study.json")
        cls.baseline = next(condition for condition in conditions if condition["id"] == "baseline")

    def test_rejects_invalid_budget_values(self) -> None:
        invalid = {
            "pilot_hours": (0, -1, float("nan"), float("inf"), True, "1"),
            "main_hours": (0, -1, float("-inf"), True),
            "pilot_rounds": (0, -1, 1.5, True, "1"),
            "main_round_timeout_minutes": (0, -1, 1.5, True),
            "pilot_max_stage": (0, 11, 1.5, True),
            "main_max_stage": (0, 11, 1.5, True),
        }
        for key, values in invalid.items():
            for value in values:
                with self.subTest(key=key, value=value):
                    condition = study.deep_merge(self.baseline, {"budget": {key: value}})
                    with self.assertRaises(study.StudyError):
                        study.validate_condition(condition, self.study_payload)

    def test_accepts_valid_budget_bounds(self) -> None:
        condition = study.deep_merge(
            self.baseline,
            {
                "budget": {
                    "pilot_hours": 0.5,
                    "pilot_rounds": 1,
                    "pilot_round_timeout_minutes": 1,
                    "pilot_max_stage": 10,
                }
            },
        )
        study.validate_condition(condition, self.study_payload)

    def test_rejects_secret_environment_override_keys(self) -> None:
        for key in ("ZAI_API_KEY", "STUDY_TOKEN", "DB_PASSWORD", "CLIENT_SECRET"):
            with self.subTest(key=key):
                condition = study.deep_merge(
                    self.baseline,
                    {"environment": {"overrides": {key: "secret"}}},
                )
                with self.assertRaisesRegex(study.StudyError, "secret environment override"):
                    study.validate_condition(condition, self.study_payload)

    def test_rejects_environment_values_that_cannot_be_frozen_safely(self) -> None:
        for value in ("single'quote", "line\nnext", "null\0byte", float("nan"), float("inf")):
            with self.subTest(value=value):
                condition = study.deep_merge(
                    self.baseline,
                    {"environment": {"overrides": {"SAFE_VALUE": value}}},
                )
                with self.assertRaisesRegex(
                    study.StudyError,
                    "serialized safely|must be finite",
                ):
                    study.validate_condition(condition, self.study_payload)


class ScheduleRunIdTests(unittest.TestCase):
    def test_run_rejects_nonpositive_replicates(self) -> None:
        for replicate in (0, -1):
            with self.subTest(replicate=replicate):
                args = argparse.Namespace(
                    study=ROOT / "studies" / "starter" / "study.json",
                    replicate=replicate,
                )
                with self.assertRaisesRegex(study.StudyError, "--replicate"):
                    study.command_run(args)

    def test_short_ids_are_readable_and_profile_specific(self) -> None:
        pilot = study.schedule_run_id("picc", "pilot", 1, "baseline")
        main = study.schedule_run_id("picc", "main", 1, "baseline")

        self.assertEqual(pilot, "picc-pilot-r01-baseline")
        self.assertEqual(main, "picc-main-r01-baseline")
        self.assertNotEqual(pilot, main)

    def test_long_ids_are_bounded_deterministic_and_collision_resistant(self) -> None:
        study_id = "s" * 64
        first_condition = "c" * 64
        second_condition = "c" * 63 + "d"

        first = study.schedule_run_id(study_id, "pilot", 1, first_condition)
        repeated = study.schedule_run_id(study_id, "pilot", 1, first_condition)
        second = study.schedule_run_id(study_id, "pilot", 1, second_condition)
        main = study.schedule_run_id(study_id, "main", 1, first_condition)

        self.assertEqual(first, repeated)
        self.assertNotEqual(first, second)
        self.assertNotEqual(first, main)
        for run_id in (first, second, main):
            self.assertLessEqual(len(run_id), study.RUN_ID_MAX_LENGTH)
            self.assertRegex(run_id, r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,95}$")
            self.assertRegex(run_id, r"-[0-9a-f]{16}$")


class MaterializePathSafetyTests(unittest.TestCase):
    def call_materialize(self, repo: Path, *, replace: bool = False) -> None:
        with mock.patch.object(study, "REPO_ROOT", repo):
            study.materialize(Path("unused.json"), {}, {}, "unsafe-run", replace=replace)

    def test_rejects_symlinked_runs_and_materialization_parents(self) -> None:
        with tempfile.TemporaryDirectory(prefix="picc-study-create-path-") as temporary:
            base = Path(temporary)
            repo = base / "repo"
            repo.mkdir()
            outside = base / "outside"
            outside.mkdir()
            (repo / "runs").symlink_to(outside, target_is_directory=True)
            with self.assertRaisesRegex(study.StudyError, "must not be a symlink"):
                self.call_materialize(repo)

        with tempfile.TemporaryDirectory(prefix="picc-study-create-path-") as temporary:
            base = Path(temporary)
            repo = base / "repo"
            (repo / "runs").mkdir(parents=True)
            outside = base / "outside"
            outside.mkdir()
            (repo / "runs" / ".study-materializations").symlink_to(
                outside,
                target_is_directory=True,
            )
            with self.assertRaisesRegex(study.StudyError, "must not be a symlink"):
                self.call_materialize(repo)

    def test_refuses_replacement_when_run_directory_exists(self) -> None:
        with tempfile.TemporaryDirectory(prefix="picc-study-create-run-") as temporary:
            repo = Path(temporary) / "repo"
            (repo / "runs" / "unsafe-run").mkdir(parents=True)
            with self.assertRaisesRegex(study.StudyError, "existing run"):
                self.call_materialize(repo, replace=True)


    def test_failed_materialization_removes_new_partial_tree(self) -> None:
        with tempfile.TemporaryDirectory(prefix="picc-study-create-failure-") as temporary:
            repo = Path(temporary) / "repo"
            parent = repo / "runs" / ".study-materializations"
            parent.mkdir(parents=True)
            target = parent / "retry-run"

            def fail_after_creation(*unused_args: object, **unused_kwargs: object) -> Path:
                target.mkdir()
                (target / "partial.txt").write_text("partial\n", encoding="utf-8")
                raise study.StudyError("injected materialization failure")

            with (
                mock.patch.object(study, "REPO_ROOT", repo),
                mock.patch.object(study, "_materialize_direct", side_effect=fail_after_creation),
            ):
                with self.assertRaisesRegex(study.StudyError, "injected materialization failure"):
                    study.materialize(Path("unused.json"), {}, {}, "retry-run")

            self.assertFalse(target.exists())

    def test_failed_preflight_cleans_materialization_for_same_id_retry(self) -> None:
        with tempfile.TemporaryDirectory(prefix="picc-study-run-retry-") as temporary:
            repo = Path(temporary) / "repo"
            parent = repo / "runs" / ".study-materializations"
            parent.mkdir(parents=True)
            target = parent / "retry-run"
            args = argparse.Namespace(
                study=Path("unused.json"),
                condition="baseline",
                profile="pilot",
                run_id="retry-run",
                replicate=1,
            )

            def fake_materialize(*unused_args: object, **unused_kwargs: object) -> Path:
                target.mkdir()
                (target / "scripts").mkdir()
                return target

            with (
                mock.patch.object(study, "REPO_ROOT", repo),
                mock.patch.object(study, "load_study", return_value=({}, [])),
                mock.patch.object(study, "find_condition", return_value={}),
                mock.patch.object(study, "materialize", side_effect=fake_materialize) as create,
                mock.patch.object(study, "safe_environment", return_value={}),
                mock.patch.object(study, "subprocess_checked", return_value=2),
                mock.patch.object(study, "freeze_run_study_metadata") as freeze,
            ):
                self.assertEqual(study.command_run(args), 2)
                self.assertFalse(target.exists())
                self.assertEqual(study.command_run(args), 2)
                self.assertFalse(target.exists())

            self.assertEqual(create.call_count, 2)
            freeze.assert_not_called()

class MaterializationLookupTests(unittest.TestCase):
    run_id = "study-run"

    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="picc-study-lookup-")
        self.repo = Path(self.temporary.name) / "repo"
        self.run_dir = self.repo / "runs" / self.run_id
        self.materialization = self.repo / "runs" / ".study-materializations" / self.run_id
        self.run_dir.mkdir(parents=True)
        self.materialization.mkdir(parents=True)
        for name in study.MATERIALIZED_HASH_DIRS:
            (self.materialization / name).mkdir(parents=True)

        files = {
            "VERSION": b"test-version\n",
            "config/defaults.env": b"MODEL_PROVIDER=zai\n",
            "docker/Dockerfile": b"FROM scratch\n",
            "scripts/run_experiment.py": b"print('run')\n",
            "pi/settings.json": b"{}\n",
            "prompts/INITIAL.txt": b"initial\n",
            "evaluator/evaluate.py": b"print('evaluate')\n",
            "data/partitions/visible/case.c": b"visible\n",
            "data/partitions/hidden/case.c": b"hidden\n",
            "data/agent-visible/case.c": b"agent visible\n",
        }
        for relative, content in files.items():
            path = self.materialization / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
        self.script = self.materialization / "scripts" / "run_experiment.py"
        self.visible_test = self.materialization / "data" / "partitions" / "visible" / "case.c"

        self.manifest_content = b"release manifest\n"
        self.manifest_digest = sha256_bytes(self.manifest_content)
        (self.materialization / "MANIFEST.sha256").write_bytes(self.manifest_content)
        file_hashes = study.materialized_harness_file_hashes(self.materialization)
        self.record = {
            "schema_version": 1,
            "run_id": self.run_id,
            "study_id": "study",
            "study_sha256": "1" * 64,
            "condition_sha256": "2" * 64,
            "effective_config": {
                "EXPERIMENT_IMAGE": "frozen-image",
                "PILOT_HOURS": "2",
                "MODEL_ID": "frozen-model",
                "MODEL_PROVIDER": "zai",
                "MODEL_THINKING": "max",
            },
            "source_harness": {
                "manifest_sha256": self.manifest_digest,
                "file_hashes": {},
            },
            "materialized_harness": {"file_hashes": file_hashes},
        }
        write_json(self.materialization / "study-materialization.json", self.record)
        write_json(self.run_dir / "study-control" / "materialization.json", self.record)
        self.sidecar = {
            **self.record,
            "materialization_root": f"runs/.study-materializations/{self.run_id}",
            "frozen_at": "test",
        }
        self.write_sidecar()

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def write_sidecar(self) -> None:
        write_json(self.run_dir / "study-metadata.json", self.sidecar)

    def lookup(self) -> tuple[Path, dict[str, object]]:
        with mock.patch.object(study, "REPO_ROOT", self.repo):
            return study.study_for_run(self.run_id)

    def test_accepts_expected_materialization_and_manifest(self) -> None:
        root, payload = self.lookup()
        self.assertEqual(root, self.materialization.resolve())
        self.assertEqual(payload["run_id"], self.run_id)

    def test_rejects_mutated_script_evaluator_and_test_bytes(self) -> None:
        paths = [
            self.script,
            self.materialization / "evaluator" / "evaluate.py",
            self.visible_test,
        ]
        for path in paths:
            with self.subTest(path=path.relative_to(self.materialization)):
                original = path.read_bytes()
                path.write_bytes(original + b"tampered\n")
                with self.assertRaisesRegex(study.StudyError, "materialized harness files changed"):
                    self.lookup()
                path.write_bytes(original)
                self.lookup()

    def test_rejects_sidecar_path_traversal_absolute_and_alias_paths(self) -> None:
        unsafe = [
            "../../outside",
            str(self.materialization.resolve()),
            f"runs/.study-materializations/{self.run_id}/../{self.run_id}",
        ]
        for raw_root in unsafe:
            with self.subTest(raw_root=raw_root):
                self.sidecar["materialization_root"] = raw_root
                self.write_sidecar()
                with self.assertRaises(study.StudyError):
                    self.lookup()

    def test_rejects_symlinked_materialization_root(self) -> None:
        outside = self.repo.parent / "outside-materialization"
        shutil.copytree(self.materialization, outside)
        shutil.rmtree(self.materialization)
        self.materialization.symlink_to(outside, target_is_directory=True)

        with self.assertRaisesRegex(study.StudyError, "must not be a symlink"):
            self.lookup()

    def test_rejects_symlinked_materialization_parent(self) -> None:
        parent = self.materialization.parent
        outside_parent = self.repo.parent / "outside-materializations"
        shutil.copytree(parent, outside_parent)
        shutil.rmtree(parent)
        parent.symlink_to(outside_parent, target_is_directory=True)

        with self.assertRaisesRegex(study.StudyError, "must not be a symlink"):
            self.lookup()

    def test_rejects_tampered_or_symlinked_frozen_manifest(self) -> None:
        manifest = self.materialization / "MANIFEST.sha256"
        manifest.write_bytes(b"tampered\n")
        with self.assertRaisesRegex(study.StudyError, "SHA-256"):
            self.lookup()

        manifest.unlink()
        outside = self.repo.parent / "outside-manifest"
        outside.write_bytes(self.manifest_content)
        manifest.symlink_to(outside)
        with self.assertRaisesRegex(study.StudyError, "must not be a symlink"):
            self.lookup()

    def test_rejects_sidecar_provenance_drift(self) -> None:
        self.sidecar["source_harness"] = {
            "manifest_sha256": "0" * 64,
            "file_hashes": {},
        }
        self.write_sidecar()

        with self.assertRaisesRegex(study.StudyError, "disagrees"):
            self.lookup()


class RuntimeCopyTests(unittest.TestCase):
    def test_release_manifest_is_required_and_copied(self) -> None:
        with tempfile.TemporaryDirectory(prefix="picc-study-runtime-") as temporary:
            base = Path(temporary)
            repo = base / "repo"
            repo.mkdir()
            for name in study.RUNTIME_COPY_DIRS:
                (repo / name).mkdir()
            (repo / "runs").mkdir()
            (repo / "VERSION").write_text("test\n", encoding="utf-8")
            manifest = b"manifest\n"
            (repo / "MANIFEST.sha256").write_bytes(manifest)
            destination = base / "materialized"

            with mock.patch.object(study, "REPO_ROOT", repo):
                study.copy_runtime_root(destination)

            self.assertEqual((destination / "MANIFEST.sha256").read_bytes(), manifest)
            self.assertTrue((destination / "runs").is_symlink())


if __name__ == "__main__":
    unittest.main()
