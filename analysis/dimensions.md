# Beyond the tests: tokens, time, and code across every main run

Exploratory and descriptive (not pre-registered). One row per completed main run of the v2–v5 cohorts; 
smoke/pilot runs excluded. Corpus scores are as stored (v2–v4 under the original oracle, v5 revised); fuzz macro is 
the post-hoc re-score for v2–v4 (50 programs per stage) and the in-harness score for v5 (100 per stage). 
Code characteristics are regex approximations over the final `src/` tree; function boundaries are heuristic.

## Per cohort and condition (medians)

| cohort | condition | n | fuzz macro | corpus hidden | output tokens | active minutes | idle minutes | assistant turns | tool calls | source loc | functions | mean function loc | self test programs | first build minutes |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| v2 | baseline | 3 | 1.000 | 0.898 | 155,434 | 61 | 45 | 56 | 61 | 2,061 | 62 | 32 | 27 | 45 |
| v2 | prompt-minimal | 3 | 1.000 | 0.958 | 184,289 | 55 | 35 | 163 | 167 | 2,155 | 73 | 29 | 0 | 45 |
| v2 | spec-architecture | 3 | 0.968 | 0.870 | 231,884 | 72 | 18 | 197 | 203 | 2,770 | 79 | 28 | 0 | 45 |
| v2 | spec-brief | 3 | 1.000 | 0.898 | 297,752 | 90 | 0.900 | 256 | 273 | 2,540 | 86 | 30 | 0 | 45 |
| v2 | spec-inline | 3 | 1.000 | 0.958 | 285,529 | 88 | 1.700 | 264 | 281 | 2,858 | 87 | 32 | 14 | 45 |
| v3 | baseline | 3 | 0.956 | 0.819 | 188,789 | 55 | 35 | 209 | 216 | 2,280 | 58 | 34 | 14 | 45 |
| v3 | tests-none | 3 | 0.680 | 0.749 | 103,830 | 46 | 45 | 36 | 52 | 2,250 | 72 | 28 | 62 | 45 |
| v4 | js-untyped | 3 | 1.000 | 0.839 | 223,195 | 86 | 3.800 | 170 | 171 | 1,146 | 142 | 7.900 | 5 | 45 |
| v4 | ts-strict | 3 | 1.000 | 0.865 | 297,427 | 89 | 1.300 | 253 | 261 | 1,964 | 210 | 7.400 | 9 | 45 |
| v5 | baseline | 4 | 0.696 | 0.839 | 234,082 | 68 | 23 | 234 | 242 | 2,124 | 68 | 30 | 23 | 45 |
| v5 | tests-none | 4 | 0.956 | 0.911 | 200,276 | 57 | 33 | 150 | 169 | 2,402 | 72 | 31 | 84 | 45 |

## What moves with correctness (Spearman rank correlation)

Pooled over all main runs, and within v5 alone (the only cohort scored in-harness by both oracles). 
With n this small treat |rho| below about 0.4 as noise.

| dimension | pooled n | rho vs fuzz | rho vs corpus | v5 n | v5 rho vs fuzz | v5 rho vs corpus |
|---|---:|---:|---:|---:|---:|---:|
| output tokens | 35 | 0.560 | 0.530 | 8 | 0.910 | 0.830 |
| thinking share of generated chars | 35 | -0.350 | -0.350 | 8 | -0.660 | -0.660 |
| active minutes | 35 | 0.540 | 0.500 | 8 | 0.840 | 0.740 |
| idle minutes (hangs) | 35 | -0.580 | -0.580 | 8 | -0.910 | -0.810 |
| assistant turns | 35 | 0.550 | 0.550 | 8 | 0.910 | 0.830 |
| tool calls | 35 | 0.570 | 0.540 | 8 | 0.910 | 0.830 |
| minutes to first buildable snapshot (round-quantized) | 35 | -0.270 | -0.280 | 8 | -0.800 | -0.750 |
| compiler source LOC | 35 | 0.150 | 0.500 | 8 | 0.700 | 0.650 |
| source files | 35 | -0.120 | 0.070 | 8 | 0.300 | 0.320 |
| functions | 35 | -0.010 | 0.130 | 8 | -0.380 | -0.360 |
| mean function LOC | 35 | 0.240 | 0.270 | 8 | 0.930 | 0.780 |
| longest function LOC | 35 | 0.230 | 0.150 | 8 | 0.480 | 0.360 |
| branch points per 100 LOC | 35 | 0.160 | -0.070 | 8 | 0.250 | 0.330 |
| comment ratio | 35 | 0.190 | 0.480 | 8 | 0.640 | 0.490 |
| unwrap/expect calls | 35 | 0.060 | 0.400 | 8 | 0.090 | 0.110 |
| panic/throw sites | 35 | 0.060 | -0.110 | 8 | — | — |
| self-written C test programs | 35 | 0.250 | 0.080 | 8 | 0.600 | 0.480 |
| self-test script + program LOC | 35 | 0.270 | 0.030 | 8 | 0.620 | 0.480 |
| final build seconds | 34 | 0.190 | 0.430 | 8 | 0.470 | 0.600 |
| median compile ms per hidden test | 33 | 0.210 | 0.130 | 7 | 0.510 | 0.210 |
| fuzz macro per M output tokens | 35 | 0.170 | 0.030 | 8 | 0.750 | 0.760 |
| source LOC per k output tokens | 35 | -0.510 | -0.270 | 8 | -0.910 | -0.810 |

