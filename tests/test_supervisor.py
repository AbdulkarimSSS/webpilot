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


def test_supervisor_spawn_and_restart_worker(monkeypatch):
    """Verify MasterSupervisor._spawn_worker and restart_worker lifecycle with start_new_session."""
    from supervisor.master_daemon import MasterSupervisor
    import subprocess
    import sys

    sup = MasterSupervisor(port=9777, token="dummy-token")
    sup._is_running = False  # Stop watchdog thread

    spawn_calls = []

    class DummyProc:
        def __init__(self, pid):
            self.pid = pid
        def poll(self):
            return None

    def fake_popen(cmd, **kwargs):
        spawn_calls.append((cmd, kwargs))
        return DummyProc(pid=1000 + len(spawn_calls))

    monkeypatch.setattr(subprocess, "Popen", fake_popen)

    # Test initial spawn via _ensure_worker
    proc1 = sup._ensure_worker()
    assert proc1.pid == 1001
    assert len(spawn_calls) == 1
    cmd1, kwargs1 = spawn_calls[0]
    assert kwargs1["env"]["WEBPILOT_SUPERVISOR_TOKEN"] == "dummy-token"
    if sys.platform != "win32":
        assert kwargs1.get("start_new_session") is True

    # Test restart_worker
    terminated = []
    monkeypatch.setattr(sup, "terminate_worker", lambda: terminated.append(True))
    resp = sup.restart_worker()

    assert resp.success is True
    assert resp.action == "restart_worker"
    assert resp.worker_pid == 1002
    assert len(terminated) == 1
    assert len(spawn_calls) == 2
    cmd2, kwargs2 = spawn_calls[1]
    # Verify that restart_worker uses the unified _spawn_worker
    if sys.platform != "win32":
        assert kwargs2.get("start_new_session") is True
    assert kwargs2["env"]["WEBPILOT_SUPERVISOR_TOKEN"] == "dummy-token"


def test_worker_process_field_verification(monkeypatch):
    """Verify worker_process calls verify_field_value and populates confirmed and unconfirmed fields."""
    from supervisor.worker_process import OperationalWorker
    from unittest.mock import MagicMock

    worker = OperationalWorker()

    mock_coord = MagicMock()
    mock_coord.page.url = "https://example.com/form"
    mock_coord.page.title.return_value = "Test Form"
    mock_coord.page.is_closed.return_value = False
    mock_coord.page.locator.return_value.count.return_value = 0
    mock_coord.context.pages = [mock_coord.page]
    worker.coordinator = mock_coord
    monkeypatch.setattr(worker, "_ensure_session", lambda req: mock_coord)

    # Mock FieldInteractionService
    mock_field_svc = MagicMock()
    mock_field_svc.set_field.side_effect = lambda k, v: k != "skipped_field"
    mock_field_svc.verify_field_value.side_effect = lambda k, v: k == "verified_field"

    monkeypatch.setattr("supervisor.worker_process.FieldInteractionService", lambda page: mock_field_svc)
    monkeypatch.setattr("supervisor.worker_process.AuthNavigationService", lambda p, c: MagicMock())
    monkeypatch.setattr("supervisor.worker_process.FormValidator", lambda p: MagicMock(get_validation_errors=lambda: []))
    monkeypatch.setattr("supervisor.worker_process.InspectionService", lambda p: MagicMock())

    req = SupervisorActionRequest(
        action="apply",
        url="https://example.com/form",
        fill_arguments=[
            "verified_field=value1",
            "unverified_field=value2",
            "skipped_field=value3",
        ],
        auto_inspect=False,
    )

    resp = worker._handle_apply(req)

    assert resp.success is True
    assert resp.confirmed_fields == [("verified_field", "value1")]
    assert resp.unconfirmed_fields == [("unverified_field", "value2")]
    assert resp.failed_fields == [("skipped_field", "value3")]
    assert mock_field_svc.verify_field_value.called

