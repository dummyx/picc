## SQL engine (picc-sql-minimal-v7): 9 included runs

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

### Endpoint 1: produced a working engine

- rust: 3/3
- python: 2/3
- python-typed: 3/3

With three replicates a difference of 3 to 0 is worth stating; anything smaller is not.

### Endpoint 2: hidden score, typed minus untyped, paired by replicate

**python-typed against python**

- replicate 1: -0.6214
- replicate 2: -0.0292

paired median: -0.3253 (threshold ±0.13)

**typing hurts**. At three replicates this is descriptive, not a test.

### Within-condition spread

- rust: n=3, median 0.4454, range 0.3414-0.5985, spread 0.2571  <- exceeds the ±0.13 threshold
- python: n=3, median 0.7555, range 0.0000-0.8508, spread 0.8508  <- exceeds the ±0.13 threshold
- python-typed: n=3, median 0.5273, range 0.1341-0.8216, spread 0.6875  <- exceeds the ±0.13 threshold
