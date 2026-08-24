# PiCC process metrics

Descriptive only: one run per condition, and run length was set by when the agent hung or was killed rather than by the condition, so cross-condition differences are not yet attributable to the treatments.

## By condition

Output cap `65536` — 9 run(s)

| Condition | n | Scores (audit-passing) | Median | Spread | Audit pass | Declined tool |
|---|---:|---|---:|---:|---:|---:|
| `baseline` | 3 | 0.819, 0.771, 0.877 | 0.8194 | 0.106 | 3/3 | 2/3 |
| `prompt-minimal` | 1 | — | — | — | 0/1 | 1/1 |
| `spec-architecture` | 3 | 0.898, 0.877, 0.000 | 0.8773 | 0.898 | 3/3 | 1/3 |
| `spec-brief` | 1 | 0.898 | 0.8981 | — | 1/1 | 0/1 |
| `spec-inline` | 1 | 0.863 | 0.8634 | — | 1/1 | 0/1 |

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
- regressions: 0, buildable snapshots: 1/4, final LOC: 0
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

