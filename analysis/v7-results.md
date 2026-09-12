# v7 results digest

```
=== v7 runs (8/8 complete)
v7-js-untyped-r1   rep=1 h=1.5 rounds=2 stalls=2 cut-offs=1 vis=0.9776 hidden=0.9579 (97/104; valid 56/57, invalid 41/47) fuzz=1.0 [1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0] kinds={} build_ok=True audit_ok=True tokens in/out=287891/282030 active/idle=88.9/1.3 turns=218 tools=219 test_visible=18 loc=1591 fns=192 self-tests=1/2 traj=[0.9343, 0.9579] fails={'unexpected_accept': 6, 'execution_timeout': 1}
    cut off: "mkdir -p /tmp/picc/suite && cd /tmp/picc/suite && cat > run_tests.sh <<'SCRIPT'\n#!/bin/bash\n# Each t"
v7-ts-strict-r1    rep=1 h=1.5 rounds=2 stalls=2 cut-offs=0 vis=0.9927 hidden=0.9667 (98/104; valid 57/57, invalid 41/47) fuzz=1.0 [1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0] kinds={} build_ok=True audit_ok=True tokens in/out=213076/304636 active/idle=88.6/1.6 turns=234 tools=246 test_visible=18 loc=1877 fns=214 self-tests=208/1076 traj=[0.9319, 0.9667] fails={'unexpected_accept': 6}
v7-js-untyped-r2   rep=2 h=1.5 rounds=2 stalls=2 cut-offs=3 vis=0.9632 hidden=0.9542 (98/104; valid 55/57, invalid 43/47) fuzz=0.993 [1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 0.95, 0.98] kinds={'wrong_behavior': 7} build_ok=True audit_ok=True tokens in/out=343815/262092 active/idle=89.5/0.7 turns=233 tools=245 test_visible=22 loc=1134 fns=131 self-tests=37/256 traj=[0.8466, 0.9542] fails={'unexpected_accept': 4, 'wrong_behavior': 1, 'unexpected_reject': 1}
    cut off: 'cd /tmp && ./m16; echo "exit=$?"; dmesg 2>&1 | tail -5; cat /proc/sys/kernel/core_pattern; ls -la co'
    cut off: 'cd /workspace && node --check src/picc.js && sh test/run.sh'
    cut off: 'cd /workspace && sh test/run.sh 2>&1 | tail -35'
v7-ts-strict-r2    rep=2 h=1.5 rounds=2 stalls=2 cut-offs=0 vis=0.0000 hidden=0.0000 (0/104; valid 0/57, invalid 0/47) fuzz=0.0 [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0] kinds={} build_ok=False audit_ok=True tokens in/out=238604/299860 active/idle=89.0/1.1 turns=217 tools=231 test_visible=18 loc=2081 fns=250 self-tests=48/796 traj=[0.9167, 0.0] fails={'build_failure': 104}
v7-js-untyped-r3   rep=3 h=1.5 rounds=2 stalls=2 cut-offs=1 vis=0.5000 hidden=0.5000 (47/104; valid 0/57, invalid 47/47) fuzz=0.0 [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0] kinds={'rejected_valid_program': 1000} build_ok=True audit_ok=True tokens in/out=457630/269602 active/idle=89.3/0.8 turns=230 tools=234 test_visible=14 loc=1208 fns=134 self-tests=0/0 traj=[0.8454, 0.5] fails={'unexpected_reject': 57}
    cut off: 'cd /tmp/picc-test/stage\nt() { printf \'%s\\n\' "$1" > dbg.c\nnode /workspace/src/picc.js dbg.c -o dbg.s '
v7-ts-strict-r3    rep=3 h=1.5 rounds=2 stalls=2 cut-offs=0 vis=0.9501 hidden=0.9653 (99/104; valid 57/57, invalid 42/47) fuzz=1.0 [1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0] kinds={} build_ok=True audit_ok=True tokens in/out=346391/265603 active/idle=89.9/0.3 turns=181 tools=187 test_visible=13 loc=1824 fns=206 self-tests=133/841 traj=[0.9389, 0.9653] fails={'unexpected_accept': 5}
v7-js-untyped-r4   rep=4 h=1.5 rounds=2 stalls=2 cut-offs=0 vis=0.9618 hidden=0.9679 (99/104; valid 55/57, invalid 44/47) fuzz=0.999 [1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 0.99, 1.0] kinds={'wrong_behavior': 1} build_ok=True audit_ok=True tokens in/out=196757/297690 active/idle=89.2/1.0 turns=272 tools=280 test_visible=25 loc=1469 fns=193 self-tests=17/837 traj=[0.9359, 0.9679] fails={'execution_timeout': 1, 'unexpected_reject': 1, 'unexpected_accept': 3}
v7-ts-strict-r4    rep=4 h=1.29 rounds=3 stalls=1 cut-offs=0 vis=1.0000 hidden=0.9667 (101/104; valid 55/57, invalid 46/47) fuzz=1.0 [1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0] kinds={} build_ok=True audit_ok=True tokens in/out=243929/255517 active/idle=77.0/0.4 turns=225 tools=232 test_visible=27 loc=1891 fns=237 self-tests=122/3093 traj=[0.9292, 0.9667, 0.9667] fails={'unexpected_accept': 1, 'wrong_behavior': 1, 'assembly_or_link_failure': 1}

--- endpoint: hidden (frozen protocol)
  js-untyped   n=4 median=0.9561 mean=0.8450 range=[0.5000, 0.9679] sd=0.2301
  ts-strict    n=4 median=0.9660 mean=0.7247 range=[0.0000, 0.9667] sd=0.4831
  replicate 1: ts-strict - js-untyped = +0.0088
  replicate 2: ts-strict - js-untyped = -0.9542
  replicate 3: ts-strict - js-untyped = +0.4653
  replicate 4: ts-strict - js-untyped = -0.0012
  paired median = +0.0038 (threshold 0.13); replicates below -0.13: 1/4, above +0.13: 1/4

--- endpoint: fuzz (frozen protocol)
  js-untyped   n=4 median=0.9960 mean=0.7480 range=[0.0000, 1.0000] sd=0.4987
  ts-strict    n=4 median=1.0000 mean=0.7500 range=[0.0000, 1.0000] sd=0.5000
  replicate 1: ts-strict - js-untyped = +0.0000
  replicate 2: ts-strict - js-untyped = -0.9930
  replicate 3: ts-strict - js-untyped = +1.0000
  replicate 4: ts-strict - js-untyped = +0.0010
  paired median = +0.0005 (threshold 0.13); replicates below -0.13: 1/4, above +0.13: 1/4

--- harness check (Amendment 1: idle minutes and unanswered bash calls, not round-cap stalls)
  runs idling >= 5 min: 0/8 []
  runs with an unanswered bash call: 0/8; total 0
  runs with a cut-off: 3/8; total cut-offs 5
  rounds ended by the 45-min cap (normal for a working agent): 15 of 17
  runs with fuzz macro < 0.9 (fuzz): 2/8; corpus < 0.30 (hidden): 1/8

--- secondary endpoints (ts-strict - js-untyped, paired by replicate; per-condition medians)
  output tokens        medians js-untyped=275816, ts-strict=282732; paired deltas [22606, 37768, -3999, -42173] median +9303.5
  input tokens         medians js-untyped=315853, ts-strict=241266; paired deltas [-74815, -105211, -111239, 47172] median -90013
  active minutes       medians js-untyped=89.25, ts-strict=88.8; paired deltas [-0.3, -0.5, 0.6, -12.2] median -0.4
  idle minutes         medians js-untyped=0.9, ts-strict=0.75; paired deltas [0.3, 0.4, -0.5, -0.6] median -0.1
  assistant turns      medians js-untyped=231.5, ts-strict=221; paired deltas [16, -16, -49, -47] median -31.5
  tool calls           medians js-untyped=239.5, ts-strict=231.5; paired deltas [27, -14, -47, -48] median -30.5
  test_visible calls   medians js-untyped=20, ts-strict=18; paired deltas [0, -4, -1, 2] median -0.5
  tsc invocations      medians js-untyped=0, ts-strict=24.5; paired deltas [27, 22, 21, 27] median +24.5
  tsc attempts blocked medians js-untyped=0, ts-strict=0; paired deltas [0, 0, 0, 0] median +0
  source LOC           medians js-untyped=1338.5, ts-strict=1884; paired deltas [286, 947, 616, 422] median +519
  functions            medians js-untyped=163, ts-strict=225.5; paired deltas [22, 119, 72, 44] median +58
  self-test programs   medians js-untyped=9, ts-strict=127.5; paired deltas [207, 11, 133, 105] median +119
  self-test LOC        medians js-untyped=129, ts-strict=958.5; paired deltas [1074, 540, 841, 2256] median +957.5
  final build s        medians js-untyped=0.01, ts-strict=0.37; paired deltas [0.4, 0.3, 0.4, 0.4] median +0.36
  compile ms/test      medians js-untyped=19.24, ts-strict=19.45; paired deltas [0.2, 0.1] median +0.145
  compactions          medians js-untyped=7, ts-strict=7; paired deltas [0, 0, -1, 0] median +0
  cut-offs             medians js-untyped=1, ts-strict=0; paired deltas [-1, -3, -1, 0] median -1
  stalls               medians js-untyped=2, ts-strict=2; paired deltas [0, 0, 0, -1] median +0

=== v4 for the harness check (same contrast on image 0.2, original oracle, no default timeout; never pooled with v7)
=== v4 runs (6/6 complete)
v4-js-untyped-r1   rep=1 h=1.5 rounds=2 stalls=2 cut-offs=0 vis=0.8930 hidden=0.8833 (90/104; valid 45/57, invalid 45/47) fuzz=None None kinds=None build_ok=True audit_ok=True tokens in/out=254257/278120 active/idle=89.6/0.5 turns=289 tools=369 test_visible=138 loc=1345 fns=156 self-tests=0/0 traj=[0.8778, 0.8833] fails={'unexpected_reject': 12, 'unexpected_accept': 2}
v4-ts-strict-r1    rep=1 h=1.51 rounds=2 stalls=2 cut-offs=0 vis=0.8602 hidden=0.8389 (87/104; valid 42/57, invalid 45/47) fuzz=None None kinds=None build_ok=True audit_ok=True tokens in/out=252819/297427 active/idle=89.4/1.3 turns=253 tools=261 test_visible=3 loc=1964 fns=226 self-tests=9/467 traj=[0.8222, 0.8389] fails={'unexpected_reject': 15, 'unexpected_accept': 2}
v4-js-untyped-r2   rep=2 h=1.5 rounds=2 stalls=2 cut-offs=0 vis=0.8641 hidden=0.8389 (87/104; valid 42/57, invalid 45/47) fuzz=None None kinds=None build_ok=True audit_ok=True tokens in/out=115920/142527 active/idle=45.7/44.5 turns=123 tools=127 test_visible=0 loc=1141 fns=139 self-tests=999/29867 traj=[0.8389, 0.8389] fails={'unexpected_reject': 15, 'unexpected_accept': 2}
v4-ts-strict-r2    rep=2 h=1.5 rounds=2 stalls=2 cut-offs=0 vis=0.8709 hidden=0.8653 (88/104; valid 45/57, invalid 43/47) fuzz=None None kinds=None build_ok=True audit_ok=True tokens in/out=215945/301658 active/idle=89.5/0.7 turns=258 tools=271 test_visible=8 loc=2000 fns=210 self-tests=110/1718 traj=[0.8764, 0.8653] fails={'unexpected_reject': 12, 'unexpected_accept': 4}
v4-js-untyped-r3   rep=3 h=1.5 rounds=2 stalls=2 cut-offs=0 vis=0.8736 hidden=0.8278 (85/104; valid 42/57, invalid 43/47) fuzz=None None kinds=None build_ok=True audit_ok=True tokens in/out=199052/223195 active/idle=86.3/3.8 turns=170 tools=171 test_visible=6 loc=1146 fns=142 self-tests=5/10 traj=[0.8333, 0.8278] fails={'unexpected_reject': 15, 'unexpected_accept': 4}
v4-ts-strict-r3    rep=3 h=1.5 rounds=2 stalls=2 cut-offs=0 vis=0.9202 hidden=0.8986 (94/104; valid 49/57, invalid 45/47) fuzz=None None kinds=None build_ok=True audit_ok=True tokens in/out=183355/185738 active/idle=55.9/34.3 turns=166 tools=167 test_visible=7 loc=1414 fns=180 self-tests=0/0 traj=[0.9069, 0.8986] fails={'unexpected_accept': 2, 'unexpected_reject': 7, 'assembly_or_link_failure': 1}

--- endpoint: hidden (frozen protocol)
  js-untyped   n=3 median=0.8389 mean=0.8500 range=[0.8278, 0.8833] sd=0.0294
  ts-strict    n=3 median=0.8653 mean=0.8676 range=[0.8389, 0.8986] sd=0.0299
  replicate 1: ts-strict - js-untyped = -0.0444
  replicate 2: ts-strict - js-untyped = +0.0264
  replicate 3: ts-strict - js-untyped = +0.0708
  paired median = +0.0264 (threshold 0.13); replicates below -0.13: 0/3, above +0.13: 0/3

--- endpoint: fuzz (frozen protocol)

--- harness check (Amendment 1: idle minutes and unanswered bash calls, not round-cap stalls)
  runs idling >= 5 min: 2/6 [('v4-js-untyped-r2', 44.5), ('v4-ts-strict-r3', 34.3)]
  runs with an unanswered bash call: 4/6; total 5
  runs with a cut-off: 0/6; total cut-offs 0
  rounds ended by the 45-min cap (normal for a working agent): 12 of 12
  runs with fuzz macro < 0.9 (fuzz): 0/0; corpus < 0.30 (hidden): 0/6

--- secondary endpoints (ts-strict - js-untyped, paired by replicate; per-condition medians)
  output tokens        medians js-untyped=223195, ts-strict=297427; paired deltas [19307, 159131, -37457] median +19307
  input tokens         medians js-untyped=199052, ts-strict=215945; paired deltas [-1438, 100025, -15697] median -1438
  active minutes       medians js-untyped=86.3, ts-strict=89.4; paired deltas [-0.2, 43.8, -30.4] median -0.2
  idle minutes         medians js-untyped=3.8, ts-strict=1.3; paired deltas [0.8, -43.8, 30.5] median +0.8
  assistant turns      medians js-untyped=170, ts-strict=253; paired deltas [-36, 135, -4] median -4
  tool calls           medians js-untyped=171, ts-strict=261; paired deltas [-108, 144, -4] median -4
  test_visible calls   medians js-untyped=6, ts-strict=7; paired deltas [-135, 8, 1] median +1
  tsc invocations      medians js-untyped=0, ts-strict=20; paired deltas [20, 24, 17] median +20
  tsc attempts blocked medians js-untyped=0, ts-strict=0; paired deltas [0, 0, 0] median +0
  source LOC           medians js-untyped=1146, ts-strict=1964; paired deltas [619, 859, 268] median +619
  functions            medians js-untyped=142, ts-strict=210; paired deltas [70, 71, 38] median +70
  self-test programs   medians js-untyped=5, ts-strict=9; paired deltas [9, -889, -5] median -5
  self-test LOC        medians js-untyped=10, ts-strict=467; paired deltas [467, -28149, -10] median -10
  final build s        medians js-untyped=0.01, ts-strict=0.36; paired deltas [0.3, 0.4, 0.3] median +0.35
  compile ms/test      medians js-untyped=18.21, ts-strict=19.7; paired deltas [0.9, 1.9, 0.4] median +0.86
  compactions          medians js-untyped=4, ts-strict=6; paired deltas [0, 4, 0] median +0
  cut-offs             medians js-untyped=0, ts-strict=0; paired deltas [0, 0, 0] median +0
  stalls               medians js-untyped=2, ts-strict=2; paired deltas [0, 0, 0] median +0

```
