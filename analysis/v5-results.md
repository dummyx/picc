# v5 results digest

```
=== v5 runs (8/8 complete)
v5-baseline-r1     rep=1 h=1.5 rounds=2 stalls=2 vis=0.9830 hidden=0.9667 (99/104; valid 55/57, invalid 44/47) fuzz=1.0 [1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0] kinds={} audit_ok=True build_ok=True tokens in/out=229203/304924 test_visible=27 traj=[0.9403, 0.9667] fails={'unexpected_reject': 1, 'wrong_behavior': 1, 'unexpected_accept': 3}
v5-tests-none-r1   rep=1 h=1.5 rounds=2 stalls=2 vis=0.9251 hidden=0.9038 (94/104; valid 52/57, invalid 42/47) fuzz=0.912 [1.0, 1.0, 1.0, 0.8, 0.91, 0.93, 0.84, 0.93, 0.84, 0.87] kinds={'wrong_behavior': 88} audit_ok=True build_ok=True tokens in/out=159668/191141 test_visible=0 traj=[0.8927, 0.9038] fails={'unexpected_accept': 5, 'execution_timeout': 1, 'unexpected_reject': 4}
v5-baseline-r2     rep=2 h=1.5 rounds=2 stalls=2 vis=0.9618 hidden=0.9556 (99/104; valid 55/57, invalid 44/47) fuzz=1.0 [1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0] kinds={} audit_ok=True build_ok=True tokens in/out=227064/303024 test_visible=17 traj=[0.9139, 0.9556] fails={'unexpected_accept': 3, 'unexpected_reject': 1, 'wrong_behavior': 1}
v5-tests-none-r2   rep=2 h=1.5 rounds=2 stalls=2 vis=0.9445 hidden=0.9736 (101/104; valid 56/57, invalid 45/47) fuzz=1.0 [1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0] kinds={} audit_ok=True build_ok=True tokens in/out=178232/209410 test_visible=0 traj=[0.9569, 0.9736] fails={'unexpected_accept': 2, 'unexpected_reject': 1}
v5-baseline-r3     rep=3 h=1.5 rounds=2 stalls=2 vis=0.7863 hidden=0.7222 (67/104; valid 24/57, invalid 43/47) fuzz=0.392 [1.0, 1.0, 1.0, 0.47, 0.24, 0.08, 0.07, 0.05, 0.01, 0.0] kinds={'assembly_or_link_failure': 607, 'wrong_behavior': 1} audit_ok=True build_ok=True tokens in/out=141318/165141 test_visible=0 traj=[0.7222, 0.7222] fails={'assembly_or_link_failure': 25, 'unexpected_accept': 4, 'unexpected_reject': 8}
v5-tests-none-r3   rep=3 h=1.52 rounds=2 stalls=2 vis=0.5152 hidden=0.4764 (44/104; valid 0/57, invalid 44/47) fuzz=0.0 [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0] kinds={'wrong_behavior': 1000} audit_ok=True build_ok=True tokens in/out=116807/93848 test_visible=0 traj=[0.4764, 0.4764] fails={'wrong_behavior': 53, 'unexpected_accept': 3, 'unexpected_reject': 4}
v5-baseline-r4     rep=4 h=1.53 rounds=2 stalls=2 vis=0.5898 hidden=0.5847 (57/104; valid 15/57, invalid 42/47) fuzz=0.019 [0.0, 0.19, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0] kinds={'assembly_or_link_failure': 200, 'timeout': 62, 'wrong_behavior': 719} audit_ok=True build_ok=True tokens in/out=39370/61032 test_visible=0 traj=[0.5847, 0.5847] fails={'wrong_behavior': 26, 'unexpected_accept': 4, 'unexpected_reject': 12, 'compiler_crash': 1, 'assembly_or_link_failure': 4}
v5-tests-none-r4   rep=4 h=1.5 rounds=2 stalls=2 vis=0.9322 hidden=0.9181 (96/104; valid 53/57, invalid 43/47) fuzz=1.0 [1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0] kinds={} audit_ok=True build_ok=True tokens in/out=251385/299760 test_visible=0 traj=[0.8806, 0.9181] fails={'unexpected_accept': 4, 'unexpected_reject': 4}

--- endpoint: hidden
  baseline     n=4 median=0.8389 mean=0.8073 range=[0.5847, 0.9667] sd=0.1864
  tests-none   n=4 median=0.9110 mean=0.8180 range=[0.4764, 0.9736] sd=0.2297
  replicate 1: tests-none - baseline = -0.0629
  replicate 2: tests-none - baseline = +0.0180
  replicate 3: tests-none - baseline = -0.2458
  replicate 4: tests-none - baseline = +0.3334
  paired median = -0.0224 (threshold 0.13); replicates below -0.13: 1/4, above +0.13: 1/4

--- endpoint: fuzz
  baseline     n=4 median=0.6960 mean=0.6028 range=[0.0190, 1.0000] sd=0.4833
  tests-none   n=4 median=0.9560 mean=0.7280 range=[0.0000, 1.0000] sd=0.4871
  replicate 1: tests-none - baseline = -0.0880
  replicate 2: tests-none - baseline = +0.0000
  replicate 3: tests-none - baseline = -0.3920
  replicate 4: tests-none - baseline = +0.9810
  paired median = -0.0440 (threshold 0.13); replicates below -0.13: 1/4, above +0.13: 1/4

=== v3 bridge (v3 finals re-scored under the revised oracle; descriptive only)
v3-baseline-r1     corpus old=0.8188 new(preprocessed)=0.9008 fuzz=1.0 [1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0]
v3-baseline-r2     corpus old=0.9306 new(preprocessed)=0.9306 fuzz=0.953 [1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 0.72, 0.81]
v3-baseline-r3     corpus old=0.8194 new(preprocessed)=0.9097 fuzz=0.956 [1.0, 1.0, 1.0, 1.0, 1.0, 0.92, 0.88, 0.95, 0.89, 0.92]
v3-tests-none-r1   corpus old=0.8458 new(preprocessed)=0.9361 fuzz=1.0 [1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0]
v3-tests-none-r2   corpus old=0.7492 new(preprocessed)=0.8089 fuzz=0.68 [1.0, 1.0, 1.0, 0.86, 0.8, 0.82, 0.82, 0.31, 0.19, 0.0]
v3-tests-none-r3   corpus old=0.6839 new(preprocessed)=0.7464 fuzz=0.228 [1.0, 1.0, 0.02, 0.07, 0.02, 0.06, 0.04, 0.07, 0.0, 0.0]
  v3 corpus new: paired deltas [0.0353, -0.1216, -0.1633] median -0.1216
  v3 fuzz: paired deltas [0.0, -0.273, -0.728] median -0.2730
```
