#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

python3 -m py_compile scripts/*.py evaluator/evaluate.py studies/runtime/evaluate.py
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
