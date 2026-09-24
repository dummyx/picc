"""The object the server asks: one Results per repository, built from the
mixins, each covering one kind of question.
"""

from __future__ import annotations

import queue
import threading
from pathlib import Path
from typing import Any

from .records import DEFAULT_TOKENIZER, Redactor, Store
from .runs import RunsMixin
from .timeline import TimelineMixin
from .conversation import ConversationMixin
from .workspace import WorkspaceMixin
from .testresults import TestResultsMixin
from .pages import PagesMixin
from .warm import WarmUpMixin


# --------------------------------------------------------------------------
# the results


class Results(
    RunsMixin, TimelineMixin, ConversationMixin, WorkspaceMixin, TestResultsMixin, PagesMixin, WarmUpMixin
):
    """Everything the dashboard shows, one method per question (see the mixins)."""

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
