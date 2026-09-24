"""Per-test results of every scored version, hidden and visible.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .records import cap_text, DataError, fingerprint, read_json


class TestResultsMixin:
    # ---------------------------------------------------------------- tests

    def _eval_path(self, run: Path, partition: str, round_no: int) -> tuple[Path, str | None]:
        art = run / "artifacts"
        name = f"{partition}-round-{round_no:03d}.json"
        if partition == "hidden":
            rescore = self._rescore_dir(run.name)
            if rescore is not None and (rescore / "evaluations" / name).is_file():
                return rescore / "evaluations" / name, str(rescore.relative_to(self.root))
            snaps = self._snapshots(run)
            v6 = self.root / "analysis" / "v6-rescore" / f"{run.name}.hidden.json"
            if v6.is_file() and snaps and snaps[-1]["round"] == round_no:
                return v6, "analysis/v6-rescore"
        return art / "evaluations" / name, None

    def _eval_rounds(self, run: Path, partition: str) -> list[int]:
        found = set()
        for p in (run / "artifacts" / "evaluations").glob(f"{partition}-round-*.json"):
            m = re.search(r"-round-(\d+)\.json$", p.name)
            if m:
                found.add(int(m.group(1)))
        rescore = self._rescore_dir(run.name)
        if partition == "hidden" and rescore is not None:
            for p in (rescore / "evaluations").glob("hidden-round-*.json"):
                m = re.search(r"-round-(\d+)\.json$", p.name)
                if m:
                    found.add(int(m.group(1)))
        return sorted(found)

    def tests(self, run_id: str, partition: str, round_no: int | None) -> dict[str, Any]:
        run = self.run_dir(run_id)
        if partition not in ("hidden", "visible"):
            raise DataError("partition must be hidden or visible")
        available = self._eval_rounds(run, partition)
        if not available:
            return {"partition": partition, "round": None, "rounds": [], "tests": [], "summary": None}
        if round_no is None:
            round_no = available[-1]
        if round_no not in available:
            raise DataError(f"no {partition} test results for round {round_no}")
        path, corrected = self._eval_path(run, partition, round_no)
        ev = read_json(path) or {}
        summary = {k: v for k, v in (ev.get("summary") or {}).items() if k != "failures"}
        build = ev.get("build") or {}
        output = (str(build.get("stdout") or "") + ("\n" if build.get("stdout") and build.get("stderr") else "")
                  + str(build.get("stderr") or ""))
        audit = ev.get("source_audit") or {}
        tests = []
        for t in ev.get("tests") or []:
            detail, _ = cap_text(str(t.get("detail") or ""), 4000)
            tests.append({
                "id": t.get("id"), "stage": t.get("stage"), "validity": t.get("validity"),
                "passed": t.get("passed"), "score": t.get("score"),
                "failure": t.get("failure_type"), "detail": detail,
                "failures": (t.get("failures") or [])[:8], "records": t.get("records"),
                "seconds": round(float(t.get("compile_seconds") or 0) + float(t.get("execute_seconds") or 0), 3),
            })
        return {
            "partition": partition, "round": round_no, "rounds": available, "corrected_by": corrected,
            "summary": summary,
            "build": {"ok": build.get("returncode") == 0 if build else None, "command": build.get("args"),
                      "returncode": build.get("returncode"), "seconds": build.get("elapsed_seconds"),
                      "output": output[-40_000:], "cut": len(output) > 40_000},
            "audit": {"passed": audit.get("passed"), "findings": (audit.get("findings") or [])[:60]},
            "task": ev.get("task"), "tests": tests,
        }

    def matrix(self, run_id: str, partition: str) -> dict[str, Any]:
        run = self.run_dir(run_id)
        if partition not in ("hidden", "visible"):
            raise DataError("partition must be hidden or visible")
        rounds = self._eval_rounds(run, partition)
        paths = [self._eval_path(run, partition, r)[0] for r in rounds]
        fp = fingerprint(paths)

        def compute() -> dict[str, Any]:
            cells: dict[str, dict[int, float | None]] = {}
            stages: dict[str, Any] = {}
            for r, p in zip(rounds, paths):
                ev = read_json(p) or {}
                for t in ev.get("tests") or []:
                    tid = str(t.get("id"))
                    stages[tid] = t.get("stage")
                    score = t.get("score")
                    if score is None:
                        score = 1.0 if t.get("passed") else 0.0
                    cells.setdefault(tid, {})[r] = round(float(score), 4)
            ids = sorted(cells, key=lambda tid: (stages.get(tid) or 0, tid))
            return {"rounds": rounds, "tests": ids, "stages": [stages.get(t) for t in ids],
                    "cells": [[cells[t].get(r) for r in rounds] for t in ids]}

        return self.store.get("matrix", f"{run_id}.{partition}", fp, compute)

    def final_tests(self, run_id: str, compute: bool = True) -> dict[str, Any] | None:
        """Per-test (SQL: per script) or per-stage (compiler) final hidden scores."""
        run = self.run_dir(run_id)
        rounds = self._eval_rounds(run, "hidden")
        snaps = self._snapshots(run)
        final_round = snaps[-1]["round"] if snaps else (rounds[-1] if rounds else None)
        if final_round not in rounds:
            final_round = rounds[-1] if rounds else None
        if final_round is None:
            return None
        path, corrected = self._eval_path(run, "hidden", final_round)
        fp = fingerprint([path])
        if not compute:
            return self.store.peek("final", run_id, fp)

        def build() -> dict[str, Any]:
            ev = read_json(path) or {}
            tests = ev.get("tests") or []
            fractional = any(t.get("score") is not None for t in tests)
            if fractional:
                cols = [str(t.get("id") or "").removeprefix("test/") for t in tests]
                vals = [round(float(t.get("score") or 0), 4) for t in tests]
                fails = [t.get("failure_type") for t in tests]
                kind = "test"
            else:
                st = (ev.get("summary") or {}).get("stages") or {}
                keys = sorted(st, key=lambda s: int(s) if str(s).isdigit() else 0)
                cols = [f"stage {k}" for k in keys]
                vals = [round(float((st[k] or {}).get("score") or 0), 4) for k in keys]
                fails = [None for _ in keys]
                kind = "stage"
            return {"round": final_round, "kind": kind, "columns": cols, "scores": vals, "failures": fails,
                    "corrected_by": corrected}

        return self.store.get("final", run_id, fp, build)
