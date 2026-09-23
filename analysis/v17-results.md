## SQL engine (picc-sql-minimal-v7): 15 included runs

| condition | rep | hidden | last buildable | replies | writes | cut off | stream errors | broken compactions |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| rust | 1 | 0.4454 | 0.4454 | 308 | 122 |  0.0% |  0.0% | 0 |
| rust | 2 | 0.5985 | 0.5985 | 442 | 125 |  0.0% |  0.0% | 0 |
| rust | 3 | 0.3414 | 0.3414 | 367 | 140 |  0.0% |  0.0% | 0 |
| python | 1 | 0.7555 | 0.7555 | 457 | 121 |  0.0% |  0.0% | 0 |
| python | 2 | 0.8508 | 0.8508 | 415 | 122 |  0.0% |  0.0% | 0 |
| python | 3 | 0.0000 | 0.0000 | 478 | 124 |  0.0% |  0.0% | 0 |
| python-typed | 1 | 0.1341 | 0.1341 | 409 | 123 |  0.0% |  0.0% | 0 |
| python-typed | 2 | 0.8216 | 0.8216 | 350 | 94 |  0.0% |  0.0% | 0 |
| python-typed | 3 | 0.5273 | 0.5273 | 382 | 126 |  0.0% |  0.0% | 0 |
| javascript | 1 | 0.6454 | 0.6454 | 404 | 121 |  0.2% |  0.0% | 0 |
| javascript | 2 | 0.8148 | 0.8148 | 438 | 121 |  0.0% |  0.0% | 0 |
| javascript | 3 | 0.7930 | 0.7930 | 360 | 80 |  0.3% |  0.0% | 0 |
| typescript | 1 | 0.0000 | 0.0000 | 195 | 51 |  1.0% |  0.0% | 0 |
| typescript | 2 | 0.7636 | 0.7636 | 350 | 76 |  0.3% |  0.0% | 0 |
| typescript | 3 | 0.0853 | 0.0853 | 407 | 103 |  0.2% |  0.0% | 0 |

### Endpoint 1: produced a working engine

- rust: 3/3
- python: 2/3
- python-typed: 3/3
- javascript: 3/3
- typescript: 2/3

With three replicates a difference of 3 to 0 is worth stating; anything smaller is not.

### Endpoint 2: hidden score, typed minus untyped, paired by replicate

**python-typed against python**

- replicate 1: -0.6214
- replicate 2: -0.0292

paired median: -0.3253 (threshold ±0.13)

**typing hurts**. At three replicates this is descriptive, not a test.

**typescript against javascript**  *(added mid-batch; see the amendment in the plan)*

- replicate 2: -0.0512
- replicate 3: -0.7077

paired median: -0.3795 (threshold ±0.13)

**typing hurts**. At three replicates this is descriptive, not a test.

### Within-condition spread

- rust: n=3, median 0.4454, range 0.3414-0.5985, spread 0.2571  <- exceeds the ±0.13 threshold
- python: n=3, median 0.7555, range 0.0000-0.8508, spread 0.8508  <- exceeds the ±0.13 threshold
- python-typed: n=3, median 0.5273, range 0.1341-0.8216, spread 0.6875  <- exceeds the ±0.13 threshold
- javascript: n=3, median 0.7930, range 0.6454-0.8148, spread 0.1694  <- exceeds the ±0.13 threshold
- typescript: n=3, median 0.0853, range 0.0000-0.7636, spread 0.7636  <- exceeds the ±0.13 threshold

---

## Reading of the result

Written after the data, and marked as such.

### The harness is fixed

5,762 replies across 15 runs: **6 cut off (0.10%), zero stream errors, zero
failed compactions**, and every run's last-buildable score equals its final
score, so no run was penalised by a bad last snapshot. In v15 the typed runs
lost 61-64% of their replies and wrote nothing at all. That question is
closed; this batch is analysable where v15 was not.

### Neither typing contrast resolves

Both return "typing hurts" under the rule fixed before the data: -0.3253 for
Python, -0.3795 for TypeScript. Both should be read as not resolved, for
reasons stated in the plan before these runs started.

**The two endpoints disagree, and they disagree in opposite directions for the
two languages.** On whether a run produced a working engine at all:
`python-typed` beat `python` 3/3 against 2/3, while `typescript` lost to
`javascript` 2/3 against 3/3. A factor that helped one typed arm and hurt the
other is not one effect measured twice.

