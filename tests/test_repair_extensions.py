"""The two extensions that repair what the harness's own limits break.

`compaction-bound.ts`: Pi's summarization serializer truncates tool results and
nothing else, so a reasoning model's thinking blocks and a `write` call's file
body reach the summarization request whole. That request outgrew the context
window in runs from v10 on (132k-401k tokens against 131072) and length-stopped
the turn-prefix summary in v6-v9.

`truncation-repair.ts`: a reply that reaches the output cap while still
reasoning produces nothing, and leaves unfinished reasoning in the context. The
next reply is then cut off 64.7% of the time against a 5.8% base rate, which is
how a run stops producing for the rest of its budget.

Both extensions' own logic is exercised in the pinned image by
scripts/smoke_extensions.sh; these tests cover the wiring around them.
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

EXTENSIONS = ROOT / "pi" / "extensions"
EXTENSION = EXTENSIONS / "compaction-bound.ts"
REPAIR = EXTENSIONS / "truncation-repair.ts"


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


class TruncationRepairTest(unittest.TestCase):
    def setUp(self) -> None:
        self.source = REPAIR.read_text(encoding="utf-8")

    def test_subscribes_and_announces_itself(self) -> None:
        self.assertIn('pi.on("message_end"', self.source)
        self.assertIn("export default function", self.source)
        self.assertIn('appendEvent({ event: "truncation_repair_loaded" })', self.source)

    def test_note_states_what_happened_without_directing_the_agent(self) -> None:
        # The repair removes an artifact of the harness's output cap. Telling
        # the agent what to do next would be steering, and the experiment is
        # partly about how the agent chooses to spend its turns.
        for directive in ("you should", "You should", "instead", "now write", "stop planning"):
            self.assertNotIn(directive, self.source)


class MaterializationTest(unittest.TestCase):
    def test_every_materialization_carries_the_extension(self) -> None:
        path = ROOT / "studies" / "sql" / "study.json"
        payload, conditions = study.load_study(path)
        condition = conditions[0]
        run_id = f"unit-compaction-{uuid.uuid4().hex}"
        root = ROOT / "runs" / ".study-materializations" / run_id
        self.addCleanup(shutil.rmtree, root, ignore_errors=True)
        study.materialize(path, payload, condition, run_id)
        for name in ("compaction-bound.ts", "truncation-repair.ts"):
            rendered = root / "pi" / "extensions" / name
            self.assertTrue(rendered.is_file(), name)
            self.assertEqual(
                rendered.read_text(encoding="utf-8"),
                (EXTENSIONS / name).read_text(encoding="utf-8"),
                name,
            )


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
            json.dumps({"event": "compaction_bound_loaded"}) + "\n"
            + json.dumps({"event": "truncation_repair_loaded"}) + "\n",
            encoding="utf-8",
        )
        run_experiment.require_extensions(self.artifacts, self.events)

    def test_refuses_a_round_that_ran_without_the_extension(self) -> None:
        self.events.write_text('{"type":"session"}\n', encoding="utf-8")
        (self.artifacts / "extension-events.jsonl").write_text(
            json.dumps({"event": "guard_block"}) + "\n", encoding="utf-8"
        )
        with self.assertRaises(SystemExit) as caught:
            run_experiment.require_extensions(self.artifacts, self.events)
        self.assertIn("compaction-bound.ts", str(caught.exception))
        self.assertIn("truncation-repair.ts", str(caught.exception))

    def test_refuses_when_no_extension_log_exists(self) -> None:
        self.events.write_text('{"type":"session"}\n', encoding="utf-8")
        with self.assertRaises(SystemExit):
            run_experiment.require_extensions(self.artifacts, self.events)

    def test_ignores_a_load_event_from_an_earlier_round(self) -> None:
        # A resumed run starts with the earlier rounds' events already in the
        # log; only what this round appended counts.
        log = self.artifacts / "extension-events.jsonl"
        log.write_text(
            json.dumps({"event": "compaction_bound_loaded"}) + "\n"
            + json.dumps({"event": "truncation_repair_loaded"}) + "\n",
            encoding="utf-8",
        )
        offset = log.stat().st_size
        self.events.write_text('{"type":"session"}\n', encoding="utf-8")
        with log.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps({"event": "guard_block"}) + "\n")
        with self.assertRaises(SystemExit):
            run_experiment.require_extensions(self.artifacts, self.events, offset)
        with log.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps({"event": "compaction_bound_loaded"}) + "\n")
            handle.write(json.dumps({"event": "truncation_repair_loaded"}) + "\n")
        run_experiment.require_extensions(self.artifacts, self.events, offset)

    def test_stays_quiet_when_pi_produced_no_events(self) -> None:
        # A Pi process that never started is the process-failure path's to
        # report; a second error here would only hide it.
        run_experiment.require_extensions(self.artifacts, None)
        self.events.write_text("", encoding="utf-8")
        run_experiment.require_extensions(self.artifacts, self.events)


if __name__ == "__main__":
    unittest.main()
