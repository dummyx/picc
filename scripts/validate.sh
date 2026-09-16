#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

python3 -m py_compile scripts/*.py evaluator/evaluate.py studies/runtime/evaluate.py studies/runtime/candidate_runtime.py studies/runtime/sql/evaluate.py studies/runtime/sql/sqllogictest.py fixtures/mock-pisql-*/pisql.py
python3 -m unittest discover -s tests -p 'test_*.py' -v
for script in scripts/*.sh; do
  bash -n "$script"
done
python3 -m json.tool pi/settings.json >/dev/null
if command -v node >/dev/null 2>&1 && node -e 'require.resolve("typescript")' >/dev/null 2>&1; then
  node scripts/check_typescript.js
else
  echo "TypeScript syntax check skipped locally (Node + TypeScript not found); make auth-check validates runtime extension loading in the pinned image."
fi

rm -rf data/smoke-partitions data/smoke-partitions-repeat
python3 scripts/split_tests.py \
  --source fixtures/smoke \
  --output data/smoke-partitions \
  --seed 20260810 \
  --visible-fraction 0.70 \
  --max-stage 3 \
  --source-revision local-smoke >/dev/null
python3 scripts/split_tests.py \
  --source fixtures/smoke \
  --output data/smoke-partitions-repeat \
  --seed 20260810 \
  --visible-fraction 0.70 \
  --max-stage 3 \
  --source-revision local-smoke >/dev/null

python3 - <<'PY'
import json
from pathlib import Path

root = Path("data/smoke-partitions")
repeat = Path("data/smoke-partitions-repeat")
manifests = {}
for partition in ("visible", "hidden"):
    path = root / partition / "manifest.json"
    repeated = repeat / partition / "manifest.json"
    data = json.loads(path.read_text())
    assert data["tests"], f"empty {partition} smoke partition"
    assert path.read_bytes() == repeated.read_bytes(), f"nondeterministic {partition} manifest"
    manifests[partition] = data

visible_ids = {row["id"] for row in manifests["visible"]["tests"]}
hidden_ids = {row["id"] for row in manifests["hidden"]["tests"]}
assert visible_ids.isdisjoint(hidden_ids), "visible/hidden test leakage"

visible_families = {row["family"] for row in manifests["visible"]["tests"]}
hidden_families = {row["family"] for row in manifests["hidden"]["tests"]}
assert visible_families.isdisjoint(hidden_families), "family-group leakage"

combined = manifests["visible"]["tests"] + manifests["hidden"]["tests"]
for row in combined:
    test_path = root / ("visible" if row["id"] in visible_ids else "hidden") / row["relative_path"]
    assert test_path.read_bytes() == (Path("fixtures/smoke/tests") / row["relative_path"]).read_bytes()

print("Python, shell, JSON, TypeScript syntax, deterministic split, and leakage checks passed.")
PY
rm -rf data/smoke-partitions-repeat

# Chapters 1-18 task: the fixtures scope must split the smoke corpus
# deterministically and record every evaluator-side fixture.
rm -rf data/smoke-partitions-c18 data/smoke-partitions-c18-repeat
for out in data/smoke-partitions-c18 data/smoke-partitions-c18-repeat; do
  python3 scripts/split_tests.py \
    --source fixtures/smoke-c18 \
    --output "$out" \
    --seed 20260916 \
    --visible-fraction 0.70 \
    --max-stage 18 \
    --scope core-with-fixtures \
    --source-revision local-smoke >/dev/null
done
cmp data/smoke-partitions-c18/visible/manifest.json data/smoke-partitions-c18-repeat/visible/manifest.json
cmp data/smoke-partitions-c18/hidden/manifest.json data/smoke-partitions-c18-repeat/hidden/manifest.json
rm -rf data/smoke-partitions-c18-repeat

# SQL task: the smoke selection must build deterministically and every
# script must reproduce under the host SQLite.
rm -rf data/smoke-partitions-sql data/smoke-partitions-sql-repeat
for out in data/smoke-partitions-sql data/smoke-partitions-sql-repeat; do
  python3 scripts/select_sqllogictest.py \
    --source fixtures/smoke-sql \
    --selection fixtures/smoke-sql/selection.json \
    --output "$out" \
    --seed 20260916 \
    --visible-fraction 0.70 \
    --source-revision local-smoke \
    --verify-sqlite >/dev/null
done
cmp data/smoke-partitions-sql/visible/manifest.json data/smoke-partitions-sql-repeat/visible/manifest.json
cmp data/smoke-partitions-sql/hidden/manifest.json data/smoke-partitions-sql-repeat/hidden/manifest.json
rm -rf data/smoke-partitions-sql-repeat
python3 - <<'PY2'
import json
for part in ("visible", "hidden"):
    manifest = json.load(open(f"data/smoke-partitions-sql/{part}/manifest.json"))
    for row in manifest["tests"]:
        assert row["script"]["host_reference_disagreements"] == 0, row
print("Chapters 1-18 fixture split and SQL smoke selection checks passed.")
PY2

# Pinned task selections, when the partitions have been fetched.
if [[ -f data/partitions-c18/visible/manifest.json ]]; then
  python3 scripts/pin_selection.py --check --record studies/c18/selection.json --partitions data/partitions-c18
fi
if [[ -f data/partitions-sql/visible/manifest.json ]]; then
  python3 scripts/pin_selection.py --check --record studies/sql/selection-record.json --partitions data/partitions-sql
fi
