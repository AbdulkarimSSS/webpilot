"""Tests verifying remediation of benchmark defects WPB-001 through WPB-009."""

import json
import os
import tempfile
import pytest
from unittest.mock import MagicMock

from common.paths import validate_safe_path, validate_safe_url
from core.exceptions import ValidationError
from mcp_tools import (
    _truncate_echo,
    execute_inspect,
    execute_save_cookies,
    execute_screenshot,
    execute_switch_tab,
)
from supervisor.contracts import SupervisorActionResponse
from adapters.live_session_manager import LiveSessionManager


def test_wpb_002_save_cookies_empty_path_rejected():
    mock_client = MagicMock()
    res = execute_save_cookies(mock_client, output_path="")
    assert "Failed to save cookies: output_path cannot be empty" in res
    assert not mock_client.execute.called


def test_wpb_002_save_cookies_sensitive_path_rejected():
    mock_client = MagicMock()
    res = execute_save_cookies(mock_client, output_path="/home/user/.ssh/authorized_keys")
    assert "Failed to save cookies" in res
    assert "Security restriction" in res
    assert not mock_client.execute.called


def test_wpb_002_save_cookies_failure_reported_honestly():
    mock_client = MagicMock()
    mock_client.execute.return_value = SupervisorActionResponse(
        success=False,
        action="apply",
        message="Form completed with unconfirmed or failed fields.",
        output_lines=["[!] Failed to save cookies: Permission denied"],
    )
    res = execute_save_cookies(mock_client, output_path="valid_cookies.json")
    assert "Failed to save cookies" in res


def test_wpb_003_url_scheme_lfi_blocked():
    with pytest.raises(ValidationError) as exc:
        validate_safe_url("file:///etc/passwd")
    assert "file://" in str(exc.value)


def test_wpb_003_url_scheme_data_and_js_blocked():
    with pytest.raises(ValidationError):
        validate_safe_url("data:text/html,<h1>x</h1>")
    with pytest.raises(ValidationError):
        validate_safe_url("javascript:alert(1)")


def test_wpb_003_cloud_metadata_ssrf_blocked():
    with pytest.raises(ValidationError) as exc:
        validate_safe_url("http://169.254.169.254/latest/meta-data/")
    assert "cloud instance metadata" in str(exc.value)


def test_wpb_004_screenshot_overwrite_prevented():
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tf:
        tf.write(b"existing content")
        existing_path = tf.name

    try:
        mock_client = MagicMock()
        res = execute_screenshot(mock_client, output_path=existing_path)
        assert "Failed to capture screenshot" in res
        assert "already exists" in res
        assert not mock_client.execute.called
    finally:
        if os.path.exists(existing_path):
            os.remove(existing_path)


def test_wpb_005_response_bloat_truncation():
    big_val = "A" * 2_000_000
    truncated = _truncate_echo(big_val, max_len=150)
    assert len(truncated) < 300
    assert "[truncated 2000000 chars]" in truncated

    nested = {"name": big_val, "list": [big_val]}
    t_nested = _truncate_echo(nested, max_len=150)
    assert "[truncated 2000000 chars]" in t_nested["name"]
    assert "[truncated 2000000 chars]" in t_nested["list"][0]


def test_wpb_006_no_attach_shadow_override_in_adapter():
    with open("adapters/browser_adapter.py", "r", encoding="utf-8") as f:
        content = f.read()
    assert "Element.prototype.attachShadow" not in content
    assert "fakePlugin" not in content


def test_wpb_008_switch_tab_out_of_range_message():
    mock_client = MagicMock()
    mock_client.execute.return_value = SupervisorActionResponse(
        success=False,
        action="switch_tab",
        active_tab_index=0,
        active_url="http://example.com",
        active_title="Example",
        message="",
    )
    raw_res = execute_switch_tab(mock_client, tab_index=99)
    res = json.loads(raw_res)
    assert not res["success"]
    assert "out of range" in res["message"]


def test_wpb_009_temp_profile_cleanup():
    tmp = tempfile.gettempdir()
    fake_profile = os.path.join(tmp, "playwright_chromiumdev_profile-test_wpb009")
    os.makedirs(fake_profile, exist_ok=True)
    with open(os.path.join(fake_profile, "test.txt"), "w") as f:
        f.write("mock profile")

    assert os.path.isdir(fake_profile)
    cleaned = LiveSessionManager.cleanup_temp_profiles(max_age_seconds=0)
    assert cleaned >= 1
    assert not os.path.exists(fake_profile)
