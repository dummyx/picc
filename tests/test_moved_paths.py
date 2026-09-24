"""studies/moved.json: files that moved after runs used them, and how old runs still match."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import study  # noqa: E402
import summarize_study  # noqa: E402

MOVES = json.loads((ROOT / "studies" / "moved.json").read_text(encoding="utf-8"))["moves"]
STUDIES = sorted(ROOT.glob("studies/**/study.json"))


def strings(value: object):
    if isinstance(value, dict):
        for item in value.values():
            yield from strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from strings(item)
    elif isinstance(value, str):
        yield value


class MovedPathsTests(unittest.TestCase):
    def test_every_move_is_complete(self) -> None:
        self.assertTrue(MOVES)
        for old, new in MOVES.items():
            with self.subTest(old=old):
                self.assertFalse((ROOT / old).exists(), "the old location still exists")
                self.assertTrue((ROOT / new).exists(), "the new location is missing")

    def test_no_study_file_names_an_old_location(self) -> None:
        self.assertEqual(len(STUDIES), 7)
        for path in STUDIES:
            with self.subTest(study=str(path.relative_to(ROOT))):
                _, conditions = study.load_study(path)
                stale = [value for condition in conditions for value in strings(condition) if value in MOVES]
                self.assertEqual(stale, [])

    def test_a_run_frozen_before_the_move_matches_the_current_study(self) -> None:
        # A condition as a run frozen it before the move: the same settings,
        # naming the old locations. Translated, it equals today's condition.
        backwards = {new: old for old, new in MOVES.items()}
        used_moved_files = 0
        for path in STUDIES:
            _, conditions = study.load_study(path)
            for condition in conditions:
                frozen = summarize_study.relocated(condition, backwards)
                used_moved_files += frozen != condition
                with self.subTest(study=path.parent.name, condition=condition["id"]):
                    self.assertEqual(summarize_study.relocated(frozen, MOVES), condition)
        self.assertEqual(used_moved_files, 30)  # every condition of every study uses a moved file

    def test_only_whole_paths_are_translated(self) -> None:
        old = "studies/minimal/agents.md"
        condition = {
            "prompt": {"agents": old},
            "description": "Same inputs as studies/minimal except the product is a SQL engine.",
        }
        moved = summarize_study.relocated(condition, MOVES)
        self.assertEqual(moved["prompt"]["agents"], MOVES[old])
        self.assertEqual(moved["description"], condition["description"])
        self.assertEqual(
            summarize_study.relocated("studies/assets/scaffolds/rust-pipeline/src/main.rs", MOVES),
            "studies/c10/scaffolds/rust-pipeline/src/main.rs",
        )


if __name__ == "__main__":
    unittest.main()
