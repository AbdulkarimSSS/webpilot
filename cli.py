"""WebPilot: Autonomous Multi-Tier Browser Automation Engine & AI Agent Web Runtime."""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any, Dict

from orchestration.context import ApplyRequestContext, InspectionRequestContext
from orchestration.flow_orchestrator import FlowOrchestrator
from services.inspection_formatter_service import InspectionFormatterService
from supervisor.client import DEFAULT_SUPERVISOR_URL, SupervisorClient
from supervisor.contracts import SupervisorActionRequest, SupervisorActionResponse


def print_telemetry_banner(resp: SupervisorActionResponse) -> None:
    """Renders real-time process tree telemetry across Layer 1, 2, and 3."""
    if resp.browser_pid or resp.worker_pid or resp.active_url:
        print("\n" + "═" * 70)
        print(" 🚀 WEBPILOT | AUTONOMOUS BROWSER RUNTIME & SUPERVISOR TELEMETRY")
        print("═" * 70)
        if resp.worker_pid:
            print(f" • Layer 2 Worker PID   : {resp.worker_pid}")
        if resp.browser_pid:
            print(f" • Layer 3 Chromium PID : {resp.browser_pid}")
        if resp.active_tab_index is not None:
            print(f" • Active Tab Index     : Tab #{resp.active_tab_index} (Total: {resp.total_tabs})")
        if resp.active_title:
            print(f" • Active Page Title    : {resp.active_title}")
        if resp.active_url:
            print(f" • Active Page URL      : {resp.active_url}")
        print("═" * 70)


def get_base_url(args: argparse.Namespace) -> str:
    host = getattr(args, "host", None) or "127.0.0.1"
    port = getattr(args, "port", None) or 9333
    return f"http://{host}:{port}"


def inspect_cmd(args: argparse.Namespace) -> None:
    """Executes the universal inspection workflow."""
    if getattr(args, "standalone", False):
        req = InspectionRequestContext(
            url=args.url,
            output_path=args.output,
            screenshot_path=args.screenshot,
            cookies_path=args.cookies,
            unpack_options=args.unpack_options,
            headed=args.headed,
            config_path=args.config,
            device_profile_path=args.device_profile,
            env_file=args.env_file,
            keep_alive=args.keep_alive,
            close_session=args.close_session,
            list_tabs=args.list_tabs,
            tab_index=args.tab,
            timeout_minutes=args.timeout_minutes,
        )
        FlowOrchestrator.execute_inspection_flow(req)
        return

    # Multi-tier Master Supervisor execution (default)
    client = SupervisorClient(base_url=get_base_url(args))

    if args.close_session:
        res = client.stop_service()
        print(f"[✓] {res.message}")
        return

    if args.list_tabs:
        resp = client.execute(SupervisorActionRequest(action="list_tabs"))
        print("\n" + "═" * 70)
        print(" 📑 OPEN BROWSER TABS")
        print("═" * 70)
        if not resp.tabs:
            print(" [!] No open tabs detected in current session.")
        else:
            for t in resp.tabs:
                active_mark = " [*ACTIVE*]" if t.get("is_active") else ""
                print(f" • Tab #{t['index']}{active_mark}: '{t['title']}'\n   URL: {t['url']}")
        print("═" * 70 + "\n")
        return

    req = SupervisorActionRequest(
        action="inspect",
        url=args.url,
        cookies_path=args.cookies,
        screenshot_path=args.screenshot,
        tab_index=args.tab,
        unpack_options=args.unpack_options,
        headed=args.headed,
        timeout_minutes=args.timeout_minutes,
    )
    resp = client.execute(req)
    print_telemetry_banner(resp)
    for line in resp.output_lines:
        print(line)

    if resp.schema:
        if args.output:
            with open(args.output, "w", encoding="utf-8") as f:
                json.dump(resp.schema, f, indent=2, ensure_ascii=False)
            print(f"[✓] Full schema successfully saved to: {args.output}")
        summary = InspectionFormatterService.format_summary(resp.schema)
        print("\n" + summary)

    if not resp.success:
        print(f"[!] Inspection failed: {resp.message}")
        sys.exit(1)


