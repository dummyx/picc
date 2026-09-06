#!/usr/bin/env python3
"""Treatment-fidelity metrics for the static-typing study (picc-types-v1).

Answers "was the typing treatment actually delivered, and what did the agent do
with it?" from artifacts every run already produces. Read-only, regex-based,
and deliberately approximate: the counts describe the final snapshot and the
event streams, they are not a type-checker.

Like process_metrics.py this lives outside scripts/ on purpose: scripts/ is
fingerprinted by the study layer, so adding a file there would change the
harness hash of every later materialization.

Usage:
    python3 analysis/typing_metrics.py                       # all picc-types-v1 runs
    python3 analysis/typing_metrics.py --run v4-ts-strict-r1 --run v4-js-untyped-r1
    python3 analysis/typing_metrics.py --json analysis/typing-metrics.json \
        --markdown analysis/typing-metrics.md
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
from collections import Counter
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
RUNS_ROOT = REPO_ROOT / "runs"
SKIP_PARTS = {".git", ".pi", "target", "node_modules", "__pycache__", ".pytest_cache"}
TYPING_GUARD_REASON = "static type checking is unavailable in this condition"
CONTROL_KEYWORDS = {"if", "for", "while", "switch", "catch", "return", "function", "constructor", "with", "do", "else", "typeof", "new", "await", "yield", "super", "this"}

# Shell-command intents that reveal how each arm used its toolchain.
COMMAND_PATTERNS: dict[str, re.Pattern[str]] = {
    "tsc_invocations": re.compile(r"(^|[;&|]\s*)(?:\S*/)?(?:npx\s+)?tsc(?=\s|$)"),
    "node_check_invocations": re.compile(r"\bnode\s+--check\b"),
    "compiler_runs": re.compile(r"\bnode\s+(?:\S*/)?(?:src|dist)/picc\.[jt]s\s+\S"),
    "direct_ts_runs": re.compile(r"\bnode\s+(?:--experimental-strip-types\s+)?\S+\.ts\b"),
    "self_tests": re.compile(r"\./[\w./-]*test|run_test|\btests?-local\b|\bnode\s+\S*test\S*\.[jt]s\b|\bnpm\s+test\b|\bnode\s+--test\b"),
}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.is_file():
        return rows
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            rows.append(value)
    return rows


def load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return value if isinstance(value, dict) else {}


def strip_comments_and_strings(text: str) -> str:
    """Remove comments and string/template literals so token counts see code only.

    A single regex pass in source order: whichever construct starts first wins,
    so `//` inside a string or `'` inside a comment does not confuse it. Regex
    literals are left alone (rare in the counted constructs).
    """
    pattern = re.compile(
        r"//[^\n]*"                      # line comment
        r"|/\*[\s\S]*?\*/"               # block comment
        r"|\"(?:\\.|[^\"\\\n])*\""       # double-quoted string
        r"|'(?:\\.|[^'\\\n])*'"          # single-quoted string
        r"|`(?:\\.|[^`\\])*`",           # template literal
    )
    return pattern.sub(lambda match: " " if match.group(0).startswith(("/", "//")) else '""', text)


def split_parameters(raw: str) -> list[str]:
    """Split a parameter list on top-level commas (ignores nesting depth of <>, (), [], {})."""
    parts: list[str] = []
    depth = 0
    current = []
    for char in raw:
        if char in "<([{":
            depth += 1
        elif char in ">)]}":
            depth -= 1
        if char == "," and depth == 0:
            parts.append("".join(current))
            current = []
        else:
            current.append(char)
    if current:
        parts.append("".join(current))
    return [part.strip() for part in parts if part.strip()]


def typescript_metrics(code: str, raw: str) -> dict[str, Any]:
    functions = re.findall(r"\bfunction\s*\*?\s*(\w*)\s*(?:<[^>]*>)?\s*\(([^)]*)\)\s*(:)?", code)
    named = [row for row in functions if row[0]]
    methods = [
        match
        for match in re.finditer(
            r"^\s*(?:(?:public|private|protected|static|readonly|async|override)\s+)*(\w+)\s*(?:<[^>]*>)?\s*\(([^)]*)\)\s*(:\s*[^{;=]+)?\s*\{",
            code,
            re.M,
        )
        if match.group(1) not in CONTROL_KEYWORDS
    ]
    params: list[str] = []
    for _, raw_params, _ in functions:
        params.extend(split_parameters(raw_params))
    for match in methods:
        params.extend(split_parameters(match.group(2)))
    annotated_params = sum(1 for param in params if ":" in param)
    return {
        "function_declarations": len(named),
        "function_declarations_with_return_type": sum(1 for row in named if row[2]),
        "method_declarations": len(methods),
        "method_declarations_with_return_type": sum(1 for match in methods if match.group(3)),
        "parameters": len(params),
        "parameters_annotated": annotated_params,
        "parameter_annotation_share": round(annotated_params / len(params), 3) if params else None,
        "any_count": len(re.findall(r"\bany\b", code)),
        "unknown_count": len(re.findall(r"\bunknown\b", code)),
        "as_casts": len(re.findall(r"\sas\s+(?!const\b)[A-Za-z_$]", code)),
        "as_const": len(re.findall(r"\sas\s+const\b", code)),
        "non_null_assertions": len(re.findall(r"(?<=[\w)\]])!(?![=])", code)),
        "interfaces": len(re.findall(r"\binterface\s+\w+", code)),
        "type_aliases": len(re.findall(r"\btype\s+\w+\s*(?:<[^=]*>)?\s*=", code)),
        "enums": len(re.findall(r"\benum\s+\w+", code)),
        "classes": len(re.findall(r"\bclass\s+\w+", code)),
        "ts_suppressions": {
            "nocheck": len(re.findall(r"@ts-nocheck\b", raw)),
            "ignore": len(re.findall(r"@ts-ignore\b", raw)),
            "expect_error": len(re.findall(r"@ts-expect-error\b", raw)),
        },
    }


def javascript_metrics(code: str, raw: str) -> dict[str, Any]:
    functions = re.findall(r"\bfunction\s*\*?\s*(\w*)\s*\(([^)]*)\)", code)
    return {
        "function_declarations": sum(1 for row in functions if row[0]),
        "classes": len(re.findall(r"\bclass\s+\w+", code)),
        "jsdoc_type_tags": {
            "param": len(re.findall(r"@param\s*\{", raw)),
            "type": len(re.findall(r"@type\s*\{", raw)),
            "returns": len(re.findall(r"@returns?\s*\{", raw)),
            "typedef": len(re.findall(r"@typedef\b", raw)),
        },
        "ts_check_pragmas": len(re.findall(r"@ts-check\b", raw)),
        "typeof_guards": len(re.findall(r"\btypeof\s+\w+\s*[!=]==?", code)),
    }


def source_files(workspace: Path, extensions: set[str], excluded: list[str]) -> list[Path]:
    files: list[Path] = []
    if not workspace.is_dir():
        return files
    for path in sorted(workspace.rglob("*")):
        if not path.is_file() or path.is_symlink():
            continue
        relative = path.relative_to(workspace)
        if any(part in SKIP_PARTS for part in relative.parts):
            continue
        if any(relative.parts[: len(Path(prefix).parts)] == Path(prefix).parts for prefix in excluded):
            continue
        if path.suffix in extensions:
            files.append(path)
    return files


def build_diagnostics_kind(evaluation: dict[str, Any]) -> str:
    """Why a snapshot failed to build: the type gate, a missing entry, or other."""
    build = evaluation.get("build") or {}
    text = str(build.get("stdout", "")) + str(build.get("stderr", ""))
    if not build or build.get("args") is None:
        return "not_built"
    # Entry/layout diagnostics come first: TS6053/TS18003 (root file missing)
    # and TS6059 (file outside rootDir) are not type errors.
    if "TS6053" in text or "TS18003" in text or "Cannot find module" in text or "no such file" in text.lower():
        return "missing_entry"
    if "TS6059" in text:
        return "layout_error"
    if "error TS" in text:
        return "type_error"
    if "SyntaxError" in text:
        return "syntax_error"
    return "other"


def analyse_run(run: Path) -> dict[str, Any] | None:
    study = load_json(run / "study-metadata.json")
    metadata = load_json(run / "metadata.json")
    if not study or not metadata or metadata.get("status") == "running":
        return None
    condition = study.get("condition") or {}
    adapter = load_json(run / "study-control" / "candidate.json")
    extensions = {str(item) for item in adapter.get("source_extensions", [])}
    excluded = [str(item) for item in (adapter.get("audit") or {}).get("exclude_paths", [])]
    language = str(condition.get("candidate", {}).get("language", "?"))

    workspace = run / "workspace"
    files = source_files(workspace, extensions, excluded)
    raw = "\n".join(path.read_text(encoding="utf-8", errors="replace") for path in files)
    code = strip_comments_and_strings(raw)
    loc = sum(len(path.read_text(encoding="utf-8", errors="replace").splitlines()) for path in files)
    stray_ts = [
        str(path.relative_to(workspace))
        for path in source_files(workspace, {".ts", ".mts", ".cts"}, excluded)
        if language == "javascript"
    ]
    stray_js = [
        str(path.relative_to(workspace))
        for path in source_files(workspace, {".js", ".mjs", ".cjs"}, excluded)
        if language == "typescript"
    ]
    typing = typescript_metrics(code, raw) if language == "typescript" else javascript_metrics(code, raw)

    # Shell usage from the Pi event streams.
    commands: Counter[str] = Counter()
    bash_total = 0
    for path in sorted((run / "artifacts" / "events").glob("round-*.jsonl")):
        for event in load_jsonl(path):
            if event.get("type") != "message_end":
                continue
            message = event.get("message") or {}
            if message.get("role") != "assistant":
                continue
            for item in message.get("content") or []:
                if not isinstance(item, dict) or item.get("type") != "toolCall" or item.get("name") != "bash":
                    continue
                command = str((item.get("arguments") or {}).get("command", ""))
                bash_total += 1
                for label, pattern in COMMAND_PATTERNS.items():
                    if pattern.search(command):
                        commands[label] += 1

    guard = load_jsonl(run / "artifacts" / "guard.jsonl")
    typing_blocks = [row for row in guard if row.get("reason") == TYPING_GUARD_REASON]

    # Build outcomes per snapshot, visible (in-run) and hidden (post hoc).
    snapshots = load_jsonl(run / "artifacts" / "snapshots.jsonl")
    visible_build: Counter[str] = Counter()
    for snapshot in snapshots:
        visible = snapshot.get("visible") or {}
        if visible.get("build_ok"):
            visible_build["ok"] += 1
            continue
        evaluation = load_json(run / "artifacts" / "evaluations" / f"visible-round-{int(snapshot.get('round', 0)):03d}.json")
        visible_build[build_diagnostics_kind(evaluation)] += 1
    hidden_rows = load_jsonl(run / "artifacts" / "hidden-scores.jsonl")
    hidden_build: Counter[str] = Counter()
    last_buildable_score: float | None = None
    for row in hidden_rows:
        summary = row.get("summary") or {}
        if summary.get("build_ok"):
            hidden_build["ok"] += 1
            last_buildable_score = float(summary.get("score") or 0.0)
            continue
        evaluation = load_json(run / "artifacts" / "evaluations" / f"hidden-round-{int(row.get('round', 0)):03d}.json")
        hidden_build[build_diagnostics_kind(evaluation)] += 1
    final_summary = (hidden_rows[-1].get("summary") if hidden_rows else {}) or {}
    final_full = load_json(run / "artifacts" / "evaluations" / f"hidden-round-{int(hidden_rows[-1].get('round', 0)):03d}.json") if hidden_rows else {}
    audit_reasons = Counter(str(row.get("reason")) for row in (final_full.get("source_audit") or {}).get("findings", []))

    return {
        "run_id": run.name,
        "condition": condition.get("id"),
        "language": language,
        "replicate": metadata.get("replicate"),
        "profile": metadata.get("profile"),
        "termination": metadata.get("termination_reason"),
        "elapsed_hours": round(float(metadata.get("elapsed_seconds") or 0.0) / 3600, 2),
        "source_files": len(files),
        "source_loc": loc,
        "stray_typescript_files": stray_ts,
        "stray_javascript_files": stray_js,
        "typing": typing,
        "bash_commands": bash_total,
        "command_intents": dict(commands),
        "guard_blocks_total": len(guard),
        "guard_blocks_typing": len(typing_blocks),
        "guard_typing_subjects": [str(row.get("subject", ""))[:120] for row in typing_blocks[:10]],
        "visible_build_outcomes": dict(visible_build),
        "hidden_build_outcomes": dict(hidden_build),
        "hidden_final_score": round(float(final_summary.get("score") or 0.0), 4),
        "hidden_final_build_ok": bool(final_summary.get("build_ok")),
        "hidden_final_audit_ok": bool(final_summary.get("audit_ok")),
        "hidden_last_buildable_score": None if last_buildable_score is None else round(last_buildable_score, 4),
        "final_audit_findings": dict(audit_reasons),
    }


def median(values: list[float]) -> float | None:
    return round(statistics.median(values), 4) if values else None


def render_markdown(reports: list[dict[str, Any]]) -> str:
    lines = [
        "# Typing treatment fidelity (picc-types-v1)",
        "",
        "Regex-based, descriptive counts over each run's final workspace and event streams. "
        "They document whether the treatment was delivered and how each arm used its toolchain; "
        "they are not an outcome measure.",
        "",
        "## Per run",
        "",
        "| Run | Condition | Hidden final | Last buildable | Build outcomes (hidden) | LOC | tsc calls | node --check | compiler runs | guard tsc blocks | Typing signals | Audit findings |",
        "|---|---|---:|---:|---|---:|---:|---:|---:|---:|---|---|",
    ]
    for row in reports:
        typing = row["typing"]
        if row["language"] == "typescript":
            share = typing.get("parameter_annotation_share")
            signals = (
                f"any={typing['any_count']}, unknown={typing['unknown_count']}, as={typing['as_casts']}, "
                f"non-null={typing['non_null_assertions']}, interfaces={typing['interfaces']}, "
                f"type aliases={typing['type_aliases']}, fn return types={typing['function_declarations_with_return_type']}/{typing['function_declarations']}, "
                f"param annotation share={'n/a' if share is None else share}, "
                f"suppressions={sum(typing['ts_suppressions'].values())}"
                + (f", stray .js={len(row['stray_javascript_files'])}" if row["stray_javascript_files"] else "")
            )
        else:
            tags = typing["jsdoc_type_tags"]
            signals = (
                f"jsdoc types={sum(tags.values())} (param={tags['param']}, type={tags['type']}, returns={tags['returns']}), "
                f"@ts-check={typing['ts_check_pragmas']}, fns={typing['function_declarations']}, classes={typing['classes']}"
                + (f", stray .ts={len(row['stray_typescript_files'])}" if row["stray_typescript_files"] else "")
            )
        intents = row["command_intents"]
        lines.append(
            f"| `{row['run_id']}` | `{row['condition']}` | {row['hidden_final_score']:.4f} | "
            f"{'-' if row['hidden_last_buildable_score'] is None else format(row['hidden_last_buildable_score'], '.4f')} | "
            f"{', '.join(f'{k}={v}' for k, v in sorted(row['hidden_build_outcomes'].items())) or '-'} | {row['source_loc']} | "
            f"{intents.get('tsc_invocations', 0)} | {intents.get('node_check_invocations', 0)} | {intents.get('compiler_runs', 0)} | "
            f"{row['guard_blocks_typing']} | {signals} | "
            f"{', '.join(f'{k}={v}' for k, v in sorted(row['final_audit_findings'].items())) or 'none'} |"
        )

    lines += ["", "## Per condition (main profile only)", ""]
    by_condition: dict[str, list[dict[str, Any]]] = {}
    for row in reports:
        if row.get("profile") == "main":
            by_condition.setdefault(str(row["condition"]), []).append(row)
    lines.append("| Condition | n | Median hidden final | Median last buildable | Median LOC | Median tsc calls | Runs with any unbuildable hidden snapshot | Median guard tsc blocks |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|---:|")
    for condition, rows in sorted(by_condition.items()):
        unbuildable = sum(1 for row in rows if any(k != "ok" for k in row["hidden_build_outcomes"]))
        lines.append(
            f"| `{condition}` | {len(rows)} | {median([r['hidden_final_score'] for r in rows])} | "
            f"{median([r['hidden_last_buildable_score'] for r in rows if r['hidden_last_buildable_score'] is not None])} | "
            f"{median([r['source_loc'] for r in rows])} | {median([r['command_intents'].get('tsc_invocations', 0) for r in rows])} | "
            f"{unbuildable} | {median([r['guard_blocks_typing'] for r in rows])} |"
        )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--study", default="picc-types-v1")
    parser.add_argument("--run", action="append", default=[], help="run id (repeatable); default: every run of --study")
    parser.add_argument("--json", type=Path)
    parser.add_argument("--markdown", type=Path)
    args = parser.parse_args()

    runs = [RUNS_ROOT / run_id for run_id in args.run] if args.run else sorted(
        path for path in RUNS_ROOT.iterdir()
        if path.is_dir() and not path.name.startswith(".") and load_json(path / "study-metadata.json").get("study_id") == args.study
    )
    reports = [report for report in (analyse_run(run) for run in runs) if report]
    reports.sort(key=lambda row: (str(row["condition"]), row["replicate"] or 0, row["run_id"]))
    markdown = render_markdown(reports)
    if args.json:
        args.json.write_text(json.dumps(reports, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if args.markdown:
        args.markdown.write_text(markdown, encoding="utf-8")
    print(markdown)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
