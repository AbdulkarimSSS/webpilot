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


def _client_log(msg: str) -> None:
    """Logs client status messages to stderr when in non-tty or MCP stdio mode to preserve stdout purity."""
    if os.environ.get("WEBPILOT_NO_STDIN") == "1" or not sys.stdout.isatty():
        sys.stderr.write(f"{msg}\n")
        sys.stderr.flush()
    else:
        print(msg)


class SupervisorClient:
    """Thin client for interacting with the Master Supervisor daemon."""

    def __init__(self, base_url: str = DEFAULT_SUPERVISOR_URL, token: Optional[str] = None):
        self.base_url = base_url.rstrip("/")
        self.token = token or load_supervisor_token()
        self._last_auth_error = False

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
        self._last_auth_error = False
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
                    except urllib.error.HTTPError as retry_err:
                        if retry_err.code == 401:
                            self._last_auth_error = True
                    except Exception:
                        pass
                else:
                    self._last_auth_error = True
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

        if getattr(self, "_last_auth_error", False):
            raise RuntimeError(
                f"Master Supervisor is actively running on port {port}, but authentication failed (HTTP 401 Unauthorized). "
                f"Please verify supervisor token or restart the supervisor service explicitly."
            )

        # WP-006 & M1: Stale daemon port recovery if port is blocked by dead/unauthenticated daemon
        stale_pid = self._find_pid_by_port(port)
        if stale_pid:
            # Verify that stale_pid is strictly a webpilot master_daemon process before terminating
            is_webpilot_proc = False
            try:
                if sys.platform == "win32":
                    ps_cmd = f'powershell -NoProfile -Command "(Get-CimInstance Win32_Process -Filter \\"ProcessId = {stale_pid}\\").CommandLine"'
                    out = subprocess.check_output(ps_cmd, shell=True, text=True, stderr=subprocess.DEVNULL).lower()
                    if any(marker in out for marker in ("master_daemon", "webpilot", "universal_web_applier")):
                        is_webpilot_proc = True
                else:
                    cmdline_file = f"/proc/{stale_pid}/cmdline"
                    if os.path.isfile(cmdline_file):
                        with open(cmdline_file, "r", errors="ignore") as f:
                            cmdline = f.read().lower()
                        if any(marker in cmdline for marker in ("master_daemon", "webpilot", "supervisor.master_daemon")):
                            is_webpilot_proc = True
                    else:
                        out = subprocess.check_output(["ps", "-p", str(stale_pid), "-o", "args="], text=True, stderr=subprocess.DEVNULL).lower()
                        if any(marker in out for marker in ("master_daemon", "webpilot", "supervisor.master_daemon")):
                            is_webpilot_proc = True
            except Exception:
                pass

            if is_webpilot_proc:
                _client_log(f"[!] Detected stale unauthenticated daemon holding port {port} (PID: {stale_pid}). Terminating...")
                get_process_manager().kill_process_tree(stale_pid, force=True)
                time.sleep(0.5)
            else:
                raise RuntimeError(
                    f"Port {port} is occupied by an unrelated process (PID: {stale_pid}). "
                    f"Please terminate that process or configure a different supervisor port."
                )

        _client_log("[*] Master Supervisor (Layer 1) not running. Auto-spawning background host...")
        script_path = os.path.join(PROJECT_ROOT, "supervisor", "master_daemon.py")
        py_exe = sys.executable

        if getattr(sys, "frozen", False):
            cwd = os.path.dirname(py_exe)
            cmd = [py_exe, "--run-daemon", "--port", str(port)]
        else:
            cwd = PROJECT_ROOT
            cmd = [py_exe, script_path, "--port", str(port)]

        spawn_env = os.environ.copy()
        spawn_env["WEBPILOT_SUPERVISOR_PORT"] = str(port)
        if self.token:
            spawn_env["WEBPILOT_SUPERVISOR_TOKEN"] = self.token

        get_process_manager().launch_detached(cmd, cwd=cwd, env=spawn_env)

        # Wait up to 4 seconds for supervisor to become active
        start = time.time()
        while time.time() - start < 4.0:
            if not self.token:
                self.token = load_supervisor_token()
            if self.is_running():
                _client_log("[✓] Master Supervisor is ready and active.")
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
        req_timeout = max(240, int(getattr(action_req, "timeout_minutes", 4) or 4) * 60)
        try:
            with urllib.request.urlopen(req, timeout=req_timeout) as resp:
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
        try:
            self.ensure_running()
            headers = self._get_headers({"Content-Type": "application/json"})
            req = urllib.request.Request(f"{self.base_url}/restart", data=b"{}", headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return SupervisorActionResponse.from_dict(data)
        except Exception as exc:
            # Stale daemon recovery: if 401 or supervisor hang, force kill stale PID and respawn
            port = 9333
            if ":" in self.base_url:
                try:
                    port = int(self.base_url.rsplit(":", 1)[-1].split("/")[0])
                except Exception:
                    pass
            stale_pid = self._find_pid_by_port(port)
            if stale_pid:
                try:
                    get_process_manager().kill_process_tree(stale_pid, force=True)
                    self._last_auth_error = False
                    self.ensure_running()
                    return SupervisorActionResponse(
                        success=True,
                        action="restart",
                        message=f"Terminated stale supervisor (PID: {stale_pid}) and respawned clean daemon.",
                    )
                except Exception as k_err:
                    return SupervisorActionResponse(
                        success=False,
                        action="restart",
                        message=f"Failed to recycle stale supervisor daemon: {k_err}",
                    )

            return SupervisorActionResponse(
                success=False,
                action="restart",
                message=f"Failed to restart worker: {exc}",
            )

    def stop_service(self) -> SupervisorActionResponse:
        """Completely terminates Master Supervisor and all worker tiers and reclaims temp profiles."""
        result = None
        if not self.is_running():
            result = SupervisorActionResponse(
                success=True,
                action="stop",
                message="Master Supervisor is already stopped.",
            )
        else:
            headers = self._get_headers({"Content-Type": "application/json"})
            req = urllib.request.Request(f"{self.base_url}/stop", data=b"{}", headers=headers, method="POST")
            try:
                with urllib.request.urlopen(req, timeout=10) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    result = SupervisorActionResponse.from_dict(data)
            except Exception as exc:
                result = SupervisorActionResponse(
                    success=False,
                    action="stop",
                    message=f"Error stopping service: {exc}",
                )

        try:
            from adapters.live_session_manager import LiveSessionManager
            LiveSessionManager.cleanup_temp_profiles(max_age_seconds=0)
        except Exception:
            pass

        return result


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
