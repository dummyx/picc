#!/usr/bin/env python3
"""Shared helpers for the PiCC experiment starter."""

from __future__ import annotations

import contextlib
import fcntl
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


@contextlib.contextmanager
def harness_lock(run_dir: Path) -> Iterator[None]:
    lock_path = run_dir / ".harness.lock"
    with lock_path.open("a+", encoding="utf-8") as handle:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise ExperimentError(f"Run is already locked by another harness process: {run_dir.name}") from error
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


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


def context_budget_problems(config: Mapping[str, str], compaction: Mapping[str, Any] | None = None) -> list[str]:
    """Check that one model turn cannot make the session unsummarizable.

    Pi compacts when the conversation reaches ``n_ctx - reserveTokens``; the
    reserve is what absorbs the turn that follows. If a single turn may emit
    more than the reserve, the conversation can jump past the window, and the
    summarization request (which must carry what it summarizes) then exceeds
    the context: the provider returns 400 and the session is permanently dead.

    This killed five v10 runs and two v11 runs with `LOCAL_MAX_OUTPUT=65536`
    against a 131072-token window, exactly half, so two maximal turns filled
    it. Every run with two or more cap-length turns died; every run with at
    most one survived. The harness refuses to start rather than repeat it.
    """
    problems: list[str] = []
    try:
        window = int(config["LOCAL_CONTEXT_WINDOW"])
        output = int(config["LOCAL_MAX_OUTPUT"])
    except (KeyError, ValueError):
        return problems
    if window <= 0 or output <= 0:
        return ["LOCAL_CONTEXT_WINDOW and LOCAL_MAX_OUTPUT must be positive"]

    if compaction is None:
        settings_path = REPO_ROOT / "pi" / "settings.json"
        try:
            compaction = json.loads(settings_path.read_text(encoding="utf-8")).get("compaction") or {}
        except (OSError, json.JSONDecodeError):
            compaction = {}
    reserve = int(compaction.get("reserveTokens") or 0)
    keep_recent = int(compaction.get("keepRecentTokens") or 0)

    if compaction.get("enabled") is not False and reserve and output > reserve:
        problems.append(
            f"LOCAL_MAX_OUTPUT={output} exceeds Pi's compaction reserveTokens={reserve}: one turn can "
            f"overshoot the compaction threshold and leave the session unsummarizable. Lower the output "
            f"cap or raise reserveTokens in pi/settings.json."
        )
    if output + reserve > window:
        problems.append(
            f"LOCAL_MAX_OUTPUT={output} plus reserveTokens={reserve} exceeds LOCAL_CONTEXT_WINDOW={window}: "
            f"compaction cannot leave room for a maximal turn."
        )
    if keep_recent and output > keep_recent:
        problems.append(
            f"LOCAL_MAX_OUTPUT={output} exceeds Pi's keepRecentTokens={keep_recent}: one assistant message "
            f"is larger than the whole 'keep recent' budget, so every compaction takes Pi's split-turn path "
            f"and summarizes a span containing those oversized turns. Raise keepRecentTokens above the "
            f"output cap in pi/settings.json."
        )
    if keep_recent and keep_recent + output > window:
        problems.append(
            f"keepRecentTokens={keep_recent} plus LOCAL_MAX_OUTPUT={output} exceeds "
            f"LOCAL_CONTEXT_WINDOW={window}: a compacted session has no room to continue."
        )
    return problems


def require_context_budget(config: Mapping[str, str]) -> None:
    problems = context_budget_problems(config)
    if problems:
        raise ExperimentError("Unsafe context budget: " + "; ".join(problems))


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


SUPPORTED_PROVIDERS = ("zai", "zai-coding-cn", LOCAL_PROVIDER)


def require_model_provider(config: Mapping[str, str]) -> str:
    """The declared provider. No model or provider is assumed by default."""
    provider = (config.get("MODEL_PROVIDER", "") or "").strip()
    if not provider:
        raise ExperimentError(
            "MODEL_PROVIDER is not set. The harness assumes no model: declare one in "
            ".env, using " + ", ".join(repr(name) for name in SUPPORTED_PROVIDERS)
        )
    if provider not in SUPPORTED_PROVIDERS:
        raise ExperimentError(
            f"Unsupported provider {provider!r}; use "
            + ", ".join(repr(name) for name in SUPPORTED_PROVIDERS)
        )
    return provider


