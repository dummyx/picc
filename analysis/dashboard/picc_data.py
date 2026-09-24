"""Everything the results dashboard shows, read from runs/ and analysis/.

Read-only: nothing here writes to runs/ or to the repository. Parsed results are
kept in memory and, when a cache directory is given, on disk (by default
~/.cache/picc-dashboard), keyed by the size and modification time of every file
they came from. A run's numbers are therefore recomputed exactly when its files
change, which is what keeps a running run up to date.

The numbers are measured from the raw records the same way
analysis/v17_internals.py measures them for docs/REPORT_2026-09-23.md:

- the Pi session file (artifacts/sessions/*.jsonl) for replies, their timing and
  token use, tool calls and their results, and conversation summaries;
- the harness ledgers (rounds, snapshots, hidden-scores, fuzz-scores, guard,
  extension-events, state) for rounds, scores and blocked commands;
- the evaluator records (artifacts/evaluations/*.json) for per-test results;
- the workspace's harness-owned Git history for the files the agent wrote.

Scores re-computed after a batch (analysis/v<N>-rescore/, analysis/v6-rescore.json)
replace the frozen ledger values, as the batch results scripts do, and are
marked as corrected.

Reasoning tokens are not in the run records (every reply records 0), so they are
counted from the streamed reasoning text with the served model's own tokenizer
when the `tokenizers` package can be imported, and reported as unavailable
otherwise. They are never estimated from character counts.
"""

from __future__ import annotations

import bisect
import hashlib
import json
import os
import queue
import re
import statistics
import subprocess
import tempfile
import threading
import time
from collections import Counter, OrderedDict, defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Iterable

EXTRACTOR_VERSION = 7
DEFAULT_TOKENIZER = Path.home() / "models" / "Qwen3.8-27B-NVFP4" / "tokenizer.json"
NOT_RUNS = {"inference", "study-results"}
RUN_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,120}$")
COMMIT = re.compile(r"^[0-9a-f]{7,64}$")
SECRET_WORDS = ("KEY", "TOKEN", "SECRET", "PASSWORD", "CREDENTIAL")
TEXT_CAP = 60_000
LANGUAGE_OF = {"python": "python", "python-typed": "python", "rust": "rust", "javascript": "javascript",
               "typescript": "typescript", "js-untyped": "javascript", "ts-strict": "typescript"}


class DataError(Exception):
    """A request the data cannot answer (unknown run, round, file...)."""


# --------------------------------------------------------------------------
# small helpers


def jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    try:
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    value = json.loads(line)
                except json.JSONDecodeError:
                    continue  # a line a live run is still writing
                if isinstance(value, dict):
                    rows.append(value)
    except OSError:
        pass
    return rows


def read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except (OSError, json.JSONDecodeError):
        return None


def read_text(path: Path, cap: int | None = None) -> str | None:
    try:
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            return handle.read(cap) if cap else handle.read()
    except OSError:
        return None


def iso_ms(value: Any) -> float | None:
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).timestamp() * 1000
    except ValueError:
        return None


def fingerprint(paths: Iterable[Path]) -> str:
    digest = hashlib.sha1(f"v{EXTRACTOR_VERSION}".encode())
    for path in paths:
        try:
            st = path.stat()
            digest.update(f"{path}:{st.st_size}:{st.st_mtime_ns};".encode())
        except OSError:
            digest.update(f"{path}:-;".encode())
    return digest.hexdigest()


def median(values: list[float]) -> float | None:
    return statistics.median(values) if values else None


def cap_text(text: str, cap: int = TEXT_CAP) -> tuple[str, int | None]:
    """Return text cut to `cap` characters and the original length when cut."""
    if len(text) <= cap:
        return text, None
    return text[:cap], len(text)


def is_secret_name(name: str) -> bool:
    upper = name.upper()
    return any(word in upper for word in SECRET_WORDS)


def blocks(message: dict[str, Any]) -> list[dict[str, Any]]:
    content = message.get("content")
    if isinstance(content, str):
        return [{"type": "text", "text": content}]
    return [b for b in content or [] if isinstance(b, dict)]


