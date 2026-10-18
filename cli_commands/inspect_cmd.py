"""Inspect command implementation for WebPilot CLI."""

from __future__ import annotations

import argparse
import json
import sys

from cli_commands.common import get_supervisor_client, populate_network_args
from common.telemetry import print_telemetry_banner
from orchestration.context import InspectionRequestContext
from orchestration.flow_orchestrator import FlowOrchestrator
from services.inspection_formatter_service import InspectionFormatterService
from supervisor.contracts import SupervisorActionRequest


def inspect_cmd(args: argparse.Namespace) -> None:
    """Executes the universal inspection workflow."""
    if getattr(args, "url", None):
        import os
        if getattr(args, "allow_internal", False):
            os.environ["WEBPILOT_ALLOW_INTERNAL_URLS"] = "1"
        from common.paths import validate_safe_url
        try:
            validate_safe_url(args.url)
        except Exception as exc:
            print(f"[!] Invalid URL: {exc}", file=sys.stderr)
            sys.exit(1)

    do_reload = bool(getattr(args, "reload", False) or getattr(args, "command", "") in ("reload", "refresh"))
    strip_header = getattr(args, "strip_header", False)
    auto_expand = getattr(args, "auto_expand", True)
    if getattr(args, "standalone", False):
        req = InspectionRequestContext(
            url=args.url,
            output_path=args.output,
            screenshot_path=args.screenshot,
            cookies_path=args.cookies,
            unpack_options=args.unpack_options,
            headed=args.headed,
            config_path=args.config,
            device_profile_path=args.device_profile,
            env_file=args.env_file,
            keep_alive=args.keep_alive,
            close_session=args.close_session,
            list_tabs=args.list_tabs,
            tab_index=args.tab,
            timeout_minutes=args.timeout_minutes,
            reload=do_reload,
            strip_header=strip_header,
            auto_expand=auto_expand,
        )
        FlowOrchestrator.execute_inspection_flow(req)
        return

    client = get_supervisor_client(args)

    if args.close_session:
        res = client.stop_service()
        print(f"[✓] {res.message}")
        return

    if args.list_tabs:
        resp = client.execute(SupervisorActionRequest(action="list_tabs"))
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
                print(f" • Tab #{t['index']}{active_mark}: '{t['title']}'\n   URL: {t['url']}")
        print("═" * 70 + "\n")
        return

    req = SupervisorActionRequest(
        action="reload" if do_reload else "inspect",
        url=args.url,
        cookies_path=args.cookies,
        screenshot_path=args.screenshot,
        tab_index=args.tab,
        unpack_options=args.unpack_options,
        headed=args.headed,
        timeout_minutes=args.timeout_minutes,
        reload=do_reload,
        strip_header=strip_header,
        auto_expand=auto_expand,
        session_name=getattr(args, "session", None),
    )
    populate_network_args(req, args)
    resp = client.execute(req)
    print_telemetry_banner(resp, strip_header=strip_header)
    summary_only = getattr(args, "summary_only", False)
    if not summary_only:
        for line in resp.output_lines:
            print(line)

    if resp.schema:
        if args.output:
            with open(args.output, "w", encoding="utf-8") as f:
                json.dump(resp.schema, f, indent=2, ensure_ascii=False)
            print(f"[✓] Full schema successfully saved to: {args.output}")
        summary = InspectionFormatterService.format_summary(resp.schema)
        print("\n" + summary)

    if not resp.success:
        print(f"[!] Inspection failed: {resp.message}")
        sys.exit(1)
