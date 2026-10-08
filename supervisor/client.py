"""Lightweight HTTP Client for communicating with the Master Supervisor (Layer 1).

Includes Zero-Touch Auto-Spawn capability: automatically boots the background
supervisor host detached via WMI if not already running.
"""

from __future__ import annotations

import base64
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

DEFAULT_SUPERVISOR_URL: str = "http://127.0.0.1:9333"


class SupervisorClient:
    """Thin client for interacting with the Master Supervisor daemon."""

    def __init__(self, base_url: str = DEFAULT_SUPERVISOR_URL):
        self.base_url = base_url.rstrip("/")

    def is_running(self) -> bool:
        """Pings the supervisor health endpoint."""
        try:
            req = urllib.request.Request(f"{self.base_url}/ping", headers={"User-Agent": "WebPilotClient/2.0"})
            with urllib.request.urlopen(req, timeout=0.8) as resp:
                return resp.status == 200
        except Exception:
            return False

    def ensure_running(self) -> None:
        """Checks if supervisor is alive; if not, launches it detached via WMI."""
        if self.is_running():
            return

        print("[*] Master Supervisor (Layer 1) not running. Auto-spawning background host...")
        script_path = os.path.join(PROJECT_ROOT, "supervisor", "master_daemon.py")
        py_exe = sys.executable

        # Launch detached via WMI outside any parent terminal Job Object on Windows
        if sys.platform == "win32":
            if getattr(sys, "frozen", False):
                cwd = os.path.dirname(py_exe)
                cmd_line = f'`"{py_exe}`" --run-daemon'
            else:
                cwd = PROJECT_ROOT
                cmd_line = f'`"{py_exe}`" `"{script_path}`"'

            ps_script = f"""
$cwd = '{cwd}'
$cmd = '{cmd_line}'
$proc = ([wmiclass]'Win32_Process').Create($cmd, $cwd, $null)
if ($proc.ReturnValue -eq 0) {{
    Write-Output $proc.ProcessId
}} else {{
    exit 1
}}
"""
            encoded = base64.b64encode(ps_script.encode("utf-16le")).decode("ascii")
            subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-EncodedCommand", encoded],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=5,
            )
        else:
            # POSIX / Linux / macOS
            if getattr(sys, "frozen", False):
                cmd = [py_exe, "--run-daemon"]
                cwd = os.path.dirname(py_exe)
            else:
                cmd = [py_exe, script_path]
                cwd = PROJECT_ROOT

            subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
                cwd=cwd,
            )

        # Wait up to 4 seconds for supervisor to become active
        start = time.time()
        while time.time() - start < 4.0:
            if self.is_running():
                print("[✓] Master Supervisor is ready and active.")
                return
            time.sleep(0.2)

        raise RuntimeError("Failed to auto-spawn Master Supervisor on http://127.0.0.1:9333.")

    def execute(self, action_req: SupervisorActionRequest) -> SupervisorActionResponse:
        """Sends an action request to the supervisor and returns structured response."""
        self.ensure_running()
        url = f"{self.base_url}/execute"
        body = json.dumps(action_req.to_dict()).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=body,
            headers={"Content-Type": "application/json", "User-Agent": "WebPilotClient/2.0"},
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
        req = urllib.request.Request(f"{self.base_url}/restart", data=b"{}", method="POST")
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

        req = urllib.request.Request(f"{self.base_url}/stop", data=b"{}", method="POST")
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
            req = urllib.request.Request(f"{self.base_url}/status")
            with urllib.request.urlopen(req, timeout=2) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                data["status"] = "running"
                data["supervisor_alive"] = True
                return data
        except Exception:
            return {"status": "unreachable", "supervisor_alive": False}
