#!/usr/bin/env python3
"""Tests for the optional local OpenAI-compatible provider configuration."""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import common  # noqa: E402
import run_experiment as runner  # noqa: E402
import study  # noqa: E402


LOCAL_MODEL_ID = "unsloth/Qwen3.8-27B-GGUF:UD-Q4_K_XL"


def local_config(**overrides: str) -> dict[str, str]:
    config = {
        "EXPERIMENT_IMAGE": "picc-test:0.1",
        "ZAI_PROVIDER": "local",
        "ZAI_MODEL": LOCAL_MODEL_ID,
        "ZAI_THINKING": "high",
        "LOCAL_BASE_URL": "http://host.docker.internal:8080/v1",
        "LOCAL_API": "openai-completions",
        "LOCAL_CONTEXT_WINDOW": "131072",
        "LOCAL_MAX_OUTPUT": "32768",
        "LOCAL_REASONING": "1",
        "LOCAL_THINKING_FORMAT": "qwen-chat-template",
        "LOCAL_SAMPLING_PARAMS": "",
        "LOCAL_COMPAT": '{"supportsDeveloperRole": false, "maxTokensField": "max_tokens"}',
    }
    config.update(overrides)
    return config


class ApiKeyResolutionTests(unittest.TestCase):
    def test_local_provider_defaults_to_placeholder_key(self) -> None:
        variable, value = common.api_key_for(local_config())
        self.assertEqual(variable, "LOCAL_API_KEY")
        self.assertEqual(value, common.LOCAL_API_KEY_PLACEHOLDER)

    def test_local_provider_uses_configured_key(self) -> None:
        variable, value = common.api_key_for(local_config(LOCAL_API_KEY="server-secret"))
        self.assertEqual((variable, value), ("LOCAL_API_KEY", "server-secret"))

    def test_hosted_providers_still_require_their_key(self) -> None:
        with self.assertRaisesRegex(common.ExperimentError, "ZAI_API_KEY"):
            common.api_key_for({"ZAI_PROVIDER": "zai"})
        variable, value = common.api_key_for({"ZAI_PROVIDER": "zai", "ZAI_API_KEY": "k"})
        self.assertEqual((variable, value), ("ZAI_API_KEY", "k"))

    def test_unknown_provider_is_rejected(self) -> None:
        with self.assertRaisesRegex(common.ExperimentError, "Unsupported provider"):
            common.api_key_for({"ZAI_PROVIDER": "other"})


class LocalProviderResolutionTests(unittest.TestCase):
    def test_rejects_hosted_default_model_id(self) -> None:
        for model in ("", "glm-5.2"):
            with self.subTest(model=model):
                with self.assertRaisesRegex(common.ExperimentError, "ZAI_MODEL"):
                    common.resolve_local_provider(local_config(ZAI_MODEL=model))

    def test_rejects_non_http_base_url(self) -> None:
        with self.assertRaisesRegex(common.ExperimentError, "LOCAL_BASE_URL"):
            common.resolve_local_provider(local_config(LOCAL_BASE_URL="host.docker.internal:8080"))

    def test_rejects_unknown_api_type(self) -> None:
        with self.assertRaisesRegex(common.ExperimentError, "LOCAL_API"):
            common.resolve_local_provider(local_config(LOCAL_API="grpc"))

    def test_rejects_nonpositive_window_and_tokens(self) -> None:
        with self.assertRaisesRegex(common.ExperimentError, "positive"):
            common.resolve_local_provider(local_config(LOCAL_CONTEXT_WINDOW="0"))
        with self.assertRaisesRegex(common.ExperimentError, "must be an integer"):
            common.resolve_local_provider(local_config(LOCAL_MAX_OUTPUT="many"))

    def test_rejects_malformed_json_knobs(self) -> None:
        with self.assertRaisesRegex(common.ExperimentError, "LOCAL_SAMPLING_PARAMS"):
            common.resolve_local_provider(local_config(LOCAL_SAMPLING_PARAMS="{not json"))
        with self.assertRaisesRegex(common.ExperimentError, "LOCAL_COMPAT"):
            common.resolve_local_provider(local_config(LOCAL_COMPAT='["not", "object"]'))

    def test_rejects_invalid_boolean(self) -> None:
        with self.assertRaisesRegex(common.ExperimentError, "LOCAL_REASONING"):
            common.resolve_local_provider(local_config(LOCAL_REASONING="maybe"))

    def test_requires_local_provider_selection(self) -> None:
        with self.assertRaisesRegex(common.ExperimentError, "ZAI_PROVIDER=local"):
            common.resolve_local_provider(local_config(ZAI_PROVIDER="zai"))


