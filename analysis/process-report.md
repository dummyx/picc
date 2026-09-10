# PiCC process metrics

Descriptive only: one run per condition, and run length was set by when the agent hung or was killed rather than by the condition, so cross-condition differences are not yet attributable to the treatments.

## By condition

Output cap `65536` — 48 run(s)

| Condition | n | Scores (audit-passing) | Median | Spread | Audit pass | Declined tool |
|---|---:|---|---:|---:|---:|---:|
| `baseline` | 14 | 0.958, 0.819, 0.967, 1.000, 0.819, 0.898, 0.931, 0.956, 0.771, 0.898, 0.722, 0.877, 0.585 | 0.8981 | 0.415 | 13/14 | 7/14 |
| `js-untyped` | 4 | 0.883, 1.000, 0.839, 0.828 | 0.8833 | 0.172 | 4/4 | 1/4 |
| `prompt-minimal` | 4 | 0.958, 0.958 | 0.9583 | 0.000 | 2/4 | 1/4 |
| `spec-architecture` | 6 | 0.898, 0.870, 0.877, 0.863, 0.000, 0.958 | 0.8773 | 0.958 | 6/6 | 2/6 |
| `spec-brief` | 4 | 0.958, 0.898, 0.898 | 0.8981 | 0.060 | 3/4 | 1/4 |
| `spec-inline` | 4 | 0.863, 0.898, 0.958, 0.958 | 0.9583 | 0.095 | 4/4 | 1/4 |
| `tests-none` | 8 | 0.846, 0.000, 0.904, 0.749, 0.974, 0.684, 0.476, 0.918 | 0.8458 | 0.974 | 8/8 | 0/8 |
| `ts-strict` | 4 | 0.958, 0.839, 0.865, 0.899 | 0.8986 | 0.119 | 4/4 | 1/4 |

Output cap `32768` — 6 run(s)

| Condition | n | Scores (audit-passing) | Median | Spread | Audit pass | Declined tool |
|---|---:|---|---:|---:|---:|---:|
| `baseline` | 2 | 0.869 | 0.8694 | — | 1/2 | 1/2 |
| `language-python` | 1 | 0.785 | 0.7847 | — | 1/1 | 1/1 |
| `reference-oracle` | 1 | 0.877 | 0.8773 | — | 1/1 | 0/1 |
| `spec-brief` | 1 | 0.840 | 0.8403 | — | 1/1 | 1/1 |
| `tests-none` | 1 | 0.898 | 0.8981 | — | 1/1 | 0/1 |

| Run | Cond | Rep | Cap | Rounds | Active/Elapsed min | Turns | Tools | Truncated | Offered-but-declined | Hidden |
|---|---|---|---|---|---|---|---|---|---|
| baseline-main-r1 | baseline | 1 | 32768 | 1 | 25.0/1440.0 | 52 | 63 | 0 | experiment_status=0, test_visible=0 | 0.8694 |
| baseline-pilot-r1 | baseline | 1 | 32768 | 1 | 44.8/45.0 | 145 | 161 | 1 | all used / none offered | 0.0 |
| baseline-pilot-r2 | baseline | 2 | 65536 | 1 | 43.4/45.0 | 95 | 104 | 1 | test_visible=0 | 0.8194 |
| baseline-pilot-r3 | baseline | 3 | 65536 | 1 | 25.2/45.0 | 57 | 61 | 0 | test_visible=0 | 0.7708 |
| baseline-pilot-r4 | baseline | 4 | 65536 | 1 | 36.8/45.0 | 142 | 150 | 1 | all used / none offered | 0.8773 |
| language-python-pilot-r1 | language-python | 1 | 32768 | 4 | 43.0/68.4 | 28 | 29 | 4 | test_visible=0 | 0.7847 |
| prompt-minimal-pilot-r1 | prompt-minimal | 1 | 65536 | 2 | 61.0/61.2 | 135 | 139 | 2 | experiment_status=0, test_visible=0 | 0.0 |
| reference-oracle-pilot-r1 | reference-oracle | 1 | 32768 | 3 | 59.5/60.7 | 136 | 136 | 4 | reference_oracle=0 | 0.8773 |
| spec-architecture-pilot-r1 | spec-architecture | 1 | 65536 | 1 | 44.4/45.0 | 114 | 128 | 2 | experiment_status=0 | 0.8981 |
| spec-architecture-pilot-r2 | spec-architecture | 2 | 65536 | 1 | 41.6/45.0 | 122 | 128 | 1 | all used / none offered | 0.8773 |
| spec-architecture-pilot-r3 | spec-architecture | 3 | 65536 | 2 | 61.0/81.2 | 57 | 63 | 3 | test_visible=0 | 0.0 |
| spec-brief-pilot-r1 | spec-brief | 1 | 32768 | 6 | 67.8/68.2 | 68 | 66 | 6 | test_visible=0 | 0.8403 |
| spec-brief-pilot-r2 | spec-brief | 2 | 65536 | 1 | 44.7/45.0 | 172 | 180 | 1 | all used / none offered | 0.8981 |
| spec-inline-pilot-r1 | spec-inline | 1 | 65536 | 1 | 44.5/45.0 | 81 | 87 | 1 | all used / none offered | 0.8634 |
| tests-none-pilot-r1 | tests-none | 1 | 32768 | 1 | 44.6/45.0 | 100 | 104 | 1 | experiment_status=0 | 0.8981 |
| v2-baseline-r1 | baseline | 1 | 65536 | 2 | 75.6/75.8 | 322 | 330 | 4 | all used / none offered | 0.9583 |
| v2-baseline-r2 | baseline | 2 | 65536 | 2 | 45.0/90.1 | 35 | 40 | 0 | test_visible=0 | 0.8981 |
| v2-baseline-r3 | baseline | 3 | 65536 | 3 | 61.3/106.3 | 56 | 61 | 1 | experiment_status=0, test_visible=0 | 0.8981 |
| v2-prompt-minimal-r1 | prompt-minimal | 1 | 65536 | 2 | 46.5/90.0 | 163 | 167 | 1 | experiment_status=0 | 0.9583 |
| v2-prompt-minimal-r2 | prompt-minimal | 2 | 65536 | 2 | 89.6/90.0 | 295 | 312 | 3 | all used / none offered | 0.9583 |
| v2-prompt-minimal-r3 | prompt-minimal | 3 | 65536 | 2 | 54.6/90.0 | 102 | 108 | 3 | all used / none offered | 0.0 |
| v2-spec-architecture-r1 | spec-architecture | 1 | 65536 | 2 | 45.0/90.1 | 45 | 55 | 0 | experiment_status=0, test_visible=0 | 0.8704 |
| v2-spec-architecture-r2 | spec-architecture | 2 | 65536 | 2 | 72.2/90.0 | 197 | 203 | 4 | experiment_status=0 | 0.8634 |
| v2-spec-architecture-r3 | spec-architecture | 3 | 65536 | 2 | 74.9/90.0 | 213 | 252 | 3 | all used / none offered | 0.9583 |
| v2-spec-brief-r1 | spec-brief | 1 | 65536 | 4 | 118.7/120.0 | 247 | 243 | 4 | all used / none offered | 0.9583 |
| v2-spec-brief-r2 | spec-brief | 2 | 65536 | 2 | 89.1/90.0 | 256 | 302 | 3 | all used / none offered | 0.8981 |
| v2-spec-brief-r3 | spec-brief | 3 | 65536 | 2 | 89.8/90.1 | 259 | 273 | 3 | experiment_status=0, test_visible=0 | 0.877 |
| v2-spec-inline-r1 | spec-inline | 1 | 65536 | 2 | 87.3/90.1 | 237 | 241 | 5 | experiment_status=0, test_visible=0 | 0.8981 |
| v2-spec-inline-r2 | spec-inline | 2 | 65536 | 3 | 104.1/104.4 | 278 | 281 | 6 | all used / none offered | 0.9583 |
| v2-spec-inline-r3 | spec-inline | 3 | 65536 | 2 | 88.4/90.1 | 264 | 287 | 3 | all used / none offered | 0.9583 |
| v3-baseline-r1 | baseline | 1 | 65536 | 2 | 48.7/90.4 | 209 | 216 | 1 | experiment_status=0 | 0.8188 |
| v3-baseline-r2 | baseline | 2 | 65536 | 2 | 89.7/90.1 | 340 | 350 | 3 | experiment_status=0 | 0.9306 |
| v3-baseline-r3 | baseline | 3 | 65536 | 2 | 55.3/90.1 | 160 | 169 | 3 | experiment_status=0 | 0.8194 |
| v3-tests-none-r1 | tests-none | 1 | 65536 | 4 | 119.5/120.0 | 502 | 501 | 6 | all used / none offered | 0.8458 |
| v3-tests-none-r2 | tests-none | 2 | 65536 | 2 | 45.9/91.7 | 30 | 36 | 0 | experiment_status=0 | 0.7492 |
| v3-tests-none-r3 | tests-none | 3 | 65536 | 2 | 45.3/90.5 | 36 | 52 | 0 | experiment_status=0 | 0.6839 |
| v4-js-untyped-r1 | js-untyped | 1 | 65536 | 2 | 89.6/90.1 | 289 | 369 | 4 | all used / none offered | 0.8833 |
| v4-js-untyped-r2 | js-untyped | 2 | 65536 | 2 | 45.7/90.2 | 123 | 127 | 2 | test_visible=0 | 0.8389 |
| v4-js-untyped-r3 | js-untyped | 3 | 65536 | 2 | 86.3/90.1 | 170 | 171 | 2 | all used / none offered | 0.8278 |
| v4-pilot-js-untyped-smoke1 | js-untyped | 1 | 65536 | 2 | 23.9/24.0 | 31 | 32 | 0 | experiment_status=0 | 1.0 |
| v4-pilot-ts-strict-smoke1 | ts-strict | 1 | 65536 | 2 | 23.4/24.0 | 75 | 84 | 0 | test_visible=0 | 0.9583 |
| v4-ts-strict-r1 | ts-strict | 1 | 65536 | 2 | 89.4/90.7 | 253 | 261 | 5 | all used / none offered | 0.8389 |
| v4-ts-strict-r2 | ts-strict | 2 | 65536 | 2 | 89.5/90.2 | 258 | 271 | 4 | all used / none offered | 0.8653 |
| v4-ts-strict-r3 | ts-strict | 3 | 65536 | 2 | 55.9/90.2 | 166 | 167 | 3 | experiment_status=0 | 0.8986 |
| v5-baseline-r1 | baseline | 1 | 65536 | 2 | 89.7/90.1 | 342 | 351 | 2 | all used / none offered | 0.9667 |
| v5-baseline-r2 | baseline | 2 | 65536 | 2 | 90.0/90.1 | 336 | 347 | 4 | experiment_status=0 | 0.9556 |
| v5-baseline-r3 | baseline | 3 | 65536 | 2 | 45.3/90.1 | 131 | 138 | 2 | test_visible=0 | 0.7222 |
| v5-baseline-r4 | baseline | 4 | 65536 | 2 | 45.9/91.8 | 32 | 39 | 0 | experiment_status=0, test_visible=0 | 0.5847 |
| v5-pilot-baseline-smoke1 | baseline | 1 | 65536 | 2 | 23.6/24.0 | 50 | 56 | 0 | experiment_status=0, test_visible=0 | 1.0 |
| v5-pilot-tests-none-smoke1 | tests-none | 1 | 65536 | 2 | 21.9/24.0 | 8 | 11 | 0 | experiment_status=0 | 0.0 |
| v5-tests-none-r1 | tests-none | 1 | 65536 | 2 | 55.1/90.1 | 141 | 162 | 2 | all used / none offered | 0.9038 |
| v5-tests-none-r2 | tests-none | 2 | 65536 | 2 | 59.8/90.1 | 158 | 176 | 2 | all used / none offered | 0.9736 |
| v5-tests-none-r3 | tests-none | 3 | 65536 | 2 | 46.0/91.3 | 72 | 75 | 1 | all used / none offered | 0.4764 |
| v5-tests-none-r4 | tests-none | 4 | 65536 | 2 | 89.5/90.1 | 307 | 315 | 3 | experiment_status=0 | 0.9181 |