## The same correlations without the hang lottery

Runs that lost fewer than five minutes idle (no hang, or a hang so late it cost nothing). 
If a dimension still tracks correctness here, it is not merely 'the run got to work longer'.

17 of 35 main runs never hung. Fuzz macro among them: median 1.000, min 0.953; among the 18 that hung: median 0.962.

| dimension | n | rho vs fuzz | rho vs corpus |
|---|---:|---:|---:|
| output tokens | 17 | 0.240 | 0.230 |
| thinking share of generated chars | 17 | -0.030 | 0.210 |
| active minutes | 17 | 0.150 | 0.170 |
| idle minutes (hangs) | 17 | -0.160 | -0.400 |
| assistant turns | 17 | 0.040 | 0.380 |
| tool calls | 17 | 0.080 | 0.270 |
| minutes to first buildable snapshot (round-quantized) | 17 | 0.020 | -0.190 |
| compiler source LOC | 17 | -0.040 | 0.500 |
| source files | 17 | 0.200 | -0.230 |
| functions | 17 | -0.290 | -0.410 |
| mean function LOC | 17 | -0.030 | 0.490 |
| longest function LOC | 17 | 0.160 | 0.420 |
| branch points per 100 LOC | 17 | -0.110 | -0.250 |
| comment ratio | 17 | -0.250 | 0.600 |
| unwrap/expect calls | 17 | 0.010 | 0.610 |
| panic/throw sites | 17 | 0.130 | -0.390 |
| self-written C test programs | 17 | 0.350 | 0.150 |
| self-test script + program LOC | 17 | 0.350 | -0.050 |
| final build seconds | 17 | 0.050 | 0.620 |
| median compile ms per hidden test | 17 | -0.060 | -0.360 |
| fuzz macro per M output tokens | 17 | -0.080 | -0.230 |
| source LOC per k output tokens | 17 | -0.070 | 0.510 |

## Paired within-cohort contrasts (variant minus its baseline, median over replicates)

Same replicate number = same block. Positive means the variant used or produced more.

| cohort | contrast | pairs | fuzz macro | output tokens | active minutes | assistant turns | tool calls | source loc | functions | self test loc | compactions |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| v2 | prompt-minimal − baseline | 3 | 0.000 | +28,855 | -6.700 | +46 | +47 | -27 | +6 | +40 | +4 |
| v2 | spec-brief − baseline | 3 | 0.000 | +142,318 | +43 | +203 | +212 | +538 | +19 | 0 | +6 |
| v2 | spec-inline − baseline | 3 | 0.000 | +130,095 | +27 | +208 | +226 | +797 | +25 | -75 | +6 |
| v2 | spec-architecture − baseline | 3 | -0.032 | +76,450 | +14 | +157 | +163 | +904 | +17 | -159 | +4 |
| v3 | tests-none − baseline | 3 | -0.273 | -84,959 | -10 | -124 | -117 | -487 | -4 | +432 | -4 |
| v4 | ts-strict − js-untyped | 3 | 0.000 | +19,307 | -0.200 | -4 | -4 | +619 | +70 | -10 | 0 |
| v5 | tests-none − baseline | 4 | -0.044 | -82,454 | -15 | -118 | -117 | +39 | -1.500 | +28 | -1.000 |

