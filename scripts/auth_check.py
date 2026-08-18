#!/usr/bin/env python3
"""Make one minimal provider request (Coding Plan or local endpoint) through the pinned Pi image."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from common import (
    ExperimentError,
    REPO_ROOT,
    api_key_for,
    docker_image_id,
    docker_pi_config_mounts,
    docker_secret_env,
    is_local_provider,
    load_config,
    require_command,
    write_local_models_json,
)


def extract_text(jsonl: str) -> str:
    final = ""
    for line in jsonl.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("type") != "message_end":
            continue
        message = event.get("message", {})
        if message.get("role") != "assistant":
            continue
        parts = []
        for item in message.get("content", []):
            if isinstance(item, dict) and item.get("type") == "text":
                parts.append(str(item.get("text", "")))
        if parts:
            final = "".join(parts)
    return final.strip()


def main() -> int:
    require_command("docker")
    config = load_config()
    image = config["EXPERIMENT_IMAGE"]
    docker_image_id(image)
    variable, key = api_key_for(config)
    provider = config.get("MODEL_PROVIDER", "zai")
    model = config.get("MODEL_ID", "glm-5.2")
    platform_name = config.get("DOCKER_PLATFORM", "linux/amd64")

    with tempfile.TemporaryDirectory(prefix="picc-auth-") as temporary, docker_secret_env(variable, key) as env_file:
        state = Path(temporary) / "state"
        work = Path(temporary) / "work"
        (state / "home").mkdir(parents=True)
        (state / "pi").mkdir()
        work.mkdir()
        (work / ".pi").mkdir()
        local_args: list[str] = []
        if is_local_provider(config):
            # Pi resolves the custom provider from PI_CODING_AGENT_DIR/models.json.
            write_local_models_json(config, state / "pi")
            local_args = ["--add-host", "host.docker.internal:host-gateway"]
        user_args: list[str] = []
        if hasattr(os, "getuid") and hasattr(os, "getgid"):
            user_args = ["--user", f"{os.getuid()}:{os.getgid()}"]
        command = [
            "docker",
            "run",
            "--rm",
            "--init",
            "--platform",
            platform_name,
            "--read-only",
            "--tmpfs",
            "/tmp:rw,exec,nosuid,nodev,size=256m",
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges",
            *local_args,
            *user_args,
            "--env-file",
            str(env_file),
            "-e",
            "PI_OFFLINE=1",
            "-e",
            "PI_SKIP_VERSION_CHECK=1",
            "-e",
            "PI_TELEMETRY=0",
            "-e",
            "HOME=/state/home",
            "-e",
            "PI_CODING_AGENT_DIR=/state/pi",
            "--mount",
            f"type=bind,src={state},dst=/state",
            "--mount",
            f"type=bind,src={work},dst=/work,readonly",
            *docker_pi_config_mounts(REPO_ROOT / "pi", "/work/.pi"),
            "--workdir",
            "/work",
            image,
            "pi",
            "--mode",
            "json",
            "--no-session",
            "--no-tools",
            "--approve",
            "--no-skills",
            "--no-prompt-templates",
            "--no-themes",
            "--no-context-files",
            "--provider",
            provider,
            "--model",
            model,
            "--thinking",
            "off",
            "Reply with exactly AUTH_OK and no other text.",
        ]
        result = subprocess.run(command, check=False, capture_output=True, text=True, timeout=300)
    if result.returncode != 0:
        raise ExperimentError(
            f"Pi provider check failed for {provider}/{model} ({result.returncode}).\n"
            f"stderr:\n{result.stderr[-4000:]}\nstdout:\n{result.stdout[-4000:]}"
        )
    text = extract_text(result.stdout)
    print(f"Provider/model request and project-extension load succeeded: {provider}/{model}")
    print(f"Model response: {text or '[no final text extracted]'}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ExperimentError, subprocess.TimeoutExpired) as error:
        print(f"error: {error}", file=sys.stderr)
        raise SystemExit(1)
