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

docker build \
  --platform "$DOCKER_PLATFORM" \
  --build-arg "STARTER_VERSION=$STARTER_VERSION" \
  --build-arg "NODE_IMAGE=$NODE_IMAGE" \
  --build-arg "PI_VERSION=$PI_VERSION" \
  --build-arg "RUST_TOOLCHAIN=$RUST_TOOLCHAIN" \
  --tag "$EXPERIMENT_IMAGE" \
  --file "$ROOT/docker/Dockerfile" \
  "$ROOT"

docker image inspect "$EXPERIMENT_IMAGE" --format 'built {{.Id}}'
