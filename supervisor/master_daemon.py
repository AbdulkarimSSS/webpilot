"""Layer 1: Master Supervisor Daemon Host.

Runs as a lightweight, persistent background daemon (Zero-Admin, Standard User).
Supervises Layer 2 (Operational Worker) and enforces cascading teardown.
Exposes a minimal HTTP endpoint on 127.0.0.1:9333 for CLI and Shell clients.
"""

from __future__ import annotations

import json
import os
import queue
import subprocess
import sys
import threading
import time
from http.server import ThreadingHTTPServer
from typing import Any, Dict, Optional

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from common.process_manager import get_process_manager
from supervisor.contracts import SupervisorActionRequest, SupervisorActionResponse
from supervisor.handler import create_supervisor_handler
from supervisor.security import (
    generate_supervisor_token,
    load_supervisor_token,
    remove_supervisor_token,
    save_supervisor_token,
)
from supervisor.watchdog import InactivityWatchdog

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
        self.worker_response_queue: Optional[queue.Queue] = None
        self.last_active_time: float = time.time()
        self.lock = threading.Lock()
        self.rpc_lock = threading.Lock()
        self._is_running = True

        # Launch watchdog sentinel
        self.watchdog = InactivityWatchdog(
            get_last_active_time=lambda: self.last_active_time,
            get_worker_process=lambda: self.worker_process,
            terminate_worker=self.terminate_worker,
            timeout_seconds=self.inactivity_timeout_seconds,
        )
        self.watchdog.start()

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

        resp_queue: queue.Queue = queue.Queue()
        self.worker_response_queue = resp_queue

        def _drain_stdout(pipe, q):
            try:
                for line in iter(pipe.readline, ""):
                    if not line:
                        break
                    q.put(line)
            except Exception:
                pass
            finally:
                q.put(None)
                try:
                    pipe.close()
                except Exception:
                    pass

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

        if getattr(proc, "stdout", None):
            threading.Thread(target=_drain_stdout, args=(proc.stdout, resp_queue), daemon=True).start()
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
            self.watchdog.stop()
            return SupervisorActionResponse(
                success=True,
                action="stop",
                message="Master Supervisor and all worker tiers shut down.",
            )

        with self.rpc_lock:
            worker = self._ensure_worker()
            if worker.stdin is None or self.worker_response_queue is None:
                raise RuntimeError("Worker process stdin or response queue is not initialized.")

            req_line = json.dumps(req.to_dict()) + "\n"
            try:
                worker.stdin.write(req_line)
                worker.stdin.flush()

                rpc_timeout_seconds = 60.0
                data = None
                start_t = time.time()
                while True:
                    elapsed = time.time() - start_t
                    remaining_timeout = max(0.1, rpc_timeout_seconds - elapsed)
                    if elapsed >= rpc_timeout_seconds:
                        log_daemon(f"Worker RPC call timed out after {rpc_timeout_seconds}s")
                        self.terminate_worker()
                        return SupervisorActionResponse(
                            success=False,
                            action=req.action,
                            message=f"Operational Worker RPC timed out after {rpc_timeout_seconds}s.",
                        )

                    try:
                        line = self.worker_response_queue.get(timeout=remaining_timeout)
                    except queue.Empty:
                        log_daemon(f"Worker RPC call timed out after {rpc_timeout_seconds}s")
                        self.terminate_worker()
                        return SupervisorActionResponse(
                            success=False,
                            action=req.action,
                            message=f"Operational Worker RPC timed out after {rpc_timeout_seconds}s.",
                        )

                    if line is None:
                        # Worker closed pipe
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


def run_master_daemon(port: int = DEFAULT_SUPERVISOR_PORT, token: Optional[str] = None):
    """Starts the Master Supervisor HTTP service."""
    sys.stdout = LogWriter(LOG_FILE)
    sys.stderr = LogWriter(LOG_FILE)
    log_daemon(f"run_master_daemon starting on port {port} (PID: {os.getpid()})")
    supervisor = None
    bound_successfully = False
    try:
        eff_token = (
            token
            or os.environ.get("WEBPILOT_SUPERVISOR_TOKEN")
            or load_supervisor_token()
            or generate_supervisor_token()
        )
        supervisor = MasterSupervisor(port=port, token=eff_token, auto_save_token=False)
        handler_class = create_supervisor_handler(supervisor)
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
        if bound_successfully:
            remove_supervisor_token()


__all__ = [
    "DEFAULT_SUPERVISOR_HOST",
    "DEFAULT_SUPERVISOR_PORT",
    "DEFAULT_INACTIVITY_TIMEOUT_SECONDS",
    "MasterSupervisor",
    "create_supervisor_handler",
    "run_master_daemon",
    "log_daemon",
]


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="WebPilot Master Daemon (Layer 1)")
    parser.add_argument("--port", type=int, default=int(os.environ.get("WEBPILOT_SUPERVISOR_PORT", DEFAULT_SUPERVISOR_PORT)))
    parser.add_argument("--token", type=str, default=os.environ.get("WEBPILOT_SUPERVISOR_TOKEN", None))
    args, _ = parser.parse_known_args()
    run_master_daemon(port=args.port, token=args.token)

