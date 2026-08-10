#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

fail=0
for command in docker git python3 make; do
  if command -v "$command" >/dev/null 2>&1; then
    printf '%-12s %s\n' "$command" "$(command -v "$command")"
  else
    echo "missing: $command" >&2
    fail=1
  fi
done

if command -v docker >/dev/null 2>&1; then
  if docker info >/dev/null 2>&1; then
    echo "docker       daemon reachable"
  else
    echo "docker daemon is not reachable" >&2
    fail=1
  fi
fi

arch="$(uname -m)"
if [[ "$arch" != "x86_64" && "$arch" != "amd64" ]]; then
  echo "note: host architecture is $arch; the experiment pins linux/amd64 and will use Docker emulation."
fi

if [[ -f "$ROOT/.env" ]]; then
  echo ".env         present"
else
  echo ".env         absent (copy .env.example before auth-check or a run)"
fi

python3 - <<'PY'
import sys
if sys.version_info < (3, 11):
    raise SystemExit("Python 3.11 or newer is required")
print("python       version OK")
PY

if [[ "$fail" -ne 0 ]]; then
  exit 1
fi
