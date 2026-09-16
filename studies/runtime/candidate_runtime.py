#!/usr/bin/env python3
"""Shared candidate runtime for the PiCC task evaluators.

Process control, the frozen-adapter build step, and the candidate source audit
are task-independent: the C compiler evaluator (`evaluate.py`), the fuzz
oracle (`fuzz_evaluate.py`), and the SQL engine evaluator (`sql/evaluate.py`)
all import them from here. The behaviour of every function is unchanged from
the evaluator it was extracted from; only the module boundary is new.

The source audit covers Rust (Cargo manifests), Python (imports), and
JavaScript/TypeScript (imports, package manifests, vendored modules) candidates.
"""

from __future__ import annotations

import ast
import contextlib
import json
import os
import re
import signal
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

MAX_CAPTURE_BYTES = 1024 * 1024
DEPENDENCY_TABLES = {"dependencies", "dev-dependencies", "build-dependencies"}
SKIP_PARTS = {".git", ".pi", "target", "node_modules", "__pycache__", ".pytest_cache"}
SUBPROCESS_ENV_ALLOWLIST = {
    "CARGO_HOME",
    "LANG",
    "LC_ALL",
    "PATH",
    "RUSTUP_HOME",
    "TERM",
}
# Audit findings split into two kinds. A blocking finding means the candidate
# either delegated the task or is unsafe to execute, so its measured behaviour
# would be meaningless; those still gate scoring. An advisory finding is a broken
# rule that leaves the compiler both safe to run and honestly measurable — it is
# reported as its own compliance outcome rather than nullifying the score, so a
# single debug flag cannot erase an otherwise working compiler.
ADVISORY_AUDIT_REASONS = frozenset({"credential or environment inspection", "type-check suppression"})

