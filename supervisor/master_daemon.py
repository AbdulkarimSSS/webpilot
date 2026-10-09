"""Layer 1: Master Supervisor Daemon Host.

Runs as a lightweight, persistent background daemon (Zero-Admin, Standard User).
Supervises Layer 2 (Operational Worker) and enforces cascading teardown.
Exposes a minimal HTTP endpoint on 127.0.0.1:9333 for CLI and Shell clients.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer, ThreadingHTTPServer
from typing import Any, Dict, Optional

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from supervisor.contracts import SupervisorActionRequest, SupervisorActionResponse
from supervisor.security import (
    generate_supervisor_token,
    save_supervisor_token,
    remove_supervisor_token,
    validate_supervisor_token,
    load_supervisor_token,
)
from common.process_manager import get_process_manager

DEFAULT_SUPERVISOR_HOST: str = "127.0.0.1"
DEFAULT_SUPERVISOR_PORT: int = 9333
DEFAULT_INACTIVITY_TIMEOUT_SECONDS: int = 1800  # 30 minutes
LOG_FILE: str = os.path.join(PROJECT_ROOT, "master_daemon.log")



class LogWriter:
    """Safe file-backed stream writer for headless daemon background logging."""
    def __init__(self, filepath: str):
        self.filepath = filepath

    def write(self, s: str) -> None:
        if s:
            try:
                with open(self.filepath, "a", encoding="utf-8") as f:
                    f.write(s)
            except Exception:
                pass

    def flush(self) -> None:
        pass


def log_daemon(msg: str) -> None:
    """Appends timestamped event to master_daemon.log."""
    try:
        ts = time.strftime("%Y-%m-%d %H:%M:%S")
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"[{ts}] {msg}\n")
    except Exception:
        pass


class MasterSupervisor:
    """Layer 1 Master Supervisor: controls Worker process lifecycle and inactivity watchdog."""

    def __init__(
        self,
        host: str = DEFAULT_SUPERVISOR_HOST,
        port: int = DEFAULT_SUPERVISOR_PORT,
        inactivity_timeout_seconds: int = DEFAULT_INACTIVITY_TIMEOUT_SECONDS,
        token: Optional[str] = None,
        auto_save_token: bool = True,
    ):
        self.host = host
        self.port = port
        self.inactivity_timeout_seconds = inactivity_timeout_seconds
        self.token: str = token or os.environ.get("WEBPILOT_SUPERVISOR_TOKEN") or generate_supervisor_token()
        if auto_save_token:
            save_supervisor_token(self.token)

        self.worker_process: Optional[subprocess.Popen] = None
        self.last_active_time: float = time.time()
        self.lock = threading.Lock()
        self._is_running = True

        # Launch watchdog thread
        self.watchdog_thread = threading.Thread(target=self._watchdog_loop, daemon=True)
        self.watchdog_thread.start()

    def _spawn_worker(self) -> subprocess.Popen:
        """Spawns Layer 2 Worker subprocess with process group isolation."""
        if getattr(sys, "frozen", False):
            worker_cmd = [sys.executable, "--run-worker"]
            worker_cwd = os.path.dirname(sys.executable)
        else:
            worker_cmd = [sys.executable, "-m", "supervisor.worker_process"]
            worker_cwd = PROJECT_ROOT

        worker_env = os.environ.copy()
        worker_env["WEBPILOT_SUPERVISOR_TOKEN"] = self.token

        popen_kwargs: Dict[str, Any] = {
            "stdin": subprocess.PIPE,
            "stdout": subprocess.PIPE,
            "stderr": subprocess.PIPE,
            "text": True,
            "bufsize": 1,
            "cwd": worker_cwd,
            "env": worker_env,
        }
        if sys.platform != "win32":
            popen_kwargs["start_new_session"] = True

        proc = subprocess.Popen(worker_cmd, **popen_kwargs)

        # WP-013: Drain worker stderr in background thread to prevent pipe deadlocks
        def _drain_stderr(pipe):
            try:
                for line in iter(pipe.readline, ""):
                    if not line:
                        break
                    line_str = line.strip()
                    if line_str:
                        log_daemon(f"[worker-stderr] {line_str}")
            except Exception:
                pass
            finally:
                try:
                    pipe.close()
                except Exception:
                    pass

        if getattr(proc, "stderr", None):
            threading.Thread(target=_drain_stderr, args=(proc.stderr,), daemon=True).start()

        return proc

    def _ensure_worker(self) -> subprocess.Popen:
        """Spawns Layer 2 Worker subprocess if not currently running."""
        with self.lock:
            if self.worker_process is None or self.worker_process.poll() is not None:
                self.worker_process = self._spawn_worker()
            return self.worker_process

    def execute_action(self, req: SupervisorActionRequest) -> SupervisorActionResponse:
        """Proxies action request to Layer 2 Worker and returns structured response."""
        self.last_active_time = time.time()

        if req.action == "restart_worker":
            return self.restart_worker()

        if req.action in ("stop", "shutdown"):
            self.terminate_worker()
            self._is_running = False
            return SupervisorActionResponse(
                success=True,
                action="stop",
                message="Master Supervisor and all worker tiers shut down.",
            )

        worker = self._ensure_worker()
        assert worker.stdin is not None and worker.stdout is not None

        req_line = json.dumps(req.to_dict()) + "\n"
        try:
            worker.stdin.write(req_line)
            worker.stdin.flush()

            data = None
            while True:
                line = worker.stdout.readline()
                if not line:
                    break
                line_str = line.strip()
                if not line_str:
                    continue
                try:
                    data = json.loads(line_str)
                    break
                except Exception:
                    log_daemon(f"Skipping non-JSON worker stdout: {line_str}")
                    continue

            if not data:
                log_daemon("Worker returned no valid JSON response.")
                self.terminate_worker()
                return SupervisorActionResponse(
                    success=False,
                    action=req.action,
                    message="Operational Worker failed to return valid JSON response.",
                )

            return SupervisorActionResponse.from_dict(data)

        except Exception as exc:
            return SupervisorActionResponse(
                success=False,
                action=req.action,
                message=f"Supervisor dispatch error: {exc}",
            )

    def restart_worker(self) -> SupervisorActionResponse:
        """Cascading kill of Layer 2 Worker and all child Chromium processes, then respawns fresh."""
        with self.lock:
            old_pid = self.worker_process.pid if self.worker_process else None
            self.terminate_worker()
            # Spawn fresh Worker using unified helper with start_new_session on POSIX
            new_worker = self._spawn_worker()
            self.worker_process = new_worker
            self.last_active_time = time.time()

        return SupervisorActionResponse(
            success=True,
            action="restart_worker",
            message=f"Cascading kill completed for PID {old_pid}. Fresh Worker spawned (PID: {new_worker.pid}).",
            worker_pid=new_worker.pid,
        )

    def terminate_worker(self) -> None:
        """Forcefully kills the Layer 2 Worker process tree via ProcessManager."""
        proc = self.worker_process
        self.worker_process = None
        if proc and proc.poll() is None:
            get_process_manager().kill_process_tree(proc.pid, force=True)

    def get_status(self) -> Dict[str, Any]:
        """Returns telemetry for Supervisor and Worker."""
        worker_alive = self.worker_process is not None and self.worker_process.poll() is None
        worker_pid = self.worker_process.pid if worker_alive else None
        return {
            "supervisor_pid": os.getpid(),
            "supervisor_port": self.port,
            "worker_alive": worker_alive,
            "worker_pid": worker_pid,
            "idle_seconds": round(time.time() - self.last_active_time, 1),
            "inactivity_timeout_seconds": self.inactivity_timeout_seconds,
        }

    def _watchdog_loop(self) -> None:
        """Periodically checks inactivity. Kills idle Worker to release 100% of browser RAM."""
        while self._is_running:
            time.sleep(15)
            if self.worker_process and self.worker_process.poll() is None:
                idle = time.time() - self.last_active_time
                if idle > self.inactivity_timeout_seconds:
                    print(f"[*] Inactivity watchdog triggered ({idle:.0f}s idle). Terminating Worker to release RAM.")
                    self.terminate_worker()


def create_supervisor_handler(supervisor: MasterSupervisor):
    """Factory creating an HTTP Request Handler bound to the supervisor instance."""

    class SupervisorHTTPHandler(BaseHTTPRequestHandler):
        def log_message(self, format, *args):
            # Suppress default stdout HTTP access logs
            return

        def _send_json(self, status_code: int, data: Dict[str, Any]):
            body = json.dumps(data, ensure_ascii=False).encode("utf-8")
            self.send_response(status_code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _check_host(self) -> bool:
            """WP-011: Validates incoming Host header to protect against DNS rebinding attacks."""
            host = self.headers.get("Host")
            if not host:
                return True
            host_clean = host.split(":")[0].strip().lower()
            if host_clean in ("127.0.0.1", "localhost", "::1"):
                return True
            self._send_json(
                403,
                {
                    "success": False,
                    "error": f"Forbidden: Host '{host}' is rejected by DNS rebinding defense.",
                },
            )
            return False

        def _authenticate(self) -> bool:
            """Validates incoming HTTP request against the supervisor's secure token."""
            if not self._check_host():
                return False

            header_token = self.headers.get("X-Supervisor-Token") or self.headers.get("Authorization")
            try:
                is_valid = validate_supervisor_token(header_token, supervisor.token)
            except Exception:
                is_valid = False

            if not is_valid:
                self._send_json(
                    401,
                    {
                        "success": False,
                        "error": "Unauthorized: Invalid or missing supervisor authentication token.",
                    },
                )
                return False
            return True

        def do_GET(self):
            if not self._authenticate():
                return

            if self.path == "/ping":
                self._send_json(200, {"status": "ok", "supervisor_pid": os.getpid()})
            elif self.path == "/status":
                status = supervisor.get_status()
                self._send_json(200, status)
            else:
                self._send_json(404, {"error": "Not Found"})

        def do_POST(self):
            if not self._authenticate():
                return

            content_length = int(self.headers.get("Content-Length", 0))
            raw_body = self.rfile.read(content_length).decode("utf-8") if content_length > 0 else "{}"

            try:
                data = json.loads(raw_body)
            except Exception:
                data = {}

            if self.path == "/execute":
                req = SupervisorActionRequest.from_dict(data)
                res = supervisor.execute_action(req)
                self._send_json(200, res.to_dict())
            elif self.path == "/restart":
                res = supervisor.restart_worker()
                self._send_json(200, res.to_dict())
            elif self.path == "/stop":
                req = SupervisorActionRequest(action="stop")
                res = supervisor.execute_action(req)
                self._send_json(200, res.to_dict())
                # Schedule daemon shutdown in background thread
                threading.Thread(target=self.server.shutdown, daemon=True).start()
            else:
                self._send_json(404, {"error": "Not Found"})

    return SupervisorHTTPHandler