def joined_text(message: dict[str, Any]) -> str:
    parts = []
    for b in blocks(message):
        if b.get("type") == "text":
            parts.append(str(b.get("text") or ""))
        elif b.get("type") == "image":
            parts.append("[image]")
    return "".join(parts)


class Redactor:
    """Replaces the values of secret-named settings wherever they appear.

    The values come from the repository's .env and the server's own
    environment; they are never sent anywhere, only removed from responses.
    """

    def __init__(self, values: Iterable[str]) -> None:
        self.values = sorted({v for v in values if len(v) >= 8}, key=len, reverse=True)

    @classmethod
    def for_repo(cls, root: Path) -> "Redactor":
        values: list[str] = []
        text = read_text(root / ".env") or ""
        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            name, _, value = line.partition("=")
            name = name.strip().removeprefix("export ").strip()
            value = value.strip().strip("'\"")
            if is_secret_name(name):
                values.append(value)
        values += [v for k, v in os.environ.items() if is_secret_name(k)]
        return cls(values)

    def __call__(self, text: str) -> str:
        for value in self.values:
            if value in text:
                text = text.replace(value, "[hidden]")
        return text


# --------------------------------------------------------------------------
# classification in plain words


SHELL_KINDS: tuple[tuple[str, re.Pattern[str]], ...] = tuple(
    (label, re.compile(pattern)) for label, pattern in (
        ("writes files", r"cat\s*>>?\s*\S+\s*<<|<<-?\s*['\"]?\w+['\"]?\s*>>?\s*\S+|\btee\s+(-a\s+)?\S"
                         r"|printf[^|;&]*[^2]>\s*[\w/.]|\.write_text\(|open\([^)]*,\s*['\"][wa]b?['\"]"),
        ("builds or type-checks", r"\bmypy\b|\btsc\b|\bcargo\s+(build|check|clippy)\b|py_compile|node\s+--check"
                                  r"|\brustc\b|\bnpm\s+run\s+build\b"),
        ("runs tests", r"\bcargo\s+test\b|\bpytest\b|\bunittest\b|node\s+--test\b"
                       r"|(^|[\s/;&|])(run|test|check|review)[\w.-]*\.(sh|py|js|mjs|ts)\b|\btest_\w+\.py\b"
                       r"|for\s+\w+\s+in\s+[^;]*\.(sql|c|test)\b"),
        ("runs its own program", r"(python3?|node|tsx|ts-node)(\s+-[-\w=]+)*\s+(\S*/)?(pisql|picc)\.(py|js|ts)(?=[\s<>;|&)'\"]|$)"
                                 r"|(\S*/)?(dist|src)/(pisql|picc)\.js(?=[\s<>;|&)'\"]|$)"
                                 r"|(\./)?target/(release|debug)/(pisql|picc)(?=[\s<>;|&)'\"]|$)|\bcargo\s+run\b"
                                 r"|(^|[\s;&|(])\./(pisql|picc)(?=[\s<>;|&)'\"]|$)"),
        ("probes its own code", r"\bimport\s+(pisql|picc)\b|\bfrom\s+(pisql|picc)\b|require\(\s*['\"]\./(src|dist)/"),
        ("reads or searches files", r"\b(sed\s+-n|grep|rg|cat|head|tail|wc|ls|find|awk|diff|tree|nl|stat|file|xxd|od)\b"),
        ("uses git", r"\bgit\b"),
    )
)


def shell_kinds(command: str) -> list[str]:
    found = [label for label, pattern in SHELL_KINDS if pattern.search(command)]
    return found or ["other"]


def why_failed(tool: str, text: str) -> str:
    t = text.strip()
    if t.startswith("Experiment guard:"):
        return "blocked by the rule checker"
    if "was not executed: the response hit the output token limit" in t:
        return "not run: reply was cut off"
    if re.search(r"Could not find (edits\[\d+\]|the exact text)", t):
        return "edit: text to replace not found"
    if re.search(r"occurrences|must be unique|more than once", t, re.I) and tool == "edit":
        return "edit: text to replace not unique"
    if re.search(r"Command timed out after|timed out", t):
        return "command ran out of time"
    if re.search(r"Command exited with code \d+\s*$", t):
        return "command exited with an error"
    if re.search(r"ENOENT|No such file or directory|EISDIR|is a directory", t):
        return "file not found"
    if re.search(r"\baborted\b", t, re.I):
        return "stopped before it finished"
    return "other error"


