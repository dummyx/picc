#!/usr/bin/env bash
# End-to-end smoke of the two task evaluators inside the pinned image:
#   * SQL engine: the reference-backed candidate (Python sqlite3, the pinned
#     SQLite) must score 1.0 on the smoke scripts and on the hidden partition
#     when fetched; the reject-all and constant-output candidates must not.
#   * Chapters 1-18 compiler: the GCC-backed candidate must score 1.0 on the
#     smoke corpus (partner units, assembly helper, header, -lm); reject-all
#     and constant-output candidates must fail as documented.
# Needs Docker and the pinned image; `make validate` builds the smoke partitions.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
set -a
# shellcheck disable=SC1091
source "$ROOT/config/defaults.env"
if [[ -f "$ROOT/.env" ]]; then
  # shellcheck disable=SC1091
  source "$ROOT/.env"
fi
set +a

if [[ ! -f "$ROOT/data/smoke-partitions-sql/visible/manifest.json" || ! -f "$ROOT/data/smoke-partitions-c18/visible/manifest.json" ]]; then
  "$ROOT/scripts/validate.sh"
fi

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
uid="$(id -u)"
gid="$(id -g)"

merge_partitions() {
  # $1 = partitions dir, $2 = destination: one tests root holding both partitions.
  python3 - "$1" "$2" <<'PY'
import json, shutil, sys
from pathlib import Path
source, destination = Path(sys.argv[1]), Path(sys.argv[2])
rows = []
for partition in ("visible", "hidden"):
    manifest = json.loads((source / partition / "manifest.json").read_text())
    shutil.copytree(source / partition, destination, dirs_exist_ok=True)
    rows.extend(manifest["tests"])
(destination / "manifest.json").write_text(json.dumps({**manifest, "partition": "all", "tests": rows}))
PY
}

run_in_image() {
  # $1 = workspace, $2 = evaluator dir, $3 = tests dir, $4 = artifacts dir, $5.. = evaluator args
  local workspace="$1" evaluator="$2" tests="$3" artifacts="$4"
  shift 4
  docker run --rm --init \
    --platform "$DOCKER_PLATFORM" \
    --read-only \
    --tmpfs /tmp:rw,exec,nosuid,nodev,size=512m \
    --cap-drop ALL \
    --security-opt no-new-privileges \
    --user "$uid:$gid" \
    --mount "type=bind,src=$workspace,dst=/workspace" \
    --mount "type=bind,src=$tests,dst=/tests,readonly" \
    --mount "type=bind,src=$evaluator,dst=/opt/picc-eval,readonly" \
    --mount "type=bind,src=$artifacts,dst=/run-artifacts" \
    --workdir /workspace \
    "$EXPERIMENT_IMAGE" \
    python3 /opt/picc-eval/evaluate.py --workspace /workspace --tests-root /tests --manifest /tests/manifest.json \
      --candidate-config /opt/picc-eval/candidate.json "$@"
}

# ---- SQL engine -----------------------------------------------------------
sql_eval="$tmp/sql-eval"
mkdir -p "$sql_eval"
cp "$ROOT/studies/runtime/sql/evaluate.py" "$ROOT/studies/runtime/sql/sqllogictest.py" "$ROOT/studies/runtime/candidate_runtime.py" "$sql_eval/"
python3 - "$sql_eval/task.json" "$SQLITE_VERSION" <<'PY'
import json, sys
json.dump({"id": "sql-engine-sqllogictest", "runtime": "sql-engine", "max_stage": 8,
           "parameters": {"sqlite_version": sys.argv[2], "script_timeout_seconds": 120}}, open(sys.argv[1], "w"))
PY
sql_tests="$tmp/sql-tests"
mkdir -p "$sql_tests"
merge_partitions "$ROOT/data/smoke-partitions-sql" "$sql_tests"

