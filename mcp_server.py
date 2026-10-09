"""WebPilot MCP Server (Model Context Protocol).

Exposes WebPilot's autonomous multi-tier browser engine as standard MCP tools
for AI Agents (Claude, OpenCode, Cursor, etc.).

Features:
- Persistent browser state across tool calls (no restarting between actions)
- Zero administrative elevation required (Standard User Mode)
- Token-optimized DOM schemas returned directly to LLMs
- Reactive mutation tracking (redirects, new tabs, dynamic loaders)
"""

from __future__ import annotations

import json
import os
import sys
from typing import Any, Dict, List, Optional

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

try:
    from mcp.server.fastmcp import FastMCP
except ImportError:
    FastMCP = None


class _DummyMCP:
    def tool(self, *args, **kwargs):
        def decorator(f):
            return f
        return decorator

    def run(self):
        print("\n[!] Error: WebPilot FastMCP server requires the optional 'mcp' dependency.", file=sys.stderr)
        print("    Please install it using: pip install \"webpilot-engine[mcp]\"\n", file=sys.stderr)
        sys.exit(1)


# Initialize FastMCP application if installed, or fallback gracefully
if FastMCP is not None:
    mcp = FastMCP(
        "WebPilot",
        instructions=(
            "WebPilot is an autonomous multi-tier browser runtime for AI agents. "
            "It provides persistent browser sessions across tool calls, universal form inspection, "
            "reactive mutation tracking, and dynamic loading dissolution without requiring site-specific CSS selectors."
        ),
    )
else:
    mcp = _DummyMCP()


from supervisor.client import SupervisorClient
from supervisor.contracts import SupervisorActionRequest, SupervisorActionResponse

client = SupervisorClient()


@mcp.tool()
def webpilot_inspect(
    url: Optional[str] = None,
    unpack_options: bool = False,
    screenshot_path: Optional[str] = None,
    tab_index: Optional[int] = None,
) -> str:
    """Inspects a web page and returns a token-optimized schema of all inputs, buttons, and dropdowns.

    Args:
        url: Target web page URL to inspect (optional if connecting to existing active page).
        unpack_options: If True, probes dropdowns to sample options (burns more tokens).
        screenshot_path: Optional file path to save a visual screenshot.
        tab_index: Optional specific tab index to inspect (0-based).

    Returns:
        Structured JSON schema containing form fields, picklists, radio groups, and action buttons.
    """
    req = SupervisorActionRequest(
        action="inspect",
        url=url,
        unpack_options=unpack_options,
        screenshot_path=screenshot_path,
        tab_index=tab_index,
    )
    resp = client.execute(req)
    if not resp.success:
        return f"Error inspecting page: {resp.message}"

    output = {
        "status": "success",
        "active_url": resp.active_url,
        "active_title": resp.active_title,
        "active_tab": resp.active_tab_index,
        "total_tabs": resp.total_tabs,
        "schema": resp.schema,
        "message": resp.message,
    }
    return json.dumps(output, indent=2, ensure_ascii=False)


@mcp.tool()
def webpilot_fill_form(
    fields: Dict[str, str],
    url: Optional[str] = None,
    submit: bool = False,
    cookies_path: Optional[str] = None,
    screenshot_path: Optional[str] = None,
    tab_index: Optional[int] = None,
) -> str:
    """Fills form fields on the active page by name or label, and optionally submits.

    Args:
        fields: Key-value dictionary of field names to values (e.g. {"username": "user@test.com", "password": "xyz"}).
        url: Optional target URL if starting a fresh session.
        submit: If True, automatically clicks the form submit button after filling fields.
        cookies_path: Optional path to save updated session cookies.
        screenshot_path: Optional path to save visual screenshot after interaction.
        tab_index: Optional specific tab index to target (0-based).

    Returns:
        Confirmation of filled fields, any validation errors, and observed page state.
    """
    fill_args = [f"{k}={v}" for k, v in fields.items()]
    req = SupervisorActionRequest(
        action="apply",
        url=url,
        fill_arguments=fill_args,
        submit=submit,
        cookies_path=cookies_path,
        screenshot_path=screenshot_path,
        tab_index=tab_index,
    )
    resp = client.execute(req)

    output = {
        "success": resp.success,
        "message": resp.message,
        "active_url": resp.active_url,
        "confirmed_fields": resp.confirmed_fields,
        "failed_fields": resp.failed_fields,
        "validation_errors": resp.validation_errors,
        "logs": resp.output_lines,
    }
    return json.dumps(output, indent=2, ensure_ascii=False)


@mcp.tool()
def webpilot_click_button(
    button_text: str,
    screenshot_path: Optional[str] = None,
    cookies_path: Optional[str] = None,
    tab_index: Optional[int] = None,
) -> str:
    """Clicks a button, link, or tab with reactive mutation tracking (redirects, loaders, popups).

    Args:
        button_text: The visible text of the button or element to click (e.g. 'Sign In', 'Next', 'Submit').
        screenshot_path: Optional file path to capture screenshot after clicking.
        cookies_path: Optional file path to save updated session cookies.
        tab_index: Optional tab index to target (0-based).

    Returns:
        Result of the click, detected redirects or new tabs, and updated page state.
    """
    req = SupervisorActionRequest(
        action="apply",
        press_buttons=[button_text],
        screenshot_path=screenshot_path,
        cookies_path=cookies_path,
        tab_index=tab_index,
    )
    resp = client.execute(req)

    output = {
        "success": resp.success,
        "message": resp.message,
        "active_url": resp.active_url,
        "active_title": resp.active_title,
        "active_tab": resp.active_tab_index,
        "total_tabs": resp.total_tabs,
        "logs": resp.output_lines,
    }
    return json.dumps(output, indent=2, ensure_ascii=False)


