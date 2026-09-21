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

# The interpreter has to ship its own development headers. Triton compiles a
# small C module against Python.h the first time the server starts, and this
# host's /usr/bin/python3.12 is a stripped build with no headers (and no
# ensurepip), so a venv on it installs cleanly and then dies at first launch
# with a bare CalledProcessError from gcc. A uv-managed CPython carries its
# headers with it; --managed-python refuses the system interpreter.
if [[ ! -d "$VENV" ]]; then
  echo "creating $VENV on a uv-managed CPython"
  uv python install 3.12
  uv venv --python 3.12 --managed-python "$VENV"
fi
"$VENV/bin/python" - <<'PY'
import os, sys, sysconfig
include = sysconfig.get_paths()["include"]
if not os.path.exists(os.path.join(include, "Python.h")):
    sys.exit(
        f"error: {sys.executable} has no development headers ({include}/Python.h is missing).\n"
        "SGLang would install and then fail at first launch. Remove the venv and rerun;\n"
        "this script builds it on a uv-managed CPython, which ships its headers."
    )
print(f"python  {sys.version.split()[0]} with headers at {include}")
PY

# Install the exact environment that was measured when a lock exists, and the
# pinned release otherwise. Unpinned, `sglang` resolves to whatever is newest
# that day, and the serving behaviour this project records -- pool sizes,
# parser behaviour, the tool-call buffering -- is specific to a version.
# --prerelease=allow is required: the wheels depend on prerelease CUDA 13
# builds of torch and flashinfer. ninja is needed because SGLang JIT-compiles
# kernels at first launch and shells out to it.
LOCK="$ROOT/config/sglang.lock.txt"
if [[ -f "$LOCK" && "${1:-}" != "--upgrade" ]]; then
  echo "installing the locked environment ($(grep -vc '^#' "$LOCK") packages) into ${VENV#"$ROOT"/}"
  uv pip install --python "$VENV/bin/python" --prerelease=allow -r "$LOCK"
else
  echo "installing sglang==${SGLANG_VERSION} into ${VENV#"$ROOT"/}"
  uv pip install --python "$VENV/bin/python" --prerelease=allow ${1:+--upgrade} \
    "sglang==${SGLANG_VERSION}" ninja
fi

# The CUDA wheels do not agree with each other out of the box: sglang's
# dependency graph resolves nvcc, nvvm and nvjitlink to 13.4 while the runtime
# and its headers stay at 13.0. Both mismatches are fatal, in different ways
# and at different points in the build:
#
#   nvcc 13.4 against 13.0 headers  -> "CUDA compiler and CUDA toolkit headers
#                                       are incompatible" from flashinfer
#   nvvm 13.4 against ptxas 13.0    -> "Unsupported .version 9.4; current
#                                       version is 9.0" from ptxas
#
# Pin the compiler side down to the runtime's 13.0 so every component agrees.
echo "aligning the CUDA toolchain with the 13.0 runtime"
uv pip install --python "$VENV/bin/python" \
  'nvidia-cuda-nvcc==13.0.*' 'nvidia-cuda-crt==13.0.*' \
  'nvidia-nvvm==13.0.*' 'nvidia-nvjitlink==13.0.*'

# SGLang JIT-compiles a few kernels at first launch. Its linker flags are
# written for a system CUDA toolkit -- "-L$CUDA_HOME/lib64 -lcudart" -- but
# the toolkit here comes from pip, which puts libraries in lib/ and ships
# only versioned sonames. Without these links the server compiles its
# kernels and then dies at the link step with "cannot find -lcudart".
"$VENV/bin/python" "$ROOT/scripts/link_cuda_dev.py" "$VENV"

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
