"""Tests for cookies command and extraction functionality."""

import json
from unittest.mock import MagicMock, patch
from supervisor.contracts import SupervisorActionRequest, SupervisorActionResponse
from supervisor.worker_process import OperationalWorker
from webpilot.client import WebPilot


def test_worker_handle_cookies(tmp_path):
    worker = OperationalWorker(headed=False)
    mock_coord = MagicMock()
    mock_ctx = MagicMock()
    mock_page = MagicMock()
    mock_page.url = "https://example.com"
    mock_page.title.return_value = "Example Domain"
    mock_coord.context = mock_ctx
    mock_coord.page = mock_page
    mock_coord.adapter.browser_pid = 1234

    raw_cookies = [
        {"name": "session_id", "value": "xyz123", "domain": "example.com", "path": "/"},
        {"name": "tracking", "value": "abc987", "domain": "analytics.net", "path": "/"},
    ]
    mock_ctx.cookies.return_value = raw_cookies

    out_file = str(tmp_path / "saved_cookies.json")
    req = SupervisorActionRequest(
        action="cookies",
        query="example.com",
        output_path=out_file,
    )

    with patch.object(worker, "_ensure_session", return_value=mock_coord):
        resp = worker.handle_request(req)

    assert resp.success is True
    assert resp.action == "cookies"
    assert len(resp.cookies) == 1
    assert resp.cookies[0]["name"] == "session_id"
    assert "saved_cookies.json" in resp.message

    # Verify file saved
    with open(out_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert len(data) == 1
    assert data[0]["name"] == "session_id"


def test_webpilot_sdk_cookies():
    client_mock = MagicMock()
    client_mock.execute.return_value = SupervisorActionResponse(
        success=True,
        action="cookies",
        cookies=[{"name": "token", "value": "secret", "domain": "test.com"}],
    )
    with patch("webpilot.client.SupervisorClient", return_value=client_mock):
        wp = WebPilot()
        cookies = wp.cookies(domain_or_url="test.com")
        assert len(cookies) == 1
        assert cookies[0]["name"] == "token"