## baseline-main-r1  (condition `baseline`, factor `baseline`)

- termination: `round_timeout`, visible trajectory: [0.8566]
- regressions: 0, buildable snapshots: 1/1, final LOC: 1762
- tools: {'bash': 39, 'edit': 13, 'write': 9, 'read': 1, 'ls': 1}
- shell intent: {'self_test': 27, 'build': 7, 'other': 5}
- affordances: test_visible=0 (offered), experiment_status=0 (offered), reference_oracle=0 (not offered)
- PROGRESS.md kept: False; self-authored test artifacts: ['tests-local']
- thinking 188,912 chars vs prose 2,965 chars; output tokens 95,303
- guard blocks: 0 ; compactions: 0; provider retries: 0
- hidden failure types: {'unexpected_reject': 10, 'unexpected_accept': 2}
- **stalled** in round-000 on `bash`: `cd /workspace/tests-local/cases
sed -i 's/(a % 1000 == -48)/(a % 1000 == -8)/' e22_wrap.c
cat > e26_shadow_global.c <<'EOF'
int g2(void);
int g = 10;
int main(v`

## baseline-pilot-r1  (condition `baseline`, factor `baseline`)

- termination: `round_timeout`, visible trajectory: [0.0]
- regressions: 0, buildable snapshots: 0/1, final LOC: 2011
- tools: {'bash': 107, 'edit': 24, 'read': 10, 'write': 10, 'test_visible': 6, 'experiment_status': 3, 'ls': 1}
- shell intent: {'other': 41, 'self_test': 29, 'build': 17, 'write_via_shell': 12, 'vcs': 6, 'inspect': 2}
- affordances: test_visible=6 (offered), experiment_status=3 (offered), reference_oracle=0 (not offered)
- PROGRESS.md kept: True; self-authored test artifacts: none
- thinking 347,905 chars vs prose 7,945 chars; output tokens 155,716
- guard blocks: 4 {'direct use of an existing C/C++ compiler is prohibited; use the experimental tools': 2, 'direct evaluator execution is prohibited; use the condition-controlled tools': 1, 'retrieving external repository content is prohibited': 1}; compactions: 2; provider retries: 0
- hidden failure types: {'source_audit_failure': 12}

## baseline-pilot-r2  (condition `baseline`, factor `baseline`)

- termination: `round_timeout`, visible trajectory: [0.8768]
- regressions: 0, buildable snapshots: 1/1, final LOC: 1891
- tools: {'bash': 74, 'edit': 11, 'read': 10, 'write': 7, 'ls': 1, 'experiment_status': 1}
- shell intent: {'self_test': 55, 'build': 9, 'other': 7, 'inspect': 2, 'write_via_shell': 1}
- affordances: test_visible=0 (offered), experiment_status=1 (offered), reference_oracle=0 (not offered)
- PROGRESS.md kept: False; self-authored test artifacts: none
- thinking 355,496 chars vs prose 5,558 chars; output tokens 152,838
- guard blocks: 1 {'direct use of an existing C/C++ compiler is prohibited; use the experimental tools': 1}; compactions: 2; provider retries: 0
- hidden failure types: {'unexpected_reject': 6, 'assembly_or_link_failure': 2, 'wrong_behavior': 2, 'unexpected_accept': 2}

## baseline-pilot-r3  (condition `baseline`, factor `baseline`)

- termination: `round_timeout`, visible trajectory: [0.7966]
- regressions: 0, buildable snapshots: 1/1, final LOC: 2233
- tools: {'bash': 34, 'edit': 12, 'write': 9, 'read': 4, 'ls': 1, 'experiment_status': 1}
- shell intent: {'other': 10, 'build': 9, 'write_via_shell': 8, 'self_test': 4, 'inspect': 3}
- affordances: test_visible=0 (offered), experiment_status=1 (offered), reference_oracle=0 (not offered)
- PROGRESS.md kept: False; self-authored test artifacts: none
- thinking 209,481 chars vs prose 1,494 chars; output tokens 94,181
- guard blocks: 0 ; compactions: 0; provider retries: 0
- hidden failure types: {'unexpected_reject': 6, 'assembly_or_link_failure': 4, 'wrong_behavior': 1, 'unexpected_accept': 1}
- **stalled** in round-000 on `bash`: `cd /workspace/scratch && ld -o faketest fake.o stub.o 2>/dev/null && ./faketest; echo "RC=$?"; ld -o tt t.o stub.o 2>/dev/null && ./tt; echo "RC2=$?"`

## baseline-pilot-r4  (condition `baseline`, factor `baseline`)

- termination: `round_timeout`, visible trajectory: [0.8947]
- regressions: 0, buildable snapshots: 1/1, final LOC: 1687
- tools: {'bash': 119, 'edit': 10, 'write': 8, 'read': 6, 'test_visible': 5, 'ls': 1, 'experiment_status': 1}
- shell intent: {'self_test': 36, 'other': 31, 'write_via_shell': 29, 'build': 22, 'inspect': 1}
- affordances: test_visible=5 (offered), experiment_status=1 (offered), reference_oracle=0 (not offered)
- PROGRESS.md kept: False; self-authored test artifacts: ['dev-tests']
- thinking 274,271 chars vs prose 5,746 chars; output tokens 130,684
- guard blocks: 1 {'direct evaluator execution is prohibited; use the condition-controlled tools': 1}; compactions: 2; provider retries: 0
- hidden failure types: {'unexpected_reject': 8, 'unexpected_accept': 2}
- **stalled** in round-000 on `bash`: `cd /workspace/dev-tests && t() { printf 'int main(void) { int a=1,b=2,c=3,d=4,x=1,y=1; %s }\n' "$1" > probe/p.c; ../target/release/picc probe/p.c -o probe/p.s >`

## language-python-pilot-r1  (condition `language-python`, factor `candidate`)

- termination: `round_timeout`, visible trajectory: [0.0, 0.0, 0.0, 0.7949]
- regressions: 0, buildable snapshots: 1/4, final LOC: 2927
- tools: {'write': 13, 'bash': 6, 'edit': 6, 'ls': 2, 'read': 1, 'experiment_status': 1}
- shell intent: {'self_test': 3, 'other': 2, 'inspect': 1}
- affordances: test_visible=0 (offered), experiment_status=1 (offered), reference_oracle=0 (not offered)
- PROGRESS.md kept: False; self-authored test artifacts: ['.selftest']
- thinking 459,742 chars vs prose 1,522 chars; output tokens 175,652
- guard blocks: 2 {'writes are restricted to /workspace': 2}; compactions: 0; provider retries: 0
- hidden failure types: {'unexpected_reject': 8, 'wrong_behavior': 4}
- **stalled** in round-003 on `bash`: `cd /workspace && python3 .selftest/gen_tests.py && bash .selftest/all.sh`

