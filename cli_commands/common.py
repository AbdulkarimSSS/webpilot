"""Common utilities and client factory for WebPilot CLI commands."""

from __future__ import annotations

import argparse
from supervisor.client import SupervisorClient


def get_base_url(args: argparse.Namespace) -> str:
    """Returns Master Supervisor HTTP base URL resolved from command-line arguments."""
    host = getattr(args, "host", None) or "127.0.0.1"
    port = getattr(args, "port", None) or 9333
    return f"http://{host}:{port}"


def get_supervisor_client(args: argparse.Namespace) -> SupervisorClient:
    """Instantiates a SupervisorClient configured with target host, port, and security token."""
    import os
    token = getattr(args, "token", None)
    token_file = getattr(args, "token_file", None)
    if not token and token_file:
        from supervisor.security import load_supervisor_token
        token = load_supervisor_token(token_file)
    elif token and token.startswith("@file:"):
        from supervisor.security import load_supervisor_token
        token = load_supervisor_token(token[6:].strip())
    elif token and token.startswith("@env:"):
        token = os.environ.get(token[5:].strip())
    return SupervisorClient(base_url=get_base_url(args), token=token)


def populate_network_args(req: Any, args: argparse.Namespace) -> None:
    """Populates DoH and network blocking options from parsed CLI args onto SupervisorActionRequest."""
    if hasattr(args, "no_dns"):
        req.enable_dns = not getattr(args, "no_dns", False)
    if hasattr(args, "doh_servers") and args.doh_servers:
        req.doh_servers = args.doh_servers
    if hasattr(args, "block_images") and args.block_images:
        req.block_images = True
    if hasattr(args, "block_patterns") and args.block_patterns:
        req.block_patterns = list(args.block_patterns)
    import os
    allow_int = (
        getattr(args, "allow_internal", False)
        or os.environ.get("WEBPILOT_ALLOW_INTERNAL_URLS") == "1"
        or os.environ.get("WEBPILOT_ALLOW_LOCAL_URLS") == "1"
    )
    if allow_int:
        req.allow_internal = True
