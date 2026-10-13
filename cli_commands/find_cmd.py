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
    up_val = getattr(args, "up", 0)
    screen_val = getattr(args, "screenshot", None)
    strip_header = getattr(args, "strip_header", False)
    selector_val = getattr(args, "selector", None)
    target_val = args.target or selector_val

    if not target_val:
        print("[!] Error: You must specify a target or provide a --selector (e.g. wp find --selector 'div.datePicker').", file=sys.stderr)
        sys.exit(1)

    if getattr(args, "standalone", False) and args.url:
        from playwright.sync_api import sync_playwright
        from services.field_interaction_service import FieldInteractionService
        from services.inspection_service import InspectionService

        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=not args.headed)
            page = browser.new_page()
            page.goto(args.url)
            if target_val and target_val.startswith("@"):
                InspectionService(page).inspect()
            svc = FieldInteractionService(page)
            details = svc.probe_field(
                target=target_val,
                include_options=args.options,
                query=args.query,
                include_html=args.html or (up_val > 0),
                up_levels=up_val,
                screenshot_path=screen_val,
                selector=selector_val,
            )
            browser.close()

            if not details or not details.get("found"):
                print(f"\n[!] Element not found: '{selector_val or target_val}'")
                sys.exit(1)
    else:
        client = get_supervisor_client(args)
        req = SupervisorActionRequest(
            action="probe",
            url=args.url,
            cookies_path=args.cookies,
            tab_index=args.tab,
            target_field=target_val,
            selector=selector_val,
            include_options=args.options,
            query=args.query,
            include_html=args.html or (up_val > 0),
            up_levels=up_val,
            screenshot_path=screen_val,
            headed=args.headed,
            timeout_minutes=args.timeout_minutes,
            strip_header=strip_header,
        )
        resp = client.execute(req)
        print_telemetry_banner(resp, strip_header=strip_header)

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

    dep = details.get("dependency")
    if dep and dep.get("is_dependent"):
        p_label = dep.get("parent_label", "Unknown")
        p_id = dep.get("parent_id", "")
        p_loc = f"[{dep.get('parent_local_id')}] " if dep.get("parent_local_id") else ""
        print(f" • Linked Parent : {p_loc}'{p_label}' (ID: {p_id})")
        if details.get("disabled") or details.get("options_count", 1) == 0:
            print(f" ⚠️ DEPENDENCY ALERT: Field is locked/empty awaiting parent selection '{p_label}'!")

    ancestor_d = details.get("ancestor_depth", 0)
    if ancestor_d > 0:
        a_tag = details.get("ancestor_tag", "")
        a_id = details.get("ancestor_id", "")
        id_str = f"#{a_id}" if a_id else ""
        a_cls = details.get("ancestor_class", "")
        cls_str = f".{a_cls.replace(' ', '.')}" if a_cls else ""
        print(f" • Ascended Up : +{ancestor_d} levels -> <{a_tag}{id_str}{cls_str}>")

    if details.get("screenshot_path"):
        bbox = details.get("bounding_box") or {}
        box_str = f"({bbox.get('width')}x{bbox.get('height')}px at x={bbox.get('x')}, y={bbox.get('y')})" if bbox else ""
        print(f" • Screenshot  : Saved to '{details.get('screenshot_path')}' {box_str}")

    opts = details.get("options")
    if opts is not None:
        total_cnt = details.get("options_count", len(opts))
        show_all = getattr(args, "all_options", False)
        page = getattr(args, "page", None)
        page_size = getattr(args, "page_size", 20) or 20

        if page is not None and page > 0:
            offset = (page - 1) * page_size
            limit = page_size
        else:
            offset = getattr(args, "offset", 0) or 0
            if show_all:
                limit = None
            else:
                limit = getattr(args, "limit", None)
                if limit is None:
                    limit = 30

        start_idx = max(0, offset)
        end_idx = min(len(opts), (start_idx + limit)) if limit is not None else len(opts)
        sliced_opts = opts[start_idx:end_idx]

        pagination_header = ""
        if page is not None and page > 0:
            total_pages = max(1, (len(opts) + page_size - 1) // page_size)
            pagination_header = f" | Page {page}/{total_pages} (size: {page_size})"
        elif limit is not None and (start_idx > 0 or end_idx < len(opts)):
            pagination_header = f" | Showing {start_idx + 1}-{end_idx} of {len(opts)}"
        elif show_all:
            pagination_header = " | Full List"

        print(f"\n 📋 Options ({total_cnt} total{pagination_header}):")
        for o in sliced_opts:
            if isinstance(o, dict):
                loc = f"[{o.get('local_id')}] " if o.get('local_id') else ""
                val_part = f" (value: {o.get('value')})" if o.get('value') and o.get('value') != o.get('text') else ""
                print(f"   • {loc}'{o.get('text')}'{val_part}")
            else:
                print(f"   • {o}")

        if not show_all and end_idx < len(opts):
            remaining = len(opts) - end_idx
            next_page_hint = f"--page {(page or 1) + 1}" if page is not None else f"--from {end_idx}"
            print(f"   ... and {remaining} more options (use --all, --show <N>, {next_page_hint}, or -q to filter).")

    outer_html = details.get("outerHTML") or details.get("html")
    if (args.html or up_val > 0) and outer_html:
        header_lvl = f" (Level +{ancestor_d})" if ancestor_d > 0 else ""
        print(f"\n 🌐 Outer HTML{header_lvl}:\n{outer_html}")
    print("═" * 70 + "\n")
