"""Unit tests for Master Supervisor, Worker Process contracts, and Supervisor Client."""

import json
import pytest
from supervisor.contracts import SupervisorActionRequest, SupervisorActionResponse
from supervisor.client import SupervisorClient, DEFAULT_SUPERVISOR_URL


def test_supervisor_action_request_roundtrip():
    """Verify SupervisorActionRequest serialization and deserialization."""
    req = SupervisorActionRequest(
        action="apply",
        url="https://example.com/login",
        fill_arguments=["username=testuser", "password=secret"],
        press_buttons=["Sign In"],
        submit=True,
        screenshot_path="screenshot.png",
        tab_index=1,
        auto_inspect=False,
    )
    data = req.to_dict()
    assert data["action"] == "apply"
    assert data["url"] == "https://example.com/login"
    assert data["fill_arguments"] == ["username=testuser", "password=secret"]
    assert data["press_buttons"] == ["Sign In"]
    assert data["submit"] is True
    assert data["screenshot_path"] == "screenshot.png"
    assert data["tab_index"] == 1
    assert data["auto_inspect"] is False

    reconstructed = SupervisorActionRequest.from_dict(data)
    assert reconstructed == req


def test_supervisor_action_response_roundtrip():
    """Verify SupervisorActionResponse serialization and deserialization."""
    resp = SupervisorActionResponse(
        success=True,
        action="apply",
        message="Success",
        browser_pid=1234,
        worker_pid=5678,
        active_tab_index=0,
        active_url="https://example.com/dashboard",
        active_title="Dashboard",
        total_tabs=1,
        tabs=[{"index": 0, "title": "Dashboard", "url": "https://example.com/dashboard", "is_active": True}],
        confirmed_fields=[("username", "testuser")],
        failed_fields=[],
        validation_errors=[],
        output_lines=["[✓] Form submitted"],
    )
    data = resp.to_dict()
    assert data["success"] is True
    assert data["browser_pid"] == 1234
    assert data["worker_pid"] == 5678
    assert len(data["tabs"]) == 1
    assert data["output_lines"] == ["[✓] Form submitted"]

    reconstructed = SupervisorActionResponse.from_dict(data)
    assert reconstructed == resp


def test_supervisor_client_default_url():
    """Verify SupervisorClient initialization with default and custom URLs."""
    client_default = SupervisorClient()
    assert client_default.base_url == DEFAULT_SUPERVISOR_URL

    client_custom = SupervisorClient(base_url="http://127.0.0.1:9555/")
    assert client_custom.base_url == "http://127.0.0.1:9555"


def test_supervisor_action_request_defaults():
    """Verify default values of SupervisorActionRequest."""
    req = SupervisorActionRequest(action="inspect")
    assert req.action == "inspect"
    assert req.url is None
    assert req.fill_arguments == []
    assert req.press_buttons == []
    assert req.upload_files == []
    assert req.submit is False
    assert req.auto_inspect is True
    assert req.timeout_minutes == 30
