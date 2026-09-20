"""The bound on Pi's compaction request, and the harness check that it loaded.

Pi's summarization serializer truncates tool results and nothing else, so a
reasoning model's thinking blocks and a `write` call's file body reach the
summarization request whole. That request outgrew the context window in runs
from v10 on (132k-401k tokens against 131072) and length-stopped the turn-prefix
summary in v6-v9. pi/extensions/compaction-bound.ts caps what goes in and turns
thinking off for that one call.

The extension's own logic is exercised in the pinned image by
scripts/smoke_compaction.sh; these tests cover the wiring around it.
"""
import json
import shutil
import sys
import unittest
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import run_experiment  # noqa: E402
import study  # noqa: E402

EXTENSION = ROOT / "pi" / "extensions" / "compaction-bound.ts"


class CompactionExtensionTest(unittest.TestCase):
    def setUp(self) -> None:
        self.source = EXTENSION.read_text(encoding="utf-8")

    def test_subscribes_and_announces_itself(self) -> None:
        self.assertIn('pi.on("session_before_compact"', self.source)
        self.assertIn("export default function", self.source)
        self.assertIn('appendEvent({ event: "compaction_bound_loaded" })', self.source)

    def test_summarization_call_does_not_think(self) -> None:
        # The summary shares one token budget with the thinking that precedes
        # it; a thinking model spends the budget and stops on length, and Pi
        # refuses a length-stopped summary. v6-v9 lost 12 compactions that way.
        self.assertIn('"off",', self.source)

    def test_hands_back_to_pi_rather_than_failing_compaction(self) -> None:
        # Returning nothing runs Pi's default path. Throwing here would fail the
        # compaction outright, which is the outcome being fixed.
        self.assertNotIn("throw new Error", self.source)


class MaterializationTest(unittest.TestCase):
    def test_every_materialization_carries_the_extension(self) -> None:
        path = ROOT / "studies" / "sql" / "study.json"
        payload, conditions = study.load_study(path)
        condition = conditions[0]
        run_id = f"unit-compaction-{uuid.uuid4().hex}"
        root = ROOT / "runs" / ".study-materializations" / run_id
        self.addCleanup(shutil.rmtree, root, ignore_errors=True)
        study.materialize(path, payload, condition, run_id)
        rendered = root / "pi" / "extensions" / "compaction-bound.ts"
        self.assertTrue(rendered.is_file())
        self.assertEqual(rendered.read_text(encoding="utf-8"), EXTENSION.read_text(encoding="utf-8"))


class LoadCheckTest(unittest.TestCase):
    def setUp(self) -> None:
        self.artifacts = Path(
            ROOT / "runs" / ".study-materializations" / f"unit-loadcheck-{uuid.uuid4().hex}"
        )
        self.artifacts.mkdir(parents=True)
        self.addCleanup(shutil.rmtree, self.artifacts, ignore_errors=True)
        self.events = self.artifacts / "round-000.jsonl"

    def test_accepts_a_round_whose_extension_logged_its_load(self) -> None:
        self.events.write_text('{"type":"session"}\n', encoding="utf-8")
        (self.artifacts / "extension-events.jsonl").write_text(
            json.dumps({"event": "compaction_bound_loaded"}) + "\n", encoding="utf-8"
        )
        run_experiment.require_compaction_extension(self.artifacts, self.events)

    def test_refuses_a_round_that_ran_without_the_extension(self) -> None:
        self.events.write_text('{"type":"session"}\n', encoding="utf-8")
        (self.artifacts / "extension-events.jsonl").write_text(
            json.dumps({"event": "guard_block"}) + "\n", encoding="utf-8"
        )
        with self.assertRaises(SystemExit) as caught:
            run_experiment.require_compaction_extension(self.artifacts, self.events)
        self.assertIn("compaction-bound.ts did not load", str(caught.exception))

    def test_refuses_when_no_extension_log_exists(self) -> None:
        self.events.write_text('{"type":"session"}\n', encoding="utf-8")
        with self.assertRaises(SystemExit):
            run_experiment.require_compaction_extension(self.artifacts, self.events)

    def test_ignores_a_load_event_from_an_earlier_round(self) -> None:
        # A resumed run starts with the earlier rounds' events already in the
        # log; only what this round appended counts.
        log = self.artifacts / "extension-events.jsonl"
        log.write_text(json.dumps({"event": "compaction_bound_loaded"}) + "\n", encoding="utf-8")
        offset = log.stat().st_size
        self.events.write_text('{"type":"session"}\n', encoding="utf-8")
        with log.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps({"event": "guard_block"}) + "\n")
        with self.assertRaises(SystemExit):
            run_experiment.require_compaction_extension(self.artifacts, self.events, offset)
        with log.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps({"event": "compaction_bound_loaded"}) + "\n")
        run_experiment.require_compaction_extension(self.artifacts, self.events, offset)

    def test_stays_quiet_when_pi_produced_no_events(self) -> None:
        # A Pi process that never started is the process-failure path's to
        # report; a second error here would only hide it.
        run_experiment.require_compaction_extension(self.artifacts, None)
        self.events.write_text("", encoding="utf-8")
        run_experiment.require_compaction_extension(self.artifacts, self.events)


if __name__ == "__main__":
    unittest.main()
