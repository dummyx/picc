#!/usr/bin/env bash
# Install the SGLang inference server into its own virtualenv.
#
# SGLang is not a dependency of the harness: the harness's Python is standard
# library only, deliberately, so that a run's Python environment is the pinned
# Docker image and nothing else. SGLang is a dependency of the *operator*, the
# thing that serves the model the harness talks to over HTTP. It therefore
# gets its own virtualenv, outside the harness import path, and is pinned in
# config/sglang.env rather than in any requirements file the harness reads.
#
#   scripts/install_sglang.sh [--upgrade]
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$ROOT/config/sglang.env"
VENV="$ROOT/${SGLANG_VENV:-.venv-sglang}"

# uv rather than pip: this host's python3.12 ships without ensurepip, so
# `python3 -m venv` produces an environment with no pip in it. uv needs
# neither, and it is what SGLang's own install guide recommends.
if ! command -v uv >/dev/null 2>&1; then
  if [[ -x "$HOME/.local/bin/uv" ]]; then
    export PATH="$HOME/.local/bin:$PATH"
  else
    echo "installing uv into ~/.local/bin"
    export UV_INSTALL_DIR="$HOME/.local/bin"
    mkdir -p "$UV_INSTALL_DIR"
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
  fi
fi

if [[ ! -d "$VENV" ]]; then
  echo "creating $VENV"
  uv venv --python 3.12 "$VENV"
fi

# --prerelease=allow is required: SGLang's published wheels depend on
# prerelease CUDA 13 builds of torch and flashinfer.
echo "installing sglang into ${VENV#"$ROOT"/}"
uv pip install --python "$VENV/bin/python" --prerelease=allow ${1:+--upgrade} sglang

"$VENV/bin/python" - <<'PY'
import sglang, torch
print(f"sglang  {sglang.__version__}")
print(f"torch   {torch.__version__}")
print(f"cuda    {torch.version.cuda}")
print(f"gpu     {torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'NOT AVAILABLE'}")
if torch.cuda.is_available():
    major, minor = torch.cuda.get_device_capability(0)
    print(f"compute sm_{major}{minor}")
PY