DEFAULT_SOURCE_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (
        re.compile(
            r"\b(?:std::)?env::(?:var|var_os|vars|vars_os)\b|"
            r"\bstd::env::\{[^}\n]*\b(?:var|var_os|vars|vars_os)\b|\bos\.(?:environ|getenv)\b|"
            r"/proc(?:/[^\s]*)?/environ|"
            r"ZAI_(?:API_KEY|CODING_CN_API_KEY)|LOCAL_API_KEY",
            re.I,
        ),
        "credential or environment inspection",
    ),
    (
        re.compile(
            r"\b(?:std::)?process::Command\b|\bCommand::new\s*\(|"
            r"\bsubprocess\b|\bos\.system\s*\(|\bPopen\s*\(|\bexec[lvpe]+\s*\(",
            re.I,
        ),
        "subprocess invocation",
    ),
    (
        re.compile(r"\b(?:libclang|libgccjit|libtcc|LLVM|llvm[_-]sys|clang[_-]sys|tinycc|tcc)\b", re.I),
        "compiler library reference",
    ),
    (
        re.compile(
            r"\b(?:TcpStream|UdpSocket|requests|httpx|urllib|socket)\b|https?://",
            re.I,
        ),
        "network access",
    ),
]
PROHIBITED_PYTHON_MODULES = {
    "ctypes",
    "http",
    "multiprocessing",
    "requests",
    "socket",
    "subprocess",
    "urllib",
}
NODE_SOURCE_EXTENSIONS = {".js", ".mjs", ".cjs", ".ts", ".mts", ".cts"}
# Node.js 24 built-in module roots (the `node:` prefix is stripped before lookup).
NODE_BUILTIN_MODULES = {
    "assert",
    "async_hooks",
    "buffer",
    "child_process",
    "cluster",
    "console",
    "constants",
    "crypto",
    "dgram",
    "diagnostics_channel",
    "dns",
    "domain",
    "events",
    "fs",
    "http",
    "http2",
    "https",
    "inspector",
    "module",
    "net",
    "os",
    "path",
    "perf_hooks",
    "process",
    "punycode",
    "querystring",
    "readline",
    "repl",
    "sea",
    "sqlite",
    "stream",
    "string_decoder",
    "sys",
    "test",
    "timers",
    "tls",
    "trace_events",
    "tty",
    "url",
    "util",
    "v8",
    "vm",
    "wasi",
    "worker_threads",
    "zlib",
}
PROHIBITED_NODE_MODULES = {
    "child_process",
    "cluster",
    "dgram",
    "dns",
    "http",
    "http2",
    "https",
    "inspector",
    "net",
    "repl",
    "tls",
    "wasi",
}
NODE_IMPORT_PATTERNS = [
    re.compile(r"""\brequire\s*\(\s*['"]([^'"]+)['"]\s*\)"""),
    re.compile(r"""\bimport\s*\(\s*['"]([^'"]+)['"]\s*\)"""),
    re.compile(r"""\bimport\s+(?:type\s+)?(?:[\w*{}\s,$]+?\s+from\s+)?['"]([^'"]+)['"]"""),
    re.compile(r"""\bexport\s+(?:type\s+)?(?:\*|\{[^}]*\})\s*(?:as\s+\w+\s+)?from\s+['"]([^'"]+)['"]"""),
]
# Line patterns applied only to JavaScript/TypeScript sources. Method-shaped
# names that are common in compilers (`exec`, `fetch`, `spawn` as identifiers)
# are deliberately not matched; delegation through Node requires importing a
# prohibited module, which the import audit catches. Blocking patterns run on
# comment-stripped code so that a comment mentioning a prohibited module cannot
# zero a run; advisory patterns run on the raw text because the suppression
# pragmas are comments.
NODE_BLOCKING_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\bchild_process\b"), "subprocess invocation"),
    (re.compile(r"\bWebSocket\b|\bXMLHttpRequest\b|\bEventSource\b"), "network access"),
    (
        re.compile(r"\bprocess\.(?:dlopen|binding)\s*\(|\bWebAssembly\.(?:instantiate|compile|Module|Instance)\b"),
        "dynamic loading or embedded binary execution",
    ),
]
NODE_ADVISORY_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\bprocess\.env\b"), "credential or environment inspection"),
    (re.compile(r"@ts-(?:nocheck|ignore|expect-error)\b"), "type-check suppression"),
]
# Compiled/native artifacts that could carry an embedded compiler. Object files
# and archives are deliberately absent: agents assemble their own output while
# self-testing, and those files are ignored by the workspace .gitignore anyway.
BINARY_ARTIFACT_EXTENSIONS = {".wasm", ".node", ".so", ".dylib", ".dll"}
JS_COMMENT_PATTERN = re.compile(r"//[^\n]*|/\*[\s\S]*?\*/")
# Resolution order for a relative Node/TypeScript import specifier.
NODE_LOCAL_IMPORT_SUFFIXES = (
    "", ".js", ".cjs", ".mjs", ".ts", ".mts", ".cts",
    "/index.js", "/index.cjs", "/index.mjs", "/index.ts",
)


@dataclass
class CommandResult:
    args: list[str]
    returncode: int
    stdout: str
    stderr: str
    elapsed_seconds: float
    timed_out: bool = False



def load_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return value


def resolve_test_source(tests_root: Path, test: Mapping[str, Any]) -> Path:
    raw_relative = test.get("relative_path")
    if not isinstance(raw_relative, str) or not raw_relative.strip():
        raise ValueError("Test relative_path must be a nonempty string")
    relative = Path(raw_relative)
    if relative.is_absolute() or relative == Path(".") or ".." in relative.parts:
        raise ValueError(f"Test relative_path must stay within the partition: {raw_relative!r}")

    candidate = tests_root / relative
    if candidate.is_symlink():
        raise ValueError(f"Test source must not be a symlink: {raw_relative}")
    try:
        source = candidate.resolve(strict=True)
        source.relative_to(tests_root)
    except (FileNotFoundError, ValueError) as error:
        raise ValueError(f"Test source must resolve within the partition: {raw_relative}") from error
    if not source.is_file():
        raise ValueError(f"Test source is not a regular file: {raw_relative}")

    return source


