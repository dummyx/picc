#!/usr/bin/env bash
# Exercise the compaction bound's pure logic inside the pinned image.
#
# The end-to-end behaviour is covered by resuming a real session, but that only
# reaches the truncation path: on real conversations the per-block caps already
# bring the request far under budget, so nothing is ever dropped. This drives
# the drop path directly with input that truncation alone cannot fit.
set -euo pipefail

cd "$(dirname "$0")/.."
IMAGE="$(python3 - <<'PY'
import sys
sys.path.insert(0, "scripts")
from common import load_config
print(load_config()["EXPERIMENT_IMAGE"])
PY
)"

docker run --rm --init \
  --mount "type=bind,src=$(pwd)/pi/extensions/compaction-bound.ts,dst=/probe/compaction-bound.ts,readonly" \
  --mount "type=bind,src=$(pwd)/scripts/compaction_probe.mjs,dst=/probe/probe.mjs,readonly" \
  --entrypoint sh "$IMAGE" -c '
set -e
mkdir -p /tmp/probe/node_modules/@earendil-works
cp /probe/compaction-bound.ts /tmp/probe/
cp /probe/probe.mjs /tmp/probe/
ln -s "$(npm root -g)/@earendil-works/pi-coding-agent" /tmp/probe/node_modules/@earendil-works/pi-coding-agent
cd /tmp/probe
node probe.mjs
'
