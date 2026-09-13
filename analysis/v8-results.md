# v8 results digest

```
=== v8 runs (8/8 complete)
v8-baseline-r1       rep=1 h=1.5 rounds=2 cut-offs=0 vis=0.9718 hidden=0.9736 lb=0.9736@r1 (101/104; valid 56/57, invalid 45/47) fuzz=1.0 lb=1.0 [1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0] kinds={} build_ok=True audit_ok=True tokens in/out=327721/278641 active/idle=89.9/0.2 turns=260 tools=263 test_visible=15 pushed=0 [] loc=2573 fns=75 self-tests=0/0 traj=[0.9194, 0.9736] fails={'unexpected_accept': 2, 'unexpected_reject': 1}
v8-tests-pushed-r1   rep=1 h=1.5 rounds=2 cut-offs=0 vis=0.9875 hidden=0.9403 lb=0.9403@r1 (97/104; valid 55/57, invalid 42/47) fuzz=0.996 lb=0.996 [1.0, 1.0, 1.0, 0.99, 0.99, 1.0, 1.0, 0.99, 0.99, 1.0] kinds={'wrong_behavior': 4} build_ok=True audit_ok=True tokens in/out=278159/282709 active/idle=89.3/0.7 turns=283 tools=290 test_visible=8 pushed=8 [0.0, 0.766, 0.857, 0.0, 0.924, 0.962, 0.971, 0.988] loc=2240 fns=50 self-tests=0/79 traj=[0.0, 0.9403] fails={'unexpected_accept': 5, 'unexpected_reject': 1, 'assembly_or_link_failure': 1}
v8-baseline-r2       rep=2 h=1.5 rounds=2 cut-offs=0 vis=0.9643 hidden=0.9611 lb=0.9611@r1 (100/104; valid 56/57, invalid 44/47) fuzz=1.0 lb=1.0 [1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0] kinds={} build_ok=True audit_ok=True tokens in/out=287647/292619 active/idle=89.5/0.6 turns=267 tools=289 test_visible=11 pushed=0 [] loc=2657 fns=78 self-tests=0/0 traj=[0.9292, 0.9611] fails={'unexpected_accept': 3, 'unexpected_reject': 1}
v8-tests-pushed-r2   rep=2 h=1.5 rounds=2 cut-offs=1 vis=0.9593 hidden=0.9444 lb=0.9444@r1 (97/104; valid 56/57, invalid 41/47) fuzz=1.0 lb=1.0 [1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0] kinds={} build_ok=True audit_ok=True tokens in/out=315811/267541 active/idle=89.5/0.6 turns=298 tools=314 test_visible=13 pushed=8 [0.0, 0.493, 0.657, 0.921, 0.926, 0.959, 0.962, 0.0] loc=2616 fns=60 self-tests=179/1055 traj=[0.9125, 0.9444] fails={'unexpected_accept': 6, 'unexpected_reject': 1}
v8-baseline-r3       rep=3 h=1.5 rounds=2 cut-offs=0 vis=0.9475 hidden=0.9389 lb=0.9389@r1 (98/104; valid 54/57, invalid 44/47) fuzz=1.0 lb=1.0 [1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0] kinds={} build_ok=True audit_ok=True tokens in/out=250714/295945 active/idle=90.0/0.1 turns=273 tools=283 test_visible=23 pushed=0 [] loc=2165 fns=62 self-tests=0/267 traj=[0.9236, 0.9389] fails={'unexpected_accept': 3, 'unexpected_reject': 3}
v8-tests-pushed-r3   rep=3 h=1.5 rounds=2 cut-offs=0 vis=0.9755 hidden=0.9512 lb=0.9512@r1 (96/104; valid 55/57, invalid 41/47) fuzz=1.0 lb=1.0 [1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0] kinds={} build_ok=True audit_ok=True tokens in/out=262143/295139 active/idle=89.5/0.6 turns=301 tools=313 test_visible=13 pushed=8 [0.0, 0.646, 0.0, 0.945, 0.971, 0.971, 0.971, 0.976] loc=2454 fns=66 self-tests=173/758 traj=[0.9734, 0.9512] fails={'wrong_behavior': 1, 'unexpected_accept': 6, 'unexpected_reject': 1}
v8-baseline-r4       rep=4 h=1.5 rounds=2 cut-offs=0 vis=0.9518 hidden=0.9500 lb=0.9500@r1 (98/104; valid 55/57, invalid 43/47) fuzz=1.0 lb=1.0 [1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0] kinds={} build_ok=True audit_ok=True tokens in/out=278498/301838 active/idle=89.8/0.3 turns=297 tools=305 test_visible=17 pushed=0 [] loc=2282 fns=69 self-tests=227/1072 traj=[0.8675, 0.95] fails={'unexpected_accept': 4, 'unexpected_reject': 2}
v8-tests-pushed-r4   rep=4 h=1.5 rounds=2 cut-offs=1 vis=0.0000 hidden=0.0000 lb=0.8942@r0 (0/104; valid 0/57, invalid 0/47) fuzz=0.0 lb=0.932 [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0] kinds={} build_ok=False audit_ok=True tokens in/out=268120/276086 active/idle=89.4/0.7 turns=195 tools=207 test_visible=5 pushed=8 [0.0, 0.879, 0.914, 0.932, 0.93, 0.951, 0.977, 0.977] loc=2488 fns=63 self-tests=41/2064 traj=[0.8942, 0.0] fails={'build_failure': 104}

--- endpoint: corpus, last buildable snapshot (PRIMARY)
  baseline     n=4 median=0.9555 mean=0.9559 range=[0.9389, 0.9736] sd=0.0149
  tests-pushed n=4 median=0.9424 mean=0.9325 range=[0.8942, 0.9512] sd=0.0259
  replicate 1: tests-pushed - baseline = -0.0333
  replicate 2: tests-pushed - baseline = -0.0167
  replicate 3: tests-pushed - baseline = +0.0123
  replicate 4: tests-pushed - baseline = -0.0558
  paired median = -0.0250 (threshold 0.13); replicates below -0.13: 0/4, above +0.13: 0/4

--- endpoint: fuzz, last buildable snapshot (PRIMARY)
  baseline     n=4 median=1.0000 mean=1.0000 range=[1.0000, 1.0000] sd=0.0000
  tests-pushed n=4 median=0.9980 mean=0.9820 range=[0.9320, 1.0000] sd=0.0334
  replicate 1: tests-pushed - baseline = -0.0040
  replicate 2: tests-pushed - baseline = +0.0000
  replicate 3: tests-pushed - baseline = +0.0000
  replicate 4: tests-pushed - baseline = -0.0680
  paired median = -0.0020 (threshold 0.13); replicates below -0.13: 0/4, above +0.13: 0/4

--- endpoint: corpus, final snapshot
  baseline     n=4 median=0.9555 mean=0.9559 range=[0.9389, 0.9736] sd=0.0149
  tests-pushed n=4 median=0.9424 mean=0.7090 range=[0.0000, 0.9512] sd=0.4727
  replicate 1: tests-pushed - baseline = -0.0333
  replicate 2: tests-pushed - baseline = -0.0167
  replicate 3: tests-pushed - baseline = +0.0123
  replicate 4: tests-pushed - baseline = -0.9500
  paired median = -0.0250 (threshold 0.13); replicates below -0.13: 1/4, above +0.13: 0/4

--- endpoint: fuzz, final snapshot
  baseline     n=4 median=1.0000 mean=1.0000 range=[1.0000, 1.0000] sd=0.0000
  tests-pushed n=4 median=0.9980 mean=0.7490 range=[0.0000, 1.0000] sd=0.4993
  replicate 1: tests-pushed - baseline = -0.0040
  replicate 2: tests-pushed - baseline = +0.0000
  replicate 3: tests-pushed - baseline = +0.0000
  replicate 4: tests-pushed - baseline = -1.0000
  paired median = -0.0020 (threshold 0.13); replicates below -0.13: 1/4, above +0.13: 0/4

--- harness check (idle minutes, unanswered bash calls, cut-offs, cap-cut finals)
  runs idling >= 5 min: 0/8 []
  runs with an unanswered bash call: 1/8
  runs with a cut-off: 2/8; total cut-offs 2
  finals that did not build (last buildable differs): 1/8
  runs with fuzz macro < 0.9 (last buildable): 0/8; corpus < 0.30: 0/8

--- secondary endpoints (tests-pushed - baseline, paired by replicate; per-condition medians)
  output tokens        medians baseline=294282, tests-pushed=279398; paired deltas [4068, -25078, -806, -25752] median -12942
  input tokens         medians baseline=283072, tests-pushed=273140; paired deltas [-49562, 28164, 11429, -10378] median +525.5
  active minutes       medians baseline=89.85, tests-pushed=89.45; paired deltas [-0.6, 0.0, -0.5, -0.4] median -0.45
  idle minutes         medians baseline=0.25, tests-pushed=0.65; paired deltas [0.5, 0.0, 0.5, 0.4] median +0.45
  assistant turns      medians baseline=270, tests-pushed=290.5; paired deltas [23, 31, 28, -102] median +25.5
  tool calls           medians baseline=286, tests-pushed=301.5; paired deltas [27, 25, 30, -98] median +26
  test_visible calls   medians baseline=16, tests-pushed=10.5; paired deltas [-7, 2, -10, -12] median -8.5
  pushed reports       medians baseline=0, tests-pushed=8; paired deltas [8, 8, 8, 8] median +8
  source LOC           medians baseline=2427.5, tests-pushed=2471; paired deltas [-333, -41, 289, 206] median +82.5
  functions            medians baseline=72, tests-pushed=61.5; paired deltas [-25, -18, 4, -6] median -12
  self-test programs   medians baseline=0, tests-pushed=107; paired deltas [0, 179, 173, -186] median +86.5
  self-test LOC        medians baseline=133.5, tests-pushed=906.5; paired deltas [79, 1055, 491, 992] median +741.5
  final build s        medians baseline=0.485, tests-pushed=0.49; paired deltas [0.0, 0.2, -0.1, -0.4] median -0.05
  compile ms/test      medians baseline=7.38, tests-pushed=7.41; paired deltas [0.0, 0.0, 0.1] median +0.05
  compactions          medians baseline=9, tests-pushed=8.5; paired deltas [2, -2, 0, -1] median -0.5
  cut-offs             medians baseline=0, tests-pushed=0.5; paired deltas [0, 1, 0, 1] median +0.5
  stalls               medians baseline=2, tests-pushed=2; paired deltas [0, 0, 0, 0] median +0

=== v6 for the gradient (baseline vs tests-none on the same image; last-buildable fuzz absent in pre-v8 ledgers; never pooled)
=== v6 runs (8/8 complete)
v6-baseline-r1       rep=1 h=1.5 rounds=2 cut-offs=0 vis=0.9830 hidden=0.9317 lb=0.9317@r1 (95/104; valid 55/57, invalid 40/47) fuzz=1.0 lb=1.0 [1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0] kinds={} build_ok=True audit_ok=True tokens in/out=561229/260210 active/idle=89.6/0.4 turns=308 tools=321 test_visible=13 pushed=0 [] loc=1883 fns=55 self-tests=181/1028 traj=[0.0, 0.9317] fails={'unexpected_accept': 7, 'unexpected_reject': 2}
v6-tests-none-r1     rep=1 h=1.5 rounds=2 cut-offs=0 vis=0.8997 hidden=0.9234 lb=0.9234@r1 (96/104; valid 52/57, invalid 44/47) fuzz=1.0 lb=1.0 [1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0] kinds={} build_ok=True audit_ok=True tokens in/out=290127/299569 active/idle=89.8/0.3 turns=244 tools=246 test_visible=0 pushed=0 [] loc=2575 fns=81 self-tests=92/249 traj=[0.0, 0.9234] fails={'unexpected_accept': 3, 'wrong_behavior': 1, 'unexpected_reject': 4}
v6-baseline-r2       rep=2 h=1.5 rounds=2 cut-offs=0 vis=0.9430 hidden=0.9500 lb=0.9500@r1 (98/104; valid 55/57, invalid 43/47) fuzz=1.0 lb=1.0 [1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0] kinds={} build_ok=True audit_ok=True tokens in/out=220305/295812 active/idle=88.8/1.3 turns=187 tools=222 test_visible=20 pushed=0 [] loc=2080 fns=74 self-tests=1/7 traj=[0.9431, 0.95] fails={'unexpected_accept': 4, 'unexpected_reject': 1, 'assembly_or_link_failure': 1}
v6-tests-none-r2     rep=2 h=1.5 rounds=2 cut-offs=0 vis=0.9299 hidden=0.9236 lb=0.9236@r1 (97/104; valid 53/57, invalid 44/47) fuzz=1.0 lb=1.0 [1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0] kinds={} build_ok=True audit_ok=True tokens in/out=265066/287118 active/idle=87.9/2.2 turns=297 tools=316 test_visible=0 pushed=0 [] loc=2716 fns=68 self-tests=169/1186 traj=[0.8986, 0.9236] fails={'unexpected_accept': 3, 'unexpected_reject': 4}
v6-baseline-r3       rep=3 h=1.5 rounds=2 cut-offs=1 vis=0.9914 hidden=0.9748 lb=0.9748@r1 (101/104; valid 56/57, invalid 45/47) fuzz=1.0 lb=1.0 [1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0] kinds={} build_ok=True audit_ok=True tokens in/out=362449/286084 active/idle=88.8/1.3 turns=235 tools=281 test_visible=24 pushed=0 [] loc=2788 fns=74 self-tests=194/1021 traj=[0.9345, 0.9748] fails={'unexpected_accept': 2, 'execution_timeout': 1}
v6-tests-none-r3     rep=3 h=1.5 rounds=2 cut-offs=0 vis=0.0000 hidden=0.0000 lb=0.6935@r0 (0/104; valid 0/57, invalid 0/47) fuzz=0.0 lb=None [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0] kinds={} build_ok=False audit_ok=False tokens in/out=296895/289850 active/idle=88.6/1.5 turns=395 tools=408 test_visible=0 pushed=0 [] loc=1821 fns=55 self-tests=142/1834 traj=[0.6935, 0.0] fails={'source_audit_failure': 104}
v6-baseline-r4       rep=4 h=1.5 rounds=2 cut-offs=1 vis=0.9213 hidden=0.9040 lb=0.9040@r1 (95/104; valid 52/57, invalid 43/47) fuzz=1.0 lb=1.0 [1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0] kinds={} build_ok=True audit_ok=True tokens in/out=199989/243185 active/idle=87.7/2.4 turns=193 tools=203 test_visible=1 pushed=0 [] loc=2301 fns=73 self-tests=0/915 traj=[0.8968, 0.904] fails={'unexpected_accept': 4, 'unexpected_reject': 4, 'assembly_or_link_failure': 1}
v6-tests-none-r4     rep=4 h=1.51 rounds=2 cut-offs=1 vis=0.8885 hidden=0.8972 lb=0.8972@r1 (93/104; valid 49/57, invalid 44/47) fuzz=0.756 lb=0.756 [1.0, 1.0, 0.74, 0.87, 0.75, 0.78, 0.84, 0.8, 0.32, 0.46] kinds={'assembly_or_link_failure': 86, 'wrong_behavior': 158} build_ok=True audit_ok=True tokens in/out=390174/268609 active/idle=88.4/1.9 turns=279 tools=286 test_visible=0 pushed=0 [] loc=2777 fns=71 self-tests=50/348 traj=[0.8188, 0.8972] fails={'wrong_behavior': 2, 'unexpected_accept': 3, 'unexpected_reject': 4, 'assembly_or_link_failure': 2}

--- endpoint: corpus, last buildable snapshot (PRIMARY)
  baseline     n=4 median=0.9408 mean=0.9401 range=[0.9040, 0.9748] sd=0.0299
  tests-none   n=4 median=0.9103 mean=0.8594 range=[0.6935, 0.9236] sd=0.1113
  replicate 1: tests-none - baseline = -0.0083
  replicate 2: tests-none - baseline = -0.0264
  replicate 3: tests-none - baseline = -0.2813
  replicate 4: tests-none - baseline = -0.0068
  paired median = -0.0173 (threshold 0.13); replicates below -0.13: 1/4, above +0.13: 0/4

--- endpoint: fuzz, last buildable snapshot (PRIMARY)
  baseline     n=4 median=1.0000 mean=1.0000 range=[1.0000, 1.0000] sd=0.0000
  tests-none   n=3 median=1.0000 mean=0.9187 range=[0.7560, 1.0000] sd=0.1409
  replicate 1: tests-none - baseline = +0.0000
  replicate 2: tests-none - baseline = +0.0000
  replicate 4: tests-none - baseline = -0.2440
  paired median = +0.0000 (threshold 0.13); replicates below -0.13: 1/3, above +0.13: 0/3

--- endpoint: corpus, final snapshot
  baseline     n=4 median=0.9408 mean=0.9401 range=[0.9040, 0.9748] sd=0.0299
  tests-none   n=4 median=0.9103 mean=0.6861 range=[0.0000, 0.9236] sd=0.4575
  replicate 1: tests-none - baseline = -0.0083
  replicate 2: tests-none - baseline = -0.0264
  replicate 3: tests-none - baseline = -0.9748
  replicate 4: tests-none - baseline = -0.0068
  paired median = -0.0173 (threshold 0.13); replicates below -0.13: 1/4, above +0.13: 0/4

--- endpoint: fuzz, final snapshot
  baseline     n=4 median=1.0000 mean=1.0000 range=[1.0000, 1.0000] sd=0.0000
  tests-none   n=4 median=0.8780 mean=0.6890 range=[0.0000, 1.0000] sd=0.4735
  replicate 1: tests-none - baseline = +0.0000
  replicate 2: tests-none - baseline = +0.0000
  replicate 3: tests-none - baseline = -1.0000
  replicate 4: tests-none - baseline = -0.2440
  paired median = -0.1220 (threshold 0.13); replicates below -0.13: 2/4, above +0.13: 0/4

--- harness check (idle minutes, unanswered bash calls, cut-offs, cap-cut finals)
  runs idling >= 5 min: 0/8 []
  runs with an unanswered bash call: 3/8
  runs with a cut-off: 3/8; total cut-offs 3
  finals that did not build (last buildable differs): 1/8
  runs with fuzz macro < 0.9 (last buildable): 1/7; corpus < 0.30: 0/8

--- secondary endpoints (tests-none - baseline, paired by replicate; per-condition medians)
  output tokens        medians baseline=273147, tests-none=288484; paired deltas [39359, -8694, 3766, 25424] median +14595
  input tokens         medians baseline=291377, tests-none=293511; paired deltas [-271102, 44761, -65554, 190185] median -10396.5
  active minutes       medians baseline=88.8, tests-none=88.5; paired deltas [0.2, -0.9, -0.2, 0.7] median +0
  idle minutes         medians baseline=1.3, tests-none=1.7; paired deltas [-0.1, 0.9, 0.2, -0.5] median +0.05
  assistant turns      medians baseline=214, tests-none=288; paired deltas [-64, 110, 160, 86] median +98
  tool calls           medians baseline=251.5, tests-none=301; paired deltas [-75, 94, 127, 83] median +88.5
  test_visible calls   medians baseline=16.5, tests-none=0; paired deltas [-13, -20, -24, -1] median -16.5
  pushed reports       medians baseline=0, tests-none=0; paired deltas [0, 0, 0, 0] median +0
  source LOC           medians baseline=2190.5, tests-none=2645.5; paired deltas [692, 636, -967, 476] median +556
  functions            medians baseline=73.5, tests-none=69.5; paired deltas [26, -6, -19, -2] median -4
  self-test programs   medians baseline=91, tests-none=117; paired deltas [-89, 168, -52, 50] median -1
  self-test LOC        medians baseline=968, tests-none=767; paired deltas [-779, 1179, 813, -567] median +123
  final build s        medians baseline=0.48, tests-none=0.52; paired deltas [0.1, -0.0, 0.1] median +0.08
  compile ms/test      medians baseline=7.31, tests-none=7.37; paired deltas [0.0, 0.1, 0.2] median +0.06
  compactions          medians baseline=7, tests-none=8; paired deltas [-1, 1, 0, 2] median +0.5
  cut-offs             medians baseline=0.5, tests-none=0; paired deltas [0, 0, -1, 0] median +0
  stalls               medians baseline=2, tests-none=2; paired deltas [0, 0, 0, 0] median +0

```