def apply_cmd(args: argparse.Namespace) -> None:
    """Executes the universal form filling and submission workflow."""
    auto_inspect = not getattr(args, "no_auto_inspect", False)

    from common.secrets import parse_and_resolve_fill_args
    from builder import FormPayloadBuilder

    raw_fill_args = args.fill or []
    resolved_pairs = parse_and_resolve_fill_args(raw_fill_args)
    effective_fill_args = [f"{k}={v}" for k, v in resolved_pairs]

    effective_data_path = args.data
    if args.data in ("-", "@stdin"):
        try:
            stdin_json = json.load(sys.stdin)
            stdin_pairs = FormPayloadBuilder.normalize_payload(stdin_json)
            effective_fill_args.extend([f"{k}={v}" for k, v in stdin_pairs])
            effective_data_path = None
        except Exception as exc:
            print(f"[!] Error reading JSON payload from stdin: {exc}", file=sys.stderr)
            sys.exit(1)

    if getattr(args, "standalone", False):
        req = ApplyRequestContext(
            url=args.url,
            data_path=effective_data_path,
            fill_arguments=effective_fill_args,
            press_buttons=args.press or [],
            upload_files=args.upload or [],
            cookies_path=args.cookies,
            submit=args.submit,
            screenshot_path=args.screenshot,
            headed=args.headed,
            config_path=args.config,
            device_profile_path=args.device_profile,
            env_file=args.env_file,
            keep_alive=args.keep_alive,
            close_session=args.close_session,
            list_tabs=args.list_tabs,
            tab_index=args.tab,
            timeout_minutes=args.timeout_minutes,
            auto_inspect=auto_inspect,
        )
        FlowOrchestrator.execute_apply_flow(req)
        return

    # Multi-tier Master Supervisor execution (default)
    client = SupervisorClient(base_url=get_base_url(args))

    if args.close_session:
        res = client.stop_service()
        print(f"[✓] {res.message}")
        return

    if args.list_tabs:
        resp = client.execute(SupervisorActionRequest(action="list_tabs"))
        print("\n" + "═" * 70)
        print(" 📑 OPEN BROWSER TABS")
        print("═" * 70)
        if not resp.tabs:
            print(" [!] No open tabs detected in current session.")
        else:
            for t in resp.tabs:
                active_mark = " [*ACTIVE*]" if t.get("is_active") else ""
                print(f" • Tab #{t['index']}{active_mark}: '{t['title']}'\n   URL: {t['url']}")
        print("═" * 70 + "\n")
        return

    req = SupervisorActionRequest(
        action="apply",
        url=args.url,
        data_path=effective_data_path,
        fill_arguments=effective_fill_args,
        press_buttons=args.press or [],
        upload_files=args.upload or [],
        cookies_path=args.cookies,
        submit=args.submit,
        screenshot_path=args.screenshot,
        headed=args.headed,
        auto_inspect=auto_inspect,
        tab_index=args.tab,
        timeout_minutes=args.timeout_minutes,
    )
    resp = client.execute(req)
    print_telemetry_banner(resp)
    for line in resp.output_lines:
        print(line)

    if resp.schema and auto_inspect:
        summary = InspectionFormatterService.format_summary(resp.schema)
        print("\n" + summary)

    if not resp.success:
        print(f"[!] Apply operation failed: {resp.message}")
        sys.exit(1)


def service_cmd(args: argparse.Namespace) -> None:
    """Manages the Master Supervisor daemon (status, restart, stop, start)."""
    client = SupervisorClient(base_url=get_base_url(args))
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
    run_interactive_shell(host=args.host, port=args.port)


