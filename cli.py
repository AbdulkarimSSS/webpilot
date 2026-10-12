"""WebPilot: Autonomous Multi-Tier Browser Automation Engine & AI Agent Web Runtime."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

try:
    from cli_parser import build_cli_parser
except ImportError:
    try:
        from .cli_parser import build_cli_parser
    except Exception:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from cli_parser import build_cli_parser
from common.telemetry import print_telemetry_banner
from orchestration.context import ApplyRequestContext, InspectionRequestContext
from orchestration.flow_orchestrator import FlowOrchestrator
from services.inspection_formatter_service import InspectionFormatterService
from supervisor.client import SupervisorClient
from supervisor.contracts import SupervisorActionRequest, SupervisorActionResponse


def get_base_url(args: argparse.Namespace) -> str:
    """Returns Master Supervisor HTTP base URL resolved from command-line arguments."""
    host = getattr(args, "host", None) or "127.0.0.1"
    port = getattr(args, "port", None) or 9333
    return f"http://{host}:{port}"


def get_supervisor_client(args: argparse.Namespace) -> SupervisorClient:
    """Instantiates a SupervisorClient configured with target host, port, and security token."""
    token = getattr(args, "token", None)
    return SupervisorClient(base_url=get_base_url(args), token=token)


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

    client = get_supervisor_client(args)

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

    from builder import FormPayloadBuilder
    from common.secrets import parse_and_resolve_fill_args

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

    client = get_supervisor_client(args)

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
        if getattr(args, "full_inspect", False) or getattr(args, "inspect_all", False):
            summary = InspectionFormatterService.format_summary(resp.schema)
            print("\n" + summary)
        else:
            touched_keys = [k for k, _ in resolved_pairs]
            if effective_data_path and os.path.isfile(effective_data_path):
                try:
                    loaded = FormPayloadBuilder.load_from_file(effective_data_path)
                    touched_keys.extend([k for k, _ in loaded])
                except Exception:
                    pass
            targeted_summary = InspectionFormatterService.format_targeted_summary(resp.schema, touched_keys)
            if targeted_summary:
                print("\n" + targeted_summary)
                print("\n💡 (Note: Use --full-inspect to display all form fields)")
            else:
                summary = InspectionFormatterService.format_summary(resp.schema)
                print("\n" + summary)

    if not resp.success:
        print(f"[!] Apply operation failed: {resp.message}")
        sys.exit(1)


def find_cmd(args: argparse.Namespace) -> None:
    """Probes a specific element/field and inspects its properties, options, or HTML."""
    client = get_supervisor_client(args)
    req = SupervisorActionRequest(
        action="probe",
        url=args.url,
        cookies_path=args.cookies,
        tab_index=args.tab,
        target_field=args.target,
        include_options=args.options,
        query=args.query,
        include_html=args.html,
        headed=args.headed,
        timeout_minutes=args.timeout_minutes,
    )
    resp = client.execute(req)
    print_telemetry_banner(resp)

    if not resp.success:
        print(f"\n[!] {resp.message}")
        sys.exit(1)

    details = resp.field_details or {}
    if getattr(args, "json", False):
        print(json.dumps(details, indent=2, ensure_ascii=False))
        return

    print("\n" + "═" * 70)
    local_id_str = details.get("local_id") or "@fld"
    type_str = (details.get("type") or "element").upper()
    print(f" 🔍 WEBPILOT ELEMENT DIAGNOSTIC | {local_id_str} | {type_str}")
    print("═" * 70)
    print(f" • Label       : {details.get('label')}")
    print(f" • Local ID    : {details.get('local_id')}")
    print(f" • DOM ID      : {details.get('id')}")
    print(f" • Widget Type : {details.get('type')}")
    print(f" • Current Val : {details.get('value')}")
    print(f" • Required    : {details.get('required')}")
    print(f" • Disabled    : {details.get('disabled')}")
    print(f" • Visible     : {details.get('visible')}")

    opts = details.get("options")
    if opts is not None:
        total_cnt = details.get("options_count", len(opts))
        print(f"\n 📋 Options ({total_cnt} total):")
        for o in opts[:30]:
            if isinstance(o, dict):
                loc = f"[{o.get('local_id')}] " if o.get('local_id') else ""
                val_part = f" (value: {o.get('value')})" if o.get('value') and o.get('value') != o.get('text') else ""
                print(f"   • {loc}'{o.get('text')}'{val_part}")
            else:
                print(f"   • {o}")
        if len(opts) > 30:
            print(f"   ... and {len(opts) - 30} more options (use --query to filter).")

    outer_html = details.get("outerHTML") or details.get("html")
    if args.html and outer_html:
        print(f"\n 🌐 Outer HTML:\n{outer_html}")
    print("═" * 70 + "\n")


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
    base_dir = Path(__file__).resolve().parent
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
    sys.exit(1)


def main():
    if "--run-daemon" in sys.argv:
        from supervisor.master_daemon import run_master_daemon
        idx = sys.argv.index("--run-daemon")
        port = 9333
        token = os.environ.get("WEBPILOT_SUPERVISOR_TOKEN")
        if len(sys.argv) > idx + 1 and sys.argv[idx + 1].isdigit():
            port = int(sys.argv[idx + 1])
        if not token and len(sys.argv) > idx + 2:
            token = sys.argv[idx + 2]
        run_master_daemon(port=port, token=token)
        return

    if "--run-worker" in sys.argv:
        from supervisor.worker_process import run_worker_loop
        run_worker_loop()
        return

    parser = build_cli_parser()
    args = parser.parse_args()
    try:
        if args.command == "inspect":
            inspect_cmd(args)
        elif args.command == "apply":
            apply_cmd(args)
        elif args.command in ("find", "probe"):
            find_cmd(args)
        elif args.command == "shell":
            shell_cmd(args)
        elif args.command == "service":
            service_cmd(args)
        elif args.command == "install":
            install_cmd(args)
        elif args.command == "skill":
            skill_cmd(args)
    except KeyboardInterrupt:
        print("\n[!] Operation cancelled by user.")
        sys.exit(130)
    except Exception as exc:
        print(f"\n[!] Error: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
