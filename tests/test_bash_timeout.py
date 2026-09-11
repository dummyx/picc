"""The per-command bash cap: configuration helper, guard ledger metrics, and the guard sources."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import common  # noqa: E402
import summarize_run  # noqa: E402
import summarize_study  # noqa: E402

LEDGER = [
    {"event": "blocked_tool_call", "toolName": "bash", "reason": "network/download command is prohibited"},
    {"toolName": "read", "reason": "reads are restricted"},  # pre-cap rows carry no event field
    {"event": "bash_timeout_clamped", "toolName": "bash", "requested": 900, "applied": 120},
    {"event": "bash_timeout_fired", "toolName": "bash", "timeout": 120},
    {"event": "bash_timeout_fired", "toolName": "bash", "timeout": 60},
]


class BashTimeoutConfigTests(unittest.TestCase):
    def test_frozen_configurations_without_the_key_run_uncapped(self) -> None:
        self.assertEqual(common.agent_bash_timeout_seconds({}), 0)

    def test_value_is_an_integer_number_of_seconds(self) -> None:
        self.assertEqual(common.agent_bash_timeout_seconds({"AGENT_BASH_TIMEOUT_SECONDS": "120"}), 120)
        self.assertEqual(common.agent_bash_timeout_seconds({"AGENT_BASH_TIMEOUT_SECONDS": "0"}), 0)

    def test_negative_or_non_integer_values_are_rejected(self) -> None:
        for raw in ("-1", "2.5", "two"):
            with self.assertRaises(common.ExperimentError):
                common.agent_bash_timeout_seconds({"AGENT_BASH_TIMEOUT_SECONDS": raw})

    def test_repository_default_caps_commands_at_two_minutes(self) -> None:
        defaults = common._parse_env_file(REPO_ROOT / "config" / "defaults.env")
        self.assertEqual(common.agent_bash_timeout_seconds(defaults), 120)


class GuardLedgerMetricsTests(unittest.TestCase):
    def ledger(self, rows: list[dict[str, object]]) -> Path:
        directory = Path(tempfile.mkdtemp(prefix="picc-guard-"))
        path = directory / "guard.jsonl"
        path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
        return path

    def test_timeouts_are_counted_apart_from_blocks(self) -> None:
        metrics = summarize_run.collect_guard(self.ledger(LEDGER))
        self.assertEqual(metrics["blocked_calls"], 2)
        self.assertEqual(metrics["tools"], {"bash": 1, "read": 1})
        self.assertEqual(metrics["bash_timeouts_fired"], 2)
        self.assertEqual(metrics["bash_timeouts_clamped"], 1)
        self.assertNotIn("unknown", metrics["reasons"])

    def test_run_report_and_study_summary_compute_the_same_metrics(self) -> None:
        path = self.ledger(LEDGER)
        self.assertEqual(summarize_run.collect_guard(path), summarize_study.guard_event_metrics(path))
        empty = self.ledger([])
        self.assertEqual(summarize_run.collect_guard(empty), summarize_study.guard_event_metrics(empty))

    def test_reports_written_before_the_cap_are_not_stale(self) -> None:
        guard = summarize_study.guard_event_metrics(self.ledger(LEDGER[:2]))
        legacy = {key: guard[key] for key in ("blocked_calls", "reasons", "tools")}
        self.assertFalse(summarize_study.guard_report_is_stale(legacy, guard))
        self.assertTrue(summarize_study.guard_report_is_stale({**legacy, "blocked_calls": 5}, guard))
        self.assertTrue(summarize_study.guard_report_is_stale({"blocked_calls": 2}, guard))
        self.assertTrue(summarize_study.guard_report_is_stale({**guard, "bash_timeouts_fired": 9}, guard))


class GuardSourceTests(unittest.TestCase):
    def test_both_guard_sources_apply_and_log_the_cap(self) -> None:
        for relative in ("pi/extensions/experiment-guard.ts", "studies/runtime/experiment-guard.ts.in"):
            text = (REPO_ROOT / relative).read_text(encoding="utf-8")
            for needle in (
                "process.env.PICC_BASH_TIMEOUT_SECONDS",
                "applyBashTimeout(event.input",
                '"bash_timeout_clamped"',
                '"bash_timeout_fired"',
                'pi.on("tool_result"',
            ):
                self.assertIn(needle, text, relative)


if __name__ == "__main__":
    unittest.main()
