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
print("Evaluator smoke test passed.")
PY
