#!/usr/bin/env python3
"""Check that the local endpoint can do what the harness actually needs.

`make preflight` checks identity and size: is this the right model, and will
the context fit. That is not the same as checking the endpoint works. The
harness needs four things from it, and three of them fail silently when
misconfigured rather than returning an error:

1. a chat completion at all;
2. **tool calls parsed into `tool_calls`** — with the wrong `--tool-call-parser`
   the model still emits a perfectly good call, as text, and the agent simply
   never appears to use a tool;
3. **reasoning separated into `reasoning_content`** — without
   `--reasoning-parser` the thinking arrives inside `content` and Pi cannot
   tell reasoning from answer;
4. **a finish reason**, since the harness's truncation repair keys off
   `stopReason == "length"`.

It also reports the usable context and, when the server was launched with
--enable-strict-thinking, checks that a per-request thinking budget is
actually enforced.

Usage: python3 scripts/smoke_inference.py [--verbose]
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from common import (  # noqa: E402
    ExperimentError,
    api_key_for,
    is_local_provider,
    load_config,
    require_model_id,
)

TOOL = {
    "type": "function",
    "function": {
        "name": "write_file",
        "description": "Write text to a file in the workspace.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Path to write"},
                "content": {"type": "string", "description": "File contents"},
            },
            "required": ["path", "content"],
        },
    },
}


def post(url: str, key: str, payload: dict, timeout: float = 300.0) -> dict:
    body = json.dumps(payload).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if key:
        headers["Authorization"] = f"Bearer {key}"
    request = urllib.request.Request(url, data=body, headers=headers, method="POST")
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def get(url: str, key: str, timeout: float = 30.0) -> dict:
    headers = {"Authorization": f"Bearer {key}"} if key else {}
    with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=timeout) as r:
        value = json.loads(r.read().decode("utf-8"))
    return value if isinstance(value, dict) else {}


class Checks:
    def __init__(self) -> None:
        self.failures: list[str] = []

    def ok(self, name: str, detail: str = "") -> None:
        print(f"  PASS  {name}" + (f" — {detail}" if detail else ""))

    def bad(self, name: str, detail: str) -> None:
        print(f"  FAIL  {name} — {detail}")
        self.failures.append(f"{name}: {detail}")

    def note(self, name: str, detail: str) -> None:
        print(f"  --    {name} — {detail}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    config = load_config()
    if not is_local_provider(config):
        print("MODEL_PROVIDER is not local; nothing to smoke.")
        return 0

    base = config.get("LOCAL_BASE_URL", "").rstrip("/")
    root = base[: -len("/v1")] if base.endswith("/v1") else base
    model = require_model_id(config)
    _, key = api_key_for(config)
    checks = Checks()

    print(f"endpoint {base}")
    print(f"model    {model}\n")

    # Server shape, for the record.
    try:
        info = get(f"{root}/get_server_info", key)
        sargs = info.get("server_args") or {}
        declared = info.get("context_length") or sargs.get("context_length")
        pool = info.get("max_total_num_tokens") or sargs.get("max_total_num_tokens")
        checks.note("context", f"declared {declared}, KV pool {pool}")
    except (urllib.error.URLError, OSError, ValueError) as error:
        checks.note("server info", f"unavailable ({error})")
        pool = None

    # 1. A completion at all.
    try:
        reply = post(f"{base}/chat/completions", key, {
            "model": model,
            "messages": [{"role": "user", "content": "Reply with exactly: ready"}],
            "max_tokens": 2048,
        })
        choice = reply["choices"][0]
        text = (choice["message"].get("content") or "").strip()
        checks.ok("chat completion", f"{reply.get('usage', {}).get('completion_tokens', '?')} tokens")
    except Exception as error:  # noqa: BLE001 - any failure here is a failure
        checks.bad("chat completion", str(error))
        print("\nthe endpoint does not answer; nothing else can be checked")
        return 1

    # 2. Finish reason, which the truncation repair depends on.
    if choice.get("finish_reason"):
        checks.ok("finish_reason", choice["finish_reason"])
    else:
        checks.bad("finish_reason", "absent; truncation repair cannot detect a cut-off reply")

    # 3. Reasoning separated out.
    reasoning = choice["message"].get("reasoning_content")
    if reasoning:
        checks.ok("reasoning_content", f"{len(reasoning)} chars separated from content")
    elif "<think>" in text:
        checks.bad("reasoning_content",
                   "thinking arrived inside content; is --reasoning-parser set?")
    else:
        checks.note("reasoning_content", "empty (model may not have reasoned on this prompt)")

    # 4. Tool calls, the one that fails silently.
    try:
        reply = post(f"{base}/chat/completions", key, {
            "model": model,
            "messages": [{
                "role": "user",
                "content": "Create a file hello.txt containing the text 'hi'. Use the tool.",
            }],
            "tools": [TOOL],
            "max_tokens": 4096,
        })
        message = reply["choices"][0]["message"]
        calls = message.get("tool_calls") or []
        if calls:
            call = calls[0]
            name = call.get("function", {}).get("name")
            raw = call.get("function", {}).get("arguments") or "{}"
            try:
                parsed = json.loads(raw)
                checks.ok("tool_calls", f"{name}({', '.join(sorted(parsed))})")
            except json.JSONDecodeError:
                checks.bad("tool_calls", f"{name} arguments are not JSON: {raw[:120]}")
        else:
            body = (message.get("content") or "")
            hint = "looks like an unparsed call" if "<tool_call>" in body or "<function" in body else ""
            checks.bad("tool_calls",
                       f"no tool_calls in the reply; {hint or 'model declined'}. "
                       f"Check --tool-call-parser (qwen3_coder for this template). "
                       f"content began: {body[:120]!r}")
    except Exception as error:  # noqa: BLE001
        checks.bad("tool_calls", str(error))

    # 5. The thinking budget, tested rather than asked about.
    #
    # The server does not report --enable-strict-thinking anywhere, so whether
    # a budget is enforced cannot be read off /get_server_info. It has to be
    # measured: ask for something the model will over-think, once with a small
    # budget and once without, and compare. Without enforcement the two are
    # identical and the budget is being silently ignored -- which is the whole
    # hazard, since the request is accepted either way.
    budget = (config.get("LOCAL_THINKING_BUDGET", "") or "").strip()
    prompt = ("Design a complete SQL query engine from scratch: tokenizer, parser, "
              "planner, and executor. Consider alternatives for each component and "
              "justify your choices before writing any code.")
    try:
        def reason_and_answer(with_budget: int | None) -> tuple[int, int]:
            payload = {
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 4096,
            }
            if with_budget:
                payload["custom_params"] = {"thinking_budget": with_budget}
            message = post(f"{base}/chat/completions", key, payload)["choices"][0]["message"]
            return (len(message.get("reasoning_content") or ""),
                    len(message.get("content") or ""))

        free_reasoning, free_answer = reason_and_answer(None)
        capped_reasoning, capped_answer = reason_and_answer(256)

        if capped_reasoning < free_reasoning / 2:
            detail = (f"256-token budget cut reasoning from {free_reasoning} to "
                      f"{capped_reasoning} chars")
            if free_answer == 0 and capped_answer > 0:
                detail += f"; the uncapped reply produced no answer at all, the capped one {capped_answer} chars"
            checks.ok("thinking budget enforced", detail)
        else:
            checks.bad("thinking budget enforced",
                       f"a 256-token budget barely changed reasoning "
                       f"({free_reasoning} -> {capped_reasoning} chars). The server is "
                       f"ignoring it; launch it with --enable-strict-thinking "
                       f"(SGLANG_ENABLE_STRICT_THINKING=1 in config/sglang.env).")
    except Exception as error:  # noqa: BLE001
        checks.bad("thinking budget enforced", str(error))

    checks.note("configured budget", budget or "none (LOCAL_THINKING_BUDGET empty)")

    print()
    if checks.failures:
        print(f"{len(checks.failures)} check(s) failed:")
        for failure in checks.failures:
            print(f"  - {failure}")
        return 1
    print("all checks passed")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ExperimentError as error:
        print(f"error: {error}", file=sys.stderr)
        raise SystemExit(1)
