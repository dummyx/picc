"""Plain-language classification of what the agent did: shell commands,
failed tool calls, and the files it wrote.
"""

from __future__ import annotations

import json
import re
from typing import Any


# --------------------------------------------------------------------------
# classification in plain words


SHELL_KINDS: tuple[tuple[str, re.Pattern[str]], ...] = tuple(
    (label, re.compile(pattern)) for label, pattern in (
        ("writes files", r"cat\s*>>?\s*\S+\s*<<|<<-?\s*['\"]?\w+['\"]?\s*>>?\s*\S+|\btee\s+(-a\s+)?\S"
                         r"|printf[^|;&]*[^2]>\s*[\w/.]|\.write_text\(|open\([^)]*,\s*['\"][wa]b?['\"]"),
        ("builds or type-checks", r"\bmypy\b|\btsc\b|\bcargo\s+(build|check|clippy)\b|py_compile|node\s+--check"
                                  r"|\brustc\b|\bnpm\s+run\s+build\b"),
        ("runs tests", r"\bcargo\s+test\b|\bpytest\b|\bunittest\b|node\s+--test\b"
                       r"|(^|[\s/;&|])(run|test|check|review)[\w.-]*\.(sh|py|js|mjs|ts)\b|\btest_\w+\.py\b"
                       r"|for\s+\w+\s+in\s+[^;]*\.(sql|c|test)\b"),
        ("runs its own program", r"(python3?|node|tsx|ts-node)(\s+-[-\w=]+)*\s+(\S*/)?(pisql|picc)\.(py|js|ts)(?=[\s<>;|&)'\"]|$)"
                                 r"|(\S*/)?(dist|src)/(pisql|picc)\.js(?=[\s<>;|&)'\"]|$)"
                                 r"|(\./)?target/(release|debug)/(pisql|picc)(?=[\s<>;|&)'\"]|$)|\bcargo\s+run\b"
                                 r"|(^|[\s;&|(])\./(pisql|picc)(?=[\s<>;|&)'\"]|$)"),
        ("probes its own code", r"\bimport\s+(pisql|picc)\b|\bfrom\s+(pisql|picc)\b|require\(\s*['\"]\./(src|dist)/"),
        ("reads or searches files", r"\b(sed\s+-n|grep|rg|cat|head|tail|wc|ls|find|awk|diff|tree|nl|stat|file|xxd|od)\b"),
        ("uses git", r"\bgit\b"),
    )
)


def shell_kinds(command: str) -> list[str]:
    found = [label for label, pattern in SHELL_KINDS if pattern.search(command)]
    return found or ["other"]


def why_failed(tool: str, text: str) -> str:
    t = text.strip()
    if t.startswith("Experiment guard:"):
        return "blocked by the rule checker"
    if "was not executed: the response hit the output token limit" in t:
        return "not run: reply was cut off"
    if re.search(r"Could not find (edits\[\d+\]|the exact text)", t):
        return "edit: text to replace not found"
    if re.search(r"occurrences|must be unique|more than once", t, re.I) and tool == "edit":
        return "edit: text to replace not unique"
    if re.search(r"Command timed out after|timed out", t):
        return "command ran out of time"
    if re.search(r"Command exited with code \d+\s*$", t):
        return "command exited with an error"
    if re.search(r"ENOENT|No such file or directory|EISDIR|is a directory", t):
        return "file not found"
    if re.search(r"\baborted\b", t, re.I):
        return "stopped before it finished"
    return "other error"


def error_line(text: str) -> str:
    """The most informative short line of a failed tool result."""
    lines = [l.strip() for l in text.strip().splitlines() if l.strip()]
    if not lines:
        return ""
    last = lines[-1]
    if re.match(r"Command exited with code \d+$", last) and len(lines) > 1:
        return (lines[-2] + " | " + last)[:240]
    return lines[0][:240] if len(lines[0]) > 20 else last[:240]


def describe_call(name: str, args: Any) -> str:
    if not isinstance(args, dict):
        return str(args)[:400]
    if name == "bash":
        return str(args.get("command") or "")[:600]
    path = str(args.get("path") or args.get("file_path") or "")
    if name == "write":
        content = str(args.get("content") or "")
        return f"{path}  ({content.count(chr(10)) + (1 if content else 0)} lines, {len(content):,} characters)"
    if name == "edit":
        edits = args.get("edits")
        n = len(edits) if isinstance(edits, list) else 1
        return f"{path}  ({n} change{'s' if n != 1 else ''})"
    if name == "read":
        extra = []
        if args.get("offset"):
            extra.append(f"from line {args['offset']}")
        if args.get("limit"):
            extra.append(f"{args['limit']} lines")
        return path + (f"  ({', '.join(extra)})" if extra else "")
    if name in ("grep", "find", "ls"):
        return " ".join(str(v) for v in args.values())[:400]
    return json.dumps(args, ensure_ascii=False)[:400]


CONFIG_NAMES = {
    "Cargo.toml", "Cargo.lock", "package.json", "package-lock.json", "tsconfig.json", ".gitignore",
    "mypy.ini", "pyproject.toml", "setup.cfg", "rust-toolchain", "rust-toolchain.toml", ".editorconfig",
}
TEST_DIRS = {"tests", "test", "sql_tests", "testdata", "test_data", "spec", "specs", "cases", "fixtures", "examples", "t"}


def file_kind(path: str, exts: set[str], roots: list[str], entry: str, language: str, c_task: bool) -> str:
    parts = path.split("/")
    name = parts[-1]
    lower = name.lower()
    suffix = ("." + lower.rsplit(".", 1)[1]) if "." in lower[1:] else ""
    if len(parts) == 1 and name in ("AGENTS.md", "TASK.md"):
        return "given to the agent"
    if parts[0] == ".pi":
        return "given to the agent"
    if name in CONFIG_NAMES:
        return "project settings"
    in_test_dir = any(p.lower() in TEST_DIRS for p in parts[:-1])
    test_name = bool(re.match(r"(test|tests|check|review|run)([\w.-]*)$", lower)
                     or re.search(r"_tests?\.\w+$|\.test$|\.slt$|\.sql$|\.expected$", lower))
    scratch = bool(re.match(r"(dbg|debug|tmp|temp|scratch|probe|try|foo|bar|t\d+|x\d*)([\w.-]*)$", lower)) \
        or suffix in (".log", ".out", ".tmp", ".o", ".s")
    if language == "rust":
        in_roots = parts[0] == "src"
    elif roots:
        in_roots = any(path == r or path.startswith(r.rstrip("/") + "/") for r in roots)
    else:
        in_roots = True
    if suffix in exts:
        if in_test_dir or test_name:
            return "tests written by the agent"
        if scratch:
            return "scratch files"
        if path == entry or in_roots:
            return "program code"
        return "helper scripts"
    if in_test_dir or test_name or (c_task and suffix in (".c", ".h")):
        return "tests written by the agent"
    if scratch or suffix == ".txt":
        return "scratch files"
    if suffix in (".sh", ".py", ".js", ".mjs", ".cjs", ".ts", ".rs", ".pl", ".awk"):
        return "helper scripts"
    if suffix == ".md":
        return "notes"
    return "other"