## prompt-minimal-pilot-r1  (condition `prompt-minimal`, factor `prompt`)

- termination: `round_timeout`, visible trajectory: [0.0, 0.0]
- regressions: 0, buildable snapshots: 0/2, final LOC: 2482
- tools: {'bash': 76, 'edit': 37, 'read': 14, 'write': 11, 'ls': 1}
- shell intent: {'other': 37, 'build': 22, 'self_test': 9, 'write_via_shell': 7, 'inspect': 1}
- affordances: test_visible=0 (offered), experiment_status=0 (offered), reference_oracle=0 (not offered)
- PROGRESS.md kept: False; self-authored test artifacts: none
- thinking 498,053 chars vs prose 5,791 chars; output tokens 217,099
- guard blocks: 0 ; compactions: 2; provider retries: 0
- hidden failure types: {'source_audit_failure': 12}

## reference-oracle-pilot-r1  (condition `reference-oracle`, factor `reference`)

- termination: `round_timeout`, visible trajectory: [0.0, 0.0, 0.9548]
- regressions: 0, buildable snapshots: 1/3, final LOC: 1957
- tools: {'bash': 86, 'edit': 28, 'read': 10, 'write': 7, 'test_visible': 3, 'ls': 1, 'experiment_status': 1}
- shell intent: {'other': 27, 'build': 20, 'self_test': 19, 'write_via_shell': 16, 'inspect': 4}
- affordances: test_visible=3 (offered), experiment_status=1 (offered), reference_oracle=0 (offered)
- PROGRESS.md kept: False; self-authored test artifacts: none
- thinking 557,920 chars vs prose 5,804 chars; output tokens 218,558
- guard blocks: 2 {'direct access to visible test files is withheld': 1, 'direct use of an existing C/C++ compiler is prohibited; use the experimental tools': 1}; compactions: 2; provider retries: 0
- hidden failure types: {'unexpected_reject': 8, 'unexpected_accept': 2}
- **stalled** in round-002 on `bash`: `cd /workspace && cargo build --release --offline 2>&1 | grep -E "^error" -A6; cd /tmp/picctest
./check.sh h7.c 28
./check.sh h8.c 36
cat > h9.c <<'EOF'
int inne`

## spec-architecture-pilot-r1  (condition `spec-architecture`, factor `specification`)

- termination: `round_timeout`, visible trajectory: [0.9313]
- regressions: 0, buildable snapshots: 1/1, final LOC: 2833
- tools: {'bash': 66, 'edit': 32, 'write': 12, 'test_visible': 10, 'read': 5, 'grep': 2, 'ls': 1}
- shell intent: {'other': 22, 'self_test': 17, 'build': 15, 'write_via_shell': 11, 'inspect': 1}
- affordances: test_visible=10 (offered), experiment_status=0 (offered), reference_oracle=0 (not offered)
- PROGRESS.md kept: False; self-authored test artifacts: none
- thinking 308,561 chars vs prose 4,749 chars; output tokens 155,378
- guard blocks: 3 {'writes are restricted to /workspace': 2, 'direct use of an existing C/C++ compiler is prohibited; use the experimental tools': 1}; compactions: 2; provider retries: 0
- hidden failure types: {'unexpected_reject': 8, 'unexpected_accept': 1}

## spec-architecture-pilot-r2  (condition `spec-architecture`, factor `specification`)

- termination: `round_timeout`, visible trajectory: [0.9429]
- regressions: 0, buildable snapshots: 1/1, final LOC: 2829
- tools: {'bash': 79, 'edit': 21, 'test_visible': 11, 'write': 10, 'read': 4, 'experiment_status': 2, 'ls': 1}
- shell intent: {'other': 30, 'self_test': 20, 'build': 18, 'inspect': 11}
- affordances: test_visible=11 (offered), experiment_status=2 (offered), reference_oracle=0 (not offered)
- PROGRESS.md kept: False; self-authored test artifacts: none
- thinking 290,227 chars vs prose 5,521 chars; output tokens 147,798
- guard blocks: 1 {"reads are restricted by this condition's test/reference access policy": 1}; compactions: 2; provider retries: 0
- hidden failure types: {'unexpected_reject': 8, 'unexpected_accept': 2}
- **stalled** in round-000 on `bash`: `cd /tmp/picctest && . ./battery.sh
t 'int main(void){int x=1,y=0;if(x)y=2;return y;}' 2
t 'int main(void){int x=0,y=0;if(x);y=3;return y;}' 3
t 'int main(void){`

## spec-architecture-pilot-r3  (condition `spec-architecture`, factor `specification`)

- termination: `round_timeout`, visible trajectory: [0.0, 0.0139]
- regressions: 0, buildable snapshots: 1/2, final LOC: 4325
- tools: {'bash': 25, 'edit': 16, 'write': 13, 'read': 5, 'experiment_status': 2, 'ls': 1, 'grep': 1}
- shell intent: {'other': 11, 'build': 10, 'inspect': 2, 'write_via_shell': 1, 'self_test': 1}
- affordances: test_visible=0 (offered), experiment_status=2 (offered), reference_oracle=0 (not offered)
- PROGRESS.md kept: False; self-authored test artifacts: none
- thinking 491,641 chars vs prose 2,391 chars; output tokens 220,166
- guard blocks: 0 ; compactions: 2; provider retries: 0
- hidden failure types: {'compiler_crash': 12}

## spec-brief-pilot-r1  (condition `spec-brief`, factor `specification`)

- termination: `max_rounds`, visible trajectory: [0.0, 0.0, 0.0, 0.0, 0.0, 0.9472]
- regressions: 0, buildable snapshots: 1/6, final LOC: 2171
- tools: {'bash': 49, 'write': 7, 'edit': 7, 'read': 1, 'ls': 1, 'experiment_status': 1}
- shell intent: {'self_test': 18, 'other': 17, 'build': 12, 'inspect': 1, 'write_via_shell': 1}
- affordances: test_visible=0 (offered), experiment_status=1 (offered), reference_oracle=0 (not offered)
- PROGRESS.md kept: False; self-authored test artifacts: none
- thinking 748,806 chars vs prose 2,919 chars; output tokens 272,581
- guard blocks: 1 {'direct use of an existing C/C++ compiler is prohibited; use the experimental tools': 1}; compactions: 1; provider retries: 0
- hidden failure types: {'unexpected_reject': 7, 'wrong_behavior': 3, 'unexpected_accept': 2}

## spec-brief-pilot-r2  (condition `spec-brief`, factor `specification`)

- termination: `round_timeout`, visible trajectory: [0.9548]
- regressions: 0, buildable snapshots: 1/1, final LOC: 2872
- tools: {'bash': 101, 'edit': 44, 'read': 21, 'write': 7, 'test_visible': 4, 'ls': 1, 'experiment_status': 1, 'grep': 1}
- shell intent: {'other': 31, 'write_via_shell': 31, 'build': 20, 'self_test': 13, 'inspect': 6}
- affordances: test_visible=4 (offered), experiment_status=1 (offered), reference_oracle=0 (not offered)
- PROGRESS.md kept: False; self-authored test artifacts: none
- thinking 317,190 chars vs prose 6,716 chars; output tokens 157,524
- guard blocks: 2 {'direct access to visible test files is withheld': 1, 'credential or harness-internal access is prohibited': 1}; compactions: 2; provider retries: 0
- hidden failure types: {'unexpected_reject': 8, 'unexpected_accept': 1}

## spec-inline-pilot-r1  (condition `spec-inline`, factor `specification`)

- termination: `round_timeout`, visible trajectory: [0.9353]
- regressions: 0, buildable snapshots: 1/1, final LOC: 1949
- tools: {'bash': 38, 'edit': 25, 'write': 8, 'read': 7, 'test_visible': 5, 'grep': 2, 'ls': 1, 'experiment_status': 1}
- shell intent: {'self_test': 18, 'other': 12, 'build': 3, 'write_via_shell': 3, 'inspect': 2}
- affordances: test_visible=5 (offered), experiment_status=1 (offered), reference_oracle=0 (not offered)
- PROGRESS.md kept: False; self-authored test artifacts: ['local-test']
- thinking 328,995 chars vs prose 4,757 chars; output tokens 144,721
- guard blocks: 2 {'direct use of an existing C/C++ compiler is prohibited; use the experimental tools': 1, 'direct access to visible test files is withheld': 1}; compactions: 2; provider retries: 0
- hidden failure types: {'unexpected_reject': 8, 'unexpected_accept': 2, 'wrong_behavior': 1}

## tests-none-pilot-r1  (condition `tests-none`, factor `tests`)

