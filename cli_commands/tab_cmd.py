"""Tab management command implementation for WebPilot CLI."""

from __future__ import annotations

import argparse
import json
import sys

from cli_commands.common import get_supervisor_client
from supervisor.contracts import SupervisorActionRequest


def tab_cmd(args: argparse.Namespace) -> None:
    """Manages browser tabs (list, new, switch, close)."""
    subaction = getattr(args, "tab_action", None)
    if not subaction:
        subaction = "list"
    subaction = subaction.lower().strip()

    client = get_supervisor_client(args)

    # 1. Tab List
    if subaction == "list":
        req = SupervisorActionRequest(action="list_tabs")
        resp = client.execute(req)
        if getattr(args, "json", False):
            print(json.dumps(resp.to_dict(), indent=2, ensure_ascii=False))
            if not resp.success:
                sys.exit(1)
            return
        if not resp.success:
            print(f"[!] Error listing tabs: {resp.message}", file=sys.stderr)
            sys.exit(1)
        print("\n" + "═" * 70)
        print(" 📑 OPEN BROWSER TABS")
        print("═" * 70)
        if not resp.tabs:
            print(" [!] No open tabs detected in current session.")
        else:
            for t in resp.tabs:
                active_mark = " [*ACTIVE*]" if t.get("is_active") else ""
                print(f" • Tab #{t['index']}{active_mark}: '{t.get('title', 'Untitled')}'\n   URL: {t.get('url', '')}")
        print("═" * 70 + "\n")
        return

    # 2. Tab New
    elif subaction == "new":
        target_url = getattr(args, "target_url", None) or getattr(args, "tab_target", None) or getattr(args, "url", None)
        req = SupervisorActionRequest(action="new_tab", url=target_url)
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
        req = SupervisorActionRequest(action="switch_tab", tab_index=int(target_index))
        resp = client.execute(req)
        if getattr(args, "json", False):
            print(json.dumps(resp.to_dict(), indent=2, ensure_ascii=False))
            return
        if resp.success:
            print(f"[✓] {resp.message}")
        else:
            print(f"[!] Error switching tab: {resp.message}", file=sys.stderr)
            sys.exit(1)

    # 4. Tab Close
    elif subaction == "close":
        target_index = getattr(args, "tab_index", None)
        if target_index is None:
            target_index = getattr(args, "tab_target", None)
        if target_index is None:
            target_index = getattr(args, "tab", None)
        idx_int = int(target_index) if target_index is not None else None
        req = SupervisorActionRequest(action="close_tab", tab_index=idx_int)
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
        print(f"[!] Unknown tab action: '{subaction}'. Supported: list, new, switch, close.", file=sys.stderr)
        sys.exit(1)
