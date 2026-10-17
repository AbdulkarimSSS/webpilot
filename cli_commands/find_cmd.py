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

    max_chars_val = getattr(args, "max_chars", 20000)
    if max_chars_val is not None and max_chars_val < 0:
        print("[!] Error: --max-chars cannot be negative. Use 0 or --all to disable the ceiling.", file=sys.stderr)
        sys.exit(1)

    search_val = getattr(args, "search", None)
    has_upper = bool(getattr(args, "upper_include", None) or getattr(args, "upper_exclude", None))
    if has_upper and not search_val:
        print("[i] Notice: --upper-* controls require --search/-q to establish an ancestral spine (ignored).", file=sys.stderr)

    has_html_intent = bool(
        getattr(args, "html", False)
        or up_val > 0
        or getattr(args, "include", None)
        or getattr(args, "exclude", None)
        or getattr(args, "lines", None)
        or getattr(args, "chars", None)
    )
    want_html = has_html_intent
    opt_query = getattr(args, "query", None) or search_val

    details: Dict[str, Any] = {}
    if target_val and str(target_val).startswith("@exc-"):
        from services.html_diagnostic_service import HTMLDiagnosticService
        exc_id = str(target_val).strip()
        node_meta = HTMLDiagnosticService.get_pruned_node(exc_id)
        if not node_meta:
            print(f"\n[!] Error: Pruned node '{exc_id}' not found in session cache.", file=sys.stderr)
            sys.exit(1)

        want_info = getattr(args, "info", False)
        # If user explicitly asked for --info, or did not ask for --html/slicing/filtering
        if want_info or (not want_html and not getattr(args, "html", False)):
            if getattr(args, "json", False):
                print(json.dumps(node_meta, indent=2, ensure_ascii=False))
            else:
                print("\n" + "═" * 70)
                print(f" WEBPILOT PRUNED NODE METADATA | {exc_id}")
                print("═" * 70)
                print(HTMLDiagnosticService.format_pruned_info(node_meta))
                print("═" * 70 + "\n")
            return

        outer_html = node_meta["raw_html"]
        details = {
            "local_id": exc_id,
            "id": node_meta.get("dom_id") or "",
            "type": "pruned_node",
            "outerHTML": outer_html,
            "html": outer_html,
            "found": True,
            "label": node_meta.get("selector_desc"),
        }
    elif getattr(args, "standalone", False) and args.url:
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
                query=opt_query,
                include_html=want_html,
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
            query=opt_query,
            include_html=want_html,
            up_levels=up_val,
            screenshot_path=screen_val,
            headed=args.headed,
            timeout_minutes=args.timeout_minutes,
            strip_header=strip_header,
            session_name=getattr(args, "session", None),
        )
        resp = client.execute(req)
        if not getattr(args, "text", False):
            print_telemetry_banner(resp, strip_header=strip_header)

        if not resp.success:
            print(f"\n[!] {resp.message}")
            sys.exit(1)

        details = resp.field_details or {}

    if getattr(args, "text", False):
        raw_val = details.get("inner_text") or details.get("text") or details.get("value") or ""
        if not raw_val:
            cand_html = details.get("outerHTML") or details.get("html") or ""
            if cand_html:
                try:
                    from bs4 import BeautifulSoup
                    soup = BeautifulSoup(cand_html, "html.parser")
                    for s in soup(["script", "style", "svg"]):
                        s.decompose()
                    raw_val = soup.get_text(separator="\n", strip=True)
                except Exception:
                    pass
        print(str(raw_val).strip())
        return

    processed_html: Optional[str] = None
    search_match_desc: Optional[str] = None
    outer_html = details.get("outerHTML") or details.get("html")
    if want_html:
        if outer_html:
            try:
                from services.html_diagnostic_service import (
                    HTMLDiagnosticService,
                    DiagnosticSearchNotFoundError,
                    DiagnosticInputError,
                )
                pretty_mode = not getattr(args, "raw", False)
                show_all = getattr(args, "all_options", False)
                processed_html = HTMLDiagnosticService.process_html_pipeline(
                    raw_html=outer_html,
                    search_query=search_val,
                    include_tags=getattr(args, "include", None),
                    exclude_tags=getattr(args, "exclude", None),
                    upper_include=getattr(args, "upper_include", None),
                    upper_exclude=getattr(args, "upper_exclude", None),
                    pretty=pretty_mode,
                    lines_slice=getattr(args, "lines", None),
                    chars_slice=getattr(args, "chars", None),
                    max_chars=getattr(args, "max_chars", 20000),
                    show_all=show_all,
                )
                if search_val:
                    search_match_desc = HTMLDiagnosticService.get_last_search_match()
                if "outerHTML" in details:
                    details["outerHTML"] = processed_html
                if "html" in details:
                    details["html"] = processed_html
            except (DiagnosticSearchNotFoundError, DiagnosticInputError) as e:
                print(f"\n[!] Error: {e}", file=sys.stderr)
                sys.exit(1)
        elif search_val:
            print(f"\n[!] Error: Search target '{search_val}' not found within element boundary", file=sys.stderr)
            sys.exit(1)

    if getattr(args, "json", False):
        print(json.dumps(details, indent=2, ensure_ascii=False))
        return

    final_html = processed_html or outer_html
    if strip_header:
        if final_html:
            print(final_html)
        return

    print("\n" + "═" * 70)
    local_id_str = details.get("local_id") or "@fld"
    type_str = (details.get("type") or "element").upper()
    print(f" WEBPILOT ELEMENT DIAGNOSTIC | {local_id_str} | {type_str}")
    print("═" * 70)
    print(f" • Label       : {details.get('label')}")
    print(f" • Local ID    : {details.get('local_id')}")
    print(f" • DOM ID      : {details.get('id')}")
    print(f" • Widget Type : {details.get('type')}")
    print(f" • Current Val : {details.get('value')}")
    print(f" • Required    : {details.get('required')}")
    print(f" • Disabled    : {details.get('disabled')}")
    print(f" • Visible     : {details.get('visible')}")
    if search_val and search_match_desc:
        print(f" • Match       : {search_match_desc}")

    dep = details.get("dependency")
    if dep and dep.get("is_dependent"):
        p_label = dep.get("parent_label", "Unknown")
        p_id = dep.get("parent_id", "")
        p_loc = f"[{dep.get('parent_local_id')}] " if dep.get("parent_local_id") else ""
        print(f" • Linked Parent : {p_loc}'{p_label}' (ID: {p_id})")
        if details.get("disabled") or details.get("options_count", 1) == 0:
            print(f" [!] DEPENDENCY ALERT: Field is locked/empty awaiting parent selection '{p_label}'!")

    ancestor_d = details.get("ancestor_depth", 0)
    requested_d = details.get("ancestor_requested", up_val)
    max_reached = details.get("ancestor_max_reached", False)
    if ancestor_d > 0:
        a_tag = details.get("ancestor_tag", "")
        a_id = details.get("ancestor_id", "")
        id_str = f"#{a_id}" if a_id else ""
        a_cls = details.get("ancestor_class", "")
        cls_str = f".{a_cls.replace(' ', '.')}" if a_cls else ""
        
        limit_note = ""
        if max_reached:
            if requested_d >= 9999:
                limit_note = " (PAGE ROOT / FULL CEILING REACHED)"
            elif requested_d > ancestor_d:
                limit_note = f" (PAGE ROOT CEILING: Capped at <{a_tag}>, requested: +{requested_d})"
        
        print(f" • Ascended Up : +{ancestor_d} levels{limit_note} -> <{a_tag}{id_str}{cls_str}>")

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

        print(f"\n Options ({total_cnt} total{pagination_header}):")
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

    final_html = processed_html or outer_html
    if (want_html or getattr(args, "html", False) or up_val > 0) and final_html:
        max_str = " - PAGE ROOT" if max_reached else ""
        header_lvl = f" (Level +{ancestor_d}{max_str})" if ancestor_d > 0 else ""
        print(f"\n Outer HTML{header_lvl}:\n{final_html}")
    print("═" * 70 + "\n")
