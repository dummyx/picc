"""The files the agent wrote, read from the run's own Git history.
"""

from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from .classify import file_kind
from .records import COMMIT, DataError, fingerprint, jsonl, read_json


class WorkspaceMixin:
    # ---------------------------------------------------------------- files (Git)

    def _git_dir(self, run: Path) -> Path:
        git_dir = run / "workspace" / ".git"
        if git_dir.is_dir():
            return git_dir
        bundle = run / "workspace.git.bundle"
        if not bundle.is_file():
            raise DataError(f"run {run.name} has no saved file history")
        base = self.cache_dir or Path(tempfile.gettempdir()) / "picc-dashboard"
        target = base / "git" / f"{run.name}.git"
        if not target.is_dir():
            target.parent.mkdir(parents=True, exist_ok=True)
            subprocess.run(["git", "clone", "--bare", "--quiet", str(bundle), str(target)],
                           check=True, capture_output=True, timeout=120)
        return target

    def _git(self, run: Path, *args: str, stdin: bytes | None = None, timeout: int = 60) -> bytes:
        env = {**os.environ, "GIT_OPTIONAL_LOCKS": "0", "GIT_TERMINAL_PROMPT": "0", "GIT_CONFIG_NOSYSTEM": "1",
               "GIT_PAGER": "cat", "LC_ALL": "C"}
        proc = subprocess.run(["git", f"--git-dir={self._git_dir(run)}", *args], input=stdin,
                              capture_output=True, timeout=timeout, env=env)
        if proc.returncode != 0:
            raise DataError(proc.stderr.decode("utf-8", "replace").strip()[:300] or "git failed")
        return proc.stdout

    def _snapshots(self, run: Path) -> list[dict[str, Any]]:
        rows = []
        for s in jsonl(run / "artifacts" / "snapshots.jsonl"):
            commit = str(s.get("git_commit") or "")
            if COMMIT.match(commit):
                rows.append({"round": int(s.get("round", len(rows))), "commit": commit,
                             "added": s.get("insertions"), "removed": s.get("deletions"),
                             "changed": s.get("changed_files")})
        return rows

    def _commit_for(self, run: Path, round_no: int | None) -> tuple[int, str]:
        snaps = self._snapshots(run)
        if not snaps:
            raise DataError(f"run {run.name} has no saved versions yet")
        if round_no is None:
            return snaps[-1]["round"], snaps[-1]["commit"]
        for s in snaps:
            if s["round"] == round_no:
                return s["round"], s["commit"]
        raise DataError(f"run {run.name} has no saved version for round {round_no}")

    def _adapter(self, run: Path) -> dict[str, Any]:
        adapter = read_json(run / "study-control" / "candidate.json") or {}
        sm = read_json(run / "study-metadata.json") or {}
        task = (sm.get("task") or (sm.get("condition") or {}).get("task") or {}).get("id") or "c-compiler-ch1-10"
        language = adapter.get("language") or ((sm.get("condition") or {}).get("candidate") or {}).get("language") or "rust"
        exts = set(adapter.get("source_extensions") or {"rust": [".rs"], "python": [".py"],
                                                          "javascript": [".js", ".mjs", ".cjs"],
                                                          "typescript": [".ts"]}.get(language, [".rs"]))
        audit = adapter.get("audit") or {}
        build = adapter.get("build") or {}
        entry = audit.get("entry") or build.get("artifact") or ""
        return {"language": language, "exts": exts, "roots": list(audit.get("roots") or []), "entry": entry,
                "c_task": task.startswith("c-"), "build": build.get("command"), "run": (adapter.get("run") or {}).get("command")}

    def files(self, run_id: str) -> dict[str, Any]:
        run = self.run_dir(run_id)
        fp = fingerprint([run / "artifacts" / "snapshots.jsonl", run / "study-control" / "candidate.json"])
        return self.store.get("files", run_id, fp, lambda: self._files(run))

    def files_totals(self, run_id: str, compute: bool = True) -> dict[str, Any] | None:
        run = self.run_dir(run_id)
        fp = fingerprint([run / "artifacts" / "snapshots.jsonl", run / "study-control" / "candidate.json"])
        if not compute:
            return self.store.peek("files_totals", run_id, fp)

        def build() -> dict[str, Any]:
            data = self.files(run_id)
            last = data["rounds"][-1] if data["rounds"] else {"totals": {}}
            return {"final": last["totals"],
                    "by_round": [{"round": r["round"], "totals": r["totals"], "added": r["added"],
                                  "removed": r["removed"], "changed": r["changed"]} for r in data["rounds"]]}

        return self.store.get("files_totals", run_id, fp, build)

    def _files(self, run: Path) -> dict[str, Any]:
        adapter = self._adapter(run)
        snaps = self._snapshots(run)
        rounds = []
        blob_lines: dict[str, int | None] = {}
        listings = []
        for s in snaps:
            try:
                raw = self._git(run, "ls-tree", "-r", "-l", "-z", s["commit"])
            except DataError:
                listings.append((s, []))
                continue
            rows = []
            for item in raw.split(b"\0"):
                if not item:
                    continue
                meta, _, path = item.partition(b"\t")
                parts = meta.split()
                if len(parts) < 4 or parts[1] != b"blob":
                    continue
                size = int(parts[3]) if parts[3].isdigit() else 0
                rows.append((path.decode("utf-8", "replace"), parts[2].decode(), size))
                blob_lines.setdefault(parts[2].decode(), None)
            listings.append((s, rows))
        wanted = [sha for sha in blob_lines]
        if wanted:
            try:
                out = self._git(run, "cat-file", "--batch", stdin=("\n".join(wanted) + "\n").encode(), timeout=120)
                pos = 0
                while pos < len(out):
                    nl = out.index(b"\n", pos)
                    header = out[pos:nl].split()
                    pos = nl + 1
                    if len(header) < 3 or header[1] == b"missing":
                        continue
                    size = int(header[2])
                    body = out[pos:pos + size]
                    pos += size + 1
                    sha = header[0].decode()
                    blob_lines[sha] = None if b"\0" in body[:8000] else body.count(b"\n") + (0 if body.endswith(b"\n") or not body else 1)
            except (DataError, ValueError, subprocess.TimeoutExpired):
                pass
        for s, rows in listings:
            files = []
            totals: dict[str, dict[str, int]] = {}
            for path, sha, size in rows:
                kind = file_kind(path, adapter["exts"], adapter["roots"], adapter["entry"], adapter["language"], adapter["c_task"])
                lines = blob_lines.get(sha)
                files.append([path, kind, size, lines, sha[:12]])
                t = totals.setdefault(kind, {"files": 0, "lines": 0, "bytes": 0})
                t["files"] += 1
                t["lines"] += lines or 0
                t["bytes"] += size
            rounds.append({"round": s["round"], "commit": s["commit"], "added": s["added"], "removed": s["removed"],
                           "changed": s["changed"], "files": files, "totals": totals})
        return {"language": adapter["language"], "entry": adapter["entry"], "rounds": rounds}

    def file(self, run_id: str, round_no: int | None, path: str) -> dict[str, Any]:
        run = self.run_dir(run_id)
        path = self._clean_path(path)
        rnd, commit = self._commit_for(run, round_no)
        data = self._git(run, "cat-file", "blob", f"{commit}:{path}", timeout=30)
        binary = b"\0" in data[:8000]
        text = "" if binary else data[:3_000_000].decode("utf-8", "replace")
        return {"round": rnd, "path": path, "bytes": len(data), "binary": binary, "text": text,
                "cut": len(data) > 3_000_000}

    def diff(self, run_id: str, round_no: int | None, path: str | None = None) -> dict[str, Any]:
        run = self.run_dir(run_id)
        rnd, commit = self._commit_for(run, round_no)
        args = ["diff", "--no-color", "--no-ext-diff", "-M", f"{commit}^", commit]
        try:
            numstat = self._git(run, *args[:-2], "--numstat", "-z", f"{commit}^", commit).decode("utf-8", "replace")
        except DataError:
            return {"round": rnd, "files": [], "text": "", "cut": False}
        files = []
        items = numstat.split("\0")
        i = 0
        while i < len(items):
            item = items[i]
            if not item:
                i += 1
                continue
            fields = item.split("\t")
            if len(fields) >= 3 and fields[2] == "":  # rename: next two items are old and new path
                old, new = items[i + 1], items[i + 2]
                files.append({"path": new, "from": old, "added": fields[0], "removed": fields[1]})
                i += 3
                continue
            if len(fields) >= 3:
                files.append({"path": fields[2], "added": fields[0], "removed": fields[1]})
            i += 1
        text = ""
        cut = False
        if path:
            path = self._clean_path(path)
            raw = self._git(run, *args, "--", path)
            cut = len(raw) > 2_000_000
            text = raw[:2_000_000].decode("utf-8", "replace")
        return {"round": rnd, "files": files, "text": text, "cut": cut}

    @staticmethod
    def _clean_path(path: str) -> str:
        path = (path or "").strip().lstrip("/")
        if not path or any(part in ("", ".", "..") for part in path.split("/")) or "\0" in path or path.startswith("-"):
            raise DataError("bad file path")
        return path
