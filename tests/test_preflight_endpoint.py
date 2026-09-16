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

    def test_unreachable_endpoint(self) -> None:
        def fetch(url: str, key: str, timeout: float) -> dict:
            raise OSError("connection refused")

        with mock.patch.object(preflight_endpoint, "fetch_json", fetch):
            status, record = preflight_endpoint.preflight(LOCAL, timeout=1)
        self.assertEqual((status, record["status"]), (3, "unreachable"))


if __name__ == "__main__":
    unittest.main()
