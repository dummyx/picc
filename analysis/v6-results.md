# v6 results digest

```
=== v6 runs (8/8 complete)
v6-baseline-r1     rep=1 h=1.5 rounds=2 stalls=2 cut-offs=0 vis=0.9830 hidden=0.9317 (95/104; valid 55/57, invalid 40/47) fuzz=1.0 [1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0] kinds={} build_ok=True audit_ok=True tokens in/out=561229/260210 active/idle=89.6/0.4 turns=308 tools=321 test_visible=13 loc=1883 fns=55 self-tests=181/1028 traj=[0.0, 0.9317] fails={'unexpected_accept': 7, 'unexpected_reject': 2}
v6-tests-none-r1   rep=1 h=1.5 rounds=2 stalls=2 cut-offs=0 vis=0.8997 hidden=0.9234 (96/104; valid 52/57, invalid 44/47) fuzz=1.0 [1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0] kinds={} build_ok=True audit_ok=True tokens in/out=290127/299569 active/idle=89.8/0.3 turns=244 tools=246 test_visible=0 loc=2575 fns=81 self-tests=92/249 traj=[0.0, 0.9234] fails={'unexpected_accept': 3, 'wrong_behavior': 1, 'unexpected_reject': 4}
v6-baseline-r2     rep=2 h=1.5 rounds=2 stalls=2 cut-offs=0 vis=0.9430 hidden=0.9500 (98/104; valid 55/57, invalid 43/47) fuzz=1.0 [1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0] kinds={} build_ok=True audit_ok=True tokens in/out=220305/295812 active/idle=88.8/1.3 turns=187 tools=222 test_visible=20 loc=2080 fns=74 self-tests=1/7 traj=[0.9431, 0.95] fails={'unexpected_accept': 4, 'unexpected_reject': 1, 'assembly_or_link_failure': 1}
v6-tests-none-r2   rep=2 h=1.5 rounds=2 stalls=2 cut-offs=0 vis=0.9299 hidden=0.9236 (97/104; valid 53/57, invalid 44/47) fuzz=1.0 [1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0] kinds={} build_ok=True audit_ok=True tokens in/out=265066/287118 active/idle=87.9/2.2 turns=297 tools=316 test_visible=0 loc=2716 fns=68 self-tests=169/1186 traj=[0.8986, 0.9236] fails={'unexpected_accept': 3, 'unexpected_reject': 4}
v6-baseline-r3     rep=3 h=1.5 rounds=2 stalls=2 cut-offs=1 vis=0.9914 hidden=0.9748 (101/104; valid 56/57, invalid 45/47) fuzz=1.0 [1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0] kinds={} build_ok=True audit_ok=True tokens in/out=362449/286084 active/idle=88.8/1.3 turns=235 tools=281 test_visible=24 loc=2788 fns=74 self-tests=194/1021 traj=[0.9345, 0.9748] fails={'unexpected_accept': 2, 'execution_timeout': 1}
    cut off: 'cd /workspace && cargo build --release --offline 2>&1 | grep -E "^error" -A8 | head -25; echo BUILD-'
v6-tests-none-r3   rep=3 h=1.5 rounds=2 stalls=2 cut-offs=0 vis=0.0000 hidden=0.0000 (0/104; valid 0/57, invalid 0/47) fuzz=0.0 [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0] kinds={} build_ok=False audit_ok=False tokens in/out=296895/289850 active/idle=88.6/1.5 turns=395 tools=408 test_visible=0 loc=1821 fns=55 self-tests=142/1834 traj=[0.6935, 0.0] fails={'source_audit_failure': 104}
v6-baseline-r4     rep=4 h=1.5 rounds=2 stalls=2 cut-offs=1 vis=0.9213 hidden=0.9040 (95/104; valid 52/57, invalid 43/47) fuzz=1.0 [1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0] kinds={} build_ok=True audit_ok=True tokens in/out=199989/243185 active/idle=87.7/2.4 turns=193 tools=203 test_visible=1 loc=2301 fns=73 self-tests=0/915 traj=[0.8968, 0.904] fails={'unexpected_accept': 4, 'unexpected_reject': 4, 'assembly_or_link_failure': 1}
    cut off: 'cd /workspace && bash tools/difftest.sh 150 1 2>&1 | tail -12'
v6-tests-none-r4   rep=4 h=1.51 rounds=2 stalls=2 cut-offs=1 vis=0.8885 hidden=0.8972 (93/104; valid 49/57, invalid 44/47) fuzz=0.756 [1.0, 1.0, 0.74, 0.87, 0.75, 0.78, 0.84, 0.8, 0.32, 0.46] kinds={'assembly_or_link_failure': 86, 'wrong_behavior': 158} build_ok=True audit_ok=True tokens in/out=390174/268609 active/idle=88.4/1.9 turns=279 tools=286 test_visible=0 loc=2777 fns=71 self-tests=50/348 traj=[0.8188, 0.8972] fails={'wrong_behavior': 2, 'unexpected_accept': 3, 'unexpected_reject': 4, 'assembly_or_link_failure': 2}
    cut off: "cd /workspace/tests && chmod +x run.sh && mkdir -p out\ncat > t01_main.c <<'EOF'\nint main(void) {\n   "

--- Amendment 2 re-score: 7/8 runs reproduce their frozen values exactly; changed: v6-tests-none-r3 hidden 0.0->0.9109 fuzz 0.0->1.0

--- endpoint: hidden (PRIMARY: Amendment 2 re-score, audit scoped to src/)
  baseline     n=4 median=0.9408 mean=0.9401 range=[0.9040, 0.9748] sd=0.0299
  tests-none   n=4 median=0.9172 mean=0.9138 range=[0.8972, 0.9236] sd=0.0125
  replicate 1: tests-none - baseline = -0.0083
  replicate 2: tests-none - baseline = -0.0264
  replicate 3: tests-none - baseline = -0.0639
  replicate 4: tests-none - baseline = -0.0068
  paired median = -0.0173 (threshold 0.13); replicates below -0.13: 0/4, above +0.13: 0/4

--- endpoint: fuzz (PRIMARY: Amendment 2 re-score)
  baseline     n=4 median=1.0000 mean=1.0000 range=[1.0000, 1.0000] sd=0.0000
  tests-none   n=4 median=1.0000 mean=0.9390 range=[0.7560, 1.0000] sd=0.1220
  replicate 1: tests-none - baseline = +0.0000
  replicate 2: tests-none - baseline = +0.0000
  replicate 3: tests-none - baseline = +0.0000
  replicate 4: tests-none - baseline = -0.2440
  paired median = +0.0000 (threshold 0.13); replicates below -0.13: 1/4, above +0.13: 0/4

--- endpoint: hidden (frozen protocol)
  baseline     n=4 median=0.9408 mean=0.9401 range=[0.9040, 0.9748] sd=0.0299
  tests-none   n=4 median=0.9103 mean=0.6861 range=[0.0000, 0.9236] sd=0.4575
  replicate 1: tests-none - baseline = -0.0083
  replicate 2: tests-none - baseline = -0.0264
  replicate 3: tests-none - baseline = -0.9748
  replicate 4: tests-none - baseline = -0.0068
  paired median = -0.0173 (threshold 0.13); replicates below -0.13: 1/4, above +0.13: 0/4

--- endpoint: fuzz (frozen protocol)
  baseline     n=4 median=1.0000 mean=1.0000 range=[1.0000, 1.0000] sd=0.0000
  tests-none   n=4 median=0.8780 mean=0.6890 range=[0.0000, 1.0000] sd=0.4735
  replicate 1: tests-none - baseline = +0.0000
  replicate 2: tests-none - baseline = +0.0000
  replicate 3: tests-none - baseline = -1.0000
  replicate 4: tests-none - baseline = -0.2440
  paired median = -0.1220 (threshold 0.13); replicates below -0.13: 2/4, above +0.13: 0/4

--- harness check (Amendment 1: idle minutes and unanswered bash calls, not round-cap stalls)
  runs idling >= 5 min: 0/8 []
  runs with an unanswered bash call: 3/8; total 3
  runs with a cut-off: 3/8; total cut-offs 3
  rounds ended by the 45-min cap (normal for a working agent): 16 of 16
  runs with fuzz macro < 0.9 (fuzz_rescored): 1/8; corpus < 0.30 (hidden_rescored): 0/8

--- secondary endpoints (tests-none - baseline, paired by replicate; per-condition medians)
  output tokens        medians baseline=273147, tests-none=288484; paired deltas [39359, -8694, 3766, 25424] median +14595
  input tokens         medians baseline=291377, tests-none=293511; paired deltas [-271102, 44761, -65554, 190185] median -10396.5
  active minutes       medians baseline=88.8, tests-none=88.5; paired deltas [0.2, -0.9, -0.2, 0.7] median +0
  idle minutes         medians baseline=1.3, tests-none=1.7; paired deltas [-0.1, 0.9, 0.2, -0.5] median +0.05
  assistant turns      medians baseline=214, tests-none=288; paired deltas [-64, 110, 160, 86] median +98
  tool calls           medians baseline=251.5, tests-none=301; paired deltas [-75, 94, 127, 83] median +88.5
  test_visible calls   medians baseline=16.5, tests-none=0; paired deltas [-13, -20, -24, -1] median -16.5
  source LOC           medians baseline=2190.5, tests-none=2645.5; paired deltas [692, 636, -967, 476] median +556
  functions            medians baseline=73.5, tests-none=69.5; paired deltas [26, -6, -19, -2] median -4
  self-test programs   medians baseline=91, tests-none=117; paired deltas [-89, 168, -52, 50] median -1
  self-test LOC        medians baseline=968, tests-none=767; paired deltas [-779, 1179, 813, -567] median +123
  final build s        medians baseline=0.48, tests-none=0.52; paired deltas [0.1, -0.0, 0.1] median +0.08
  compile ms/test      medians baseline=7.31, tests-none=7.37; paired deltas [0.0, 0.1, 0.2] median +0.06
  compactions          medians baseline=7, tests-none=8; paired deltas [-1, 1, 0, 2] median +0.5
  cut-offs             medians baseline=0.5, tests-none=0; paired deltas [0, 0, -1, 0] median +0
  stalls               medians baseline=2, tests-none=2; paired deltas [0, 0, 0, 0] median +0

=== v5 for the harness check (same contrast, no default timeout; never pooled with v6)
=== v5 runs (8/8 complete)
v5-baseline-r1     rep=1 h=1.5 rounds=2 stalls=2 cut-offs=0 vis=0.9830 hidden=0.9667 (99/104; valid 55/57, invalid 44/47) fuzz=1.0 [1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0] kinds={} build_ok=True audit_ok=True tokens in/out=229203/304924 active/idle=89.7/0.4 turns=342 tools=351 test_visible=27 loc=2123 fns=64 self-tests=35/350 traj=[0.9403, 0.9667] fails={'unexpected_reject': 1, 'wrong_behavior': 1, 'unexpected_accept': 3}
v5-tests-none-r1   rep=1 h=1.5 rounds=2 stalls=2 cut-offs=0 vis=0.9251 hidden=0.9038 (94/104; valid 52/57, invalid 42/47) fuzz=0.912 [1.0, 1.0, 1.0, 0.8, 0.91, 0.93, 0.84, 0.93, 0.84, 0.87] kinds={'wrong_behavior': 88} build_ok=True audit_ok=True tokens in/out=159668/191141 active/idle=55.1/35.0 turns=141 tools=162 test_visible=0 loc=2413 fns=78 self-tests=0/254 traj=[0.8927, 0.9038] fails={'unexpected_accept': 5, 'execution_timeout': 1, 'unexpected_reject': 4}
v5-baseline-r2     rep=2 h=1.5 rounds=2 stalls=2 cut-offs=0 vis=0.9618 hidden=0.9556 (99/104; valid 55/57, invalid 44/47) fuzz=1.0 [1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0] kinds={} build_ok=True audit_ok=True tokens in/out=227064/303024 active/idle=90.0/0.1 turns=336 tools=347 test_visible=17 loc=3148 fns=87 self-tests=172/821 traj=[0.9139, 0.9556] fails={'unexpected_accept': 3, 'unexpected_reject': 1, 'wrong_behavior': 1}
v5-tests-none-r2   rep=2 h=1.5 rounds=2 stalls=2 cut-offs=0 vis=0.9445 hidden=0.9736 (101/104; valid 56/57, invalid 45/47) fuzz=1.0 [1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0] kinds={} build_ok=True audit_ok=True tokens in/out=178232/209410 active/idle=59.8/30.3 turns=158 tools=176 test_visible=0 loc=2413 fns=66 self-tests=107/756 traj=[0.9569, 0.9736] fails={'unexpected_accept': 2, 'unexpected_reject': 1}
v5-baseline-r3     rep=3 h=1.5 rounds=2 stalls=2 cut-offs=0 vis=0.7863 hidden=0.7222 (67/104; valid 24/57, invalid 43/47) fuzz=0.392 [1.0, 1.0, 1.0, 0.47, 0.24, 0.08, 0.07, 0.05, 0.01, 0.0] kinds={'assembly_or_link_failure': 607, 'wrong_behavior': 1} build_ok=True audit_ok=True tokens in/out=141318/165141 active/idle=45.3/44.8 turns=131 tools=138 test_visible=0 loc=2124 fns=68 self-tests=11/307 traj=[0.7222, 0.7222] fails={'assembly_or_link_failure': 25, 'unexpected_accept': 4, 'unexpected_reject': 8}
v5-tests-none-r3   rep=3 h=1.52 rounds=2 stalls=2 cut-offs=0 vis=0.5152 hidden=0.4764 (44/104; valid 0/57, invalid 44/47) fuzz=0.0 [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0] kinds={'wrong_behavior': 1000} build_ok=True audit_ok=True tokens in/out=116807/93848 active/idle=46.0/45.3 turns=72 tools=75 test_visible=0 loc=1929 fns=77 self-tests=61/429 traj=[0.4764, 0.4764] fails={'wrong_behavior': 53, 'unexpected_accept': 3, 'unexpected_reject': 4}
v5-baseline-r4     rep=4 h=1.53 rounds=2 stalls=2 cut-offs=0 vis=0.5898 hidden=0.5847 (57/104; valid 15/57, invalid 42/47) fuzz=0.019 [0.0, 0.19, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0] kinds={'assembly_or_link_failure': 200, 'timeout': 62, 'wrong_behavior': 719} build_ok=True audit_ok=True tokens in/out=39370/61032 active/idle=45.9/45.9 turns=32 tools=39 test_visible=0 loc=2118 fns=69 self-tests=0/0 traj=[0.5847, 0.5847] fails={'wrong_behavior': 26, 'unexpected_accept': 4, 'unexpected_reject': 12, 'compiler_crash': 1, 'assembly_or_link_failure': 4}
v5-tests-none-r4   rep=4 h=1.5 rounds=2 stalls=2 cut-offs=0 vis=0.9322 hidden=0.9181 (96/104; valid 53/57, invalid 43/47) fuzz=1.0 [1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0] kinds={} build_ok=True audit_ok=True tokens in/out=251385/299760 active/idle=89.5/0.6 turns=307 tools=315 test_visible=0 loc=2391 fns=57 self-tests=145/1261 traj=[0.8806, 0.9181] fails={'unexpected_accept': 4, 'unexpected_reject': 4}

--- endpoint: hidden (frozen protocol)
  baseline     n=4 median=0.8389 mean=0.8073 range=[0.5847, 0.9667] sd=0.1864
  tests-none   n=4 median=0.9110 mean=0.8180 range=[0.4764, 0.9736] sd=0.2297
  replicate 1: tests-none - baseline = -0.0629
  replicate 2: tests-none - baseline = +0.0180
  replicate 3: tests-none - baseline = -0.2458
  replicate 4: tests-none - baseline = +0.3334
  paired median = -0.0224 (threshold 0.13); replicates below -0.13: 1/4, above +0.13: 1/4

--- endpoint: fuzz (frozen protocol)
  baseline     n=4 median=0.6960 mean=0.6028 range=[0.0190, 1.0000] sd=0.4833
  tests-none   n=4 median=0.9560 mean=0.7280 range=[0.0000, 1.0000] sd=0.4871
  replicate 1: tests-none - baseline = -0.0880
  replicate 2: tests-none - baseline = +0.0000
  replicate 3: tests-none - baseline = -0.3920
  replicate 4: tests-none - baseline = +0.9810
  paired median = -0.0440 (threshold 0.13); replicates below -0.13: 1/4, above +0.13: 1/4

--- harness check (Amendment 1: idle minutes and unanswered bash calls, not round-cap stalls)
  runs idling >= 5 min: 5/8 [('v5-tests-none-r1', 35.0), ('v5-tests-none-r2', 30.3), ('v5-baseline-r3', 44.8), ('v5-tests-none-r3', 45.3), ('v5-baseline-r4', 45.9)]
  runs with an unanswered bash call: 5/8; total 7
  runs with a cut-off: 0/8; total cut-offs 0
  rounds ended by the 45-min cap (normal for a working agent): 16 of 16
  runs with fuzz macro < 0.9 (fuzz): 3/8; corpus < 0.30 (hidden): 0/8

--- secondary endpoints (tests-none - baseline, paired by replicate; per-condition medians)
  output tokens        medians baseline=234082, tests-none=200276; paired deltas [-113783, -93614, -71293, 238728] median -82453.5
  input tokens         medians baseline=184191, tests-none=168950; paired deltas [-69535, -48832, -24511, 212015] median -36671.5
  active minutes       medians baseline=67.8, tests-none=57.45; paired deltas [-34.6, -30.2, 0.7, 43.6] median -14.75
  idle minutes         medians baseline=22.6, tests-none=32.65; paired deltas [34.6, 30.2, 0.5, -45.3] median +15.35
  assistant turns      medians baseline=233.5, tests-none=149.5; paired deltas [-201, -178, -59, 275] median -118.5
  tool calls           medians baseline=242.5, tests-none=169; paired deltas [-189, -171, -63, 276] median -117
  test_visible calls   medians baseline=8.5, tests-none=0; paired deltas [-27, -17, 0, 0] median -8.5
  source LOC           medians baseline=2123.5, tests-none=2402; paired deltas [290, -735, -195, 273] median +39
  functions            medians baseline=68.5, tests-none=71.5; paired deltas [14, -21, 9, -12] median -1.5
  self-test programs   medians baseline=23, tests-none=84; paired deltas [-35, -65, 50, 145] median +7.5
  self-test LOC        medians baseline=328.5, tests-none=592.5; paired deltas [-96, -65, 122, 1261] median +28.5
  final build s        medians baseline=0.485, tests-none=0.44; paired deltas [-0.1, -0.1, 0.0, 0.0] median -0.015
  compile ms/test      medians baseline=7.33, tests-none=7.27; paired deltas [-0.1, -0.2, 0.1] median -0.12
  compactions          medians baseline=4, tests-none=4; paired deltas [-2, -2, 0, 6] median -1
  cut-offs             medians baseline=0, tests-none=0; paired deltas [0, 0, 0, 0] median +0
  stalls               medians baseline=2, tests-none=2; paired deltas [0, 0, 0, 0] median +0

```
