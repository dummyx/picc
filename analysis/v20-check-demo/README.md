# The round check on six real zero runs

One file per run: the message `scripts/run_experiment.py:round_check_message`
composes from today's scorer (`--example`), run in the pinned image on the
run's final workspace as it stood when the run ended. Made by
`python3 analysis/v20_check_demo.py` before the v20 batch (2026-10-04); the
scorer was given one visible test so the check (build plus example) is all it
spends time on.

| run | hidden score | what the v18/v19 analysis found | what the message says |
|---|---:|---|---|
| `v18-sql-rust-r2` | 0 | read standard input, ignored the file name | built; on the example input it printed nothing; first difference line 1 |
| `v18-sql-python-typed-r2` | 0 | `1\|x` rows, no `ok N` line | built; its final state prints one error line and exits 1; first difference line 1 |
| `v18-sql-python-r2` | 0 | a value where the `ok N` line goes | built; `ok 1` for `INSERT` where `ok 0` is required; first difference line 2 |
| `v19-sql-rust-r3` | 0 | crate built in `/workspace/pisql/` | the build command, run in `/workspace`, failed: no `Cargo.toml` |
| `v19-c18-python-typed-r2` | 0 | never ran `mypy`; type errors | the build command failed, with the `mypy` error list |
| `v19-c18-rust-r1` | 0.500 (no valid program) | panic on every valid program | first example: exit 101, panic at `src/picc/ast.rs:446`; second example rejected as required |

Each agent would have read this after its first round instead of `Continue.`
