#!/usr/bin/env python3
"""PiCC results dashboard: batches, runs, conversations, files and reports in a browser.

    make dashboard            # runs in this terminal, http://127.0.0.1:8765
    make dashboard-start      # runs in the background; make dashboard-stop ends it

or directly:

    python3 analysis/dashboard/server.py [--port 8765] [--background | --stop | --status]

Read-only over runs/ and the write-ups; parsed results are cached under
~/.cache/picc-dashboard. It listens on 127.0.0.1 only. Listening on any other
address (--host) exposes the experiment's records to the network, so it needs an
access code, printed at start-up; open the page once as http://HOST:PORT/?code=CODE.

Run it with the SGLang virtualenv's Python (make dashboard does) to get
reasoning-token counts: they need the `tokenizers` package and the model's
tokenizer file. Everything else is standard library.
"""

from __future__ import annotations

import argparse
import gzip
import hmac
import ipaddress
import json
import os
import secrets
import signal
import subprocess
import sys
import threading
import time
import traceback
import urllib.parse
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from picc_data import DataError, Results  # noqa: E402

ROOT = HERE.parent.parent
STATIC = HERE / "static"
DEFAULT_CACHE = Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache") / "picc-dashboard"
TYPES = {
    ".html": "text/html; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".json": "application/json; charset=utf-8",
}
LOOPBACK_NAMES = {"localhost", "127.0.0.1", "::1", "[::1]"}


def is_loopback(host: str) -> bool:
    if host in LOOPBACK_NAMES:
        return True
    try:
        return ipaddress.ip_address(host.strip("[]")).is_loopback
    except ValueError:
        return False


def int_arg(query: dict[str, list[str]], name: str) -> int | None:
    values = query.get(name)
    if not values or values[0] in ("", "last", "final"):
        return None
    try:
        return int(values[0])
    except ValueError as error:
        raise DataError(f"{name} must be a number") from error


def str_arg(query: dict[str, list[str]], name: str, default: str = "") -> str:
    values = query.get(name)
    return values[0] if values else default


class Dashboard(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, address: tuple[str, int], results: Results, code: str | None) -> None:
        super().__init__(address, Handler)
        self.results = results
        self.code = code
        self.loopback_only = is_loopback(address[0])


