"""Find and probe command implementation for WebPilot CLI."""

from __future__ import annotations

import argparse
import json
import sys

from cli_commands.common import get_supervisor_client
from common.telemetry import print_telemetry_banner
from supervisor.contracts import SupervisorActionRequest


def find_cmd(args: argparse.Namespace) -> None:
    """Probes a specific element/field and inspects its properties, options, or HTML."""
    client = get_supervisor_client(args)
    req = SupervisorActionRequest(
        action="probe",
        url=args.url,
        cookies_path=args.cookies,
        tab_index=args.tab,
        target_field=args.target,
        include_options=args.options,
        query=args.query,
        include_html=args.html,
        headed=args.headed,
        timeout_minutes=args.timeout_minutes,
    )
    resp = client.execute(req)
    print_telemetry_banner(resp)

    if not resp.success:
        print(f"\n[!] {resp.message}")
        sys.exit(1)

    details = resp.field_details or {}
    if getattr(args, "json", False):
        print(json.dumps(details, indent=2, ensure_ascii=False))
        return

    print("\n" + "═" * 70)
    local_id_str = details.get("local_id") or "@fld"
    type_str = (details.get("type") or "element").upper()
    print(f" 🔍 WEBPILOT ELEMENT DIAGNOSTIC | {local_id_str} | {type_str}")
    print("═" * 70)
    print(f" • Label       : {details.get('label')}")
    print(f" • Local ID    : {details.get('local_id')}")
    print(f" • DOM ID      : {details.get('id')}")
    print(f" • Widget Type : {details.get('type')}")
    print(f" • Current Val : {details.get('value')}")
    print(f" • Required    : {details.get('required')}")
    print(f" • Disabled    : {details.get('disabled')}")
    print(f" • Visible     : {details.get('visible')}")

    opts = details.get("options")
    if opts is not None:
        total_cnt = details.get("options_count", len(opts))
        print(f"\n 📋 Options ({total_cnt} total):")
        for o in opts[:30]:
            if isinstance(o, dict):
                loc = f"[{o.get('local_id')}] " if o.get('local_id') else ""
                val_part = f" (value: {o.get('value')})" if o.get('value') and o.get('value') != o.get('text') else ""
                print(f"   • {loc}'{o.get('text')}'{val_part}")
            else:
                print(f"   • {o}")
        if len(opts) > 30:
            print(f"   ... and {len(opts) - 30} more options (use --query to filter).")

    outer_html = details.get("outerHTML") or details.get("html")
    if args.html and outer_html:
        print(f"\n 🌐 Outer HTML:\n{outer_html}")
    print("═" * 70 + "\n")
