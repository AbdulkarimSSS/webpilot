"""Apply / form fill command implementation for WebPilot CLI."""

from __future__ import annotations

import argparse
import json
import os
import sys

from builder import FormPayloadBuilder
from cli_commands.common import get_supervisor_client
from common.secrets import parse_and_resolve_fill_args
from common.telemetry import print_telemetry_banner
from orchestration.context import ApplyRequestContext
from orchestration.flow_orchestrator import FlowOrchestrator
from services.inspection_formatter_service import InspectionFormatterService
from supervisor.contracts import SupervisorActionRequest


def apply_cmd(args: argparse.Namespace) -> None:
    """Executes the universal form filling and submission workflow."""
    auto_inspect = not getattr(args, "no_auto_inspect", False)

    raw_fill_args = args.fill or []
    resolved_pairs = parse_and_resolve_fill_args(raw_fill_args)
    effective_fill_args = [f"{k}={v}" for k, v in resolved_pairs]

    effective_data_path = args.data
    if args.data in ("-", "@stdin"):
        try:
            stdin_json = json.load(sys.stdin)
            stdin_pairs = FormPayloadBuilder.normalize_payload(stdin_json)
            effective_fill_args.extend([f"{k}={v}" for k, v in stdin_pairs])
            effective_data_path = None
        except Exception as exc:
            print(f"[!] Error reading JSON payload from stdin: {exc}", file=sys.stderr)
            sys.exit(1)

    strip_header = getattr(args, "strip_header", False)
    if getattr(args, "standalone", False):
        req = ApplyRequestContext(
            url=args.url,
            data_path=effective_data_path,
            fill_arguments=effective_fill_args,
            press_buttons=args.press or [],
            upload_files=args.upload or [],
            cookies_path=args.cookies,
            submit=args.submit,
            screenshot_path=args.screenshot,
            headed=args.headed,
            config_path=args.config,
            device_profile_path=args.device_profile,
            env_file=args.env_file,
            keep_alive=args.keep_alive,
            close_session=args.close_session,
            list_tabs=args.list_tabs,
            tab_index=args.tab,
            timeout_minutes=args.timeout_minutes,
            auto_inspect=auto_inspect,
            reload=bool(getattr(args, "reload", False)),
            strip_header=strip_header,
        )
        res = FlowOrchestrator.execute_apply_flow(req)
        if not getattr(res, "overall_success", False):
            sys.exit(1)
        return

    client = get_supervisor_client(args)

    if args.close_session:
        res = client.stop_service()
        print(f"[✓] {res.message}")
        return

    if args.list_tabs:
        resp = client.execute(SupervisorActionRequest(action="list_tabs"))
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

    do_reload = bool(getattr(args, "reload", False))
    req = SupervisorActionRequest(
        action="apply_reload" if do_reload else "apply",
        url=args.url,
        data_path=effective_data_path,
        fill_arguments=effective_fill_args,
        press_buttons=args.press or [],
        upload_files=args.upload or [],
        cookies_path=args.cookies,
        submit=args.submit,
        screenshot_path=args.screenshot,
        headed=args.headed,
        auto_inspect=auto_inspect,
        tab_index=args.tab,
        timeout_minutes=args.timeout_minutes,
        reload=do_reload,
        strip_header=strip_header,
    )
    resp = client.execute(req)
    print_telemetry_banner(resp, strip_header=strip_header)
    for line in resp.output_lines:
        print(line)

    if resp.schema and auto_inspect:
        if getattr(args, "full_inspect", False) or getattr(args, "inspect_all", False):
            summary = InspectionFormatterService.format_summary(resp.schema)
            print("\n" + summary)
        else:
            touched_keys = [k for k, _ in resolved_pairs]
            if effective_data_path and os.path.isfile(effective_data_path):
                try:
                    loaded = FormPayloadBuilder.load_from_file(effective_data_path)
                    touched_keys.extend([k for k, _ in loaded])
                except Exception:
                    pass
            targeted_summary = InspectionFormatterService.format_targeted_summary(resp.schema, touched_keys)
            if targeted_summary:
                print("\n" + targeted_summary)
                print("\n💡 (Note: Use --full-inspect to display all form fields)")
            else:
                summary = InspectionFormatterService.format_summary(resp.schema)
                print("\n" + summary)

    if not resp.success:
        print(f"[!] Apply operation failed: {resp.message}")
        sys.exit(1)
