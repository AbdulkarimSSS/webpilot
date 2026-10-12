"""Service, shell, install, and skill commands implementation for WebPilot CLI."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from cli_commands.common import get_supervisor_client
from supervisor.contracts import SupervisorActionRequest


def service_cmd(args: argparse.Namespace) -> None:
    """Manages the Master Supervisor daemon (status, restart, stop, start)."""
    client = get_supervisor_client(args)
    action = args.service_action.lower()

    if action == "status":
        status_info = client.get_status()
        print("\n" + "═" * 70)
        print(" 🛡️ MASTER SUPERVISOR & MULTI-TIER DAEMON STATUS")
        print("═" * 70)
        if not status_info.get("supervisor_alive"):
            print(" • Layer 1 Supervisor   : ⭕ STOPPED / INACTIVE")
            print(" • Layer 2 Worker       : ⭕ INACTIVE")
            print(" • Layer 3 Chromium     : ⭕ INACTIVE")
        else:
            print(f" • Layer 1 Supervisor   : 🟢 RUNNING (PID: {status_info.get('supervisor_pid')}, Port: {status_info.get('supervisor_port')})")
            worker_alive = status_info.get("worker_alive", False)
            worker_mark = "🟢 RUNNING" if worker_alive else "⚪ IDLE"
            print(f" • Layer 2 Worker       : {worker_mark} (PID: {status_info.get('worker_pid') or 'None'})")
            print(f" • Watchdog Inactivity  : {status_info.get('idle_seconds', 0)}s idle / {status_info.get('inactivity_timeout_seconds')}s limit")

            if worker_alive:
                worker_resp = client.execute(SupervisorActionRequest(action="status"))
                if worker_resp.browser_pid:
                    print(f" • Layer 3 Chromium     : 🟢 RUNNING (PID: {worker_resp.browser_pid})")
                    print(f" • Active Page          : {worker_resp.active_title} ({worker_resp.active_url})")
                    print(f" • Open Tabs Count      : {worker_resp.total_tabs}")
                else:
                    print(" • Layer 3 Chromium     : ⚪ NOT SPAWNED YET")
        print("═" * 70 + "\n")

    elif action == "restart":
        res = client.restart_worker()
        print(f"[*] {res.message}")

    elif action == "stop":
        res = client.stop_service()
        print(f"[✓] {res.message}")

    elif action == "start":
        client.ensure_running()
        print("[✓] Master Supervisor is active and listening.")

    else:
        print(f"[!] Unknown service action: '{action}'. Use status, restart, stop, or start.")


def shell_cmd(args: argparse.Namespace) -> None:
    """Launches the interactive REPL shell."""
    from supervisor.shell import run_interactive_shell
    run_interactive_shell(host=args.host, port=args.port, token=getattr(args, "token", None))


def install_cmd(args: argparse.Namespace) -> None:
    """Installs required Playwright browser binaries."""
    print("\n" + "═" * 70)
    print(" 🚀 WEBPILOT | BROWSER BINARY INSTALLER")
    print("═" * 70)
    target = "all" if getattr(args, "all", False) else "chromium"
    cmd = [sys.executable, "-m", "playwright", "install"]
    if target != "all":
        cmd.append("chromium")
    print(f"[*] Downloading and configuring Playwright {target} browser binaries...")
    try:
        subprocess.run(cmd, check=True)
        print("\n[✓] Browser binaries downloaded and configured successfully!")
    except Exception as exc:
        print(f"\n[!] Failed to install browser binaries: {exc}", file=sys.stderr)
        print("Please check your internet connection or run 'playwright install chromium' manually.", file=sys.stderr)
        sys.exit(1)


def skill_cmd(args: argparse.Namespace) -> None:
    """Outputs the AI agent skill specification (SKILL.md) to terminal."""
    base_dir = Path(__file__).resolve().parent.parent
    candidates = [
        base_dir / "skills" / "webpilot-automation" / "SKILL.md",
        base_dir.parent / "skills" / "webpilot-automation" / "SKILL.md",
        Path.home() / ".gemini" / "config" / "skills" / "webpilot-automation" / "SKILL.md",
    ]
    for candidate in candidates:
        if candidate.exists():
            print(candidate.read_text(encoding="utf-8"))
            return

    print("[!] Error: webpilot-automation/SKILL.md not found in package.", file=sys.stderr)
