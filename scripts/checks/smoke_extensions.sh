#!/usr/bin/env bash
# Exercise the repair extensions' pure logic inside the pinned image, after a
# syntax check of every extension and extension template (the host usually
# has no TypeScript compiler; the image does).
#
# Both are covered end to end by resuming a real session that failed, but that
# only reaches the paths real conversations take. These probes drive the rest:
# the compaction bound's drop path, which needs input that truncation alone
# cannot fit, and the truncation repair's decisions about which replies to
# leave alone.
set -euo pipefail

cd "$(dirname "$0")/../.."
IMAGE="$(python3 - <<'PY'
import sys
sys.path.insert(0, "scripts")
from common import load_config
print(load_config()["EXPERIMENT_IMAGE"])
PY
)"

docker run --rm --init --network none \
  --mount "type=bind,src=$(pwd)/pi,dst=/repo/pi,readonly" \
  --mount "type=bind,src=$(pwd)/studies/runtime,dst=/repo/studies/runtime,readonly" \
  --mount "type=bind,src=$(pwd)/scripts/checks,dst=/repo/scripts/checks,readonly" \
  --workdir /repo --entrypoint sh "$IMAGE" -c 'NODE_PATH="$(npm root -g)" node scripts/checks/check_typescript.js'

docker run --rm --init \
  --mount "type=bind,src=$(pwd)/pi/extensions/compaction-bound.ts,dst=/probe/compaction-bound.ts,readonly" \
  --mount "type=bind,src=$(pwd)/pi/extensions/truncation-repair.ts,dst=/probe/truncation-repair.ts,readonly" \
  --mount "type=bind,src=$(pwd)/scripts/checks/compaction_probe.mjs,dst=/probe/compaction_probe.mjs,readonly" \
  --mount "type=bind,src=$(pwd)/scripts/checks/truncation_probe.mjs,dst=/probe/truncation_probe.mjs,readonly" \
  --entrypoint sh "$IMAGE" -c '
set -e
mkdir -p /tmp/probe/node_modules/@earendil-works
cp /probe/*.ts /probe/*.mjs /tmp/probe/
ln -s "$(npm root -g)/@earendil-works/pi-coding-agent" /tmp/probe/node_modules/@earendil-works/pi-coding-agent
cd /tmp/probe
node compaction_probe.mjs
node truncation_probe.mjs
'
