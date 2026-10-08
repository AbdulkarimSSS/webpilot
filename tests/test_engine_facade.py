"""Tests for UniversalFormEngine facade backwards compatibility and orchestration."""

from config.settings import get_settings, load_device_profile, reset_settings_cache
from engine import UniversalFormEngine
from models import DeviceProfile


def setup_function():
    reset_settings_cache()


def test_engine_facade_initialization_defaults():
    engine = UniversalFormEngine(headless=True)
    assert engine.headless is True
    assert engine.settings is not None
    assert engine.device_profile is not None
    assert engine.browser_adapter is not None
    assert engine.browser is None
    assert engine.context is None
    assert engine.page is None


def test_engine_facade_custom_profile_and_viewport():
    profile = DeviceProfile(
        device_name="Custom Profile",
        user_agent="FacadeTestAgent/1.0",
        viewport_width=1280,
        viewport_height=720,
    )
    engine = UniversalFormEngine(
        headless=True,
        device_profile=profile,
        viewport={"width": 1920, "height": 1080},
        user_agent="OverrideAgent/2.0",
    )
    assert engine.user_agent == "OverrideAgent/2.0"
    assert engine.viewport == {"width": 1920, "height": 1080}
    assert engine.device_profile.viewport_width == 1920


def test_format_inspection_summary_facade():
    engine = UniversalFormEngine(headless=True)
    data = {
        "title": "Test Form",
        "url": "https://test.local",
        "sections": [],
        "inputs": [],
        "dropdowns": [],
        "choices": [],
        "file_uploads": [],
        "already_uploaded_files": [],
        "buttons": [],
    }
    summary = engine.format_inspection_summary(data)
    assert "=== FORM INSPECTION SUMMARY: 'Test Form' ===" in summary
