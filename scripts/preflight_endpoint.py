#!/usr/bin/env python3
"""Verify the local model endpoint before launching a run.

The harness freezes its client-side configuration, but a self-hosted model
server is operator-managed: it can be restarted on a different checkpoint, or
with a smaller context, without anything in the repository changing. This
preflight asks the server what it is actually serving and compares that with
the frozen configuration.

Two server flavours are understood. `llama-server` answers `/props` with a
`model_alias` and an `n_ctx`. SGLang answers `/get_model_info` with a
`model_path` and `served_model_name`, and `/get_server_info` with its resolved
server arguments. Both are normalised to the same record.

Besides the model identity, the usable context is checked. SGLang sizes its KV
pool from whatever VRAM is left after the weights, so it will start with a pool
far smaller than the `--context-length` it advertises; a conversation that
outgrows the pool is rejected mid-run. `LOCAL_CONTEXT_WINDOW` must fit in what
the server can actually hold, and the harness refuses to start when it does not.

Exit status: 0 verified (or nothing to verify for a hosted provider), 2 the
served model or the usable context does not match the frozen configuration,
3 the endpoint is unreachable or does not identify itself.

Usage:
    python3 scripts/preflight_endpoint.py [--record runs/preflight.json]
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from common import (
    ExperimentError,
    api_key_for,
    atomic_write_json,
    context_budget_problems,
    is_local_provider,
    load_config,
    require_model_id,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--record", type=Path, help="write the preflight record as JSON to this path")
    parser.add_argument("--timeout", type=float, default=15.0)
    return parser.parse_args()


def fetch_json(url: str, key: str, timeout: float) -> dict[str, Any]:
    headers = {"Authorization": f"Bearer {key}"} if key else {}
    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        value = json.loads(response.read().decode("utf-8"))
    return value if isinstance(value, dict) else {}


def endpoint_root(base_url: str) -> str:
    base = base_url.rstrip("/")
    return base[: -len("/v1")] if base.endswith("/v1") else base


# Keys that only SGLang's /get_model_info carries. llama-server's /props has
# none of them, so their presence is what tells the two servers apart without
# having to ask the operator which one they started.
SGLANG_MARKERS = ("served_model_name", "tokenizer_path", "is_generation")


def describe_server(root: str, key: str, timeout: float) -> dict[str, Any]:
    """Normalise either server's metadata into one shape.

    Returns a dict with `kind`, `served_model`, `served_model_path`,
    `context_length` (what the server will accept for one request, or None),
    and the raw fields worth keeping in the record.
    """
    props: dict[str, Any] = {}
    try:
        props = fetch_json(f"{root}/props", key, timeout)
    except (urllib.error.URLError, OSError, ValueError):
        props = {}

    if props.get("model_alias") or (props and not any(m in props for m in SGLANG_MARKERS)):
        generation = props.get("default_generation_settings") or {}
        return {
            "kind": "llama.cpp",
            "served_model": str(props.get("model_alias") or ""),
            "served_model_path": str(props.get("model_path") or ""),
            "context_length": generation.get("n_ctx"),
            "server_total_slots": props.get("total_slots"),
            "server_build": props.get("build_info") or props.get("version"),
        }

    info = fetch_json(f"{root}/get_model_info", key, timeout)
    if not any(marker in info for marker in SGLANG_MARKERS):
        return {"kind": "unknown", "served_model": "", "served_model_path": "", "context_length": None}

    try:
        server = fetch_json(f"{root}/get_server_info", key, timeout)
    except (urllib.error.URLError, OSError, ValueError):
        server = {}
    args = server.get("server_args") or {}

    # Two different ceilings, and a request has to clear both: `context_length`
    # is what the model was launched to accept, `max_total_num_tokens` is how
    # many tokens the KV pool can actually hold. With --max-running-requests 1
    # a single conversation may use the whole pool, so the usable context is
    # the smaller of the two.
    declared = server.get("context_length") or args.get("context_length")
    pool = server.get("max_total_num_tokens") or args.get("max_total_num_tokens")
    usable = min([v for v in (declared, pool) if isinstance(v, int) and v > 0], default=None)

    return {
        "kind": "sglang",
        "served_model": str(info.get("served_model_name") or info.get("model_path") or ""),
        "served_model_path": str(info.get("model_path") or ""),
        "context_length": usable,
        "server_declared_context_length": declared,
        "server_max_total_tokens": pool,
        "server_max_running_requests": server.get("max_running_requests") or args.get("max_running_requests"),
        "server_attention_backend": args.get("attention_backend"),
        "server_kv_cache_dtype": args.get("kv_cache_dtype"),
        "server_build": server.get("version") or server.get("sglang_version"),
    }


def preflight(config: dict[str, str], *, timeout: float) -> tuple[int, dict[str, Any]]:
    record: dict[str, Any] = {"checked_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    if not is_local_provider(config):
        record["status"] = "not_applicable"
        record["detail"] = "hosted provider; the harness cannot inspect the served model"
        return 0, record

    budget_problems = context_budget_problems(config)
    if budget_problems:
        record["status"] = "unsafe_context_budget"
        record["problems"] = budget_problems
        return 2, record

    root = endpoint_root(config.get("LOCAL_BASE_URL", ""))
    _, key = api_key_for(config)
    record["endpoint"] = root
    try:
        # SGLang answers /health with an empty 200 body, llama-server with a
        # JSON status, so a failure to parse here is not a failure to reach.
        try:
            health = fetch_json(f"{root}/health", key, timeout).get("status") or "ok"
        except ValueError:
            health = "ok"
        described = describe_server(root, key, timeout)
    except (urllib.error.URLError, OSError, ValueError) as error:
        record["status"] = "unreachable"
        record["detail"] = str(error)
        return 3, record

    served = described["served_model"]
    # Keep the server-specific extras (attention backend, pool sizes, build)
    # under their own names; the four normalised fields are set explicitly.
    extras = {
        key: value
        for key, value in described.items()
        if value is not None
        and key not in {"kind", "served_model", "served_model_path", "context_length"}
    }
    record.update(extras)
    record.update(
        {
            "health": health,
            "server_kind": described["kind"],
            "served_model_alias": served,
            "served_model_path": described["served_model_path"],
            "server_n_ctx": described.get("context_length"),
        }
    )

    expected_model = require_model_id(config)
    if not served:
        record["status"] = "unverifiable"
        record["detail"] = "endpoint does not expose model_alias"
        return 3, record
    if served != expected_model:
        record["status"] = "mismatch"
        record["problems"] = [f"served model alias {served!r} is not MODEL_ID {expected_model!r}"]
        return 2, record

    # The window the harness freezes into models.json has to be one the server
    # can actually hold. Pi compacts at n_ctx - reserveTokens and sends the
    # whole conversation, so a window wider than the KV pool is not a slow
    # degradation: the request is rejected and the session dies.
    usable = described.get("context_length")
    declared_window = config.get("LOCAL_CONTEXT_WINDOW")
    if isinstance(usable, int) and usable > 0 and declared_window:
        try:
            wanted = int(declared_window)
        except ValueError:
            wanted = 0
        if wanted > usable:
            record["status"] = "context_too_small"
            record["problems"] = [
                f"LOCAL_CONTEXT_WINDOW={wanted} exceeds the {usable} tokens this server can hold "
                f"for one request. Lower LOCAL_CONTEXT_WINDOW (and the compaction budget with it) "
                f"or give the server more room."
            ]
            return 2, record

    record["status"] = "verified"
    return 0, record


def main() -> int:
    args = parse_args()
    config = load_config()
    status, record = preflight(config, timeout=args.timeout)
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
