"""Results dashboard (analysis/dashboard): numbers, safety checks and the web server.

Everything runs against a small synthetic repository built in a temporary
directory, with a session whose timing is known to the second, so the
time split, token and tool counts can be checked exactly.
"""

from __future__ import annotations

import fcntl
import http.client
import json
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "analysis" / "dashboard"))

import picc_data  # noqa: E402
import server  # noqa: E402
from picc_data import DataError, Results, file_kind, shell_kinds, why_failed  # noqa: E402

RUN = "v99-sql-python-r1"
SECRET = "sk-test-secret-1234567890"
T0 = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)


def at(seconds: float) -> str:
    return (T0 + timedelta(seconds=seconds)).isoformat().replace("+00:00", "Z")


def ms(seconds: float) -> int:
    return int((T0 + timedelta(seconds=seconds)).timestamp() * 1000)


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")


def git(ws: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(ws), "-c", "user.name=t", "-c", "user.email=t@example.invalid",
                           "-c", "commit.gpgsign=false", *args],
                          check=True, capture_output=True, text=True).stdout.strip()


def build_repo(base: Path) -> Path:
    root = base / "repo"
    run = root / "runs" / RUN
    art = run / "artifacts"
    (root / "docs").mkdir(parents=True)
    (root / "analysis").mkdir()
    (root / ".env").write_text(f"MODEL_PROVIDER=local\nLOCAL_API_KEY='{SECRET}'\n", encoding="utf-8")
    (root / "docs" / "EXPERIMENT_PLAN_v99.md").write_text("# Experiment plan: v99 (a test batch)\n\nText.\n")
    (root / "docs" / "REPORT_2026-01-01.md").write_text("# Report on v99\n\n- **bold that\n  wraps**\n")

    ws = run / "workspace"
    (ws / "tests").mkdir(parents=True)
    git(ws, "init", "-q")
    (ws / "AGENTS.md").write_text("\n")
    git(ws, "add", "-A")
    git(ws, "commit", "-q", "-m", "harness: initialize empty product repository")
    (ws / "pisql.py").write_text("import sys\nprint('ok')\n")
    (ws / "tests" / "t1.sql").write_text("SELECT 1;\n")
    (ws / "dbg_notes.txt").write_text("scratch\n")
    git(ws, "add", "-A")
    git(ws, "commit", "-q", "-m", "harness: round 000")
    c0 = git(ws, "rev-parse", "HEAD")
    (ws / "pisql.py").write_text("import sys\nprint('ok')\nprint('more')\n")
    git(ws, "add", "-A")
    git(ws, "commit", "-q", "-m", "harness: round 001")
    c1 = git(ws, "rev-parse", "HEAD")

    (run / "metadata.json").write_text(json.dumps({
        "run_id": RUN, "profile": "main", "replicate": 1, "status": "completed",
        "termination_reason": "wall_time_budget", "started_at": at(0), "ended_at": at(200),
        "elapsed_seconds": 195.0, "budget": {"wall_hours": 2.0, "max_rounds": 30, "round_timeout_minutes": 45, "max_stage": 8},
        "model": {"id": "test/model", "provider": "local", "context_window": 1000, "max_tokens": 500,
                  "sampling_params": {"custom_params": {"thinking_budget": 64}}},
        "configuration": {"MODEL_ID": "test/model", "LOCAL_API_KEY_NAME": "x", "PI_VERSION": "0.85.1"},
    }))
    (run / "study-metadata.json").write_text(json.dumps({
        "study_id": "picc-sql-test", "study_path": "studies/none.json",
        "condition": {"id": "python", "description": "Plain Python", "candidate": {"language": "python"}},
        "task": {"id": "sql-engine-sqllogictest", "max_stage": 8},
    }))
    (run / "study-control").mkdir()
    (run / "study-control" / "candidate.json").write_text(json.dumps({
        "language": "python", "build": {"command": ["python3", "-m", "py_compile", "pisql.py"], "artifact": "pisql.py"},
        "source_extensions": [".py"],
    }))
    (run / "control").mkdir()
    (run / "control" / "INITIAL.txt").write_text("Build it.\n")
    (run / ".harness.lock").write_text("")

    write_jsonl(art / "rounds.jsonl", [
        {"round": 0, "started_at": at(0), "ended_at": at(100), "elapsed_seconds": 100, "timed_out": True, "returncode": 137},
        {"round": 1, "started_at": at(105), "ended_at": at(200), "elapsed_seconds": 95, "timed_out": True, "returncode": 137},
    ])
    write_jsonl(art / "snapshots.jsonl", [
        {"round": 0, "git_commit": c0, "elapsed_seconds": 101, "insertions": 4, "deletions": 0, "changed_files": 3,
         "visible": {"score": 0.5, "build_ok": True, "passed": 1, "total": 2}},
        {"round": 1, "git_commit": c1, "elapsed_seconds": 201, "insertions": 1, "deletions": 0, "changed_files": 1,
         "visible": {"score": 0.75, "build_ok": True, "passed": 1, "total": 2}},
    ])
    write_jsonl(art / "hidden-scores.jsonl", [
        {"round": 0, "elapsed_seconds": 101, "summary": {"score": 0.4, "build_ok": True}},
        {"round": 1, "elapsed_seconds": 201, "summary": {"score": 0.6, "build_ok": True}},
    ])
    for part in ("hidden", "visible"):
        for rnd, score in ((0, 0.4), (1, 0.6)):
            (art / "evaluations").mkdir(exist_ok=True)
            (art / "evaluations" / f"{part}-round-{rnd:03d}.json").write_text(json.dumps({
                "summary": {"score": score, "passed": 1, "total": 2, "build_ok": True, "failures": []},
                "build": {"args": ["python3", "-m", "py_compile", "pisql.py"], "returncode": 0, "stdout": "", "stderr": ""},
                "source_audit": {"passed": True, "findings": []},
                "tests": [
                    {"id": "test/a.test", "stage": 1, "score": 1.0, "passed": True},
                    {"id": "test/b.test", "stage": 2, "score": score * 2 - 1.0 + 0.2, "passed": False,
                     "failure_type": "wrong_results", "failures": [{"line": 3, "kind": "query", "detail": "expected 1 got 2"}],
                     "records": {"passed": 1, "total": 5}},
                ],
            }))

    usage = lambda i, o, c=0: {"input": i, "output": o, "cacheRead": c, "cacheWrite": 0}  # noqa: E731
    write_jsonl(art / "sessions" / "2026-01-01T00-00-00-000Z_x.jsonl", [
        {"type": "session", "version": 3, "id": "s", "timestamp": at(0)},
        {"type": "message", "timestamp": at(1), "message": {"role": "user", "content": [{"type": "text", "text": "Build it."}], "timestamp": ms(1)}},
        {"type": "message", "timestamp": at(12), "message": {
            "role": "assistant", "timestamp": ms(2), "usage": usage(100, 50), "stopReason": "toolUse",
            "content": [{"type": "thinking", "thinking": "let me think about sqlite"},
                        {"type": "toolCall", "id": "c1", "name": "bash", "arguments": {"command": "cd /workspace && python3 pisql.py t.sql"}}]}},
        {"type": "message", "timestamp": at(15), "message": {"role": "toolResult", "toolCallId": "c1", "toolName": "bash", "isError": True,
                                                              "content": [{"type": "text", "text": "boom\n\nCommand exited with code 1"}]}},
        {"type": "message", "timestamp": at(20), "message": {
            "role": "assistant", "timestamp": ms(15), "usage": usage(200, 30, 100), "stopReason": "toolUse",
            "content": [{"type": "toolCall", "id": "c2", "name": "write", "arguments": {"path": "/workspace/x.py", "content": "print(1)\n"}}]}},
        {"type": "message", "timestamp": at(20.5), "message": {"role": "toolResult", "toolCallId": "c2", "toolName": "write", "isError": False,
                                                                "content": [{"type": "text", "text": "Successfully wrote"}]}},
        {"type": "compaction", "timestamp": at(40), "summary": "Summary of the work.", "tokensBefore": 900, "usage": usage(900, 77)},
        {"type": "message", "timestamp": at(50), "message": {
            "role": "assistant", "timestamp": ms(41), "usage": usage(300, 20, 250), "stopReason": "stop",
            "content": [{"type": "text", "text": f"All done. The key is {SECRET}."}]}},
        {"type": "message", "timestamp": at(106), "message": {"role": "user", "content": [{"type": "text", "text": "Continue."}], "timestamp": ms(106)}},
        {"type": "message", "timestamp": at(130), "message": {
            "role": "assistant", "timestamp": ms(107), "usage": usage(400, 10, 300), "stopReason": "toolUse",
            "content": [{"type": "toolCall", "id": "c3", "name": "edit",
                         "arguments": {"path": "/workspace/pisql.py", "edits": [{"oldText": "a", "newText": "b\nc"}]}}]}},
        {"type": "message", "timestamp": at(131), "message": {"role": "toolResult", "toolCallId": "c3", "toolName": "edit", "isError": True,
                                                               "content": [{"type": "text", "text": "Could not find edits[0] in /workspace/pisql.py. The oldText must match exactly."}]}},
    ])
    write_jsonl(art / "guard.jsonl", [{"timestamp": at(30), "event": "blocked_tool_call", "toolName": "bash",
                                        "toolCallId": "c9", "reason": "no database engines", "subject": "sqlite3 x.db"}])
    write_jsonl(art / "extension-events.jsonl", [{"timestamp": at(0), "event": "compaction_bound_loaded"},
                                                  {"timestamp": at(39), "event": "compaction_bound"},
                                                  {"timestamp": at(45), "event": "truncation_repaired"}])

    def delta(text: str) -> dict:
        return {"type": "message_update", "assistantMessageEvent": {"type": "thinking_delta", "delta": text}}

    def end(role: str, out: int = 0) -> dict:
        return {"type": "message_end", "message": {"role": role, "usage": {"output": out}}}

    write_jsonl(art / "events" / "round-000.jsonl", [
        end("user"), delta("let me think"), delta(" about sqlite"), end("assistant", 50), end("toolResult"),
        end("assistant", 30), end("toolResult"), delta("one two three"), end("assistant", 20),
    ])
    write_jsonl(art / "events" / "round-001.jsonl", [end("user"), end("assistant", 10), end("toolResult")])
    return root


