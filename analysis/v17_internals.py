#!/usr/bin/env python3
"""v17 batch: what the coding agent actually did, run by run.

Everything here is measured from the raw records of each run, not taken from
earlier write-ups:

- the Pi session file (`artifacts/sessions/*.jsonl`): every message with two
  timestamps -- when the model started a reply (`message.timestamp`) and when
  the reply was saved (`entry.timestamp`) -- so time splits exactly into
  "model generating" and "tool running";
- the Pi event stream (`artifacts/events/round-*.jsonl`): the reasoning text as
  it was streamed, which survives even for replies that were later cut down by
  truncation-repair.ts, and the token usage the server reported;
- the harness ledgers (`rounds.jsonl`, `snapshots.jsonl`, `hidden-scores.jsonl`,
  `extension-events.jsonl`, `guard.jsonl`) and the per-script evaluator
  records (`evaluations/*.json`);
- the final workspace: the files the agent left behind.

Reasoning tokens are counted by tokenizing the streamed reasoning with the
served checkpoint's own tokenizer, because the run records hold 0 for them
(SGLang reports `usage.reasoning_tokens`, Pi reads
`completion_tokens_details.reasoning_tokens`). That needs the `tokenizers`
package; run with the SGLang venv's Python to get those columns:

    .venv-sglang/bin/python analysis/v17_internals.py

Writes analysis/v17-internals.json. Read-only over runs/.
"""

from __future__ import annotations

import json
import re
import statistics
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
PREFIX = "v17-sql-"
ORDER = ("python", "python-typed", "javascript", "typescript", "rust")
BUDGET = 8192
TOKENIZER = Path.home() / "models" / "Qwen3.8-27B-NVFP4" / "tokenizer.json"

# --------------------------------------------------------------------------
# helpers


def jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def iso_ms(value: str) -> float:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp() * 1000


def pct(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(q * len(ordered)))]


def med(values: list[float]) -> float:
    return statistics.median(values) if values else 0.0


# --------------------------------------------------------------------------
# shell command classification


def bash_labels(command: str) -> set[str]:
    """What a shell command did. A command can do several things at once."""
    c = command
    labels: set[str] = set()
    if re.search(r"\bmypy\b|\btsc\b|cargo (build|check|clippy)|py_compile|node --check", c):
        labels.add("type-check or build")
    if re.search(r"python3?(\s+-\w+)*\s+(\S*/)?pisql\.py(?=[\s<;|&)]|$)"
                 r"|node\s+(\S*/)?(src|dist)/pisql\.js(?=[\s<;|&)]|$)"
                 r"|(\./)?target/(release|debug)/pisql(?=[\s<;|&)]|$)|cargo run", c):
        labels.add("run own engine on SQL")
    if re.search(r"import pisql|from pisql|require\(['\"]\./(src|dist)/pisql", c):
        labels.add("probe engine internals")
    if re.search(r"(run|test)[\w-]*\.sh|test_\w+\.py|review\.py|for \w+ in [^;]*\.sql", c):
        labels.add("run own test script")
    if re.search(r"cat\s*>>?\s*\S*(pisql|src/)\S*\.(ts|js|py|rs)\s*<<", c):
        labels.add("write source via shell")
    if re.search(r"\.(py|ts|js|rs)['\"]\)\.read\(\)|open\(['\"][^'\"]*(pisql|src/)[^'\"]*['\"]\)\.read", c) and "write" in c:
        labels.add("edit source via script")
    if re.search(r"(cat\s*>|printf[^|;&]*>)\s*\S*\.sql|<<['\"]?\w*['\"]?\s*⏎?\s*(CREATE|SELECT|INSERT)", c):
        labels.add("write SQL test input")
    if re.search(r"\b(sed -n|grep|cat|head|tail|wc|ls|find|awk|diff)\b", c):
        labels.add("read or search files")
    if re.search(r"\bgit\b", c):
        labels.add("git")
    if not labels:
        labels.add("other")
    return labels


