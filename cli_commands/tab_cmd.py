"""Tab management command implementation for WebPilot CLI."""

from __future__ import annotations

import argparse
import json
import sys

from cli_commands.common import get_supervisor_client
from supervisor.contracts import SupervisorActionRequest


def tab_cmd(args: argparse.Namespace) -> None:
    """Manages browser tabs (list, new, switch, close, timeout)."""
    subaction = getattr(args, "tab_action", None)
    if not subaction:
        subaction = "list"
    subaction = subaction.lower().strip()

    client = get_supervisor_client(args)
    session_name = getattr(args, "session", None)

    # 1. Tab List
    if subaction == "list":
        # If user explicitly specified a session or did not request multi-session
        from adapters.live_session_manager import LiveSessionManager
        active_sessions = LiveSessionManager.list_all_active_sessions()

        if getattr(args, "json", False):
            # Fetch tabs for all active sessions or targeted session
            results: Dict[str, Any] = {"sessions": []}
            if session_name:
                req = SupervisorActionRequest(action="list_tabs", session_name=session_name)
                resp = client.execute(req)
                print(json.dumps(resp.to_dict(), indent=2, ensure_ascii=False))
                return

            if not active_sessions:
                # Query default via client
                req = SupervisorActionRequest(action="list_tabs")
                resp = client.execute(req)
                print(json.dumps(resp.to_dict(), indent=2, ensure_ascii=False))
                return

            for s_info in active_sessions:
                s_name = s_info.get("session_name", "default")
                req = SupervisorActionRequest(action="list_tabs", session_name=s_name)
                r = client.execute(req)
                results["sessions"].append({
                    "session_name": s_name,
                    "pid": s_info.get("pid"),
                    "port": s_info.get("port"),
                    "total_tabs": r.total_tabs,
                    "tabs": r.tabs,
                })
            print(json.dumps(results, indent=2, ensure_ascii=False))
            return

        print("\n" + "═" * 78)
        print(" 📑 WEBPILOT ACTIVE BROWSER INSTANCES & TABS")
        print("═" * 78)

        # If a single specific session is targeted
        if session_name:
            req = SupervisorActionRequest(action="list_tabs", session_name=session_name)
            resp = client.execute(req)
            if not resp.success:
                print(f"[!] Error listing tabs for session '{session_name}': {resp.message}", file=sys.stderr)
                sys.exit(1)
            _print_session_tabs(session_name, resp.browser_pid, resp.tabs)
            print("═" * 78 + "\n")
            return

        # If multiple sessions are running or default
        if not active_sessions:
            # Query default via client
            req = SupervisorActionRequest(action="list_tabs")
            resp = client.execute(req)
            if not resp.success:
                print(" [!] No active browser instances or open tabs detected.")
            else:
                _print_session_tabs("default (main)", resp.browser_pid, resp.tabs)
        else:
            for s_info in active_sessions:
                s_name = s_info.get("session_name", "default")
                s_pid = s_info.get("pid")
                s_port = s_info.get("port")
                req = SupervisorActionRequest(action="list_tabs", session_name=s_name)
                resp = client.execute(req)
                tabs = resp.tabs if resp.success else []
                _print_session_tabs(s_name, s_pid, tabs, port=s_port)

        print("═" * 78 + "\n")
        return

    # 2. Tab New
    elif subaction == "new":
        target_url = getattr(args, "target_url", None) or getattr(args, "tab_target", None) or getattr(args, "url", None)
        tab_timeout = getattr(args, "tab_timeout", None)
        req = SupervisorActionRequest(
            action="new_tab",
            url=target_url,
            session_name=session_name,
            tab_timeout=tab_timeout,
        )
        resp = client.execute(req)
        if getattr(args, "json", False):
            print(json.dumps(resp.to_dict(), indent=2, ensure_ascii=False))
            return
        if resp.success:
            print(f"[✓] {resp.message}")
            if resp.active_url:
                print(f"    URL: {resp.active_url}")
        else:
            print(f"[!] Error creating new tab: {resp.message}", file=sys.stderr)
            sys.exit(1)

    # 3. Tab Switch
    elif subaction == "switch":
        target_index = getattr(args, "tab_index", None)
        if target_index is None:
            target_index = getattr(args, "tab_target", None)
        if target_index is None:
            target_index = getattr(args, "tab", None)
        if target_index is None:
            print("[!] Error: Tab index is required for switch (e.g. wp tab switch 0).", file=sys.stderr)
            sys.exit(1)
        req = SupervisorActionRequest(action="switch_tab", tab_index=int(target_index), session_name=session_name)
        resp = client.execute(req)
        if getattr(args, "json", False):
            print(json.dumps(resp.to_dict(), indent=2, ensure_ascii=False))
            return
        if resp.success:
            print(f"[✓] {resp.message}")
        else:
            print(f"[!] Error switching tab: {resp.message}", file=sys.stderr)
            sys.exit(1)

    # 4. Tab Timeout Configuration
    elif subaction in ("timeout", "set-timeout", "set_timeout"):
        # e.g. wp tab timeout 0 15  (tab 0, 15 min) or wp tab timeout 15 (active tab, 15 min)
        target = getattr(args, "tab_target", None)
        timeout_arg = getattr(args, "tab_timeout", None)
        tab_idx: Optional[int] = getattr(args, "tab_index", None)

        if timeout_arg is None and target is not None:
            # Check if target is minutes or tab_index
            try:
                val = int(target)
                timeout_arg = val
            except ValueError:
                pass

        if timeout_arg is None:
            print("[!] Error: You must specify timeout minutes (e.g. wp tab timeout 15 or wp tab timeout --tab 0 15).", file=sys.stderr)
            sys.exit(1)

        req = SupervisorActionRequest(
            action="set_tab_timeout",
            tab_index=tab_idx,
            tab_timeout=int(timeout_arg),
            session_name=session_name,
        )
        resp = client.execute(req)
        if getattr(args, "json", False):
            print(json.dumps(resp.to_dict(), indent=2, ensure_ascii=False))
            return
        if resp.success:
            print(f"[✓] {resp.message}")
        else:
            print(f"[!] Error setting tab timeout: {resp.message}", file=sys.stderr)
            sys.exit(1)

    # 5. Tab Close
    elif subaction == "close":
        target_index = getattr(args, "tab_index", None)
        if target_index is None:
            target_index = getattr(args, "tab_target", None)
        if target_index is None:
            target_index = getattr(args, "tab", None)
        idx_int = int(target_index) if target_index is not None else None
        req = SupervisorActionRequest(action="close_tab", tab_index=idx_int, session_name=session_name)
        resp = client.execute(req)
        if getattr(args, "json", False):
            print(json.dumps(resp.to_dict(), indent=2, ensure_ascii=False))
            return
        if resp.success:
            print(f"[✓] {resp.message}")
        else:
            print(f"[!] Error closing tab: {resp.message}", file=sys.stderr)
            sys.exit(1)

    else:
        print(f"[!] Unknown tab action: '{subaction}'. Supported: list, new, switch, close, timeout.", file=sys.stderr)
        sys.exit(1)