- termination: `round_timeout`, visible trajectory: [0.9548]
- regressions: 0, buildable snapshots: 1/1, final LOC: 2071
- tools: {'bash': 78, 'write': 11, 'edit': 6, 'read': 5, 'grep': 3, 'ls': 1}
- shell intent: {'self_test': 49, 'build': 15, 'other': 11, 'write_via_shell': 2, 'inspect': 1}
- affordances: test_visible=0 (not offered), experiment_status=0 (offered), reference_oracle=0 (not offered)
- PROGRESS.md kept: False; self-authored test artifacts: ['tests']
- thinking 262,960 chars vs prose 6,325 chars; output tokens 158,839
- guard blocks: 0 ; compactions: 2; provider retries: 0
- hidden failure types: {'unexpected_reject': 8, 'unexpected_accept': 1}

## v2-baseline-r1  (condition `baseline`, factor `baseline`)

- termination: `visible_complete_after_review`, visible trajectory: [1.0, 1.0]
- regressions: 0, buildable snapshots: 2/2, final LOC: 2516
- tools: {'bash': 192, 'edit': 55, 'read': 36, 'test_visible': 20, 'write': 14, 'grep': 6, 'experiment_status': 5, 'ls': 2}
- shell intent: {'self_test': 102, 'other': 58, 'write_via_shell': 19, 'build': 12, 'inspect': 1}
- affordances: test_visible=20 (offered), experiment_status=5 (offered), reference_oracle=0 (not offered)
- PROGRESS.md kept: True; self-authored test artifacts: ['local-tests']
- thinking 463,215 chars vs prose 15,451 chars; output tokens 242,834
- guard blocks: 1 {'writes are restricted to /workspace': 1}; compactions: 6; provider retries: 0
- hidden failure types: {'unexpected_accept': 2}

## v2-baseline-r2  (condition `baseline`, factor `baseline`)

- termination: `round_timeout`, visible trajectory: [0.9429, 0.9429]
- regressions: 0, buildable snapshots: 2/2, final LOC: 1860
- tools: {'bash': 25, 'write': 6, 'edit': 4, 'read': 2, 'ls': 2, 'experiment_status': 1}
- shell intent: {'other': 13, 'build': 7, 'write_via_shell': 2, 'self_test': 2, 'inspect': 1}
- affordances: test_visible=0 (offered), experiment_status=1 (offered), reference_oracle=0 (not offered)
- PROGRESS.md kept: False; self-authored test artifacts: none
- thinking 190,097 chars vs prose 1,751 chars; output tokens 97,788
- guard blocks: 0 ; compactions: 0; provider retries: 0
- hidden failure types: {'unexpected_reject': 8, 'unexpected_accept': 1}
- **stalled** in round-000 on `bash`: `cd /workspace && cat > scratch/t/s4c.c <<'EOF'
int main(void) {
    int a = 1;
    int b = 0;
    int r = (a == 1) && (b = 5);
    return r * 100 + b;
}
EOF
car`
- **stalled** in round-001 on `bash`: `cd /workspace && cargo build --release --offline 2>&1 | grep -cE "^(error|warning)" ; for t in "s1a 42" "s1b 0" "s1c 8" "s2a 3" "s2b 0" "s2c 2" "s3a 9" "s3b 10"`

## v2-baseline-r3  (condition `baseline`, factor `baseline`)

- termination: `round_timeout`, visible trajectory: [0.0, 0.9373, 0.9373]
- regressions: 0, buildable snapshots: 2/3, final LOC: 2164
- tools: {'bash': 28, 'edit': 22, 'write': 8, 'read': 2, 'ls': 1}
- shell intent: {'self_test': 17, 'build': 7, 'inspect': 3, 'other': 1}
- affordances: test_visible=0 (offered), experiment_status=0 (offered), reference_oracle=0 (not offered)
- PROGRESS.md kept: False; self-authored test artifacts: none
- thinking 399,720 chars vs prose 2,675 chars; output tokens 154,457
- guard blocks: 0 ; compactions: 0; provider retries: 0
- hidden failure types: {'unexpected_reject': 8, 'unexpected_accept': 1}
- **stalled** in round-001 on `bash`: `cd /workspace && cargo build --release --offline 2>&1 | grep -cE "^error"; cd /tmp/picc-test && PICC=/workspace/target/release/picc
for t in d1 d2 t1 t3; do $PI`
- **stalled** in round-002 on `bash`: `mkdir -p /tmp/picc-test && cd /tmp/picc-test && PICC=/workspace/target/release/picc
cat > stub.s <<'EOF'
.intel_syntax noprefix
.global _start
_start:
    call `

## v2-prompt-minimal-r1  (condition `prompt-minimal`, factor `prompt`)

- termination: `round_timeout`, visible trajectory: [1.0, 1.0]
- regressions: 0, buildable snapshots: 2/2, final LOC: 2385
- tools: {'bash': 116, 'edit': 25, 'read': 14, 'write': 7, 'test_visible': 4, 'ls': 1}
- shell intent: {'self_test': 56, 'other': 23, 'build': 21, 'write_via_shell': 15, 'inspect': 1}
- affordances: test_visible=4 (offered), experiment_status=0 (offered), reference_oracle=0 (not offered)
- PROGRESS.md kept: False; self-authored test artifacts: none
- thinking 322,652 chars vs prose 6,150 chars; output tokens 155,861
- guard blocks: 1 {'direct use of an existing C/C++ compiler is prohibited; use the experimental tools': 1}; compactions: 2; provider retries: 0
- hidden failure types: {'unexpected_accept': 2}
- **stalled** in round-001 on `bash`: `cd /tmp/pc/tests && cat > h1.c <<'EOF'
/* nested loops: break/continue targeting */
int main(void) {
    int r = 0;
    int i = 0;
    while (i < 5) {
        i`

## v2-prompt-minimal-r2  (condition `prompt-minimal`, factor `prompt`)

- termination: `round_timeout`, visible trajectory: [0.0, 1.0]
- regressions: 0, buildable snapshots: 1/2, final LOC: 2272
- tools: {'bash': 155, 'edit': 57, 'test_visible': 40, 'read': 37, 'write': 17, 'experiment_status': 4, 'ls': 1, 'grep': 1}
- shell intent: {'other': 76, 'self_test': 52, 'build': 22, 'write_via_shell': 4, 'inspect': 1}
- affordances: test_visible=40 (offered), experiment_status=4 (offered), reference_oracle=0 (not offered)
- PROGRESS.md kept: False; self-authored test artifacts: ['.picc_tests']
- thinking 687,147 chars vs prose 15,957 chars; output tokens 295,839
- guard blocks: 3 {'writes are restricted to /workspace': 1, 'mutation of experiment-control files is prohibited': 1, "reads are restricted by this condition's test/reference access policy": 1}; compactions: 7; provider retries: 0
- hidden failure types: {'unexpected_accept': 2}

## v2-prompt-minimal-r3  (condition `prompt-minimal`, factor `prompt`)

- termination: `round_timeout`, visible trajectory: [0.9548, 0.0]
- regressions: 1, buildable snapshots: 1/2, final LOC: 3278
- tools: {'bash': 59, 'edit': 21, 'write': 14, 'read': 8, 'test_visible': 4, 'ls': 1, 'experiment_status': 1}
- shell intent: {'build': 22, 'self_test': 20, 'other': 10, 'write_via_shell': 5, 'inspect': 2}
- affordances: test_visible=4 (offered), experiment_status=1 (offered), reference_oracle=0 (not offered)
- PROGRESS.md kept: False; self-authored test artifacts: none
- thinking 400,098 chars vs prose 5,557 chars; output tokens 184,228
- guard blocks: 1 {'writes are restricted to /workspace': 1}; compactions: 4; provider retries: 0
- hidden failure types: {'source_audit_failure': 12}
- **stalled** in round-001 on `bash`: `/workspace/tools/fuzz.sh 0 40 2>&1 | tail -15`

## v2-spec-architecture-r1  (condition `spec-architecture`, factor `specification`)

- termination: `round_timeout`, visible trajectory: [0.9369, 0.9369]
- regressions: 0, buildable snapshots: 2/2, final LOC: 2408
- tools: {'bash': 24, 'edit': 19, 'write': 9, 'read': 2, 'ls': 1}
- shell intent: {'build': 13, 'other': 5, 'self_test': 3, 'write_via_shell': 2, 'inspect': 1}
- affordances: test_visible=0 (offered), experiment_status=0 (offered), reference_oracle=0 (not offered)
- PROGRESS.md kept: False; self-authored test artifacts: none
- thinking 201,325 chars vs prose 1,514 chars; output tokens 98,174
- guard blocks: 0 ; compactions: 0; provider retries: 0
- hidden failure types: {'unexpected_reject': 9, 'wrong_behavior': 2, 'unexpected_accept': 1}
- **stalled** in round-000 on `bash`: `cd /workspace && cargo build --release --offline 2>&1 | grep -E "^error" ; cd /tmp/picctest && ./battery.sh \
  s2:251 s3:10 s3b:225 s4:3 s4b:5 s5:17 s6:18 s6b:`
- **stalled** in round-001 on `bash`: `mkdir -p /tmp/picctest/tests && cd /tmp/picctest
cat > stub.s <<'EOF'
	.globl	_start
_start:
	call	main
	movl	%eax, %edi
	movl	$60, %eax
	syscall
EOF
as -o stub`

## v2-spec-architecture-r2  (condition `spec-architecture`, factor `specification`)

