#!/usr/bin/env bash
# Build the pinned experiment image (make image). Every version comes from
# config/defaults.env. The build context is this directory alone: the
# Dockerfile copies nothing in, and the repository root would send runs/
# (many GB), the SGLang virtualenv and .env to the Docker daemon.
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

docker build \
  --platform "$DOCKER_PLATFORM" \
  --build-arg "STARTER_VERSION=$STARTER_VERSION" \
  --build-arg "NODE_IMAGE=$NODE_IMAGE" \
  --build-arg "PI_VERSION=$PI_VERSION" \
  --build-arg "RUST_TOOLCHAIN=$RUST_TOOLCHAIN" \
  --build-arg "TYPESCRIPT_VERSION=$TYPESCRIPT_VERSION" \
  --build-arg "NODE_TYPES_VERSION=$NODE_TYPES_VERSION" \
  --build-arg "BASH_TIMEOUT_PACKAGE=$BASH_TIMEOUT_PACKAGE" \
  --build-arg "BASH_TIMEOUT_PACKAGE_VERSION=$BASH_TIMEOUT_PACKAGE_VERSION" \
  --build-arg "MYPY_VERSION=$MYPY_VERSION" \
  --tag "$EXPERIMENT_IMAGE" \
  --file "$ROOT/docker/Dockerfile" \
  "$ROOT/docker"

docker image inspect "$EXPERIMENT_IMAGE" --format 'built {{.Id}}'
