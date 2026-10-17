"""Network CLI command implementations: sniff, dump, capture, block, network.

Supports:
- Sniffing real-time fetch/XHR traffic: webpilot sniff --types xhr,fetch
- Sniffing specific endpoint pattern: webpilot sniff --url "endpoint_pattern"
- Dumping scripts and assets: webpilot dump --types js --output ./site_scripts/
- Capturing API JSON responses: webpilot capture --filter "/api/" --output ./api_data/
- Blocking resource patterns & images: webpilot block --pattern "*analytics*.js"
- HAR 1.2 session recording: webpilot network record -o session.har
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import List

from cli_commands.common import get_supervisor_client, populate_network_args
from common.telemetry import print_telemetry_banner
from supervisor.contracts import SupervisorActionRequest


def sniff_cmd(args: argparse.Namespace) -> None:
    """Sniffs live network traffic (fetch, xhr, APIs)."""
    client = get_supervisor_client(args)
    strip_header = getattr(args, "strip_header", False)

    types_list = [t.strip() for t in getattr(args, "types", "xhr,fetch").split(",") if t.strip()]
    url_target = getattr(args, "url", None)
    filter_pattern = getattr(args, "filter_pattern", None)

    req = SupervisorActionRequest(
        action="sniff",
        url=url_target,
        filter_pattern=filter_pattern,
        resource_types=types_list,
        wait_timeout=getattr(args, "timeout", 3000),
        tab_index=getattr(args, "tab", None),
        session_name=getattr(args, "session_name", None) or getattr(args, "session", None),
        strip_header=strip_header,
    )
    populate_network_args(req, args)

    resp = client.execute(req)
    print_telemetry_banner(resp, strip_header=strip_header)

    if not resp.success:
        print(f"[!] Sniff Error: {resp.message}", file=sys.stderr)
        sys.exit(1)

    if getattr(args, "json", False):
        print(json.dumps(resp.reactive_event or {}, indent=2, ensure_ascii=False))
    else:
        for line in resp.output_lines:
            print(line)


def dump_cmd(args: argparse.Namespace) -> None:
    """Dumps site scripts or network assets to a local directory."""
    client = get_supervisor_client(args)
    strip_header = getattr(args, "strip_header", False)

    types_list = [t.strip() for t in getattr(args, "types", "js").split(",") if t.strip()]
    output_dir = getattr(args, "output", "./site_scripts/")
    filter_pattern = getattr(args, "filter_pattern", None)

    req = SupervisorActionRequest(
        action="dump",
        output_path=output_dir,
        resource_types=types_list,
        filter_pattern=filter_pattern,
        tab_index=getattr(args, "tab", None),
        session_name=getattr(args, "session_name", None) or getattr(args, "session", None),
        strip_header=strip_header,
    )
    populate_network_args(req, args)

    resp = client.execute(req)
    print_telemetry_banner(resp, strip_header=strip_header)

    if not resp.success:
        print(f"[!] Dump Error: {resp.message}", file=sys.stderr)
        sys.exit(1)

    if getattr(args, "json", False):
        print(json.dumps(resp.reactive_event or {}, indent=2, ensure_ascii=False))
    else:
        for line in resp.output_lines:
            print(line)


def capture_cmd(args: argparse.Namespace) -> None:
    """Captures background API JSON responses to a local directory."""
    client = get_supervisor_client(args)
    strip_header = getattr(args, "strip_header", False)

    types_list = [t.strip() for t in getattr(args, "types", "json").split(",") if t.strip()]
    output_dir = getattr(args, "output", "./api_data/")
    filter_pattern = getattr(args, "filter_pattern", "/api/")

    req = SupervisorActionRequest(
        action="capture",
        output_path=output_dir,
        resource_types=types_list,
        filter_pattern=filter_pattern,
        tab_index=getattr(args, "tab", None),
        session_name=getattr(args, "session_name", None) or getattr(args, "session", None),
        strip_header=strip_header,
    )
    populate_network_args(req, args)

    resp = client.execute(req)
    print_telemetry_banner(resp, strip_header=strip_header)

    if not resp.success:
        print(f"[!] Capture Error: {resp.message}", file=sys.stderr)
        sys.exit(1)

    if getattr(args, "json", False):
        print(json.dumps(resp.reactive_event or {}, indent=2, ensure_ascii=False))
    else:
        for line in resp.output_lines:
            print(line)


def block_cmd(args: argparse.Namespace) -> None:
    """Configures real-time URL and resource blocking rules."""
    client = get_supervisor_client(args)
    strip_header = getattr(args, "strip_header", False)

    patterns = getattr(args, "block_patterns", []) or []
    if isinstance(patterns, str):
        patterns = [patterns]

    block_images = getattr(args, "images", False) or getattr(args, "block_images", False)

    req = SupervisorActionRequest(
        action="block",
        block_images=block_images,
        block_patterns=patterns,
        tab_index=getattr(args, "tab", None),
        session_name=getattr(args, "session_name", None) or getattr(args, "session", None),
        strip_header=strip_header,
    )
    populate_network_args(req, args)

    resp = client.execute(req)
    print_telemetry_banner(resp, strip_header=strip_header)

    if not resp.success:
        print(f"[!] Block Error: {resp.message}", file=sys.stderr)
        sys.exit(1)

    if getattr(args, "json", False):
        print(json.dumps(resp.reactive_event or {}, indent=2, ensure_ascii=False))
    else:
        for line in resp.output_lines:
            print(line)


def network_cmd(args: argparse.Namespace) -> None:
    """Controls network engine, HAR recording, and traffic management."""
    client = get_supervisor_client(args)
    strip_header = getattr(args, "strip_header", False)
    subaction = getattr(args, "subaction", "status") or "status"

    output_path = getattr(args, "output_path", "session.har")

    req = SupervisorActionRequest(
        action="network",
        query=subaction,
        har_path=output_path if subaction == "record" else None,
        output_path=output_path if subaction == "record" else None,
        tab_index=getattr(args, "tab", None),
        session_name=getattr(args, "session_name", None) or getattr(args, "session", None),
        strip_header=strip_header,
    )
    populate_network_args(req, args)

    resp = client.execute(req)
    print_telemetry_banner(resp, strip_header=strip_header)

    if not resp.success:
        print(f"[!] Network Command Error: {resp.message}", file=sys.stderr)
        sys.exit(1)

    if getattr(args, "json", False):
        print(json.dumps(resp.reactive_event or {}, indent=2, ensure_ascii=False))
    else:
        for line in resp.output_lines:
            print(line)
