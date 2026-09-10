#!/usr/bin/env python3
"""Verify the local model endpoint before launching a run.

The harness freezes its client-side configuration, but a self-hosted
`llama-server` is operator-managed: it can be restarted on a different model
file without anything in the repository changing. This preflight asks the
server which file it is serving (`/props`), hashes that file (cached by path,
size, and mtime so a 17 GB file is hashed once), and compares the digest with
the pre-registered `LOCAL_MODEL_SHA256`. Exit status: 0 verified (or nothing
to verify for a hosted provider), 2 the served model does not match, 3 the
endpoint is unreachable or does not expose its model path.

Usage:
    python3 scripts/preflight_endpoint.py [--record runs/preflight.json] [--skip-hash]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from common import ExperimentError, REPO_ROOT, api_key_for, atomic_write_json, is_local_provider, load_config, require_model_id

DIGEST_CACHE = REPO_ROOT / "runs" / ".model-digest-cache.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expect-sha256", help="override LOCAL_MODEL_SHA256 from the configuration")
    parser.add_argument("--skip-hash", action="store_true", help="report the served path without hashing it")
    parser.add_argument("--record", type=Path, help="write the preflight record as JSON to this path")
    parser.add_argument("--timeout", type=float, default=15.0)
    return parser.parse_args()


def fetch_json(url: str, key: str, timeout: float) -> dict[str, Any]:
    headers = {"Authorization": f"Bearer {key}"} if key else {}
    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        value = json.loads(response.read().decode("utf-8"))
    return value if isinstance(value, dict) else {}


def cached_digest(path: Path) -> str:
    """SHA-256 of `path`, cached by path, size, and mtime."""
    stat = path.stat()
    key = f"{path}\0{stat.st_size}\0{stat.st_mtime_ns}"
    cache: dict[str, Any] = {}
    if DIGEST_CACHE.is_file():
        try:
            loaded = json.loads(DIGEST_CACHE.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                cache = loaded
        except (OSError, json.JSONDecodeError):
            cache = {}
    cached = cache.get(key)
    if isinstance(cached, str) and len(cached) == 64:
        return cached
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(block)
    value = digest.hexdigest()
    cache[key] = value
    atomic_write_json(DIGEST_CACHE, cache)
    return value


def endpoint_root(base_url: str) -> str:
    base = base_url.rstrip("/")
    return base[: -len("/v1")] if base.endswith("/v1") else base


def preflight(config: dict[str, str], *, expect_sha256: str | None, skip_hash: bool, timeout: float) -> tuple[int, dict[str, Any]]:
    record: dict[str, Any] = {"checked_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    if not is_local_provider(config):
        record["status"] = "not_applicable"
        record["detail"] = "hosted provider; the harness cannot inspect the served model"
        return 0, record

    root = endpoint_root(config.get("LOCAL_BASE_URL", ""))
    _, key = api_key_for(config)
    record["endpoint"] = root
    try:
        health = fetch_json(f"{root}/health", key, timeout)
        props = fetch_json(f"{root}/props", key, timeout)
    except (urllib.error.URLError, OSError, ValueError) as error:
        record["status"] = "unreachable"
        record["detail"] = str(error)
        return 3, record

    served_alias = str(props.get("model_alias") or "")
    served_path = str(props.get("model_path") or "")
    record.update(
        {
            "health": health.get("status"),
            "served_model_alias": served_alias,
            "served_model_path": served_path,
            "server_n_ctx": (props.get("default_generation_settings") or {}).get("n_ctx"),
            "server_total_slots": props.get("total_slots"),
            "server_build": props.get("build_info") or props.get("version"),
        }
    )
    problems: list[str] = []
    expected_model = require_model_id(config)
    if served_alias and served_alias != expected_model:
        problems.append(f"served model alias {served_alias!r} is not MODEL_ID {expected_model!r}")

    expected = (expect_sha256 or config.get("LOCAL_MODEL_SHA256", "") or "").strip().lower()
    record["expected_sha256"] = expected or None
    if not served_path:
        record["status"] = "unverifiable"
        record["detail"] = "endpoint does not expose model_path"
        return 3, record
    path = Path(served_path)
    if skip_hash:
        record["served_sha256"] = None
    elif not path.is_file():
        record["served_sha256"] = None
        if expected:
            problems.append(f"served model path is not readable on this host: {served_path}")
    else:
        started = time.monotonic()
        record["served_sha256"] = cached_digest(path)
        record["served_bytes"] = path.stat().st_size
        record["hash_seconds"] = round(time.monotonic() - started, 1)
        if expected and record["served_sha256"] != expected:
            problems.append(f"served model SHA-256 {record['served_sha256'][:16]}… is not the pre-registered {expected[:16]}…")

    if problems:
        record["status"] = "mismatch"
        record["problems"] = problems
        return 2, record
    record["status"] = "verified" if expected and record.get("served_sha256") else "recorded"
    if not expected:
        record["detail"] = "LOCAL_MODEL_SHA256 is unset; the served digest was recorded but not verified"
    return 0, record


def main() -> int:
    args = parse_args()
    config = load_config()
    status, record = preflight(config, expect_sha256=args.expect_sha256, skip_hash=args.skip_hash, timeout=args.timeout)
    if args.record:
        atomic_write_json(args.record, record)
    print(json.dumps(record, indent=2, sort_keys=True))
    return status


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ExperimentError as error:
        print(f"error: {error}", file=sys.stderr)
        raise SystemExit(1)