def require_model_id(config: Mapping[str, str]) -> str:
    """The declared model ID, which is also the run's provenance label."""
    model = (config.get("MODEL_ID", "") or "").strip()
    if not model:
        raise ExperimentError(
            "MODEL_ID is not set. Declare the exact model the provider should serve; "
            "it is recorded as the run's provenance label."
        )
    return model


def is_local_provider(config: Mapping[str, str]) -> bool:
    return (config.get("MODEL_PROVIDER", "") or "").strip() == LOCAL_PROVIDER


LOCAL_NETWORK_MODES = ("bridge", "host")


def local_network_mode(config: Mapping[str, str]) -> str:
    """Network mode for containers that must reach the local model endpoint."""
    mode = (config.get("LOCAL_NETWORK_MODE", "") or "bridge").strip() or "bridge"
    if mode not in LOCAL_NETWORK_MODES:
        raise ExperimentError(
            "LOCAL_NETWORK_MODE must be 'bridge' (default; maps host.docker.internal "
            "to the host gateway) or 'host' (share the host network namespace so "
            "LOCAL_BASE_URL may target a loopback endpoint)"
        )
    return mode


def _container_memory(config: Mapping[str, str], role: str) -> str:
    """Memory ceiling for a container, by what it is for."""
    if role == "evaluation":
        return config.get("EVALUATION_MEMORY", "") or "8g"
    return config.get("AGENT_MEMORY", "16g")


def base_container_args(
    config: dict[str, str],
    *,
    name: str | None = None,
    model_endpoint: bool = False,
    role: str = "agent",
) -> list[str]:
    """Docker arguments shared by the agent and evaluation containers.

    `role` selects the memory ceiling. The agent needs room to run a build and
    whatever it spawns; an evaluation container runs one candidate against one
    test script and needs far less. Giving them the same ceiling means a
    candidate with a runaway query can take the agent's whole allowance: on a
    30 GB host with the model server resident, a candidate that reached 16 GB
    left under 5 GB free and the kernel started killing processes. The
    evaluator's own per-script timeout ends such a script, but the host should
    not be at risk for the two minutes that takes.
    """
    args = [
        "docker",
        "run",
        "--rm",
        "--init",
        "--platform",
        config.get("DOCKER_PLATFORM", "linux/amd64"),
        "--read-only",
        "--tmpfs",
        "/tmp:rw,exec,nosuid,nodev,size=2g",
        "--cap-drop",
        "ALL",
        "--security-opt",
        "no-new-privileges",
        "--cpus",
        config.get("AGENT_CPUS", "8"),
        "--memory",
        _container_memory(config, role),
        "--pids-limit",
        config.get("AGENT_PIDS", "512"),
    ]
    if model_endpoint and is_local_provider(config):
        if local_network_mode(config) == "host":
            # Share the host network namespace so the frozen LOCAL_BASE_URL can
            # target a loopback endpoint that host firewalling hides from the
            # docker bridge. Only containers that talk to the model get this.
            args += ["--network", "host"]
        else:
            # Reach the operator's endpoint from inside the container on Linux
            # engines; Docker Desktop resolves host.docker.internal either way.
            args += ["--add-host", "host.docker.internal:host-gateway"]
    if name:
        args += ["--name", name]
    if hasattr(os, "getuid") and hasattr(os, "getgid"):
        args += ["--user", f"{os.getuid()}:{os.getgid()}"]
    return args


def api_key_for(config: Mapping[str, str]) -> tuple[str, str]:
    provider = require_model_provider(config)
    if provider == "zai-coding-cn":
        variable = "ZAI_CODING_CN_API_KEY"
    elif provider == "zai":
        variable = "ZAI_API_KEY"
    else:
        # Keyless local servers still need a non-empty value: the generated
        # models.json resolves "$LOCAL_API_KEY" from the container environment.
        value = config.get("LOCAL_API_KEY", "").strip()
        return "LOCAL_API_KEY", value or LOCAL_API_KEY_PLACEHOLDER
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