PRIMARY_ORDER = (
    "write source via shell", "edit source via script", "type-check or build",
    "run own test script", "run own engine on SQL", "probe engine internals",
    "write SQL test input", "read or search files", "git", "other",
)


def primary(labels: set[str]) -> str:
    return next(label for label in PRIMARY_ORDER if label in labels)


# --------------------------------------------------------------------------
# source code shape


LANG_OF = {".py": "python", ".ts": "typescript", ".js": "javascript", ".rs": "rust"}
SKIP_DIRS = {".git", ".pi", "__pycache__", "node_modules", "dist", "target", ".mypy_cache"}


def code_shape(text: str, lang: str) -> dict[str, int]:
    lines = text.splitlines()
    shape = {
        "lines": len(lines),
        "blank_or_comment": sum(1 for l in lines if not l.strip() or l.strip().startswith(("#", "//", "/*", "*"))),
    }
    if lang == "python":
        shape.update(
            functions=len(re.findall(r"^\s*def \w+\(", text, re.M)),
            classes=len(re.findall(r"^\s*class \w+", text, re.M)),
            type_ignores=len(re.findall(r"#\s*type:\s*ignore", text)),
            any_uses=len(re.findall(r"\bAny\b", text)),
            casts=len(re.findall(r"\bcast\(", text)),
        )
    elif lang in ("typescript", "javascript"):
        shape.update(
            functions=len(re.findall(r"\bfunction\s+\w+", text))
            + len(re.findall(r"^\s*(?:(?:public|private|protected|static|async|get|set)\s+)*"
                             r"(?!(?:if|for|while|switch|catch|return|else|do|with|function)\b)"
                             r"\w+\s*\([^)]*\)\s*(?::[^{;]+)?\{", text, re.M)),
            classes=len(re.findall(r"\bclass\s+\w+", text)),
            interfaces_and_types=len(re.findall(r"\binterface\s+\w+|\btype\s+\w+\s*=", text)),
            any_uses=len(re.findall(r":\s*any\b|\bas any\b|<any>", text)),
            ts_ignores=len(re.findall(r"@ts-(ignore|expect-error|nocheck)", text)),
            hand_declared_node_globals=len(re.findall(r"declare\s+(const|var|let|function)\s+(require|process|BigInt)\b", text)),
        )
    elif lang == "rust":
        shape.update(
            functions=len(re.findall(r"\bfn\s+\w+", text)),
            structs_and_enums=len(re.findall(r"\b(struct|enum)\s+\w+", text)),
            impls=len(re.findall(r"^\s*impl\b", text, re.M)),
            unwraps=len(re.findall(r"\.unwrap\(\)", text)),
            unsafe_blocks=len(re.findall(r"\bunsafe\b", text)),
        )
    shape["mentions_hash_join"] = int(bool(re.search(r"hash[_ ]?join|HashJoin|build[^\n]{0,40}hash[^\n]{0,40}probe", text, re.I)))
    shape["mentions_index"] = len(re.findall(r"\bindex(es|ed)?\b", text, re.I))
    return shape


def python_return_annotation_share(text: str) -> float:
    """Share of `def` signatures that declare a return type."""
    sigs = re.findall(r"^\s*def \w+\((?:[^()]|\([^()]*\))*\)\s*(->)?", text, re.M)
    if not sigs:
        return 0.0
    return sum(1 for s in sigs if s) / len(sigs)


def classify_file(rel: str, entry: str) -> str:
    name = rel.rsplit("/", 1)[-1]
    if rel == entry:
        return "main source"
    if name.endswith((".sql", ".test")) or rel.split("/")[0] in ("tests", "sql_tests", "test"):
        return "agent-written tests"
    if re.match(r"(test|review|check|run)[\w-]*\.(py|sh|js|ts)$", name):
        return "agent-written tests"
    if re.match(r"dbg|debug|tmp|scratch", name):
        return "scratch / debugging"
    if name in ("tsconfig.json", "Cargo.toml", "Cargo.lock", "package.json", ".gitignore"):
        return "project config"
    if name in ("AGENTS.md", "TASK.md"):
        return "provided (empty)"
    if Path(name).suffix in LANG_OF:
        return "other source"
    return "other"