def run_master_daemon(port: int = DEFAULT_SUPERVISOR_PORT, token: Optional[str] = None):
    """Starts the Master Supervisor HTTP service."""
    sys.stdout = LogWriter(LOG_FILE)
    sys.stderr = LogWriter(LOG_FILE)
    log_daemon(f"run_master_daemon starting on port {port} (PID: {os.getpid()})")
    supervisor = None
    bound_successfully = False
    try:
        eff_token = token or os.environ.get("WEBPILOT_SUPERVISOR_TOKEN") or load_supervisor_token() or generate_supervisor_token()
        supervisor = MasterSupervisor(port=port, token=eff_token, auto_save_token=False)
        handler_class = create_supervisor_handler(supervisor)
        # Bind socket first: if port is in use, will raise OSError without touching token file
        server = ThreadingHTTPServer((DEFAULT_SUPERVISOR_HOST, port), handler_class)
        bound_successfully = True
        save_supervisor_token(supervisor.token)
        log_daemon(f"Master Supervisor listening on http://{DEFAULT_SUPERVISOR_HOST}:{port}")
        print(f"[*] Master Supervisor (Layer 1) started on http://{DEFAULT_SUPERVISOR_HOST}:{port} (PID: {os.getpid()})")
        server.serve_forever()
    except Exception as exc:
        log_daemon(f"Master Supervisor fatal exception: {exc}")
        raise
    finally:
        if supervisor:
            try:
                supervisor.terminate_worker()
            except Exception:
                pass
        # WP-016: Only remove token file if THIS process was the one that successfully bound and owned the port
        if bound_successfully:
            remove_supervisor_token()
        log_daemon("Master Supervisor stopped.")
        print("[*] Master Supervisor stopped.")


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else DEFAULT_SUPERVISOR_PORT
    # WP-001: Resolve token from environment or token file to avoid leaking credentials in sys.argv
    token = os.environ.get("WEBPILOT_SUPERVISOR_TOKEN") or load_supervisor_token()
    if not token and len(sys.argv) > 2:
        token = sys.argv[2]
    run_master_daemon(port=port, token=token)