class ModelsJsonGenerationTests(unittest.TestCase):
    def test_declares_single_frozen_provider_and_model(self) -> None:
        payload = common.local_models_json(
            local_config(LOCAL_SAMPLING_PARAMS='{"temperature": 0.6, "top_p": 0.95}')
        )
        provider = payload["providers"]["local"]
        self.assertEqual(provider["baseUrl"], "http://host.docker.internal:8080/v1")
        self.assertEqual(provider["api"], "openai-completions")
        self.assertEqual(provider["apiKey"], "$LOCAL_API_KEY")
        self.assertEqual(provider["compat"]["supportsDeveloperRole"], False)
        self.assertEqual(provider["compat"]["thinkingFormat"], "qwen-chat-template")
        (model,) = provider["models"]
        self.assertEqual(model["id"], LOCAL_MODEL_ID)
        self.assertEqual(model["contextWindow"], 131072)
        self.assertEqual(model["maxTokens"], 32768)
        self.assertTrue(model["reasoning"])
        self.assertEqual(model["samplingParams"], {"temperature": 0.6, "top_p": 0.95})
        self.assertEqual(
            set(model["thinkingLevelMap"]), {"minimal", "low", "medium", "high", "xhigh", "max"}
        )

    def test_explicit_compat_thinking_format_wins(self) -> None:
        payload = common.local_models_json(
            local_config(LOCAL_COMPAT='{"thinkingFormat": "qwen"}', LOCAL_THINKING_FORMAT="qwen-chat-template")
        )
        self.assertEqual(payload["providers"]["local"]["compat"]["thinkingFormat"], "qwen")

    def test_non_reasoning_model_omits_thinking_configuration(self) -> None:
        payload = common.local_models_json(local_config(LOCAL_REASONING="0"))
        (model,) = payload["providers"]["local"]["models"]
        self.assertFalse(model["reasoning"])
        self.assertNotIn("thinkingLevelMap", model)
        self.assertNotIn("samplingParams", model)

    def test_written_file_is_deterministic(self) -> None:
        config = local_config()
        with tempfile.TemporaryDirectory(prefix="picc-local-test-") as temporary:
            first = common.write_local_models_json(config, Path(temporary) / "a")
            second = common.write_local_models_json(config, Path(temporary) / "b")
            self.assertEqual(first.read_bytes(), second.read_bytes())
            self.assertEqual(json.loads(first.read_text()), common.local_models_json(config))


class ControlFileTests(unittest.TestCase):
    def test_local_run_control_includes_models_json(self) -> None:
        with tempfile.TemporaryDirectory(prefix="picc-local-control-") as temporary:
            control = runner.copy_control_files(Path(temporary) / "run", local_config())
            payload = json.loads((control / "pi" / "models.json").read_text(encoding="utf-8"))
            self.assertEqual(payload["providers"]["local"]["models"][0]["id"], LOCAL_MODEL_ID)
            self.assertIn("pi/models.json", runner.prompt_hashes(control))

    def test_hosted_run_control_has_no_models_json(self) -> None:
        with tempfile.TemporaryDirectory(prefix="picc-hosted-control-") as temporary:
            control = runner.copy_control_files(
                Path(temporary) / "run", {"ZAI_PROVIDER": "zai", "ZAI_MODEL": "glm-5.2"}
            )
            self.assertFalse((control / "pi" / "models.json").exists())


