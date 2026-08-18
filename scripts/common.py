#!/usr/bin/env python3
"""Shared helpers for the PiCC GLM-5.2 experiment starter."""

from __future__ import annotations

import contextlib
import hashlib
import json
import os
import platform
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Iterator, Mapping, Sequence

REPO_ROOT = Path(__file__).resolve().parent.parent


class ExperimentError(RuntimeError):
    """A user-actionable experiment setup or execution error."""


def _parse_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        if "=" not in line:
            raise ExperimentError(f"Malformed environment line {path}:{line_number}")
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key):
            raise ExperimentError(f"Invalid environment key {key!r} in {path}:{line_number}")
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        values[key] = value
    return values


# Pre-rename names of the provider/model/thinking keys. They are refused, not
# aliased: a silently ignored override or a fuzzy frozen-config comparison is
# worse for this harness than a hard error.
LEGACY_KEY_RENAMES = {
    "ZAI_PROVIDER": "MODEL_PROVIDER",
    "ZAI_MODEL": "MODEL_ID",
    "ZAI_THINKING": "MODEL_THINKING",
}


def reject_legacy_keys(source: str, keys: Any) -> None:
    stale = sorted(set(keys) & set(LEGACY_KEY_RENAMES))
    if stale:
        renames = ", ".join(f"{key} -> {LEGACY_KEY_RENAMES[key]}" for key in stale)
        raise ExperimentError(
            f"Legacy configuration keys in {source}: {renames}. "
            "Rename them; they are refused so an outdated override cannot silently fall back to defaults."
        )


def load_config() -> dict[str, str]:
    """Load defaults, project .env, then process environment overrides."""
    config = _parse_env_file(REPO_ROOT / "config" / "defaults.env")
    overrides = _parse_env_file(REPO_ROOT / ".env")
    reject_legacy_keys(".env", overrides)
    reject_legacy_keys("the process environment", os.environ)
    config.update(overrides)
    for key in set(config) | {
        "ZAI_API_KEY",
        "ZAI_CODING_CN_API_KEY",
        "MODEL_PROVIDER",
        "MODEL_ID",
        "MODEL_THINKING",
        "LOCAL_API_KEY",
    }:
        if key in os.environ:
            config[key] = os.environ[key]
    return config


def config_int(config: Mapping[str, str], key: str) -> int:
    try:
        return int(config[key])
    except (KeyError, ValueError) as exc:
        raise ExperimentError(f"Configuration {key} must be an integer") from exc


def config_float(config: Mapping[str, str], key: str) -> float:
    try:
        return float(config[key])
    except (KeyError, ValueError) as exc:
        raise ExperimentError(f"Configuration {key} must be a number") from exc


def config_bool(config: Mapping[str, str], key: str) -> bool:
    raw = str(config.get(key, "")).strip().lower()
    if raw in {"1", "true", "yes", "on"}:
        return True
    if raw in {"", "0", "false", "no", "off"}:
        return False
    raise ExperimentError(f"Configuration {key} must be a boolean (0/1/true/false)")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def sha256_text(text: str) -> str:
    return sha256_bytes(text.encode("utf-8"))


