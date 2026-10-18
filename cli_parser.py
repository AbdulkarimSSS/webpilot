"""Command line argument parser definition for WebPilot."""

from __future__ import annotations

import argparse
from typing import Any


def _parse_up_levels(val: Any) -> int:
    """Parses --up arguments supporting integers and keywords like 'max', 'full', 'all'."""
    if val is None:
        return 0
    val_s = str(val).strip().lower()
    if val_s in ("max", "full", "all", "root"):
        return 9999
    try:
        return int(val_s)
    except ValueError:
        raise argparse.ArgumentTypeError(f"Invalid --up level '{val}'; must be an integer or 'max'/'full'.")


def _add_common_network_flags(p: argparse.ArgumentParser) -> None:
    """Adds DNS-over-HTTPS (DoH) and real-time network resource blocking flags."""
    p.add_argument(
        "--no-dns",
        action="store_true",
        default=argparse.SUPPRESS,
        help="Disable DNS-over-HTTPS (DoH) and bypass secure DNS resolution",
    )
    p.add_argument(
        "--dns-over-https-servers",
        "--doh-servers",
        dest="doh_servers",
        default=argparse.SUPPRESS,
        help="Custom DNS-over-HTTPS server URLs (comma or space separated, e.g. 'https://dns.adguard.com/dns-query')",
    )
    p.add_argument(
        "--block-images",
        action="store_true",
        default=argparse.SUPPRESS,
        help="Block all image resources (.png, .jpg, .webp, .svg, etc.) to accelerate browsing and save memory",
    )
    p.add_argument(
        "--block-pattern",
        action="append",
        dest="block_patterns",
        default=argparse.SUPPRESS,
        help="Block resources matching URL glob pattern (e.g. '*analytics*.js')",
    )