class DashboardData(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="picc-dash-"))
        self.root = build_repo(self.tmp)
        self.results = Results(self.root, self.tmp / "cache", tokenizer_path=None)

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_summary_scores_and_labels(self) -> None:
        s = self.results.summary(RUN, locks="")
        self.assertEqual(s["batch"], "v99")
        self.assertEqual(s["variant"], "python")
        self.assertEqual(s["task"], "sql-engine-sqllogictest")
        self.assertEqual(s["status"], "finished")
        self.assertEqual(s["rounds"], 2)
        self.assertAlmostEqual(s["final"], 0.6)
        self.assertAlmostEqual(s["visible_final"], 0.75)
        self.assertAlmostEqual(s["scores"]["best"], 0.6)
        self.assertIsNone(s["scores"]["corrected_by"])
        self.assertEqual(s["thinking_budget"], 64)

    def test_rescore_replaces_frozen_scores(self) -> None:
        d = self.root / "analysis" / "v99-rescore" / RUN
        write_jsonl(d / "hidden-scores.jsonl", [{"round": 1, "elapsed_seconds": 201, "summary": {"score": 0.9}}])
        s = Results(self.root, None, tokenizer_path=None).summary(RUN, locks="")
        self.assertAlmostEqual(s["final"], 0.9)
        self.assertAlmostEqual(s["scores"]["final_frozen"], 0.6)
        self.assertEqual(s["scores"]["corrected_by"], "analysis/v99-rescore")

    def test_time_split_tokens_and_tools(self) -> None:
        t = self.results.totals(RUN)
        self.assertEqual(t["replies"], 4)
        self.assertEqual(t["out"], 110)
        self.assertEqual(t["in"], 100 + 300 + 550 + 700)
        self.assertEqual(t["cached"], 650)
        time = t["time"]
        self.assertAlmostEqual(time["model"], 10 + 5 + 9 + 23)
        self.assertAlmostEqual(time["tools"], 3 + 0.5 + 1)
        self.assertAlmostEqual(time["summaries"], 19.5)
        self.assertAlmostEqual(time["lost"], 50 + 69)
        self.assertAlmostEqual(time["startup"], 1 + 1 + 0 + 1 + 1 + 1)
        # every second of both rounds is accounted for
        self.assertAlmostEqual(sum(time.values()), t["wall_s"])
        self.assertEqual(t["calls"], 3)
        self.assertEqual(t["failed"], 2)
        self.assertEqual(t["why_failed"], {"command exited with an error": 1, "edit: text to replace not found": 1})
        self.assertEqual(t["summaries"], 1)
        self.assertEqual(t["summary_written"], 77)
        self.assertEqual(t["blocked"], 1)
        self.assertEqual(t["repaired"], 1)
        self.assertEqual(t["ended_turn"], 1)
        self.assertEqual(t["files"]["writes"], 1)
        self.assertEqual(t["files"]["failed_edits"], 1)
        d = self.results.digest(RUN)
        self.assertEqual([r["round"] for r in d["rounds"]], [0, 1])
        self.assertEqual([r["r"] for r in d["replies"]], [0, 0, 0, 1])
        self.assertEqual(d["unfinished"][0]["stop"], "stop")

    def test_liveness_reads_locks_without_taking_them(self) -> None:
        meta = self.root / "runs" / RUN / "metadata.json"
        data = json.loads(meta.read_text())
        data["status"] = "running"
        meta.write_text(json.dumps(data))
        lock = self.root / "runs" / RUN / ".harness.lock"
        with lock.open("a+") as handle:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.assertEqual(self.results.summary(RUN)["status"], "running")
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        self.assertEqual(self.results.summary(RUN)["status"], "interrupted")

    def test_conversation_entry_and_search(self) -> None:
        c = self.results.conversation(RUN, 0)
        self.assertEqual(c["rounds"], [0, 1])
        kinds = [e["kind"] for e in c["entries"]]
        self.assertEqual(kinds, ["prompt", "reply", "result", "reply", "result", "summary", "reply"])
        reply = c["entries"][1]
        self.assertEqual(reply["thinking"]["text"], "let me think about sqlite")
        self.assertEqual(reply["calls"][0]["name"], "bash")
        self.assertTrue(c["entries"][2]["err"])
        self.assertAlmostEqual(c["entries"][2]["d"], 3.0)
        self.assertEqual([e["kind"] for e in self.results.conversation(RUN, 1)["entries"]], ["prompt", "reply", "result"])
        with self.assertRaises(DataError):
            self.results.conversation(RUN, 7)
        hits = self.results.search(RUN, "SQLITE")
        self.assertEqual(hits["hits"][0]["where"], "thinking")
        self.assertEqual(hits["hits"][0]["match"], "sqlite")

    def test_files_from_the_saved_history(self) -> None:
        f = self.results.files(RUN)
        self.assertEqual([r["round"] for r in f["rounds"]], [0, 1])
        kinds = {row[0]: row[1] for row in f["rounds"][1]["files"]}
        self.assertEqual(kinds["pisql.py"], "program code")
        self.assertEqual(kinds["tests/t1.sql"], "tests written by the agent")
        self.assertEqual(kinds["dbg_notes.txt"], "scratch files")
        self.assertEqual(kinds["AGENTS.md"], "given to the agent")
        lines = {row[0]: row[3] for row in f["rounds"][1]["files"]}
        self.assertEqual(lines["pisql.py"], 3)
        self.assertEqual(self.results.file(RUN, 0, "pisql.py")["text"], "import sys\nprint('ok')\n")
        diff = self.results.diff(RUN, 1, "pisql.py")
        self.assertEqual([x["path"] for x in diff["files"]], ["pisql.py"])
        self.assertIn("+print('more')", diff["text"])
        totals = self.results.files_totals(RUN)
        self.assertEqual(totals["final"]["program code"]["lines"], 3)

    def test_tests_matrix_and_final(self) -> None:
        t = self.results.tests(RUN, "hidden", None)
        self.assertEqual(t["round"], 1)
        self.assertEqual(t["rounds"], [0, 1])
        self.assertEqual(t["tests"][1]["failure"], "wrong_results")
        m = self.results.matrix(RUN, "visible")
        self.assertEqual(m["tests"], ["test/a.test", "test/b.test"])
        self.assertEqual(m["cells"][0], [1.0, 1.0])
        f = self.results.final_tests(RUN)
        self.assertEqual(f["columns"], ["a.test", "b.test"])
        self.assertEqual(f["kind"], "test")

    def test_paths_that_must_be_refused(self) -> None:
        r = self.results
        for bad in ("../.env", "/etc/passwd", ".env", "runs/v99-sql-python-r1/metadata.json", "docs/../.env",
                    "runs/../.env.md", "analysis/../../x.md"):
            with self.subTest(doc=bad), self.assertRaises(DataError):
                r.doc(bad)
        self.assertIn("bold that wraps", r.doc("docs/REPORT_2026-01-01.md")["text"].replace("\n  ", " "))
        for bad in ("../x", "..", "", "a/../../b", "-x"):
            with self.subTest(file=bad), self.assertRaises(DataError):
                r.file(RUN, 1, bad)
        for bad in ("../v99", "v99-sql-python-r1/..", "nope", "inference", "study-results"):
            with self.subTest(run=bad), self.assertRaises(DataError):
                r.run_dir(bad)
        for bad in ("../../.env", "metadata.json", "study-control/prompts/../../metadata.json"):
            with self.subTest(prompt=bad), self.assertRaises(DataError):
                r.prompt(RUN, bad)
        self.assertEqual(r.prompt(RUN, "INITIAL.txt")["text"], "Build it.\n")

    def test_secret_values_are_redacted_and_settings_hidden(self) -> None:
        self.assertEqual(self.results.redact(f"x {SECRET} y"), "x [hidden] y")
        setup = self.results.setup(RUN)
        self.assertNotIn("LOCAL_API_KEY_NAME", setup["config"])
        self.assertIn("PI_VERSION", setup["config"])

    def test_reasoning_counts_with_the_tokenizer(self) -> None:
        class Words:
            def encode_batch(self, texts, add_special_tokens=False):  # noqa: ANN001, ARG002
                return [type("E", (), {"ids": t.split()})() for t in texts]

        self.results._tokenizer = Words()
        self.results._tokenizer_state = "ready"
        value = self.results.count_reasoning(RUN)
        self.assertEqual(value["per_reply"], [5, 0, 3, 0])
        self.assertEqual(value["outs"], [r["out"] for r in self.results.digest(RUN)["replies"]])
        self.assertEqual(self.results.reasoning(RUN)["status"], "ready")

    def test_no_tokenizer_means_not_counted(self) -> None:
        self.assertEqual(self.results.reasoning(RUN)["status"], "unavailable")

    def test_overview_and_batch(self) -> None:
        o = self.results.overview()
        card = o["batches"][0]
        self.assertEqual(card["key"], "v99")
        self.assertEqual(card["subtitle"], "a test batch")
        self.assertEqual(card["docs"]["reports"], ["docs/REPORT_2026-01-01.md"])
        b = self.results.batch("v99")
        self.assertEqual(b["studies"][0]["variants"][0]["id"], "python")
        self.assertEqual(b["runs"][RUN]["totals"]["replies"], 4)
        with self.assertRaises(DataError):
            self.results.batch("v1000")

    def test_cache_survives_a_restart_and_notices_changes(self) -> None:
        first = self.results.totals(RUN)
        again = Results(self.root, self.tmp / "cache", tokenizer_path=None)
        self.assertEqual(again.totals(RUN, compute=False), first)
        session = next((self.root / "runs" / RUN / "artifacts" / "sessions").glob("*.jsonl"))
        with session.open("a") as handle:
            handle.write(json.dumps({"type": "message", "timestamp": at(150), "message": {
                "role": "assistant", "timestamp": ms(140), "usage": {"output": 5}, "stopReason": "stop", "content": []}}) + "\n")
        self.assertIsNone(again.totals(RUN, compute=False))
        self.assertEqual(again.totals(RUN)["replies"], 5)


