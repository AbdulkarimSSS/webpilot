"""Unit tests for WebPilot MCP Server and tool registrations."""

import json
from unittest.mock import MagicMock, patch
import pytest

from mcp_server import mcp, webpilot_service_status, webpilot_screenshot
from supervisor.contracts import SupervisorActionResponse


def test_mcp_server_tools_registered():
    """Verify that all 10 WebPilot tools are properly registered on FastMCP."""
    tool_manager = mcp._tool_manager
    tool_names = [t.name for t in tool_manager.list_tools()]

    expected_tools = [
        "webpilot_inspect",
        "webpilot_fill_form",
        "webpilot_click_button",
        "webpilot_upload_file",
        "webpilot_screenshot",
        "webpilot_list_tabs",
        "webpilot_switch_tab",
        "webpilot_save_cookies",
        "webpilot_service_status",
        "webpilot_service_restart",
    ]

    for tool in expected_tools:
        assert tool in tool_names, f"Tool '{tool}' not found in registered MCP tools"


@patch("mcp_server.client")
def test_mcp_service_status_stopped(mock_client):
    """Verify webpilot_service_status returns stopped status when daemon is not alive."""
    mock_client.is_running.return_value = False

    result_json = webpilot_service_status()
    data = json.loads(result_json)

    assert data["status"] == "stopped"
    assert "not currently running" in data["message"]


@patch("mcp_server.client")
def test_mcp_service_status_active(mock_client):
    """Verify webpilot_service_status returns full telemetry when daemon is active."""
    mock_client.is_running.return_value = True
    mock_client.base_url = "http://127.0.0.1:9333"

    mock_resp = SupervisorActionResponse(
        success=True,
        action="inspect",
        worker_pid=1111,
        browser_pid=2222,
        active_tab_index=0,
        total_tabs=1,
        active_url="https://example.com",
        active_title="Example Domain",
    )
    mock_client.execute.return_value = mock_resp

    result_json = webpilot_service_status()
    data = json.loads(result_json)

    assert data["status"] == "active"
    assert data["layer2_worker_pid"] == 1111
    assert data["layer3_chromium_pid"] == 2222
    assert data["active_url"] == "https://example.com"


@patch("mcp_server.client")
def test_mcp_screenshot_tool(mock_client):
    """Verify webpilot_screenshot tool call."""
    mock_client.execute.return_value = SupervisorActionResponse(success=True, action="apply")

    res = webpilot_screenshot("output.png")
    assert "successfully captured" in res
    assert "output.png" in res
