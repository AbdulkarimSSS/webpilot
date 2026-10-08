"""Cross-Platform Process Management and Isolation Layer.

Isolates OS-specific process lifecycle mechanisms (WMI, CIM, taskkill on Windows;
killpg, pgrep, signals on POSIX/Linux/macOS) behind a clean, unified ProcessManager interface.
"""

from __future__ import annotations

import base64
import os
import signal
import subprocess
import sys
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Union


class BaseProcessManager(ABC):
    """Abstract interface for system process management and detached lifecycle execution."""

    @abstractmethod
    def launch_detached(
        self,
        cmd: Union[str, List[str]],
        cwd: Optional[str] = None,
        env: Optional[Dict[str, str]] = None,
    ) -> Optional[int]:
        """Launches a detached process decoupled from the caller's terminal and process group."""
        pass

    @abstractmethod
    def kill_process_tree(self, pid: int, force: bool = True) -> bool:
        """Kills the target process and all descendant child processes (cascading teardown)."""
        pass

    @abstractmethod
    def get_child_pids(self, parent_pid: int) -> List[int]:
        """Returns direct child process IDs for the given parent PID."""
        pass

    @abstractmethod
    def is_process_running(self, pid: int) -> bool:
        """Checks if a process with the specified PID is currently active."""
        pass


class WindowsProcessManager(BaseProcessManager):
    """Windows-specific implementation using PowerShell WMI/CIM and taskkill."""

    def launch_detached(
        self,
        cmd: Union[str, List[str]],
        cwd: Optional[str] = None,
        env: Optional[Dict[str, str]] = None,
    ) -> Optional[int]:
        target_cwd = cwd or os.getcwd()
        if isinstance(cmd, list):
            cmd_str = " ".join(f'"{arg}"' if " " in arg and not arg.startswith('"') else arg for arg in cmd)
        else:
            cmd_str = cmd

        # Primary approach: Win32_Process.Create via WMI to break out of terminal Job Objects
        ps_script = f"""
$cwd = '{target_cwd}'
$cmd = @'
{cmd_str}
'@
$startup = ([wmiclass]'Win32_ProcessStartup').CreateInstance()
$startup.ShowWindow = 0
$proc = ([wmiclass]'Win32_Process').Create($cmd, $cwd, $startup)
if ($proc.ReturnValue -eq 0) {{
    Write-Output $proc.ProcessId
}} else {{
    exit 1
}}
"""
        try:
            encoded = base64.b64encode(ps_script.encode("utf-16le")).decode("ascii")
            res = subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-EncodedCommand", encoded],
                capture_output=True,
                text=True,
                timeout=10,
            )
            out = res.stdout.strip()
            if res.returncode == 0 and out.isdigit():
                return int(out)
        except Exception:
            pass

        # Fallback approach: subprocess.Popen with DETACHED_PROCESS
        try:
            cmd_args = cmd if isinstance(cmd, list) else cmd_str
            creation_flags = (
                getattr(subprocess, "DETACHED_PROCESS", 0x00000008)
                | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0x00000200)
            )
            proc = subprocess.Popen(
                cmd_args,
                cwd=target_cwd,
                env=env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL,
                creationflags=creation_flags,
            )
            return proc.pid
        except Exception:
            return None

    def kill_process_tree(self, pid: int, force: bool = True) -> bool:
        if not pid or pid <= 0:
            return False
        args = ["taskkill"]
        if force:
            args.append("/F")
        args.extend(["/T", "/PID", str(pid)])
        try:
            res = subprocess.run(
                args,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=10,
            )
            return res.returncode == 0
        except Exception:
            return False

    def get_child_pids(self, parent_pid: int) -> List[int]:
        if not parent_pid or parent_pid <= 0:
            return []
        try:
            ps_c = f"(Get-CimInstance Win32_Process | Where-Object {{ $_.ParentProcessId -eq {parent_pid} }}).ProcessId"
            out = subprocess.check_output(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_c],
                text=True,
                stderr=subprocess.DEVNULL,
                timeout=8,
            ).strip()
            pids = []
            for line in out.splitlines():
                line = line.strip()
                if line.isdigit():
                    pids.append(int(line))
            return pids
        except Exception:
            return []

    def is_process_running(self, pid: int) -> bool:
        if not pid or pid <= 0:
            return False
        try:
            ps_c = f"(Get-Process -Id {pid} -ErrorAction SilentlyContinue) -ne $null"
            out = subprocess.check_output(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_c],
                text=True,
                stderr=subprocess.DEVNULL,
                timeout=5,
            ).strip()
            return out.lower() == "true"
        except Exception:
            return False


class PosixProcessManager(BaseProcessManager):
    """POSIX/Linux/macOS implementation using setsid, signal.SIGKILL, and pgrep."""

    def launch_detached(
        self,
        cmd: Union[str, List[str]],
        cwd: Optional[str] = None,
        env: Optional[Dict[str, str]] = None,
    ) -> Optional[int]:
        target_cwd = cwd or os.getcwd()
        try:
            cmd_args = cmd if isinstance(cmd, list) else cmd.split()
            proc = subprocess.Popen(
                cmd_args,
                cwd=target_cwd,
                env=env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL,
                start_new_session=True,  # setsid decoupling
            )
            return proc.pid
        except Exception:
            return None

    def kill_process_tree(self, pid: int, force: bool = True) -> bool:
        if not pid or pid <= 0:
            return False
        sig = signal.SIGKILL if force else signal.SIGTERM
        killed = False
        # Strategy 1: Process group kill if leader
        try:
            pgid = os.getpgid(pid)
            os.killpg(pgid, sig)
            killed = True
        except Exception:
            pass

        # Strategy 2: pkill children then kill target
        try:
            subprocess.run(["pkill", "-P", str(pid)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            os.kill(pid, sig)
            killed = True
        except Exception:
            pass

        return killed

    def get_child_pids(self, parent_pid: int) -> List[int]:
        if not parent_pid or parent_pid <= 0:
            return []
        try:
            out = subprocess.check_output(
                ["pgrep", "-P", str(parent_pid)],
                text=True,
                stderr=subprocess.DEVNULL,
                timeout=5,
            ).strip()
            pids = []
            for line in out.splitlines():
                line = line.strip()
                if line.isdigit():
                    pids.append(int(line))
            return pids
        except Exception:
            return []

    def is_process_running(self, pid: int) -> bool:
        if not pid or pid <= 0:
            return False
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False


_GLOBAL_PROCESS_MANAGER: Optional[BaseProcessManager] = None


def get_process_manager() -> BaseProcessManager:
    """Returns the platform-appropriate ProcessManager singleton."""
    global _GLOBAL_PROCESS_MANAGER
    if _GLOBAL_PROCESS_MANAGER is None:
        if sys.platform == "win32":
            _GLOBAL_PROCESS_MANAGER = WindowsProcessManager()
        else:
            _GLOBAL_PROCESS_MANAGER = PosixProcessManager()
    return _GLOBAL_PROCESS_MANAGER


def set_process_manager(manager: Optional[BaseProcessManager]) -> None:
    """Allows injecting custom or mock ProcessManager implementations for testing."""
    global _GLOBAL_PROCESS_MANAGER
    _GLOBAL_PROCESS_MANAGER = manager