- termination: `round_timeout`, visible trajectory: [0.8361, 0.9413]
- regressions: 0, buildable snapshots: 2/2, final LOC: 2904
- tools: {'bash': 141, 'edit': 32, 'write': 10, 'test_visible': 9, 'read': 6, 'grep': 4, 'ls': 1}
- shell intent: {'other': 45, 'write_via_shell': 43, 'self_test': 42, 'build': 7, 'inspect': 4}
- affordances: test_visible=9 (offered), experiment_status=0 (offered), reference_oracle=0 (not offered)
- PROGRESS.md kept: True; self-authored test artifacts: none
- thinking 427,368 chars vs prose 9,815 chars; output tokens 239,571
- guard blocks: 3 {'direct evaluator execution is prohibited; use the condition-controlled tools': 1, 'direct use of an existing C/C++ compiler is prohibited; use the experimental tools': 1, 'writes are restricted to /workspace': 1}; compactions: 6; provider retries: 0
- hidden failure types: {'unexpected_reject': 8, 'wrong_behavior': 2, 'unexpected_accept': 2}
- **stalled** in round-001 on `bash`: `cd /tmp/picc-dev && cat > difffuzz.py <<'PYEOF'
import random, subprocess, sys
sys.path.insert(0, '/tmp/picc-dev')
import oracle

def gen(seed):
    random.seed`

## v2-spec-architecture-r3  (condition `spec-architecture`, factor `specification`)

- termination: `round_timeout`, visible trajectory: [1.0, 1.0]
- regressions: 0, buildable snapshots: 2/2, final LOC: 3101
- tools: {'bash': 144, 'edit': 61, 'read': 16, 'test_visible': 15, 'write': 14, 'ls': 1, 'experiment_status': 1}
- shell intent: {'other': 60, 'build': 31, 'write_via_shell': 28, 'self_test': 23, 'inspect': 2}
- affordances: test_visible=15 (offered), experiment_status=1 (offered), reference_oracle=0 (not offered)
- PROGRESS.md kept: True; self-authored test artifacts: none
- thinking 438,443 chars vs prose 10,206 chars; output tokens 230,957
- guard blocks: 2 {'direct use of an existing C/C++ compiler is prohibited; use the experimental tools': 1, 'writes are restricted to /workspace': 1}; compactions: 4; provider retries: 0
- hidden failure types: {'unexpected_accept': 2}
- **stalled** in round-001 on `bash`: `cd /workspace && python3 dev/fuzz.py 500 1000 2>&1 | tail -20`

## v2-spec-brief-r1  (condition `spec-brief`, factor `specification`)

- termination: `visible_complete_after_review`, visible trajectory: [0.9548, 0.9548, 1.0, 1.0]
- regressions: 0, buildable snapshots: 4/4, final LOC: 2686
- tools: {'bash': 138, 'read': 42, 'edit': 32, 'test_visible': 16, 'write': 12, 'experiment_status': 2, 'ls': 1}
- shell intent: {'self_test': 71, 'other': 40, 'write_via_shell': 12, 'build': 9, 'inspect': 4, 'vcs': 2}
- affordances: test_visible=16 (offered), experiment_status=2 (offered), reference_oracle=0 (not offered)
- PROGRESS.md kept: True; self-authored test artifacts: none
- thinking 909,555 chars vs prose 35,972 chars; output tokens 361,987
- guard blocks: 6 {'writes are restricted to /workspace': 3, 'direct use of an existing C/C++ compiler is prohibited; use the experimental tools': 1, 'direct access to visible test files is withheld': 1, "reads are restricted by this condition's test/reference access policy": 1}; compactions: 8; provider retries: 0
- hidden failure types: {'unexpected_accept': 2}

## v2-spec-brief-r2  (condition `spec-brief`, factor `specification`)

- termination: `round_timeout`, visible trajectory: [0.931, 0.9429]
- regressions: 0, buildable snapshots: 2/2, final LOC: 2405
- tools: {'bash': 113, 'write': 79, 'edit': 45, 'read': 38, 'grep': 14, 'test_visible': 9, 'experiment_status': 3, 'ls': 1}
- shell intent: {'other': 46, 'self_test': 37, 'build': 22, 'write_via_shell': 7, 'inspect': 1}
- affordances: test_visible=9 (offered), experiment_status=3 (offered), reference_oracle=0 (not offered)
- PROGRESS.md kept: False; self-authored test artifacts: ['devtests']
- thinking 630,273 chars vs prose 9,755 chars; output tokens 279,477
- guard blocks: 10 {'direct use of an existing C/C++ compiler is prohibited; use the experimental tools': 8, 'credential/environment inspection is prohibited': 1, 'direct access to visible test files is withheld': 1}; compactions: 6; provider retries: 0
- hidden failure types: {'unexpected_reject': 8, 'unexpected_accept': 1}

## v2-spec-brief-r3  (condition `spec-brief`, factor `specification`)

- termination: `round_timeout`, visible trajectory: [0.9429, 0.9429]
- regressions: 0, buildable snapshots: 2/2, final LOC: 2823
- tools: {'bash': 199, 'edit': 42, 'read': 24, 'write': 6, 'ls': 1, 'find': 1}
- shell intent: {'self_test': 116, 'other': 46, 'build': 19, 'write_via_shell': 15, 'inspect': 3}
- affordances: test_visible=0 (offered), experiment_status=0 (offered), reference_oracle=0 (not offered)
- PROGRESS.md kept: False; self-authored test artifacts: none
- thinking 592,921 chars vs prose 15,997 chars; output tokens 297,752
- guard blocks: 6 {'direct use of an existing C/C++ compiler is prohibited; use the experimental tools': 5, "reads are restricted by this condition's test/reference access policy": 1}; compactions: 6; provider retries: 0
- hidden failure types: {'unexpected_reject': 9, 'unexpected_accept': 2}

## v2-spec-inline-r1  (condition `spec-inline`, factor `specification`)

- termination: `round_timeout`, visible trajectory: [0.8697, 0.9548]
- regressions: 0, buildable snapshots: 2/2, final LOC: 2346
- tools: {'bash': 178, 'edit': 48, 'write': 10, 'read': 3, 'ls': 1, 'grep': 1}
- shell intent: {'other': 112, 'self_test': 41, 'build': 23, 'write_via_shell': 2}
- affordances: test_visible=0 (offered), experiment_status=0 (offered), reference_oracle=0 (not offered)
- PROGRESS.md kept: False; self-authored test artifacts: none
- thinking 501,107 chars vs prose 9,695 chars; output tokens 253,515
- guard blocks: 2 {'direct use of an existing C/C++ compiler is prohibited; use the experimental tools': 1, 'writes are restricted to /workspace': 1}; compactions: 6; provider retries: 0
- hidden failure types: {'unexpected_reject': 8, 'unexpected_accept': 1}
- **stalled** in round-000 on `bash`: `cd /workspace && python3 - <<'EOF'
p = 'src/codegen.rs'
s = open(p).read()

old = "        RExpr::Bin(_, l, r) => rdepth(l).max(rdepth(r) + 1),"
new = "        `

## v2-spec-inline-r2  (condition `spec-inline`, factor `specification`)

- termination: `visible_complete_after_review`, visible trajectory: [0.0, 1.0, 1.0]
- regressions: 0, buildable snapshots: 2/3, final LOC: 3188
- tools: {'bash': 148, 'edit': 66, 'read': 39, 'test_visible': 17, 'write': 8, 'experiment_status': 2, 'ls': 1}
- shell intent: {'other': 54, 'write_via_shell': 46, 'build': 34, 'self_test': 12, 'inspect': 2}
- affordances: test_visible=17 (offered), experiment_status=2 (offered), reference_oracle=0 (not offered)
- PROGRESS.md kept: True; self-authored test artifacts: none
- thinking 779,765 chars vs prose 16,233 chars; output tokens 342,956
- guard blocks: 0 ; compactions: 6; provider retries: 0
- hidden failure types: {'unexpected_accept': 2}

## v2-spec-inline-r3  (condition `spec-inline`, factor `specification`)

- termination: `round_timeout`, visible trajectory: [0.9429, 1.0]
- regressions: 0, buildable snapshots: 2/2, final LOC: 3009
- tools: {'bash': 163, 'edit': 59, 'test_visible': 24, 'write': 21, 'read': 15, 'experiment_status': 3, 'ls': 2}
- shell intent: {'other': 77, 'self_test': 54, 'build': 20, 'write_via_shell': 8, 'inspect': 4}
- affordances: test_visible=24 (offered), experiment_status=3 (offered), reference_oracle=0 (not offered)
- PROGRESS.md kept: True; self-authored test artifacts: none
- thinking 573,758 chars vs prose 10,979 chars; output tokens 284,865
- guard blocks: 1 {'writes are restricted to /workspace': 1}; compactions: 6; provider retries: 0
- hidden failure types: {'unexpected_accept': 2}
- **stalled** in round-001 on `bash`: `cd /tmp && python3 - <<'EOF'
src = open('fuzz_loops.py').read()
src = src.replace("""def call_function(name, args, prog, env, steps):
    fn = prog['funcs'][nam`

## v3-baseline-r1  (condition `baseline`, factor `baseline`)