def error_line(text: str) -> str:
    """The most informative short line of a failed tool result."""
    lines = [l.strip() for l in text.strip().splitlines() if l.strip()]
    if not lines:
        return ""
    last = lines[-1]
    if re.match(r"Command exited with code \d+$", last) and len(lines) > 1:
        return (lines[-2] + " | " + last)[:240]
    return lines[0][:240] if len(lines[0]) > 20 else last[:240]


def describe_call(name: str, args: Any) -> str:
    if not isinstance(args, dict):
        return str(args)[:400]
    if name == "bash":
        return str(args.get("command") or "")[:600]
    path = str(args.get("path") or args.get("file_path") or "")
    if name == "write":
        content = str(args.get("content") or "")
        return f"{path}  ({content.count(chr(10)) + (1 if content else 0)} lines, {len(content):,} characters)"
    if name == "edit":
        edits = args.get("edits")
        n = len(edits) if isinstance(edits, list) else 1
        return f"{path}  ({n} change{'s' if n != 1 else ''})"
    if name == "read":
        extra = []
        if args.get("offset"):
            extra.append(f"from line {args['offset']}")
        if args.get("limit"):
            extra.append(f"{args['limit']} lines")
        return path + (f"  ({', '.join(extra)})" if extra else "")
    if name in ("grep", "find", "ls"):
        return " ".join(str(v) for v in args.values())[:400]
    return json.dumps(args, ensure_ascii=False)[:400]


CONFIG_NAMES = {
    "Cargo.toml", "Cargo.lock", "package.json", "package-lock.json", "tsconfig.json", ".gitignore",
    "mypy.ini", "pyproject.toml", "setup.cfg", "rust-toolchain", "rust-toolchain.toml", ".editorconfig",
}
TEST_DIRS = {"tests", "test", "sql_tests", "testdata", "test_data", "spec", "specs", "cases", "fixtures", "examples", "t"}


def file_kind(path: str, exts: set[str], roots: list[str], entry: str, language: str, c_task: bool) -> str:
    parts = path.split("/")
    name = parts[-1]
    lower = name.lower()
    suffix = ("." + lower.rsplit(".", 1)[1]) if "." in lower[1:] else ""
    if len(parts) == 1 and name in ("AGENTS.md", "TASK.md"):
        return "given to the agent"
    if parts[0] == ".pi":
        return "given to the agent"
    if name in CONFIG_NAMES:
        return "project settings"
    in_test_dir = any(p.lower() in TEST_DIRS for p in parts[:-1])
    test_name = bool(re.match(r"(test|tests|check|review|run)([\w.-]*)$", lower)
                     or re.search(r"_tests?\.\w+$|\.test$|\.slt$|\.sql$|\.expected$", lower))
    scratch = bool(re.match(r"(dbg|debug|tmp|temp|scratch|probe|try|foo|bar|t\d+|x\d*)([\w.-]*)$", lower)) \
        or suffix in (".log", ".out", ".tmp", ".o", ".s")
    if language == "rust":
        in_roots = parts[0] == "src"
    elif roots:
        in_roots = any(path == r or path.startswith(r.rstrip("/") + "/") for r in roots)
    else:
        in_roots = True
    if suffix in exts:
        if in_test_dir or test_name:
            return "tests written by the agent"
        if scratch:
            return "scratch files"
        if path == entry or in_roots:
            return "program code"
        return "helper scripts"
    if in_test_dir or test_name or (c_task and suffix in (".c", ".h")):
        return "tests written by the agent"
    if scratch or suffix == ".txt":
        return "scratch files"
    if suffix in (".sh", ".py", ".js", ".mjs", ".cjs", ".ts", ".rs", ".pl", ".awk"):
        return "helper scripts"
    if suffix == ".md":
        return "notes"
    return "other"


