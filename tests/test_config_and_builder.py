"""Unit and integration tests for Settings, DeviceProfile, and EnvelopeBuilder."""

import json
import os
import tempfile
import pytest

from exceptions import ConfigurationError, ValidationError
from models import DeviceProfile, ProxyConfig
from config.settings import (
    Settings,
    get_settings,
    load_device_profile,
    reset_settings_cache,
    parse_env_file,
    load_json_file,
    ValueResolver,
    DEFAULT_SETTINGS_JSON,
    DEFAULT_DEVICE_PROFILE_JSON,
)
from builder import BrowserContextEnvelopeBuilder, FormPayloadBuilder
from engine import UniversalFormEngine


def setup_function():
    """Reset settings cache before each test."""
    reset_settings_cache()


def test_settings_precedence_order():
    """Verify 3-tier precedence: os.environ > .env > JSON file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # 1. Create a dummy settings JSON file
        settings_file = os.path.join(tmpdir, "settings.json")
        with open(settings_file, "w", encoding="utf-8") as f:
            json.dump({
                "headless": True,
                "default_timeout_ms": 11111,
                "submission_wait_ms": 22222
            }, f)

        # 2. Create a dummy .env file
        env_file = os.path.join(tmpdir, ".env")
        with open(env_file, "w", encoding="utf-8") as f:
            f.write("APP_DEFAULT_TIMEOUT_MS=33333\n")
            f.write("APP_SUBMISSION_WAIT_MS=44444\n")

        # 3. Test tier 2 (.env overrides JSON)
        settings = get_settings(env_file=env_file, settings_json_path=settings_file, reload=True)
        assert settings.default_timeout_ms == 33333
        assert settings.submission_wait_ms == 44444
        assert settings.headless is True

        # 4. Test tier 1 (os.environ overrides .env and JSON)
        os.environ["APP_DEFAULT_TIMEOUT_MS"] = "99999"
        try:
            settings_env = get_settings(env_file=env_file, settings_json_path=settings_file, reload=True)
            assert settings_env.default_timeout_ms == 99999
            assert settings_env.submission_wait_ms == 44444  # Still from .env
        finally:
            del os.environ["APP_DEFAULT_TIMEOUT_MS"]


def test_device_profile_loading_and_env_override():
    """Verify DeviceProfile loads from JSON and supports environment variable overrides."""
    with tempfile.TemporaryDirectory() as tmpdir:
        profile_file = os.path.join(tmpdir, "device_profile.json")
        with open(profile_file, "w", encoding="utf-8") as f:
            json.dump({
                "device_name": "Test Emulated Browser",
                "user_agent": "CustomTestAgent/1.0",
                "viewport": {"width": 1280, "height": 720},
                "locale": "en-GB",
                "timezone_id": "Europe/London"
            }, f)

        # Base load
        profile = load_device_profile(profile_path=profile_file, reload=True)
        assert profile.device_name == "Test Emulated Browser"
        assert profile.user_agent == "CustomTestAgent/1.0"
        assert profile.viewport_width == 1280
        assert profile.viewport_height == 720
        assert profile.locale == "en-GB"
        assert profile.timezone_id == "Europe/London"

        # Override user agent and viewport via environment variable
        os.environ["DEVICE_USER_AGENT"] = "EnvOverrideAgent/2.0"
        os.environ["DEVICE_VIEWPORT_WIDTH"] = "1920"
        try:
            profile_overridden = load_device_profile(profile_path=profile_file, reload=True)
            assert profile_overridden.user_agent == "EnvOverrideAgent/2.0"
            assert profile_overridden.viewport_width == 1920
            assert profile_overridden.viewport_height == 720
        finally:
            del os.environ["DEVICE_USER_AGENT"]
            del os.environ["DEVICE_VIEWPORT_WIDTH"]


def test_envelope_builder_strictly_reads_model():
    """Verify BrowserContextEnvelopeBuilder produces exact envelope from DeviceProfile without hardcoded literals."""
    profile = DeviceProfile(
        device_name="Synthetic Profile",
        user_agent="StrictNoFallbackAgent/1.0",
        viewport_width=1600,
        viewport_height=900,
        device_scale_factor=1.5,
        is_mobile=False,
        has_touch=False,
        locale="fr-FR",
        timezone_id="Europe/Paris",
        geolocation_latitude=48.8566,
        geolocation_longitude=2.3522,
        geolocation_accuracy=5.0
    )

    builder = BrowserContextEnvelopeBuilder(profile=profile)
    envelope = builder.build_context_envelope()

    assert envelope["user_agent"] == "StrictNoFallbackAgent/1.0"
    assert envelope["viewport"] == {"width": 1600, "height": 900}
    assert envelope["device_scale_factor"] == 1.5
    assert envelope["locale"] == "fr-FR"
    assert envelope["timezone_id"] == "Europe/Paris"
    assert envelope["geolocation"] == {"latitude": 48.8566, "longitude": 2.3522, "accuracy": 5.0}


def test_envelope_builder_missing_attributes_fallback_or_error():
    """Verify that missing attributes in profile fall back to verified config or raise ConfigurationError."""
    # Profile with missing required user_agent
    incomplete_profile = DeviceProfile(
        device_name="Incomplete Profile",
        user_agent="",
        viewport_width=1000,
        viewport_height=800
    )

    # With default verified config file available, it should fall back to the verified config's user_agent
    builder = BrowserContextEnvelopeBuilder(profile=incomplete_profile)
    envelope = builder.build_context_envelope()
    assert envelope["user_agent"] != ""  # Successfully retrieved from verified config
    assert envelope["viewport"] == {"width": 1000, "height": 800}

    # With an empty non-existent config path, it must raise ConfigurationError
    invalid_profile = DeviceProfile(
        device_name="Invalid Profile",
        user_agent="",
        viewport_width=1000,
        viewport_height=800
    )
    failing_builder = BrowserContextEnvelopeBuilder(profile=invalid_profile, profile_path="non_existent.json")
    with pytest.raises(ConfigurationError):
        failing_builder.build_context_envelope()


def test_form_payload_builder():
    """Verify FormPayloadBuilder parses files and CLI fill arguments correctly."""
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
        json.dump({"field_a": "value_a", "field_b": 123}, f)
        temp_path = f.name

    try:
        loaded = FormPayloadBuilder.load_from_file(temp_path)
        assert ("field_a", "value_a") in loaded
        assert ("field_b", 123) in loaded

        # Test CLI args parsing
        cli_fields = FormPayloadBuilder.parse_cli_fill_arguments(["name=John Doe", "role=Engineer"])
        assert cli_fields == [("name", "John Doe"), ("role", "Engineer")]

        # Test invalid CLI format
        with pytest.raises(ValidationError):
            FormPayloadBuilder.parse_cli_fill_arguments(["invalid_entry_without_equals"])
    finally:
        os.remove(temp_path)


def test_universal_form_engine_initialization_with_settings():
    """Verify UniversalFormEngine receives and binds settings and device profile properly."""
    settings = get_settings(reload=True)
    profile = load_device_profile(reload=True)

    engine = UniversalFormEngine(headless=True, settings=settings, device_profile=profile)
    assert engine.settings is settings
    assert engine.device_profile is profile
    assert engine.headless is True
    assert engine.user_agent == profile.user_agent
    assert engine.viewport == profile.viewport_dict()
