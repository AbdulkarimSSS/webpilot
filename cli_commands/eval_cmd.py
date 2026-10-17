"""Eval / JavaScript execution command implementation for WebPilot CLI."""

from __future__ import annotations

import argparse
import json
import os
import sys

from cli_commands.common import get_supervisor_client
from common.telemetry import print_telemetry_banner
from supervisor.contracts import SupervisorActionRequest


def eval_cmd(args: argparse.Namespace) -> None:
    """Executes arbitrary JavaScript expression in the active page."""
    script = (getattr(args, "script", None) or getattr(args, "code", None) or "").strip()
    file_path = getattr(args, "file", None)
    if file_path:
        if not os.path.isfile(file_path):
            print(f"[!] Error: Script file not found: '{file_path}'", file=sys.stderr)
            sys.exit(1)
        with open(file_path, "r", encoding="utf-8") as f:
            script = f.read().strip()

    if not script:
        print("[!] Error: You must provide a JavaScript expression or script file (e.g. wp eval 'document.title').", file=sys.stderr)
        sys.exit(1)

    strip_header = getattr(args, "strip_header", False)

    if getattr(args, "standalone", False) and args.url:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=not args.headed)
            page = browser.new_page()
            page.goto(args.url)
            try:
                res = page.evaluate(script)
                browser.close()
                if getattr(args, "json", False):
                    print(json.dumps({"success": True, "result": res}, indent=2, ensure_ascii=False))
                else:
                    if res is not None:
                        print(json.dumps(res, indent=2, ensure_ascii=False) if isinstance(res, (dict, list)) else str(res))
            except Exception as exc:
                browser.close()
                print(f"[!] JavaScript Evaluation Error: {exc}", file=sys.stderr)
                sys.exit(1)
        return

    client = get_supervisor_client(args)
    req = SupervisorActionRequest(
        action="eval",
        url=args.url,
        cookies_path=getattr(args, "cookies", None),
        tab_index=args.tab,
        script=script,
        headed=args.headed,
        timeout_minutes=args.timeout_minutes,
        strip_header=strip_header,
        session_name=getattr(args, "session", None),
    )
    resp = client.execute(req)
    print_telemetry_banner(resp, strip_header=strip_header)

    if not resp.success:
        print(f"[!] JavaScript Evaluation Error: {resp.message}", file=sys.stderr)
        sys.exit(1)

    result_data = (resp.reactive_event or {}).get("result")
    if getattr(args, "json", False):
        print(json.dumps({"success": True, "result": result_data, "url": resp.active_url}, indent=2, ensure_ascii=False))
    else:
        if result_data is not None:
            if isinstance(result_data, (dict, list)):
                print(json.dumps(result_data, indent=2, ensure_ascii=False))
            else:
                print(str(result_data))
        else:
            print("[✓] Script executed successfully (undefined/void return).")