- termination: `round_timeout`, visible trajectory: [0.8705, 0.8705]
- regressions: 0, buildable snapshots: 2/2, final LOC: 2357
- tools: {'bash': 164, 'edit': 41, 'write': 7, 'test_visible': 2, 'read': 1, 'ls': 1}
- shell intent: {'self_test': 77, 'other': 45, 'inspect': 24, 'build': 14, 'write_via_shell': 4}
- affordances: test_visible=2 (offered), experiment_status=0 (offered), reference_oracle=0 (not offered)
- PROGRESS.md kept: False; self-authored test artifacts: ['runtest.sh', 'tests-local']
- thinking 367,187 chars vs prose 4,798 chars; output tokens 170,683
- guard blocks: 1 {'direct use of an existing C/C++ compiler is prohibited; use the experimental tools': 1}; compactions: 2; provider retries: 0
- hidden failure types: {'unexpected_reject': 10, 'unexpected_accept': 1, 'execution_timeout': 1}
- **stalled** in round-001 on `bash`: `cd /workspace/tests-local && sed -i 's|// EXPECT_EXIT 0|// EXPECT_EXIT 42|' t01_basics.c && sed -i 's/if (hex != 39) return 9;/if (hex != 49) return 9;/' t03_ar`

## v3-baseline-r2  (condition `baseline`, factor `baseline`)

- termination: `round_timeout`, visible trajectory: [0.931, 0.9548]
- regressions: 0, buildable snapshots: 2/2, final LOC: 3535
- tools: {'bash': 173, 'edit': 96, 'read': 45, 'test_visible': 18, 'write': 13, 'grep': 4, 'ls': 1}
- shell intent: {'other': 80, 'build': 35, 'self_test': 32, 'write_via_shell': 23, 'inspect': 3}
- affordances: test_visible=18 (offered), experiment_status=0 (offered), reference_oracle=0 (not offered)
- PROGRESS.md kept: False; self-authored test artifacts: none
- thinking 643,920 chars vs prose 12,144 chars; output tokens 299,741
- guard blocks: 4 {'writes are restricted to /workspace': 2, 'direct access to visible test files is withheld': 1, 'direct use of an existing C/C++ compiler is prohibited; use the experimental tools': 1}; compactions: 6; provider retries: 0
- hidden failure types: {'unexpected_accept': 6, 'wrong_behavior': 2, 'unexpected_reject': 1}

## v3-baseline-r3  (condition `baseline`, factor `baseline`)

- termination: `round_timeout`, visible trajectory: [0.8618, 0.8618]
- regressions: 0, buildable snapshots: 2/2, final LOC: 2272
- tools: {'bash': 110, 'edit': 27, 'read': 16, 'write': 12, 'ls': 2, 'test_visible': 2}
- shell intent: {'other': 53, 'self_test': 25, 'build': 16, 'write_via_shell': 7, 'vcs': 7, 'inspect': 2}
- affordances: test_visible=2 (offered), experiment_status=0 (offered), reference_oracle=0 (not offered)
- PROGRESS.md kept: True; self-authored test artifacts: none
- thinking 423,067 chars vs prose 8,279 chars; output tokens 188,510
- guard blocks: 1 {'direct use of an existing C/C++ compiler is prohibited; use the experimental tools': 1}; compactions: 4; provider retries: 0
- hidden failure types: {'unexpected_reject': 10, 'unexpected_accept': 2}
- **stalled** in round-001 on `bash`: `cd /tmp/piccdv && cat > al.s <<'EOF'
	.globl _start
	.type _start, @function
_start:
	movq	%rsp, %rax
	andl	$15, %eax
	movl	$1, %edi
	movq	$0, %rsi
	movl	$1, %e`

## v3-tests-none-r1  (condition `tests-none`, factor `tests`)

- termination: `wall_time_budget`, visible trajectory: [0.8578, 0.8686, 0.8686, 0.8686]
- regressions: 0, buildable snapshots: 4/4, final LOC: 2378
- tools: {'bash': 380, 'edit': 86, 'read': 16, 'write': 16, 'experiment_status': 2, 'ls': 1}
- shell intent: {'self_test': 182, 'other': 177, 'build': 16, 'write_via_shell': 4, 'vcs': 1}
- affordances: test_visible=0 (not offered), experiment_status=2 (offered), reference_oracle=0 (not offered)
- PROGRESS.md kept: True; self-authored test artifacts: ['tests']
- thinking 767,870 chars vs prose 29,011 chars; output tokens 381,928
- guard blocks: 0 ; compactions: 10; provider retries: 0
- hidden failure types: {'unexpected_reject': 10, 'unexpected_accept': 2}

## v3-tests-none-r2  (condition `tests-none`, factor `tests`)

- termination: `round_timeout`, visible trajectory: [0.7839, 0.7839]
- regressions: 0, buildable snapshots: 2/2, final LOC: 2703
- tools: {'bash': 14, 'write': 10, 'edit': 9, 'read': 2, 'ls': 1}
- shell intent: {'build': 6, 'self_test': 3, 'inspect': 2, 'vcs': 1, 'write_via_shell': 1, 'other': 1}
- affordances: test_visible=0 (not offered), experiment_status=0 (offered), reference_oracle=0 (not offered)
- PROGRESS.md kept: False; self-authored test artifacts: ['tests']
- thinking 224,964 chars vs prose 909 chars; output tokens 102,080
- guard blocks: 1 {'direct use of an existing C/C++ compiler is prohibited; use the experimental tools': 1}; compactions: 0; provider retries: 0
- hidden failure types: {'unexpected_reject': 8, 'wrong_behavior': 2, 'unexpected_accept': 2}
- **stalled** in round-000 on `bash`: `cd /workspace && cargo build --release --offline 2>/dev/null; ./tests/run.sh 2>&1 | grep -v "^ok" ; echo; ./tests/run.sh 2>&1 | tail -2`
- **stalled** in round-001 on `bash`: `cd /workspace && cargo build --release --offline 2>&1 | grep -E "^error" | head; echo "BUILD: ${PIPESTATUS[0]}"; ./tests/run.sh 2>&1 | tail -25`

## v3-tests-none-r3  (condition `tests-none`, factor `tests`)

- termination: `round_timeout`, visible trajectory: [0.7271, 0.7271]
- regressions: 0, buildable snapshots: 2/2, final LOC: 1748
- tools: {'bash': 21, 'edit': 19, 'write': 10, 'read': 1, 'ls': 1}
- shell intent: {'self_test': 11, 'build': 5, 'write_via_shell': 3, 'other': 2}
- affordances: test_visible=0 (not offered), experiment_status=0 (offered), reference_oracle=0 (not offered)
- PROGRESS.md kept: False; self-authored test artifacts: ['run_tests.sh', 'tests']
- thinking 242,101 chars vs prose 2,015 chars; output tokens 103,613
- guard blocks: 0 ; compactions: 0; provider retries: 0
- hidden failure types: {'unexpected_reject': 6, 'wrong_behavior': 5, 'unexpected_accept': 1}
- **stalled** in round-000 on `bash`: `cd /workspace && cargo build --release --offline 2>&1 | grep -E '^error'; ./run_tests.sh 2>&1 | grep -E '^(FAIL|pass=)'`
- **stalled** in round-001 on `bash`: `cd /workspace && ./run_tests.sh 2>&1 | grep -E '^(FAIL|pass=)'`

## v4-js-untyped-r1  (condition `js-untyped`, factor `baseline`)

- termination: `round_timeout`, visible trajectory: [0.893, 0.893]
- regressions: 0, buildable snapshots: 2/2, final LOC: 1423
- tools: {'bash': 149, 'test_visible': 138, 'edit': 47, 'read': 24, 'write': 6, 'grep': 3, 'ls': 1, 'experiment_status': 1}
- shell intent: {'other': 61, 'write_via_shell': 59, 'self_test': 13, 'build': 10, 'inspect': 6}
- affordances: test_visible=138 (offered), experiment_status=1 (offered), reference_oracle=0 (not offered)
- PROGRESS.md kept: True; self-authored test artifacts: none
- thinking 637,711 chars vs prose 17,841 chars; output tokens 276,545
- guard blocks: 4 {'direct use of an existing C/C++ compiler is prohibited; use the experimental tools': 2, 'direct access to visible test files is withheld': 1, "reads are restricted by this condition's test/reference access policy": 1}; compactions: 6; provider retries: 0
- hidden failure types: {'unexpected_reject': 10, 'unexpected_accept': 2}
- **stalled** in round-000 on `bash`: `cd /tmp/piccdev && cat > fuzz1.js <<'EOF'
const { execFileSync } = require('child_process');
const fs = require('fs');
let seed = 12345;
function rnd(n) { seed `

## v4-js-untyped-r2  (condition `js-untyped`, factor `baseline`)