## Spread of the dimensions (all main runs)

| dimension | min | median | max |
|---|---:|---:|---:|
| output tokens | 61,032 | 231,884 | 381,928 |
| thinking share of generated chars | 0.962 | 0.981 | 0.996 |
| active minutes | 45 | 75 | 120 |
| idle minutes (hangs) | 0.100 | 15 | 46 |
| assistant turns | 30 | 209 | 502 |
| tool calls | 36 | 216 | 501 |
| minutes to first buildable snapshot (round-quantized) | 45 | 45 | 90 |
| compiler source LOC | 1,141 | 2,250 | 3,389 |
| source files | 1 | 6 | 10 |
| functions | 54 | 77 | 226 |
| mean function LOC | 6.800 | 29 | 38 |
| longest function LOC | 41 | 213 | 371 |
| branch points per 100 LOC | 8.600 | 12 | 32 |
| comment ratio | 0.002 | 0.032 | 0.070 |
| unwrap/expect calls | 0 | 35 | 52 |
| panic/throw sites | 0 | 0 | 6 |
| self-written C test programs | 0 | 14 | 999 |
| self-test script + program LOC | 0 | 307 | 29,867 |
| final build seconds | 0.010 | 0.425 | 0.680 |
| median compile ms per hidden test | 7.000 | 7.230 | 20 |
| fuzz macro per M output tokens | 0.000 | 3.596 | 10 |
| source LOC per k output tokens | 4.840 | 10 | 35 |

## Every run

