"""CLI command handler for 'webpilot wait' / 'wp wait'."""

from __future__ import annotations

import argparse
import sys

from cli_commands.common import get_supervisor_client
from common.telemetry import print_telemetry_banner
from supervisor.contracts import SupervisorActionRequest


def wait_cmd(args: argparse.Namespace) -> None:
    """Explicitly waits for an element selector, network idle, or dynamic AJAX rendering."""
    client = get_supervisor_client(args)
    client.ensure_running()

    strip_header = getattr(args, "strip_header", False)
    selector = getattr(args, "selector", None) or getattr(args, "target", None)
    timeout_ms = getattr(args, "timeout", 10000)
    state = getattr(args, "state", "visible")
    network_idle = getattr(args, "network_idle", False)
    url = getattr(args, "url", None)
    tab_index = getattr(args, "tab", None)
    session_name = getattr(args, "session", None)

    if not selector and not network_idle and not url:
        print("[!] Error: 'wp wait' requires at least one condition: --selector <sel>, --network-idle, or --url <url>.", file=sys.stderr)
        sys.exit(1)

    req = SupervisorActionRequest(
        action="wait",
        selector=selector,
        wait_timeout=timeout_ms,
        wait_state=state,
        network_idle=network_idle,
        url=url,
        tab_index=tab_index,
        session_name=session_name,
        strip_header=strip_header,
    )

    resp = client.execute(req)
    print_telemetry_banner(resp, strip_header=strip_header)

    if not resp.success:
        print(f"\n[!] Wait failed: {resp.message}", file=sys.stderr)
        sys.exit(1)

    if not strip_header:
        target_info = selector or ("network idle" if network_idle else "readiness")
        print(f"[✓] Wait succeeded for {target_info} (timeout: {timeout_ms}ms).")
