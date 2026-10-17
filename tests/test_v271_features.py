"""Unit and integration tests for WebPilot v2.7.1 features.

Tests cover:
1. Container-confined read: wp read --selector <sel>
2. Pure text extraction: wp find <target> --text
3. Explicit wait command: wp wait --selector <sel> --timeout <ms>
4. Active/interactive typeahead probe for AJAX picklists: wp probe <target> --search <query>
5. Persistent user preferences & sticky flags: wp config & inversion flags
6. Multi-session independent browser instances: --session <name>
"""

import argparse
import json
import os
import tempfile
from unittest.mock import MagicMock, patch
import pytest

from adapters.live_session_manager import LiveSessionManager, DEFAULT_CDP_PORT
from config.preferences import (
    apply_persistent_preferences,
    clear_preferences,
    get_preference,
    load_preferences,
    save_preferences,
    set_preference,
    unset_preference,
)
from cli_parser import build_cli_parser
from supervisor.contracts import SupervisorActionRequest, SupervisorActionResponse


# ==============================================================================
# Feature 5: Persistent User Preferences & Sticky Flags
# ==============================================================================

def test_persistent_preferences_lifecycle(monkeypatch):
    """Verifies load, set, unset, clear of preferences on disk."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        test_pref_file = os.path.join(tmp_dir, "preferences.json")
        monkeypatch.setattr("config.preferences.PREFERENCES_FILE", test_pref_file)
        monkeypatch.setattr("config.preferences.CONFIG_DIR", tmp_dir)

        # Empty initially
        assert load_preferences() == {}

        # Set preferences
        set_preference("strip_header", True)
        set_preference("exclude", "svg,script")
        set_preference("session", "main")

        loaded = load_preferences()
        assert loaded.get("strip_header") is True
        assert loaded.get("exclude") == "svg,script"
        assert loaded.get("session") == "main"
        assert get_preference("session") == "main"

        # Unset preference
        assert unset_preference("session") is True
        assert "session" not in load_preferences()

        # Clear preferences
        clear_preferences()
        assert load_preferences() == {}


def test_persistent_preferences_application_and_inversion(monkeypatch):
    """Verifies sticky flags apply additively and can be inverted by CLI flags."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        test_pref_file = os.path.join(tmp_dir, "preferences.json")
        monkeypatch.setattr("config.preferences.PREFERENCES_FILE", test_pref_file)
        monkeypatch.setattr("config.preferences.CONFIG_DIR", tmp_dir)

        set_preference("strip_header", True)
        set_preference("exclude", "svg,script")
        set_preference("session", "auto_session")

        # 1. Normal command: inherits persistent preferences
        args = argparse.Namespace(
            command="find",
            target="@fld-1",
            strip_header=None,
            with_header=False,
            exclude=None,
            no_exclude=False,
            session=None,
            no_persistent_config=False,
        )
        notices = apply_persistent_preferences(args)
        assert args.strip_header is True
        assert args.exclude == "svg,script"
        assert args.session == "auto_session"
        assert len(notices) >= 3

        # 2. Additive merge for exclude tags
        args_merge = argparse.Namespace(
            command="find",
            target="@fld-1",
            strip_header=None,
            with_header=False,
            exclude="style,iframe",
            no_exclude=False,
            session=None,
            no_persistent_config=False,
        )
        apply_persistent_preferences(args_merge)
        assert "iframe" in args_merge.exclude
        assert "script" in args_merge.exclude
        assert "svg" in args_merge.exclude
        assert "style" in args_merge.exclude

        # 3. Inversion flag: --with-header
        args_with_hdr = argparse.Namespace(
            command="find",
            target="@fld-1",
            strip_header=None,
            with_header=True,
            exclude=None,
            no_exclude=False,
            session=None,
            no_persistent_config=False,
        )
        apply_persistent_preferences(args_with_hdr)
        assert args_with_hdr.strip_header is False

        # 4. Inversion flag: --no-exclude
        args_no_exc = argparse.Namespace(
            command="find",
            target="@fld-1",
            strip_header=None,
            with_header=False,
            exclude="style",
            no_exclude=True,
            session=None,
            no_persistent_config=False,
        )
        apply_persistent_preferences(args_no_exc)
        assert args_no_exc.exclude is None

        # 5. Global bypass: --no-persistent-config
        args_bypass = argparse.Namespace(
            command="find",
            target="@fld-1",
            strip_header=None,
            with_header=False,
            exclude=None,
            no_exclude=False,
            session=None,
            no_persistent_config=True,
        )
        notices_bypass = apply_persistent_preferences(args_bypass)
        assert notices_bypass == []
        assert args_bypass.strip_header is None
        assert args_bypass.exclude is None


