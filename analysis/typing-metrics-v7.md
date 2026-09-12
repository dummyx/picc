# Typing treatment fidelity (picc-types-v1)

Regex-based, descriptive counts over each run's final workspace and event streams. They document whether the treatment was delivered and how each arm used its toolchain; they are not an outcome measure.

## Per run

| Run | Condition | Hidden final | Last buildable | Build outcomes (hidden) | LOC | tsc calls | node --check | compiler runs | guard tsc blocks | Typing signals | Audit findings |
|---|---|---:|---:|---|---:|---:|---:|---:|---:|---|---|
| `v7-js-untyped-r1` | `js-untyped` | 0.9579 | 0.9579 | ok=2 | 1679 | 0 | 11 | 46 | 0 | jsdoc types=0 (param=0, type=0, returns=0), @ts-check=0, fns=11, classes=2 | none |
| `v7-js-untyped-r2` | `js-untyped` | 0.9542 | 0.9542 | ok=2 | 1228 | 0 | 21 | 40 | 0 | jsdoc types=0 (param=0, type=0, returns=0), @ts-check=0, fns=9, classes=3 | none |
| `v7-js-untyped-r3` | `js-untyped` | 0.5000 | 0.5000 | ok=2 | 1283 | 0 | 21 | 67 | 0 | jsdoc types=0 (param=0, type=0, returns=0), @ts-check=0, fns=22, classes=1 | none |
| `v7-js-untyped-r4` | `js-untyped` | 0.9679 | 0.9679 | ok=2 | 2398 | 0 | 28 | 44 | 0 | jsdoc types=0 (param=0, type=0, returns=0), @ts-check=0, fns=55, classes=5 | none |
| `v7-ts-strict-r1` | `ts-strict` | 0.9667 | 0.9667 | ok=2 | 2013 | 27 | 0 | 69 | 0 | any=0, unknown=0, as=2, non-null=0, interfaces=31, type aliases=8, fn return types=8/9, param annotation share=1.0, suppressions=0 | none |
| `v7-ts-strict-r2` | `ts-strict` | 0.0000 | 0.9167 | ok=1, type_error=1 | 2224 | 22 | 0 | 31 | 0 | any=0, unknown=0, as=2, non-null=0, interfaces=11, type aliases=6, fn return types=28/29, param annotation share=1.0, suppressions=0, stray .js=5 | none |
| `v7-ts-strict-r3` | `ts-strict` | 0.9653 | 0.9653 | ok=2 | 2082 | 21 | 0 | 33 | 0 | any=0, unknown=2, as=3, non-null=0, interfaces=30, type aliases=5, fn return types=6/6, param annotation share=0.941, suppressions=0 | none |
| `v7-ts-strict-r4` | `ts-strict` | 0.9667 | 0.9667 | ok=3 | 2015 | 26 | 0 | 30 | 0 | any=0, unknown=0, as=3, non-null=0, interfaces=12, type aliases=6, fn return types=19/19, param annotation share=0.98, suppressions=0, stray .js=1 | none |

## Per condition (main profile only)

| Condition | n | Median hidden final | Median last buildable | Median LOC | Median tsc calls | Runs with any unbuildable hidden snapshot | Median guard tsc blocks |
|---|---:|---:|---:|---:|---:|---:|---:|
| `js-untyped` | 4 | 0.9561 | 0.9561 | 1481.0 | 0.0 | 0 | 0.0 |
| `ts-strict` | 4 | 0.966 | 0.966 | 2048.5 | 24.0 | 1 | 0.0 |