**Each median rests on two pairs, and within each pair the two disagree**:
-0.6214 and -0.0292 for Python, -0.7077 and -0.0512 for TypeScript. In both
languages one pair is a near-tie and the other is a collapse.

**The noise is larger than the effect.** Within-condition spread runs 0.17 to
0.85 against a claimed effect of 0.33 to 0.38. A three-replicate contrast
cannot resolve a difference smaller than the scatter inside one condition.

### The two "typed" conditions are not the same treatment

This is the finding worth carrying forward, and it was not anticipated.

| condition | snapshots that failed to build |
|---|---|
| python-typed (`mypy --strict`) | **0 / 10** |
| python | 0 / 9 |
| javascript (`node --check`) | 1 / 10 |
| rust (`cargo`) | 1 / 12 |
| typescript (`tsc --strict --noEmitOnError`) | **4 / 9** |

`mypy --strict` never once blocked a Python snapshot. `tsc --strict` blocked
44% of TypeScript snapshots, and `typescript-r1` never compiled in three
rounds, so its zero is a gate failure and not a measurement of its engine --
that code was never executed and its quality is unknown.

So the two contrasts do not measure the same thing. The Python contrast
compares two arms that both always built: its numbers are engine quality (or
noise). The TypeScript contrast is dominated by whether the arm cleared its
gate at all. Pooling them, or treating one as a replication of the other,
would be wrong.

*Corrected 2026-09-23 (details in `docs/REPORT_2026-09-23.md` §4):* the gate
explains `typescript-r1`, which is excluded from the paired contrast. The
contrast's collapse pair is replicate 3, and `typescript-r3` cleared its gate
from round 1 on; its 0.085 comes from an engine that prints no block for
`CREATE TABLE`, `INSERT` or `CREATE INDEX`. Of the four failed TypeScript
snapshots, three are `typescript-r1`'s, caused by the agent type-checking with
a shortened command that lacked the Node and ES2022 settings, and one is
`typescript-r3`'s round 0, caused by a single stray brace from an edit saved
about a second before the stop.

### Zeros have four different causes

Every zero in this batch means something different, and all four are
indistinguishable in the score column alone:

- `python-r3` 0.0000 -- engine ran cleanly every round, exit 0, no crashes,
  but it never read the file named on its command line: it always opened its
  own six-statement sample `INPUT.sql` from the working folder, so every
  script received the answers to that sample. It also separated columns with
  spaces and quoted text. *(Corrected 2026-09-23; earlier text: "printed
  results in the wrong shape".)*
- `typescript-r1` 0.0000 -- never compiled. 21 type errors reduced to 3 over
  two rounds, then stalled on three redeclarations of Node globals that
  `@types/node` already provides. It declared them because it type-checked
  with a shortened command without `--types node` or `--lib es2022`.
- `typescript-r3` 0.0853 -- round 0 failed to build because of one stray brace
  (all 72 errors; without it the file checks clean). It built from round 1 on,
  but its engine prints no block for `CREATE TABLE`, `INSERT` or
  `CREATE INDEX`, so from the first table on every answer is compared with the
  wrong statement. *(Corrected 2026-09-23; earlier text: "spent most of its
  budget reaching a clean build (72 errors, including 25 syntax errors from a
  truncated write)".)*
- `javascript-r3` round 0 -- its entry file did not exist yet at the first
  snapshot, because its first reply ran to the 32,768-token reply limit while
  reasoning in plain text and issued no command; it recovered to the batch's
  best score, 0.8804 visible.

### What this batch is actually evidence for

1. The harness repairs hold under 30 hours of continuous load.
2. Run-to-run variance on this task exceeds the effect size these batches are
   designed to detect. Three replicates is not enough here, and no amount of
   careful analysis fixes that.
3. The build gate, not the type system, dominates the TypeScript result. Any
   future typing contrast should report gate failures separately from scores,
   or the two are confounded. *(Corrected 2026-09-23: this holds for
   `typescript-r1` only; `typescript-r3`'s low score is an output-rule failure,
   see above.)*

A fourth replicate would not help. What would: more replicates, a longer
budget so a run is not scored mid-repair, or an endpoint that separates "did
it satisfy its gate" from "how good is the engine".
