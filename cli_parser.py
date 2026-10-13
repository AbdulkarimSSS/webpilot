"""Command line argument parser definition for WebPilot."""

from __future__ import annotations

import argparse


def build_cli_parser() -> argparse.ArgumentParser:
    """Constructs and returns the comprehensive command-line parser for WebPilot."""
    parser = argparse.ArgumentParser(
        prog="webpilot",
        description="WebPilot: Autonomous Multi-Tier Browser Automation Engine & AI Agent Web Runtime",
    )
    parser.add_argument("--config", help="Path to custom settings.json configuration file")
    parser.add_argument("--device-profile", help="Path to custom device_profile.json configuration file")
    parser.add_argument("--env-file", help="Path to custom .env file")
    parser.add_argument("--host", default="127.0.0.1", help="Supervisor host address (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=9333, help="Supervisor port (default: 9333)")
    parser.add_argument("--token", help="Explicit Master Supervisor authentication token")
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
        "--standalone",
        action="store_true",
        help="Run in-process via FlowOrchestrator instead of Master Supervisor",
    )
    p_inspect.add_argument("--host", default="127.0.0.1", help="Supervisor host address")
    p_inspect.add_argument("--port", type=int, default=9333, help="Supervisor port")
    p_inspect.add_argument("--token", help="Explicit Master Supervisor authentication token")
    p_inspect.add_argument("--config", help="Path to custom settings.json configuration file")
    p_inspect.add_argument("--device-profile", help="Path to custom device_profile.json configuration file")
    p_inspect.add_argument("--env-file", help="Path to custom .env file")

    # 2. Apply / Fill Subcommand
    p_apply = subparsers.add_parser(
        "apply",
        help="Fill fields dynamically via JSON file or CLI flags, and optionally submit",
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

    # 7. Find / Probe Subcommand
    p_find = subparsers.add_parser(
        "find",
        aliases=["probe"],
        help="Probe a specific element/field and inspect its properties, options, or HTML",
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
    p_find.add_argument("--query", "-q", help="Filter options by search substring or regex")
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
        help="Display all options without truncation (full option dump)",
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
    p_find.add_argument("--html", action="store_true", help="Include outerHTML in diagnostic output")
    p_find.add_argument(
        "--up",
        "--ascend",
        "--ancestor",
        dest="up",
        type=int,
        default=0,
        help="Ascend N levels up the DOM hierarchy (e.g. --up 1 for parent wrapper, --up 2 for outer section/card) to inspect ancestor HTML",
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

    return parser