- termination: `round_timeout`, visible trajectory: [0.8641, 0.8641]
- regressions: 0, buildable snapshots: 2/2, final LOC: 1678
- tools: {'bash': 78, 'edit': 28, 'write': 13, 'read': 4, 'ls': 3, 'experiment_status': 1}
- shell intent: {'other': 45, 'write_via_shell': 18, 'self_test': 10, 'inspect': 3, 'build': 2}
- affordances: test_visible=0 (offered), experiment_status=1 (offered), reference_oracle=0 (not offered)
- PROGRESS.md kept: False; self-authored test artifacts: none
- thinking 268,582 chars vs prose 6,528 chars; output tokens 140,068
- guard blocks: 2 {'direct access to visible test files is withheld': 1, 'direct use of an existing C/C++ compiler is prohibited; use the experimental tools': 1}; compactions: 2; provider retries: 0
- hidden failure types: {'unexpected_reject': 10, 'unexpected_accept': 2}
- **stalled** in round-000 on `bash`: `cd /workspace/scratch
cat > s12_flow.c <<'EOF'
int main(void) {
  int s = 0;
  int i;
  for (i = 0; i < 10; i++) {
    if (i == 3) break;
    if (i % 2) continu`
- **stalled** in round-001 on `bash`: `cd /workspace/scratch && ./run.sh s12_flow 0 && node -e "
const {interpret}=require('./interp.js');
const fs=require('fs');
const w=interpret(fs.readFileSync('s`

## v4-js-untyped-r3  (condition `js-untyped`, factor `baseline`)

- termination: `round_timeout`, visible trajectory: [0.8736, 0.8736]
- regressions: 0, buildable snapshots: 2/2, final LOC: 1274
- tools: {'bash': 132, 'edit': 21, 'write': 6, 'test_visible': 6, 'read': 4, 'ls': 1, 'experiment_status': 1}
- shell intent: {'other': 78, 'self_test': 42, 'write_via_shell': 9, 'inspect': 2, 'build': 1}
- affordances: test_visible=6 (offered), experiment_status=1 (offered), reference_oracle=0 (not offered)
- PROGRESS.md kept: True; self-authored test artifacts: none
- thinking 437,579 chars vs prose 10,173 chars; output tokens 221,091
- guard blocks: 4 {"reads are restricted by this condition's test/reference access policy": 2, 'direct evaluator execution is prohibited; use the condition-controlled tools': 1, 'writes are restricted to /workspace': 1}; compactions: 4; provider retries: 0
- hidden failure types: {'unexpected_reject': 10, 'unexpected_accept': 2}
- **stalled** in round-001 on `bash`: `cd /tmp/picc-t && python3 - <<'PYEOF'
s = open('df3.py').read()
old = """        if o == '+': return wrap(a + b)
        if o == '-': return wrap(a - b)
       `

## v4-pilot-js-untyped-smoke1  (condition `js-untyped`, factor `baseline`)

- termination: `round_timeout`, visible trajectory: [0.5, 0.9848]
- regressions: 0, buildable snapshots: 2/2, final LOC: 1503
- tools: {'bash': 15, 'write': 6, 'test_visible': 4, 'edit': 4, 'read': 2, 'ls': 1}
- shell intent: {'other': 8, 'build': 3, 'self_test': 2, 'inspect': 1, 'write_via_shell': 1}
- affordances: test_visible=4 (offered), experiment_status=0 (offered), reference_oracle=0 (not offered)
- PROGRESS.md kept: False; self-authored test artifacts: none
- thinking 147,112 chars vs prose 2,636 chars; output tokens 90,195
- guard blocks: 2 {'direct use of an existing C/C++ compiler is prohibited; use the experimental tools': 1, 'writes are restricted to /workspace': 1}; compactions: 0; provider retries: 0
- hidden failure types: none

## v4-pilot-ts-strict-smoke1  (condition `ts-strict`, factor `candidate`)

- termination: `round_timeout`, visible trajectory: [0.0, 0.9242]
- regressions: 0, buildable snapshots: 1/2, final LOC: 1705
- tools: {'bash': 53, 'edit': 16, 'write': 8, 'read': 5, 'ls': 1, 'experiment_status': 1}
- shell intent: {'other': 23, 'write_via_shell': 13, 'self_test': 9, 'build': 7, 'inspect': 1}
- affordances: test_visible=0 (offered), experiment_status=1 (offered), reference_oracle=0 (not offered)
- PROGRESS.md kept: True; self-authored test artifacts: ['tests']
- thinking 179,626 chars vs prose 2,445 chars; output tokens 87,499
- guard blocks: 0 ; compactions: 0; provider retries: 0
- hidden failure types: {'wrong_behavior': 1}

## v4-ts-strict-r1  (condition `ts-strict`, factor `candidate`)

- termination: `round_timeout`, visible trajectory: [0.8276, 0.8602]
- regressions: 0, buildable snapshots: 2/2, final LOC: 2096
- tools: {'bash': 180, 'edit': 39, 'read': 21, 'write': 16, 'test_visible': 3, 'ls': 1, 'experiment_status': 1}
- shell intent: {'self_test': 94, 'other': 65, 'write_via_shell': 16, 'build': 4, 'inspect': 1}
- affordances: test_visible=3 (offered), experiment_status=1 (offered), reference_oracle=0 (not offered)
- PROGRESS.md kept: True; self-authored test artifacts: none
- thinking 611,687 chars vs prose 13,626 chars; output tokens 297,427
- guard blocks: 0 ; compactions: 6; provider retries: 0
- hidden failure types: {'unexpected_reject': 10, 'unexpected_accept': 2}

## v4-ts-strict-r2  (condition `ts-strict`, factor `candidate`)

- termination: `round_timeout`, visible trajectory: [0.8709, 0.8709]
- regressions: 0, buildable snapshots: 2/2, final LOC: 2113
- tools: {'bash': 149, 'edit': 72, 'read': 24, 'write': 14, 'test_visible': 8, 'experiment_status': 3, 'ls': 1}
- shell intent: {'other': 70, 'self_test': 67, 'write_via_shell': 6, 'build': 5, 'inspect': 1}
- affordances: test_visible=8 (offered), experiment_status=3 (offered), reference_oracle=0 (not offered)
- PROGRESS.md kept: True; self-authored test artifacts: none
- thinking 698,740 chars vs prose 14,060 chars; output tokens 301,658
- guard blocks: 1 {'direct use of an existing C/C++ compiler is prohibited; use the experimental tools': 1}; compactions: 6; provider retries: 0
- hidden failure types: {'unexpected_reject': 10, 'unexpected_accept': 2}

## v4-ts-strict-r3  (condition `ts-strict`, factor `candidate`)

- termination: `round_timeout`, visible trajectory: [0.9333, 0.9202]
- regressions: 1, buildable snapshots: 2/2, final LOC: 1514
- tools: {'bash': 125, 'edit': 21, 'write': 8, 'test_visible': 7, 'read': 5, 'ls': 1}
- shell intent: {'other': 59, 'self_test': 45, 'write_via_shell': 15, 'build': 4, 'inspect': 2}
- affordances: test_visible=7 (offered), experiment_status=0 (offered), reference_oracle=0 (not offered)
- PROGRESS.md kept: True; self-authored test artifacts: none
- thinking 417,548 chars vs prose 9,361 chars; output tokens 185,333
- guard blocks: 1 {'direct use of an existing C/C++ compiler is prohibited; use the experimental tools': 1}; compactions: 4; provider retries: 0
- hidden failure types: {'unexpected_reject': 7, 'unexpected_accept': 2, 'assembly_or_link_failure': 1}
- **stalled** in round-001 on `bash`: `cd /workspace && tsc --strict --noEmitOnError --target es2022 --lib es2022 --module commonjs --esModuleInterop --skipLibCheck --types node --typeRoots /usr/loca`

## v5-baseline-r1  (condition `baseline`, factor `baseline`)

- termination: `round_timeout`, visible trajectory: [0.9369, 0.983]
- regressions: 0, buildable snapshots: 2/2, final LOC: 2227
- tools: {'bash': 224, 'edit': 67, 'test_visible': 27, 'read': 20, 'write': 9, 'experiment_status': 3, 'ls': 1}
- shell intent: {'other': 98, 'build': 44, 'write_via_shell': 40, 'self_test': 29, 'inspect': 13}
- affordances: test_visible=27 (offered), experiment_status=3 (offered), reference_oracle=0 (not offered)
- PROGRESS.md kept: True; self-authored test artifacts: ['.tests']
- thinking 721,019 chars vs prose 11,858 chars; output tokens 304,924
- guard blocks: 3 {'writes are restricted to /workspace': 2, 'direct use of an existing C/C++ compiler is prohibited; use the experimental tools': 1}; compactions: 6; provider retries: 0
- hidden failure types: {'unexpected_accept': 3, 'unexpected_reject': 1, 'wrong_behavior': 1}

## v5-baseline-r2  (condition `baseline`, factor `baseline`)

- termination: `round_timeout`, visible trajectory: [0.9235, 0.9618]
- regressions: 0, buildable snapshots: 2/2, final LOC: 3301
- tools: {'bash': 185, 'edit': 91, 'read': 32, 'write': 21, 'test_visible': 17, 'ls': 1}
- shell intent: {'other': 87, 'self_test': 66, 'build': 24, 'write_via_shell': 6, 'inspect': 2}
- affordances: test_visible=17 (offered), experiment_status=0 (offered), reference_oracle=0 (not offered)
- PROGRESS.md kept: False; self-authored test artifacts: ['tests']
- thinking 632,536 chars vs prose 10,324 chars; output tokens 303,024
- guard blocks: 2 {'writes are restricted to /workspace': 1, 'direct use of an existing C/C++ compiler is prohibited; use the experimental tools': 1}; compactions: 6; provider retries: 0
- hidden failure types: {'unexpected_accept': 3, 'unexpected_reject': 1, 'wrong_behavior': 1}

