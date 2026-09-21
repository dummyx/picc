#!/usr/bin/env python3
"""Exact reasoning-token counts per reply, from recorded text.

Run records cannot answer "how long did the model reason": SGLang reports
`usage.reasoning_tokens` at the top level, Pi reads
`usage.completion_tokens_details.reasoning_tokens`, and so every reply records
`reasoning: 0`. Dividing character counts by a characters-per-token ratio does
not work either -- the ratio measured 2.8 on short prose, 3.3-3.9 on the
agent's own code reasoning and 4.3 on a design essay, and three successive
conclusions about the thinking budget were wrong because of it.

This counts instead. The reasoning text of every reply is in the event stream
(`thinking_delta` events; the `message_end` copy is no use for cut-off replies,
because truncation-repair.ts replaces it with a 1500-character stub), and the
served checkpoint's tokenizer is on disk. Tokenizing one with the other gives
the exact number the server saw, offline and without the GPU.

Needs the `tokenizers` package, which the SGLang venv has:

    .venv-sglang/bin/python analysis/reasoning_tokens.py RUN_ID [RUN_ID ...]
        [--budget 8192] [--tokenizer ~/models/Qwen3.8-27B-NVFP4/tokenizer.json]

Read-only over runs/.
"""

from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def replies(run_id: str):
    """Yield (reasoning_text, stop_reason, output_tokens) per assistant reply."""
    events = ROOT / "runs" / run_id / "artifacts" / "events"
    for path in sorted(events.glob("round-*.jsonl")):
        parts: list[str] = []
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            kind = event.get("type")
            if kind == "message_update":
                update = event.get("assistantMessageEvent") or {}
                if update.get("type") == "thinking_delta":
                    parts.append(update.get("delta") or "")
            elif kind == "message_end":
                message = event.get("message") or {}
                if message.get("role") == "assistant":
                    usage = message.get("usage") or {}
                    yield "".join(parts), message.get("stopReason"), usage.get("output") or 0
                parts = []


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("runs", nargs="+")
    parser.add_argument("--budget", type=int, default=8192)
    parser.add_argument("--tokenizer", type=Path,
                        default=Path.home() / "models" / "Qwen3.8-27B-NVFP4" / "tokenizer.json")
    args = parser.parse_args()

    try:
        from tokenizers import Tokenizer
    except ImportError:
        print("needs the `tokenizers` package: run with .venv-sglang/bin/python")
        return 2
    tokenizer = Tokenizer.from_file(str(args.tokenizer))

    print(f"budget {args.budget} tokens; tokenizer {args.tokenizer}\n")
    print(f"{'run':<28}{'replies':>8}{'cut off':>9}{'median':>8}{'p90':>8}{'max':>8}"
          f"{'at budget':>11}{'over budget':>13}")
    print("-" * 93)
    for run_id in args.runs:
        counts, cut, at_budget, over = [], 0, 0, 0
        for text, stop, _output in replies(run_id):
            n = len(tokenizer.encode(text, add_special_tokens=False).ids) if text else 0
            counts.append(n)
            cut += stop == "length"
            # The server counts the think-open token and forces the close, so a
            # budget-bound reply lands within a few tokens of the budget.
            at_budget += abs(n - args.budget) <= 8
            over += n > args.budget + 8
        if not counts:
            print(f"{run_id:<28} no replies found")
            continue
        counts.sort()
        print(f"{run_id:<28}{len(counts):>8}{cut:>9}{statistics.median(counts):>8.0f}"
              f"{counts[int(0.9 * len(counts))]:>8}{counts[-1]:>8}{at_budget:>11}{over:>13}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
