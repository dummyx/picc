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

SOURCE_DIR="$ROOT/data/upstream/writing-a-c-compiler-tests"
PARENT_DIR="$(dirname "$SOURCE_DIR")"
mkdir -p "$PARENT_DIR"

checkout_is_valid=0
if [[ -d "$SOURCE_DIR/.git" ]]; then
  if current="$(git -C "$SOURCE_DIR" rev-parse HEAD 2>/dev/null)"; then
    if [[ "$current" == "$TEST_REF" ]]; then
      checkout_is_valid=1
    elif [[ "${FORCE_TEST_REFRESH:-0}" != "1" ]]; then
      echo "Existing test checkout is $current, expected $TEST_REF." >&2
      echo "Set FORCE_TEST_REFRESH=1 to replace it." >&2
      exit 1
    fi
  else
    echo "Removing an incomplete upstream checkout left by an earlier failed fetch." >&2
  fi
fi

if [[ "$checkout_is_valid" != "1" ]]; then
  rm -rf "$SOURCE_DIR"
  TEMP_DIR="$(mktemp -d "$PARENT_DIR/.writing-a-c-compiler-tests.XXXXXX")"
  cleanup() { rm -rf "$TEMP_DIR"; }
  trap cleanup EXIT

  git init -q "$TEMP_DIR"
  git -C "$TEMP_DIR" remote add origin "$TEST_REPOSITORY"
  git -C "$TEMP_DIR" fetch --depth 1 origin "$TEST_REF"
  git -C "$TEMP_DIR" checkout --detach FETCH_HEAD

  resolved="$(git -C "$TEMP_DIR" rev-parse HEAD)"
  if [[ "$resolved" != "$TEST_REF" ]]; then
    echo "Resolved revision $resolved does not match pinned TEST_REF=$TEST_REF" >&2
    exit 1
  fi

  mv "$TEMP_DIR" "$SOURCE_DIR"
  trap - EXIT
fi

resolved="$(git -C "$SOURCE_DIR" rev-parse HEAD)"
if [[ "$resolved" != "$TEST_REF" ]]; then
  echo "Resolved revision $resolved does not match pinned TEST_REF=$TEST_REF" >&2
  exit 1
fi

python3 "$ROOT/scripts/split_tests.py" \
  --source "$SOURCE_DIR" \
  --output "$ROOT/data/partitions" \
  --seed "$SPLIT_SEED" \
  --visible-fraction "$VISIBLE_FRACTION" \
  --max-stage "$TEST_MAX_STAGE" \
  --source-revision "$resolved"

if [[ -f "$SOURCE_DIR/LICENSE" ]]; then
  cp "$SOURCE_DIR/LICENSE" "$ROOT/data/UPSTREAM_TEST_LICENSE"
fi

git -C "$SOURCE_DIR" show -s --format='%H%n%cI%n%s' > "$ROOT/data/upstream-revision.txt"
echo "Prepared visible and hidden partitions at data/partitions from $resolved"