class Handler(BaseHTTPRequestHandler):
    server: Dashboard
    server_version = "picc-dashboard"
    sys_version = ""
    protocol_version = "HTTP/1.1"

    # ------------------------------------------------------------ plumbing

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002 - signature from the base class
        if os.environ.get("PICC_DASHBOARD_LOG"):
            sys.stderr.write("%s %s\n" % (self.address_string(), format % args))

    def _headers(self, status: int, ctype: str, length: int, extra: dict[str, str] | None = None,
                 cache: bool = False) -> None:
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(length))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Content-Security-Policy",
                         "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; "
                         "script-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'")
        self.send_header("Cache-Control", "no-cache" if cache else "no-store")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()

    def _send(self, status: int, body: bytes, ctype: str, cache: bool = False,
              extra: dict[str, str] | None = None) -> None:
        extra = dict(extra or {})
        if len(body) > 1500 and "gzip" in (self.headers.get("Accept-Encoding") or ""):
            body = gzip.compress(body, 5)
            extra["Content-Encoding"] = "gzip"
            extra["Vary"] = "Accept-Encoding"
        self._headers(status, ctype, len(body), extra, cache)
        if self.command != "HEAD":
            self.wfile.write(body)

    def _json(self, value: Any, status: int = 200) -> None:
        text = json.dumps(value, ensure_ascii=False, separators=(",", ":"), default=str)
        self._send(status, self.server.results.redact(text).encode("utf-8"), "application/json; charset=utf-8")

    def _error(self, status: int, message: str) -> None:
        self._json({"error": message}, status)

    def _allowed(self) -> bool:
        host = (self.headers.get("Host") or "").strip()
        name = host.rsplit(":", 1)[0] if not host.startswith("[") else host.split("]")[0] + "]"
        if self.server.loopback_only:
            # Only names that mean "this machine": a web page elsewhere cannot
            # point its own domain at 127.0.0.1 and read the results.
            return name.lower() in LOOPBACK_NAMES
        code = self.server.code or ""
        cookie = self.headers.get("Cookie") or ""
        for part in cookie.split(";"):
            k, _, v = part.strip().partition("=")
            if k == "picc_code" and hmac.compare_digest(v, code):
                return True
        return False

    # ------------------------------------------------------------ routing

    def do_HEAD(self) -> None:  # noqa: N802 - http.server naming
        self.do_GET()

    def do_GET(self) -> None:  # noqa: N802 - http.server naming
        url = urllib.parse.urlsplit(self.path)
        query = urllib.parse.parse_qs(url.query, keep_blank_values=True)
        if not self.server.loopback_only and "code" in query:
            given = query["code"][0]
            if hmac.compare_digest(given, self.server.code or ""):
                self._send(303, b"", "text/plain", extra={
                    "Location": "/", "Set-Cookie": f"picc_code={given}; Path=/; HttpOnly; SameSite=Strict; Max-Age=2592000"})
                return
        if not self._allowed():
            self._send(403, b"Forbidden. Open the address printed when the dashboard started.\n", "text/plain; charset=utf-8")
            return
        try:
            if url.path.startswith("/api/"):
                self._api(url.path[5:], query)
            else:
                self._static(url.path)
        except DataError as error:
            self._error(404, str(error))
        except (BrokenPipeError, ConnectionResetError):
            pass
        except Exception as error:  # noqa: BLE001 - report, keep serving
            traceback.print_exc()
            try:
                self._error(500, f"internal error: {type(error).__name__}: {error}")
            except OSError:
                pass

    def _static(self, path: str) -> None:
        if path in ("", "/", "/index.html"):
            target = STATIC / "index.html"
        elif path.startswith("/static/"):
            target = (STATIC / path[len("/static/"):]).resolve()
            if STATIC.resolve() not in target.parents:
                raise DataError("not found")
        elif path == "/favicon.ico":
            target = STATIC / "icon.svg"
        else:
            raise DataError("not found")
        if not target.is_file() or target.suffix not in TYPES:
            raise DataError("not found")
        self._send(200, target.read_bytes(), TYPES[target.suffix], cache=True)

    def _api(self, path: str, q: dict[str, list[str]]) -> None:
        r = self.server.results
        parts = [urllib.parse.unquote(p) for p in path.split("/") if p]
        if not parts:
            raise DataError("not found")
        head = parts[0]
        if head == "overview" and len(parts) == 1:
            return self._json(r.overview())
        if head == "runs" and len(parts) == 1:
            return self._json(r.runs_index())
        if head == "batch" and len(parts) == 2:
            return self._json(r.batch(parts[1]))
        if head == "docs" and len(parts) == 1:
            return self._json(r.docs())
        if head == "doc" and len(parts) == 1:
            return self._json(r.doc(str_arg(q, "path")))
        if head == "server" and len(parts) == 1:
            return self._json(r.server_launches())
        if head == "run" and len(parts) in (2, 3):
            run_id = parts[1]
            what = parts[2] if len(parts) == 3 else ""
            handlers: dict[str, Callable[[], Any]] = {
                "": lambda: self._run(run_id),
                "conversation": lambda: r.conversation(run_id, int_arg(q, "round")),
                "entry": lambda: r.entry(run_id, int_arg(q, "k") or 0),
                "search": lambda: r.search(run_id, str_arg(q, "q")),
                "files": lambda: r.files(run_id),
                "file": lambda: r.file(run_id, int_arg(q, "round"), str_arg(q, "path")),
                "diff": lambda: r.diff(run_id, int_arg(q, "round"), str_arg(q, "path") or None),
                "tests": lambda: r.tests(run_id, str_arg(q, "partition", "hidden"), int_arg(q, "round")),
                "matrix": lambda: r.matrix(run_id, str_arg(q, "partition", "visible")),
                "setup": lambda: r.setup(run_id),
                "prompt": lambda: r.prompt(run_id, str_arg(q, "name")),
                "reasoning": lambda: {k: v for k, v in r.reasoning(run_id).items() if k not in ("per_reply", "outs", "rounds")},
                "activity": lambda: r.activity(run_id),
            }
            if what in handlers:
                return self._json(handlers[what]())
        raise DataError("not found")

    def _run(self, run_id: str) -> dict[str, Any]:
        r = self.server.results
        out: dict[str, Any] = {"summary": r.summary(run_id), "digest": r.digest(run_id)}
        try:
            out["code"] = r.files_totals(run_id)
        except DataError as error:
            out["code"] = None
            out["code_error"] = str(error)
        out["final_tests"] = r.final_tests(run_id)
        reasoning = dict(r.reasoning(run_id))
        if reasoning.get("status") == "ready":
            replies = out["digest"]["replies"]
            reasoning["aligned"] = (len(reasoning.get("per_reply") or []) == len(replies)
                                    and reasoning.get("outs") == [x["out"] for x in replies])
            if not reasoning["aligned"]:
                reasoning.pop("per_reply", None)
            reasoning.pop("outs", None)
            reasoning.pop("rounds", None)
        out["reasoning"] = reasoning
        out["tokenizer"] = r.tokenizer_note()
        return out


# ---------------------------------------------------------------- start / stop


def pid_file(cache: Path) -> Path:
    return cache / "server.pid"