# --------------------------------------------------------------------------
# where the time went


def time_split(rounds: list[dict[str, Any]], entries: list[dict[str, Any]]) -> dict[str, Any]:
    """Split each round's wall time between what the session file shows.

    Every saved entry closes an interval that started when the previous entry
    was saved: a reply (from its own start stamp), a tool result, or a
    conversation summary. A reply the harness killed at the round cap is never
    saved, so the time from the last saved entry to the round's end is lost.
    Each entry belongs to the last round that had started by then (a reply by
    its start stamp), so an entry saved right at a round boundary is counted
    once.
    """
    starts = [iso_ms(r["started_at"]) for r in rounds]
    ends = [iso_ms(r["ended_at"]) for r in rounds]
    split = {"model_writing": 0.0, "tools": 0.0, "summarizing": 0.0, "startup": 0.0, "lost_at_round_end": 0.0}
    summaries: list[float] = []
    last = [s for s in starts]
    for e in entries:
        if not e.get("timestamp"):
            continue
        saved = iso_ms(e["timestamp"])
        m = e.get("message") or {}
        key = float(m["timestamp"]) if m.get("role") == "assistant" and m.get("timestamp") else saved
        i = max((k for k, s in enumerate(starts) if s <= key + 1000), default=None)
        if i is None:
            continue
        if e.get("type") == "message":
            role = m.get("role")
            if role == "assistant":
                split["model_writing"] += (saved - key) / 1000
                split["startup"] += max(0.0, key - last[i]) / 1000
            elif role == "toolResult":
                split["tools"] += (saved - last[i]) / 1000
            else:
                split["startup"] += (saved - last[i]) / 1000
        elif e.get("type") == "compaction":
            summaries.append((saved - last[i]) / 1000)
            split["summarizing"] += summaries[-1]
        else:
            split["startup"] += max(0.0, saved - last[i]) / 1000
        last[i] = max(last[i], saved)
    split["lost_at_round_end"] = sum(max(0.0, end - l) for end, l in zip(ends, last)) / 1000
    out: dict[str, Any] = {k: round(v / 60, 1) for k, v in split.items()}
    out["total"] = round(sum(float(r.get("elapsed_seconds") or 0) for r in rounds) / 60, 1)
    out["longest_summary_seconds"] = round(max(summaries, default=0.0), 1)
    return out


def unfinished_replies(entries: list[dict[str, Any]], tokenizer: Any) -> list[dict[str, Any]]:
    """Replies that did not end in a tool call.

    `length`: the reply hit the 32,768-token output cap and was thrown away.
    `stop`: the agent ended its turn on its own, which ends the round.
    """
    rows = []
    for e in entries:
        m = e.get("message") or {}
        if m.get("role") != "assistant" or m.get("stopReason") == "toolUse" or not e.get("timestamp"):
            continue
        content = [b for b in m.get("content") or [] if isinstance(b, dict)]
        thinking = "".join(str(b.get("thinking") or "") for b in content if b.get("type") == "thinking")
        text = "".join(str(b.get("text") or "") for b in content if b.get("type") == "text")
        count = (lambda s: len(tokenizer.encode(s, add_special_tokens=False).ids)) if tokenizer else (lambda s: None)
        rows.append({
            "saved": e["timestamp"],
            "stop": m.get("stopReason"),
            "minutes": round((iso_ms(e["timestamp"]) - float(m.get("timestamp") or 0)) / 60000, 1),
            "generated": int((m.get("usage") or {}).get("output") or 0),
            "reasoning_tokens": count(thinking) if thinking else 0,
            "visible_text_tokens": count(text) if text else 0,
            "tool_calls": [b.get("name") for b in content if b.get("type") == "toolCall"],
            "text_head": text.strip()[:160],
        })
    return rows


# --------------------------------------------------------------------------
# one run


