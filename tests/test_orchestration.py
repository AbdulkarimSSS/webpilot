"""Tests for Tier 2 Orchestration: contexts, SessionCoordinator, and FlowOrchestrator."""

from unittest.mock import MagicMock, patch
import pytest

from config.settings import Settings, get_settings
from core.models import DeviceProfile
from orchestration.context import (
    SessionContext,
    InspectionRequestContext,
    ApplyRequestContext,
    ApplyExecutionResult,
)
from orchestration.session_coordinator import SessionCoordinator
from orchestration.flow_orchestrator import FlowOrchestrator


def test_session_and_request_context_initialization():
    """Verify dataclasses initialize properly with expected defaults and types."""
    settings = get_settings()
    profile = DeviceProfile(
        device_name="Test Device",
        user_agent="TestAgent/1.0",
        viewport_width=1280,
        viewport_height=720,
    )

    session_ctx = SessionContext(
        settings=settings,
        device_profile=profile,
        headless=True,
        cookies_path="/path/to/cookies.json",
    )
    assert session_ctx.headless is True
    assert session_ctx.cookies_path == "/path/to/cookies.json"
    assert session_ctx.device_profile.device_name == "Test Device"

    insp_req = InspectionRequestContext(
        url="https://example.com/form",
        output_path="output.json",
        screenshot_path="shot.png",
        unpack_options=True,
    )
    assert insp_req.url == "https://example.com/form"
    assert insp_req.unpack_options is True
    assert insp_req.headed is False

    apply_req = ApplyRequestContext(
        url="https://example.com/form",
        fill_arguments=["name=John"],
        press_buttons=["Next"],
        upload_files=["cv=sample.pdf"],
        submit=True,
    )
    assert apply_req.url == "https://example.com/form"
    assert apply_req.fill_arguments == ["name=John"]
    assert apply_req.press_buttons == ["Next"]
    assert apply_req.submit is True


def test_session_coordinator_lifecycle():
    """Verify SessionCoordinator start, context management, cookie persistence, and stop."""
    settings = get_settings()
    profile = DeviceProfile(
        device_name="Mock Device",
        user_agent="MockAgent/1.0",
        viewport_width=1280,
        viewport_height=720,
    )
    session_ctx = SessionContext(
        settings=settings,
        device_profile=profile,
        headless=True,
        cookies_path="/tmp/fake_cookies.json",
    )

    with patch("orchestration.session_coordinator.BrowserAdapter") as mock_adapter_cls, \
         patch("orchestration.session_coordinator.save_cookies") as mock_save_cookies:
        
        mock_adapter = MagicMock()
        mock_ctx = MagicMock()
        mock_page = MagicMock()
        mock_ctx.cookies.return_value = [{"name": "sid", "value": "xyz123"}]
        mock_ctx.pages = [mock_page]
        mock_adapter.context = mock_ctx
        mock_adapter.page = mock_page
        mock_adapter_cls.return_value = mock_adapter

        coordinator = SessionCoordinator(session_ctx)
        with coordinator:
            assert coordinator.page == mock_page
            assert coordinator.context == mock_ctx
            mock_adapter.start.assert_called_once_with(cookies_path="/tmp/fake_cookies.json")

            # Test tab switching
            new_page = MagicMock()
            mock_ctx.pages.append(new_page)
            active_tab = coordinator.switch_to_latest_page()
            assert active_tab == new_page

        mock_save_cookies.assert_called_once_with("/tmp/fake_cookies.json", [{"name": "sid", "value": "xyz123"}])
        mock_adapter.stop.assert_called_once()


def test_flow_orchestrator_execute_inspection_flow(tmp_path):
    """Verify FlowOrchestrator inspection pipeline runs through services cleanly."""
    out_file = str(tmp_path / "inspect_out.json")
    shot_file = str(tmp_path / "inspect_shot.png")

    insp_req = InspectionRequestContext(
        url="https://jobs.example.com/apply",
        output_path=out_file,
        screenshot_path=shot_file,
    )

    fake_inspection_data = {
        "title": "Application Form",
        "url": "https://jobs.example.com/apply",
        "sections": ["Info"],
        "inputs": [],
        "dropdowns": [],
        "choices": [],
        "file_uploads": [],
        "already_uploaded_files": [],
        "buttons": [],
    }

    with patch("orchestration.flow_orchestrator.SessionCoordinator") as mock_coord_cls, \
         patch("orchestration.flow_orchestrator.AuthNavigationService") as mock_auth_cls, \
         patch("orchestration.flow_orchestrator.InspectionService") as mock_insp_cls, \
         patch("orchestration.flow_orchestrator.InspectionFormatterService") as mock_fmt_cls:

        mock_coord = MagicMock()
        mock_page = MagicMock()
        mock_ctx = MagicMock()
        mock_page.url = "https://jobs.example.com/apply"
        mock_page.locator.return_value.count.return_value = 0
        mock_coord.page = mock_page
        mock_coord.context = mock_ctx
        mock_coord.__enter__.return_value = mock_coord
        mock_coord_cls.return_value = mock_coord

        mock_insp_svc = MagicMock()
        mock_insp_svc.inspect.return_value = fake_inspection_data
        mock_insp_cls.return_value = mock_insp_svc

        mock_fmt_cls.format_summary.return_value = "Mock Summary"

        res = FlowOrchestrator.execute_inspection_flow(insp_req)

        assert res == fake_inspection_data
        mock_coord.adapter.navigate.assert_called_once_with("https://jobs.example.com/apply")
        mock_coord.adapter.capture_screenshot.assert_called_once_with(shot_file, full_page=True)
