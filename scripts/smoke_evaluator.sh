#!/usr/bin/env bash
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

if [[ ! -f "$ROOT/data/smoke-partitions/visible/manifest.json" ]]; then
  "$ROOT/scripts/validate.sh"
fi

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
cp -R "$ROOT/fixtures/mock-picc/." "$tmp/workspace"
mkdir -p "$tmp/artifacts/evaluations"
uid="$(id -u)"
gid="$(id -g)"

docker run --rm --init \
  --platform "$DOCKER_PLATFORM" \
  --read-only \
  --tmpfs /tmp:rw,exec,nosuid,nodev,size=512m \
  --cap-drop ALL \
  --security-opt no-new-privileges \
  --user "$uid:$gid" \
  --mount "type=bind,src=$tmp/workspace,dst=/workspace" \
  --mount "type=bind,src=$ROOT/data/smoke-partitions/visible,dst=/tests,readonly" \
  --mount "type=bind,src=$ROOT/evaluator,dst=/opt/picc-eval,readonly" \
  --mount "type=bind,src=$tmp/artifacts,dst=/run-artifacts" \
  --workdir /workspace \
  "$EXPERIMENT_IMAGE" \
  python3 /opt/picc-eval/evaluate.py \
    --workspace /workspace \
    --tests-root /tests \
    --manifest /tests/manifest.json \
    --max-stage 1 \
    --output /run-artifacts/evaluations/smoke.json \
    --summary-json

python3 - "$tmp/artifacts/evaluations/smoke.json" <<'PY'
import json, sys
result = json.load(open(sys.argv[1]))
summary = result["summary"]
assert summary["build_ok"] is True
assert summary["score"] == 1.0, summary
print("Evaluator smoke test passed (Rust, base evaluator).")
PY

# The study-layer evaluator with the language-neutral adapters: each mock must
# build, pass the source audit, and score 1.0 at stage 1; a TypeScript type
# error must be a build failure (the static-typing gate), not a runtime one.
run_study_evaluator() {
  local label="$1" adapter="$2" fixture="$3" expect="$4"
  local work="$tmp/$label"
  rm -rf "$work"
  mkdir -p "$work/eval" "$work/artifacts/evaluations"
  cp -R "$ROOT/$fixture/." "$work/workspace"
  cp "$ROOT/studies/runtime/evaluate.py" "$work/eval/evaluate.py"
  cp "$ROOT/$adapter" "$work/eval/candidate.json"
  if [[ "$expect" == "type-error" ]]; then
    printf 'const smokeTypeError: number = "not a number";\n' >> "$work/workspace/src/picc.ts"
  fi
  docker run --rm --init \
    --platform "$DOCKER_PLATFORM" \
    --read-only \
    --tmpfs /tmp:rw,exec,nosuid,nodev,size=512m \
    --cap-drop ALL \
    --security-opt no-new-privileges \
    --user "$uid:$gid" \
    --mount "type=bind,src=$work/workspace,dst=/workspace" \
    --mount "type=bind,src=$ROOT/data/smoke-partitions/visible,dst=/tests,readonly" \
    --mount "type=bind,src=$work/eval,dst=/opt/picc-eval,readonly" \
    --mount "type=bind,src=$work/artifacts,dst=/run-artifacts" \
    --workdir /workspace \
    "$EXPERIMENT_IMAGE" \
    python3 /opt/picc-eval/evaluate.py \
      --workspace /workspace \
      --tests-root /tests \
      --manifest /tests/manifest.json \
      --candidate-config /opt/picc-eval/candidate.json \
      --max-stage 1 \
      --output /run-artifacts/evaluations/smoke.json \
      --summary-json
  python3 - "$work/artifacts/evaluations/smoke.json" "$label" "$expect" <<'PY'
import json, sys
result = json.load(open(sys.argv[1]))
label, expect = sys.argv[2], sys.argv[3]
summary = result["summary"]
if expect == "pass":
    assert summary["audit_ok"] is True, result["source_audit"]
    assert summary["build_ok"] is True, result["build"]
    assert summary["score"] == 1.0, summary
    print(f"Evaluator smoke test passed ({label}, study evaluator).")
else:
    assert summary["build_ok"] is False, result["build"]
    assert summary["score"] == 0.0, summary
    build = result["build"] or {}
    assert "TS2322" in build.get("stdout", "") + build.get("stderr", ""), build
    assert all(row["failure_type"] == "build_failure" and "TS2322" in (row["detail"] or "") for row in result["tests"]), result["tests"]
    print(f"Evaluator smoke test passed ({label}: type error is a build failure).")
PY
}

run_study_evaluator typescript studies/assets/candidates/typescript-strict.json fixtures/mock-picc-ts pass
run_study_evaluator javascript studies/assets/candidates/javascript-node.json fixtures/mock-picc-js pass
run_study_evaluator typescript-gate studies/assets/candidates/typescript-strict.json fixtures/mock-picc-ts type-error