def truncate(value: str, limit: int = 8000) -> str:
    if len(value) <= limit:
        return value
    return value[:limit] + f"\n... [truncated {len(value) - limit} characters]"


def atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(value, handle, indent=2, sort_keys=True, ensure_ascii=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        with contextlib.suppress(FileNotFoundError):
            os.unlink(temporary)


def subprocess_environment(overrides: Mapping[str, str] | None = None) -> dict[str, str]:
    env = {key: os.environ[key] for key in SUBPROCESS_ENV_ALLOWLIST if key in os.environ}
    env.setdefault("PATH", os.defpath)
    env.update({"HOME": "/tmp", "TMPDIR": "/tmp"})
    if overrides:
        env.update(overrides)
    return env


def run_command(
    args: Sequence[str],
    *,
    cwd: Path,
    timeout: int,
    env: Mapping[str, str] | None = None,
    stdout_path: Path | None = None,
) -> CommandResult:
    """Run one process with a wall-clock limit, killing its whole session on timeout.

    With ``stdout_path`` the child's standard output is written to that file
    (uncapped; the SQL evaluator reads whole result streams from it) and the
    returned ``stdout`` is empty; otherwise it is captured and capped.
    """
    started = time.monotonic()
    with contextlib.ExitStack() as stack:
        stdout_target: Any = subprocess.PIPE
        if stdout_path is not None:
            stdout_target = stack.enter_context(stdout_path.open("wb"))
        process = subprocess.Popen(
            list(args),
            cwd=cwd,
            env=subprocess_environment(env),
            stdin=subprocess.DEVNULL,
            stdout=stdout_target,
            stderr=subprocess.PIPE,
            text=True,
            errors="replace",
            start_new_session=True,
        )
        timed_out = False
        try:
            stdout, stderr = process.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            with contextlib.suppress(ProcessLookupError):
                os.killpg(process.pid, signal.SIGTERM)
            try:
                stdout, stderr = process.communicate(timeout=2)
            except subprocess.TimeoutExpired:
                with contextlib.suppress(ProcessLookupError):
                    os.killpg(process.pid, signal.SIGKILL)
                stdout, stderr = process.communicate()
    return CommandResult(
        args=list(args),
        returncode=process.returncode if process.returncode is not None else 128,
        stdout=(stdout or "")[:MAX_CAPTURE_BYTES],
        stderr=(stderr or "")[:MAX_CAPTURE_BYTES],
        elapsed_seconds=time.monotonic() - started,
        timed_out=timed_out,
    )


def render_command(parts: Sequence[str], variables: Mapping[str, str]) -> list[str]:
    rendered: list[str] = []
    for part in parts:
        value = part
        for key, replacement in variables.items():
            value = value.replace("{" + key + "}", replacement)
        unresolved = re.findall(r"\{([a-zA-Z0-9_]+)\}", value)
        if unresolved:
            raise ValueError(f"Unresolved candidate command variables: {unresolved}")
        rendered.append(value)
    return rendered


def iter_dependency_tables(value: Any, path: tuple[str, ...] = ()) -> Iterable[tuple[tuple[str, ...], dict[str, Any]]]:
    if not isinstance(value, dict):
        return
    for key, child in value.items():
        child_path = (*path, str(key))
        if str(key) in DEPENDENCY_TABLES and isinstance(child, dict):
            yield child_path, child
        if isinstance(child, dict):
            yield from iter_dependency_tables(child, child_path)


def excluded_prefixes(policy: Mapping[str, Any]) -> list[tuple[str, ...]]:
    """Workspace-relative directories the adapter declares as build output.

    They are skipped by every audit walk so that a previous in-container build
    (for example `dist/` emitted by tsc) is never mistaken for candidate source.
    """
    prefixes: list[tuple[str, ...]] = []
    for raw in policy.get("exclude_paths", []) if isinstance(policy, Mapping) else []:
        parts = tuple(part for part in str(raw).split("/") if part and part != ".")
        if parts and ".." not in parts:
            prefixes.append(parts)
    return prefixes


def is_excluded(relative: Path, prefixes: Sequence[tuple[str, ...]]) -> bool:
    if any(part in SKIP_PARTS for part in relative.parts):
        return True
    return any(relative.parts[: len(prefix)] == prefix for prefix in prefixes)


def iter_source_files(
    workspace: Path,
    extensions: set[str],
    roots: Sequence[str] | None = None,
    prefixes: Sequence[tuple[str, ...]] = (),
) -> Iterable[Path]:
    candidates: list[Path] = []
    for raw_root in roots or ["."]:
        root = (workspace / raw_root).resolve()
        try:
            root.relative_to(workspace)
        except ValueError:
            continue
        if root.is_file():
            candidates.append(root)
        elif root.is_dir():
            candidates.extend(root.rglob("*"))
    seen: set[Path] = set()
    for path in sorted(candidates):
        if path in seen or not path.is_file() or path.is_symlink():
            continue
        seen.add(path)
        relative = path.relative_to(workspace)
        if is_excluded(relative, prefixes):
            continue
        if path.suffix in extensions:
            yield path


def built_cargo_manifests(workspace: Path) -> list[Path]:
    """The Cargo manifests the frozen build command compiles: the root
    manifest and, when it declares a workspace, the member manifests.

    A crate elsewhere in the workspace (developer tooling such as a
    self-written simulator that depends on the candidate by path) is not
    built by ``cargo build`` at the root and is not part of the product; v9
    Amendment 2 scopes the dependency audit accordingly.
    """
    root = workspace / "Cargo.toml"
    if not root.is_file() or root.is_symlink():
        return []
    manifests = [root]
    try:
        import tomllib

        cargo = tomllib.loads(root.read_text(encoding="utf-8"))
    except Exception:
        return manifests
    members = (cargo.get("workspace") or {}).get("members") or []
    excluded = set((cargo.get("workspace") or {}).get("exclude") or [])
    for pattern in members:
        if not isinstance(pattern, str):
            continue
        for member_dir in sorted(workspace.glob(pattern)):
            relative = member_dir.relative_to(workspace).as_posix()
            if relative in excluded or any(part in SKIP_PARTS for part in member_dir.relative_to(workspace).parts):
                continue
            manifest = member_dir / "Cargo.toml"
            if manifest.is_file() and not manifest.is_symlink() and manifest not in manifests:
                manifests.append(manifest)
    return manifests


def audit_cargo(workspace: Path, policy: dict[str, Any], findings: list[dict[str, Any]]) -> None:
    allowed = {str(item).lower().replace("_", "-") for item in policy.get("allowed_dependencies", [])}
    manifests = built_cargo_manifests(workspace)

    for cargo_toml in manifests:
        relative = cargo_toml.relative_to(workspace).as_posix()
        try:
            import tomllib

            cargo = tomllib.loads(cargo_toml.read_text(encoding="utf-8"))
        except Exception as error:
            findings.append({"path": relative, "kind": "toml_error", "reason": str(error)})
            continue
        for table_path, dependencies in iter_dependency_tables(cargo):
            for name in dependencies:
                normalized = str(name).lower().replace("_", "-")
                if normalized not in allowed:
                    findings.append(
                        {
                            "path": relative,
                            "kind": "dependency",
                            "table": ".".join(table_path),
                            "value": name,
                            "reason": "dependency is outside the frozen candidate policy",
                        }
                    )


def imported_roots(tree: ast.AST) -> set[str]:
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".", 1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            roots.add(node.module.split(".", 1)[0])
    return roots


def audit_python(workspace: Path, files: list[Path], policy: dict[str, Any], findings: list[dict[str, Any]]) -> None:
    allow_stdlib = bool(policy.get("python_stdlib_only", False))
    allowed = {str(item).split(".", 1)[0] for item in policy.get("allowed_python_modules", [])}
    # Task-specific prohibitions (the SQL task forbids the sqlite3 module) are
    # declared by the adapter and join the fixed delegation/network set.
    prohibited = PROHIBITED_PYTHON_MODULES | {
        str(item).split(".", 1)[0] for item in policy.get("prohibited_python_modules", [])
    }
    stdlib = set(getattr(sys, "stdlib_module_names", set()))
    local_modules = {path.stem for path in files}
    local_modules |= {path.parent.name for path in files if (path.parent / "__init__.py").is_file()}
    for path in files:
        relative = path.relative_to(workspace).as_posix()
        try:
            tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"), filename=relative)
        except SyntaxError as error:
            findings.append({"path": relative, "line": error.lineno, "kind": "python_syntax", "reason": str(error)})
            continue
        for module in imported_roots(tree):
            if module in prohibited:
                findings.append(
                    {
                        "path": relative,
                        "kind": "python_import",
                        "value": module,
                        "reason": (
                            "subprocess, network, or dynamic-loading module is prohibited"
                            if module in PROHIBITED_PYTHON_MODULES
                            else "module is prohibited by the frozen candidate policy"
                        ),
                    }
                )
            elif allow_stdlib and module not in stdlib and module not in local_modules and module not in allowed:
                findings.append(
                    {
                        "path": relative,
                        "kind": "python_import",
                        "value": module,
                        "reason": "non-standard-library import is outside the frozen candidate policy",
                    }
                )


def node_module_root(specifier: str) -> str | None:
    """Return the package root of an import specifier, or None for local paths."""
    value = specifier.strip()
    if value.startswith("node:"):
        value = value[len("node:"):]
    if not value or value.startswith((".", "/")):
        return None
    if value.startswith("@"):
        parts = value.split("/")
        return "/".join(parts[:2]) if len(parts) >= 2 else value
    return value.split("/", 1)[0]


def strip_js_comments(text: str) -> str:
    """Blank out `//` and `/* */` comments while preserving line numbers."""
    return JS_COMMENT_PATTERN.sub(lambda match: "\n" * match.group(0).count("\n"), text)


def node_import_specifiers(text: str) -> list[str]:
    specifiers: list[str] = []
    for pattern in NODE_IMPORT_PATTERNS:
        specifiers.extend(match.group(1) for match in pattern.finditer(text))
    return specifiers


def node_import_closure(workspace: Path, entry: Path, prefixes: Sequence[tuple[str, ...]]) -> list[Path]:
    """Source files reachable from the entry through relative require/import specifiers.

    The audit's file scan is scoped to the adapter's declared source roots so
    that agent-authored test drivers elsewhere in the workspace (which
    legitimately spawn the candidate) are not mistaken for the compiler. The
    closure closes the obvious hole: a module outside the roots that the
    compiler itself imports is still scanned. Dynamic `require(variable)` is
    not resolvable statically and remains a documented limitation.
    """
    closure: list[Path] = []
    seen: set[Path] = set()
    queue = [entry]
    while queue:
        path = queue.pop()
        if path.is_symlink() or not path.is_file():
            continue
        resolved = path.resolve()
        if resolved in seen:
            continue
        try:
            relative = resolved.relative_to(workspace)
        except ValueError:
            continue
        if is_excluded(relative, prefixes) or resolved.suffix not in NODE_SOURCE_EXTENSIONS:
            continue
        seen.add(resolved)
        closure.append(resolved)
        text = strip_js_comments(resolved.read_text(encoding="utf-8", errors="replace"))
        for specifier in node_import_specifiers(text):
            if not specifier.startswith("."):
                continue
            base = resolved.parent / specifier
            for suffix in NODE_LOCAL_IMPORT_SUFFIXES:
                candidate = Path(str(base) + suffix)
                if candidate.is_file() and not candidate.is_symlink():
                    queue.append(candidate)
                    break
    return closure


def built_package_manifests(workspace: Path) -> list[Path]:
    """The package manifests the frozen build uses: the root ``package.json``
    and, when it declares ``workspaces``, the member manifests (v9 Amendment
    2: manifests outside the build are developer tooling, not the product)."""
    root = workspace / "package.json"
    if not root.is_file() or root.is_symlink():
        return []
    manifests = [root]
    try:
        package = json.loads(root.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return manifests
    workspaces = package.get("workspaces") if isinstance(package, dict) else None
    if isinstance(workspaces, dict):
        workspaces = workspaces.get("packages")
    for pattern in workspaces or []:
        if not isinstance(pattern, str):
            continue
        for member_dir in sorted(workspace.glob(pattern)):
            if any(part in SKIP_PARTS for part in member_dir.relative_to(workspace).parts):
                continue
            manifest = member_dir / "package.json"
            if manifest.is_file() and not manifest.is_symlink() and manifest not in manifests:
                manifests.append(manifest)
    return manifests


def audit_node(workspace: Path, files: list[Path], policy: dict[str, Any], findings: list[dict[str, Any]]) -> None:
    builtins_only = bool(policy.get("node_builtins_only", False))
    allowed = {str(item) for item in policy.get("allowed_node_modules", [])}
    prohibited = PROHIBITED_NODE_MODULES | {str(item) for item in policy.get("prohibited_node_modules", [])}
    prefixes = excluded_prefixes(policy)
    for path in files:
        relative = path.relative_to(workspace).as_posix()
        text = path.read_text(encoding="utf-8", errors="replace")
        code = strip_js_comments(text)
        for specifier in node_import_specifiers(code):
            root = node_module_root(specifier)
            if root is None:
                continue
            if root in prohibited:
                findings.append(
                    {
                        "path": relative,
                        "kind": "node_import",
                        "value": specifier,
                        "reason": (
                            "subprocess, network, or dynamic-loading module is prohibited"
                            if root in PROHIBITED_NODE_MODULES
                            else "module is prohibited by the frozen candidate policy"
                        ),
                    }
                )
            elif builtins_only and root not in NODE_BUILTIN_MODULES and root not in allowed:
                findings.append(
                    {
                        "path": relative,
                        "kind": "node_import",
                        "value": specifier,
                        "reason": "non-built-in module import is outside the frozen candidate policy",
                    }
                )
        raw_lines = text.splitlines()
        for source, patterns in ((code.splitlines(), NODE_BLOCKING_PATTERNS), (raw_lines, NODE_ADVISORY_PATTERNS)):
            for line_number, line in enumerate(source, 1):
                for pattern, reason in patterns:
                    if pattern.search(line):
                        excerpt = raw_lines[line_number - 1] if line_number <= len(raw_lines) else line
                        findings.append(
                            {
                                "path": relative,
                                "line": line_number,
                                "kind": "source_pattern",
                                "reason": reason,
                                "excerpt": truncate(excerpt.strip(), 300),
                            }
                        )

    for manifest in built_package_manifests(workspace):
        relative_path = manifest.relative_to(workspace)
        relative = relative_path.as_posix()
        try:
            package = json.loads(manifest.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            findings.append({"path": relative, "kind": "json_error", "reason": str(error)})
            continue
        if not isinstance(package, dict):
            continue
        for table in ("dependencies", "devDependencies", "peerDependencies", "optionalDependencies"):
            dependencies = package.get(table)
            if not isinstance(dependencies, dict):
                continue
            for name in dependencies:
                if str(name) not in allowed:
                    findings.append(
                        {
                            "path": relative,
                            "kind": "dependency",
                            "table": table,
                            "value": name,
                            "reason": "dependency is outside the frozen candidate policy",
                        }
                    )
    for vendored in sorted(workspace.rglob("node_modules")):
        if not vendored.is_dir() or vendored.is_symlink():
            continue
        relative_path = vendored.relative_to(workspace)
        parents = relative_path.parts[:-1]
        if parents and is_excluded(Path(*parents), prefixes):
            continue
        if any(child.is_file() and not child.name.startswith(".") for child in vendored.rglob("*")):
            findings.append(
                {
                    "path": relative_path.as_posix(),
                    "kind": "dependency",
                    "reason": "dependency is outside the frozen candidate policy",
                }
            )


def audit_binary_artifacts(workspace: Path, prefixes: Sequence[tuple[str, ...]], findings: list[dict[str, Any]]) -> None:
    for path in sorted(workspace.rglob("*")):
        relative = path.relative_to(workspace)
        if is_excluded(relative, prefixes) or path.is_symlink() or not path.is_file():
            continue
        if path.suffix.lower() in BINARY_ARTIFACT_EXTENSIONS:
            findings.append(
                {
                    "path": relative.as_posix(),
                    "kind": "binary_artifact",
                    "reason": "binary artifact is prohibited in candidate source",
                }
            )


def audit_symlinks(workspace: Path, findings: list[dict[str, Any]]) -> None:
    for path in sorted(workspace.rglob("*")):
        relative = path.relative_to(workspace)
        if any(part in SKIP_PARTS for part in relative.parts):
            continue
        if path.is_symlink():
            findings.append(
                {
                    "path": relative.as_posix(),
                    "kind": "symlink",
                    "reason": "symlinks are prohibited in candidate source and manifests",
                }
            )


RUST_INCLUDE_PATTERNS = [
    re.compile(r'#\s*\[\s*path\s*=\s*"([^"]+)"\s*\]'),
    re.compile(r'\binclude(?:_str|_bytes)?!\s*\(\s*"([^"]+)"\s*\)'),
]


def rust_include_closure(workspace: Path, seeds: Sequence[Path], prefixes: Sequence[tuple[str, ...]]) -> list[Path]:
    """Files outside the scanned roots that a scanned Rust file pulls in by path
    (`#[path = "..."]` modules, `include!`/`include_str!`/`include_bytes!`)."""
    found: list[Path] = []
    seen: set[Path] = {path.resolve() for path in seeds}
    queue = list(seeds)
    while queue:
        current = queue.pop()
        try:
            text = current.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for pattern in RUST_INCLUDE_PATTERNS:
            for match in pattern.finditer(text):
                target = (current.parent / match.group(1)).resolve()
                try:
                    relative = target.relative_to(workspace)
                except ValueError:
                    continue
                if target in seen or not target.is_file() or target.is_symlink() or is_excluded(relative, prefixes):
                    continue
                seen.add(target)
                found.append(target)
                if target.suffix == ".rs":
                    queue.append(target)
    return found


def source_audit(workspace: Path, adapter: dict[str, Any]) -> dict[str, Any]:
    findings: list[dict[str, Any]] = []
    policy = adapter.get("audit", {})
    if not isinstance(policy, dict):
        policy = {}
    extensions = {str(item) for item in adapter.get("source_extensions", [])}
    roots = policy.get("roots") if isinstance(policy.get("roots"), list) else None
    prefixes = excluded_prefixes(policy)
    if roots is None and ".rs" in extensions:
        # A Cargo package's binary is built from src/ alone; tests/, benches/,
        # examples/, and ad-hoc helpers are the agent's own tooling, not the
        # submitted compiler (the v4 lesson, report 8.5, applied to Rust after
        # v6-tests-none-r3 was zeroed for a fuzzer under tests/). Files that
        # src/ pulls in from elsewhere by path stay audited.
        roots = ["src"]
    files = list(iter_source_files(workspace, extensions, roots, prefixes))
    if ".rs" in extensions:
        known = {path.resolve() for path in files}
        for path in rust_include_closure(workspace, files, prefixes):
            if path not in known:
                files.append(path)
                known.add(path)
    entry = policy.get("entry")
    if isinstance(entry, str) and entry and extensions & NODE_SOURCE_EXTENSIONS:
        known = {path.resolve() for path in files}
        for path in node_import_closure(workspace, workspace / entry, prefixes):
            if path not in known:
                files.append(path)
                known.add(path)
    audit_symlinks(workspace, findings)
    audit_binary_artifacts(workspace, prefixes, findings)
    audit_cargo(workspace, policy, findings)
    if ".py" in extensions:
        audit_python(workspace, [path for path in files if path.suffix == ".py"], policy, findings)
    if extensions & NODE_SOURCE_EXTENSIONS:
        audit_node(workspace, [path for path in files if path.suffix in NODE_SOURCE_EXTENSIONS], policy, findings)

    patterns = list(DEFAULT_SOURCE_PATTERNS)
    for row in policy.get("prohibited_patterns", []):
        if isinstance(row, dict) and isinstance(row.get("pattern"), str):
            patterns.append((re.compile(row["pattern"], re.I), str(row.get("reason", "prohibited source pattern"))))
    for path in files:
        relative = path.relative_to(workspace).as_posix()
        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError as error:
            findings.append({"path": relative, "kind": "read_error", "reason": str(error)})
            continue
        for line_number, line in enumerate(lines, 1):
            for pattern, reason in patterns:
                if pattern.search(line):
                    findings.append(
                        {
                            "path": relative,
                            "line": line_number,
                            "kind": "source_pattern",
                            "reason": reason,
                            "excerpt": truncate(line.strip(), 300),
                        }
                    )
    blocking = [
        finding for finding in findings if finding.get("reason") not in ADVISORY_AUDIT_REASONS
    ]
    return {
        "passed": not findings,
        "blocking": bool(blocking),
        "findings": findings,
        "blocking_findings": blocking,
        "advisory_findings": [finding for finding in findings if finding not in blocking],
        "source_files_scanned": len(files),
        "source_extensions": sorted(extensions),
    }


def resolve_candidate_artifact(workspace: Path, logical: Path) -> Path:
    if logical.is_symlink():
        raise ValueError("Candidate artifact must not be a symlink")
    artifact = logical.resolve()
    try:
        artifact.relative_to(workspace)
    except ValueError as error:
        raise ValueError("Candidate artifact must resolve inside the workspace") from error
    if artifact.exists() and not artifact.is_file():
        raise ValueError("Candidate artifact must be a regular file")
    return artifact


def build_candidate(workspace: Path, adapter: dict[str, Any], timeout: int) -> tuple[CommandResult, Path]:
    build = adapter["build"]
    logical_artifact = workspace / str(build["artifact"])
    artifact = resolve_candidate_artifact(workspace, logical_artifact)
    variables = {"workspace": str(workspace), "artifact": str(artifact)}
    command = render_command(build["command"], variables)
    env = {
        "CARGO_NET_OFFLINE": "true",
        "RUST_BACKTRACE": "1",
        "PYTHONDONTWRITEBYTECODE": "1",
        "PIP_NO_INDEX": "1",
        "PIP_DISABLE_PIP_VERSION_CHECK": "1",
    }
    if command:
        result = run_command(command, cwd=workspace, timeout=int(build.get("timeout_seconds", timeout)), env=env)
    else:
        result = CommandResult([], 0, "", "", 0.0, False)
    try:
        verified_artifact = resolve_candidate_artifact(workspace, logical_artifact)
    except ValueError as error:
        detail = f"candidate artifact policy failure: {error}"
        result = CommandResult(
            result.args,
            result.returncode if result.returncode != 0 else 1,
            result.stdout,
            (result.stderr + "\n" + detail).strip(),
            result.elapsed_seconds,
            result.timed_out,
        )
        return result, logical_artifact
    return result, verified_artifact


def select_tests(manifest: dict[str, Any], max_stage: int, latest_only: bool, test_id: str | None) -> list[dict[str, Any]]:
    tests = [row for row in manifest.get("tests", []) if int(row["stage"]) <= max_stage]
    if latest_only:
        tests = [row for row in tests if int(row["stage"]) == max_stage]
    if test_id:
        exact = [row for row in tests if row["id"] == test_id]
        if not exact:
            exact = [row for row in tests if test_id in row["id"]]
        if len(exact) != 1:
            raise ValueError(f"--test-id matched {len(exact)} tests; use one exact manifest ID")
        tests = exact
    return sorted(tests, key=lambda row: (int(row["stage"]), str(row["validity"]), str(row["id"])))
