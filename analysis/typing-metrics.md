# Typing treatment fidelity (picc-types-v1)

Regex-based, descriptive counts over each run's final workspace and event streams. They document whether the treatment was delivered and how each arm used its toolchain; they are not an outcome measure.

## Per run

| Run | Condition | Hidden final | Last buildable | Build outcomes (hidden) | LOC | tsc calls | node --check | compiler runs | guard tsc blocks | Typing signals | Audit findings |
|---|---|---:|---:|---|---:|---:|---:|---:|---:|---|---|
| `v4-js-untyped-r1` | `js-untyped` | 0.8833 | 0.8833 | ok=2 | 1423 | 0 | 11 | 13 | 0 | jsdoc types=0 (param=0, type=0, returns=0), @ts-check=0, fns=28, classes=2 | none |
| `v4-pilot-js-untyped-smoke1` | `js-untyped` | 1.0000 | 1.0000 | ok=2 | 1503 | 0 | 3 | 1 | 0 | jsdoc types=0 (param=0, type=0, returns=0), @ts-check=0, fns=71, classes=1 | none |
| `v4-js-untyped-r2` | `js-untyped` | 0.8389 | 0.8389 | ok=2 | 1678 | 0 | 2 | 10 | 0 | jsdoc types=0 (param=0, type=0, returns=0), @ts-check=0, fns=37, classes=4 | none |
| `v4-js-untyped-r3` | `js-untyped` | 0.8278 | 0.8278 | ok=2 | 1274 | 0 | 12 | 38 | 0 | jsdoc types=0 (param=0, type=0, returns=0), @ts-check=0, fns=9, classes=6 | none |
| `v4-pilot-ts-strict-smoke1` | `ts-strict` | 0.9583 | 0.9583 | missing_entry=1, ok=1 | 1705 | 7 | 0 | 2 | 0 | any=0, unknown=0, as=4, non-null=0, interfaces=10, type aliases=9, fn return types=14/14, param annotation share=1.0, suppressions=0 | none |
| `v4-ts-strict-r1` | `ts-strict` | 0.8389 | 0.8389 | ok=2 | 2096 | 19 | 0 | 53 | 0 | any=0, unknown=0, as=2, non-null=0, interfaces=28, type aliases=9, fn return types=15/16, param annotation share=1.0, suppressions=0 | none |
| `v4-ts-strict-r2` | `ts-strict` | 0.8653 | 0.8653 | ok=2 | 2113 | 24 | 0 | 67 | 0 | any=5, unknown=0, as=6, non-null=1, interfaces=12, type aliases=10, fn return types=38/38, param annotation share=1.0, suppressions=0 | none |
| `v4-ts-strict-r3` | `ts-strict` | 0.8986 | 0.8986 | ok=2 | 1514 | 14 | 0 | 36 | 0 | any=0, unknown=0, as=4, non-null=0, interfaces=5, type aliases=9, fn return types=8/8, param annotation share=1.0, suppressions=0 | none |

## Per condition (main profile only)

| Condition | n | Median hidden final | Median last buildable | Median LOC | Median tsc calls | Runs with any unbuildable hidden snapshot | Median guard tsc blocks |
|---|---:|---:|---:|---:|---:|---:|---:|
| `js-untyped` | 3 | 0.8389 | 0.8389 | 1423 | 0 | 0 | 0 |
| `ts-strict` | 3 | 0.8653 | 0.8653 | 2096 | 19 | 0 | 0 |
