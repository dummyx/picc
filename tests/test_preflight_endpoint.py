from __future__ import annotations

import json
import sys
import tempfile
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
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="picc-preflight-")
        self.root = Path(self.temporary.name)
        self.model = self.root / "model.gguf"
        self.model.write_bytes(b"weights")
        self.digest = preflight_endpoint.hashlib.sha256(b"weights").hexdigest()
        self.cache_patch = mock.patch.object(preflight_endpoint, "DIGEST_CACHE", self.root / "cache.json")
        self.cache_patch.start()

    def tearDown(self) -> None:
        self.cache_patch.stop()
        self.temporary.cleanup()

    def fake_fetch(self, alias: str = "vendor/model", path: str | None = None):
        served = self.model if path is None else path

        def fetch(url: str, key: str, timeout: float) -> dict:
            if url.endswith("/health"):
                return {"status": "ok"}
            return {"model_alias": alias, "model_path": str(served), "total_slots": 4, "build_info": "b1-test"}

        return fetch

    def test_endpoint_root_strips_v1(self) -> None:
        self.assertEqual(preflight_endpoint.endpoint_root("http://h:1/v1"), "http://h:1")
        self.assertEqual(preflight_endpoint.endpoint_root("http://h:1/"), "http://h:1")

    def test_hosted_provider_has_nothing_to_verify(self) -> None:
        status, record = preflight_endpoint.preflight({"MODEL_PROVIDER": "zai", "MODEL_ID": "m"}, expect_sha256=None, skip_hash=False, timeout=1)
        self.assertEqual((status, record["status"]), (0, "not_applicable"))

    def test_matching_digest_verifies_and_caches(self) -> None:
        config = {**LOCAL, "LOCAL_MODEL_SHA256": self.digest}
        with mock.patch.object(preflight_endpoint, "fetch_json", self.fake_fetch()):
            status, record = preflight_endpoint.preflight(config, expect_sha256=None, skip_hash=False, timeout=1)
        self.assertEqual((status, record["status"]), (0, "verified"))
        self.assertEqual(record["served_sha256"], self.digest)
        self.assertEqual(record["server_build"], "b1-test")
        cache = json.loads((self.root / "cache.json").read_text(encoding="utf-8"))
        self.assertIn(self.digest, cache.values())
        with mock.patch.object(preflight_endpoint.hashlib, "sha256", side_effect=AssertionError("must hit the cache")):
            self.assertEqual(preflight_endpoint.cached_digest(self.model), self.digest)

    def test_wrong_digest_or_alias_is_a_mismatch(self) -> None:
        config = {**LOCAL, "LOCAL_MODEL_SHA256": "0" * 64}
        with mock.patch.object(preflight_endpoint, "fetch_json", self.fake_fetch()):
            status, record = preflight_endpoint.preflight(config, expect_sha256=None, skip_hash=False, timeout=1)
        self.assertEqual((status, record["status"]), (2, "mismatch"))
        self.assertTrue(any("SHA-256" in problem for problem in record["problems"]))
        with mock.patch.object(preflight_endpoint, "fetch_json", self.fake_fetch(alias="other/model")):
            status, record = preflight_endpoint.preflight({**LOCAL, "LOCAL_MODEL_SHA256": self.digest}, expect_sha256=None, skip_hash=False, timeout=1)
        self.assertEqual(status, 2)
        self.assertTrue(any("alias" in problem for problem in record["problems"]))

    def test_unpinned_digest_is_recorded_not_verified(self) -> None:
        with mock.patch.object(preflight_endpoint, "fetch_json", self.fake_fetch()):
            status, record = preflight_endpoint.preflight(dict(LOCAL), expect_sha256=None, skip_hash=False, timeout=1)
        self.assertEqual((status, record["status"]), (0, "recorded"))

    def test_unreachable_endpoint(self) -> None:
        def fetch(url: str, key: str, timeout: float) -> dict:
            raise OSError("connection refused")

        with mock.patch.object(preflight_endpoint, "fetch_json", fetch):
            status, record = preflight_endpoint.preflight(dict(LOCAL), expect_sha256=None, skip_hash=False, timeout=1)
        self.assertEqual((status, record["status"]), (3, "unreachable"))


if __name__ == "__main__":
    unittest.main()
