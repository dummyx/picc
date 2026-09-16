#!/usr/bin/env bash
# Fetch the pinned sqllogictest scripts named in studies/sql/selection.json
# (sparse, blob-less clone of the mirror at SQLLOGICTEST_REF), build the SQL
# task partitions under data/partitions-sql, and check them against the
# committed selection record.
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

SOURCE_DIR="$ROOT/data/upstream/sqllogictest"
PARENT_DIR="$(dirname "$SOURCE_DIR")"
SELECTION="$ROOT/studies/sql/selection.json"
mkdir -p "$PARENT_DIR"

mapfile -t wanted < <(python3 - "$SELECTION" <<'PY'
import json, sys
record = json.load(open(sys.argv[1]))
for stage in record["stages"]:
    for path in stage["scripts"]:
        print(path)
PY
)

checkout_is_valid=0
if [[ -d "$SOURCE_DIR/.git" ]]; then
  if current="$(git -C "$SOURCE_DIR" rev-parse HEAD 2>/dev/null)"; then
    if [[ "$current" == "$SQLLOGICTEST_REF" ]]; then
      checkout_is_valid=1
    elif [[ "${FORCE_TEST_REFRESH:-0}" != "1" ]]; then
      echo "Existing sqllogictest checkout is $current, expected $SQLLOGICTEST_REF." >&2
      echo "Set FORCE_TEST_REFRESH=1 to replace it." >&2
      exit 1
    fi
  fi
fi

if [[ "$checkout_is_valid" != "1" ]]; then
  rm -rf "$SOURCE_DIR"
  TEMP_DIR="$(mktemp -d "$PARENT_DIR/.sqllogictest.XXXXXX")"
  cleanup() { rm -rf "$TEMP_DIR"; }
  trap cleanup EXIT
  git clone --quiet --filter=blob:none --no-checkout "$SQLLOGICTEST_REPOSITORY" "$TEMP_DIR"
  git -C "$TEMP_DIR" sparse-checkout init --no-cone >/dev/null
  git -C "$TEMP_DIR" sparse-checkout set COPYRIGHT.md src/sqllogictest.c src/slt_sqlite.c "${wanted[@]}" >/dev/null
  git -C "$TEMP_DIR" checkout --quiet --detach "$SQLLOGICTEST_REF"
  mv "$TEMP_DIR" "$SOURCE_DIR"
  trap - EXIT
else
  # Make sure every selected script is materialized in the sparse checkout.
  git -C "$SOURCE_DIR" sparse-checkout add "${wanted[@]}" >/dev/null
fi

resolved="$(git -C "$SOURCE_DIR" rev-parse HEAD)"
if [[ "$resolved" != "$SQLLOGICTEST_REF" ]]; then
  echo "Resolved revision $resolved does not match pinned SQLLOGICTEST_REF=$SQLLOGICTEST_REF" >&2
  exit 1
fi
for path in "${wanted[@]}"; do
  if [[ ! -f "$SOURCE_DIR/$path" ]]; then
    echo "Selected script missing from the checkout: $path" >&2
    exit 1
  fi
done
if [[ -f "$SOURCE_DIR/COPYRIGHT.md" ]]; then
  cp "$SOURCE_DIR/COPYRIGHT.md" "$ROOT/data/UPSTREAM_SQLLOGICTEST_COPYRIGHT.md"
fi

python3 "$ROOT/scripts/select_sqllogictest.py" \
  --source "$SOURCE_DIR" \
  --selection "$SELECTION" \
  --output "$ROOT/data/partitions-sql" \
  --seed "$SQL_SPLIT_SEED" \
  --visible-fraction "$VISIBLE_FRACTION" \
  --source-revision "$resolved" \
  --verify-sqlite

if [[ "${WRITE_SELECTION:-0}" == "1" ]]; then
  python3 "$ROOT/scripts/pin_selection.py" --write --record "$ROOT/studies/sql/selection-record.json" --partitions "$ROOT/data/partitions-sql"
fi
python3 "$ROOT/scripts/pin_selection.py" --check --record "$ROOT/studies/sql/selection-record.json" --partitions "$ROOT/data/partitions-sql"
git -C "$SOURCE_DIR" show -s --format='%H%n%cI%n%s' > "$ROOT/data/upstream-sqllogictest-revision.txt"
echo "Prepared SQL task partitions at data/partitions-sql from $resolved"