def build_cli_parser() -> argparse.ArgumentParser:
    """Constructs and returns the comprehensive command-line parser for WebPilot."""
    parser = argparse.ArgumentParser(
        prog="webpilot",
        description="WebPilot: Autonomous Multi-Tier Browser Automation Engine & AI Agent Web Runtime",
    )
    _add_common_network_flags(parser)
    parser.add_argument("--config", help="Path to custom settings.json configuration file")
    parser.add_argument("--device-profile", help="Path to custom device_profile.json configuration file")
    parser.add_argument("--env-file", help="Path to custom .env file")
    parser.add_argument("--host", default="127.0.0.1", help="Supervisor host address (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=9333, help="Supervisor port (default: 9333)")
    parser.add_argument(
        "--token",
        help="Explicit Master Supervisor authentication token (Note: use --token-file or WEBPILOT_SUPERVISOR_TOKEN env var to avoid exposing secrets in process list)",
    )
    parser.add_argument(
        "--token-file",
        help="Path to file containing supervisor authentication token (avoids leaking token via process list)",
    )
    parser.add_argument(
        "--strip-header",
        "--strip-headers",
        "--StripHeader",
        "--stripheader",
        "--no-header",
        dest="strip_header",
        action="store_true",
        help="Suppress verbose telemetry banners and headers from tool output to conserve tokens",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # 1. Inspect Subcommand
    p_inspect = subparsers.add_parser(
        "inspect",
        help="Inspect URL and return full schema of inputs, dropdowns, buttons, uploads",
    )
    p_inspect.add_argument(
        "--strip-header",
        "--strip-headers",
        "--StripHeader",
        "--stripheader",
        "--no-header",
        dest="strip_header",
        action="store_true",
        default=argparse.SUPPRESS,
        help="Suppress verbose telemetry banners and headers from tool output to conserve tokens",
    )
    p_inspect.add_argument(
        "--url",
        nargs="?",
        default=None,
        help="Target URL to inspect (optional if connecting to existing live session)",
    )
    p_inspect.add_argument("--cookies", help="Path to cookies JSON file")
    p_inspect.add_argument("--output", help="Path to save full inspection JSON schema")
    p_inspect.add_argument("--screenshot", help="Path to save visual screenshot")
    p_inspect.add_argument(
        "--unpack-options",
        action="store_true",
        help="Probe dropdowns to sample options (burns more tokens/time)",
    )
    p_inspect.add_argument("--headed", action="store_true", help="Run headed browser")
    p_inspect.add_argument(
        "--keep-alive",
        action="store_true",
        help="Keep browser open across sequential commands",
    )
    p_inspect.add_argument(
        "--close-session",
        action="store_true",
        help="Terminate active live browser session and exit",
    )
    p_inspect.add_argument(
        "--list-tabs",
        action="store_true",
        help="List all open tabs in active session",
    )
    p_inspect.add_argument(
        "--tab",
        type=int,
        default=None,
        help="Target specific tab by index (0-based)",
    )
    p_inspect.add_argument(
        "--timeout-minutes",
        type=int,
        default=30,
        help="Inactivity timeout in minutes (default: 30, 0 = disable)",
    )
    p_inspect.add_argument(
        "--reload",
        "--refresh",
        action="store_true",
        help="Hard-reload active page from server before inspecting",
    )
    p_inspect.add_argument(
        "--expand",
        dest="auto_expand",
        action="store_true",
        default=True,
        help="Automatically expand all collapsed accordion sections (default: True)",
    )
    p_inspect.add_argument(
        "--no-expand",
        dest="auto_expand",
        action="store_false",
        help="Do not auto-expand collapsed sections, inspect current DOM state as-is",
    )
    p_inspect.add_argument("--session", dest="session", default=None, help="Named browser session instance")
    p_inspect.add_argument("--with-header", "--no-strip-header", dest="with_header", action="store_true", default=False, help="Invert persistent strip_header and display headers")
    p_inspect.add_argument("--standalone",
        action="store_true",
        help="Run in-process via FlowOrchestrator instead of Master Supervisor",
    )
    p_inspect.add_argument("--host", default="127.0.0.1", help="Supervisor host address")
    p_inspect.add_argument("--port", type=int, default=9333, help="Supervisor port")
    p_inspect.add_argument("--token", help="Explicit Master Supervisor authentication token")
    p_inspect.add_argument("--config", help="Path to custom settings.json configuration file")
    p_inspect.add_argument("--device-profile", help="Path to custom device_profile.json configuration file")
    p_inspect.add_argument("--env-file", help="Path to custom .env file")
    _add_common_network_flags(p_inspect)

    # 2. Apply / Fill Subcommand
    p_apply = subparsers.add_parser(
        "apply",
        help="Fill fields dynamically via JSON file or CLI flags, and optionally submit",
    )
    p_apply.add_argument(
        "--session",
        dest="session",
        default=None,
        help="Named browser session instance (e.g. --session main)",
    )
    p_apply.add_argument(
        "--with-header",
        "--no-strip-header",
        dest="with_header",
        action="store_true",
        default=False,
        help="Invert persistent strip_header and display headers",
    )
    p_apply.add_argument(
        "--strip-header",
        "--strip-headers",
        "--StripHeader",
        "--stripheader",
        "--no-header",
        dest="strip_header",
        action="store_true",
        default=argparse.SUPPRESS,
        help="Suppress verbose telemetry banners and headers from tool output to conserve tokens",
    )
    p_apply.add_argument(
        "--url",
        nargs="?",
        default=None,
        help="Target URL to fill (optional if connecting to existing live session)",
    )
    p_apply.add_argument("--data", help="Path to JSON file containing key-value mappings")
    p_apply.add_argument(
        "--fill",
        action="append",
        help="Field to set, e.g. --fill 'First Name=John' (can be repeated)",
    )
    p_apply.add_argument(
        "--press",
        action="append",
        help="Button to click, e.g. --press 'Next' (can be repeated)",
    )
    p_apply.add_argument(
        "--upload",
        action="append",
        help="File to upload, e.g. --upload 'resume=sample.pdf' (can be repeated)",
    )
    p_apply.add_argument("--cookies", help="Path to cookies JSON file")
    p_apply.add_argument("--submit", action="store_true", help="Click Apply/Submit after filling")
    p_apply.add_argument(
        "--reload",
        "--refresh",
        action="store_true",
        help="Hard-reload active page from server (after actions if any, or immediately)",
    )
    p_apply.add_argument("--screenshot", help="Path to save screenshot")
    p_apply.add_argument("--headed", action="store_true", help="Run headed browser")
    p_apply.add_argument(
        "--keep-alive",
        action="store_true",
        help="Keep browser open across sequential commands",
    )
    p_apply.add_argument(
        "--close-session",
        action="store_true",
        help="Terminate active live browser session and exit",
    )
    p_apply.add_argument(
        "--list-tabs",
        action="store_true",
        help="List all open tabs in active session",
    )
    p_apply.add_argument(
        "--tab",
        type=int,
        default=None,
        help="Target specific tab by index (0-based)",
    )
    p_apply.add_argument(
        "--timeout-minutes",
        type=int,
        default=30,
        help="Inactivity timeout in minutes (default: 30, 0 = disable)",
    )
    p_apply.add_argument(
        "--no-auto-inspect",
        action="store_true",
        help="Disable automatic post-interaction form inspection",
    )
    p_apply.add_argument(
        "--full-inspect",
        "--inspect-all",
        action="store_true",
        help="Display full inspection summary of all form fields instead of targeted summary",
    )
    p_apply.add_argument(
        "--standalone",
        action="store_true",
        help="Run in-process via FlowOrchestrator instead of Master Supervisor",
    )
    p_apply.add_argument("--host", default="127.0.0.1", help="Supervisor host address")
    p_apply.add_argument("--port", type=int, default=9333, help="Supervisor port")
    p_apply.add_argument("--token", help="Explicit Master Supervisor authentication token")
    p_apply.add_argument("--config", help="Path to custom settings.json configuration file")
    p_apply.add_argument("--device-profile", help="Path to custom device_profile.json configuration file")
    p_apply.add_argument("--env-file", help="Path to custom .env file")
    _add_common_network_flags(p_apply)

    # 3. Interactive REPL Shell Subcommand
    p_shell = subparsers.add_parser("shell", help="Launch interactive REPL automation shell")
    p_shell.add_argument("--host", default="127.0.0.1", help="Supervisor host address")
    p_shell.add_argument("--port", type=int, default=9333, help="Supervisor port")
    p_shell.add_argument("--token", help="Explicit Master Supervisor authentication token")

    # 4. Supervisor Service Management Subcommand
    p_service = subparsers.add_parser("service", help="Manage Master Supervisor background daemon")
    p_service.add_argument(
        "service_action",
        choices=["status", "restart", "stop", "start"],
        help="Action to execute",
    )
    p_service.add_argument("--host", default="127.0.0.1", help="Supervisor host address")
    p_service.add_argument("--port", type=int, default=9333, help="Supervisor port")
    p_service.add_argument("--token", help="Explicit Master Supervisor authentication token")

    # 5. Browser Binaries Installation Subcommand
    p_install = subparsers.add_parser("install", help="Download and configure required Playwright Chromium browser")
    p_install.add_argument("--all", action="store_true", help="Download all browsers (Chromium, Firefox, WebKit)")

    # 6. Skill Specification Subcommand
    p_skill = subparsers.add_parser("skill", help="Output the AI agent skill specification (SKILL.md) to terminal")

    # 6b. Read Subcommand (Clean Markdown Content Extraction via Trafilatura)
    p_read = subparsers.add_parser(
        "read",
        aliases=["clean_read", "content"],
        help="Extract clean, high-density markdown content from active or target page saving ~99.7%% of tokens via Trafilatura",
    )
    p_read.add_argument(
        "--url",
        nargs="?",
        default=None,
        help="Target URL to read (optional if reading existing active tab/session)",
    )
    p_read.add_argument(
        "--selector",
        "-s",
        dest="selector",
        default=None,
        help="Target CSS selector or element container to extract content strictly from",
    )
    p_read.add_argument("--output", "-o", help="Path to save clean markdown content")
    p_read.add_argument("--tab", type=int, help="Target browser tab index to read")
    p_read.add_argument("--session", dest="session", default=None, help="Named browser session instance")
    p_read.add_argument(
        "--strip-header",
        "--strip-headers",
        "--no-header",
        dest="strip_header",
        action="store_true",
        default=argparse.SUPPRESS,
        help="Suppress verbose telemetry banners and headers from tool output",
    )
    p_read.add_argument("--port", type=int, default=9333, help="Master Supervisor RPC port")
    _add_common_network_flags(p_read)

    # 7. Find / Probe Subcommand
    p_find = subparsers.add_parser(
        "find",
        aliases=["probe"],
        help="Probe a specific element/field and inspect its properties, options, or HTML",
    )
    p_find.add_argument(
        "--text",
        "-t",
        action="store_true",
        default=False,
        help="Extract pure visible text (innerText) directly without HTML or telemetry banners",
    )
    p_find.add_argument(
        "--session",
        dest="session",
        default=None,
        help="Named browser session instance",
    )
    p_find.add_argument(
        "--with-header",
        "--no-strip-header",
        dest="with_header",
        action="store_true",
        default=False,
        help="Invert persistent strip_header and display headers",
    )
    p_find.add_argument(
        "--no-exclude",
        dest="no_exclude",
        action="store_true",
        default=False,
        help="Invert persistent exclude tags and retain all elements",
    )
    p_find.add_argument(
        "--no-include",
        dest="no_include",
        action="store_true",
        default=False,
        help="Invert persistent include tags",
    )
    p_find.add_argument(
        "--strip-header",
        "--strip-headers",
        "--StripHeader",
        "--stripheader",
        "--no-header",
        dest="strip_header",
        action="store_true",
        default=argparse.SUPPRESS,
        help="Suppress verbose telemetry banners and headers from tool output to conserve tokens",
    )
    p_find.add_argument(
        "--selector",
        "--css",
        "--xpath",
        "-sel",
        dest="selector",
        default=None,
        help="Search / probe element by arbitrary CSS selector or XPath (e.g. --selector 'div.datePicker', --selector '#250\\:_datepicker', --selector '//button[contains(., \"Next\")]')",
    )
    p_find.add_argument("target", nargs="?", default=None, help="Field identifier (local_id e.g. @fld-1, label, name, DOM id, or selector)")
    p_find.add_argument(
        "--url",
        nargs="?",
        default=None,
        help="Target URL (optional if connecting to existing live session)",
    )
    p_find.add_argument("--cookies", help="Path to cookies JSON file")
    p_find.add_argument(
        "--options",
        action="store_true",
        default=True,
        help="Include available dropdown options (default: True)",
    )
    p_find.add_argument(
        "--no-options",
        dest="options",
        action="store_false",
        help="Do not include options",
    )
    p_find.add_argument("--query", help="Filter options by search substring or regex")
    p_find.add_argument(
        "--limit",
        "--show",
        "-n",
        dest="limit",
        type=int,
        default=None,
        help="Maximum number of options to display (e.g. --show 50 or -n 50)",
    )
    p_find.add_argument(
        "--offset",
        "--from",
        "--start",
        "--showfrom",
        "--show-from",
        dest="offset",
        type=int,
        default=0,
        help="Starting index offset (0-based) for options list (e.g. --from 30 or --showfrom 30)",
    )
    p_find.add_argument(
        "--all",
        "--full",
        dest="all_options",
        action="store_true",
        default=False,
        help="Display all options or HTML without truncation (full dump)",
    )
    p_find.add_argument(
        "--page",
        dest="page",
        type=int,
        default=None,
        help="Page number (1-based) to display (e.g. --page 2)",
    )
    p_find.add_argument(
        "--page-size",
        "--pagesize",
        dest="page_size",
        type=int,
        default=20,
        help="Number of options per page when using --page (default: 20)",
    )
    p_find.add_argument(
        "--search", "-q",
        type=str,
        default=None,
        help="Filter HTML tree to elements matching substring or regex ('re:<pattern>'), pruning non-ancestral sibling branches",
    )
    p_find.add_argument(
        "--include",
        type=str,
        default=None,
        help="Comma-separated list of HTML tag names to retain (e.g. 'div,label,input')",
    )
    p_find.add_argument(
        "--exclude",
        type=str,
        default=None,
        help="Comma-separated list of HTML tag names to prune (e.g. 'svg,script,style')",
    )
    p_find.add_argument(
        "--upper-include",
        type=str,
        default=None,
        help="Comma-separated whitelist of upper-tier uncle elements/tags to spare from default spine pruning (e.g. 'header,h2,button')",
    )
    p_find.add_argument(
        "--upper-exclude",
        type=str,
        default=None,
        help="Comma-separated blacklist to prune child elements from inside spared --upper-include containers (e.g. 'svg,script')",
    )
    p_find.add_argument(
        "--lines",
        type=str,
        default=None,
        help="Line slice filter on formatted output: '<start>:<end>', ':<end>', '<start>:', or '-<tail>:'",
    )
    p_find.add_argument(
        "--chars",
        type=str,
        default=None,
        help="Character slice filter on formatted output: '<start>:<end>', ':<end>', '<start>:', or '-<tail>:'",
    )
    p_find.add_argument(
        "--max-chars",
        type=int,
        default=20000,
        help="Maximum character ceiling before truncation (default: 20000; set to 0 or use --all to disable ceiling)",
    )
    p_find.add_argument(
        "--info",
        action="store_true",
        default=False,
        help="Display structural metadata summary (chars, lines, depth, inner elements) for pruned node (@exc-N) or element",
    )
    p_find.add_argument(
        "--pretty",
        action="store_true",
        default=True,
        help="Format and indent HTML tree into distinct lines (default: True)",
    )
    p_find.add_argument(
        "--raw",
        action="store_true",
        default=False,
        help="Disable pretty-printing and output unformatted raw DOM string",
    )
    p_find.add_argument(
        "--rules",
        "--constraints",
        dest="show_rules",
        action="store_true",
        default=False,
        help="Display field input constraints and accepted formats (max/min length, pattern, inputmode, accept)",
    )
    p_find.add_argument(
        "--error",
        "--errors",
        dest="show_error",
        action="store_true",
        default=False,
        help="Display direct field-level validation error state and error messages (aria-invalid, describedby)",
    )
    p_find.add_argument(
        "--deps",
        "--dependencies",
        dest="show_deps",
        action="store_true",
        default=False,
        help="Display field parent dependencies and cascading triggers",
    )
    p_find.add_argument(
        "--context",
        "--frame",
        dest="show_context",
        action="store_true",
        default=False,
        help="Display containment environment (Main Document, Iframe, Shadow DOM)",
    )
    p_find.add_argument(
        "--smart",
        "--meta",
        dest="show_smart",
        action="store_true",
        default=False,
        help="Shortcut to display all intelligent diagnostic cards (rules, error, deps, context) together",
    )
    p_find.add_argument("--html", action="store_true", help="Include outerHTML in diagnostic output")
    p_find.add_argument(
        "--up",
        "--ascend",
        "--ancestor",
        dest="up",
        type=_parse_up_levels,
        default=0,
        help="Ascend N levels up the DOM hierarchy (e.g. --up 1, --up 2, or --up max/full to reach page root ceiling)",
    )
    p_find.add_argument(
        "--screenshot",
        "-s",
        dest="screenshot",
        nargs="?",
        const="auto",
        default=None,
        help="Save visual screenshot of the target element (or its ascended container) to image file path",
    )
    p_find.add_argument("--json", action="store_true", help="Output raw JSON instead of formatted text")
    p_find.add_argument(
        "--tab",
        type=int,
        default=None,
        help="Target specific tab by index (0-based)",
    )
    p_find.add_argument("--headed", action="store_true", help="Run headed browser")
    p_find.add_argument(
        "--timeout-minutes",
        type=int,
        default=30,
        help="Inactivity timeout in minutes (default: 30)",
    )
    p_find.add_argument("--standalone", action="store_true", help="Run in-process via Playwright instead of Master Supervisor daemon")
    p_find.add_argument("--host", default="127.0.0.1", help="Supervisor host address")
    p_find.add_argument("--port", type=int, default=9333, help="Supervisor port")
    p_find.add_argument("--token", help="Explicit Master Supervisor authentication token")
    _add_common_network_flags(p_find)

    # 8. Reload Subcommand
    p_reload = subparsers.add_parser(
        "reload",
        aliases=["refresh"],
        help="Hard-reload the active page from the server and inspect updated form state",
    )
    p_reload.add_argument(
        "--strip-header",
        "--strip-headers",
        "--StripHeader",
        "--stripheader",
        "--no-header",
        dest="strip_header",
        action="store_true",
        default=argparse.SUPPRESS,
        help="Suppress verbose telemetry banners and headers from tool output to conserve tokens",
    )
    p_reload.add_argument("--url", nargs="?", default=None, help="Optional target URL")
    p_reload.add_argument("--cookies", help="Path to cookies JSON file")
    p_reload.add_argument("--output", help="Path to save full inspection JSON schema")
    p_reload.add_argument("--screenshot", help="Path to save visual screenshot")
    p_reload.add_argument("--unpack-options", action="store_true", help="Probe dropdowns to sample options")
    p_reload.add_argument("--headed", action="store_true", help="Run headed browser")
    p_reload.add_argument("--keep-alive", action="store_true", help="Keep browser open")
    p_reload.add_argument("--close-session", action="store_true", help="Terminate active session")
    p_reload.add_argument("--list-tabs", action="store_true", help="List open tabs")
    p_reload.add_argument("--tab", type=int, default=None, help="Target specific tab by index (0-based)")
    p_reload.add_argument("--timeout-minutes", type=int, default=30, help="Inactivity timeout in minutes")
    p_reload.add_argument("--standalone", action="store_true", help="Run in-process")
    p_reload.add_argument("--host", default="127.0.0.1", help="Supervisor host address")
    p_reload.add_argument("--port", type=int, default=9333, help="Supervisor port")
    p_reload.add_argument("--token", help="Explicit Master Supervisor authentication token")
    p_reload.add_argument("--config", help="Path to custom settings.json configuration file")
    p_reload.add_argument("--device-profile", help="Path to custom device_profile.json configuration file")
    p_reload.add_argument("--env-file", help="Path to custom .env file")
    p_reload.set_defaults(reload=True)
    _add_common_network_flags(p_reload)

    # 9. Eval / JavaScript Execution Subcommand
    p_eval = subparsers.add_parser(
        "eval",
        aliases=["js", "exec"],
        help="Execute arbitrary JavaScript expression in the active page and return results",
    )
    p_eval.add_argument(
        "--strip-header",
        "--strip-headers",
        "--StripHeader",
        "--stripheader",
        "--no-header",
        dest="strip_header",
        action="store_true",
        default=argparse.SUPPRESS,
        help="Suppress verbose telemetry banners and headers from tool output to conserve tokens",
    )
    p_eval.add_argument("script", nargs="?", default=None, help="JavaScript expression or function to evaluate")
    p_eval.add_argument("--code", "-c", help="Alternative flag to pass JavaScript expression")
    p_eval.add_argument("--file", "-f", help="Path to .js file to execute")
    p_eval.add_argument("--url", nargs="?", default=None, help="Target URL (optional if connecting to existing live session)")
    p_eval.add_argument("--tab", type=int, default=None, help="Target specific tab by index (0-based)")
    p_eval.add_argument("--json", action="store_true", help="Output raw JSON instead of text")
    p_eval.add_argument("--headed", action="store_true", help="Run headed browser")
    p_eval.add_argument("--timeout-minutes", type=int, default=30, help="Inactivity timeout in minutes")
    p_eval.add_argument("--standalone", action="store_true", help="Run in-process via Playwright instead of Master Supervisor daemon")
    p_eval.add_argument("--host", default="127.0.0.1", help="Supervisor host address")
    p_eval.add_argument("--port", type=int, default=9333, help="Supervisor port")
    p_eval.add_argument("--token", help="Explicit Master Supervisor authentication token")
    _add_common_network_flags(p_eval)

    # 10. CSS Injection & Inspection Subcommand
    p_css = subparsers.add_parser(
        "css",
        aliases=["style"],
        help="Inject custom CSS styles or inspect computed styles of an element",
    )
    p_css.add_argument(
        "--strip-header",
        "--strip-headers",
        "--StripHeader",
        "--stripheader",
        "--no-header",
        dest="strip_header",
        action="store_true",
        default=argparse.SUPPRESS,
        help="Suppress verbose telemetry banners and headers from tool output to conserve tokens",
    )
    p_css.add_argument("target", nargs="?", default=None, help="CSS stylesheet rules to inject, or selector to inspect/modify computed styles")
    p_css.add_argument("--selector", "-sel", help="Element selector to inspect or modify styles")
    p_css.add_argument("--set", "-s", dest="set_style", help="Write / set inline CSS styles on the element (e.g. --set 'display: block !important')")
    p_css.add_argument("--prop", "-p", help="Specific computed CSS property name to inspect (e.g. display, visibility)")
    p_css.add_argument("--file", "-f", help="Path to .css file to inject")
    p_css.add_argument("--url", nargs="?", default=None, help="Target URL (optional if connecting to existing live session)")
    p_css.add_argument("--tab", type=int, default=None, help="Target specific tab by index (0-based)")
    p_css.add_argument("--json", action="store_true", help="Output raw JSON instead of text")
    p_css.add_argument("--headed", action="store_true", help="Run headed browser")
    p_css.add_argument("--timeout-minutes", type=int, default=30, help="Inactivity timeout in minutes")
    p_css.add_argument("--standalone", action="store_true", help="Run in-process via Playwright instead of Master Supervisor daemon")
    p_css.add_argument("--host", default="127.0.0.1", help="Supervisor host address")
    p_css.add_argument("--port", type=int, default=9333, help="Supervisor port")
    p_css.add_argument("--token", help="Explicit Master Supervisor authentication token")

    # 11. Tab Management Subcommand
    p_tab = subparsers.add_parser(
        "tab",
        aliases=["tabs"],
        help="Manage browser tabs (list, new, switch, close)",
    )
    p_tab.add_argument(
        "tab_action",
        nargs="?",
        default="list",
        choices=["list", "new", "switch", "close", "timeout", "set-timeout", "set_timeout"],
        help="Tab action: list (default), new, switch, close, timeout",
    )
    p_tab.add_argument(
        "tab_target",
        nargs="?",
        default=None,
        help="Target URL for 'new', Tab Index for 'switch'/'close', or minutes/index for 'timeout'",
    )
    p_tab.add_argument(
        "--url",
        help="Target URL when creating a new tab (e.g. wp tab new https://example.com)",
    )
    p_tab.add_argument(
        "--tab",
        dest="tab_index",
        type=int,
        default=None,
        help="Target tab index (0-based) for switch, close, or timeout",
    )
    p_tab.add_argument(
        "--tab-timeout",
        dest="tab_timeout",
        type=int,
        default=None,
        help="Inactivity timeout in minutes for tab auto-close (default: 30, 0 = disable)",
    )
    p_tab.add_argument(
        "--json",
        action="store_true",
        help="Output raw JSON instead of formatted text",
    )
    p_tab.add_argument(
        "--strip-header",
        "--strip-headers",
        "--StripHeader",
        "--stripheader",
        "--no-header",
        dest="strip_header",
        action="store_true",
        default=argparse.SUPPRESS,
        help="Suppress verbose telemetry banners and headers from tool output to conserve tokens",
    )
    p_tab.add_argument("--host", default="127.0.0.1", help="Supervisor host address")
    p_tab.add_argument("--port", type=int, default=9333, help="Supervisor port")
    p_tab.add_argument("--token", help="Explicit Master Supervisor authentication token")

    # 12. Cookies Management Subcommand
    p_cookies = subparsers.add_parser(
        "cookies",
        aliases=["cookie"],
        help="Export, inspect, or manage browser session cookies",
    )
    p_cookies.add_argument(
        "cookies_action",
        nargs="?",
        default="export",
        choices=["export", "dump", "list", "save", "clear"],
        help="Action: export/dump (default), list, save, clear",
    )
    p_cookies.add_argument(
        "--output",
        "--out",
        "-o",
        dest="output_path",
        help="Path to save exported cookies JSON file",
    )
    p_cookies.add_argument(
        "--domain",
        "-d",
        dest="query",
        help="Filter cookies by domain or name substring (e.g. --domain example.com)",
    )
    p_cookies.add_argument(
        "--url",
        help="Target URL (optional; if specified, navigates or filters by URL)",
    )
    p_cookies.add_argument(
        "--tab",
        type=int,
        default=None,
        help="Target specific tab by index (0-based)",
    )
    p_cookies.add_argument(
        "--json",
        action="store_true",
        help="Output raw JSON instead of formatted table",
    )
    p_cookies.add_argument(
        "--strip-header",
        "--strip-headers",
        "--StripHeader",
        "--stripheader",
        "--no-header",
        dest="strip_header",
        action="store_true",
        default=argparse.SUPPRESS,
        help="Suppress verbose telemetry banners and headers from tool output to conserve tokens",
    )
    p_cookies.add_argument("--headed", action="store_true", help="Run headed browser")
    p_cookies.add_argument("--timeout-minutes", type=int, default=30, help="Inactivity timeout in minutes")
    p_cookies.add_argument("--standalone", action="store_true", help="Run in-process via Playwright instead of Master Supervisor daemon")
    p_cookies.add_argument("--host", default="127.0.0.1", help="Supervisor host address")
    p_cookies.add_argument("--port", type=int, default=9333, help="Supervisor port")
    p_cookies.add_argument("--token", help="Explicit Master Supervisor authentication token")

    # 13. Wait Subcommand
    p_wait = subparsers.add_parser(
        "wait",
        aliases=["wait_for"],
        help="Explicitly wait for an element selector, network idle state, or page readiness",
    )
    p_wait.add_argument(
        "--selector",
        "-s",
        dest="selector",
        default=None,
        help="CSS selector or XPath to wait for (e.g. --selector '#submitBtn')",
    )
    p_wait.add_argument(
        "--timeout",
        dest="timeout",
        type=int,
        default=10000,
        help="Timeout in milliseconds (default: 10000)",
    )
    p_wait.add_argument(
        "--state",
        choices=["visible", "attached", "detached", "hidden"],
        default="visible",
        help="Target element state to wait for: visible (default), attached, detached, hidden",
    )
    p_wait.add_argument(
        "--network-idle",
        "--networkidle",
        dest="network_idle",
        action="store_true",
        default=False,
        help="Wait for network requests to settle (networkidle state)",
    )
    p_wait.add_argument("--url", help="Target URL (optional; navigates before waiting)")
    p_wait.add_argument("--tab", type=int, default=None, help="Target tab index (0-based)")
    p_wait.add_argument("--session", dest="session", default=None, help="Named browser session instance")
    p_wait.add_argument(
        "--strip-header",
        "--strip-headers",
        "--StripHeader",
        "--stripheader",
        "--no-header",
        dest="strip_header",
        action="store_true",
        default=argparse.SUPPRESS,
        help="Suppress verbose telemetry banners and headers from tool output",
    )
    p_wait.add_argument("--host", default="127.0.0.1", help="Supervisor host address")
    p_wait.add_argument("--port", type=int, default=9333, help="Supervisor port")
    p_wait.add_argument("--token", help="Explicit Master Supervisor authentication token")
    _add_common_network_flags(p_wait)

    # 14. Persistent Config / Sticky Flags Subcommand
    p_config = subparsers.add_parser(
        "config",
        aliases=["pref", "prefs", "preference", "preferences"],
        help="Manage persistent user preferences and sticky flags (~/.webpilot/preferences.json)",
    )
    p_config.add_argument(
        "config_action",
        nargs="?",
        default="list",
        choices=["list", "set", "unset", "remove", "delete", "clear", "reset"],
        help="Action: list (default), set, unset, clear",
    )
    p_config.add_argument("key", nargs="?", default=None, help="Preference key name (e.g. strip_header, exclude, session)")
    p_config.add_argument("value", nargs="?", default=None, help="Preference value to set (e.g. true, 'svg,script', 'main')")
    p_config.add_argument("--json", action="store_true", help="Output stored preferences as raw JSON")

    # 15. Sniff Subcommand (Real-time network API & fetch/XHR sniffing)
    p_sniff = subparsers.add_parser(
        "sniff",
        help="Sniff network API and fetch/xhr requests and responses in real time",
    )
    p_sniff.add_argument("--url", nargs="?", default=None, help="Target URL or endpoint pattern to filter")
    p_sniff.add_argument("--types", default="xhr,fetch", help="Comma-separated resource types to sniff (default: xhr,fetch)")
    p_sniff.add_argument("--filter", dest="filter_pattern", default=None, help="URL filter pattern")
    p_sniff.add_argument("--timeout", type=int, default=3000, help="Listen timeout in milliseconds (default: 3000)")
    p_sniff.add_argument("--tab", type=int, default=None, help="Target specific tab by index")
    p_sniff.add_argument("--session", dest="session_name", default=None, help="Named browser session")
    p_sniff.add_argument("--json", action="store_true", help="Output raw JSON results")
    p_sniff.add_argument("--strip-header", dest="strip_header", action="store_true", default=argparse.SUPPRESS, help="Suppress telemetry headers")
    p_sniff.add_argument("--host", default="127.0.0.1", help="Supervisor host address")
    p_sniff.add_argument("--port", type=int, default=9333, help="Supervisor port")
    p_sniff.add_argument("--token", help="Explicit Master Supervisor authentication token")
    _add_common_network_flags(p_sniff)

    # 16. Dump Subcommand (Site scripts & assets local extraction)
    p_dump = subparsers.add_parser(
        "dump",
        help="Dump site scripts and network assets to local directory",
    )
    p_dump.add_argument("--types", default="js", help="Comma-separated asset types (default: js)")
    p_dump.add_argument("-o", "--output", default="./site_scripts/", help="Output directory path (default: ./site_scripts/)")
    p_dump.add_argument("--filter", dest="filter_pattern", default=None, help="URL filter pattern")
    p_dump.add_argument("--tab", type=int, default=None, help="Target specific tab by index")
    p_dump.add_argument("--session", dest="session_name", default=None, help="Named browser session")
    p_dump.add_argument("--json", action="store_true", help="Output raw JSON results")
    p_dump.add_argument("--strip-header", dest="strip_header", action="store_true", default=argparse.SUPPRESS, help="Suppress telemetry headers")
    p_dump.add_argument("--host", default="127.0.0.1", help="Supervisor host address")
    p_dump.add_argument("--port", type=int, default=9333, help="Supervisor port")
    p_dump.add_argument("--token", help="Explicit Master Supervisor authentication token")
    _add_common_network_flags(p_dump)

    # 17. Capture Subcommand (Background API JSON responses)
    p_capture = subparsers.add_parser(
        "capture",
        help="Capture and save background API JSON responses",
    )
    p_capture.add_argument("--filter", dest="filter_pattern", default="/api/", help="URL pattern or prefix to capture (default: /api/)")
    p_capture.add_argument("-o", "--output", default="./api_data/", help="Output directory path (default: ./api_data/)")
    p_capture.add_argument("--types", default="json", help="Comma-separated types (default: json)")
    p_capture.add_argument("--tab", type=int, default=None, help="Target specific tab by index")
    p_capture.add_argument("--session", dest="session_name", default=None, help="Named browser session")
    p_capture.add_argument("--json", action="store_true", help="Output raw JSON results")
    p_capture.add_argument("--strip-header", dest="strip_header", action="store_true", default=argparse.SUPPRESS, help="Suppress telemetry headers")
    p_capture.add_argument("--host", default="127.0.0.1", help="Supervisor host address")
    p_capture.add_argument("--port", type=int, default=9333, help="Supervisor port")
    p_capture.add_argument("--token", help="Explicit Master Supervisor authentication token")
    _add_common_network_flags(p_capture)

    # 18. Block Subcommand (URL patterns & images)
    p_block = subparsers.add_parser(
        "block",
        help="Configure URL pattern or image blocking",
    )
    p_block.add_argument("--pattern", action="append", dest="block_patterns", default=[], help="Pattern to block (e.g. '*analytics*.js')")
    p_block.add_argument("--images", action="store_true", help="Block all image resources")
    p_block.add_argument("--clear", action="store_true", help="Clear all blocking patterns")
    p_block.add_argument("--tab", type=int, default=None, help="Target specific tab by index")
    p_block.add_argument("--session", dest="session_name", default=None, help="Named browser session")
    p_block.add_argument("--json", action="store_true", help="Output raw JSON results")
    p_block.add_argument("--strip-header", dest="strip_header", action="store_true", default=argparse.SUPPRESS, help="Suppress telemetry headers")
    p_block.add_argument("--host", default="127.0.0.1", help="Supervisor host address")
    p_block.add_argument("--port", type=int, default=9333, help="Supervisor port")
    p_block.add_argument("--token", help="Explicit Master Supervisor authentication token")
    _add_common_network_flags(p_block)

    # 19. Network Subcommand (HAR 1.2 recording & trace management)
    p_network = subparsers.add_parser(
        "network",
        help="Network engine inspection, HAR recording, and buffer management",
    )
    p_network.add_argument("subaction", nargs="?", default="status", choices=["record", "status", "clear", "reset"], help="Network action (record, status, clear)")
    p_network.add_argument("-o", "--output", dest="output_path", default="session.har", help="HAR output file path (default: session.har)")
    p_network.add_argument("--tab", type=int, default=None, help="Target specific tab by index")
    p_network.add_argument("--session", dest="session_name", default=None, help="Named browser session")
    p_network.add_argument("--json", action="store_true", help="Output raw JSON results")
    p_network.add_argument("--strip-header", dest="strip_header", action="store_true", default=argparse.SUPPRESS, help="Suppress telemetry headers")
    p_network.add_argument("--host", default="127.0.0.1", help="Supervisor host address")
    p_network.add_argument("--port", type=int, default=9333, help="Supervisor port")
    p_network.add_argument("--token", help="Explicit Master Supervisor authentication token")
    _add_common_network_flags(p_network)

    return parser
