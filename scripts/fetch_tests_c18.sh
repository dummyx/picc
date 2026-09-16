#!/usr/bin/env bash
# Prepare the chapters 1-18 partitions (data/partitions-c18) from the pinned
# upstream revision and check them against the committed selection record.
# The chapters 1-10 partitions (data/partitions) are not touched.
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
  --output "$ROOT/data/partitions-c18" \
  --seed "$C18_SPLIT_SEED" \
  --visible-fraction "$VISIBLE_FRACTION" \
  --max-stage "$C18_MAX_STAGE" \
  --scope core-with-fixtures \
  --source-revision "$resolved" >/dev/null

if [[ "${WRITE_SELECTION:-0}" == "1" ]]; then
  python3 "$ROOT/scripts/pin_selection.py" --write --record "$ROOT/studies/c18/selection.json" --partitions "$ROOT/data/partitions-c18"
fi
python3 "$ROOT/scripts/pin_selection.py" --check --record "$ROOT/studies/c18/selection.json" --partitions "$ROOT/data/partitions-c18"
echo "Prepared chapters 1-18 partitions at data/partitions-c18 from $resolved"