def analyse_run(run: Path, tokenizer: Any) -> dict[str, Any]:
    art = run / "artifacts"
    cond = run.name[len(PREFIX):].rsplit("-r", 1)[0]
    rep = int(run.name.rsplit("-r", 1)[1])
    meta = json.loads((run / "metadata.json").read_text())
    adapter = json.loads((run / "study-control" / "candidate.json").read_text())
    entry = (adapter.get("audit") or adapter.get("source_audit") or {}).get("entry") or (adapter.get("build") or {}).get("artifact") or ""

    out: dict[str, Any] = {"run": run.name, "condition": cond, "replicate": rep}

    # ---- outcome
    rounds = jsonl(art / "rounds.jsonl")
    snaps = jsonl(art / "snapshots.jsonl")
    hidden = jsonl(art / "hidden-scores.jsonl")
    visible = [s.get("visible") or {} for s in snaps]
    hid = [h.get("summary") or {} for h in hidden]
    out["outcome"] = {
        "termination": meta.get("termination_reason"),
        "rounds": len(rounds),
        "round_minutes": [round(float(r.get("elapsed_seconds") or 0) / 60, 1) for r in rounds],
        "rounds_ended_at_cap": sum(1 for r in rounds if r.get("timed_out")),
        "visible_by_round": [round(float(v.get("score") or 0), 4) for v in visible],
        "visible_build_ok": [v.get("build_ok") for v in visible],
        "hidden_by_snapshot": [round(float(h.get("score") or 0), 4) for h in hid],
        "hidden_final": round(float(hid[-1].get("score") or 0), 4) if hid else 0.0,
        "hidden_scripts_passed": hid[-1].get("passed") if hid else 0,
        "hidden_scripts_total": hid[-1].get("total") if hid else 0,
        "hidden_checks_passed": hid[-1].get("records_passed") if hid else 0,
        "hidden_checks_total": hid[-1].get("records_total") if hid else 0,
        "visible_scripts_passed_final": visible[-1].get("passed") if visible else 0,
        "first_working_round": next((i for i, v in enumerate(visible) if float(v.get("score") or 0) > 0.0503), None),
    }

    # per-script results on the held-out set, final snapshot
    finals = sorted((art / "evaluations").glob("hidden-round-*.json"))
    scripts = []
    if finals:
        ev = json.loads(finals[-1].read_text())
        for t in ev.get("tests") or []:
            scripts.append({
                "script": str(t.get("id")).replace("test/", ""),
                "score": round(float(t.get("score") or 0), 4),
                "failure": t.get("failure_type") or "passed",
                "seconds": round(float(t.get("execute_seconds") or 0), 2),
            })
    out["hidden_scripts"] = scripts

    # build-check failures, with the error counts the checker reported
    gate = []
    for p in sorted((art / "evaluations").glob("visible-round-*.json")):
        ev = json.loads(p.read_text())
        s = ev.get("summary") or {}
        b = ev.get("build") or {}
        text = str(b.get("stdout") or "") + str(b.get("stderr") or "")
        errs = re.findall(r"error(?:\[E\d+\])?[: ]|error TS\d+", text)
        gate.append({"round": int(p.stem.rsplit("-", 1)[1]), "build_ok": s.get("build_ok"), "errors": len(errs),
                     "audit_findings": len(((ev.get("source_audit") or {}).get("findings")) or [])})
    out["build_checks"] = gate

    # ---- extensions and guard
    ext = jsonl(art / "extension-events.jsonl")
    comp = [e for e in ext if e.get("event") == "compaction_bound"]
    out["summaries"] = {
        "count": len(comp),
        "ok": sum(1 for e in comp if e.get("outcome") == "ok"),
        "conversation_tokens_before": [e.get("tokens_before") for e in comp],
        "messages_dropped": sum(int(e.get("history_dropped") or 0) for e in comp),
    }
    out["repaired_cut_off_replies"] = sum(1 for e in ext if e.get("event") == "truncation_repaired")
    guard = jsonl(art / "guard.jsonl")
    out["guard"] = {
        "events": len(guard),
        "by_kind": dict(Counter(g.get("event") for g in guard)),
        "reasons": dict(Counter(str(g.get("reason")) for g in guard)),
        "examples": [str(g.get("subject"))[:160] for g in guard[:3]],
    }

    # ---- session file: timing, replies, tools
    session = next(iter(sorted((art / "sessions").glob("*.jsonl"))), None)
    entries = jsonl(session) if session else []
    gen_seconds: list[float] = []
    tool_calls: list[dict[str, Any]] = []
    pending: list[dict[str, Any]] = []   # tool calls of the reply awaiting results
    last_end = None
    user_prompts = 0
    for e in entries:
        if e.get("type") != "message":
            continue
        m = e.get("message") or {}
        role = m.get("role")
        saved = iso_ms(e["timestamp"]) if e.get("timestamp") else None
        if role == "user":
            user_prompts += 1
            last_end = saved
        elif role == "assistant":
            started = m.get("timestamp")
            if started and saved:
                gen_seconds.append((saved - started) / 1000)
            pending = []
            for b in m.get("content") or []:
                if isinstance(b, dict) and b.get("type") == "toolCall":
                    call = {"id": b.get("id"), "tool": b.get("name"), "args": b.get("arguments") or {},
                            "seconds": None, "error": None, "result_chars": 0}
                    tool_calls.append(call)
                    pending.append(call)
            last_end = saved
        elif role == "toolResult":
            call = next((c for c in pending if c["id"] == m.get("toolCallId")), None)
            if call is not None and saved and last_end:
                call["seconds"] = (saved - last_end) / 1000
                call["error"] = bool(m.get("isError"))
                call["result_chars"] = sum(len(str(b.get("text") or "")) for b in m.get("content") or [] if isinstance(b, dict))
            last_end = saved

    by_tool: dict[str, dict[str, float]] = defaultdict(lambda: {"calls": 0, "errors": 0, "seconds": 0.0})
    for c in tool_calls:
        t = by_tool[c["tool"]]
        t["calls"] += 1
        t["errors"] += 1 if c["error"] else 0
        t["seconds"] += c["seconds"] or 0.0
    out["tools"] = {k: {"calls": int(v["calls"]), "errors": int(v["errors"]), "minutes": round(v["seconds"] / 60, 1)}
                    for k, v in sorted(by_tool.items(), key=lambda kv: -kv[1]["calls"])}
    out["time"] = time_split(rounds, entries)
    # What writing the summaries cost the model: the session file keeps the
    # server's usage for each summary request.
    written = [int((e.get("usage") or {}).get("output") or 0) for e in entries if e.get("type") == "compaction"]
    out["summaries"].update(
        minutes=out["time"]["summarizing"],
        tokens_written=sum(written),
        tokens_written_median=int(med(written)),
        tokens_written_max=max(written, default=0),
    )
    out["unfinished_replies"] = unfinished_replies(entries, tokenizer)

    # shell commands
    bash = [c for c in tool_calls if c["tool"] == "bash"]
    flags: Counter[str] = Counter()
    prim: dict[str, dict[str, float]] = defaultdict(lambda: {"calls": 0, "seconds": 0.0})
    timeouts = 0
    for c in bash:
        command = str(c["args"].get("command") or "")
        labels = bash_labels(command)
        flags.update(labels)
        p = prim[primary(labels)]
        p["calls"] += 1
        p["seconds"] += c["seconds"] or 0.0
        if (c["seconds"] or 0) >= 118:
            timeouts += 1
    out["shell"] = {
        "calls": len(bash),
        "does_this": dict(flags.most_common()),
        "mainly": {k: {"calls": int(v["calls"]), "minutes": round(v["seconds"] / 60, 1)}
                   for k, v in sorted(prim.items(), key=lambda kv: -kv[1]["calls"])},
        "ran_120s_or_more": timeouts,
        "slowest_seconds": round(max((c["seconds"] or 0) for c in bash), 1) if bash else 0,
    }

    # file tools
    writes = [c for c in tool_calls if c["tool"] == "write"]
    edits = [c for c in tool_calls if c["tool"] == "edit"]
    reads = [c for c in tool_calls if c["tool"] == "read"]
    def edit_lines(c: dict[str, Any]) -> tuple[int, int]:
        added = removed = 0
        for ed in c["args"].get("edits") or [c["args"]]:
            added += str(ed.get("newText") or ed.get("new_string") or "").count("\n") + 1
            removed += str(ed.get("oldText") or ed.get("old_string") or "").count("\n") + 1
        return added, removed
    er = [edit_lines(c) for c in edits]
    out["file_tools"] = {
        "writes": len(writes),
        "write_targets": dict(Counter(str(c["args"].get("path") or "").replace("/workspace/", "") for c in writes).most_common(6)),
        "bytes_written": sum(len(str(c["args"].get("content") or "")) for c in writes),
        "largest_write_bytes": max((len(str(c["args"].get("content") or "")) for c in writes), default=0),
        "edits": len(edits),
        "edit_lines_added": sum(a for a, _ in er),
        "edit_lines_removed": sum(r for _, r in er),
        "failed_edits": sum(1 for c in edits if c["error"]),
        "reads": len(reads),
        "distinct_files_read": len({str(c["args"].get("path")) for c in reads}),
    }

    # ---- event stream: tokens per reply, reasoning counted with the tokenizer
    per_reply: list[dict[str, Any]] = []
    for path in sorted((art / "events").glob("round-*.jsonl")):
        parts: list[str] = []
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if '"thinking_delta"' in line:
                try:
                    ev = json.loads(line)
                except json.JSONDecodeError:
                    continue
                upd = ev.get("assistantMessageEvent") or {}
                if upd.get("type") == "thinking_delta":
                    parts.append(upd.get("delta") or "")
                continue
            if '"message_end"' not in line:
                continue
            try:
                ev = json.loads(line)
            except json.JSONDecodeError:
                continue
            m = ev.get("message") or {}
            if ev.get("type") != "message_end" or m.get("role") != "assistant":
                if ev.get("type") == "message_end":
                    parts = []
                continue
            u = m.get("usage") or {}
            text = "".join(parts)
            parts = []
            reasoning = len(tokenizer.encode(text, add_special_tokens=False).ids) if (tokenizer and text) else None
            per_reply.append({
                "stop": m.get("stopReason"),
                "prompt": int(u.get("input") or 0) + int(u.get("cacheRead") or 0),
                "cached": int(u.get("cacheRead") or 0),
                "output": int(u.get("output") or 0),
                "reasoning": reasoning,
                "reasoning_chars": len(text),
            })
    outputs = [r["output"] for r in per_reply]
    prompts = [r["prompt"] for r in per_reply]
    reasoning = [r["reasoning"] for r in per_reply if r["reasoning"] is not None]
    out["replies"] = {
        "count": len(per_reply),
        "stops": dict(Counter(r["stop"] for r in per_reply)),
        "with_tool_call_share": round(sum(1 for r in per_reply if r["stop"] == "toolUse") / max(len(per_reply), 1), 3),
        "prompts_sent": user_prompts,
        "generation_minutes": round(sum(gen_seconds) / 60, 1),
        "reply_seconds_median": round(med(gen_seconds), 1),
        "reply_seconds_p90": round(pct(gen_seconds, 0.9), 1),
        "reply_seconds_max": round(max(gen_seconds, default=0), 1),
    }
    total_prompt = sum(prompts)
    out["tokens"] = {
        "generated": sum(outputs),
        "reasoning": sum(reasoning) if reasoning else None,
        "answer_and_tool_calls": (sum(outputs) - sum(reasoning)) if reasoning else None,
        "reasoning_share": round(sum(reasoning) / max(sum(outputs), 1), 3) if reasoning else None,
        "read_by_model": total_prompt,
        "read_from_cache": sum(r["cached"] for r in per_reply),
        "cache_share": round(sum(r["cached"] for r in per_reply) / max(total_prompt, 1), 3),
        "conversation_size_median": int(med(prompts)),
        "conversation_size_max": max(prompts, default=0),
        "generated_per_reply_median": int(med(outputs)),
        "generated_per_reply_max": max(outputs, default=0),
        "generated_per_minute": round(sum(outputs) / max(sum(gen_seconds) / 60, 1e-9)),
    }
    if reasoning:
        out["reasoning"] = {
            "median": int(med(reasoning)), "p90": int(pct(reasoning, 0.9)), "max": max(reasoning),
            "replies_at_budget": sum(1 for r in reasoning if abs(r - BUDGET) <= 8),
            "replies_over_budget": sum(1 for r in reasoning if r > BUDGET + 8),
            "replies_with_no_reasoning": sum(1 for r in reasoning if r == 0),
        }

    # ---- the product: files in the final workspace
    ws = run / "workspace"
    files = []
    # The engine is what the build takes in: pisql.py for Python, and every
    # source file in the run's own language under src/ for the others (a Rust
    # crate has no single entry file). Anything else in that language -- a
    # comparison script, or the pieces typescript-r3 assembled its file from
    # and left behind in src_parts/ -- is a helper, not the engine.
    ext = {"python": ".py", "python-typed": ".py", "javascript": ".js",
           "typescript": ".ts", "rust": ".rs"}[cond]
    engine_text: list[str] = []
    for p in sorted(ws.rglob("*")):
        if not p.is_file() or any(part in SKIP_DIRS for part in p.relative_to(ws).parts):
            continue
        rel = str(p.relative_to(ws))
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        kind = classify_file(rel, entry)
        if kind == "other source" and p.suffix != ext:
            kind = "helper script (other language)"
        elif kind == "other source" and (ext == ".py" or not rel.startswith("src/")):
            kind = "helper script"
        files.append({"path": rel, "kind": kind, "bytes": p.stat().st_size, "lines": text.count("\n")})
        if kind in ("main source", "other source"):
            engine_text.append(text)
    joined = "\n".join(engine_text)
    main_shape = code_shape(joined, LANG_OF.get(ext, "")) if joined else {}
    if ext == ".py" and joined:
        main_shape["share_of_functions_with_return_type"] = round(python_return_annotation_share(joined), 3)
    source_files = [f for f in files if f["kind"] in ("main source", "other source")]
    tests = [f for f in files if f["kind"] == "agent-written tests"]
    out["product"] = {
        "entry_file": entry,
        "files": len(files),
        "source_files": len(source_files),
        "source_lines": sum(f["lines"] for f in source_files),
        "engine_bytes": sum(f["bytes"] for f in source_files),
        "engine_shape": main_shape,
        "test_files": len(tests),
        "test_lines": sum(f["lines"] for f in tests),
        "by_kind": dict(Counter(f["kind"] for f in files)),
        "listing": files,
        "lines_added_by_round": [int(s.get("insertions") or 0) for s in snaps],
        "lines_removed_by_round": [int(s.get("deletions") or 0) for s in snaps],
    }
    return out


def main() -> int:
    tokenizer = None
    try:
        from tokenizers import Tokenizer  # type: ignore[import-not-found]
        if TOKENIZER.is_file():
            tokenizer = Tokenizer.from_file(str(TOKENIZER))
    except ImportError:
        print("tokenizers not available: reasoning-token columns will be empty "
              "(run with .venv-sglang/bin/python for them)")
    runs = [d for d in sorted((ROOT / "runs").glob(PREFIX + "*")) if (d / "report.md").is_file()]
    results = []
    for run in sorted(runs, key=lambda d: (ORDER.index(d.name[len(PREFIX):].rsplit("-r", 1)[0])
                                            if d.name[len(PREFIX):].rsplit("-r", 1)[0] in ORDER else 9, d.name)):
        print(f"  {run.name}", flush=True)
        results.append(analyse_run(run, tokenizer))
    target = ROOT / "analysis" / "v17-internals.json"
    target.write_text(json.dumps({"runs": results}, indent=1) + "\n", encoding="utf-8")
    print(f"wrote {target.relative_to(ROOT)} ({len(results)} runs)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
