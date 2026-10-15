"""Unit tests for WebPilot programmatic Python SDK package."""

import pytest
from unittest.mock import MagicMock, patch

import webpilot
import webpilot_engine
from webpilot import (
    WebPilot,
    WebPilotEngine,
    UniversalFormEngine,
    SupervisorClient,
    __version__,
)
from supervisor.contracts import SupervisorActionResponse


def test_package_exports_and_aliases():
    """Verifies that webpilot exports expected symbols and version."""
    assert __version__ == "2.5.4"
    assert webpilot.__version__ == "2.5.4"
    assert webpilot_engine.__version__ == "2.5.4"
    assert WebPilotEngine is UniversalFormEngine
    assert issubclass(WebPilot, object)


def test_webpilot_client_init_and_context_manager():
    """Verifies client initialization and context manager protocol."""
    wp = WebPilot(host="127.0.0.1", port=9333, token="test-token")
    assert wp.base_url == "http://127.0.0.1:9333"
    assert wp.client.token == "test-token"

    with WebPilot(host="127.0.0.1", port=9333) as client:
        assert isinstance(client, WebPilot)


@patch.object(SupervisorClient, "execute")
def test_webpilot_inspect(mock_execute):
    """Verifies wp.inspect delegates cleanly to SupervisorClient."""
    mock_execute.return_value = SupervisorActionResponse(
        success=True,
        action="inspect",
        schema={"title": "Test Form", "inputs": [{"name": "email"}]},
    )

    wp = WebPilot()
    schema = wp.inspect("http://127.0.0.1:8900/s/S01", unpack_options=True)

    assert schema["title"] == "Test Form"
    assert len(schema["inputs"]) == 1
    mock_execute.assert_called_once()
    req = mock_execute.call_args[0][0]
    assert req.action == "inspect"
    assert req.url == "http://127.0.0.1:8900/s/S01"
    assert req.unpack_options is True


@patch.object(SupervisorClient, "execute")
def test_webpilot_inspect_failure_raises(mock_execute):
    """Verifies wp.inspect raises RuntimeError on failure."""
    mock_execute.return_value = SupervisorActionResponse(
        success=False,
        action="inspect",
        message="Page load timeout",
    )

    wp = WebPilot()
    with pytest.raises(RuntimeError, match="Inspection failed: Page load timeout"):
        wp.inspect("http://invalid.url")


@patch.object(SupervisorClient, "execute")
def test_webpilot_apply(mock_execute):
    """Verifies wp.apply constructs fill, press, upload, and submit payloads."""
    mock_execute.return_value = SupervisorActionResponse(
        success=True,
        action="apply",
        confirmed_fields=["first_name", "email"],
        unconfirmed_fields=[],
        failed_fields=[],
    )

    wp = WebPilot()
    res = wp.apply(
        url="http://127.0.0.1:8900/s/S01",
        fields={"first_name": "Alice", "email": "alice@example.com"},
        press=["Next", "Submit"],
        upload="resume=cv.pdf",
        submit=True,
    )

    assert res.success is True
    assert res.confirmed_fields == ["first_name", "email"]
    mock_execute.assert_called_once()
    req = mock_execute.call_args[0][0]
    assert req.action == "apply"
    assert req.url == "http://127.0.0.1:8900/s/S01"
    assert "first_name=Alice" in req.fill_arguments
    assert "email=alice@example.com" in req.fill_arguments
    assert req.press_buttons == ["Next", "Submit"]
    assert req.upload_files == ["resume=cv.pdf"]
    assert req.submit is True


@patch.object(SupervisorClient, "execute")
def test_webpilot_find_and_click(mock_execute):
    """Verifies wp.find and wp.click helper methods."""
    mock_execute.return_value = SupervisorActionResponse(
        success=True,
        action="probe",
        output_lines=["Field: Country", "Options: [USA, Japan]"],
    )

    wp = WebPilot()
    res = wp.find("Country", options=True, query="Jap", html=True, up=2, screenshot="crop.png")

    assert res.success is True
    req = mock_execute.call_args[0][0]
    assert req.action == "probe"
    assert req.target_field == "Country"
    assert req.include_options is True
    assert req.include_html is True
    assert req.up_levels == 2
    assert req.screenshot_path == "crop.png"
    assert req.query == "Jap"

    # Test click
    wp.click("Apply Now")
    click_req = mock_execute.call_args[0][0]
    assert click_req.action == "apply"
    assert click_req.press_buttons == ["Apply Now"]


@patch.object(SupervisorClient, "execute")
def test_webpilot_tabs(mock_execute):
    """Verifies tab listing and switching."""
    mock_execute.return_value = SupervisorActionResponse(
        success=True,
        action="list_tabs",
        tabs=[{"index": 0, "title": "Main Tab"}, {"index": 1, "title": "Popup"}],
    )

    wp = WebPilot()
    tabs = wp.list_tabs()
    assert len(tabs) == 2
    assert tabs[1]["title"] == "Popup"

    wp.switch_tab(1)
    switch_req = mock_execute.call_args[0][0]
    assert switch_req.action == "switch_tab"
    assert switch_req.tab_index == 1


@patch.object(SupervisorClient, "get_status")
@patch.object(SupervisorClient, "restart_worker")
def test_webpilot_service_methods(mock_restart, mock_status):
    """Verifies supervisor service inspection and worker restart."""
    mock_status.return_value = {"supervisor_running": True, "worker_running": True}
    mock_restart.return_value = True

    wp = WebPilot()
    status = wp.service_status()
    assert status["supervisor_running"] is True

    restarted = wp.service_restart()
    assert restarted is True
    mock_restart.assert_called_once()
