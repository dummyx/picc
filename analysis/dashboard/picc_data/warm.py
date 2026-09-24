"""Parsing every run once in the background, in worker processes, so pages
open instantly.
"""

from __future__ import annotations

import os
from concurrent.futures import as_completed, ProcessPoolExecutor
from pathlib import Path

from .records import DataError, fingerprint, read_locks


class WarmUpMixin:
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
        from .results import Results

        _WORKER[key] = Results(Path(root), Path(cache_dir), tokenizer_path=Path(tokenizer) if tokenizer else None)
    _WORKER[key]._warm_one(run_id)
