"""Whole-page answers: a run's setup and live activity, the overview and batch
pages, the documents, and the model server.
"""

from __future__ import annotations

import json
import os
import re
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

from .classify import describe_call
from .records import DataError, is_secret_name, iso_ms, read_json, read_locks, read_text


class PagesMixin:
    # ---------------------------------------------------------------- setup

    PROMPT_FILES = ("AGENTS.md", "TASK.md", "INITIAL.txt", "CONTINUE.txt")

    def setup(self, run_id: str) -> dict[str, Any]:
        run = self.run_dir(run_id)
        meta = read_json(run / "metadata.json") or {}
        sm = read_json(run / "study-metadata.json") or {}
        config = meta.get("configuration") or sm.get("effective_config") or {}
        config = {k: v for k, v in sorted(config.items()) if not is_secret_name(k)}
        prompts = []
        for name in self.PROMPT_FILES:
            p = run / "control" / name
            if p.is_file():
                prompts.append({"name": name, "bytes": p.stat().st_size})
        spec = [p for p in (run / "study-control" / "prompts").glob("*") if p.is_file()] if (run / "study-control" / "prompts").is_dir() else []
        for p in sorted(spec):
            if p.name not in self.PROMPT_FILES:
                prompts.append({"name": f"study-control/prompts/{p.name}", "bytes": p.stat().st_size})
        settings = read_json(run / "control" / "pi" / "settings.json")
        extensions = sorted(p.name for p in (run / "control" / "pi" / "extensions").glob("*") if p.is_file()) \
            if (run / "control" / "pi" / "extensions").is_dir() else []
        cond = sm.get("condition") or {}
        adapter = read_json(run / "study-control" / "candidate.json")
        return {
            "model": meta.get("model"), "budget": meta.get("budget"), "image": meta.get("docker_image"),
            "host": meta.get("host"), "attempts": meta.get("execution_attempts"),
            "interventions": meta.get("interventions"), "config": config,
            "condition": cond, "task": sm.get("task"), "rendered": sm.get("rendered"),
            "study": {"id": sm.get("study_id"), "path": sm.get("study_path"),
                      "created_at": sm.get("created_at"), "frozen_at": sm.get("frozen_at")},
            "adapter": adapter, "prompts": prompts, "pi_settings": settings, "extensions": extensions,
            "report": (run / "report.md").is_file(),
            "replicate_note": meta.get("replicate_note"),
        }

    def prompt(self, run_id: str, name: str) -> dict[str, Any]:
        run = self.run_dir(run_id)
        if name in self.PROMPT_FILES:
            path = run / "control" / name
        elif name.startswith("study-control/prompts/") and "/" not in name.removeprefix("study-control/prompts/"):
            path = run / name
            if ".." in name:
                raise DataError("bad prompt name")
        elif name == "report.md":
            path = run / "report.md"
        else:
            raise DataError("unknown prompt file")
        text = read_text(path, 2_000_000)
        if text is None:
            raise DataError("file not found")
        return {"name": name, "text": text}

    # ---------------------------------------------------------------- live activity

    def activity(self, run_id: str) -> dict[str, Any]:
        """What a running run is doing right now, from the tail of its files."""
        run = self.run_dir(run_id)
        art = run / "artifacts"
        state = read_json(art / "state.json") or {}
        out: dict[str, Any] = {"round": state.get("round"), "elapsed_s": state.get("elapsed_seconds"),
                               "remaining_s": state.get("remaining_seconds"), "doing": None, "detail": None}
        events = self._events(run)
        if events:
            path = events[-1]
            out["events_round"] = int(re.search(r"(\d+)", path.name).group(1)) if re.search(r"(\d+)", path.name) else None
            try:
                size = path.stat().st_size
                out["events_updated"] = path.stat().st_mtime * 1000
                with path.open("rb") as handle:
                    handle.seek(max(0, size - 8_000_000))
                    tail = handle.read().decode("utf-8", "replace").splitlines()
            except OSError:
                tail = []
            thinking = text = toolcall = 0
            open_reply = False
            running_tool = None
            compaction = False
            for line in tail:
                if '"message_update"' in line:
                    if not open_reply:
                        continue
                    if '"thinking_delta"' in line or '"text_delta"' in line or '"toolcall_delta"' in line:
                        try:
                            ev = json.loads(line)
                        except json.JSONDecodeError:
                            continue
                        upd = ev.get("assistantMessageEvent") or {}
                        delta = str(upd.get("delta") or "")
                        if upd.get("type") == "thinking_delta":
                            thinking += len(delta)
                        elif upd.get("type") == "text_delta":
                            text += len(delta)
                        elif upd.get("type") == "toolcall_delta":
                            toolcall += len(delta)
                    continue
                try:
                    ev = json.loads(line)
                except json.JSONDecodeError:
                    continue
                typ = ev.get("type")
                if typ == "message_start" and (ev.get("message") or {}).get("role") == "assistant":
                    open_reply, thinking, text, toolcall = True, 0, 0, 0
                elif typ == "message_end" and (ev.get("message") or {}).get("role") == "assistant":
                    open_reply = False
                elif typ == "tool_execution_start":
                    running_tool = {"name": ev.get("toolName"), "what": describe_call(str(ev.get("toolName")), ev.get("args"))}
                elif typ == "tool_execution_end":
                    running_tool = None
                elif typ == "compaction_start":
                    compaction = True
                elif typ == "compaction_end":
                    compaction = False
            if compaction:
                out["doing"] = "summarizing the conversation"
            elif open_reply:
                out["doing"] = "writing a reply"
                out["detail"] = {"thinking_chars": thinking, "text_chars": text, "tool_call_chars": toolcall}
            elif running_tool:
                out["doing"] = "running a tool"
                out["detail"] = running_tool
            else:
                out["doing"] = "between steps"
        session = self._session_files(run)
        if session:
            try:
                with session[-1].open("rb") as handle:
                    size = session[-1].stat().st_size
                    handle.seek(max(0, size - 200_000))
                    lines = handle.read().decode("utf-8", "replace").splitlines()
                for line in reversed(lines):
                    try:
                        e = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    out["last_saved"] = iso_ms(e.get("timestamp"))
                    break
            except OSError:
                pass
        return out

    # ---------------------------------------------------------------- overview and batches

    def overview(self) -> dict[str, Any]:
        locks = read_locks()
        runs = []
        for rid in self.run_ids():
            try:
                runs.append(self.summary(rid, locks))
            except DataError:
                continue
        batches: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for r in runs:
            batches[r["batch"]].append(r)
        cards = []
        for key in sorted(batches, key=self.batch_order):
            rs = batches[key]
            docs = self.batch_docs(key)
            starts = [r["started_at"] for r in rs if r["started_at"]]
            ends = [r["ended_at"] for r in rs if r["ended_at"]]
            finals = [r for r in rs if isinstance(r["final"], (int, float))]
            best = max(finals, key=lambda r: r["final"]) if finals else None
            cards.append({
                "key": key, "title": docs["title"], "subtitle": docs["subtitle"], "docs": docs,
                "runs": len(rs), "main": sum(1 for r in rs if r["profile"] == "main"),
                "pilot": sum(1 for r in rs if r["profile"] == "pilot"),
                "running": sum(1 for r in rs if r["status"] in ("running", "scoring")),
                "interrupted": sum(1 for r in rs if r["status"] == "interrupted"),
                "tasks": sorted({r["task"] for r in rs}),
                "studies": sorted({r["study"] for r in rs if r["study"]}),
                "variants": sorted({r["variant"] for r in rs if r["variant"]}),
                "first_start": min(starts) if starts else None, "last_end": max(ends) if ends else None,
                "dots": [[r["variant"], r["repeat"], r["final"], r["id"], r["profile"], r["status"]] for r in rs],
                "best": {"id": best["id"], "score": best["final"]} if best else None,
                "server": sorted({r["server"] for r in rs if r["server"]}),
            })
        live = [r for r in runs if r["status"] in ("running", "scoring")]
        return {"batches": cards, "live": live, "runs": len(runs), "server": self.server_status(),
                "warm": dict(self.warm), "tokenizer": self.tokenizer_note(),
                "generated_at": time.time() * 1000}

    def runs_index(self) -> list[dict[str, Any]]:
        locks = read_locks()
        out = []
        for rid in self.run_ids():
            try:
                s = self.summary(rid, locks)
            except DataError:
                continue
            out.append({k: s.get(k) for k in ("id", "batch", "study", "variant", "repeat", "profile", "task",
                                               "language", "status", "final", "visible_final", "started_at",
                                               "rounds", "end_reason")})
        return out

    def study_order(self, study_path: str | None, study_id: str | None) -> list[str]:
        """Variant order as the study manifest lists its conditions."""
        order: list[str] = []
        summary = read_json(self.runs_dir / "study-results" / str(study_id) / "summary.json") if study_id else None
        if isinstance(summary, dict):
            order = [c.get("id") for c in ((summary.get("study") or {}).get("conditions") or []) if isinstance(c, dict)]
        if not order and study_path:
            manifest = read_json(self.root / study_path)
            if isinstance(manifest, dict):
                order = [c.get("id") for c in manifest.get("conditions") or [] if isinstance(c, dict)]
        return [o for o in order if o]

    def batch(self, key: str) -> dict[str, Any]:
        locks = read_locks()
        ids = [rid for rid in self.run_ids() if self.batch_of(rid) == key]
        if not ids:
            raise DataError(f"no batch called {key!r}")
        runs = {}
        for rid in ids:
            s = self.summary(rid, locks)
            try:
                s["totals"] = self.totals(rid)
            except Exception as error:  # noqa: BLE001 - keep the page usable
                s["totals"] = None
                s["totals_error"] = str(error)
            try:
                s["code"] = self.files_totals(rid)
            except Exception as error:  # noqa: BLE001
                s["code"] = None
                s["code_error"] = str(error)
            s["final_tests"] = self.final_tests(rid)
            r = self.reasoning(rid, start=False)
            s["reasoning"] = {"status": r["status"], "total": r.get("total")} if r["status"] == "ready" else {"status": r["status"]}
            runs[rid] = s
        studies: dict[str, dict[str, Any]] = {}
        for rid, s in runs.items():
            sid = s["study"] or "(no study)"
            st = studies.setdefault(sid, {"id": sid, "task": s["task"], "runs": [], "variants": {}})
            st["runs"].append(rid)
            if s["variant"] not in st["variants"]:
                st["variants"][s["variant"]] = {"id": s["variant"], "description": s["variant_description"],
                                                "factor": s["factor"]}
        out_studies = []
        for sid, st in studies.items():
            sm = read_json(self.runs_dir / st["runs"][0] / "study-metadata.json") or {}
            order = self.study_order(sm.get("study_path"), sid)
            variants = sorted(st["variants"].values(),
                              key=lambda v: (order.index(v["id"]) if v["id"] in order else len(order), v["id"]))
            out_studies.append({"id": sid, "task": st["task"], "variants": variants,
                                "runs": sorted(st["runs"], key=lambda rid: (
                                    [v["id"] for v in variants].index(runs[rid]["variant"]),
                                    runs[rid]["profile"] != "main", runs[rid]["repeat"] or 0, rid))})
        out_studies.sort(key=lambda st: min((runs[r]["started_at"] or "") for r in st["runs"]))
        return {"key": key, "docs": self.batch_docs(key), "studies": out_studies, "runs": runs,
                "tokenizer": self.tokenizer_note()}

    # ---------------------------------------------------------------- documents

    DOC_GROUPS = (
        ("Reports", "docs/REPORT_*.md"),
        ("Batch results", "analysis/*results*.md"),
        ("Campaign write-up and analyses", "analysis/*.md"),
        ("Experiment plans", "docs/EXPERIMENT_PLAN*.md"),
        ("Study summaries", "runs/study-results/*/summary.md"),
        ("Other documents", "docs/*.md"),
    )

    def docs(self) -> list[dict[str, Any]]:
        seen: set[str] = set()
        groups = []
        for title, pattern in self.DOC_GROUPS:
            items = []
            for p in sorted(self.root.glob(pattern), reverse=title == "Reports"):
                rel = str(p.relative_to(self.root))
                if rel in seen or not p.is_file():
                    continue
                seen.add(rel)
                head = ""
                for line in (read_text(p, 2000) or "").splitlines():
                    if line.startswith("#"):
                        head = line.lstrip("#").strip()
                        break
                items.append({"path": rel, "title": head or p.name, "bytes": p.stat().st_size,
                              "modified": p.stat().st_mtime * 1000})
            if title == "Experiment plans":
                def plan_key(item: dict[str, Any]) -> int:
                    m = re.search(r"_v(\d+)\.md$", item["path"])
                    return -(int(m.group(1)) if m else 3)
                items.sort(key=plan_key)
            groups.append({"title": title, "items": items})
        return groups

    def doc(self, path: str) -> dict[str, Any]:
        rel = self._clean_path(path)
        if not rel.endswith(".md"):
            raise DataError("only Markdown documents can be shown")
        allowed = (rel.startswith(("docs/", "analysis/", "runs/study-results/"))
                   or re.fullmatch(r"runs/[A-Za-z0-9][A-Za-z0-9._-]*/report\.md", rel) is not None)
        if not allowed:
            raise DataError("that document is not available here")
        full = (self.root / rel).resolve()
        if self.root not in full.parents or not full.is_file():
            raise DataError("document not found")
        return {"path": rel, "text": read_text(full, 5_000_000) or "", "modified": full.stat().st_mtime * 1000}

    # ---------------------------------------------------------------- model server

    def server_status(self) -> dict[str, Any]:
        inf = self.runs_dir / "inference"
        out: dict[str, Any] = {"running": False, "pid": None, "launch": None}
        try:
            out["launch"] = os.readlink(inf / "current")
        except OSError:
            pass
        text = read_text(inf / "server.pid")
        if text and text.strip().isdigit():
            pid = int(text.strip())
            out["pid"] = pid
            out["running"] = Path(f"/proc/{pid}").is_dir()
        return out

    def server_launches(self) -> dict[str, Any]:
        inf = self.runs_dir / "inference"
        launches = []
        if inf.is_dir():
            for d in sorted((p for p in inf.iterdir() if p.is_dir() and not p.is_symlink()), reverse=True):
                info: dict[str, str] = {}
                for line in (read_text(d / "launch.txt", 20_000) or "").splitlines():
                    if "=" in line:
                        k, _, v = line.partition("=")
                        v = v.strip()
                        plain = v.lower() in ("yes", "no", "true", "false", "0", "1")
                        info[k.strip()] = "[hidden]" if is_secret_name(k) and not plain else v
                config = read_text(d / "config.yaml", 50_000) or ""
                config = "\n".join(
                    (line.split(":", 1)[0] + ": [hidden]") if ":" in line and is_secret_name(line.split(":", 1)[0]) else line
                    for line in config.splitlines())
                log = d / "server.log"
                launches.append({"name": d.name, "info": info, "config": config,
                                 "log_bytes": log.stat().st_size if log.is_file() else None})
        return {"status": self.server_status(), "launches": launches,
                "doc": "docs/INFERENCE_SGLANG.md" if (self.root / "docs" / "INFERENCE_SGLANG.md").is_file() else None}