# --------------------------------------------------------------------------
# caching


class Store:
    """Memory cache in front of an optional on-disk cache.

    Values are keyed by (kind, run id) and stored with the fingerprint of the
    files they were computed from; a different fingerprint means recompute.
    Heavy kinds are kept in memory only for the most recently used runs.
    """

    HEAVY = {"digest": 24, "files": 24, "session": 4, "matrix": 12, "reasoning_full": 12}

    def __init__(self, cache_dir: Path | None) -> None:
        self.dir = cache_dir
        if self.dir is not None:
            self.dir.mkdir(parents=True, exist_ok=True)
        self.mem: dict[str, OrderedDict[str, tuple[str, Any]]] = defaultdict(OrderedDict)
        self.lock = threading.Lock()
        self.key_locks: dict[tuple[str, str], threading.Lock] = defaultdict(threading.Lock)

    def _path(self, kind: str, key: str) -> Path | None:
        if self.dir is None:
            return None
        return self.dir / kind / f"{key}.json"

    def peek(self, kind: str, key: str, fp: str, disk: bool = True) -> Any:
        with self.lock:
            hit = self.mem[kind].get(key)
            if hit and hit[0] == fp:
                self.mem[kind].move_to_end(key)
                return hit[1]
        if not disk:
            return None
        path = self._path(kind, key)
        if path is None:
            return None
        data = read_json(path)
        if isinstance(data, dict) and data.get("fp") == fp:
            self._remember(kind, key, fp, data.get("value"))
            return data.get("value")
        return None

    def _remember(self, kind: str, key: str, fp: str, value: Any) -> None:
        with self.lock:
            bucket = self.mem[kind]
            bucket[key] = (fp, value)
            bucket.move_to_end(key)
            limit = self.HEAVY.get(kind)
            while limit is not None and len(bucket) > limit:
                bucket.popitem(last=False)

    def put(self, kind: str, key: str, fp: str, value: Any, disk: bool = True) -> None:
        self._remember(kind, key, fp, value)
        path = self._path(kind, key)
        if path is None or not disk:
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".tmp-")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump({"fp": fp, "value": value}, handle, ensure_ascii=False, separators=(",", ":"))
            os.replace(tmp, path)
        except BaseException:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise

    def get(self, kind: str, key: str, fp: str, compute: Callable[[], Any], disk: bool = True) -> Any:
        found = self.peek(kind, key, fp, disk)
        if found is not None:
            return found
        with self.lock:
            key_lock = self.key_locks[(kind, key)]
        with key_lock:
            found = self.peek(kind, key, fp, disk)
            if found is not None:
                return found
            value = compute()
            self.put(kind, key, fp, value, disk)
            return value


# --------------------------------------------------------------------------
# liveness


def read_locks() -> str | None:
    try:
        return Path("/proc/locks").read_text()
    except OSError:
        return None


def lock_held(path: Path, locks: str | None) -> bool | None:
    """Whether a process holds an flock on `path`, read from /proc/locks.

    Looking, not locking: taking even a shared lock on a run's lock file could
    make the harness refuse to start at that instant.
    """
    if locks is None:
        return None
    try:
        st = path.stat()
    except OSError:
        return False
    needle = f"{os.major(st.st_dev):02x}:{os.minor(st.st_dev):02x}:{st.st_ino}"
    return any(needle in line.split() for line in locks.splitlines())


# --------------------------------------------------------------------------
# the results


