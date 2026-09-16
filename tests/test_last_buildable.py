"""The last buildable snapshot: selection in the post-hoc evaluator and in the summarizer."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import evaluate_run  # noqa: E402
import summarize_study  # noqa: E402


def snapshot(round_number: int) -> dict:
    return {"round": round_number, "git_commit": f"c{round_number}", "git_tree": f"t{round_number}"}


def hidden_row(round_number: int, build_ok: bool, audit_ok: bool = True, blocking: bool = False) -> dict:
    return {
        "round": round_number,
        "git_commit": f"c{round_number}",
        "git_tree": f"t{round_number}",
        "summary": {"score": 0.5 + round_number / 10, "build_ok": build_ok, "audit_ok": audit_ok, "audit_blocking": blocking},
    }


class LastBuildableSelectionTests(unittest.TestCase):
    def test_advisory_finding_does_not_disqualify_a_buildable_snapshot(self) -> None:
        """v9 Amendment 1 (v9-spec-minimal-r1): round 0 built with an advisory
        (non-blocking) finding, the final did not build; round 0 is the last
        buildable snapshot, as it would have scored normally as a final."""
        snaps = [snapshot(0), snapshot(1)]
        rows = [hidden_row(0, True, audit_ok=False, blocking=False), hidden_row(1, False)]
        self.assertIs(evaluate_run.last_buildable_snapshot(rows, snaps), snaps[0])
        self.assertEqual(summarize_study.last_buildable_index(rows), 0)

    def test_final_snapshot_wins_when_it_builds(self) -> None:
        snaps = [snapshot(0), snapshot(1)]
        rows = [hidden_row(0, True), hidden_row(1, True)]
        self.assertIs(evaluate_run.last_buildable_snapshot(rows, snaps), snaps[1])
        self.assertEqual(summarize_study.last_buildable_index(rows), 1)

    def test_previous_snapshot_is_chosen_when_the_final_does_not_build(self) -> None:
        # The v7 case: a rewrite cut by the round cap.
        snaps = [snapshot(0), snapshot(1), snapshot(2)]
        rows = [hidden_row(0, True), hidden_row(1, True), hidden_row(2, False)]
        self.assertIs(evaluate_run.last_buildable_snapshot(rows, snaps), snaps[1])
        self.assertEqual(summarize_study.last_buildable_index(rows), 1)

    def test_audit_blocked_snapshots_do_not_count_as_buildable(self) -> None:
        snaps = [snapshot(0), snapshot(1)]
        rows = [hidden_row(0, True), hidden_row(1, True, audit_ok=False, blocking=True)]
        self.assertIs(evaluate_run.last_buildable_snapshot(rows, snaps), snaps[0])
        self.assertEqual(summarize_study.last_buildable_index(rows), 0)

    def test_no_buildable_snapshot_yields_none(self) -> None:
        snaps = [snapshot(0), snapshot(1)]
        rows = [hidden_row(0, False), hidden_row(1, False)]
        self.assertIsNone(evaluate_run.last_buildable_snapshot(rows, snaps))
        self.assertIsNone(summarize_study.last_buildable_index(rows))

    def test_selection_matches_snapshots_by_commit_and_tree(self) -> None:
        snaps = [snapshot(0), snapshot(1)]
        rows = [hidden_row(1, True)]  # only round 1 evaluated
        self.assertIs(evaluate_run.last_buildable_snapshot(rows, snaps), snaps[1])
        rows[0]["git_tree"] = "other"
        self.assertIsNone(evaluate_run.last_buildable_snapshot(rows, snaps))


if __name__ == "__main__":
    unittest.main()
