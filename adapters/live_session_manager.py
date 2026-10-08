"""Live Browser Session and Inactivity Watchdog Manager.

Manages persistent Chromium browser processes connected over CDP, allowing
sequential multi-step CLI commands to execute against the same live browser
and open tabs without closing between commands. Enforces an inactivity watchdog
timer that terminates the process after a specified duration of idle time.
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
from typing import Any, Dict, Optional, Tuple

PROJECT_ROOT: str = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SESSION_FILE: str = os.path.join(PROJECT_ROOT, ".live_session.json")
DEFAULT_CDP_PORT: int = 9222
DEFAULT_INACTIVITY_TIMEOUT_SECONDS: int = 1800  # 30 minutes


class LiveSessionManager:
    """Manages the persistent browser daemon process and session state file."""

    @staticmethod
    def get_session_file_path() -> str:
        """Returns the absolute path to the local session state file."""
        return SESSION_FILE

    @staticmethod
    def is_cdp_port_active(port: int = DEFAULT_CDP_PORT) -> bool:
        """Pings the CDP version endpoint to determine if a live browser is running."""
        url = f"http://127.0.0.1:{port}/json/version"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "SessionManager"})
            with urllib.request.urlopen(req, timeout=1.5) as resp:
                return resp.status == 200
        except Exception:
            return False

    @classmethod
    def load_session_state(cls) -> Optional[Dict[str, Any]]:
        """Reads the active session state file if present and valid."""
        path = cls.get_session_file_path()
        if not os.path.isfile(path):
            return None

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            port = data.get("port", DEFAULT_CDP_PORT)
            pid = data.get("pid")

            # Check if port is actually responsive
            if cls.is_cdp_port_active(port):
                return data
            else:
                # Stale session file; remove it
                cls.clear_session_file()
                return None
        except Exception:
            cls.clear_session_file()
            return None

    @classmethod
    def touch_session(cls) -> None:
        """Updates the last_active timestamp for the inactivity watchdog."""
        state = cls.load_session_state()
        if state:
            state["last_active"] = time.time()
            path = cls.get_session_file_path()
            try:
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(state, f, indent=2)
            except Exception:
                pass

    @classmethod
    def save_session_state(
        cls,
        pid: int,
        port: int,
        timeout_seconds: int = DEFAULT_INACTIVITY_TIMEOUT_SECONDS,
        headless: bool = True,
        viewport: Optional[Dict[str, int]] = None,
    ) -> None:
        """Writes current session metadata to disk."""
        path = cls.get_session_file_path()
        data = {
            "pid": pid,
            "port": port,
            "headless": headless,
            "viewport": viewport or {"width": 1920, "height": 1080},
            "created_at": time.time(),
            "last_active": time.time(),
            "timeout_seconds": timeout_seconds,
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    @classmethod
    def clear_session_file(cls) -> None:
        """Removes the session state file from disk."""
        path = cls.get_session_file_path()
        if os.path.isfile(path):
            try:
                os.remove(path)
            except Exception:
                pass

    @classmethod
    def terminate_session(cls) -> bool:
        """Forcefully terminates the persistent browser process and clears state."""
        state = cls.load_session_state()
        cls.clear_session_file()
        if not state:
            return False

        pid = state.get("pid")
        if pid:
            try:
                from common.process_manager import get_process_manager
                return get_process_manager().kill_process_tree(pid, force=True)
            except Exception:
                pass
        return False

    @classmethod
    def launch_persistent_chrome(
        cls,
        executable_path: str,
        port: int = DEFAULT_CDP_PORT,
        headless: bool = True,
        viewport_width: int = 1920,
        viewport_height: int = 1080,
        user_agent: Optional[str] = None,
        timeout_seconds: int = DEFAULT_INACTIVITY_TIMEOUT_SECONDS,
    ) -> Tuple[int, int]:
        """Launches a standalone detached Chromium instance with remote debugging port enabled.

        Returns (pid, port).
        """
        # If already running and active, return existing
        existing = cls.load_session_state()
        if existing and cls.is_cdp_port_active(existing.get("port", port)):
            cls.touch_session()
            return existing["pid"], existing["port"]

        user_data_dir = os.path.join(PROJECT_ROOT, ".live_browser_profile")
        os.makedirs(user_data_dir, exist_ok=True)

        args = [
            executable_path,
            f"--remote-debugging-port={port}",
            f"--user-data-dir={user_data_dir}",
            f"--window-size={viewport_width},{viewport_height}",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-blink-features=AutomationControlled",
            "--disable-gpu",
            "--disable-dev-shm-usage",
            "--no-sandbox",
            "--keep-alive-for-test",
        ]
        if headless:
            args.append("--headless=new")
        if user_agent:
            args.append(f"--user-agent={user_agent}")
        args.append("about:blank")

        proc_pid: Optional[int] = None
        cmd_str = f'"{executable_path}" ' + " ".join(f'"{a}"' if " " in a else a for a in args[1:])

        if sys.platform == "win32":
            proc_pid = cls._launch_wmi_process(cmd_str)

        if proc_pid is None:
            popen_kwargs: Dict[str, Any] = {
                "stdout": subprocess.DEVNULL,
                "stderr": subprocess.DEVNULL,
            }
            if sys.platform == "win32":
                popen_kwargs["creationflags"] = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
            else:
                popen_kwargs["start_new_session"] = True

            proc = subprocess.Popen(args, **popen_kwargs)
            proc_pid = proc.pid

        # Wait up to 5 seconds for CDP port to become active
        start_time = time.time()
        active = False
        while time.time() - start_time < 5.0:
            if cls.is_cdp_port_active(port):
                active = True
                break
            time.sleep(0.2)

        if not active:
            if proc_pid:
                try:
                    if sys.platform == "win32":
                        subprocess.run(
                            ["taskkill", "/F", "/T", "/PID", str(proc_pid)],
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL,
                        )
                    else:
                        os.kill(proc_pid, 9)
                except Exception:
                    pass
            raise RuntimeError(f"Chromium failed to open CDP port {port} within 5 seconds.")

        cls.save_session_state(
            pid=proc_pid,
            port=port,
            timeout_seconds=timeout_seconds,
            headless=headless,
            viewport={"width": viewport_width, "height": viewport_height},
        )

        # Launch watchdog supervisor if timeout > 0
        if timeout_seconds > 0:
            cls._spawn_watchdog_supervisor(proc_pid, port, timeout_seconds)

        return proc_pid, port

    @classmethod
    def run_watchdog_loop(cls, browser_pid: int, port: int, timeout_seconds: int) -> None:
        """Runs the background watchdog loop until inactivity timeout or session clear."""
        session_file = cls.get_session_file_path()
        while True:
            time.sleep(30)
            if not os.path.isfile(session_file):
                break
            try:
                with open(session_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                last_active = data.get("last_active", time.time())
                if time.time() - last_active > timeout_seconds:
                    if sys.platform == "win32":
                        subprocess.run(
                            ["taskkill", "/F", "/T", "/PID", str(browser_pid)],
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL,
                        )
                    else:
                        os.kill(browser_pid, 9)
                    cls.clear_session_file()
                    break
            except Exception:
                break

    @classmethod
    def _launch_wmi_process(cls, cmd_str: str, cwd: Optional[str] = None) -> Optional[int]:
        """Launches a detached process via Windows WMI outside any parent Job Object."""
        from common.process_manager import get_process_manager
        working_dir = cwd or PROJECT_ROOT
        return get_process_manager().launch_detached(cmd_str, cwd=working_dir)

    @classmethod
    def _spawn_watchdog_supervisor(cls, browser_pid: int, port: int, timeout_seconds: int) -> None:
        """Launches a lightweight detached background watchdog to terminate idle browser."""
        from common.process_manager import get_process_manager
        watchdog_cmd = [
            sys.executable,
            "-m",
            "adapters.live_session_manager",
            str(browser_pid),
            str(port),
            str(timeout_seconds),
        ]
        get_process_manager().launch_detached(watchdog_cmd, cwd=PROJECT_ROOT)


if __name__ == "__main__":
    if len(sys.argv) >= 4:
        b_pid = int(sys.argv[1])
        b_port = int(sys.argv[2])
        b_timeout = int(sys.argv[3])
        LiveSessionManager.run_watchdog_loop(b_pid, b_port, b_timeout)