# ==============================================================================
# Feature 6: Multi-Session Independent Browser Instances
# ==============================================================================

def test_multi_session_cdp_port_and_path_derivation():
    """Verifies deterministic port allocation and distinct profile paths per session name."""
    default_port = LiveSessionManager.get_session_cdp_port("default")
    assert default_port == DEFAULT_CDP_PORT

    main_port = LiveSessionManager.get_session_cdp_port("main")
    assert main_port == DEFAULT_CDP_PORT

    session_a_port = LiveSessionManager.get_session_cdp_port("work_session")
    session_b_port = LiveSessionManager.get_session_cdp_port("research_session")

    assert session_a_port != DEFAULT_CDP_PORT
    assert session_b_port != DEFAULT_CDP_PORT
    assert session_a_port != session_b_port
    assert 9222 < session_a_port <= 9272
    assert 9222 < session_b_port <= 9272

    path_default = LiveSessionManager.get_session_file_path("default")
    path_custom = LiveSessionManager.get_session_file_path("work_session")
    assert "work_session" in path_custom
    assert path_default != path_custom


# ==============================================================================
# Feature 1: Container-Confined Read (wp read --selector <sel>)
# ==============================================================================

def test_container_confined_read_worker_handler():
    """Verifies handle_worker_read queries target selector and confines extraction."""
    from supervisor.worker_handlers import handle_worker_read

    mock_worker = MagicMock()
    mock_coord = MagicMock()
    mock_worker._ensure_session.return_value = mock_coord
    mock_page = MagicMock()
    mock_coord.page = mock_page
    mock_coord.adapter.browser_pid = 1234
    mock_coord.adapter.get_active_tab_index.return_value = 0
    mock_coord.adapter.list_open_tabs.return_value = []
    mock_coord.context.pages = [mock_page]
    mock_page.url = "https://example.com"
    mock_page.title.return_value = "Example Page"

    # Selector returns isolated container HTML and inner text
    mock_page.evaluate.return_value = {
        "html": "<main><h1>Article Title</h1><p>Confined content</p></main>",
        "text": "Article Title\nConfined content",
    }

    req = SupervisorActionRequest(
        action="read",
        selector="main",
    )

    resp = handle_worker_read(mock_worker, req)
    assert resp.success is True
    assert "Confined reading strictly to container element" in "\n".join(resp.output_lines)
    assert "Confined content" in resp.content


# ==============================================================================
# Feature 2: Pure Text Extraction (wp find <target> --text)
# ==============================================================================

def test_pure_text_extraction_cli(capsys):
    """Verifies wp find <target> --text prints pure innerText without HTML or telemetry banners."""
    from cli_commands.find_cmd import find_cmd

    args = argparse.Namespace(
        command="find",
        target="#contentBox",
        selector=None,
        url=None,
        cookies=None,
        tab=None,
        options=False,
        query=None,
        search=None,
        html=False,
        up=0,
        screenshot=None,
        headed=False,
        timeout_minutes=30,
        strip_header=False,
        standalone=False,
        session=None,
        text=True,
        json=False,
        max_chars=20000,
        upper_include=None,
        upper_exclude=None,
        include=None,
        exclude=None,
        lines=None,
        chars=None,
        raw=False,
        all_options=False,
    )

    mock_resp = SupervisorActionResponse(
        success=True,
        action="probe",
        field_details={
            "found": True,
            "id": "contentBox",
            "type": "element",
            "inner_text": "Pure visible text without any HTML tags or SVG",
            "text": "Pure visible text without any HTML tags or SVG",
            "outerHTML": "<div id='contentBox'><svg></svg>Pure visible text without any HTML tags or SVG</div>",
        },
    )

    with patch("cli_commands.find_cmd.get_supervisor_client") as mock_get_client:
        mock_client = MagicMock()
        mock_client.execute.return_value = mock_resp
        mock_get_client.return_value = mock_client

        find_cmd(args)

    captured = capsys.readouterr()
    assert "Pure visible text without any HTML tags or SVG" in captured.out
    assert "═" not in captured.out
    assert "TELEMETRY" not in captured.out
    assert "<svg>" not in captured.out


