"""The inference server's configuration, and its agreement with the harness.

The server is configured in config/sglang.env and the harness in
config/defaults.env plus .env. Nothing forces them to agree, and when they
disagree the symptom is not a startup error: it is a batch that runs for hours
against the wrong model, or a conversation that is rejected once it outgrows a
KV pool nobody checked. These tests pin the agreement that `make preflight`
cannot check offline.
"""

from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))


def parse_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        values[key.strip()] = value.strip().strip("'\"")
    return values


def emitted_config() -> dict[str, str]:
    """The YAML the launcher hands to `sglang serve`, as a flat dict."""
    result = subprocess.run(
        [str(ROOT / "scripts" / "sglang_server.sh"), "config"],
        capture_output=True, text=True, check=True,
    )
    values: dict[str, str] = {}
    for line in result.stdout.splitlines():
        if not line.strip() or line.startswith("#") or ":" not in line:
            continue
        key, _, value = line.partition(":")
        values[key.strip()] = value.strip()
    return values


class SglangEnvTests(unittest.TestCase):
    def setUp(self) -> None:
        self.env = parse_env(ROOT / "config" / "sglang.env")

    def test_every_pin_the_launcher_needs_is_present(self) -> None:
        for key in (
            "SGLANG_MODEL_REPO", "SGLANG_SERVED_MODEL_NAME", "SGLANG_HOST",
            "SGLANG_PORT", "SGLANG_CONTEXT_LENGTH", "SGLANG_KV_CACHE_DTYPE",
            "SGLANG_MEM_FRACTION_STATIC", "SGLANG_ATTENTION_BACKEND",
            "SGLANG_MAX_RUNNING_REQUESTS", "SGLANG_CUDA_GRAPH_MAX_BS_DECODE",
            "SGLANG_MAMBA_SSM_DTYPE", "SGLANG_MAMBA_RADIX_CACHE_STRATEGY",
            "SGLANG_REASONING_PARSER", "SGLANG_TOOL_CALL_PARSER",
        ):
            self.assertIn(key, self.env, f"{key} missing from config/sglang.env")

    def test_the_blackwell_pins_are_the_measured_ones(self) -> None:
        """SM120 has no trtllm_mha, and the qwen3_coder template is not the
        hermes one: either wrong value produces a server that runs and is
        silently useless rather than one that fails."""
        self.assertEqual(self.env["SGLANG_ATTENTION_BACKEND"], "flashinfer")
        self.assertEqual(self.env["SGLANG_TOOL_CALL_PARSER"], "qwen3_coder")
        self.assertEqual(self.env["SGLANG_REASONING_PARSER"], "qwen3")

    def test_one_request_at_a_time(self) -> None:
        """The harness runs a single Pi session, and the RTX 5090 cell is
        validated only at this envelope. Raising one without the other is the
        documented way to exhaust the GDN state pool."""
        self.assertEqual(self.env["SGLANG_MAX_RUNNING_REQUESTS"], "1")
        self.assertEqual(self.env["SGLANG_CUDA_GRAPH_MAX_BS_DECODE"], "1")

    def test_loopback_only(self) -> None:
        """Binding beyond loopback exposes a server whose API key is optional;
        that is a deliberate decision, not a default."""
        self.assertEqual(self.env["SGLANG_HOST"], "127.0.0.1")


class LauncherOutputTests(unittest.TestCase):
    def setUp(self) -> None:
        self.config = emitted_config()
        self.env = parse_env(ROOT / "config" / "sglang.env")

    def test_launcher_emits_the_pins(self) -> None:
        self.assertEqual(self.config["served-model-name"], self.env["SGLANG_SERVED_MODEL_NAME"])
        self.assertEqual(self.config["attention-backend"], self.env["SGLANG_ATTENTION_BACKEND"])
        self.assertEqual(self.config["kv-cache-dtype"], self.env["SGLANG_KV_CACHE_DTYPE"])
        self.assertEqual(self.config["max-running-requests"], self.env["SGLANG_MAX_RUNNING_REQUESTS"])
        self.assertEqual(self.config["tool-call-parser"], self.env["SGLANG_TOOL_CALL_PARSER"])

    def test_the_api_key_is_never_printed(self) -> None:
        result = subprocess.run(
            [str(ROOT / "scripts" / "sglang_server.sh"), "config"],
            capture_output=True, text=True, check=True,
        )
        env_file = ROOT / ".env"
        if not env_file.exists():
            self.skipTest(".env absent")
        key = parse_env(env_file).get("LOCAL_API_KEY", "")
        if not key:
            self.skipTest("no LOCAL_API_KEY configured")
        self.assertNotIn(key, result.stdout)
        self.assertIn("api-key: <redacted>", result.stdout)


class HarnessAgreementTests(unittest.TestCase):
    """Checks that need .env, which is not in version control."""

    def setUp(self) -> None:
        env_file = ROOT / ".env"
        if not env_file.exists():
            self.skipTest(".env absent")
        self.dot = parse_env(env_file)
        self.sg = parse_env(ROOT / "config" / "sglang.env")
        if self.dot.get("MODEL_PROVIDER") != "local":
            self.skipTest("MODEL_PROVIDER is not local")

    def test_model_id_matches_the_served_name(self) -> None:
        self.assertEqual(self.dot.get("MODEL_ID"), self.sg["SGLANG_SERVED_MODEL_NAME"])

    def test_base_url_points_at_the_server(self) -> None:
        self.assertIn(f"{self.sg['SGLANG_HOST']}:{self.sg['SGLANG_PORT']}",
                      self.dot.get("LOCAL_BASE_URL", ""))

    def test_context_window_fits_the_servers_ceiling(self) -> None:
        """This is only the declared ceiling; the KV pool can be smaller still,
        which is what preflight checks against the live server."""
        self.assertLessEqual(int(self.dot["LOCAL_CONTEXT_WINDOW"]),
                             int(self.sg["SGLANG_CONTEXT_LENGTH"]))

    def test_context_budget_invariants_still_hold(self) -> None:
        from common import context_budget_problems
        self.assertEqual(context_budget_problems(self.dot), [])


if __name__ == "__main__":
    unittest.main()
