"""WebPilot MCP Server (Model Context Protocol).

Exposes WebPilot's autonomous multi-tier browser engine as standard MCP tools
for AI Agents (Claude, OpenCode, Cursor, etc.).
"""

from __future__ import annotations

import os
import sys
from typing import Any, Dict, Optional

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

try:
    from mcp.server.fastmcp import FastMCP
except ImportError:
    FastMCP = None


class _DummyMCP:
    def __init__(self):
        self._tools = {}

    def tool(self, *args, **kwargs):
        def decorator(f):
            self._tools[f.__name__] = f
            return f
        return decorator

    @property
    def _tool_manager(self):
        class _Manager:
            def __init__(self, tools):
                self._tools = tools
            def list_tools(self):
                class _T:
                    def __init__(self, name):
                        self.name = name
                return [_T(k) for k in self._tools.keys()]
        return _Manager(self._tools)

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
import mcp_tools

client = SupervisorClient()


@mcp.tool()
def webpilot_inspect(
    url: Optional[str] = None,
    unpack_options: bool = False,
    screenshot_path: Optional[str] = None,
    tab_index: Optional[int] = None,
) -> str:
    """Inspects a web page and returns a token-optimized schema of all inputs, buttons, and dropdowns."""
    return mcp_tools.execute_inspect(client, url, unpack_options, screenshot_path, tab_index)


@mcp.tool()
def webpilot_fill_form(
    fields: Dict[str, Any],
    url: Optional[str] = None,
    submit: bool = False,
    cookies_path: Optional[str] = None,
    screenshot_path: Optional[str] = None,
    tab_index: Optional[int] = None,
) -> str:
    """Fills web form fields dynamically with 3-stage physical DOM verification."""
    return mcp_tools.execute_fill_form(client, fields, url, submit, cookies_path, screenshot_path, tab_index)


@mcp.tool()
def webpilot_click_button(
    button_text: str,
    screenshot_path: Optional[str] = None,
    cookies_path: Optional[str] = None,
    tab_index: Optional[int] = None,
) -> str:
    """Clicks a button, link, or tab with reactive mutation tracking (redirects, loaders, popups)."""
    return mcp_tools.execute_click_button(client, button_text, screenshot_path, cookies_path, tab_index)


@mcp.tool()
def webpilot_upload_file(
    field_name: str,
    file_path: str,
    screenshot_path: Optional[str] = None,
) -> str:
    """Uploads a file or document to a file input or drag-and-drop zone."""
    return mcp_tools.execute_upload_file(client, field_name, file_path, screenshot_path)


@mcp.tool()
def webpilot_screenshot(
    output_path: str = "screenshot.png",
) -> str:
    """Captures a visual screenshot of the current active browser page."""
    return mcp_tools.execute_screenshot(client, output_path)


@mcp.tool()
def webpilot_list_tabs() -> str:
    """Lists all open tabs and windows in the active persistent browser session."""
    return mcp_tools.execute_list_tabs(client)


@mcp.tool()
def webpilot_switch_tab(
    tab_index: int,
) -> str:
    """Switches active focus to a specific tab by index."""
    return mcp_tools.execute_switch_tab(client, tab_index)


@mcp.tool()
def webpilot_save_cookies(
    output_path: str = "session_cookies.json",
) -> str:
    """Exports current session cookies from the browser to a JSON file."""
    return mcp_tools.execute_save_cookies(client, output_path)


@mcp.tool()
def webpilot_service_status() -> str:
    """Returns the operational status and telemetry of all WebPilot tiers."""
    return mcp_tools.execute_service_status(client)


@mcp.tool()
def webpilot_service_restart() -> str:
    """Performs an instant cascading kill and restart of the browser session."""
    return mcp_tools.execute_service_restart(client)


def main():
    """Main entrypoint for running the MCP server."""
    mcp.run()


if __name__ == "__main__":
    main()
