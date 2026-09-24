"""The agent's conversation, page by page and entry by entry, search, and
reasoning tokens counted with the model's own tokenizer.
"""

from __future__ import annotations

import json
import os
import re
import threading
from pathlib import Path
from typing import Any

from .records import (
    TEXT_CAP,
    blocks,
    cap_text,
    DataError,
    fingerprint,
    iso_ms,
    joined_text,
)


class ConversationMixin:
    # ---------------------------------------------------------------- conversation

    def conversation(self, run_id: str, round_no: int | None) -> dict[str, Any]:
        run = self.run_dir(run_id)
        s = self._session(run)
        entries, windows, index, t0 = s["entries"], s["windows"], s["index"], s["t0"]
        rounds = [w["round"] for w in windows] or [0]
        if round_no is None:
            round_no = rounds[0]
        if round_no not in rounds:
            raise DataError(f"run {run_id} has no round {round_no}")
        out = []
        prev: float | None = None
        for k, e in enumerate(entries):
            saved = iso_ms(e.get("timestamp"))
            belongs = (windows[index[k]]["round"] if windows else 0) == round_no
            if belongs:
                item = self._display(k, e, prev, t0)
                if item is not None:
                    out.append(item)
            if saved is not None:
                prev = saved
        return {"round": round_no, "rounds": rounds, "t0": t0, "entries": out}

    def entry(self, run_id: str, k: int) -> dict[str, Any]:
        run = self.run_dir(run_id)
        s = self._session(run)
        entries = s["entries"]
        if not 0 <= k < len(entries):
            raise DataError(f"run {run_id} has no entry {k}")
        prev = None
        for e in reversed(entries[:k]):
            prev = iso_ms(e.get("timestamp"))
            if prev is not None:
                break
        item = self._display(k, entries[k], prev, s["t0"], cap=10_000_000)
        return item or {}

    def _display(self, k: int, e: dict[str, Any], prev: float | None, t0: float,
                 cap: int = TEXT_CAP) -> dict[str, Any] | None:
        saved = iso_ms(e.get("timestamp"))
        typ = e.get("type")

        def text_field(value: str) -> dict[str, Any]:
            text, full = cap_text(value, cap)
            return {"text": text, "full": full}

        if typ == "message":
            m = e.get("message") or {}
            role = m.get("role")
            if role == "assistant":
                start = float(m["timestamp"]) if isinstance(m.get("timestamp"), (int, float)) else saved
                usage = m.get("usage") or {}
                thinking = "".join(str(b.get("thinking") or "") for b in blocks(m) if b.get("type") == "thinking")
                text = "".join(str(b.get("text") or "") for b in blocks(m) if b.get("type") == "text")
                calls = []
                for b in blocks(m):
                    if b.get("type") != "toolCall":
                        continue
                    args = b.get("arguments")
                    shown: Any = args
                    cut = None
                    if isinstance(args, dict):
                        shown = {}
                        for key, value in args.items():
                            if isinstance(value, str) and len(value) > cap:
                                shown[key] = value[:cap]
                                cut = max(cut or 0, len(value))
                            else:
                                shown[key] = value
                    calls.append({"id": b.get("id"), "name": b.get("name"), "args": shown, "full": cut})
                return {
                    "k": k, "kind": "reply", "t": start, "saved": saved,
                    "d": round(max(0.0, (saved or 0) - (start or 0)) / 1000, 1),
                    "in": int(usage.get("input") or 0) + int(usage.get("cacheRead") or 0),
                    "c": int(usage.get("cacheRead") or 0), "out": int(usage.get("output") or 0),
                    "stop": m.get("stopReason"), "error": m.get("errorMessage"),
                    "thinking": text_field(thinking), "text": text_field(text), "calls": calls,
                }
            if role == "toolResult":
                return {
                    "k": k, "kind": "result", "t": saved, "id": m.get("toolCallId"), "name": m.get("toolName"),
                    "err": bool(m.get("isError")), "d": round(max(0.0, (saved or 0) - (prev or saved or 0)) / 1000, 1),
                    **text_field(joined_text(m)),
                }
            if role == "user":
                return {"k": k, "kind": "prompt", "t": saved, **text_field(joined_text(m))}
            return {"k": k, "kind": "note", "t": saved, "text": f"{role} message", "full": None}
        if typ == "compaction":
            usage = e.get("usage") or {}
            return {
                "k": k, "kind": "summary", "t": saved,
                "d": round(max(0.0, (saved or 0) - (prev or saved or 0)) / 1000, 1),
                "before": e.get("tokensBefore"), "written": int(usage.get("output") or 0),
                **text_field(str(e.get("summary") or "")),
            }
        if typ == "model_change":
            return {"k": k, "kind": "note", "t": saved, "text": f"model set to {e.get('modelId')} ({e.get('provider')})", "full": None}
        if typ == "thinking_level_change":
            return {"k": k, "kind": "note", "t": saved, "text": f"thinking level set to {e.get('thinkingLevel')}", "full": None}
        if typ in ("session", "session_info"):
            return None
        return {"k": k, "kind": "note", "t": saved, "text": str(typ), "full": None}

    def search(self, run_id: str, query: str, limit: int = 300) -> dict[str, Any]:
        run = self.run_dir(run_id)
        q = query.strip().lower()
        if len(q) < 2:
            raise DataError("search needs at least 2 characters")
        s = self._session(run)
        hits = []
        total = 0
        for k, e in enumerate(s["entries"]):
            fields: list[tuple[str, str]] = []
            typ = e.get("type")
            if typ == "message":
                m = e.get("message") or {}
                role = m.get("role")
                for b in blocks(m):
                    if b.get("type") == "thinking":
                        fields.append(("thinking", str(b.get("thinking") or "")))
                    elif b.get("type") == "text":
                        fields.append(("result" if role == "toolResult" else ("prompt" if role == "user" else "reply"), str(b.get("text") or "")))
                    elif b.get("type") == "toolCall":
                        fields.append((f"call {b.get('name')}", json.dumps(b.get("arguments"), ensure_ascii=False)))
            elif typ == "compaction":
                fields.append(("summary", str(e.get("summary") or "")))
            for where, text in fields:
                low = text.lower()
                at = low.find(q)
                if at < 0:
                    continue
                total += low.count(q)
                if len(hits) < limit:
                    a = max(0, at - 90)
                    b = min(len(text), at + len(q) + 90)
                    hits.append({"k": k, "r": s["windows"][s["index"][k]]["round"] if s["windows"] else 0,
                                 "where": where, "before": text[a:at], "match": text[at:at + len(q)],
                                 "after": text[at + len(q):b]})
        return {"query": query, "hits": hits, "total": total, "shown": len(hits)}

    # ---------------------------------------------------------------- reasoning tokens

    def tokenizer(self) -> Any:
        with self._tokenizer_lock:
            if self._tokenizer_state == "untried":
                self._tokenizer_state = "missing"
                if self.tokenizer_path and self.tokenizer_path.is_file():
                    os.environ.setdefault("RAYON_NUM_THREADS", "4")
                    os.environ.setdefault("RAYON_RS_NUM_CPUS", "4")
                    try:
                        from tokenizers import Tokenizer  # type: ignore[import-not-found]
                        self._tokenizer = Tokenizer.from_file(str(self.tokenizer_path))
                        self._tokenizer_state = "ready"
                    except Exception:  # noqa: BLE001 - optional dependency
                        self._tokenizer = None
            return self._tokenizer

    def tokenizer_note(self) -> str:
        if self.tokenizer() is not None:
            return "counted with the model's own tokenizer"
        if not self.tokenizer_path or not self.tokenizer_path.is_file():
            return "not counted: the model's tokenizer file is not on this machine"
        return "not counted: start the dashboard with the SGLang Python (make dashboard does this)"

    def _events(self, run: Path) -> list[Path]:
        return sorted((run / "artifacts" / "events").glob("round-*.jsonl"))

    def reasoning(self, run_id: str, start: bool = True) -> dict[str, Any]:
        run = self.run_dir(run_id)
        fp = fingerprint(self._events(run))
        found = self.store.peek("reasoning", run_id, fp)
        if found is not None:
            return {"status": "ready", **found}
        if self.tokenizer() is None:
            return {"status": "unavailable", "note": self.tokenizer_note()}
        with self._job_lock:
            if run_id in self._job_errors:
                return {"status": "failed", "note": self._job_errors[run_id]}
            if start and run_id not in self._queued:
                self._queued.add(run_id)
                self._jobs.put(run_id)
                self._ensure_worker()
        return {"status": "counting"}

    def _ensure_worker(self) -> None:
        if getattr(self, "_worker", None) is not None and self._worker.is_alive():
            return
        self._worker = threading.Thread(target=self._work, name="reasoning-counter", daemon=True)
        self._worker.start()

    def _work(self) -> None:
        while True:
            run_id = self._jobs.get()
            try:
                self.count_reasoning(run_id)
            except Exception as error:  # noqa: BLE001 - reported to the page
                with self._job_lock:
                    self._job_errors[run_id] = f"counting failed: {error}"
            finally:
                with self._job_lock:
                    self._queued.discard(run_id)

    def count_reasoning(self, run_id: str) -> dict[str, Any]:
        run = self.run_dir(run_id)
        tok = self.tokenizer()
        if tok is None:
            raise DataError(self.tokenizer_note())
        fp = fingerprint(self._events(run))

        def compute() -> dict[str, Any]:
            texts: list[str] = []
            outs: list[int] = []
            rounds: list[int] = []
            for path in self._events(run):
                m = re.search(r"round-(\d+)", path.name)
                rnd = int(m.group(1)) if m else 0
                parts: list[str] = []
                with path.open("r", encoding="utf-8", errors="replace") as handle:
                    for line in handle:
                        if '"thinking_delta"' in line:
                            try:
                                ev = json.loads(line)
                            except json.JSONDecodeError:
                                continue
                            upd = ev.get("assistantMessageEvent") or {}
                            if upd.get("type") == "thinking_delta":
                                parts.append(str(upd.get("delta") or ""))
                            continue
                        if '"message_end"' not in line:
                            continue
                        try:
                            ev = json.loads(line)
                        except json.JSONDecodeError:
                            continue
                        if ev.get("type") != "message_end":
                            continue
                        msg = ev.get("message") or {}
                        if msg.get("role") == "assistant":
                            texts.append("".join(parts))
                            outs.append(int((msg.get("usage") or {}).get("output") or 0))
                            rounds.append(rnd)
                        parts = []
            counts = [0] * len(texts)
            nonempty = [i for i, t in enumerate(texts) if t]
            for start in range(0, len(nonempty), 64):
                chunk = nonempty[start:start + 64]
                encoded = tok.encode_batch([texts[i] for i in chunk], add_special_tokens=False)
                for i, enc in zip(chunk, encoded):
                    counts[i] = len(enc.ids)
            return {"per_reply": counts, "outs": outs, "rounds": rounds, "total": sum(counts),
                    "chars": sum(len(t) for t in texts)}

        value = self.store.get("reasoning", run_id, fp, compute)
        return value