def running_pid(cache: Path) -> int | None:
    try:
        pid = int(pid_file(cache).read_text().split()[0])
    except (OSError, ValueError, IndexError):
        return None
    try:
        os.kill(pid, 0)
    except OSError:
        return None
    try:
        cmdline = Path(f"/proc/{pid}/cmdline").read_bytes().split(b"\0")
    except OSError:
        return pid
    return pid if any(part.endswith(b"server.py") for part in cmdline) else None


def main() -> int:
    parser = argparse.ArgumentParser(description="PiCC results dashboard (read-only).")
    parser.add_argument("--host", default="127.0.0.1",
                        help="address to listen on (default 127.0.0.1: this machine only)")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE)
    parser.add_argument("--no-cache", action="store_true", help="keep parsed results in memory only")
    parser.add_argument("--workers", type=int, default=3, help="processes used to read all runs at start-up")
    parser.add_argument("--code", help="access code when --host is not this machine (default: random)")
    parser.add_argument("--background", action="store_true", help="start in the background and return")
    parser.add_argument("--stop", action="store_true", help="stop the background dashboard")
    parser.add_argument("--status", action="store_true", help="say whether the background dashboard runs")
    args = parser.parse_args()
    cache = args.cache_dir.expanduser()

    if args.stop or args.status:
        pid = running_pid(cache)
        if args.status:
            where = (cache / "server.pid").read_text().split()[1:] if pid and (cache / "server.pid").is_file() else []
            print(f"dashboard running, pid {pid}" + (f", {where[0]}" if where else "") if pid else "dashboard not running")
            return 0
        if pid is None:
            print("dashboard not running")
            return 0
        os.kill(pid, signal.SIGTERM)
        for _ in range(50):
            if running_pid(cache) is None:
                break
            time.sleep(0.1)
        pid_file(cache).unlink(missing_ok=True)
        print(f"dashboard stopped (pid {pid})")
        return 0

    code = None
    if not is_loopback(args.host):
        code = args.code or secrets.token_urlsafe(12)

    if args.background:
        pid = running_pid(cache)
        if pid is not None:
            print(f"dashboard already running (pid {pid}); make dashboard-stop first")
            return 1
        cache.mkdir(parents=True, exist_ok=True)
        log = cache / "server.log"
        argv = [sys.executable, str(Path(__file__).resolve()), "--host", args.host, "--port", str(args.port),
                "--cache-dir", str(cache), "--workers", str(args.workers)]
        if args.no_cache:
            argv.append("--no-cache")
        env = dict(os.environ)
        if code:
            env["PICC_DASHBOARD_CODE"] = code
        with log.open("ab") as handle:
            proc = subprocess.Popen(argv, stdout=handle, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                                    start_new_session=True, env=env, cwd=str(ROOT))
        for _ in range(100):
            time.sleep(0.1)
            if proc.poll() is not None:
                print(f"dashboard failed to start; see {log}")
                return 1
            if running_pid(cache) == proc.pid:
                break
        shown = "localhost" if is_loopback(args.host) else args.host
        suffix = f"/?code={code}" if code else "/"
        print(f"dashboard running in the background (pid {proc.pid}): http://{shown}:{args.port}{suffix}")
        print(f"log: {log}   stop: make dashboard-stop")
        return 0

    code = code and (os.environ.get("PICC_DASHBOARD_CODE") or code)
    results = Results(ROOT, None if args.no_cache else cache)
    try:
        httpd = Dashboard((args.host, args.port), results, code)
    except OSError as error:
        print(f"cannot listen on {args.host}:{args.port}: {error}", file=sys.stderr)
        return 1
    cache.mkdir(parents=True, exist_ok=True)
    pid_file(cache).write_text(f"{os.getpid()} http://{args.host}:{args.port}/\n")
    threading.Thread(target=results.warm_up, kwargs={"workers": args.workers}, daemon=True,
                     name="warm-up").start()

    def stop(*_: Any) -> None:
        threading.Thread(target=httpd.shutdown, daemon=True).start()

    signal.signal(signal.SIGTERM, stop)
    shown = "localhost" if is_loopback(args.host) else args.host
    print(f"PiCC dashboard: http://{shown}:{args.port}/" + (f"?code={code}" if code else ""), flush=True)
    if not is_loopback(args.host):
        print("listening beyond this machine: anyone who can reach this address and has the code can read the runs",
              flush=True)
    print(f"reasoning tokens: {results.tokenizer_note()}", flush=True)
    try:
        httpd.serve_forever(poll_interval=0.5)
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
        try:
            if pid_file(cache).read_text().split()[0] == str(os.getpid()):
                pid_file(cache).unlink()
        except (OSError, IndexError):
            pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
