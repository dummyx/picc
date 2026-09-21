from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import preflight_endpoint  # noqa: E402

LOCAL = {
    "MODEL_PROVIDER": "local",
    "MODEL_ID": "vendor/model",
    "LOCAL_BASE_URL": "http://127.0.0.1:4545/v1",
    "LOCAL_API_KEY": "k",
}


class PreflightTests(unittest.TestCase):
    def fake_fetch(self, alias: str = "vendor/model", path: str = "/models/model.gguf"):
        def fetch(url: str, key: str, timeout: float) -> dict:
            if url.endswith("/health"):
                return {"status": "ok"}
            return {"model_alias": alias, "model_path": path, "total_slots": 4, "build_info": "b1-test"}

        return fetch

    def test_endpoint_root_strips_v1(self) -> None:
        self.assertEqual(preflight_endpoint.endpoint_root("http://h:1/v1"), "http://h:1")
        self.assertEqual(preflight_endpoint.endpoint_root("http://h:1/"), "http://h:1")

    def test_hosted_provider_has_nothing_to_verify(self) -> None:
        status, record = preflight_endpoint.preflight({"MODEL_PROVIDER": "zai", "MODEL_ID": "m"}, timeout=1)
        self.assertEqual((status, record["status"]), (0, "not_applicable"))

    def test_matching_alias_verifies_and_records_metadata(self) -> None:
        with mock.patch.object(preflight_endpoint, "fetch_json", self.fake_fetch()):
            status, record = preflight_endpoint.preflight(LOCAL, timeout=1)
        self.assertEqual((status, record["status"]), (0, "verified"))
        self.assertEqual(record["health"], "ok")
        self.assertEqual(record["served_model_alias"], "vendor/model")
        self.assertEqual(record["served_model_path"], "/models/model.gguf")
        self.assertEqual(record["server_total_slots"], 4)
        self.assertEqual(record["server_build"], "b1-test")

    def test_wrong_alias_is_a_mismatch(self) -> None:
        with mock.patch.object(preflight_endpoint, "fetch_json", self.fake_fetch(alias="other/model")):
            status, record = preflight_endpoint.preflight(LOCAL, timeout=1)
        self.assertEqual((status, record["status"]), (2, "mismatch"))
        self.assertTrue(any("alias" in problem for problem in record["problems"]))

    def test_missing_alias_is_unverifiable(self) -> None:
        with mock.patch.object(preflight_endpoint, "fetch_json", self.fake_fetch(alias="")):
            status, record = preflight_endpoint.preflight(LOCAL, timeout=1)
        self.assertEqual((status, record["status"]), (3, "unverifiable"))

    def test_model_path_is_optional(self) -> None:
        with mock.patch.object(preflight_endpoint, "fetch_json", self.fake_fetch(path="")):
            status, record = preflight_endpoint.preflight(LOCAL, timeout=1)
        self.assertEqual((status, record["status"]), (0, "verified"))
        self.assertEqual(record["served_model_path"], "")

    def sglang_fetch(
        self,
        served: str = "vendor/model",
        *,
        context_length: int | None = 131072,
        max_total: int | None = 131072,
    ):
        """An SGLang endpoint: /props 404s, /get_model_info identifies it."""

        def fetch(url: str, key: str, timeout: float) -> dict:
            if url.endswith("/health"):
                raise ValueError("empty body")
            if url.endswith("/props"):
                raise OSError("404 Not Found")
            if url.endswith("/get_model_info"):
                return {
                    "model_path": "/models/" + served,
                    "served_model_name": served,
                    "tokenizer_path": "/models/" + served,
                    "is_generation": True,
                }
            return {
                "context_length": context_length,
                "max_total_num_tokens": max_total,
                "max_running_requests": 1,
                "version": "0.5.19",
                "server_args": {"attention_backend": "flashinfer", "kv_cache_dtype": "fp8_e4m3"},
            }

        return fetch

    def test_sglang_endpoint_verifies(self) -> None:
        config = dict(LOCAL, LOCAL_CONTEXT_WINDOW="131072")
        with mock.patch.object(preflight_endpoint, "fetch_json", self.sglang_fetch()):
            status, record = preflight_endpoint.preflight(config, timeout=1)
        self.assertEqual((status, record["status"]), (0, "verified"))
        self.assertEqual(record["server_kind"], "sglang")
        self.assertEqual(record["served_model_alias"], "vendor/model")
        self.assertEqual(record["server_attention_backend"], "flashinfer")
        self.assertEqual(record["server_kv_cache_dtype"], "fp8_e4m3")
        self.assertEqual(record["server_n_ctx"], 131072)

    def test_sglang_wrong_model_is_a_mismatch(self) -> None:
        with mock.patch.object(preflight_endpoint, "fetch_json", self.sglang_fetch(served="other/model")):
            status, record = preflight_endpoint.preflight(LOCAL, timeout=1)
        self.assertEqual((status, record["status"]), (2, "mismatch"))

    def test_kv_pool_smaller_than_declared_window_is_refused(self) -> None:
        """The failure SGLang introduces: it advertises the launch flag's
        context length but sizes its KV pool from leftover VRAM."""
        config = dict(LOCAL, LOCAL_CONTEXT_WINDOW="131072")
        fetch = self.sglang_fetch(context_length=131072, max_total=97280)
        with mock.patch.object(preflight_endpoint, "fetch_json", fetch):
            status, record = preflight_endpoint.preflight(config, timeout=1)
        self.assertEqual((status, record["status"]), (2, "context_too_small"))
        self.assertIn("97280", record["problems"][0])

    def test_window_within_the_pool_is_fine(self) -> None:
        config = dict(LOCAL, LOCAL_CONTEXT_WINDOW="65536")
        fetch = self.sglang_fetch(context_length=131072, max_total=97280)
        with mock.patch.object(preflight_endpoint, "fetch_json", fetch):
            status, record = preflight_endpoint.preflight(config, timeout=1)
        self.assertEqual((status, record["status"]), (0, "verified"))
        self.assertEqual(record["server_n_ctx"], 97280)

    def test_llama_cpp_short_context_is_refused_too(self) -> None:
        def fetch(url: str, key: str, timeout: float) -> dict:
            if url.endswith("/health"):
                return {"status": "ok"}
            return {
                "model_alias": "vendor/model",
                "model_path": "/models/model.gguf",
                "default_generation_settings": {"n_ctx": 32768},
            }

        config = dict(LOCAL, LOCAL_CONTEXT_WINDOW="131072")
        with mock.patch.object(preflight_endpoint, "fetch_json", fetch):
            status, record = preflight_endpoint.preflight(config, timeout=1)
        self.assertEqual((status, record["status"]), (2, "context_too_small"))

    def test_unreachable_endpoint(self) -> None:
        def fetch(url: str, key: str, timeout: float) -> dict:
            raise OSError("connection refused")

        with mock.patch.object(preflight_endpoint, "fetch_json", fetch):
            status, record = preflight_endpoint.preflight(LOCAL, timeout=1)
        self.assertEqual((status, record["status"]), (3, "unreachable"))


if __name__ == "__main__":
    unittest.main()
