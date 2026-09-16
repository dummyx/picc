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

resolved="$("$ROOT/scripts/ensure_upstream_tests.sh" | tail -n 1)"
SOURCE_DIR="$ROOT/data/upstream/writing-a-c-compiler-tests"

python3 "$ROOT/scripts/split_tests.py" \
  --source "$SOURCE_DIR" \
  --output "$ROOT/data/partitions" \
  --seed "$SPLIT_SEED" \
  --visible-fraction "$VISIBLE_FRACTION" \
  --max-stage "$TEST_MAX_STAGE" \
  --source-revision "$resolved"

git -C "$SOURCE_DIR" show -s --format='%H%n%cI%n%s' > "$ROOT/data/upstream-revision.txt"
echo "Prepared visible and hidden partitions at data/partitions from $resolved"