@mcp.tool()
def webpilot_upload_file(
    field_name: str,
    file_path: str,
    screenshot_path: Optional[str] = None,
) -> str:
    """Uploads a file or document to a file input or drag-and-drop zone.

    Args:
        field_name: Name or label of the file upload field (e.g. 'resume', 'cv', 'attachment').
        file_path: Absolute or relative path to the local file to upload.
        screenshot_path: Optional path to save visual screenshot after upload.

    Returns:
        Status of the upload action and confirmation.
    """
    upload_arg = f"{field_name}={file_path}"
    req = SupervisorActionRequest(
        action="apply",
        upload_files=[upload_arg],
        screenshot_path=screenshot_path,
    )
    resp = client.execute(req)
    return json.dumps(
        {
            "success": resp.success,
            "message": resp.message,
            "logs": resp.output_lines,
        },
        indent=2,
        ensure_ascii=False,
    )


@mcp.tool()
def webpilot_screenshot(
    output_path: str = "screenshot.png",
) -> str:
    """Captures a visual screenshot of the current active browser page.

    Args:
        output_path: File path where the screenshot PNG will be saved.

    Returns:
        Confirmation and file path of saved screenshot.
    """
    req = SupervisorActionRequest(action="apply", screenshot_path=output_path)
    resp = client.execute(req)
    if resp.success:
        return f"Screenshot successfully captured and saved to '{output_path}'."
    return f"Failed to capture screenshot: {resp.message}"


@mcp.tool()
def webpilot_list_tabs() -> str:
    """Lists all open tabs and windows in the active persistent browser session.

    Returns:
        List of tabs with index, title, URL, and active flag.
    """
    req = SupervisorActionRequest(action="list_tabs")
    resp = client.execute(req)
    return json.dumps(
        {
            "success": resp.success,
            "active_tab": resp.active_tab_index,
            "total_tabs": resp.total_tabs,
            "tabs": resp.tabs,
        },
        indent=2,
        ensure_ascii=False,
    )


@mcp.tool()
def webpilot_switch_tab(
    tab_index: int,
) -> str:
    """Switches active focus to a specific tab by index.

    Args:
        tab_index: 0-based index of the target tab.

    Returns:
        Details of the newly active tab.
    """
    req = SupervisorActionRequest(action="switch_tab", tab_index=tab_index)
    resp = client.execute(req)
    return json.dumps(
        {
            "success": resp.success,
            "active_tab_index": resp.active_tab_index,
            "active_url": resp.active_url,
            "active_title": resp.active_title,
        },
        indent=2,
        ensure_ascii=False,
    )


@mcp.tool()
def webpilot_save_cookies(
    output_path: str = "session_cookies.json",
) -> str:
    """Exports current session cookies from the browser to a JSON file.

    Args:
        output_path: File path to save the cookies JSON.

    Returns:
        Confirmation message.
    """
    req = SupervisorActionRequest(action="apply", cookies_path=output_path)
    resp = client.execute(req)
    if resp.success:
        return f"Cookies saved successfully to '{output_path}'."
    return f"Failed to save cookies: {resp.message}"


@mcp.tool()
def webpilot_service_status() -> str:
    """Returns the operational status and telemetry of all WebPilot tiers.

    Returns:
        Status of Layer 1 (Supervisor), Layer 2 (Worker PID), Layer 3 (Chromium PID), and tab count.
    """
    is_alive = client.is_running()
    if not is_alive:
        return json.dumps(
            {
                "status": "stopped",
                "message": "Master Supervisor is not currently running. It will auto-spawn upon the next tool call.",
            },
            indent=2,
        )

    req = SupervisorActionRequest(action="list_tabs")
    resp = client.execute(req)
    return json.dumps(
        {
            "status": "active",
            "layer1_supervisor_url": client.base_url,
            "layer2_worker_pid": resp.worker_pid,
            "layer3_chromium_pid": resp.browser_pid,
            "active_tab_index": resp.active_tab_index,
            "total_tabs": resp.total_tabs,
            "active_url": resp.active_url,
            "active_title": resp.active_title,
        },
        indent=2,
        ensure_ascii=False,
    )


@mcp.tool()
def webpilot_service_restart() -> str:
    """Performs an instant cascading kill and restart of the browser session.

    Cleans up any hanging processes and respawns a fresh worker tier in ~300ms.

    Returns:
        Restart confirmation.
    """
    resp = client.restart_worker()
    return json.dumps(
        {
            "success": resp.success,
            "message": resp.message,
            "new_worker_pid": resp.worker_pid,
        },
        indent=2,
    )


def main():
    """Entry point for running the WebPilot MCP Server."""
    mcp.run()


if __name__ == "__main__":
    main()