sql_case() {
  local label="$1" fixture="$2" tests="$3" expect="$4"
  local work="$tmp/sql-$label"
  mkdir -p "$work/artifacts/evaluations" "$work/eval"
  cp -R "$ROOT/fixtures/$fixture/." "$work/workspace"
  cp "$sql_eval"/* "$work/eval/"
  cp "$ROOT/fixtures/$fixture/candidate.json" "$work/eval/candidate.json"
  run_in_image "$work/workspace" "$work/eval" "$tests" "$work/artifacts" \
    --max-stage 8 --output "/run-artifacts/evaluations/result.json" --summary-json >/dev/null
  python3 - "$work/artifacts/evaluations/result.json" "$label" "$expect" "$SQLITE_VERSION" <<'PY'
import json, sys
result = json.load(open(sys.argv[1]))
label, expect, pinned = sys.argv[2], sys.argv[3], sys.argv[4]
summary = result["summary"]
assert result["task"]["sqlite_version"] == pinned, result["task"]
assert summary["build_ok"] and summary["audit_ok"], result.get("source_audit")
disagreements = sum(row["records"]["reference_disagreements"] for row in result["tests"])
if expect == "perfect":
    assert summary["score"] == 1.0, summary
    assert disagreements == 0, disagreements
elif expect == "reject":
    # Rejecting everything satisfies only the corpus's two `statement error` records.
    assert summary["records_passed"] == 2 and summary["passed"] == 0, summary
else:
    assert summary["score"] < 0.15 and summary["records_passed"] == 0, summary
print(f"Task smoke passed (SQL {label}: score {summary['score']:.4f}, records {summary['records_passed']}/{summary['records_total']}, pinned SQLite {pinned}).")
PY
}
sql_case reference mock-pisql-sqlite "$sql_tests" perfect
sql_case reject-all mock-pisql-reject "$sql_tests" reject
sql_case constant mock-pisql-constant "$sql_tests" low
if [[ -f "$ROOT/data/partitions-sql/hidden/manifest.json" ]]; then
  sql_case reference-hidden mock-pisql-sqlite "$ROOT/data/partitions-sql/hidden" perfect
fi

# ---- Chapters 1-18 compiler ----------------------------------------------------
c_eval="$tmp/c-eval"
mkdir -p "$c_eval"
cp "$ROOT/studies/runtime/evaluate.py" "$ROOT/studies/runtime/candidate_runtime.py" "$c_eval/"
c_tests="$tmp/c-tests"
mkdir -p "$c_tests"
merge_partitions "$ROOT/data/smoke-partitions-c18" "$c_tests"

c_case() {
  local label="$1" fixture="$2" expect="$3"
  local work="$tmp/c-$label"
  mkdir -p "$work/artifacts/evaluations" "$work/eval"
  cp -R "$ROOT/fixtures/$fixture/." "$work/workspace"
  cp "$c_eval"/* "$work/eval/"
  cp "$ROOT/fixtures/$fixture/candidate.json" "$work/eval/candidate.json"
  run_in_image "$work/workspace" "$work/eval" "$c_tests" "$work/artifacts" \
    --max-stage 18 --output "/run-artifacts/evaluations/result.json" --summary-json >/dev/null
  python3 - "$work/artifacts/evaluations/result.json" "$label" "$expect" <<'PY'
import json, sys
result = json.load(open(sys.argv[1]))
label, expect = sys.argv[2], sys.argv[3]
summary = result["summary"]
assert summary["build_ok"] and summary["audit_ok"], result.get("source_audit")
types = {row["id"]: row["failure_type"] for row in result["tests"]}
if expect == "perfect":
    assert summary["score"] == 1.0, summary
    assert result["input_policy"]["raw_fallbacks"] == [], result["input_policy"]
elif expect == "reject":
    assert all(t is None for i, t in types.items() if "/invalid_" in i), types
    assert all(t == "unexpected_reject" for i, t in types.items() if "/valid/" in i), types
else:
    assert types["chapter_11/valid/libraries/add_long.c"] == "assembly_or_link_failure", types
    assert types["chapter_11/valid/libraries/add_long_client.c"] == "wrong_behavior", types
    assert all(t == "unexpected_accept" for i, t in types.items() if "/invalid_" in i), types
    assert summary["score"] < 0.3, summary
print(f"Task smoke passed (chapters 1-18 {label}: score {summary['score']:.4f}, {summary['passed']}/{summary['total']}).")
PY
}
c_case reference mock-picc-gcc perfect
c_case reject-all mock-picc-reject reject
c_case constant mock-picc-constant constant

# ---- Typed-Python build gate (mypy pinned in the image) --------------------------
typed="$tmp/typed"
mkdir -p "$typed/ok" "$typed/bad"
printf 'def add(a: int, b: int) -> int:\n    return a + b\n\nprint(add(1, 2))\n' > "$typed/ok/pisql.py"
printf 'def add(a, b):\n    return a + b\n\nprint(add(1, 2))\n' > "$typed/bad/pisql.py"
for case in ok bad; do
  set +e
  docker run --rm --init --platform "$DOCKER_PLATFORM" --read-only \
    --tmpfs /tmp:rw,exec,nosuid,nodev,size=256m --cap-drop ALL --security-opt no-new-privileges \
    --user "$uid:$gid" --mount "type=bind,src=$typed/$case,dst=/workspace" --workdir /workspace \
    "$EXPERIMENT_IMAGE" mypy --strict --no-error-summary --cache-dir /tmp/mypy-cache pisql.py > "$typed/$case.log" 2>&1
  status=$?
  set -e
  if [[ "$case" == ok && "$status" -ne 0 ]]; then echo "mypy gate rejected annotated code:"; cat "$typed/$case.log"; exit 1; fi
  if [[ "$case" == bad && "$status" -eq 0 ]]; then echo "mypy gate accepted unannotated code"; exit 1; fi
done
version="$(docker run --rm "$EXPERIMENT_IMAGE" mypy --version)"
[[ "$version" == "mypy $MYPY_VERSION"* ]] || { echo "unexpected mypy: $version"; exit 1; }
echo "Task smoke passed (typed Python gate: $version; unannotated code is a build failure)."