class FrozenResumeConfigTests(unittest.TestCase):
    def metadata(self) -> dict[str, object]:
        frozen = local_config(LOCAL_SAMPLING_PARAMS='{"temperature": 0.6}')
        model = {
            "provider": "local",
            "id": LOCAL_MODEL_ID,
            "thinking": "high",
            "serving_revision": "self-hosted endpoint",
        }
        model.update(common.local_model_metadata(frozen))
        return {
            "configuration": frozen,
            "model": model,
            "docker_image": {"name": frozen["EXPERIMENT_IMAGE"], "id": "sha256:test"},
        }

    def test_matching_local_metadata_passes_and_reinjects_secret(self) -> None:
        config = runner.frozen_resume_config(self.metadata(), {"LOCAL_API_KEY": "server-secret"})
        self.assertEqual(config["LOCAL_API_KEY"], "server-secret")
        self.assertEqual(config["ZAI_MODEL"], LOCAL_MODEL_ID)

    def test_missing_local_secret_is_allowed(self) -> None:
        config = runner.frozen_resume_config(self.metadata(), {})
        self.assertNotIn("LOCAL_API_KEY", config)

    def test_tampered_endpoint_metadata_is_rejected(self) -> None:
        metadata = self.metadata()
        metadata["model"]["base_url"] = "http://elsewhere:9999/v1"
        with self.assertRaisesRegex(runner.ExperimentError, "base_url"):
            runner.frozen_resume_config(metadata, {})

    def test_tampered_frozen_shape_is_rejected(self) -> None:
        metadata = self.metadata()
        metadata["configuration"]["LOCAL_CONTEXT_WINDOW"] = "65536"
        with self.assertRaisesRegex(runner.ExperimentError, "context_window"):
            runner.frozen_resume_config(metadata, {})

    def test_invalid_frozen_local_configuration_is_reported(self) -> None:
        metadata = self.metadata()
        metadata["configuration"]["LOCAL_BASE_URL"] = "not-a-url"
        with self.assertRaisesRegex(runner.ExperimentError, "Frozen local-endpoint configuration"):
            runner.frozen_resume_config(metadata, {})


class StudyEnvironmentTests(unittest.TestCase):
    def test_local_provider_injects_only_the_local_secret(self) -> None:
        with tempfile.TemporaryDirectory(prefix="picc-study-local-env-") as temporary:
            root = Path(temporary)
            frozen = {key: value for key, value in local_config().items()}
            (root / "study-materialization.json").write_text(
                json.dumps({"effective_config": frozen}), encoding="utf-8"
            )
            host = {
                "ZAI_API_KEY": "host-zai-secret",
                "LOCAL_API_KEY": "host-local-secret",
                "UNRELATED": "preserved",
            }
            current = {"LOCAL_API_KEY": "current-local-secret", "ZAI_API_KEY": "current-zai-secret"}
            with (
                mock.patch.dict(os.environ, host, clear=True),
                mock.patch.object(study, "load_config", return_value=current),
            ):
                environment = study.safe_environment(root)
        self.assertEqual(environment["LOCAL_API_KEY"], "current-local-secret")
        self.assertNotIn("ZAI_API_KEY", environment)
        self.assertEqual(environment["ZAI_PROVIDER"], "local")
        self.assertEqual(environment["UNRELATED"], "preserved")

    def test_local_provider_without_secret_still_freezes_environment(self) -> None:
        with tempfile.TemporaryDirectory(prefix="picc-study-local-nokey-") as temporary:
            root = Path(temporary)
            (root / "study-materialization.json").write_text(
                json.dumps({"effective_config": local_config()}), encoding="utf-8"
            )
            with (
                mock.patch.dict(os.environ, {}, clear=True),
                mock.patch.object(study, "load_config", return_value={}),
            ):
                environment = study.safe_environment(root)
        self.assertNotIn("LOCAL_API_KEY", environment)
        self.assertEqual(environment["ZAI_MODEL"], LOCAL_MODEL_ID)


if __name__ == "__main__":
    unittest.main()