class Classifiers(unittest.TestCase):
    def test_shell_kinds(self) -> None:
        self.assertEqual(shell_kinds("cd /workspace && python3 pisql.py t.sql")[0], "runs its own program")
        self.assertEqual(shell_kinds("cat > tests/t1.sql <<'EOF'\nSELECT 1;\nEOF")[0], "writes files")
        self.assertEqual(shell_kinds("cargo build --release 2>&1 | tail")[0], "builds or type-checks")
        self.assertEqual(shell_kinds("sed -n '1,40p' pisql.py")[0], "reads or searches files")
        self.assertEqual(shell_kinds("echo hi"), ["other"])

    def test_why_failed(self) -> None:
        self.assertEqual(why_failed("bash", "Experiment guard: no"), "blocked by the rule checker")
        self.assertEqual(why_failed("bash", "x\nCommand exited with code 2"), "command exited with an error")
        self.assertEqual(why_failed("bash", "Command timed out after 120 seconds"), "command ran out of time")
        self.assertEqual(why_failed("edit", "Could not find the exact text in a.py"), "edit: text to replace not found")
        self.assertEqual(why_failed("write", 'Tool call "write" was not executed: the response hit the output token limit'),
                         "not run: reply was cut off")

    def test_file_kinds(self) -> None:
        js = ({".js"}, ["src"], "src/pisql.js", "javascript", False)
        self.assertEqual(file_kind("src/pisql.js", *js), "program code")
        self.assertEqual(file_kind("src/parser.js", *js), "program code")
        self.assertEqual(file_kind("cmp.js", *js), "helper scripts")
        self.assertEqual(file_kind("tests/run.js", *js), "tests written by the agent")
        rs = ({".rs"}, [], "target/release/pisql", "rust", False)
        self.assertEqual(file_kind("src/main.rs", *rs), "program code")
        self.assertEqual(file_kind("Cargo.toml", *rs), "project settings")
        c = ({".rs"}, [], "", "rust", True)
        self.assertEqual(file_kind("t/foo.c", *c), "tests written by the agent")