def atomic_write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(value, handle, indent=2, sort_keys=True, ensure_ascii=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
    finally:
        with contextlib.suppress(FileNotFoundError):
            os.unlink(temp_name)


def append_jsonl(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(value, sort_keys=True, ensure_ascii=False) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not raw_line.strip():
            continue
        try:
            value = json.loads(raw_line)
        except json.JSONDecodeError as exc:
            raise ExperimentError(f"Invalid JSONL at {path}:{line_number}: {exc}") from exc
        if isinstance(value, dict):
            rows.append(value)
    return rows


def run(
    args: Sequence[str],
    *,
    cwd: Path | None = None,
    env: Mapping[str, str] | None = None,
    check: bool = True,
    capture_output: bool = True,
    text: bool = True,
    timeout: float | None = None,
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        list(args),
        cwd=cwd,
        env=dict(env) if env is not None else None,
        check=False,
        capture_output=capture_output,
        text=text,
        timeout=timeout,
    )
    if check and result.returncode != 0:
        stdout = (result.stdout or "")[-4000:]
        stderr = (result.stderr or "")[-4000:]
        raise ExperimentError(
            f"Command failed ({result.returncode}): {' '.join(args)}\nstdout:\n{stdout}\nstderr:\n{stderr}"
        )
    return result


def require_command(name: str) -> str:
    from shutil import which

    path = which(name)
    if path is None:
        raise ExperimentError(f"Required command not found: {name}")
    return path


def sanitize_run_id(value: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,95}", value):
        raise ExperimentError(
            "Run ID must be 1-96 characters and contain only letters, digits, '.', '_' or '-'"
        )
    return value


def docker_image_id(image: str) -> str:
    result = run(["docker", "image", "inspect", "--format", "{{.Id}}", image], check=False)
    if result.returncode != 0:
        raise ExperimentError(f"Docker image {image!r} does not exist. Run `make image` first.")
    return result.stdout.strip()


LOCAL_PROVIDER = "local"
LOCAL_API_KEY_PLACEHOLDER = "local-no-key"
LOCAL_SUPPORTED_APIS = (
    "openai-completions",
    "openai-responses",
    "anthropic-messages",
    "google-generative-ai",
)
# Pi thinking levels above "off"; the generated models.json declares all of
# them so any frozen MODEL_THINKING value stays selectable against the endpoint.
PI_THINKING_LEVELS = ("minimal", "low", "medium", "high", "xhigh", "max")


def is_local_provider(config: Mapping[str, str]) -> bool:
    return config.get("MODEL_PROVIDER", "zai") == LOCAL_PROVIDER


def api_key_for(config: Mapping[str, str]) -> tuple[str, str]:
    provider = config.get("MODEL_PROVIDER", "zai")
    if provider == "zai-coding-cn":
        variable = "ZAI_CODING_CN_API_KEY"
    elif provider == "zai":
        variable = "ZAI_API_KEY"
    elif provider == LOCAL_PROVIDER:
        # Keyless local servers still need a non-empty value: the generated
        # models.json resolves "$LOCAL_API_KEY" from the container environment.
        value = config.get("LOCAL_API_KEY", "").strip()
        return "LOCAL_API_KEY", value or LOCAL_API_KEY_PLACEHOLDER
    else:
        raise ExperimentError(
            f"Unsupported provider {provider!r}; use 'zai', 'zai-coding-cn', or 'local'"
        )
    value = config.get(variable, "").strip()
    if not value:
        raise ExperimentError(f"{variable} is empty. Copy .env.example to .env and set the key.")
    return variable, value


def _config_json_object(config: Mapping[str, str], key: str) -> dict[str, Any] | None:
    raw = config.get(key, "").strip()
    if not raw:
        return None
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ExperimentError(f"Configuration {key} must be a JSON object: {exc}") from exc
    if not isinstance(value, dict):
        raise ExperimentError(f"Configuration {key} must be a JSON object")
    return value


def resolve_local_provider(config: Mapping[str, str]) -> dict[str, Any]:
    """Validate the LOCAL_* endpoint configuration used when MODEL_PROVIDER=local."""
    if not is_local_provider(config):
        raise ExperimentError("Local endpoint configuration requires MODEL_PROVIDER=local")
    model_id = config.get("MODEL_ID", "").strip()
    if not model_id or model_id == "glm-5.2":
        raise ExperimentError(
            "MODEL_PROVIDER=local requires MODEL_ID to name the locally served model, "
            "for example unsloth/Qwen3.8-27B-GGUF:UD-Q4_K_XL; refusing the hosted "
            "default 'glm-5.2' so runs cannot be silently mislabeled"
        )
    base_url = config.get("LOCAL_BASE_URL", "").strip()
    if not base_url.startswith(("http://", "https://")):
        raise ExperimentError(
            "LOCAL_BASE_URL must be an http(s) URL, e.g. http://host.docker.internal:8080/v1"
        )
    api = config.get("LOCAL_API", "openai-completions").strip()
    if api not in LOCAL_SUPPORTED_APIS:
        raise ExperimentError(
            "LOCAL_API must be one of Pi's models.json API types: " + ", ".join(LOCAL_SUPPORTED_APIS)
        )
    context_window = config_int(config, "LOCAL_CONTEXT_WINDOW")
    max_tokens = config_int(config, "LOCAL_MAX_OUTPUT")
    if context_window <= 0 or max_tokens <= 0:
        raise ExperimentError("LOCAL_CONTEXT_WINDOW and LOCAL_MAX_OUTPUT must be positive integers")
    thinking_format = config.get("LOCAL_THINKING_FORMAT", "").strip()
    compat = _config_json_object(config, "LOCAL_COMPAT") or {}
    if thinking_format and "thinkingFormat" not in compat:
        compat["thinkingFormat"] = thinking_format
    return {
        "model_id": model_id,
        "base_url": base_url,
        "api": api,
        "context_window": context_window,
        "max_tokens": max_tokens,
        "reasoning": config_bool(config, "LOCAL_REASONING"),
        "thinking_format": thinking_format,
        "sampling_params": _config_json_object(config, "LOCAL_SAMPLING_PARAMS"),
        "compat": compat,
    }


def local_models_json(config: Mapping[str, str]) -> dict[str, Any]:
    """Pi models.json payload declaring the single frozen local provider/model."""
    resolved = resolve_local_provider(config)
    model: dict[str, Any] = {
        "id": resolved["model_id"],
        "reasoning": resolved["reasoning"],
        "input": ["text"],
        "contextWindow": resolved["context_window"],
        "maxTokens": resolved["max_tokens"],
        "cost": {"input": 0, "output": 0, "cacheRead": 0, "cacheWrite": 0},
    }
    if resolved["reasoning"]:
        model["thinkingLevelMap"] = {level: level for level in PI_THINKING_LEVELS}
    if resolved["sampling_params"] is not None:
        model["samplingParams"] = resolved["sampling_params"]
    provider: dict[str, Any] = {
        "name": "PiCC local endpoint",
        "baseUrl": resolved["base_url"],
        "api": resolved["api"],
        "apiKey": "$LOCAL_API_KEY",
        "models": [model],
    }
    if resolved["compat"]:
        provider["compat"] = resolved["compat"]
    return {"providers": {LOCAL_PROVIDER: provider}}


def write_local_models_json(config: Mapping[str, str], directory: Path) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "models.json"
    path.write_text(
        json.dumps(local_models_json(config), indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return path


def local_model_metadata(config: Mapping[str, str]) -> dict[str, Any]:
    """Endpoint facts recorded in (and revalidated against) metadata.json."""
    resolved = resolve_local_provider(config)
    return {
        "base_url": resolved["base_url"],
        "api": resolved["api"],
        "context_window": resolved["context_window"],
        "max_tokens": resolved["max_tokens"],
        "reasoning": resolved["reasoning"],
        "thinking_format": resolved["thinking_format"] or None,
        "sampling_params": resolved["sampling_params"],
    }


@contextlib.contextmanager
def docker_secret_env(variable: str, value: str) -> Iterator[Path]:
    """Create a mode-0600 Docker env file so the key is not placed in argv."""
    fd, name = tempfile.mkstemp(prefix="picc-docker-env-", text=True)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(f"{variable}={value}\n")
        yield Path(name)
    finally:
        with contextlib.suppress(FileNotFoundError):
            os.unlink(name)


def docker_mount(source: Path, target: str, readonly: bool = False) -> list[str]:
    source = source.resolve()
    spec = f"type=bind,src={source},dst={target}"
    if readonly:
        spec += ",readonly"
    return ["--mount", spec]


def docker_pi_config_mounts(config_dir: Path, target: str) -> list[str]:
    """Mount immutable Pi config under a writable directory for its lock file."""
    target = target.rstrip("/")
    options = ["rw", "nosuid", "nodev", "noexec", "size=16m", "mode=0755"]
    if hasattr(os, "getuid") and hasattr(os, "getgid"):
        options += [f"uid={os.getuid()}", f"gid={os.getgid()}"]

    args = ["--tmpfs", f"{target}:{','.join(options)}"]
    args += docker_mount(config_dir / "settings.json", f"{target}/settings.json", readonly=True)
    args += docker_mount(config_dir / "extensions", f"{target}/extensions", readonly=True)
    return args


def host_metadata() -> dict[str, str]:
    return {
        "system": platform.system(),
        "release": platform.release(),
        "machine": platform.machine(),
        "python": platform.python_version(),
    }
