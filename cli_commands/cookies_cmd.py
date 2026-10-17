"""Cookies inspection and export command implementation for WebPilot CLI."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Dict, List

from cli_commands.common import get_supervisor_client
from common.cookies import save_cookies
from common.telemetry import print_telemetry_banner
from supervisor.contracts import SupervisorActionRequest


def cookies_cmd(args: argparse.Namespace) -> None:
    """Manages browser session cookies (export, dump, list, save)."""
    subaction = getattr(args, "cookies_action", None) or "export"
    subaction = subaction.lower().strip()

    strip_header = getattr(args, "strip_header", False)
    output_path = getattr(args, "output_path", None)
    query = getattr(args, "query", None)
    url = getattr(args, "url", None)

    if getattr(args, "standalone", False) and url:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=not args.headed)
            context = browser.new_context()
            page = context.new_page()
            page.goto(url)
            cookies = context.cookies()
            browser.close()

            if query:
                q_lower = query.lower()
                cookies = [
                    c for c in cookies
                    if q_lower in str(c.get("domain", "")).lower() or q_lower in str(c.get("name", "")).lower()
                ]

            if output_path:
                save_cookies(output_path, cookies)
                print(f"[✓] Successfully exported {len(cookies)} cookies to: {output_path}")
            elif getattr(args, "json", False):
                print(json.dumps(cookies, indent=2, ensure_ascii=False))
            else:
                _print_cookies_table(cookies, url=url)
        return

    client = get_supervisor_client(args)
    req = SupervisorActionRequest(
        action="cookies",
        url=url,
        query=query,
        output_path=output_path,
        tab_index=args.tab,
        headed=args.headed,
        timeout_minutes=getattr(args, "timeout_minutes", 30),
        strip_header=strip_header,
    )

    resp = client.execute(req)

    if getattr(args, "json", False):
        print(json.dumps(resp.to_dict(), indent=2, ensure_ascii=False))
        if not resp.success:
            sys.exit(1)
        return

    if not resp.success:
        print(f"[!] Error handling cookies: {resp.message}", file=sys.stderr)
        sys.exit(1)

    if not strip_header and resp.telemetry:
        print_telemetry_banner(resp.telemetry)

    cookies = resp.cookies or []
    if output_path:
        print(f"[✓] {resp.message}")
    else:
        _print_cookies_table(cookies, url=resp.active_url)


def _print_cookies_table(cookies: List[Dict[str, Any]], url: str = "") -> None:
    """Formats and prints cookie details in an elegant console table."""
    print("\n" + "═" * 78)
    header = f" 🍪 ACTIVE SESSION COOKIES ({len(cookies)} cookies)"
    if url:
        header += f" | {url}"
    print(header)
    print("═" * 78)

    if not cookies:
        print(" [!] No cookies found in active browser session matching criteria.")
    else:
        for idx, c in enumerate(cookies, 1):
            name = c.get("name", "")
            val = c.get("value", "")
            # Truncate value if very long for neat display
            display_val = val if len(val) <= 40 else val[:37] + "..."
            domain = c.get("domain", "")
            path = c.get("path", "/")
            secure = "🔒" if c.get("secure") else "  "
            http_only = "HttpOnly" if c.get("httpOnly") else ""
            same_site = c.get("sameSite", "")
            flags = " ".join(filter(Boolean, [secure.strip(), http_only, same_site])).strip()
            flag_str = f" [{flags}]" if flags else ""

            print(f" {idx:2d}. {name} = {display_val}")
            print(f"     Domain: {domain} | Path: {path}{flag_str}")
    print("═" * 78 + "\n")


Boolean = lambda x: bool(x)