| run | cohort | condition | replicate | fuzz macro | corpus hidden | output tokens | thinking share | active minutes | idle minutes | assistant turns | tool calls | first build minutes | source loc | source files | functions | mean function loc | max function loc | branches per 100 loc | comment ratio | unwrap or expect | self test programs | self test loc | median test compile ms | binary kb |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| v2-baseline-r1 | v2 | baseline | 1 | 1.000 | 0.958 | 242,834 | 0.968 | 76 | 0.200 | 322 | 330 | 45 | 2,406 | 6 | 67 | 33 | 277 | 12 | 0.034 | 30 | 159 | 976 | 7.230 | 626 |
| v2-baseline-r2 | v2 | baseline | 2 | 1.000 | 0.898 | 98,612 | 0.991 | 45 | 45 | 35 | 40 | 45 | 1,765 | 1 | 62 | 28 | 192 | 12 | 0.035 | 32 | 27 | 159 | 7.050 | 568 |
| v2-baseline-r3 | v2 | baseline | 3 | 1.000 | 0.898 | 155,434 | 0.993 | 61 | 45 | 56 | 61 | 61 | 2,061 | 6 | 54 | 32 | 234 | 11 | 0.028 | 39 | 0 | 0 | 7.120 | 621 |
| v2-prompt-minimal-r1 | v2 | prompt-minimal | 1 | 1.000 | 0.958 | 157,092 | 0.981 | 46 | 44 | 163 | 167 | 45 | 2,268 | 6 | 73 | 29 | 242 | 12 | 0.029 | 49 | 0 | 0 | 7.080 | 572 |
| v2-prompt-minimal-r2 | v2 | prompt-minimal | 2 | 1.000 | 0.958 | 295,839 | 0.977 | 90 | 0.400 | 295 | 312 | 90 | 2,155 | 5 | 74 | 28 | 171 | 14 | 0.047 | 33 | 126 | 2,081 | 7.360 | 598 |
| v2-prompt-minimal-r3 | v2 | prompt-minimal | 3 | 1.000 | 0.000 | 184,289 | 0.986 | 55 | 35 | 102 | 108 | 45 | 2,034 | 6 | 57 | 31 | 315 | 14 | 0.023 | 33 | 0 | 40 | — | 565 |
| v2-spec-architecture-r1 | v2 | spec-architecture | 1 | 0.820 | 0.870 | 100,864 | 0.993 | 45 | 45 | 45 | 55 | 45 | 2,280 | 7 | 79 | 25 | 163 | 11 | 0.032 | 38 | 0 | 0 | 7.160 | 598 |
| v2-spec-architecture-r2 | v2 | spec-architecture | 2 | 0.968 | 0.863 | 241,134 | 0.978 | 72 | 18 | 197 | 203 | 45 | 2,770 | 7 | 79 | 31 | 243 | 8.600 | 0.027 | 36 | 0 | 0 | 7.140 | 588 |
| v2-spec-architecture-r3 | v2 | spec-architecture | 3 | 1.000 | 0.958 | 231,884 | 0.977 | 75 | 15 | 213 | 252 | 45 | 2,965 | 7 | 89 | 28 | 293 | 8.700 | 0.043 | 41 | 1 | 310 | 7.160 | 613 |
| v2-spec-brief-r1 | v2 | spec-brief | 1 | 1.000 | 0.958 | 361,987 | 0.962 | 119 | 1.300 | 247 | 243 | 45 | 2,540 | 5 | 86 | 27 | 212 | 10 | 0.046 | 35 | 0 | 0 | 7.320 | 606 |
| v2-spec-brief-r2 | v2 | spec-brief | 2 | 1.000 | 0.898 | 279,477 | 0.985 | 89 | 0.900 | 256 | 302 | 45 | 2,303 | 6 | 69 | 30 | 371 | 15 | 0.023 | 37 | 142 | 2,477 | 7.260 | 606 |
| v2-spec-brief-r3 | v2 | spec-brief | 3 | 1.000 | 0.877 | 297,752 | 0.974 | 90 | 0.300 | 259 | 273 | 45 | 2,684 | 5 | 86 | 30 | 193 | 12 | 0.025 | 35 | 0 | 0 | 7.210 | 650 |
| v2-spec-inline-r1 | v2 | spec-inline | 1 | 1.000 | 0.898 | 255,967 | 0.981 | 87 | 2.800 | 237 | 241 | 45 | 2,250 | 6 | 57 | 34 | 240 | 13 | 0.028 | 36 | 0 | 0 | 7.260 | 612 |
| v2-spec-inline-r2 | v2 | spec-inline | 2 | 1.000 | 0.958 | 342,956 | 0.980 | 104 | 0.300 | 278 | 281 | 61 | 3,052 | 6 | 87 | 32 | 349 | 16 | 0.043 | 39 | 14 | 84 | 7.180 | 681 |
| v2-spec-inline-r3 | v2 | spec-inline | 3 | 1.000 | 0.958 | 285,529 | 0.981 | 88 | 1.700 | 264 | 287 | 45 | 2,858 | 6 | 99 | 26 | 201 | 14 | 0.050 | 52 | 122 | 425 | 7.140 | 643 |
| v3-baseline-r1 | v3 | baseline | 1 | 1.000 | 0.819 | 171,761 | 0.987 | 49 | 42 | 209 | 216 | 45 | 2,280 | 5 | 54 | 37 | 314 | 12 | 0.029 | 27 | 14 | 389 | 7.120 | 574 |
| v3-baseline-r2 | v3 | baseline | 2 | 0.953 | 0.931 | 299,741 | 0.981 | 90 | 0.400 | 340 | 350 | 45 | 3,389 | 6 | 89 | 34 | 258 | 12 | 0.040 | 41 | 0 | 0 | 7.240 | 742 |
| v3-baseline-r3 | v3 | baseline | 3 | 0.956 | 0.819 | 188,789 | 0.981 | 55 | 35 | 160 | 169 | 45 | 2,164 | 7 | 58 | 32 | 225 | 12 | 0.033 | 32 | 35 | 134 | 7.000 | 614 |
| v3-tests-none-r1 | v3 | tests-none | 1 | 1.000 | 0.846 | 381,928 | 0.964 | 120 | 0.500 | 502 | 501 | 45 | 2,250 | 6 | 72 | 27 | 213 | 10 | 0.033 | 31 | 594 | 17,568 | 7.180 | 620 |
| v3-tests-none-r2 | v3 | tests-none | 2 | 0.680 | 0.749 | 102,366 | 0.996 | 46 | 46 | 30 | 36 | 46 | 2,584 | 6 | 80 | 29 | 294 | 10 | 0.017 | 38 | 62 | 432 | 7.110 | 625 |
| v3-tests-none-r3 | v3 | tests-none | 3 | 0.228 | 0.684 | 103,830 | 0.992 | 45 | 45 | 36 | 52 | 45 | 1,677 | 6 | 54 | 28 | 172 | 16 | 0.042 | 2 | 55 | 411 | 7.100 | 606 |
| v4-js-untyped-r1 | v4 | js-untyped | 1 | 1.000 | 0.883 | 278,120 | 0.973 | 90 | 0.500 | 289 | 369 | 45 | 1,345 | 5 | 156 | 8.500 | 67 | 32 | 0.026 | 0 | 0 | 0 | 19 | 2 |
| v4-js-untyped-r2 | v4 | js-untyped | 2 | 1.000 | 0.839 | 142,527 | 0.976 | 46 | 44 | 123 | 127 | 45 | 1,141 | 4 | 139 | 7.900 | 49 | 30 | 0.039 | 19 | 999 | 29,867 | 18 | 2 |
| v4-js-untyped-r3 | v4 | js-untyped | 3 | 0.999 | 0.828 | 223,195 | 0.977 | 86 | 3.800 | 170 | 171 | 45 | 1,146 | 4 | 142 | 7.600 | 49 | 26 | 0.063 | 0 | 5 | 10 | 18 | 2 |
| v4-ts-strict-r1 | v4 | ts-strict | 1 | 1.000 | 0.839 | 297,427 | 0.978 | 89 | 1.300 | 253 | 261 | 46 | 1,964 | 7 | 226 | 7.400 | 66 | 18 | 0.006 | 28 | 9 | 467 | 20 | 3 |
| v4-ts-strict-r2 | v4 | ts-strict | 2 | 1.000 | 0.865 | 301,658 | 0.980 | 90 | 0.700 | 258 | 271 | 45 | 2,000 | 10 | 210 | 8.300 | 66 | 20 | 0.002 | 0 | 110 | 1,718 | 20 | 4 |
| v4-ts-strict-r3 | v4 | ts-strict | 3 | 0.806 | 0.899 | 185,738 | 0.978 | 56 | 34 | 166 | 167 | 45 | 1,414 | 7 | 180 | 6.800 | 41 | 22 | 0.021 | 0 | 0 | 0 | 19 | 4 |
| v5-baseline-r1 | v5 | baseline | 1 | 1.000 | 0.967 | 304,924 | 0.984 | 90 | 0.400 | 342 | 351 | 45 | 2,123 | 4 | 64 | 31 | 179 | 14 | 0.070 | 39 | 35 | 350 | 7.390 | 621 |
| v5-baseline-r2 | v5 | baseline | 2 | 1.000 | 0.956 | 303,024 | 0.984 | 90 | 0.100 | 336 | 347 | 45 | 3,148 | 6 | 87 | 34 | 293 | 12 | 0.041 | 44 | 172 | 821 | 7.360 | 642 |
| v5-baseline-r3 | v5 | baseline | 3 | 0.392 | 0.722 | 165,141 | 0.985 | 45 | 45 | 131 | 138 | 45 | 2,124 | 5 | 68 | 29 | 209 | 12 | 0.019 | 3 | 11 | 307 | 7.120 | 562 |
| v5-baseline-r4 | v5 | baseline | 4 | 0.019 | 0.585 | 61,032 | 0.987 | 46 | 46 | 32 | 39 | 46 | 2,118 | 6 | 69 | 26 | 168 | 11 | 0.024 | 38 | 0 | 0 | 7.300 | 557 |
| v5-tests-none-r1 | v5 | tests-none | 1 | 0.912 | 0.904 | 191,141 | 0.977 | 55 | 35 | 141 | 162 | 45 | 2,413 | 6 | 78 | 29 | 134 | 11 | 0.033 | 35 | 0 | 254 | 7.270 | 610 |
| v5-tests-none-r2 | v5 | tests-none | 2 | 1.000 | 0.974 | 209,410 | 0.981 | 60 | 30 | 158 | 176 | 45 | 2,413 | 7 | 66 | 33 | 239 | 12 | 0.026 | 33 | 107 | 756 | 7.160 | 597 |
| v5-tests-none-r3 | v5 | tests-none | 3 | 0.000 | 0.476 | 93,848 | 0.986 | 46 | 45 | 72 | 75 | 46 | 1,929 | 5 | 77 | 23 | 234 | 14 | 0.029 | 38 | 61 | 429 | — | 583 |
| v5-tests-none-r4 | v5 | tests-none | 4 | 1.000 | 0.918 | 299,760 | 0.982 | 90 | 0.600 | 307 | 315 | 45 | 2,391 | 6 | 57 | 38 | 268 | 12 | 0.041 | 27 | 145 | 1,261 | 7.430 | 589 |