def _local_sampling_params(config: Mapping[str, str]) -> dict[str, Any] | None:
    """Sampling parameters sent with every request, plus the thinking budget.

    Pi merges this object into the request body verbatim, so anything the
    endpoint accepts can go here. LOCAL_THINKING_BUDGET is broken out as its
    own key because it is the one setting in here that changes what the model
    does rather than how it samples, and because its shape is awkward: SGLang
    takes a per-request thinking budget as `custom_params.thinking_budget`,
    and only enforces it when the server was launched with
    --enable-strict-thinking (SGLANG_ENABLE_STRICT_THINKING in
    config/sglang.env). Setting one without the other silently does nothing.

    The budget bounds *reasoning* rather than the whole reply: when it is
    spent, the server forces the end-of-thinking token and the model answers
    with whatever output budget remains. That is the difference from
    LOCAL_MAX_OUTPUT, which cuts the reply off wherever it happens to be --
    and a reply cut off while still reasoning contains no answer at all.
    """
    params = _config_json_object(config, "LOCAL_SAMPLING_PARAMS")
    raw = (config.get("LOCAL_THINKING_BUDGET", "") or "").strip()
    if not raw:
        return params
    try:
        budget = int(raw)
    except ValueError as exc:
        raise ExperimentError("LOCAL_THINKING_BUDGET must be an integer") from exc
    if budget <= 0:
        raise ExperimentError("LOCAL_THINKING_BUDGET must be positive, or empty to disable")
    output = config_int(config, "LOCAL_MAX_OUTPUT") if "LOCAL_MAX_OUTPUT" in config else 0
    if output and budget >= output:
        raise ExperimentError(
            f"LOCAL_THINKING_BUDGET={budget} leaves nothing for the answer: it is not below "
            f"LOCAL_MAX_OUTPUT={output}. The budget exists to reserve room for the reply."
        )
    params = dict(params or {})
    custom = dict(params.get("custom_params") or {})
    custom["thinking_budget"] = budget
    params["custom_params"] = custom
    return params


def _local_thinking_level_map(config: Mapping[str, str]) -> dict[str, Any]:
    """Pi thinking level -> the value the endpoint's model expects.

    The default is the identity: a level passes through unchanged, which is
    right for a server that accepts Pi's own level names. It is not right for
    every model. Qwen3.8's chat template accepts only 'low', 'medium' and
    'xhigh', and *raises* on anything else, so an identity map would turn
    MODEL_THINKING=high into a failed request rather than a lower effort.

    LOCAL_THINKING_LEVEL_MAP overrides it with a JSON object. A null value
    marks a level as unsupported, which is Pi's own convention.
    """
    override = _config_json_object(config, "LOCAL_THINKING_LEVEL_MAP")
    if override is None:
        return {level: level for level in PI_THINKING_LEVELS}
    for level, value in override.items():
        if level not in PI_THINKING_LEVELS and level != "off":
            raise ExperimentError(
                f"LOCAL_THINKING_LEVEL_MAP has an unknown thinking level {level!r}; "
                f"expected one of: off, " + ", ".join(PI_THINKING_LEVELS)
            )
        if value is not None and not isinstance(value, str):
            raise ExperimentError(
                f"LOCAL_THINKING_LEVEL_MAP[{level!r}] must be a string or null"
            )
    return override


def resolve_local_provider(config: Mapping[str, str]) -> dict[str, Any]:
    """Validate the LOCAL_* endpoint configuration used when MODEL_PROVIDER=local."""
    if not is_local_provider(config):
        raise ExperimentError("Local endpoint configuration requires MODEL_PROVIDER=local")
    model_id = require_model_id(config)
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
        "thinking_level_map": _local_thinking_level_map(config),
        "thinking_format": thinking_format,
        "sampling_params": _local_sampling_params(config),
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
        model["thinkingLevelMap"] = resolved["thinking_level_map"]
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
