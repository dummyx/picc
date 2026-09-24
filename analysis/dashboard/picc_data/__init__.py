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

from .classify import describe_call, file_kind, shell_kinds, why_failed
from .records import EXTRACTOR_VERSION, DataError
from .results import Results

__all__ = ["DataError", "EXTRACTOR_VERSION", "Results", "describe_call", "file_kind", "shell_kinds", "why_failed"]