def main():
    if "--run-daemon" in sys.argv:
        from supervisor.master_daemon import run_master_daemon
        idx = sys.argv.index("--run-daemon")
        port = 9333
        if len(sys.argv) > idx + 1 and sys.argv[idx + 1].isdigit():
            port = int(sys.argv[idx + 1])
        run_master_daemon(port=port)
        return

    if "--run-worker" in sys.argv:
        from supervisor.worker_process import run_worker_loop
        run_worker_loop()
        return

    parser = argparse.ArgumentParser(
        prog="webpilot",
        description="WebPilot: Autonomous Multi-Tier Browser Automation Engine & AI Agent Web Runtime",
    )
    parser.add_argument("--config", help="Path to custom settings.json configuration file")
    parser.add_argument("--device-profile", help="Path to custom device_profile.json configuration file")
    parser.add_argument("--env-file", help="Path to custom .env file")
    parser.add_argument("--host", default="127.0.0.1", help="Supervisor host address (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=9333, help="Supervisor port (default: 9333)")

    subparsers = parser.add_subparsers(dest="command", required=True)

    # 1. Inspect Subcommand
    p_inspect = subparsers.add_parser("inspect", help="Inspect URL and return full schema of inputs, dropdowns, buttons, uploads")
    p_inspect.add_argument("--url", nargs="?", default=None, help="Target URL to inspect (optional if connecting to existing live session)")
    p_inspect.add_argument("--cookies", help="Path to cookies JSON file")
    p_inspect.add_argument("--output", help="Path to save full inspection JSON schema")
    p_inspect.add_argument("--screenshot", help="Path to save visual screenshot")
    p_inspect.add_argument("--unpack-options", action="store_true", help="Probe dropdowns to sample options (burns more tokens/time)")
    p_inspect.add_argument("--headed", action="store_true", help="Run headed browser")
    p_inspect.add_argument("--keep-alive", action="store_true", help="Keep browser open across sequential commands")
    p_inspect.add_argument("--close-session", action="store_true", help="Terminate active live browser session and exit")
    p_inspect.add_argument("--list-tabs", action="store_true", help="List all open tabs in active session")
    p_inspect.add_argument("--tab", type=int, default=None, help="Target specific tab by index (0-based)")
    p_inspect.add_argument("--timeout-minutes", type=int, default=30, help="Inactivity timeout in minutes (default: 30, 0 = disable)")
    p_inspect.add_argument("--standalone", action="store_true", help="Run in-process via FlowOrchestrator instead of Master Supervisor")
    p_inspect.add_argument("--host", default="127.0.0.1", help="Supervisor host address")
    p_inspect.add_argument("--port", type=int, default=9333, help="Supervisor port")
    p_inspect.add_argument("--config", help="Path to custom settings.json configuration file")
    p_inspect.add_argument("--device-profile", help="Path to custom device_profile.json configuration file")
    p_inspect.add_argument("--env-file", help="Path to custom .env file")

    # 2. Apply / Fill Subcommand
    p_apply = subparsers.add_parser("apply", help="Fill fields dynamically via JSON file or CLI flags, and optionally submit")
    p_apply.add_argument("--url", nargs="?", default=None, help="Target URL to fill (optional if connecting to existing live session)")
    p_apply.add_argument("--data", help="Path to JSON file containing key-value mappings")
    p_apply.add_argument("--fill", action="append", help="Field to set, e.g. --fill 'First Name=John' (can be repeated)")
    p_apply.add_argument("--press", action="append", help="Button to click, e.g. --press 'Next' (can be repeated)")
    p_apply.add_argument("--upload", action="append", help="File to upload, e.g. --upload 'resume=sample.pdf' (can be repeated)")
    p_apply.add_argument("--cookies", help="Path to cookies JSON file")
    p_apply.add_argument("--submit", action="store_true", help="Click Apply/Submit after filling")
    p_apply.add_argument("--screenshot", help="Path to save screenshot")
    p_apply.add_argument("--headed", action="store_true", help="Run headed browser")
    p_apply.add_argument("--keep-alive", action="store_true", help="Keep browser open across sequential commands")
    p_apply.add_argument("--close-session", action="store_true", help="Terminate active live browser session and exit")
    p_apply.add_argument("--list-tabs", action="store_true", help="List all open tabs in active session")
    p_apply.add_argument("--tab", type=int, default=None, help="Target specific tab by index (0-based)")
    p_apply.add_argument("--timeout-minutes", type=int, default=30, help="Inactivity timeout in minutes (default: 30, 0 = disable)")
    p_apply.add_argument("--no-auto-inspect", action="store_true", help="Disable automatic post-interaction form inspection")
    p_apply.add_argument("--standalone", action="store_true", help="Run in-process via FlowOrchestrator instead of Master Supervisor")
    p_apply.add_argument("--host", default="127.0.0.1", help="Supervisor host address")
    p_apply.add_argument("--port", type=int, default=9333, help="Supervisor port")
    p_apply.add_argument("--config", help="Path to custom settings.json configuration file")
    p_apply.add_argument("--device-profile", help="Path to custom device_profile.json configuration file")
    p_apply.add_argument("--env-file", help="Path to custom .env file")

    # 3. Interactive REPL Shell Subcommand
    p_shell = subparsers.add_parser("shell", help="Launch interactive REPL automation shell")
    p_shell.add_argument("--host", default="127.0.0.1", help="Supervisor host address")
    p_shell.add_argument("--port", type=int, default=9333, help="Supervisor port")

    # 4. Supervisor Service Management Subcommand
    p_service = subparsers.add_parser("service", help="Manage Master Supervisor background daemon")
    p_service.add_argument("service_action", choices=["status", "restart", "stop", "start"], help="Action to execute")
    p_service.add_argument("--host", default="127.0.0.1", help="Supervisor host address")
    p_service.add_argument("--port", type=int, default=9333, help="Supervisor port")

    # 5. Browser Binaries Installation Subcommand
    p_install = subparsers.add_parser("install", help="Download and configure required Playwright Chromium browser")
    p_install.add_argument("--all", action="store_true", help="Download all browsers (Chromium, Firefox, WebKit)")

    args = parser.parse_args()
    try:
        if args.command == "inspect":
            inspect_cmd(args)
        elif args.command == "apply":
            apply_cmd(args)
        elif args.command == "shell":
            shell_cmd(args)
        elif args.command == "service":
            service_cmd(args)
        elif args.command == "install":
            install_cmd(args)
    except KeyboardInterrupt:
        print("\n[!] Operation cancelled by user.")
        sys.exit(130)
    except Exception as exc:
        print(f"\n[!] Error: {exc}", file=sys.stderr)
        sys.exit(1)


def install_cmd(args: argparse.Namespace) -> None:
    """Installs required Playwright browser binaries."""
    import subprocess
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


if __name__ == "__main__":
    main()
