"""CLI command handler for 'webpilot read' / 'wp read'."""

from __future__ import annotations

import argparse
import sys
from typing import Optional

from supervisor.client import SupervisorClient
from supervisor.contracts import SupervisorActionRequest


def read_cmd(args: argparse.Namespace) -> None:
    """Executes high-density clean markdown extraction via Trafilatura."""
    port = getattr(args, "port", None)
    client = SupervisorClient(port=port)
    client.ensure_running()

    url = getattr(args, "url", None)
    tab_index = getattr(args, "tab", None)
    output_path = getattr(args, "output", None)

    req = SupervisorActionRequest(
        action="read",
        url=url,
        tab_index=tab_index,
        output_path=output_path,
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
