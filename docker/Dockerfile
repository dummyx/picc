# syntax=docker/dockerfile:1
ARG NODE_IMAGE=node:24-bookworm-slim
FROM ${NODE_IMAGE}

ARG STARTER_VERSION=0.1.0
ARG PI_VERSION=0.84.1
ARG RUST_TOOLCHAIN=1.88.0
ARG TYPESCRIPT_VERSION=5.9.3
ARG NODE_TYPES_VERSION=24.13.3

LABEL org.opencontainers.image.title="PiCC Pi experiment"
LABEL org.opencontainers.image.version="${STARTER_VERSION}"
LABEL org.opencontainers.image.description="Pinned Pi coding-agent, Rust and TypeScript toolchains, and C compiler evaluator"
LABEL io.picc.pi.version="${PI_VERSION}"
LABEL io.picc.rust.toolchain="${RUST_TOOLCHAIN}"
LABEL io.picc.typescript.version="${TYPESCRIPT_VERSION}"
LABEL io.picc.node-types.version="${NODE_TYPES_VERSION}"

ENV DEBIAN_FRONTEND=noninteractive \
    RUSTUP_HOME=/opt/rustup \
    CARGO_HOME=/opt/cargo \
    PATH=/opt/cargo/bin:${PATH} \
    PI_SKIP_VERSION_CHECK=1 \
    PI_TELEMETRY=0 \
    CARGO_NET_OFFLINE=true

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       binutils \
       build-essential \
       ca-certificates \
       curl \
       file \
       git \
       jq \
       procps \
       python3 \
       python3-venv \
       ripgrep \
       xz-utils \
    && curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs \
       | sh -s -- -y --profile minimal --default-toolchain "${RUST_TOOLCHAIN}" \
    && rustup component add rustfmt clippy --toolchain "${RUST_TOOLCHAIN}" \
    && npm install -g --ignore-scripts "@earendil-works/pi-coding-agent@${PI_VERSION}" \
    && npm install -g --ignore-scripts "typescript@${TYPESCRIPT_VERSION}" "@types/node@${NODE_TYPES_VERSION}" \
    && npm cache clean --force \
    && apt-get purge -y --auto-remove curl \
    && rm -rf /var/lib/apt/lists/* /root/.npm /tmp/*

WORKDIR /workspace
CMD ["pi", "--help"]
