"""CLI command handler for 'webpilot read' / 'wp read'."""

from __future__ import annotations

import argparse
import sys
from typing import Optional

from cli_commands.common import get_supervisor_client
from supervisor.contracts import SupervisorActionRequest


def read_cmd(args: argparse.Namespace) -> None:
    """Executes high-density clean markdown extraction via Trafilatura."""
    client = get_supervisor_client(args)
    client.ensure_running()

    url = getattr(args, "url", None)
    tab_index = getattr(args, "tab", None)
    output_path = getattr(args, "output", None)

    if url:
        from common.paths import validate_safe_url
        try:
            validate_safe_url(url)
        except Exception as exc:
            print(f"[!] Invalid URL: {exc}", file=sys.stderr)
            sys.exit(1)

    if output_path:
        from common.paths import validate_safe_path
        try:
            validate_safe_path(output_path, for_write=True)
        except Exception as exc:
            print(f"[!] Invalid output path: {exc}", file=sys.stderr)
            sys.exit(1)

    selector = getattr(args, "selector", None)
    session_name = getattr(args, "session", None)

    req = SupervisorActionRequest(
        action="read",
        url=url,
        tab_index=tab_index,
        output_path=output_path,
        selector=selector,
        session_name=session_name,
    )

    resp = client.execute(req)
    if not resp.success:
        print(f"[!] Read failed: {resp.message}", file=sys.stderr)
        sys.exit(1)

    content = resp.content or ""
    if output_path:
        print(f"[✓] Clean content successfully saved to: {output_path}")
    else:
        print(content)
