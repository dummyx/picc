# v9 results digest

```
=== v9 runs (12/12 complete)
v9-baseline-r1       rep=1 h=1.5 rounds=2 cut-offs=0 vis=0.9518 hidden=0.9736 lb=0.9736@r1 (101/104; valid 56/57, invalid 45/47) fuzz=1.0 lb=1.0 [1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0] kinds={} build_ok=True audit_ok=True tokens in/out=334410/281673 active/idle=88.4/1.7 turns=292 tools=303 test_visible=18 pushed=0 [] loc=2012 fns=61 self-tests=72/930 traj=[0.9361, 0.9736] fails={'unexpected_accept': 2, 'unexpected_reject': 1}
v9-spec-minimal-r1   rep=1 h=1.51 rounds=2 cut-offs=0 vis=0.0000 hidden=0.0000 lb=0.7835@r0 (0/104; valid 0/57, invalid 0/47) fuzz=0.0 lb=0.727 [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0] kinds={} build_ok=False audit_ok=False tokens in/out=262237/291491 active/idle=90.5/0.2 turns=334 tools=341 test_visible=5 pushed=0 [] loc=2964 fns=90 self-tests=0/0 traj=[0.7835, 0.0] fails={'build_failure': 104}
v9-tests-none-r1     rep=1 h=1.5 rounds=2 cut-offs=1 vis=0.0000 hidden=0.8692 lb=0.8692@r1 (90/104; valid 47/57, invalid 43/47) fuzz=0.8 lb=0.8 [1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 0.0, 0.0] kinds={'assembly_or_link_failure': 200} build_ok=True audit_ok=True tokens in/out=264121/302220 active/idle=89.9/0.1 turns=258 tools=283 test_visible=1 pushed=0 [] loc=2016 fns=54 self-tests=0/0 traj=[0.8637, 0.8692] fails={'unexpected_accept': 4, 'execution_timeout': 1, 'assembly_or_link_failure': 5, 'unexpected_reject': 4}
v9-spec-minimal-tests-none-r1 rep=1 h=1.5 rounds=2 cut-offs=0 vis=0.9118 hidden=0.9149 lb=0.9149@r1 (94/104; valid 53/57, invalid 41/47) fuzz=1.0 lb=1.0 [1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0] kinds={} build_ok=True audit_ok=True tokens in/out=272748/272731 active/idle=84.4/5.7 turns=241 tools=277 test_visible=0 pushed=0 [] loc=3545 fns=125 self-tests=34/1729 traj=[0.8579, 0.9149] fails={'unexpected_accept': 6, 'unexpected_reject': 4}
v9-baseline-r2       rep=2 h=1.5 rounds=2 cut-offs=1 vis=0.9657 hidden=0.9554 lb=0.9554@r1 (98/104; valid 55/57, invalid 43/47) fuzz=0.996 lb=0.996 [1.0, 1.0, 1.0, 1.0, 0.98, 1.0, 0.99, 0.99, 1.0, 1.0] kinds={'wrong_behavior': 4} build_ok=True audit_ok=True tokens in/out=245017/290427 active/idle=89.2/0.9 turns=291 tools=293 test_visible=14 pushed=0 [] loc=2159 fns=63 self-tests=1/3 traj=[0.904, 0.9554] fails={'unexpected_accept': 4, 'execution_timeout': 1, 'unexpected_reject': 1}
v9-spec-minimal-r2   rep=2 h=1.51 rounds=2 cut-offs=1 vis=0.9271 hidden=0.9458 lb=0.9458@r1 (96/104; valid 55/57, invalid 41/47) fuzz=1.0 lb=1.0 [1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0] kinds={} build_ok=True audit_ok=True tokens in/out=259485/287647 active/idle=90.3/0.2 turns=302 tools=312 test_visible=19 pushed=0 [] loc=4351 fns=108 self-tests=0/0 traj=[0.7393, 0.9458] fails={'unexpected_accept': 6, 'unexpected_reject': 2}
v9-tests-none-r2     rep=2 h=1.5 rounds=2 cut-offs=1 vis=0.9181 hidden=0.9236 lb=0.9236@r1 (97/104; valid 53/57, invalid 44/47) fuzz=1.0 lb=1.0 [1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0] kinds={} build_ok=True audit_ok=True tokens in/out=248455/278866 active/idle=88.3/1.8 turns=336 tools=344 test_visible=0 pushed=0 [] loc=2346 fns=67 self-tests=137/1303 traj=[0.9236, 0.9236] fails={'unexpected_accept': 3, 'unexpected_reject': 4}
v9-spec-minimal-tests-none-r2 rep=2 h=1.5 rounds=2 cut-offs=1 vis=0.8924 hidden=0.8790 lb=0.8790@r1 (89/104; valid 49/57, invalid 40/47) fuzz=0.996 lb=0.996 [1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 0.98, 0.98] kinds={'wrong_behavior': 4} build_ok=True audit_ok=True tokens in/out=334020/281594 active/idle=89.2/0.9 turns=210 tools=222 test_visible=0 pushed=0 [] loc=4268 fns=124 self-tests=12/306 traj=[0.0, 0.879] fails={'unexpected_accept': 7, 'unexpected_reject': 2, 'execution_timeout': 1, 'wrong_behavior': 2, 'compiler_crash': 3}
v9-baseline-r3       rep=3 h=1.5 rounds=2 cut-offs=0 vis=0.9976 hidden=0.9708 lb=0.9708@r1 (100/104; valid 57/57, invalid 43/47) fuzz=1.0 lb=1.0 [1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0] kinds={} build_ok=True audit_ok=True tokens in/out=205088/304222 active/idle=89.0/1.1 turns=199 tools=217 test_visible=25 pushed=0 [] loc=2159 fns=56 self-tests=10/55 traj=[0.9653, 0.9708] fails={'unexpected_accept': 4}
v9-spec-minimal-r3   rep=3 h=1.5 rounds=2 cut-offs=0 vis=0.9257 hidden=0.9012 lb=0.9012@r1 (92/104; valid 53/57, invalid 39/47) fuzz=0.98 lb=0.98 [1.0, 1.0, 1.0, 0.98, 0.99, 0.98, 1.0, 0.98, 0.93, 0.94] kinds={'rejected_valid_program': 15, 'wrong_behavior': 5} build_ok=True audit_ok=True tokens in/out=275069/290202 active/idle=88.9/1.3 turns=338 tools=376 test_visible=19 pushed=0 [] loc=3529 fns=139 self-tests=0/0 traj=[0.7532, 0.9012] fails={'unexpected_accept': 8, 'unexpected_reject': 4}
v9-tests-none-r3     rep=3 h=1.5 rounds=2 cut-offs=0 vis=0.6982 hidden=0.6823 lb=0.6823@r1 (65/104; valid 22/57, invalid 43/47) fuzz=0.2 lb=0.2 [1.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0] kinds={'assembly_or_link_failure': 800} build_ok=True audit_ok=True tokens in/out=381392/280442 active/idle=88.8/1.3 turns=276 tools=280 test_visible=0 pushed=0 [] loc=2100 fns=78 self-tests=0/1455 traj=[0.4639, 0.6823] fails={'assembly_or_link_failure': 31, 'unexpected_accept': 4, 'unexpected_reject': 4}
v9-spec-minimal-tests-none-r3 rep=3 h=1.5 rounds=2 cut-offs=0 vis=0.8814 hidden=0.8246 lb=0.8246@r1 (86/104; valid 50/57, invalid 36/47) fuzz=0.996 lb=0.996 [1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 0.97, 0.99] kinds={'wrong_behavior': 4} build_ok=True audit_ok=False tokens in/out=222447/301021 active/idle=89.6/0.5 turns=190 tools=195 test_visible=0 pushed=0 [] loc=3918 fns=108 self-tests=13/162 traj=[0.0, 0.8246] fails={'unexpected_accept': 11, 'wrong_behavior': 5, 'unexpected_reject': 1, 'assembly_or_link_failure': 1}

--- endpoint: corpus, last buildable snapshot (PRIMARY)
  baseline     n=3 median=0.9708 mean=0.9666 range=[0.9554, 0.9736] sd=0.0098
  spec-minimal n=3 median=0.9012 mean=0.8768 range=[0.7835, 0.9458] sd=0.0838
  spec-minimal-tests-none n=3 median=0.8790 mean=0.8728 range=[0.8246, 0.9149] sd=0.0455
  tests-none   n=3 median=0.8692 mean=0.8250 range=[0.6823, 0.9236] sd=0.1266
  [spec-minimal - baseline (spec effect, tests on demand)]
  replicate 1: spec-minimal - baseline = -0.1901
  replicate 2: spec-minimal - baseline = -0.0096
  replicate 3: spec-minimal - baseline = -0.0696
  paired median = -0.0696 (threshold 0.13); replicates below -0.13: 1/3, above +0.13: 0/3
  [spec-minimal-tests-none - tests-none (spec effect, no tests)]
  replicate 1: spec-minimal-tests-none - tests-none = +0.0457
  replicate 2: spec-minimal-tests-none - tests-none = -0.0446
  replicate 3: spec-minimal-tests-none - tests-none = +0.1423
  paired median = +0.0457 (threshold 0.13); replicates below -0.13: 0/3, above +0.13: 1/3
  [tests-none - baseline (tests effect, full spec)]
  replicate 1: tests-none - baseline = -0.1044
  replicate 2: tests-none - baseline = -0.0318
  replicate 3: tests-none - baseline = -0.2885
  paired median = -0.1044 (threshold 0.13); replicates below -0.13: 1/3, above +0.13: 0/3
  [spec-minimal-tests-none - spec-minimal (tests effect, minimal spec)]
  replicate 1: spec-minimal-tests-none - spec-minimal = +0.1314
  replicate 2: spec-minimal-tests-none - spec-minimal = -0.0668
  replicate 3: spec-minimal-tests-none - spec-minimal = -0.0766
  paired median = -0.0668 (threshold 0.13); replicates below -0.13: 0/3, above +0.13: 1/3
  [spec-minimal-tests-none - baseline (both factors)]
  replicate 1: spec-minimal-tests-none - baseline = -0.0587
  replicate 2: spec-minimal-tests-none - baseline = -0.0764
  replicate 3: spec-minimal-tests-none - baseline = -0.1462
  paired median = -0.0764 (threshold 0.13); replicates below -0.13: 1/3, above +0.13: 0/3
  [interaction: (both - tests-none) - (spec-minimal - baseline)]
  replicate 1: interaction = +0.2358
  replicate 2: interaction = -0.0350
  replicate 3: interaction = +0.2119
  paired median = +0.2119

--- endpoint: fuzz, last buildable snapshot (PRIMARY)
  baseline     n=3 median=1.0000 mean=0.9987 range=[0.9960, 1.0000] sd=0.0023
  spec-minimal n=3 median=0.9800 mean=0.9023 range=[0.7270, 1.0000] sd=0.1522
  spec-minimal-tests-none n=3 median=0.9960 mean=0.9973 range=[0.9960, 1.0000] sd=0.0023
  tests-none   n=3 median=0.8000 mean=0.6667 range=[0.2000, 1.0000] sd=0.4163
  [spec-minimal - baseline (spec effect, tests on demand)]
  replicate 1: spec-minimal - baseline = -0.2730
  replicate 2: spec-minimal - baseline = +0.0040
  replicate 3: spec-minimal - baseline = -0.0200
  paired median = -0.0200 (threshold 0.13); replicates below -0.13: 1/3, above +0.13: 0/3
  [spec-minimal-tests-none - tests-none (spec effect, no tests)]
  replicate 1: spec-minimal-tests-none - tests-none = +0.2000
  replicate 2: spec-minimal-tests-none - tests-none = -0.0040
  replicate 3: spec-minimal-tests-none - tests-none = +0.7960
  paired median = +0.2000 (threshold 0.13); replicates below -0.13: 0/3, above +0.13: 2/3
  [tests-none - baseline (tests effect, full spec)]
  replicate 1: tests-none - baseline = -0.2000
  replicate 2: tests-none - baseline = +0.0040
  replicate 3: tests-none - baseline = -0.8000
  paired median = -0.2000 (threshold 0.13); replicates below -0.13: 2/3, above +0.13: 0/3
  [spec-minimal-tests-none - spec-minimal (tests effect, minimal spec)]
  replicate 1: spec-minimal-tests-none - spec-minimal = +0.2730
  replicate 2: spec-minimal-tests-none - spec-minimal = -0.0040
  replicate 3: spec-minimal-tests-none - spec-minimal = +0.0160
  paired median = +0.0160 (threshold 0.13); replicates below -0.13: 0/3, above +0.13: 1/3
  [spec-minimal-tests-none - baseline (both factors)]
  replicate 1: spec-minimal-tests-none - baseline = +0.0000
  replicate 2: spec-minimal-tests-none - baseline = +0.0000
  replicate 3: spec-minimal-tests-none - baseline = -0.0040
  paired median = +0.0000 (threshold 0.13); replicates below -0.13: 0/3, above +0.13: 0/3
  [interaction: (both - tests-none) - (spec-minimal - baseline)]
  replicate 1: interaction = +0.4730
  replicate 2: interaction = -0.0080
  replicate 3: interaction = +0.8160
  paired median = +0.4730

--- endpoint: corpus, final snapshot
  baseline     n=3 median=0.9708 mean=0.9666 range=[0.9554, 0.9736] sd=0.0098
  spec-minimal n=3 median=0.9012 mean=0.6157 range=[0.0000, 0.9458] sd=0.5336
  spec-minimal-tests-none n=3 median=0.8790 mean=0.8728 range=[0.8246, 0.9149] sd=0.0455
  tests-none   n=3 median=0.8692 mean=0.8250 range=[0.6823, 0.9236] sd=0.1266
  [spec-minimal - baseline (spec effect, tests on demand)]
  replicate 1: spec-minimal - baseline = -0.9736
  replicate 2: spec-minimal - baseline = -0.0096
  replicate 3: spec-minimal - baseline = -0.0696
  paired median = -0.0696 (threshold 0.13); replicates below -0.13: 1/3, above +0.13: 0/3
  [spec-minimal-tests-none - tests-none (spec effect, no tests)]
  replicate 1: spec-minimal-tests-none - tests-none = +0.0457
  replicate 2: spec-minimal-tests-none - tests-none = -0.0446
  replicate 3: spec-minimal-tests-none - tests-none = +0.1423
  paired median = +0.0457 (threshold 0.13); replicates below -0.13: 0/3, above +0.13: 1/3
  [tests-none - baseline (tests effect, full spec)]
  replicate 1: tests-none - baseline = -0.1044
  replicate 2: tests-none - baseline = -0.0318
  replicate 3: tests-none - baseline = -0.2885
  paired median = -0.1044 (threshold 0.13); replicates below -0.13: 1/3, above +0.13: 0/3
  [spec-minimal-tests-none - spec-minimal (tests effect, minimal spec)]
  replicate 1: spec-minimal-tests-none - spec-minimal = +0.9149
  replicate 2: spec-minimal-tests-none - spec-minimal = -0.0668
  replicate 3: spec-minimal-tests-none - spec-minimal = -0.0766
  paired median = -0.0668 (threshold 0.13); replicates below -0.13: 0/3, above +0.13: 1/3
  [spec-minimal-tests-none - baseline (both factors)]
  replicate 1: spec-minimal-tests-none - baseline = -0.0587
  replicate 2: spec-minimal-tests-none - baseline = -0.0764
  replicate 3: spec-minimal-tests-none - baseline = -0.1462
  paired median = -0.0764 (threshold 0.13); replicates below -0.13: 1/3, above +0.13: 0/3
  [interaction: (both - tests-none) - (spec-minimal - baseline)]
  replicate 1: interaction = +1.0193
  replicate 2: interaction = -0.0350
  replicate 3: interaction = +0.2119
  paired median = +0.2119

--- endpoint: fuzz, final snapshot
  baseline     n=3 median=1.0000 mean=0.9987 range=[0.9960, 1.0000] sd=0.0023
  spec-minimal n=3 median=0.9800 mean=0.6600 range=[0.0000, 1.0000] sd=0.5717
  spec-minimal-tests-none n=3 median=0.9960 mean=0.9973 range=[0.9960, 1.0000] sd=0.0023
  tests-none   n=3 median=0.8000 mean=0.6667 range=[0.2000, 1.0000] sd=0.4163
  [spec-minimal - baseline (spec effect, tests on demand)]
  replicate 1: spec-minimal - baseline = -1.0000
  replicate 2: spec-minimal - baseline = +0.0040
  replicate 3: spec-minimal - baseline = -0.0200
  paired median = -0.0200 (threshold 0.13); replicates below -0.13: 1/3, above +0.13: 0/3
  [spec-minimal-tests-none - tests-none (spec effect, no tests)]
  replicate 1: spec-minimal-tests-none - tests-none = +0.2000
  replicate 2: spec-minimal-tests-none - tests-none = -0.0040
  replicate 3: spec-minimal-tests-none - tests-none = +0.7960
  paired median = +0.2000 (threshold 0.13); replicates below -0.13: 0/3, above +0.13: 2/3
  [tests-none - baseline (tests effect, full spec)]
  replicate 1: tests-none - baseline = -0.2000
  replicate 2: tests-none - baseline = +0.0040
  replicate 3: tests-none - baseline = -0.8000
  paired median = -0.2000 (threshold 0.13); replicates below -0.13: 2/3, above +0.13: 0/3
  [spec-minimal-tests-none - spec-minimal (tests effect, minimal spec)]
  replicate 1: spec-minimal-tests-none - spec-minimal = +1.0000
  replicate 2: spec-minimal-tests-none - spec-minimal = -0.0040
  replicate 3: spec-minimal-tests-none - spec-minimal = +0.0160
  paired median = +0.0160 (threshold 0.13); replicates below -0.13: 0/3, above +0.13: 1/3
  [spec-minimal-tests-none - baseline (both factors)]
  replicate 1: spec-minimal-tests-none - baseline = +0.0000
  replicate 2: spec-minimal-tests-none - baseline = +0.0000
  replicate 3: spec-minimal-tests-none - baseline = -0.0040
  paired median = +0.0000 (threshold 0.13); replicates below -0.13: 0/3, above +0.13: 0/3
  [interaction: (both - tests-none) - (spec-minimal - baseline)]
  replicate 1: interaction = +1.2000
  replicate 2: interaction = -0.0080
  replicate 3: interaction = +0.8160
  paired median = +0.8160

--- re-score check (v9 Amendments 1 and 2): frozen vs corrected ledgers
  v9-baseline-r1                   corpus frozen=[0.9361, 0.9736] re-scored=[0.9361, 0.9736] | fuzz frozen=1.0 re-scored=[('final', 1.0)] | identical
  v9-spec-minimal-r1               corpus frozen=[0.7835, 0.0] re-scored=[0.7835, 0.0] | fuzz frozen=0.0 re-scored=[('final', 0.0), ('last_buildable', 0.727)] | CHANGED (amended: corrected ledgers are primary)
  v9-tests-none-r1                 corpus frozen=[0.0, 0.0] re-scored=[0.8637, 0.8692] | fuzz frozen=0.0 re-scored=[('final', 0.8)] | CHANGED (amended: corrected ledgers are primary)
  v9-spec-minimal-tests-none-r1    corpus frozen=[0.8579, 0.9149] re-scored=[0.8579, 0.9149] | fuzz frozen=1.0 re-scored=[('final', 1.0)] | identical
  v9-baseline-r2                   corpus frozen=[0.904, 0.9554] re-scored=[0.904, 0.9554] | fuzz frozen=0.996 re-scored=[('final', 0.996)] | identical
  v9-spec-minimal-r2               corpus frozen=[0.7393, 0.9458] re-scored=[0.7393, 0.9458] | fuzz frozen=1.0 re-scored=[('final', 1.0)] | identical
  v9-tests-none-r2                 corpus frozen=[0.9236, 0.9236] re-scored=[0.9236, 0.9236] | fuzz frozen=1.0 re-scored=[('final', 1.0)] | identical
  v9-spec-minimal-tests-none-r2    corpus frozen=[0.0, 0.879] re-scored=[0.0, 0.879] | fuzz frozen=0.996 re-scored=[('final', 0.997)] | CHANGED
  v9-baseline-r3                   corpus frozen=[0.9653, 0.9708] re-scored=[0.9653, 0.9708] | fuzz frozen=1.0 re-scored=[('final', 1.0)] | identical
  v9-spec-minimal-r3               corpus frozen=[0.7532, 0.9012] re-scored=[0.7532, 0.9012] | fuzz frozen=0.98 re-scored=[('final', 0.98)] | identical
  v9-tests-none-r3                 corpus frozen=[0.4639, 0.6823] re-scored=[0.4639, 0.6823] | fuzz frozen=0.2 re-scored=[('final', 0.2)] | identical
  v9-spec-minimal-tests-none-r3    corpus frozen=[0.0, 0.8246] re-scored=[0.0, 0.8246] | fuzz frozen=0.996 re-scored=[('final', 0.996)] | identical
  runs whose values changed under the corrected evaluator: 3/12

--- harness check (idle minutes, unanswered bash calls, cut-offs, cap-cut finals)
  runs idling >= 5 min: 1/12 [('v9-spec-minimal-tests-none-r1', 5.7)]
  runs with an unanswered bash call: 0/12
  runs with a cut-off: 5/12; total cut-offs 5
  finals that did not build (last buildable differs): 1/12
  runs with fuzz macro < 0.9 (last buildable): 3/12; corpus < 0.30: 0/12

--- secondary endpoints (per-condition medians; paired deltas vs baseline for each cell)
  output tokens        medians baseline=290427, spec-minimal=290202, spec-minimal-tests-none=281594, tests-none=280442; spec-minimal: [9818, -2780, -14020] med -2780; tests-none: [20547, -11561, -23780] med -11561; spec-minimal-tests-none: [-8942, -8833, -3201] med -8833
  input tokens         medians baseline=245017, spec-minimal=262237, spec-minimal-tests-none=272748, tests-none=264121; spec-minimal: [-72173, 14468, 69981] med +14468; tests-none: [-70289, 3438, 176304] med +3438; spec-minimal-tests-none: [-61662, 89003, 17359] med +17359
  active minutes       medians baseline=89, spec-minimal=90.3, spec-minimal-tests-none=89.2, tests-none=88.8; spec-minimal: [2.1, 1.1, -0.1] med +1.1; tests-none: [1.5, -0.9, -0.2] med -0.2; spec-minimal-tests-none: [-4.0, 0.0, 0.6] med +0
  idle minutes         medians baseline=1.1, spec-minimal=0.2, spec-minimal-tests-none=0.9, tests-none=1.3; spec-minimal: [-1.5, -0.7, 0.2] med -0.7; tests-none: [-1.6, 0.9, 0.2] med +0.2; spec-minimal-tests-none: [4.0, 0.0, -0.6] med +0
  assistant turns      medians baseline=291, spec-minimal=334, spec-minimal-tests-none=210, tests-none=276; spec-minimal: [42, 11, 139] med +42; tests-none: [-34, 45, 77] med +45; spec-minimal-tests-none: [-51, -81, -9] med -51
  tool calls           medians baseline=293, spec-minimal=341, spec-minimal-tests-none=222, tests-none=283; spec-minimal: [38, 19, 159] med +38; tests-none: [-20, 51, 63] med +51; spec-minimal-tests-none: [-26, -71, -22] med -26
  test_visible calls   medians baseline=18, spec-minimal=19, spec-minimal-tests-none=0, tests-none=0; spec-minimal: [-13, 5, -6] med -6; tests-none: [-17, -14, -25] med -17; spec-minimal-tests-none: [-18, -14, -25] med -18
  pushed reports       medians baseline=0, spec-minimal=0, spec-minimal-tests-none=0, tests-none=0; spec-minimal: [0, 0, 0] med +0; tests-none: [0, 0, 0] med +0; spec-minimal-tests-none: [0, 0, 0] med +0
  source LOC           medians baseline=2159, spec-minimal=3529, spec-minimal-tests-none=3918, tests-none=2100; spec-minimal: [952, 2192, 1370] med +1370; tests-none: [4, 187, -59] med +4; spec-minimal-tests-none: [1533, 2109, 1759] med +1759
  functions            medians baseline=61, spec-minimal=108, spec-minimal-tests-none=124, tests-none=67; spec-minimal: [29, 45, 83] med +45; tests-none: [-7, 4, 22] med +4; spec-minimal-tests-none: [64, 61, 52] med +61
  self-test programs   medians baseline=10, spec-minimal=0, spec-minimal-tests-none=13, tests-none=0; spec-minimal: [-72, -1, -10] med -10; tests-none: [-72, 136, -10] med -10; spec-minimal-tests-none: [-38, 11, 3] med +3
  self-test LOC        medians baseline=55, spec-minimal=0, spec-minimal-tests-none=306, tests-none=1303; spec-minimal: [-930, -3, -55] med -55; tests-none: [-930, 1300, 1400] med +1300; spec-minimal-tests-none: [799, 303, 107] med +303
  final build s        medians baseline=0.62, spec-minimal=0.71, spec-minimal-tests-none=0.78, tests-none=0.475; spec-minimal: [-0.4, -0.2, 0.2] med -0.21; tests-none: [-0.5, -0.1] med -0.295; spec-minimal-tests-none: [0.0, 0.1, 0.2] med +0.08
  compile ms/test      medians baseline=7.33, spec-minimal=7.36, spec-minimal-tests-none=7.41, tests-none=7.405; spec-minimal: [-0.0, 0.1] med +0.025; tests-none: [-0.0, 0.2] med +0.07; spec-minimal-tests-none: [0.1, 0.1, 0.1] med +0.12
  compactions          medians baseline=7, spec-minimal=8, spec-minimal-tests-none=7, tests-none=7; spec-minimal: [1, 0, 2] med +1; tests-none: [0, -1, 2] med +0; spec-minimal-tests-none: [0, 1, 0] med +0
  cut-offs             medians baseline=0, spec-minimal=0, spec-minimal-tests-none=0, tests-none=1; spec-minimal: [0, 0, 0] med +0; tests-none: [1, 0, 0] med +0; spec-minimal-tests-none: [0, 0, 0] med +0
  stalls               medians baseline=2, spec-minimal=2, spec-minimal-tests-none=2, tests-none=2; spec-minimal: [0, 0, 0] med +0; tests-none: [0, 0, 0] med +0; spec-minimal-tests-none: [0, 0, 0] med +0

```
