"""Reading run records safely: files and JSON lines, secret redaction, the
on-disk cache, and whether a run is still running.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import statistics
import tempfile
import threading
from collections import defaultdict, OrderedDict
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Iterable


EXTRACTOR_VERSION = 8
DEFAULT_TOKENIZER = Path.home() / "models" / "Qwen3.8-27B-NVFP4" / "tokenizer.json"
# A re-score folder (analysis/v<N>-rescore/<run>/) replaces a run's recorded
# scores only for the runs the batch's amendment names, as its results script
# does. v9 re-scored all twelve runs but applies the result to two; the other
# ten were re-scored as a check (analysis/v9_results.py, AMENDED). Folders not
# listed here apply to every run they hold.
RESCORE_APPLIES_TO: dict[str, set[str]] = {
    "v9-rescore": {"v9-spec-minimal-r1", "v9-tests-none-r1"},
}
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
