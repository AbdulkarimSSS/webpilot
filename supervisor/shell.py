"""Interactive REPL Shell Mode (Thin Client).

Provides an interactive console prompt for step-by-step browser automation,
communicating directly with the Master Supervisor (Layer 1).
"""

from __future__ import annotations

import os
import sys
from typing import List

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from services.inspection_formatter_service import InspectionFormatterService
from supervisor.client import SupervisorClient
from supervisor.contracts import SupervisorActionRequest, SupervisorActionResponse


def run_interactive_shell(host: str = "127.0.0.1", port: int = 9333):
    """Runs the interactive REPL session."""
    client = SupervisorClient(base_url=f"http://{host}:{port}")
    try:
        client.ensure_running()
    except Exception as exc:
        print(f"[!] Failed to connect to Master Supervisor: {exc}")
        return

    print("\n" + "═" * 70)
    print(" 🚀 WEBPILOT — INTERACTIVE AUTONOMOUS REPL SHELL")
    print("═" * 70)
    print(" Commands:")
    print("  • open <url>             : Navigate to target URL")
    print("  • fill <k>=<v> [<k>=<v>] : Populate one or more fields")
    print("  • press <button_text>    : Click button with reactive mutation tracking")
    print("  • upload <key>=<path>    : Upload document/CV")
    print("  • inspect                : Inspect current page form schema")
    print("  • tabs                   : List all open tabs")
    print("  • tab <index>            : Switch to specific tab index (0-based)")
    print("  • cookies <path>         : Save refreshed session cookies")
    print("  • screenshot <path>      : Capture visual screenshot")
    print("  • status                 : View runtime PIDs and tier health")
    print("  • restart                : Cascading kill of Layer 2 & 3 with instant restart")
    print("  • exit / quit            : Exit shell")
    print("═" * 70 + "\n")

    current_url = ""

    while True:
        try:
            line = input("webpilot> ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nExiting interactive shell.")
            break

        if not line:
            continue

        parts = line.split(maxsplit=1)
        cmd = parts[0].lower()
        arg = parts[1] if len(parts) > 1 else ""

        if cmd in ("exit", "quit", "q"):
            print("Exiting interactive shell. Background supervisor remains active.")
            break

        elif cmd == "status":
            st = client.get_status()
            print("\n[📊 Supervisor & Worker Telemetry]:")
            for k, v in st.items():
                print(f" • {k:<25}: {v}")
            print()

        elif cmd == "restart":
            print("[*] Initiating cascading kill of Layer 2 & 3...")
            res = client.restart_worker()
            print(f"[✓] {res.message}\n")

        elif cmd in ("open", "goto"):
            if not arg:
                print("[!] Error: URL required, e.g. open https://example.com")
                continue
            current_url = arg.strip()
            print(f"[*] Navigating to: {current_url}...")
            req = SupervisorActionRequest(action="apply", url=current_url)
            res = client.execute(req)
            _print_apply_response(res)

        elif cmd == "fill":
            if not arg:
                print("[!] Error: field mapping required, e.g. fill username=user@mail.com")
                continue
            fill_args = [a.strip() for a in arg.split(" ") if "=" in a]
            if not fill_args:
                fill_args = [arg.strip()]
            req = SupervisorActionRequest(action="apply", fill_arguments=fill_args)
            res = client.execute(req)
            _print_apply_response(res)

        elif cmd == "press":
            if not arg:
                print("[!] Error: button label required, e.g. press 'Sign In'")
                continue
            btn = arg.strip().strip("'\"")
            print(f"[*] Pressing button: '{btn}'...")
            req = SupervisorActionRequest(action="apply", press_buttons=[btn])
            res = client.execute(req)
            _print_apply_response(res)

        elif cmd == "upload":
            if not arg:
                print("[!] Error: upload path required, e.g. upload resume=C:/cv.pdf")
                continue
            req = SupervisorActionRequest(action="apply", upload_files=[arg.strip()])
            res = client.execute(req)
            _print_apply_response(res)

        elif cmd == "inspect":
            print("[*] Inspecting active page schema...")
            req = SupervisorActionRequest(action="inspect")
            res = client.execute(req)
            if res.schema:
                print("\n" + InspectionFormatterService.format_summary(res.schema))
            else:
                print(f"[!] Inspection failed: {res.message}")

        elif cmd == "tabs":
            req = SupervisorActionRequest(action="list_tabs")
            res = client.execute(req)
            print("\n" + "═" * 70)
            print(" 📑 OPEN BROWSER TABS")
            print("═" * 70)
            if not res.tabs:
                print(" [!] No open tabs detected.")
            else:
                for t in res.tabs:
                    act = " [*ACTIVE*]" if t.get("is_active") else ""
                    print(f" • Tab #{t['index']}{act}: '{t['title']}'\n   URL: {t['url']}")
            print("═" * 70 + "\n")

        elif cmd == "tab":
            if not arg or not arg.isdigit():
                print("[!] Error: Tab index required, e.g. tab 0")
                continue
            idx = int(arg)
            req = SupervisorActionRequest(action="switch_tab", tab_index=idx)
            res = client.execute(req)
            print(f"[✓] {res.message}\n")

        elif cmd == "cookies":
            save_path = arg.strip() or "session_cookies.json"
            req = SupervisorActionRequest(action="apply", cookies_path=save_path)
            res = client.execute(req)
            print(f"[✓] Cookies requested for save: {save_path}\n")

        elif cmd == "screenshot":
            save_path = arg.strip() or "screenshot.png"
            req = SupervisorActionRequest(action="apply", screenshot_path=save_path)
            res = client.execute(req)
            print(f"[✓] Screenshot saved: {save_path}\n")

        else:
            print(f"[!] Unknown command '{cmd}'. Type 'open', 'fill', 'press', 'inspect', 'tabs', 'restart', or 'exit'.")


def _print_apply_response(res: SupervisorActionResponse):
    """Formats output lines and reactive events from worker."""
    if not res.success:
        print(f"[!] Action failed: {res.message}")
        return

    print(" 📄 ACTIVE PAGE TELEMETRY")
    print("─" * 70)
    print(f" • Tab #{res.active_tab_index} (Total: {res.total_tabs}) | Title: '{res.active_title}'")
    print(f" • URL: {res.active_url}")
    print("═" * 70)

    for line in res.output_lines:
        print(f" {line}")

    if res.reactive_event:
        rev = res.reactive_event
        if rev.get("redirected"):
            print(f"\n[🔀 Redirect / Navigation]: {rev.get('new_url')}")
        if rev.get("new_window"):
            print(f"\n[🌐 New Window Opened]: {rev.get('new_url')}")
        if rev.get("modal_opened"):
            print(f"\n[🪟 Modal Appeared]: {rev.get('modal_text')}")
        if res.schema:
            print(InspectionFormatterService.format_summary(res.schema))

    print()
