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

# The inference server, when this host is the one serving the model. Absence
# is not a failure: a run can point LOCAL_BASE_URL at any OpenAI-compatible
# endpoint, on this host or another.
if [[ -f "$ROOT/config/sglang.env" ]]; then
  # shellcheck source=/dev/null
  source "$ROOT/config/sglang.env"
  venv="$ROOT/${SGLANG_VENV:-.venv-sglang}"
  if [[ -x "$venv/bin/sglang" ]]; then
    echo "sglang       $("$venv/bin/python" -c 'import sglang; print(sglang.__version__)' 2>/dev/null || echo present)"
  else
    echo "sglang       absent (make sglang-install, if this host serves the model)"
  fi
  model_dir="${SGLANG_MODEL_DIR:-$HOME/models/${SGLANG_MODEL_REPO##*/}}"
  if [[ -f "$model_dir/config.json" ]]; then
    echo "checkpoint   $model_dir"
  else
    echo "checkpoint   absent (scripts/fetch_model.sh)"
  fi
  if command -v nvidia-smi >/dev/null 2>&1; then
    echo "gpu          $(nvidia-smi --query-gpu=name,memory.total --format=csv,noheader 2>/dev/null | head -1)"
  fi
fi

if [[ "$fail" -ne 0 ]]; then
  exit 1
fi