class Results:
    def __init__(self, root: Path, cache_dir: Path | None = None,
                 tokenizer_path: Path | None = DEFAULT_TOKENIZER) -> None:
        self.root = root.resolve()
        self.runs_dir = self.root / "runs"
        self.cache_dir = cache_dir
        self.store = Store(cache_dir)
        self.redact = Redactor.for_repo(self.root)
        self.tokenizer_path = tokenizer_path
        self._tokenizer: Any = None
        self._tokenizer_state = "untried"
        self._tokenizer_lock = threading.Lock()
        self._jobs: "queue.Queue[str]" = queue.Queue()
        self._queued: set[str] = set()
        self._job_errors: dict[str, str] = {}
        self._job_lock = threading.Lock()
        self.warm = {"total": 0, "done": 0, "running": False, "errors": 0}
        self._ids_cache: tuple[float, list[str]] = (0.0, [])

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

    # ---------------------------------------------------------------- files (Git)

    def _git_dir(self, run: Path) -> Path:
        git_dir = run / "workspace" / ".git"
        if git_dir.is_dir():
            return git_dir
        bundle = run / "workspace.git.bundle"
        if not bundle.is_file():
            raise DataError(f"run {run.name} has no saved file history")
        base = self.cache_dir or Path(tempfile.gettempdir()) / "picc-dashboard"
        target = base / "git" / f"{run.name}.git"
        if not target.is_dir():
            target.parent.mkdir(parents=True, exist_ok=True)
            subprocess.run(["git", "clone", "--bare", "--quiet", str(bundle), str(target)],
                           check=True, capture_output=True, timeout=120)
        return target

    def _git(self, run: Path, *args: str, stdin: bytes | None = None, timeout: int = 60) -> bytes:
        env = {**os.environ, "GIT_OPTIONAL_LOCKS": "0", "GIT_TERMINAL_PROMPT": "0", "GIT_CONFIG_NOSYSTEM": "1",
               "GIT_PAGER": "cat", "LC_ALL": "C"}
        proc = subprocess.run(["git", f"--git-dir={self._git_dir(run)}", *args], input=stdin,
                              capture_output=True, timeout=timeout, env=env)
        if proc.returncode != 0:
            raise DataError(proc.stderr.decode("utf-8", "replace").strip()[:300] or "git failed")
        return proc.stdout

    def _snapshots(self, run: Path) -> list[dict[str, Any]]:
        rows = []
        for s in jsonl(run / "artifacts" / "snapshots.jsonl"):
            commit = str(s.get("git_commit") or "")
            if COMMIT.match(commit):
                rows.append({"round": int(s.get("round", len(rows))), "commit": commit,
                             "added": s.get("insertions"), "removed": s.get("deletions"),
                             "changed": s.get("changed_files")})
        return rows

    def _commit_for(self, run: Path, round_no: int | None) -> tuple[int, str]:
        snaps = self._snapshots(run)
        if not snaps:
            raise DataError(f"run {run.name} has no saved versions yet")
        if round_no is None:
            return snaps[-1]["round"], snaps[-1]["commit"]
        for s in snaps:
            if s["round"] == round_no:
                return s["round"], s["commit"]
        raise DataError(f"run {run.name} has no saved version for round {round_no}")

    def _adapter(self, run: Path) -> dict[str, Any]:
        adapter = read_json(run / "study-control" / "candidate.json") or {}
        sm = read_json(run / "study-metadata.json") or {}
        task = (sm.get("task") or (sm.get("condition") or {}).get("task") or {}).get("id") or "c-compiler-ch1-10"
        language = adapter.get("language") or ((sm.get("condition") or {}).get("candidate") or {}).get("language") or "rust"
        exts = set(adapter.get("source_extensions") or {"rust": [".rs"], "python": [".py"],
                                                          "javascript": [".js", ".mjs", ".cjs"],
                                                          "typescript": [".ts"]}.get(language, [".rs"]))
        audit = adapter.get("audit") or {}
        build = adapter.get("build") or {}
        entry = audit.get("entry") or build.get("artifact") or ""
        return {"language": language, "exts": exts, "roots": list(audit.get("roots") or []), "entry": entry,
                "c_task": task.startswith("c-"), "build": build.get("command"), "run": (adapter.get("run") or {}).get("command")}

    def files(self, run_id: str) -> dict[str, Any]:
        run = self.run_dir(run_id)
        fp = fingerprint([run / "artifacts" / "snapshots.jsonl", run / "study-control" / "candidate.json"])
        return self.store.get("files", run_id, fp, lambda: self._files(run))

    def files_totals(self, run_id: str, compute: bool = True) -> dict[str, Any] | None:
        run = self.run_dir(run_id)
        fp = fingerprint([run / "artifacts" / "snapshots.jsonl", run / "study-control" / "candidate.json"])
        if not compute:
            return self.store.peek("files_totals", run_id, fp)

        def build() -> dict[str, Any]:
            data = self.files(run_id)
            last = data["rounds"][-1] if data["rounds"] else {"totals": {}}
            return {"final": last["totals"],
                    "by_round": [{"round": r["round"], "totals": r["totals"], "added": r["added"],
                                  "removed": r["removed"], "changed": r["changed"]} for r in data["rounds"]]}

        return self.store.get("files_totals", run_id, fp, build)

    def _files(self, run: Path) -> dict[str, Any]:
        adapter = self._adapter(run)
        snaps = self._snapshots(run)
        rounds = []
        blob_lines: dict[str, int | None] = {}
        listings = []
        for s in snaps:
            try:
                raw = self._git(run, "ls-tree", "-r", "-l", "-z", s["commit"])
            except DataError:
                listings.append((s, []))
                continue
            rows = []
            for item in raw.split(b"\0"):
                if not item:
                    continue
                meta, _, path = item.partition(b"\t")
                parts = meta.split()
                if len(parts) < 4 or parts[1] != b"blob":
                    continue
                size = int(parts[3]) if parts[3].isdigit() else 0
                rows.append((path.decode("utf-8", "replace"), parts[2].decode(), size))
                blob_lines.setdefault(parts[2].decode(), None)
            listings.append((s, rows))
        wanted = [sha for sha in blob_lines]
        if wanted:
            try:
                out = self._git(run, "cat-file", "--batch", stdin=("\n".join(wanted) + "\n").encode(), timeout=120)
                pos = 0
                while pos < len(out):
                    nl = out.index(b"\n", pos)
                    header = out[pos:nl].split()
                    pos = nl + 1
                    if len(header) < 3 or header[1] == b"missing":
                        continue
                    size = int(header[2])
                    body = out[pos:pos + size]
                    pos += size + 1
                    sha = header[0].decode()
                    blob_lines[sha] = None if b"\0" in body[:8000] else body.count(b"\n") + (0 if body.endswith(b"\n") or not body else 1)
            except (DataError, ValueError, subprocess.TimeoutExpired):
                pass
        for s, rows in listings:
            files = []
            totals: dict[str, dict[str, int]] = {}
            for path, sha, size in rows:
                kind = file_kind(path, adapter["exts"], adapter["roots"], adapter["entry"], adapter["language"], adapter["c_task"])
                lines = blob_lines.get(sha)
                files.append([path, kind, size, lines, sha[:12]])
                t = totals.setdefault(kind, {"files": 0, "lines": 0, "bytes": 0})
                t["files"] += 1
                t["lines"] += lines or 0
                t["bytes"] += size
            rounds.append({"round": s["round"], "commit": s["commit"], "added": s["added"], "removed": s["removed"],
                           "changed": s["changed"], "files": files, "totals": totals})
        return {"language": adapter["language"], "entry": adapter["entry"], "rounds": rounds}

    def file(self, run_id: str, round_no: int | None, path: str) -> dict[str, Any]:
        run = self.run_dir(run_id)
        path = self._clean_path(path)
        rnd, commit = self._commit_for(run, round_no)
        data = self._git(run, "cat-file", "blob", f"{commit}:{path}", timeout=30)
        binary = b"\0" in data[:8000]
        text = "" if binary else data[:3_000_000].decode("utf-8", "replace")
        return {"round": rnd, "path": path, "bytes": len(data), "binary": binary, "text": text,
                "cut": len(data) > 3_000_000}

    def diff(self, run_id: str, round_no: int | None, path: str | None = None) -> dict[str, Any]:
        run = self.run_dir(run_id)
        rnd, commit = self._commit_for(run, round_no)
        args = ["diff", "--no-color", "--no-ext-diff", "-M", f"{commit}^", commit]
        try:
            numstat = self._git(run, *args[:-2], "--numstat", "-z", f"{commit}^", commit).decode("utf-8", "replace")
        except DataError:
            return {"round": rnd, "files": [], "text": "", "cut": False}
        files = []
        items = numstat.split("\0")
        i = 0
        while i < len(items):
            item = items[i]
            if not item:
                i += 1
                continue
            fields = item.split("\t")
            if len(fields) >= 3 and fields[2] == "":  # rename: next two items are old and new path
                old, new = items[i + 1], items[i + 2]
                files.append({"path": new, "from": old, "added": fields[0], "removed": fields[1]})
                i += 3
                continue
            if len(fields) >= 3:
                files.append({"path": fields[2], "added": fields[0], "removed": fields[1]})
            i += 1
        text = ""
        cut = False
        if path:
            path = self._clean_path(path)
            raw = self._git(run, *args, "--", path)
            cut = len(raw) > 2_000_000
            text = raw[:2_000_000].decode("utf-8", "replace")
        return {"round": rnd, "files": files, "text": text, "cut": cut}

    @staticmethod
    def _clean_path(path: str) -> str:
        path = (path or "").strip().lstrip("/")
        if not path or any(part in ("", ".", "..") for part in path.split("/")) or "\0" in path or path.startswith("-"):
            raise DataError("bad file path")
        return path

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

    # ---------------------------------------------------------------- warm-up

    def warm_up(self, workers: int = 3) -> None:
        """Parse every run once in the background so pages open instantly."""
        ids = self.run_ids()
        locks = read_locks()
        order = []
        for rid in ids:
            try:
                order.append((self.summary(rid, locks).get("started_at") or "", rid))
            except DataError:
                continue
        order.sort(reverse=True)
        todo = [rid for _, rid in order if not self._warm(rid)]
        self.warm.update(total=len(order), done=len(order) - len(todo), running=bool(todo), errors=0)
        if not todo:
            return
        if self.cache_dir is None or workers <= 1:
            for rid in todo:
                try:
                    self._warm_one(rid)
                except Exception:  # noqa: BLE001
                    self.warm["errors"] += 1
                self.warm["done"] += 1
        else:
            with ProcessPoolExecutor(max_workers=workers, initializer=_lower_priority) as pool:
                tok = str(self.tokenizer_path) if self.tokenizer_path and self.tokenizer() is not None else None
                futures = {pool.submit(_warm_worker, str(self.root), str(self.cache_dir), tok, rid): rid for rid in todo}
                for future in as_completed(futures):
                    if future.exception() is not None:
                        self.warm["errors"] += 1
                    self.warm["done"] += 1
        self.warm["running"] = False

    def _warm(self, run_id: str) -> bool:
        try:
            run = self.run_dir(run_id)
            done = (self.totals(run_id, compute=False) is not None
                    and self.files_totals(run_id, compute=False) is not None
                    and (self.final_tests(run_id, compute=False) is not None
                         or not self._eval_rounds(run, "hidden")))
            if done and self.tokenizer_path is not None and self.tokenizer_path.is_file():
                done = self.store.peek("reasoning", run_id, fingerprint(self._events(run))) is not None \
                    or self.tokenizer() is None
            return done
        except DataError:
            return True

    def _warm_one(self, run_id: str) -> None:
        self.totals(run_id)
        self.files_totals(run_id)
        self.final_tests(run_id)
        if self.tokenizer() is not None:
            self.count_reasoning(run_id)


_WORKER: dict[str, Results] = {}


def _lower_priority() -> None:
    try:
        os.nice(10)
    except OSError:
        pass


def _warm_worker(root: str, cache_dir: str, tokenizer: str | None, run_id: str) -> None:
    key = f"{root}|{cache_dir}|{tokenizer}"
    if key not in _WORKER:
        _WORKER[key] = Results(Path(root), Path(cache_dir), tokenizer_path=Path(tokenizer) if tokenizer else None)
    _WORKER[key]._warm_one(run_id)
