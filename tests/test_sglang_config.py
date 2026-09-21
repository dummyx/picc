"""The inference server's configuration, and its agreement with the harness.

The server is configured in config/sglang.env and the harness in
config/defaults.env plus .env. Nothing forces them to agree, and when they
disagree the symptom is not a startup error: it is a batch that runs for hours
against the wrong model, or a conversation that is rejected once it outgrows a
KV pool nobody checked. These tests pin the agreement that `make preflight`
cannot check offline.
"""

from __future__ import annotations

import json
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



class ThinkingBudgetAgreementTests(unittest.TestCase):
    """The budget needs both halves: the harness sends it, the server enforces
    it. Either one alone is silent -- the request is accepted and the budget
    is ignored -- so the mismatch has to be caught here."""

    def setUp(self) -> None:
        env_file = ROOT / ".env"
        if not env_file.exists():
            self.skipTest(".env absent")
        self.dot = parse_env(env_file)
        self.sg = parse_env(ROOT / "config" / "sglang.env")

    def test_budget_and_enforcement_are_set_together(self) -> None:
        budget = self.dot.get("LOCAL_THINKING_BUDGET", "").strip()
        strict = self.sg.get("SGLANG_ENABLE_STRICT_THINKING", "0").strip()
        if budget and strict != "1":
            self.fail(
                f"LOCAL_THINKING_BUDGET={budget} is set but the server is launched without "
                "--enable-strict-thinking (SGLANG_ENABLE_STRICT_THINKING=0), so it is ignored"
            )
        if strict == "1" and not budget:
            self.fail(
                "SGLANG_ENABLE_STRICT_THINKING=1 but no LOCAL_THINKING_BUDGET is set, "
                "so nothing bounds the reasoning"
            )

    def test_the_launcher_emits_the_enforcement_flag(self) -> None:
        if self.sg.get("SGLANG_ENABLE_STRICT_THINKING", "0").strip() != "1":
            self.skipTest("strict thinking off")
        self.assertEqual(emitted_config().get("enable-strict-thinking"), "true")



class StreamIdleTimeoutTests(unittest.TestCase):
    """Pi kills a response stream that goes quiet for httpIdleTimeoutMs.

    Its default is 300000. That is fine while the model is emitting text --
    measured gaps between chunks are 0.1 s -- but SGLang's qwen3_coder parser
    buffers a whole tool call rather than streaming it, so a `write` of a
    large file sends nothing at all until the call is complete. One measured
    tool call went 223 s without a chunk; at ~68 tokens/s against a
    32768-token output cap a full-length write goes well past 300 s.

    When it fires, the reply arrives with the tool call's `path` and no
    `content`, stopReason "error", errorMessage "terminated". Pi retries, so
    the run survives and merely loses the time -- which is why this needs a
    test rather than being noticed. The llama.cpp batches never saw it: 303
    replies across three v15 runs, zero errors.
    """

    def test_idle_timeout_clears_a_full_length_tool_call(self) -> None:
        settings = json.loads((ROOT / "pi" / "settings.json").read_text(encoding="utf-8"))
        idle = settings.get("httpIdleTimeoutMs")
        self.assertIsNotNone(idle, "httpIdleTimeoutMs is unset, so Pi's 300000 default applies")
        if idle == 0:
            return  # disabled entirely, which also cannot fire

        dot = parse_env(ROOT / ".env") if (ROOT / ".env").exists() else {}
        output = int(dot.get("LOCAL_MAX_OUTPUT") or 32768)
        # The slowest generation rate this endpoint has been measured at.
        slowest_tokens_per_second = 60
        needed_ms = 1000 * output / slowest_tokens_per_second
        self.assertGreater(
            idle, needed_ms,
            f"httpIdleTimeoutMs={idle} is below the {needed_ms:.0f} ms a full "
            f"{output}-token reply takes at {slowest_tokens_per_second} tokens/s. A buffered "
            f"tool call that long would be cut off mid-write.",
        )


if __name__ == "__main__":
    unittest.main()
