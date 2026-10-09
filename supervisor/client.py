"""Lightweight HTTP Client for communicating with the Master Supervisor (Layer 1).

Includes Zero-Touch Auto-Spawn capability: automatically boots the background
supervisor host detached via ProcessManager if not already running.
Enforces authenticated HTTP communication using secure tokens.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from typing import Any, Dict, Optional

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from supervisor.contracts import SupervisorActionRequest, SupervisorActionResponse
from supervisor.security import load_supervisor_token
from common.process_manager import get_process_manager

DEFAULT_SUPERVISOR_URL: str = "http://127.0.0.1:9333"


class SupervisorClient:
    """Thin client for interacting with the Master Supervisor daemon."""

    def __init__(self, base_url: str = DEFAULT_SUPERVISOR_URL, token: Optional[str] = None):
        self.base_url = base_url.rstrip("/")
        self.token = token or load_supervisor_token()

    def _get_headers(self, extra_headers: Optional[Dict[str, str]] = None) -> Dict[str, str]:
        """Assembles headers including current authentication credentials."""
        if not self.token:
            self.token = load_supervisor_token()
        headers = {
            "User-Agent": "WebPilotClient/2.0",
        }
        if self.token:
            headers["X-Supervisor-Token"] = self.token
            headers["Authorization"] = f"Bearer {self.token}"
        if extra_headers:
            headers.update(extra_headers)
        return headers

    def is_running(self) -> bool:
        """Pings the supervisor health endpoint with authentication."""
        try:
            req = urllib.request.Request(f"{self.base_url}/ping", headers=self._get_headers())
            with urllib.request.urlopen(req, timeout=2.5) as resp:
                return resp.status == 200
        except urllib.error.HTTPError as err:
            # If 401 Unauthorized, a supervisor is running with a different or new token
            if err.code == 401:
                # Refresh token and retry once
                fresh_token = load_supervisor_token()
                if fresh_token and fresh_token != self.token:
                    self.token = fresh_token
                    try:
                        retry_req = urllib.request.Request(f"{self.base_url}/ping", headers=self._get_headers())
                        with urllib.request.urlopen(retry_req, timeout=2.5) as retry_resp:
                            return retry_resp.status == 200
                    except Exception:
                        pass
            return False
        except Exception:
            return False

    @staticmethod
    def _find_pid_by_port(port: int) -> Optional[int]:
        """Finds PID listening on the specified local port."""
        try:
            if sys.platform == "win32":
                out = subprocess.check_output(f'netstat -ano | findstr :{port}', shell=True, text=True, stderr=subprocess.DEVNULL)
                for line in out.strip().splitlines():
                    parts = line.strip().split()
                    if len(parts) >= 5 and "LISTENING" in line and parts[1].endswith(f":{port}"):
                        return int(parts[-1])
            else:
                try:
                    out = subprocess.check_output(["lsof", "-t", f"-i:{port}"], text=True, stderr=subprocess.DEVNULL)
                    pids = [int(p) for p in out.strip().splitlines() if p.isdigit()]
                    if pids:
                        return pids[0]
                except Exception:
                    try:
                        out = subprocess.check_output(["fuser", f"{port}/tcp"], text=True, stderr=subprocess.DEVNULL)
                        pids = [int(p) for p in out.strip().split() if p.isdigit()]
                        if pids:
                            return pids[0]
                    except Exception:
                        pass
        except Exception:
            pass
        return None

    def ensure_running(self) -> None:
        """Checks if supervisor is alive; if not, launches it detached via ProcessManager."""
        if self.is_running():
            return

        port = 9333
        if ":" in self.base_url:
            try:
                port = int(self.base_url.rsplit(":", 1)[-1].split("/")[0])
            except Exception:
                pass

        # WP-006: Stale daemon port recovery if port is blocked by dead/unauthenticated daemon
        stale_pid = self._find_pid_by_port(port)
        if stale_pid:
            print(f"[!] Detected stale unauthenticated daemon holding port {port} (PID: {stale_pid}). Terminating...")
            get_process_manager().kill_process_tree(stale_pid, force=True)
            time.sleep(0.5)

        print("[*] Master Supervisor (Layer 1) not running. Auto-spawning background host...")
        script_path = os.path.join(PROJECT_ROOT, "supervisor", "master_daemon.py")
        py_exe = sys.executable

        if getattr(sys, "frozen", False):
            cwd = os.path.dirname(py_exe)
            cmd = [py_exe, "--run-daemon"]
        else:
            cwd = PROJECT_ROOT
            cmd = [py_exe, script_path]

        spawn_env = os.environ.copy()
        if self.token:
            spawn_env["WEBPILOT_SUPERVISOR_TOKEN"] = self.token

        get_process_manager().launch_detached(cmd, cwd=cwd, env=spawn_env)

        # Wait up to 4 seconds for supervisor to become active
        start = time.time()
        while time.time() - start < 4.0:
            if not self.token:
                self.token = load_supervisor_token()
            if self.is_running():
                print("[✓] Master Supervisor is ready and active.")
                return
            time.sleep(0.2)

        # Final retry: check if port became blocked during launch
        stale_pid = self._find_pid_by_port(port)
        if stale_pid:
            get_process_manager().kill_process_tree(stale_pid, force=True)

        raise RuntimeError(f"Failed to auto-spawn Master Supervisor on http://127.0.0.1:{port}.")

    def execute(self, action_req: SupervisorActionRequest) -> SupervisorActionResponse:
        """Sends an authenticated action request to the supervisor and returns structured response."""
        self.ensure_running()
        url = f"{self.base_url}/execute"
        body = json.dumps(action_req.to_dict()).encode("utf-8")
        headers = self._get_headers({"Content-Type": "application/json"})
        req = urllib.request.Request(
            url,
            data=body,
            headers=headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=90) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return SupervisorActionResponse.from_dict(data)
        except Exception as exc:
            return SupervisorActionResponse(
                success=False,
                action=action_req.action,
                message=f"Network error communicating with Master Supervisor: {exc}",
            )

    def restart_worker(self) -> SupervisorActionResponse:
        """Triggers cascading kill of Layer 2 Worker and Chromium, then respawns fresh."""
        self.ensure_running()
        headers = self._get_headers({"Content-Type": "application/json"})
        req = urllib.request.Request(f"{self.base_url}/restart", data=b"{}", headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return SupervisorActionResponse.from_dict(data)
        except Exception as exc:
            return SupervisorActionResponse(
                success=False,
                action="restart",
                message=f"Failed to restart worker: {exc}",
            )

    def stop_service(self) -> SupervisorActionResponse:
        """Completely terminates Master Supervisor and all worker tiers."""
        if not self.is_running():
            return SupervisorActionResponse(
                success=True,
                action="stop",
                message="Master Supervisor is already stopped.",
            )

        headers = self._get_headers({"Content-Type": "application/json"})
        req = urllib.request.Request(f"{self.base_url}/stop", data=b"{}", headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return SupervisorActionResponse.from_dict(data)
        except Exception as exc:
            return SupervisorActionResponse(
                success=False,
                action="stop",
                message=f"Error stopping service: {exc}",
            )

    def get_status(self) -> Dict[str, Any]:
        """Retrieves runtime health and PID telemetry."""
        if not self.is_running():
            return {"status": "stopped", "supervisor_alive": False}

        try:
            req = urllib.request.Request(f"{self.base_url}/status", headers=self._get_headers())
            with urllib.request.urlopen(req, timeout=2) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                data["status"] = "running"
                data["supervisor_alive"] = True
                return data
        except Exception:
            return {"status": "unreachable", "supervisor_alive": False}