def _print_session_tabs(
    session_name: str,
    pid: Optional[int],
    tabs: list[dict],
    port: Optional[int] = None,
) -> None:
    """Helper to print a single browser session and its child tabs hierarchy."""
    pid_str = f"PID: {pid}" if pid else "PID: N/A"
    port_str = f" | Port: {port}" if port else ""
    print(f"\n 🌐 Browser Instance: [{session_name}] ({pid_str}{port_str})")
    print(" ────────────────────────────────────────────────────────────────────────────")
    if not tabs:
        print("    [!] No open tabs detected in this browser.")
        return

    for t in tabs:
        active_mark = " [*ACTIVE*]" if t.get("is_active") else ""
        idx = t.get("index", 0)
        title = t.get("title") or "Untitled"
        url = t.get("url") or ""
        state = t.get("state") or "IDLE"
        open_since = t.get("open_since") or "unknown"
        last_act = t.get("last_activity") or "unknown"
        to_min = t.get("tab_timeout_minutes", 30)
        to_str = f"{to_min}m" if to_min > 0 else "disabled"

        print(f"    • Tab #{idx}{active_mark}: '{title}'")
        print(f"      ├─ State: {state} | Timeout: {to_str}")
        print(f"      ├─ Open: {open_since} | Last Active: {last_act}")
        print(f"      └─ URL: {url}")
