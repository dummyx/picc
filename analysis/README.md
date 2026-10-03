# Analysis

Everything here reads the run records under `runs/` and never writes there.

- [report.md](report.md): the full write-up, one numbered section per batch
  (§1–6 v2, §7 v3, §8 v4, §9 the re-score of every v2–v4 final with random
  programs, §10 v5, §11 tokens, time and code, §12 v6, §13 v7, §14 v8, §15 v9,
  §16 v10, §17 v11–v14, §18 v15, §19 v16, §20 v17). v16 is written up in full
  in its plan ([docs/EXPERIMENT_PLAN_v16.md](../docs/EXPERIMENT_PLAN_v16.md))
  and v17 in [docs/REPORT_2026-09-23.md](../docs/REPORT_2026-09-23.md).
- [dashboard/](dashboard/): the results dashboard
  ([docs/DASHBOARD.md](../docs/DASHBOARD.md)).

The batch index, with what each batch compared and found, is in
[docs/README.md](../docs/README.md).

## Each batch's results

Each batch's results script (`v<N>_results.py`) was committed with its plan,
before the batch's first run; v5's and v16's were written after their runs
had started, and `v10_rescore.py` and `v17_internals.py` after their batches.
Run them from the repository root; every output below reproduces byte for
byte unless a note says otherwise.

| Batch | Script | Writes | Re-scored results it reads |
|---|---|---|---|
| v5 | [v5_results.py](v5_results.py) | `v5-results.md`, `v5-results.json`, the v3 entries of `v3-bridge.json` | `v3-bridge/`: the v3 (and v4) finals re-scored under the revised scorer |
| v6 | [v6_results.py](v6_results.py) | `v6-results.md`, `v6-results.json`, `v6-rescore.json` | `v6-rescore/`: every v6 final re-scored under Amendment 2, which is primary for all of them |
| v7 | [v7_results.py](v7_results.py) | `v7-results.md`, `v7-results.json` | none (no re-score was needed) |
| v8 | [v8_results.py](v8_results.py) | `v8-results.md`, `v8-results.json` | — |
| v9 | [v9_results.py](v9_results.py) | `v9-results.md`, `v9-results.json` | `v9-rescore/<run>/`: all twelve runs re-scored after Amendments 1 and 2; primary only for `v9-spec-minimal-r1` and `v9-tests-none-r1`, the two the amendments name |
| v10 | [v10_results.py](v10_results.py) | `v10-results.json` (and a table on screen) | `v10-rescore/`: made by [v10_rescore.py](v10_rescore.py), the three runs Amendment 2 re-scored |
| v11, v12 | [v11_results.py](v11_results.py), [v12_results.py](v12_results.py) | `v11-results.json`, `v12-results.json`: both `{}`, the batches were stopped | — |
| v15 | [v15_results.py](v15_results.py) | `v15-results.json` | — |
| v16 | [v16_results.py](v16_results.py) | the screen only | — |
| v17 | [v17_results.py](v17_results.py), [v17_internals.py](v17_internals.py) | the screen (the first 57 lines of `v17-results.md`), `v17-internals.json` | — |
| v18 | [v18_results.py](v18_results.py) | the screen only (6 runs; the batch was stopped) | — |
| v19 | [v19_results.py](v19_results.py) | the screen only | — |

The v10–v19 scripts read the study summary (`runs/study-results/<study-id>/runs.csv`,
written by `make study-summary`) rather than the runs directly.

## Across batches

| Script | What it measures | Writes |
|---|---|---|
| [dimensions.py](dimensions.py) | tokens, time and code shape, v2–v5; also a helper module the v6–v9 scripts import | `dimensions.md`, `.json`, `.csv` |
| [process_metrics.py](process_metrics.py) | how the agent worked in every run (turns, tool calls, self-tests) | Markdown on the screen; `--json FILE` |
| [typing_metrics.py](typing_metrics.py) | whether the TypeScript arm really used types, v4 and v7 | `typing-metrics.*` (v4), `typing-metrics-v7.*` (v7) |
| [fuzz_differential.py](fuzz_differential.py) | runs a compiler on random programs and compares it with GCC, on the host | the screen, `--json` |
| [fuzz_rescore.py](fuzz_rescore.py) | combines the v2–v4 random-program results | `fuzz-rescore.md`, `fuzz-rescore.json` |
| [turn_shape.py](turn_shape.py) | tool calls per reply against broken conversations, v10–v12 | `turn-shape.json` |
| [reasoning_tokens.py](reasoning_tokens.py) | reasoning tokens per reply, counted with the model's own tokenizer | the screen |

`condition-shape.json` (report §17.4) and `v15-censoring.json` (report §18.4)
were computed by hand; no script writes them.

## Regenerating

```bash
python3 analysis/v9_results.py                       # likewise v5-v8, v10-v12, v15, v16
python3 analysis/v17_results.py
python3 analysis/v18_results.py
python3 analysis/v19_results.py
.venv-sglang/bin/python analysis/v17_internals.py    # needs the `tokenizers` package
.venv-sglang/bin/python analysis/reasoning_tokens.py RUN_ID [RUN_ID ...]
python3 analysis/fuzz_rescore.py --results-dir analysis/fuzz-rescore/results \
    --stages-dir analysis/fuzz-rescore/stages \
    --markdown analysis/fuzz-rescore.md --json analysis/fuzz-rescore.json
python3 analysis/typing_metrics.py --run v7-ts-strict-r1 ...   # pass the batch's run ids
python3 analysis/v10_rescore.py --list                # what Amendment 2 re-scores (Docker)
```

Outputs that must not be regenerated blindly, because part of them was
written by hand:

- `v17-results.md`: lines 58 onwards (the reading of the result and a
  correction) are not script output.
- `v3-bridge.json`: the v4 entries were added with the v4 re-score;
  `v5_results.py` keeps them.
- `dimensions.json` and `dimensions.csv`: a later rename (cohort to batch) was
  applied by hand, so a fresh run differs in key order and the csv header.
- `process-report.md` and `process-metrics.json`: a snapshot of the 54 runs
  that existed on 2026-09-11; a fresh run covers every run.
- `typing-metrics*.{md,json}`: a fresh run by study id also picks up that
  study's trial runs; pass the batch's run ids with `--run`.

## Known quirks, left as they were

These scripts are the record of how each batch was analysed, so their logic
is not changed after the fact:

- `v12_results.py`'s table comparing v10–v12 prints no rows: its
  `.replace("v2", ...)` does nothing to the `-v3` study ids.
- `v16_results.py` reads the SQL study's current id, so today it reports the
  v17 runs; `--run v16-sql-python-typed-r1` still works for v16's.
- `v15_results.py`'s "rounds" column is blank; `runs.csv` has no such column.
- `typing_metrics.py` titles its Markdown "(picc-types-v1)" whatever it is
  given.