# ==============================================================================
# Feature 3: Explicit Wait Command (wp wait --selector <sel>)
# ==============================================================================

def test_wait_worker_handler_success():
    """Verifies OperationalWorker._handle_wait handles selector and network idle waits."""
    from supervisor.worker_process import OperationalWorker

    worker = OperationalWorker(headed=False)
    mock_coord = MagicMock()
    mock_page = MagicMock()
    mock_coord.page = mock_page
    mock_coord.context.pages = [mock_page]
    mock_coord.adapter.browser_pid = 5678
    mock_coord.adapter.get_active_tab_index.return_value = 0
    mock_coord.adapter.list_open_tabs.return_value = []
    mock_page.url = "https://example.com/ajax"
    mock_page.title.return_value = "AJAX Form"

    worker._ensure_session = MagicMock(return_value=mock_coord)

    req = SupervisorActionRequest(
        action="wait",
        selector="#dynamicResults",
        wait_timeout=5000,
        wait_state="visible",
        network_idle=True,
    )

    resp = worker._handle_wait(req)
    assert resp.success is True
    assert "Successfully waited for #dynamicResults" in resp.message
    mock_page.wait_for_load_state.assert_called_once_with("networkidle", timeout=5000)
    mock_page.wait_for_selector.assert_called_once_with("#dynamicResults", state="visible", timeout=5000)


def test_wait_cli_parser_and_dispatcher():
    """Verifies 'wp wait' subcommand parses all arguments correctly."""
    parser = build_cli_parser()
    parsed = parser.parse_args(["wait", "--selector", "#submitBtn", "--timeout", "3000", "--network-idle"])
    assert parsed.command == "wait"
    assert parsed.selector == "#submitBtn"
    assert parsed.timeout == 3000
    assert parsed.network_idle is True


# ==============================================================================
# Feature 4: Interactive Typeahead Dropdown Probe
# ==============================================================================

def test_interactive_ajax_typeahead_probe():
    """Verifies probe_field triggers sequential keystroke simulation and polls AJAX options."""
    from services.field_interaction_service import FieldInteractionService

    mock_page = MagicMock()
    svc = FieldInteractionService(mock_page)

    # Initial probe returns combobox with 0 initial DOM options
    mock_page.evaluate.side_effect = [
        # 1. Initial PROBE_FIELD_DOM_SCRIPT call
        {
            "found": True,
            "type": "combobox",
            "id": "countrySelect",
            "options": [],
            "options_count": 0,
            "trigger_button": "countryTrigger",
            "value": "",
        },
        # 2. AJAX options poll return
        [
            {"local_id": "@opt-1", "text": "Sudan", "value": "812004", "id": "opt-812004"},
            {"local_id": "@opt-2", "text": "South Sudan", "value": "812005", "id": "opt-812005"},
        ],
    ]

    mock_loc = MagicMock()
    mock_loc.count.return_value = 1
    mock_loc.first.is_visible.return_value = True
    mock_page.locator.return_value = mock_loc

    details = svc.probe_field(
        target="countrySelect",
        include_options=True,
        query="Sudan",
    )

    assert details is not None
    assert details.get("options_count") == 2
    opts = details.get("options")
    assert opts[0]["text"] == "Sudan"
    assert opts[0]["value"] == "812004"
    # Verify non-destructive escape key cleanup was issued
    mock_page.keyboard.press.assert_called_with("Escape")
