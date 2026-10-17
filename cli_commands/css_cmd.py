"""CSS injection and computed styles inspection command implementation for WebPilot CLI."""

from __future__ import annotations

import argparse
import json
import os
import sys

from cli_commands.common import get_supervisor_client
from common.telemetry import print_telemetry_banner
from supervisor.contracts import SupervisorActionRequest


def css_cmd(args: argparse.Namespace) -> None:
    """Injects custom CSS stylesheets or inspects computed styles of an element."""
    target_or_rules = (getattr(args, "target", None) or "").strip()
    file_path = getattr(args, "file", None)
    selector = getattr(args, "selector", None)
    prop = getattr(args, "prop", None)

    if file_path and os.path.isfile(file_path):
        with open(file_path, "r", encoding="utf-8") as f:
            target_or_rules = f.read().strip()

    if not target_or_rules and not selector:
        print("[!] Error: You must provide CSS rules to inject or an element selector to inspect (e.g. wp css '.modal { display: none; }' or wp css '#btn').", file=sys.stderr)
        sys.exit(1)

    strip_header = getattr(args, "strip_header", False)

    if getattr(args, "standalone", False) and args.url:
        from playwright.sync_api import sync_playwright
        from adapters.dom.universal_core import UNIVERSAL_DOM_CORE_JS

        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=not args.headed)
            page = browser.new_page()
            page.goto(args.url)

            set_style = getattr(args, "set_style", None) or getattr(args, "set", None)
            is_inspection = bool(selector or (target_or_rules and "{" not in target_or_rules and ";" not in target_or_rules) or set_style)
            if is_inspection:
                target_sel = selector or target_or_rules
                js_inspect = UNIVERSAL_DOM_CORE_JS + """
                ([sel, propName, setRules]) => {
                    const el = deepQuerySelector(document, sel);
                    if (!el) return { found: false, error: "Element not found" };
                    if (setRules) {
                        el.style.cssText += ';' + setRules;
                        return { found: true, modified: true, selector: sel, set: setRules, style: el.style.cssText };
                    }
                    const style = window.getComputedStyle(el);
                    if (propName) {
                        return { found: true, selector: sel, property: propName, value: style.getPropertyValue(propName) || style[propName] || "" };
                    }
                    const keys = ['display', 'visibility', 'opacity', 'position', 'zIndex', 'pointerEvents', 'overflow', 'color', 'backgroundColor', 'width', 'height', 'top', 'left'];
                    const res = { found: true, selector: sel, properties: {} };
                    keys.forEach(k => { res.properties[k] = style[k] || style.getPropertyValue(k); });
                    return res;
                }
                """
                res = page.evaluate(js_inspect, [target_sel, prop or "", set_style or ""])
                browser.close()
                if not res.get("found"):
                    print(f"[!] Element not found for selector: '{target_sel}'", file=sys.stderr)
                    sys.exit(1)
                if getattr(args, "json", False):
                    print(json.dumps(res, indent=2, ensure_ascii=False))
                else:
                    if set_style:
                        print(f"[✓] Successfully applied inline style on '{target_sel}': {set_style}")
                    elif prop:
                        print(f"[*] {target_sel} -> {prop}: {res.get('value')}")
                    else:
                        print("\n" + "═" * 60)
                        print(f" 🎨 COMPUTED CSS STYLES | {target_sel}")
                        print("═" * 60)
                        for k, v in res.get("properties", {}).items():
                            print(f" • {k:<18}: {v}")
                        print("═" * 60)
            else:
                try:
                    page.add_style_tag(content=target_or_rules)
                    browser.close()
                    if getattr(args, "json", False):
                        print(json.dumps({"success": True, "injected_length": len(target_or_rules)}, indent=2))
                    else:
                        print(f"[✓] Successfully injected CSS stylesheet ({len(target_or_rules)} chars).")
                except Exception as exc:
                    browser.close()
                    print(f"[!] CSS Injection Error: {exc}", file=sys.stderr)
                    sys.exit(1)
        return

    set_style = getattr(args, "set_style", None) or getattr(args, "set", None)
    client = get_supervisor_client(args)
    req = SupervisorActionRequest(
        action="css",
        url=args.url,
        cookies_path=getattr(args, "cookies", None),
        tab_index=args.tab,
        script=target_or_rules,
        script_args=set_style,
        selector=selector,
        query=prop,
        headed=args.headed,
        timeout_minutes=args.timeout_minutes,
        strip_header=strip_header,
        session_name=getattr(args, "session", None),
    )
    resp = client.execute(req)
    print_telemetry_banner(resp, strip_header=strip_header)

    if not resp.success:
        print(f"[!] CSS Error: {resp.message}", file=sys.stderr)
        sys.exit(1)

    result_data = (resp.reactive_event or {}).get("result")
    if getattr(args, "json", False):
        print(json.dumps(result_data or {"success": True, "message": resp.message}, indent=2, ensure_ascii=False))
    else:
        if result_data and isinstance(result_data, dict) and result_data.get("properties"):
            target_sel = result_data.get("selector", "element")
            print("\n" + "═" * 60)
            print(f" 🎨 COMPUTED CSS STYLES | {target_sel}")
            print("═" * 60)
            for k, v in result_data.get("properties", {}).items():
                print(f" • {k:<18}: {v}")
            print("═" * 60)
        elif result_data and isinstance(result_data, dict) and "property" in result_data:
            print(f"[*] {result_data.get('selector')} -> {result_data.get('property')}: {result_data.get('value')}")
        else:
            print(f"[✓] {resp.message}")
