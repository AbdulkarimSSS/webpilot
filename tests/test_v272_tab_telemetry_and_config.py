"""Tests for WebPilot v2.7.2:
- --html strict safety ceiling truncation
- Config key normalization (case-insensitive, hyphen-agnostic, tab_timeout, max_chars)
- TabManager telemetry (state, open_since, last_activity, tab_timeout)
- Tab inactivity auto-reaping
- Multi-session tab enumeration and hierarchy
"""

import time
import pytest
from unittest.mock import MagicMock, patch

from config.preferences import (
    normalize_config_key,
    get_preference,
    set_preference,
    unset_preference,
    clear_preferences,
    apply_persistent_preferences,
)
from adapters.tab_manager import TabManager, TabTelemetry
from services.html_diagnostic_service import HTMLDiagnosticService


def test_html_safety_guard_enforced():
    """Verifies that large HTML is safely truncated by default ceiling (20,000 chars) unless --all."""
    huge_html = "<div>" + ("A" * 30000) + "</div>"
    truncated = HTMLDiagnosticService.apply_safety_guard(huge_html, max_chars=20000, show_all=False)
    assert len(truncated) < 25000
    assert "Truncated: showing first 20,000" in truncated

    # Bypassed with show_all=True
    full = HTMLDiagnosticService.apply_safety_guard(huge_html, max_chars=20000, show_all=True)
    assert len(full) == len(huge_html)


def test_config_key_normalization():
    """Verifies that config keys match regardless of case or hyphens."""
    assert normalize_config_key("Tab-Timeout") == "tab_timeout"
    assert normalize_config_key("STRIP-HEADER") == "strip_header"
    assert normalize_config_key("  Strip_Header  ") == "strip_header"
    assert normalize_config_key("Max-Chars") == "max_chars"


def test_config_crud_with_variant_keys(tmp_path):
    """Verifies get, set, unset with case-insensitive and hyphen variants."""
    fake_pref_file = str(tmp_path / "preferences.json")
    with patch("config.preferences.PREFERENCES_FILE", fake_pref_file), \
         patch("config.preferences.CONFIG_DIR", str(tmp_path)):
        clear_preferences()

        set_preference("Tab-Timeout", 15)
        assert get_preference("tab_timeout") == 15
        assert get_preference("TAB_TIMEOUT") == 15
        assert get_preference("Tab-Timeout") == 15

        set_preference("Strip-Header", True)
        assert get_preference("strip_header") is True
        assert get_preference("strip-header") is True

        assert unset_preference("TAB-TIMEOUT") is True
        assert get_preference("tab_timeout") is None


def test_apply_persistent_preferences_tab_timeout_and_max_chars(tmp_path):
    """Verifies that tab_timeout and max_chars auto-apply to argparse namespace."""
    fake_pref_file = str(tmp_path / "preferences.json")
    with patch("config.preferences.PREFERENCES_FILE", fake_pref_file), \
         patch("config.preferences.CONFIG_DIR", str(tmp_path)):
        clear_preferences()
        set_preference("Tab-Timeout", 25)
        set_preference("Max-Chars", 15000)

        class FakeArgs:
            tab_timeout = 30
            max_chars = 20000
            no_persistent_config = False

        args = FakeArgs()
        notices = apply_persistent_preferences(args)
        assert args.tab_timeout == 25
        assert args.max_chars == 15000
        assert any("tab_timeout=25m" in n for n in notices)
        assert any("max_chars=15000" in n for n in notices)


def test_tab_manager_telemetry_and_duration_format():
    """Verifies TabManager duration formatting and telemetry tracking."""
    assert TabManager.format_duration(15) == "15s ago"
    assert TabManager.format_duration(95) == "1m 35s ago"
    assert TabManager.format_duration(3600) == "1h ago"
    assert TabManager.format_duration(3720) == "1h 2m ago"

    mock_page = MagicMock()
    mock_page.title.return_value = "Test Page"
    mock_page.url = "https://example.com"
    mock_page.is_closed.return_value = False

    telem = TabManager.get_or_create_telemetry(mock_page, timeout_minutes=45)
    assert telem.state == "IDLE"
    assert telem.tab_timeout_minutes == 45

    telem.mark_loading()
    assert telem.state == "LOADING"
    assert telem.loading_started is not None

    telem.mark_idle()
    assert telem.state == "IDLE"
    assert telem.loading_started is None


def test_tab_manager_inactive_reaping():
    """Verifies that background tabs exceeding their tab_timeout are reaped while active page is spared."""
    p_active = MagicMock()
    p_active.title.return_value = "Active Tab"
    p_active.url = "https://active.com"
    p_active.is_closed.return_value = False

    p_idle_old = MagicMock()
    p_idle_old.title.return_value = "Stale Background Tab"
    p_idle_old.url = "https://stale.com"
    p_idle_old.is_closed.return_value = False

    ctx = MagicMock()
    ctx.pages = [p_active, p_idle_old]

    telem_active = TabManager.get_or_create_telemetry(p_active, timeout_minutes=30)
    telem_old = TabManager.get_or_create_telemetry(p_idle_old, timeout_minutes=10)

    # Simulate p_idle_old being inactive for 15 minutes (900s > 600s timeout)
    telem_old.last_activity = time.time() - 950

    reaped = TabManager.reap_inactive_tabs(ctx, active_page=p_active)
    assert 1 in reaped
    p_idle_old.close.assert_called_once()
    p_active.close.assert_not_called()


def test_tab_cmd_print_session_tabs(capsys):
    """Verifies that _print_session_tabs outputs the expected hierarchical tree."""
    from cli_commands.tab_cmd import _print_session_tabs

    tabs = [
        {
            "index": 0,
            "title": "Google",
            "url": "https://google.com",
            "is_active": True,
            "state": "IDLE",
            "open_since": "5m ago",
            "last_activity": "10s ago",
            "tab_timeout_minutes": 30,
        },
        {
            "index": 1,
            "title": "Siemens Portal",
            "url": "https://jobs.siemens.com",
            "is_active": False,
            "state": "IDLE",
            "open_since": "2m ago",
            "last_activity": "1m ago",
            "tab_timeout_minutes": 15,
        },
    ]

    _print_session_tabs("worker-session", pid=12345, tabs=tabs, port=9225)
    captured = capsys.readouterr().out
    assert "Browser Instance: [worker-session] (PID: 12345 | Port: 9225)" in captured
    assert "Tab #0 [*ACTIVE*]: 'Google'" in captured
    assert "Tab #1: 'Siemens Portal'" in captured
    assert "Timeout: 30m" in captured
    assert "Timeout: 15m" in captured
