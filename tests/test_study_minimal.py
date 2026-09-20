from __future__ import annotations

import copy
import json
import shutil
import tempfile
import unittest
import uuid
from pathlib import Path

from test_study import ROOT, study, write_partition


class MinimalStudyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.path = ROOT / "studies" / "minimal" / "study.json"
        self.payload, conditions = study.load_study(self.path)
        self.assertEqual([row["id"] for row in conditions], ["minimal"])
        self.condition = conditions[0]

    def test_rejects_nonboolean_experiment_tools(self) -> None:
        for value in (None, "false", 0, 1):
            with self.subTest(value=value):
                condition = copy.deepcopy(self.condition)
                condition["prompt"]["experiment_tools"] = value
                with self.assertRaisesRegex(study.StudyError, "must be a boolean"):
                    study.validate_condition(condition, self.payload)

    def test_disabled_tools_cannot_promise_test_or_reference_access(self) -> None:
        for access in ("tool", "files"):
            with self.subTest(access=access):
                condition = copy.deepcopy(self.condition)
                condition["tests"].update(access=access, feedback="failures")
                with self.assertRaisesRegex(study.StudyError, "disabling experiment_tools"):
                    study.validate_condition(condition, self.payload)
        condition = copy.deepcopy(self.condition)
        condition["reference"].update(mode="oracle", oracle_limit=1)
        with self.assertRaisesRegex(study.StudyError, "disabling experiment_tools"):
            study.validate_condition(condition, self.payload)

    def test_materialized_agent_receives_only_the_short_contract_and_builtin_tools(self) -> None:
        with tempfile.TemporaryDirectory(prefix=".minimal-test-", dir=ROOT / "data") as temporary:
            for partition in ("visible", "hidden"):
                path = write_partition(Path(temporary), partition)
                self.condition["tests"][f"{partition}_partition"] = str(path.relative_to(ROOT))
            run_id = f"unit-minimal-{uuid.uuid4().hex}"
            materialization = ROOT / "runs" / ".study-materializations" / run_id
            self.addCleanup(shutil.rmtree, materialization, ignore_errors=True)
            root = study.materialize(self.path, self.payload, self.condition, run_id)

            adapter = study.load_json_object(ROOT / self.condition["candidate"]["adapter"])
            expected = study.render_template(
                (ROOT / self.condition["specification"]["path"]).read_text(),
                study.adapter_variables(adapter, self.condition),
                "minimal contract",
            ).rstrip() + "\n"
            initial = (root / "prompts" / "INITIAL.txt").read_text()
            self.assertEqual(initial, expected)
            self.assertLess(len(initial.split()), 160)
            for advice in ("PROGRESS.md", "TASK.md", "Stage 1", "lowest-numbered", "after meaningful changes"):
                self.assertNotIn(advice, initial)
            for name in ("AGENTS.md", "TASK.md"):
                self.assertEqual((root / "prompts" / name).read_text().strip(), "")
            self.assertEqual((root / "prompts" / "CONTINUE.txt").read_text(), "Continue.\n")

            extensions = root / "pi" / "extensions"
            self.assertEqual(
                sorted(path.name for path in extensions.iterdir()),
                ["compaction-bound.ts", "experiment-guard.ts"],
            )
            guard = (extensions / "experiment-guard.ts").read_text()
            self.assertNotIn("registerTool", guard)
            self.assertNotIn("promptGuidelines", guard)
            record = json.loads((root / "study-materialization.json").read_text())
            self.assertEqual(record["effective_config"]["PI_TOOLS"], "read,bash,edit,write,grep,find,ls")
            visible = root / "data" / "agent-visible"
            self.assertEqual([path.name for path in visible.iterdir()], ["manifest.json"])
            self.assertEqual(json.loads((visible / "manifest.json").read_text())["tests"], [])
            hidden = root / "data" / "partitions" / "hidden" / "manifest.json"
            self.assertTrue(json.loads(hidden.read_text())["tests"])


if __name__ == "__main__":
    unittest.main()
