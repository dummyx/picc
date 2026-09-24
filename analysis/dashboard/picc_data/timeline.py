"""Where a run's time went: the session file split into replies, tool calls,
conversation summaries and gaps, round by round.
"""

from __future__ import annotations

import bisect
import time
from collections import Counter
from pathlib import Path
from typing import Any

from .classify import describe_call, error_line, shell_kinds, why_failed
from .records import (
    blocks,
    fingerprint,
    iso_ms,
    joined_text,
    jsonl,
    median,
    read_json,
    read_locks,
)


class TimelineMixin:
    # ---------------------------------------------------------------- session

    def _session_files(self, run: Path) -> list[Path]:
        return sorted((run / "artifacts" / "sessions").glob("*.jsonl"))

    def _digest_paths(self, run: Path) -> list[Path]:
        art = run / "artifacts"
        return self._session_files(run) + [run / "metadata.json", art / "rounds.jsonl", art / "guard.jsonl",
                                           art / "extension-events.jsonl", run / ".harness.lock"]

    def _session(self, run: Path) -> dict[str, Any]:
        """Parsed session entries plus the round each one belongs to."""
        fp = fingerprint(self._digest_paths(run))

        def compute() -> dict[str, Any]:
            entries: list[dict[str, Any]] = []
            for path in self._session_files(run):
                entries += jsonl(path)
            meta = read_json(run / "metadata.json") or {}
            rounds = jsonl(run / "artifacts" / "rounds.jsonl")
            live = self._liveness(run, {"meta_status": meta.get("status")}, read_locks())["status"] == "running"
            windows = self._windows(rounds, entries, live)
            starts = [w["start"] for w in windows]
            index = []
            for e in entries:
                saved = iso_ms(e.get("timestamp"))
                m = e.get("message") if e.get("type") == "message" else None
                key = saved
                if m and m.get("role") == "assistant" and isinstance(m.get("timestamp"), (int, float)):
                    key = float(m["timestamp"])
                if key is None or not windows:
                    index.append(0)
                else:
                    index.append(max(0, bisect.bisect_right(starts, key + 1000) - 1))
            t0 = iso_ms(meta.get("started_at")) or (windows[0]["start"] if windows else
                                                    (iso_ms(entries[0].get("timestamp")) if entries else 0.0)) or 0.0
            return {"entries": entries, "windows": windows, "index": index, "t0": t0, "live": live}

        return self.store.get("session", run.name, fp, compute, disk=False)

    @staticmethod
    def _windows(rounds: list[dict[str, Any]], entries: list[dict[str, Any]], live: bool) -> list[dict[str, Any]]:
        windows: list[dict[str, Any]] = []
        for r in rounds:
            start = iso_ms(r.get("started_at"))
            if start is None:
                continue
            end = iso_ms(r.get("ended_at")) or start
            windows.append({"round": int(r.get("round", len(windows))), "start": start, "end": end,
                            "open": False, "capped": bool(r.get("timed_out")), "returncode": r.get("returncode")})
        stamps = [t for t in (iso_ms(e.get("timestamp")) for e in entries) if t is not None]
        if not stamps:
            return windows
        last_end = windows[-1]["end"] if windows else None
        if last_end is None or max(stamps) > last_end + 5000:
            prompts = [iso_ms(e.get("timestamp")) for e in entries
                       if e.get("type") == "message" and (e.get("message") or {}).get("role") == "user"]
            prompts = [p for p in prompts if p is not None and (last_end is None or p >= last_end - 1000)]
            start = prompts[-1] if prompts else (last_end if last_end is not None else min(stamps))
            end = time.time() * 1000 if live else max(stamps)
            windows.append({"round": windows[-1]["round"] + 1 if windows else 0, "start": start, "end": end,
                            "open": True, "capped": False, "returncode": None})
        return windows

    # ---------------------------------------------------------------- digest

    def digest(self, run_id: str) -> dict[str, Any]:
        run = self.run_dir(run_id)
        fp = fingerprint(self._digest_paths(run))
        return self.store.get("digest", run_id, fp, lambda: self._digest(run))

    def totals(self, run_id: str, compute: bool = True) -> dict[str, Any] | None:
        run = self.run_dir(run_id)
        fp = fingerprint(self._digest_paths(run))
        if not compute:
            return self.store.peek("totals", run_id, fp)
        return self.store.get("totals", run_id, fp, lambda: self.digest(run_id)["totals"])

    def _digest(self, run: Path) -> dict[str, Any]:
        s = self._session(run)
        entries, windows, index, t0 = s["entries"], s["windows"], s["index"], s["t0"]
        art = run / "artifacts"

        def rel(ms: float | None) -> float | None:
            return None if ms is None else round((ms - t0) / 1000, 1)

        last = [w["start"] for w in windows]
        split = [{"model": 0.0, "tools": 0.0, "summaries": 0.0, "startup": 0.0, "lost": 0.0} for _ in windows]
        replies: list[dict[str, Any]] = []
        calls: list[dict[str, Any]] = []
        summaries: list[dict[str, Any]] = []
        prompts: list[dict[str, Any]] = []
        segments: list[list[Any]] = []
        pending: dict[str, dict[str, Any]] = {}
        bytes_written = 0
        for k, e in enumerate(entries):
            saved = iso_ms(e.get("timestamp"))
            if saved is None:
                continue
            typ = e.get("type")
            m = e.get("message") if typ == "message" else None
            role = (m or {}).get("role")
            i = index[k] if windows else 0
            rnd = windows[i]["round"] if windows else 0
            since = last[i] if windows else saved
            if role == "assistant":
                start = float(m["timestamp"]) if isinstance(m.get("timestamp"), (int, float)) else saved
                dur = max(0.0, saved - start)
                if windows:
                    split[i]["model"] += dur
                    split[i]["startup"] += max(0.0, start - since)
                if start - since > 20_000:
                    # nothing saved for a while before this reply began: start-up,
                    # a retried request, or waiting on the model server
                    segments.append([rel(since), rel(start), "gap", k])
                segments.append([rel(start), rel(saved), "model", k])
                usage = m.get("usage") or {}
                content = blocks(m)
                tool_blocks = [b for b in content if b.get("type") == "toolCall"]
                replies.append({
                    "k": k, "r": rnd, "t": rel(start), "d": round(dur / 1000, 1),
                    "in": int(usage.get("input") or 0) + int(usage.get("cacheRead") or 0),
                    "c": int(usage.get("cacheRead") or 0),
                    "out": int(usage.get("output") or 0),
                    "stop": m.get("stopReason"),
                    "tools": [b.get("name") for b in tool_blocks],
                    "tc": sum(len(str(b.get("thinking") or "")) for b in content if b.get("type") == "thinking"),
                    "xc": sum(len(str(b.get("text") or "")) for b in content if b.get("type") == "text"),
                })
                for b in tool_blocks:
                    name = str(b.get("name") or "?")
                    args = b.get("arguments") if isinstance(b.get("arguments"), dict) else {}
                    cmd = describe_call(name, args)
                    call = {"k": None, "rk": k, "r": rnd, "t": None, "name": name, "d": None, "err": None,
                            "why": None, "msg": None, "cmd": cmd,
                            "kinds": shell_kinds(str(args.get("command") or "")) if name == "bash" else None,
                            "out": 0}
                    if name == "write":
                        bytes_written += len(str(args.get("content") or ""))
                    if name == "edit":
                        edits = args.get("edits") if isinstance(args.get("edits"), list) else [args]
                        call["lines"] = [
                            sum(str(x.get("newText") or x.get("new_string") or "").count("\n") + 1 for x in edits if isinstance(x, dict)),
                            sum(str(x.get("oldText") or x.get("old_string") or "").count("\n") + 1 for x in edits if isinstance(x, dict)),
                        ]
                    calls.append(call)
                    pending[str(b.get("id"))] = call
            elif role == "toolResult":
                dur = max(0.0, saved - since)
                if windows:
                    split[i]["tools"] += dur
                segments.append([rel(since), rel(saved), "tool", k])
                text = joined_text(m)
                call = pending.pop(str(m.get("toolCallId")), None)
                if call is None:
                    call = {"k": None, "rk": None, "r": rnd, "t": None, "name": str(m.get("toolName") or "?"),
                            "d": None, "err": None, "why": None, "msg": None, "cmd": "", "kinds": None, "out": 0}
                    calls.append(call)
                call.update(k=k, t=rel(saved), d=round(dur / 1000, 1), err=bool(m.get("isError")), out=len(text))
                if call["err"]:
                    call["why"] = why_failed(call["name"], text)
                    call["msg"] = error_line(text)
            elif typ == "compaction":
                dur = max(0.0, saved - since)
                if windows:
                    split[i]["summaries"] += dur
                segments.append([rel(since), rel(saved), "summary", k])
                usage = e.get("usage") or {}
                summaries.append({
                    "k": k, "r": rnd, "t": rel(saved), "d": round(dur / 1000, 1),
                    "before": e.get("tokensBefore"),
                    "written": int(usage.get("output") or 0),
                    "read": int(usage.get("input") or 0) + int(usage.get("cacheRead") or 0),
                    "chars": len(str(e.get("summary") or "")),
                })
            elif typ == "message":
                if windows:
                    split[i]["startup"] += max(0.0, saved - since)
                if role == "user":
                    text = joined_text(m)
                    prompts.append({"k": k, "r": rnd, "t": rel(saved), "chars": len(text), "head": text.strip()[:200]})
            elif windows:
                split[i]["startup"] += max(0.0, saved - since)
            if windows:
                last[i] = max(last[i], saved)

        live = s["live"]
        for i, w in enumerate(windows):
            if w["open"] and live:
                continue
            lost = max(0.0, w["end"] - last[i])
            split[i]["lost"] = lost
            if lost > 1000:
                segments.append([rel(last[i]), rel(w["end"]), "lost", None])
        segments.sort(key=lambda seg: (seg[0] if seg[0] is not None else 0))

        guard = []
        for g in jsonl(art / "guard.jsonl"):
            guard.append({
                "t": rel(iso_ms(g.get("timestamp"))),
                "event": g.get("event"),
                "tool": g.get("toolName"),
                "reason": g.get("reason"),
                "what": str(g.get("subject") or "")[:600],
                "id": g.get("toolCallId"),
            })
        by_call_id: dict[str, int] = {}
        for k, e in enumerate(entries):
            m = e.get("message") if e.get("type") == "message" else None
            if m and m.get("role") == "toolResult":
                by_call_id[str(m.get("toolCallId"))] = k
        for g in guard:
            g["k"] = by_call_id.get(str(g.get("id")))
        ext = jsonl(art / "extension-events.jsonl")
        ext_counts = Counter(str(x.get("event")) for x in ext)

        per_round = []
        for i, w in enumerate(windows):
            rr = [r for r in replies if r["r"] == w["round"]]
            rc = [c for c in calls if c["r"] == w["round"]]
            per_round.append({
                "round": w["round"], "start": rel(w["start"]), "end": rel(w["end"]), "open": w["open"],
                "capped": w["capped"], "returncode": w["returncode"],
                "time": {k: round(v / 1000, 1) for k, v in split[i].items()},
                "replies": len(rr), "calls": len(rc), "failed": sum(1 for c in rc if c["err"]),
                "summaries": sum(1 for x in summaries if x["r"] == w["round"]),
                "out": sum(r["out"] for r in rr), "in": sum(r["in"] for r in rr),
            })

        outs = [r["out"] for r in replies]
        ins = [r["in"] for r in replies]
        model_s = sum(r["d"] for r in replies)
        by_tool: dict[str, dict[str, Any]] = {}
        for c in calls:
            t = by_tool.setdefault(c["name"], {"calls": 0, "failed": 0, "seconds": 0.0, "no_result": 0})
            t["calls"] += 1
            t["failed"] += 1 if c["err"] else 0
            t["no_result"] += 1 if c["k"] is None else 0
            t["seconds"] += c["d"] or 0.0
        for t in by_tool.values():
            t["seconds"] = round(t["seconds"], 1)
        shell = [c for c in calls if c["name"] == "bash"]
        shell_by: dict[str, dict[str, Any]] = {}
        shell_any: Counter[str] = Counter()
        for c in shell:
            kinds = c["kinds"] or ["other"]
            shell_any.update(kinds)
            row = shell_by.setdefault(kinds[0], {"calls": 0, "seconds": 0.0})
            row["calls"] += 1
            row["seconds"] = round(row["seconds"] + (c["d"] or 0.0), 1)
        edits = [c for c in calls if c["name"] == "edit"]
        totals = {
            "replies": len(replies),
            "stops": dict(Counter(str(r["stop"]) for r in replies)),
            "out": sum(outs), "in": sum(ins), "cached": sum(r["c"] for r in replies),
            "conv_max": max(ins, default=0), "conv_median": median(ins),
            "out_median": median(outs), "out_max": max(outs, default=0),
            "model_s": round(model_s, 1),
            "tokens_per_min": round(sum(outs) / (model_s / 60)) if model_s > 0 else None,
            "calls": len(calls),
            "failed": sum(1 for c in calls if c["err"]),
            "no_result": sum(1 for c in calls if c["k"] is None),
            "by_tool": dict(sorted(by_tool.items(), key=lambda kv: -kv[1]["calls"])),
            "why_failed": dict(Counter(c["why"] for c in calls if c["err"]).most_common()),
            "shell": {
                "calls": len(shell),
                "by_kind": dict(sorted(shell_by.items(), key=lambda kv: -kv[1]["calls"])),
                "any_kind": dict(shell_any.most_common()),
                "long": sum(1 for c in shell if (c["d"] or 0) >= 118),
                "slowest_s": max((c["d"] or 0 for c in shell), default=0),
            },
            "files": {
                "writes": by_tool.get("write", {}).get("calls", 0),
                "edits": len(edits),
                "failed_edits": sum(1 for c in edits if c["err"]),
                "reads": by_tool.get("read", {}).get("calls", 0),
                "chars_written": bytes_written,
            },
            "summaries": len(summaries),
            "summary_s": round(sum(x["d"] for x in summaries), 1),
            "summary_written": sum(x["written"] for x in summaries),
            "summary_before_median": median([float(x["before"]) for x in summaries if x["before"]]),
            "prompts": len(prompts),
            "cut_off": sum(1 for r in replies if r["stop"] == "length"),
            "ended_turn": sum(1 for r in replies if r["stop"] == "stop"),
            "reply_errors": sum(1 for r in replies if r["stop"] in ("error", "aborted")),
            "blocked": sum(1 for g in guard if g["event"] == "blocked_tool_call"),
            "guard_events": len(guard),
            "repaired": ext_counts.get("truncation_repaired", 0),
            "ext": dict(ext_counts),
            "time": {k: round(sum(sp[k] for sp in split) / 1000, 1) for k in ("model", "tools", "summaries", "startup", "lost")},
            "wall_s": round(sum(max(0.0, w["end"] - w["start"]) for w in windows) / 1000, 1),
        }
        unfinished = [{"k": r["k"], "r": r["r"], "t": r["t"], "stop": r["stop"], "d": r["d"], "out": r["out"],
                       "head": self._reply_head(entries[r["k"]])} for r in replies if r["stop"] != "toolUse"]
        return {
            "t0": t0,
            "rounds": per_round,
            "replies": replies,
            "calls": calls,
            "summaries": summaries,
            "prompts": prompts,
            "segments": segments,
            "guard": guard,
            "unfinished": unfinished,
            "totals": totals,
        }

    @staticmethod
    def _reply_head(entry: dict[str, Any]) -> str:
        m = entry.get("message") or {}
        text = "".join(str(b.get("text") or "") for b in blocks(m) if b.get("type") == "text").strip()
        if not text:
            thinking = "".join(str(b.get("thinking") or "") for b in blocks(m) if b.get("type") == "thinking").strip()
            return ("(thinking only) " + thinking[:200]) if thinking else "(empty reply)"
        return text[:240]