## v5-baseline-r3  (condition `baseline`, factor `baseline`)

- termination: `round_timeout`, visible trajectory: [0.7863, 0.7863]
- regressions: 0, buildable snapshots: 2/2, final LOC: 2203
- tools: {'bash': 111, 'write': 15, 'edit': 9, 'read': 1, 'ls': 1, 'experiment_status': 1}
- shell intent: {'other': 62, 'self_test': 26, 'write_via_shell': 15, 'build': 5, 'inspect': 2, 'vcs': 1}
- affordances: test_visible=0 (offered), experiment_status=1 (offered), reference_oracle=0 (not offered)
- PROGRESS.md kept: False; self-authored test artifacts: none
- thinking 302,367 chars vs prose 4,698 chars; output tokens 163,871
- guard blocks: 3 {'writes are restricted to /workspace': 2, 'direct use of an existing C/C++ compiler is prohibited; use the experimental tools': 1}; compactions: 2; provider retries: 0
- hidden failure types: {'assembly_or_link_failure': 10, 'unexpected_accept': 2}
- **stalled** in round-001 on `bash`: `cd /workspace/.dev && python3 - <<'PY'
s = open('crtW.s').read()
# make main spin ~200ms by counting
old = '	leaq main(%rip), %rdi\n	call main'
# we want a spin`

## v5-baseline-r4  (condition `baseline`, factor `baseline`)

- termination: `round_timeout`, visible trajectory: [0.5898, 0.5898]
- regressions: 0, buildable snapshots: 2/2, final LOC: 2249
- tools: {'bash': 15, 'edit': 14, 'write': 8, 'read': 1, 'ls': 1}
- shell intent: {'self_test': 6, 'build': 5, 'other': 3, 'inspect': 1}
- affordances: test_visible=0 (offered), experiment_status=0 (offered), reference_oracle=0 (not offered)
- PROGRESS.md kept: False; self-authored test artifacts: none
- thinking 100,865 chars vs prose 1,322 chars; output tokens 60,414
- guard blocks: 0 ; compactions: 0; provider retries: 0
- hidden failure types: {'wrong_behavior': 12}
- **stalled** in round-000 on `bash`: `cd /workspace && cargo build --release --offline 2>&1 | grep -E "^error" | head; cd /tmp/picctest && for t in t1 t2 t3 t4; do
  /workspace/target/release/picc $`
- **stalled** in round-001 on `bash`: `mkdir -p /tmp/picctest && cd /tmp/picctest
cat > t1.c <<'EOF'
int main(void) {
    return 42;
}
EOF
cat > t2.c <<'EOF'
int main(void) {
    int x = 3;
    int y`

## v5-pilot-baseline-smoke1  (condition `baseline`, factor `baseline`)

- termination: `round_timeout`, visible trajectory: [0.0, 0.9848]
- regressions: 0, buildable snapshots: 1/2, final LOC: 1688
- tools: {'bash': 39, 'edit': 8, 'write': 7, 'read': 1, 'ls': 1}
- shell intent: {'self_test': 20, 'build': 8, 'write_via_shell': 7, 'other': 4}
- affordances: test_visible=0 (offered), experiment_status=0 (offered), reference_oracle=0 (not offered)
- PROGRESS.md kept: False; self-authored test artifacts: none
- thinking 204,429 chars vs prose 3,238 chars; output tokens 91,834
- guard blocks: 0 ; compactions: 0; provider retries: 0
- hidden failure types: none

## v5-pilot-tests-none-smoke1  (condition `tests-none`, factor `tests`)

- termination: `round_timeout`, visible trajectory: [0.0, 0.0]
- regressions: 0, buildable snapshots: 0/2, final LOC: 276
- tools: {'bash': 4, 'write': 4, 'read': 2, 'ls': 1}
- shell intent: {'inspect': 3, 'build': 1}
- affordances: test_visible=0 (not offered), experiment_status=0 (offered), reference_oracle=0 (not offered)
- PROGRESS.md kept: False; self-authored test artifacts: none
- thinking 117,460 chars vs prose 512 chars; output tokens 43,706
- guard blocks: 0 ; compactions: 0; provider retries: 0
- hidden failure types: {'build_failure': 12}

## v5-tests-none-r1  (condition `tests-none`, factor `tests`)

- termination: `round_timeout`, visible trajectory: [0.9149, 0.9251]
- regressions: 0, buildable snapshots: 2/2, final LOC: 2549
- tools: {'bash': 101, 'edit': 34, 'write': 15, 'read': 10, 'ls': 1, 'experiment_status': 1}
- shell intent: {'self_test': 35, 'other': 27, 'write_via_shell': 22, 'build': 15, 'inspect': 1, 'vcs': 1}
- affordances: test_visible=0 (not offered), experiment_status=1 (offered), reference_oracle=0 (not offered)
- PROGRESS.md kept: True; self-authored test artifacts: ['tests']
- thinking 310,311 chars vs prose 7,221 chars; output tokens 190,333
- guard blocks: 0 ; compactions: 4; provider retries: 0
- hidden failure types: {'unexpected_accept': 5, 'unexpected_reject': 4, 'execution_timeout': 1}
- **stalled** in round-001 on `bash`: `cd /workspace && python3 - <<'PYEOF'
src = open('tests/cases.py').read()
src = src.replace('s = s + j; } i = i + 1; } return s; }", "ok", 6),',
                `

## v5-tests-none-r2  (condition `tests-none`, factor `tests`)

- termination: `round_timeout`, visible trajectory: [0.941, 0.9445]
- regressions: 0, buildable snapshots: 2/2, final LOC: 2526
- tools: {'bash': 106, 'edit': 35, 'read': 19, 'write': 14, 'ls': 1, 'experiment_status': 1}
- shell intent: {'self_test': 46, 'other': 36, 'build': 21, 'write_via_shell': 2, 'inspect': 1}
- affordances: test_visible=0 (not offered), experiment_status=1 (offered), reference_oracle=0 (not offered)
- PROGRESS.md kept: True; self-authored test artifacts: ['tests']
- thinking 401,406 chars vs prose 7,862 chars; output tokens 208,792
- guard blocks: 0 ; compactions: 4; provider retries: 0
- hidden failure types: {'unexpected_accept': 2, 'unexpected_reject': 1}
- **stalled** in round-001 on `bash`: `cd /workspace/tests && cat > e50_funshadow.c <<'EOF'
int f(void) { return 3; }
int main(void) {
    int f = 5;
    return f;
}
EOF
cat > e51_forredecl.c <<'EOF'`

## v5-tests-none-r3  (condition `tests-none`, factor `tests`)

- termination: `round_timeout`, visible trajectory: [0.5152, 0.5152]
- regressions: 0, buildable snapshots: 2/2, final LOC: 2053
- tools: {'bash': 46, 'edit': 16, 'write': 8, 'read': 3, 'ls': 1, 'experiment_status': 1}
- shell intent: {'inspect': 21, 'self_test': 12, 'build': 6, 'other': 6, 'write_via_shell': 1}
- affordances: test_visible=0 (not offered), experiment_status=1 (offered), reference_oracle=0 (not offered)
- PROGRESS.md kept: False; self-authored test artifacts: ['tests']
- thinking 190,739 chars vs prose 2,725 chars; output tokens 92,967
- guard blocks: 1 {'direct use of an existing C/C++ compiler is prohibited; use the experimental tools': 1}; compactions: 2; provider retries: 0
- hidden failure types: {'wrong_behavior': 12}
- **stalled** in round-000 on `bash`: `cat > /tmp/trace.py <<'EOF'
import ctypes, os, struct, sys

libc = ctypes.CDLL(None, use_errno=True)
PTRACE_TRACEME=0; PTRACE_PEEKTEXT=1; PTRACE_PEEKDATA=2; PTR`
- **stalled** in round-001 on `bash`: `mkdir -p /tmp/t && cat > /tmp/t/m.c <<'EOF'
int main(void) { return 42; }
EOF
cat > /tmp/dbg.sh <<'EOF'
#!/bin/bash
cd /tmp/t
/workspace/target/release/picc m.c`

## v5-tests-none-r4  (condition `tests-none`, factor `tests`)

- termination: `round_timeout`, visible trajectory: [0.9287, 0.9322]
- regressions: 0, buildable snapshots: 2/2, final LOC: 2484
- tools: {'bash': 225, 'edit': 49, 'read': 23, 'write': 16, 'ls': 1, 'grep': 1}
- shell intent: {'self_test': 161, 'inspect': 25, 'other': 22, 'build': 9, 'write_via_shell': 7, 'vcs': 1}
- affordances: test_visible=0 (not offered), experiment_status=0 (offered), reference_oracle=0 (not offered)
- PROGRESS.md kept: True; self-authored test artifacts: ['test']
- thinking 621,115 chars vs prose 11,302 chars; output tokens 299,760
- guard blocks: 2 {'direct evaluator execution is prohibited; use the condition-controlled tools': 1, 'direct use of an existing C/C++ compiler is prohibited; use the experimental tools': 1}; compactions: 6; provider retries: 0
- hidden failure types: {'unexpected_accept': 4, 'unexpected_reject': 4}

