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

    subparsers = parser.add_subparsers(dest="command", required=True)

    # 1. Inspect Subcommand
    p_inspect = subparsers.add_parser(
        "inspect",
        help="Inspect URL and return full schema of inputs, dropdowns, buttons, uploads",
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
    p_find.add_argument("target", help="Field identifier (local_id e.g. @fld-1, label, name, or DOM id)")
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
    p_find.add_argument("--html", action="store_true", help="Include outerHTML in diagnostic output")
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
    p_find.add_argument("--host", default="127.0.0.1", help="Supervisor host address")
    p_find.add_argument("--port", type=int, default=9333, help="Supervisor port")
    p_find.add_argument("--token", help="Explicit Master Supervisor authentication token")

    return parser