class DashboardServer(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="picc-dash-http-"))
        self.root = build_repo(self.tmp)
        self.httpd = server.Dashboard(("127.0.0.1", 0), Results(self.root, None, tokenizer_path=None), None)
        self.port = self.httpd.server_address[1]
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self) -> None:
        self.httpd.shutdown()
        self.httpd.server_close()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def get(self, path: str, host: str | None = None) -> tuple[int, bytes]:
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=30)
        conn.putrequest("GET", path, skip_host=True)
        conn.putheader("Host", host or f"localhost:{self.port}")
        conn.endheaders()
        resp = conn.getresponse()
        body = resp.read()
        conn.close()
        return resp.status, body

    def test_pages_and_data(self) -> None:
        status, body = self.get("/")
        self.assertEqual(status, 200)
        self.assertIn(b"PiCC results", body)
        status, body = self.get("/api/overview")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["batches"][0]["key"], "v99")
        status, body = self.get(f"/api/run/{RUN}")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["digest"]["totals"]["replies"], 4)
        self.assertEqual(self.get("/api/run/nope")[0], 404)
        self.assertEqual(self.get("/api/nothing")[0], 404)

    def test_other_hosts_and_escapes_are_refused(self) -> None:
        self.assertEqual(self.get("/api/overview", host="evil.example")[0], 403)
        self.assertEqual(self.get("/api/overview", host=f"evil.example:{self.port}")[0], 403)
        self.assertEqual(self.get("/api/overview", host=f"127.0.0.1:{self.port}")[0], 200)
        for path in ("/static/../picc_data.py", "/static/%2e%2e/picc_data.py", "/static/../../../.env", "/.env",
                     "/api/doc?path=../.env", f"/api/run/{RUN}/file?path=../../metadata.json"):
            with self.subTest(path=path):
                status, body = self.get(path)
                self.assertIn(status, (403, 404))
                self.assertNotIn(SECRET.encode(), body)

    def test_secret_never_leaves_the_server(self) -> None:
        status, body = self.get(f"/api/run/{RUN}/conversation?round=0")
        self.assertEqual(status, 200)
        self.assertNotIn(SECRET.encode(), body)
        self.assertIn(b"[hidden]", body)
        status, body = self.get(f"/api/run/{RUN}/search?q=key")
        self.assertNotIn(SECRET.encode(), body)

    def test_code_required_away_from_this_machine(self) -> None:
        httpd = server.Dashboard(("127.0.0.2", 0), Results(self.root, None, tokenizer_path=None), "letmein")
        self.assertTrue(httpd.loopback_only)  # 127.0.0.2 is still this machine
        httpd.server_close()
        self.assertFalse(server.is_loopback("192.168.1.10"))
        self.assertTrue(server.is_loopback("::1"))


if __name__ == "__main__":
    unittest.main()
