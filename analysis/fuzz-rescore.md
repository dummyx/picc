# Fuzz re-score of stored batch finals

Every batch final snapshot was exported from its run workspace, rebuilt inside the pinned
image exactly as the evaluator builds it, and fuzzed on the host against GCC with
`analysis/fuzz_differential.py` (seed 20260830, stage limit = the batch's task scope).
**Fuzz pass rate** = share of generated programs on which the candidate's compiled output
agrees with GCC's exit status and stdout; rejecting a valid program, failing to assemble,
crashing, and wrong results all count as failures. **Full scope** = 300 programs using the
batch's whole feature set at once, so one broken feature fails every program. **Fuzz macro**
= mean over stages 1..K of the pass rate on 100 programs restricted to that stage's cumulative
subset, the fuzz analogue of the corpus macro score. The corpus column is the planned in advance
hidden macro score. This is a descriptive re-score, not a change to any primary endpoint.

## v2 (pilot profile, stages 1–6, Rust)

| Run | Condition | Rep | Corpus hidden | Fuzz macro (mean over stages) | Per-stage fuzz pass (stage 1→K) | Full-scope fuzz pass | Failure kinds at full scope |
|---|---|---:|---:|---:|---|---:|---|
| `v2-baseline-r1` | `baseline` | 1 | 0.9583 | 1.0000 | 1.00 1.00 1.00 1.00 1.00 1.00 | 1.0000 | none |
| `v2-baseline-r2` | `baseline` | 2 | 0.8981 | 1.0000 | 1.00 1.00 1.00 1.00 1.00 1.00 | 1.0000 | none |
| `v2-baseline-r3` | `baseline` | 3 | 0.8981 | 1.0000 | 1.00 1.00 1.00 1.00 1.00 1.00 | 1.0000 | none |
| `v2-prompt-minimal-r1` | `prompt-minimal` | 1 | 0.9583 | 1.0000 | 1.00 1.00 1.00 1.00 1.00 1.00 | 1.0000 | none |
| `v2-prompt-minimal-r2` | `prompt-minimal` | 2 | 0.9583 | 1.0000 | 1.00 1.00 1.00 1.00 1.00 1.00 | 1.0000 | none |
| `v2-prompt-minimal-r3` | `prompt-minimal` | 3 | 0.8773 \* | 1.0000 | 1.00 1.00 1.00 1.00 1.00 1.00 | 1.0000 | none |
| `v2-spec-architecture-r1` | `spec-architecture` | 1 | 0.8704 | 0.8200 | 1.00 0.83 0.79 0.87 0.66 0.77 | 0.7233 | wrong_behavior=83 |
| `v2-spec-architecture-r2` | `spec-architecture` | 2 | 0.8634 | 0.9683 | 1.00 1.00 1.00 0.94 0.94 0.93 | 0.9400 | wrong_behavior=18 |
| `v2-spec-architecture-r3` | `spec-architecture` | 3 | 0.9583 | 1.0000 | 1.00 1.00 1.00 1.00 1.00 1.00 | 1.0000 | none |
| `v2-spec-brief-r1` | `spec-brief` | 1 | 0.9583 | 1.0000 | 1.00 1.00 1.00 1.00 1.00 1.00 | 1.0000 | none |
| `v2-spec-brief-r2` | `spec-brief` | 2 | 0.8981 | 1.0000 | 1.00 1.00 1.00 1.00 1.00 1.00 | 1.0000 | none |
| `v2-spec-brief-r3` | `spec-brief` | 3 | 0.8770 | 1.0000 | 1.00 1.00 1.00 1.00 1.00 1.00 | 1.0000 | none |
| `v2-spec-inline-r1` | `spec-inline` | 1 | 0.8981 | 1.0000 | 1.00 1.00 1.00 1.00 1.00 1.00 | 1.0000 | none |
| `v2-spec-inline-r2` | `spec-inline` | 2 | 0.9583 | 1.0000 | 1.00 1.00 1.00 1.00 1.00 1.00 | 1.0000 | none |
| `v2-spec-inline-r3` | `spec-inline` | 3 | 0.9583 | 1.0000 | 1.00 1.00 1.00 1.00 1.00 1.00 | 1.0000 | none |

| Condition | n | Corpus median | Fuzz macro median | Fuzz macro range | Full-scope fuzz median |
|---|---:|---:|---:|---|---:|
| `baseline` | 3 | 0.8981 | 1.0000 | 1.000–1.000 | 1.0000 |
| `prompt-minimal` | 3 | 0.9583 | 1.0000 | 1.000–1.000 | 1.0000 |
| `spec-architecture` | 3 | 0.8704 | 0.9683 | 0.820–1.000 | 0.9400 |
| `spec-brief` | 3 | 0.8981 | 1.0000 | 1.000–1.000 | 1.0000 |
| `spec-inline` | 3 | 0.9583 | 1.0000 | 1.000–1.000 | 1.0000 |

Rank agreement with the corpus across the batch's 15 finals (Spearman ρ): fuzz macro 0.623, full-scope fuzz 0.623.

## v3 (main profile, stages 1–10, Rust)

| Run | Condition | Rep | Corpus hidden | Fuzz macro (mean over stages) | Per-stage fuzz pass (stage 1→K) | Full-scope fuzz pass | Failure kinds at full scope |
|---|---|---:|---:|---:|---|---:|---|
| `v3-baseline-r1` | `baseline` | 1 | 0.8188 | 1.0000 | 1.00 1.00 1.00 1.00 1.00 1.00 1.00 1.00 1.00 1.00 | 1.0000 | none |
| `v3-baseline-r2` | `baseline` | 2 | 0.9306 | 0.9530 | 1.00 1.00 1.00 1.00 1.00 1.00 1.00 1.00 0.72 0.81 | 0.7700 | wrong_behavior=69 (crashes=69) |
| `v3-baseline-r3` | `baseline` | 3 | 0.8194 | 0.9560 | 1.00 1.00 1.00 1.00 1.00 0.92 0.88 0.95 0.89 0.92 | 0.8833 | wrong_behavior=35 (crashes=1) |
| `v3-tests-none-r1` | `tests-none` | 1 | 0.8458 | 1.0000 | 1.00 1.00 1.00 1.00 1.00 1.00 1.00 1.00 1.00 1.00 | 1.0000 | none |
| `v3-tests-none-r2` | `tests-none` | 2 | 0.7492 | 0.7150 | 1.00 1.00 1.00 0.86 0.80 0.82 0.82 0.53 0.32 0.00 | 0.0000 | rejected_valid_program=300 |
| `v3-tests-none-r3` | `tests-none` | 3 | 0.6839 | 0.2280 | 1.00 1.00 0.02 0.07 0.02 0.06 0.04 0.07 0.00 0.00 | 0.0000 | assembly_or_link_failure=300 |

| Condition | n | Corpus median | Fuzz macro median | Fuzz macro range | Full-scope fuzz median |
|---|---:|---:|---:|---|---:|
| `baseline` | 3 | 0.8194 | 0.9560 | 0.953–1.000 | 0.8833 |
| `tests-none` | 3 | 0.7492 | 0.7150 | 0.228–1.000 | 0.0000 |

Rank agreement with the corpus across the batch's 6 finals (Spearman ρ): fuzz macro 0.551, full-scope fuzz 0.530.

Planned in advance contrast `tests-none` − `baseline`, paired by replicate:

| Rep | Corpus Δ | Fuzz macro Δ | Full-scope fuzz Δ |
|---:|---:|---:|---:|
| 1 | +0.0270 | +0.0000 | +0.0000 |
| 2 | -0.1813 | -0.2380 | -0.7700 |
| 3 | -0.1355 | -0.7280 | -0.8833 |
| median | -0.1355 | -0.2380 | -0.7700 |

## v4 (main profile, stages 1–10, TypeScript vs JavaScript)

| Run | Condition | Rep | Corpus hidden | Fuzz macro (mean over stages) | Per-stage fuzz pass (stage 1→K) | Full-scope fuzz pass | Failure kinds at full scope |
|---|---|---:|---:|---:|---|---:|---|
| `v4-js-untyped-r1` | `js-untyped` | 1 | 0.8833 | 1.0000 | 1.00 1.00 1.00 1.00 1.00 1.00 1.00 1.00 1.00 1.00 | 1.0000 | none |
| `v4-js-untyped-r2` | `js-untyped` | 2 | 0.8389 | 1.0000 | 1.00 1.00 1.00 1.00 1.00 1.00 1.00 1.00 1.00 1.00 | 1.0000 | none |
| `v4-js-untyped-r3` | `js-untyped` | 3 | 0.8278 | 0.9990 | 1.00 1.00 1.00 1.00 1.00 1.00 1.00 1.00 0.99 1.00 | 1.0000 | none |
| `v4-ts-strict-r1` | `ts-strict` | 1 | 0.8389 | 1.0000 | 1.00 1.00 1.00 1.00 1.00 1.00 1.00 1.00 1.00 1.00 | 1.0000 | none |
| `v4-ts-strict-r2` | `ts-strict` | 2 | 0.8653 | 1.0000 | 1.00 1.00 1.00 1.00 1.00 1.00 1.00 1.00 1.00 1.00 | 1.0000 | none |
| `v4-ts-strict-r3` | `ts-strict` | 3 | 0.8986 | 0.8060 | 1.00 1.00 1.00 1.00 1.00 1.00 1.00 1.00 0.04 0.02 | 0.0533 | rejected_valid_program=284 |

| Condition | n | Corpus median | Fuzz macro median | Fuzz macro range | Full-scope fuzz median |
|---|---:|---:|---:|---|---:|
| `js-untyped` | 3 | 0.8389 | 1.0000 | 0.999–1.000 | 1.0000 |
| `ts-strict` | 3 | 0.8653 | 1.0000 | 0.806–1.000 | 1.0000 |

Rank agreement with the corpus across the batch's 6 finals (Spearman ρ): fuzz macro -0.171, full-scope fuzz -0.664.

Planned in advance contrast `ts-strict` − `js-untyped`, paired by replicate:

| Rep | Corpus Δ | Fuzz macro Δ | Full-scope fuzz Δ |
|---:|---:|---:|---:|
| 1 | -0.0444 | +0.0000 | +0.0000 |
| 2 | +0.0264 | +0.0000 | +0.0000 |
| 3 | +0.0708 | -0.1930 | -0.9467 |
| median | +0.0264 | +0.0000 | +0.0000 |

\* Corpus score recorded as 0.0 by an audit false positive and corrected post hoc (report §3.2).
