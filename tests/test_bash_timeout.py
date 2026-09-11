"""The bash default timeout: the pinned package, its loading, and the cut-off ledger."""

from __future__ import annotations

import json
import re
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import common  # noqa: E402
import summarize_run  # noqa: E402
import summarize_study  # noqa: E402

PACKAGE = "@cad0p/pi-bash-timeout"
LEDGER = [
    {"event": "blocked_tool_call", "toolName": "bash", "reason": "network/download command is prohibited"},
    {"toolName": "read", "reason": "reads are restricted"},  # rows from before v6 carry no event field
    {"event": "bash_timeout_fired", "toolName": "bash", "timeout": 120},
    {"event": "bash_timeout_fired", "toolName": "bash", "timeout": 60},
]


class PinnedPackageTests(unittest.TestCase):
    def test_image_installs_the_pinned_package_the_settings_load(self) -> None:
        defaults = common._parse_env_file(REPO_ROOT / "config" / "defaults.env")
        self.assertEqual(defaults["BASH_TIMEOUT_PACKAGE"], PACKAGE)
        version = defaults["BASH_TIMEOUT_PACKAGE_VERSION"]
        self.assertRegex(version, r"^\d+\.\d+\.\d+$")
        dockerfile = (REPO_ROOT / "docker" / "Dockerfile").read_text(encoding="utf-8")
        self.assertIn(f"ARG BASH_TIMEOUT_PACKAGE={PACKAGE}\n", dockerfile)
        self.assertIn(f"ARG BASH_TIMEOUT_PACKAGE_VERSION={version}\n", dockerfile)
        # --legacy-peer-deps: without it npm nests a second, floating copy of Pi
        # (446 MB) inside the package, which the extension does not even use.
        self.assertRegex(dockerfile, r'npm install -g --ignore-scripts --legacy-peer-deps "\$\{BASH_TIMEOUT_PACKAGE\}@\$\{BASH_TIMEOUT_PACKAGE_VERSION\}"')
        build = (REPO_ROOT / "scripts" / "build_image.sh").read_text(encoding="utf-8")
        self.assertIn("BASH_TIMEOUT_PACKAGE_VERSION=$BASH_TIMEOUT_PACKAGE_VERSION", build)
        settings = json.loads((REPO_ROOT / "pi" / "settings.json").read_text(encoding="utf-8"))
        self.assertEqual(settings["packages"], [f"/usr/local/lib/node_modules/{PACKAGE}"])

    def test_guards_record_cut_offs_and_do_not_set_timeouts_themselves(self) -> None:
        for relative in ("pi/extensions/experiment-guard.ts", "studies/runtime/experiment-guard.ts.in"):
            text = (REPO_ROOT / relative).read_text(encoding="utf-8")
            self.assertIn('pi.on("tool_result"', text, relative)
            self.assertIn('"bash_timeout_fired"', text, relative)
            self.assertNotRegex(text, r"input\.timeout\s*=", relative)
            self.assertNotIn("PICC_BASH_TIMEOUT_SECONDS", text, relative)


class GuardLedgerMetricsTests(unittest.TestCase):
    def ledger(self, rows: list[dict[str, object]]) -> Path:
        directory = Path(tempfile.mkdtemp(prefix="picc-guard-"))
        path = directory / "guard.jsonl"
        path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
        return path

    def test_cut_offs_are_counted_apart_from_blocks(self) -> None:
        metrics = summarize_run.collect_guard(self.ledger(LEDGER))
        self.assertEqual(metrics["blocked_calls"], 2)
        self.assertEqual(metrics["tools"], {"bash": 1, "read": 1})
        self.assertEqual(metrics["bash_timeouts_fired"], 2)
        self.assertNotIn("unknown", metrics["reasons"])

    def test_run_report_and_study_summary_compute_the_same_metrics(self) -> None:
        path = self.ledger(LEDGER)
        self.assertEqual(summarize_run.collect_guard(path), summarize_study.guard_event_metrics(path))
        empty = self.ledger([])
        self.assertEqual(summarize_run.collect_guard(empty), summarize_study.guard_event_metrics(empty))

    def test_reports_written_before_v6_are_not_stale(self) -> None:
        guard = summarize_study.guard_event_metrics(self.ledger(LEDGER[:2]))
        legacy = {key: guard[key] for key in ("blocked_calls", "reasons", "tools")}
        self.assertFalse(summarize_study.guard_report_is_stale(legacy, guard))
        self.assertTrue(summarize_study.guard_report_is_stale({**legacy, "blocked_calls": 5}, guard))
        self.assertTrue(summarize_study.guard_report_is_stale({"blocked_calls": 2}, guard))
        self.assertTrue(summarize_study.guard_report_is_stale({**guard, "bash_timeouts_fired": 9}, guard))


if __name__ == "__main__":
    unittest.main()
