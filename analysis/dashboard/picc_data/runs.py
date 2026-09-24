"""Runs and batches: which runs exist, their scores (with later corrections),
and each run's summary and whether it is still running.
"""

from __future__ import annotations

import re
import time
from pathlib import Path
from typing import Any

from .records import (
    LANGUAGE_OF,
    NOT_RUNS,
    RESCORE_APPLIES_TO,
    RUN_ID,
    DataError,
    fingerprint,
    jsonl,
    lock_held,
    read_json,
    read_locks,
    read_text,
)


class RunsMixin:
    # ---------------------------------------------------------------- runs

    def run_ids(self) -> list[str]:
        now = time.time()
        if now - self._ids_cache[0] < 5:
            return self._ids_cache[1]
        ids = []
        try:
            for d in self.runs_dir.iterdir():
                if (d.name.startswith(".") or d.name in NOT_RUNS or not d.is_dir()
                        or not RUN_ID.match(d.name)):
                    continue
                if (d / "metadata.json").is_file() or (d / "artifacts").is_dir():
                    ids.append(d.name)
        except OSError:
            pass
        ids.sort()
        self._ids_cache = (now, ids)
        return ids

    def run_dir(self, run_id: str) -> Path:
        if not RUN_ID.match(run_id or "") or run_id not in self.run_ids():
            raise DataError(f"no run called {run_id!r}")
        return self.runs_dir / run_id

    # ---------------------------------------------------------------- batches

    @staticmethod
    def batch_of(run_id: str) -> str:
        m = re.match(r"v(\d+)(?=[a-z-]|$)", run_id)
        if m:
            return f"v{m.group(1)}"
        if run_id.startswith("probe"):
            return "probes"
        return "early"

    @staticmethod
    def batch_order(key: str) -> tuple[int, int]:
        if key.startswith("v") and key[1:].isdigit():
            return (0, -int(key[1:]))
        return (1, 0 if key == "probes" else 1)

    def batch_docs(self, key: str) -> dict[str, Any]:
        docs: dict[str, Any] = {"plan": None, "results": None, "reports": [], "title": "", "subtitle": ""}
        if key.startswith("v") and key[1:].isdigit():
            plan = self.root / "docs" / f"EXPERIMENT_PLAN_{key}.md"
            if not plan.is_file() and key == "v3":
                plan = self.root / "docs" / "EXPERIMENT_PLAN.md"
            if plan.is_file():
                docs["plan"] = str(plan.relative_to(self.root))
                head = (read_text(plan, 400) or "").splitlines()[0:1]
                m = re.search(r"\(([^)]*)\)\s*$", head[0]) if head else None
                if m:
                    docs["subtitle"] = m.group(1)
            results = self.root / "analysis" / f"{key}-results.md"
            if results.is_file():
                docs["results"] = str(results.relative_to(self.root))
            pattern = re.compile(rf"\b{re.escape(key)}\b")
            for report in sorted((self.root / "docs").glob("REPORT_*.md")):
                first = (read_text(report, 400) or "").split("\n", 1)[0]
                if pattern.search(first):
                    docs["reports"].append(str(report.relative_to(self.root)))
            docs["title"] = key
        elif key == "probes":
            docs["title"] = "Probe runs"
            docs["subtitle"] = "short runs used to test settings"
        else:
            docs["title"] = "Early trial runs"
            docs["subtitle"] = "before the numbered batches"
        return docs

    # ---------------------------------------------------------------- scores

    def _rescore_dir(self, run_id: str) -> Path | None:
        for d in sorted(self.root.glob("analysis/v*-rescore")):
            applies = RESCORE_APPLIES_TO.get(d.name)
            if applies is not None and run_id not in applies:
                continue
            if (d / run_id / "hidden-scores.jsonl").is_file():
                return d / run_id
        return None

    def _v6_rescore(self, run_id: str) -> dict[str, Any] | None:
        data = read_json(self.root / "analysis" / "v6-rescore.json")
        if isinstance(data, dict) and isinstance(data.get(run_id), dict):
            return data[run_id]
        return None

    def _score_paths(self, run: Path) -> list[Path]:
        art = run / "artifacts"
        paths = [run / "metadata.json", run / "study-metadata.json", art / "rounds.jsonl",
                 art / "snapshots.jsonl", art / "hidden-scores.jsonl", art / "fuzz-scores.jsonl",
                 art / "state.json", self.root / "analysis" / "v6-rescore.json"]
        rescore = self._rescore_dir(run.name)
        if rescore is not None:
            paths += [rescore / "hidden-scores.jsonl", rescore / "fuzz-scores.jsonl"]
        return paths

    def _scores(self, run: Path, snaps: list[dict[str, Any]]) -> dict[str, Any]:
        art = run / "artifacts"
        visible = []
        for s in snaps:
            v = s.get("visible") or {}
            visible.append({
                "round": s.get("round"),
                "t": s.get("elapsed_seconds"),
                "score": v.get("score"),
                "built": v.get("build_ok"),
                "rules_ok": not v.get("audit_blocking", False) if v else None,
                "passed": v.get("passed"),
                "total": v.get("total"),
            })
        frozen = {int(h.get("round", -1)): h for h in jsonl(art / "hidden-scores.jsonl")}
        rescore = self._rescore_dir(run.name)
        corrected_rows = {int(h.get("round", -1)): h for h in jsonl(rescore / "hidden-scores.jsonl")} if rescore else {}
        source = str(rescore.parent.relative_to(self.root)) if rescore else None
        rounds = sorted(set(frozen) | set(corrected_rows))
        hidden = []
        for r in rounds:
            row = corrected_rows.get(r) or frozen.get(r) or {}
            s = row.get("summary") or {}
            f = (frozen.get(r) or {}).get("summary") or {}
            hidden.append({
                "round": r,
                "t": row.get("elapsed_seconds"),
                "score": s.get("score"),
                "built": s.get("build_ok"),
                "passed": s.get("passed"),
                "total": s.get("total"),
                "frozen": f.get("score") if r in corrected_rows and r in frozen else None,
            })
        v6 = self._v6_rescore(run.name)
        if v6 and hidden and v6.get("hidden_rescored") is not None:
            last = hidden[-1]
            if last["score"] != v6["hidden_rescored"]:
                last["frozen"] = last["score"]
                last["score"] = v6["hidden_rescored"]
            source = "analysis/v6-rescore.json"
        fuzz_rows = jsonl(rescore / "fuzz-scores.jsonl") if rescore and (rescore / "fuzz-scores.jsonl").is_file() \
            else jsonl(art / "fuzz-scores.jsonl")
        fuzz: dict[str, Any] | None = None
        if fuzz_rows:
            by_role = {str(r.get("role") or "final"): r for r in fuzz_rows}
            final = by_role.get("final") or fuzz_rows[-1]
            fuzz = {
                "final": (final.get("summary") or {}).get("fuzz_macro"),
                "round": final.get("round"),
                "last_built": ((by_role.get("last_buildable") or {}).get("summary") or {}).get("fuzz_macro"),
                "stages": (final.get("summary") or {}).get("stage_pass_rates"),
                "frozen": None,
            }
            if v6 and v6.get("fuzz_rescored") is not None and v6["fuzz_rescored"] != fuzz["final"]:
                fuzz["frozen"] = fuzz["final"]
                fuzz["final"] = v6["fuzz_rescored"]
        final_round = snaps[-1].get("round") if snaps else None
        by_round = {h["round"]: h for h in hidden}
        final = by_round.get(final_round) if final_round is not None else None
        if final is None and hidden:
            final = hidden[-1]
        if hidden and len(hidden) == len(visible):
            # Every saved version was scored on the hidden tests: the last one
            # whose hidden scoring built with no blocking rule finding, the
            # rule the study summary uses (scripts/summarize_study.py).
            def built(r: int) -> bool:
                s = ((corrected_rows.get(r) or frozen.get(r) or {}).get("summary")) or {}
                return s.get("build_ok") is True and not s.get("audit_blocking")
            last_built_round = next((h["round"] for h in reversed(hidden) if built(h["round"])), None)
        else:
            last_built_round = next((v["round"] for v in reversed(visible) if v["built"] and v["rules_ok"] is not False), None)
        last_built = by_round.get(last_built_round) if last_built_round is not None else None
        scored = [h["score"] for h in hidden if isinstance(h["score"], (int, float))]
        vis_scores = [v["score"] for v in visible if isinstance(v["score"], (int, float))]
        changed = any(h["frozen"] is not None for h in hidden) or bool(fuzz and fuzz.get("frozen") is not None)
        return {
            "visible": visible,
            "hidden": hidden,
            "corrected_by": source if changed else None,
            "fuzz": fuzz,
            "final": final["score"] if final else None,
            "final_round": final["round"] if final else None,
            "final_frozen": final["frozen"] if final else None,
            "best": max(scored) if scored else None,
            "last_built": (last_built or {}).get("score") if last_built_round is not None else (0.0 if hidden else None),
            "last_built_round": last_built_round,
            "visible_final": vis_scores[-1] if vis_scores else None,
            "visible_best": max(vis_scores) if vis_scores else None,
        }

    # ---------------------------------------------------------------- summary

    def summary(self, run_id: str, locks: str | None = None) -> dict[str, Any]:
        run = self.run_dir(run_id)
        fp = fingerprint(self._score_paths(run))
        base = self.store.get("summary", run_id, fp, lambda: self._summary(run), disk=False)
        out = dict(base)
        out.update(self._liveness(run, base, read_locks() if locks is None else locks))
        return out

    def _summary(self, run: Path) -> dict[str, Any]:
        art = run / "artifacts"
        meta = read_json(run / "metadata.json") or {}
        sm = read_json(run / "study-metadata.json") or {}
        cond = sm.get("condition") or {}
        task = sm.get("task") or cond.get("task") or {}
        task_id = task.get("id") or (self._infer_task(run) if not sm else None) or "c-compiler-ch1-10"
        rounds = jsonl(art / "rounds.jsonl")
        snaps = jsonl(art / "snapshots.jsonl")
        state = read_json(art / "state.json") or {}
        config = meta.get("configuration") or sm.get("effective_config") or {}
        model = meta.get("model") or {}
        model_id = model.get("id") or config.get("MODEL_ID") or ""
        provider = model.get("provider") or config.get("MODEL_PROVIDER") or ""
        server = "llama.cpp" if "GGUF" in model_id else ("SGLang" if provider == "local" else provider)
        budget = meta.get("budget") or {}
        m = re.search(r"-r(\d+)$", run.name)
        repeat = meta.get("replicate") or (int(m.group(1)) if m else None)
        candidate = cond.get("candidate") or {}
        adapter = read_json(run / "study-control" / "candidate.json") or {}
        variant = cond.get("id") or sm.get("condition_id") or ("" if sm else self._infer_variant(run.name))
        language = candidate.get("language") or adapter.get("language") or LANGUAGE_OF.get(variant) \
            or ("rust" if task_id.startswith("c-") and sm else "")
        started = meta.get("started_at") or (rounds[0].get("started_at") if rounds else None)
        elapsed = meta.get("elapsed_seconds")
        if elapsed is None:
            elapsed = state.get("elapsed_seconds") or sum(float(r.get("elapsed_seconds") or 0) for r in rounds)
        sampling = model.get("sampling_params") or {}
        thinking_budget = (sampling.get("custom_params") or {}).get("thinking_budget") \
            or (int(config["LOCAL_THINKING_BUDGET"]) if str(config.get("LOCAL_THINKING_BUDGET") or "").isdigit() else None)
        scores = self._scores(run, snaps)
        return {
            "id": run.name,
            "batch": self.batch_of(run.name),
            "study": sm.get("study_id"),
            "variant": variant,
            "variant_recorded": bool(cond.get("id") or sm.get("condition_id")),
            "variant_description": cond.get("description") or "",
            "factor": cond.get("factor"),
            "repeat": repeat,
            "profile": meta.get("profile") or "",
            "task": task_id,
            "language": language,
            "framework": candidate.get("framework") or adapter.get("framework") or "",
            "meta_status": meta.get("status") or "",
            "end_reason": meta.get("termination_reason"),
            "started_at": started,
            "ended_at": meta.get("ended_at"),
            "elapsed_s": float(elapsed or 0),
            "budget_hours": budget.get("wall_hours"),
            "max_rounds": budget.get("max_rounds"),
            "round_cap_min": budget.get("round_timeout_minutes"),
            "max_stage": budget.get("max_stage") or task.get("max_stage"),
            "rounds": len(snaps) if snaps else len(rounds),
            "rounds_capped": sum(1 for r in rounds if r.get("timed_out")),
            "resumed": bool(meta.get("resumed")),
            "comparable": meta.get("protocol_comparable", True) is not False,
            "model": model_id,
            "server": server,
            "thinking": model.get("thinking") or config.get("MODEL_THINKING"),
            "context_window": model.get("context_window") or (int(config["LOCAL_CONTEXT_WINDOW"]) if str(config.get("LOCAL_CONTEXT_WINDOW") or "").isdigit() else None),
            "reply_cap": model.get("max_tokens") or (int(config["LOCAL_MAX_OUTPUT"]) if str(config.get("LOCAL_MAX_OUTPUT") or "").isdigit() else None),
            "thinking_budget": thinking_budget,
            "state_round": state.get("round"),
            "state_remaining_s": state.get("remaining_seconds"),
            "scores": scores,
            "final": scores["final"],
            "visible_final": scores["visible_final"],
        }

    @staticmethod
    def _infer_variant(run_id: str) -> str:
        """Variant of a run stopped before its study record was written, from its name."""
        m = re.match(r"v\d+[a-z]*-(?:[a-z]+-)?(?:sql|c18)-(.+?)-r\d+$", run_id)
        return m.group(1) if m else ""

    def _infer_task(self, run: Path) -> str | None:
        """Task of a run with no study record, from its first evaluator record."""
        for p in sorted((run / "artifacts" / "evaluations").glob("*-round-*.json"))[:1]:
            ev = read_json(p) or {}
            if (ev.get("task") or {}).get("sqlite_version"):
                return "sql-engine-sqllogictest"
            ids = [str(t.get("id") or "") for t in ev.get("tests") or []]
            if any(i.startswith("test/") for i in ids):
                return "sql-engine-sqllogictest"
            stages = [int(t.get("stage") or 0) for t in ev.get("tests") or []]
            if stages:
                return "c-compiler-ch1-18" if max(stages) > 10 else "c-compiler-ch1-10"
        return None

    def _liveness(self, run: Path, summary: dict[str, Any], locks: str | None) -> dict[str, Any]:
        held = lock_held(run / ".harness.lock", locks)
        status = summary.get("meta_status")
        if held is None:  # no /proc/locks: fall back to recent activity
            newest = 0.0
            for p in (run / "artifacts" / "events").glob("round-*.jsonl"):
                try:
                    newest = max(newest, p.stat().st_mtime)
                except OSError:
                    pass
            held = status == "running" and time.time() - newest < 900
        if held:
            state = "scoring" if status == "completed" else "running"
        elif status == "completed":
            state = "finished"
        elif status in ("running", "") or status is None:
            state = "interrupted"
        else:
            state = str(status)
        return {"status": state}
