"""Tests verifying fixes for Adversarial Benchmark findings WPB-010 through WPB-015."""

import os
import subprocess
import sys
import pytest

from common.paths import validate_safe_url, ValidationError
from services.dom_verifier import DOMDataMatcher
from adapters.live_session_manager import LiveSessionManager


def test_wpb_010_cli_help_no_crash():
    """WPB-010: Verify CLI --help does not crash due to unescaped percent formats."""
    # Test top-level help
    cmd = [sys.executable, "cli.py", "--help"]
    res = subprocess.run(cmd, capture_output=True, text=True)
    assert res.returncode == 0, f"--help failed: {res.stderr}"
    assert "WebPilot" in res.stdout

    # Test 'read' subcommand help
    cmd_read = [sys.executable, "cli.py", "read", "--help"]
    res_read = subprocess.run(cmd_read, capture_output=True, text=True)
    assert res_read.returncode == 0, f"read --help failed: {res_read.stderr}"
    assert "read" in res_read.stdout


def test_wpb_011_maxlength_enforcement_and_verification():
    """WPB-011: Verify maxlength constraints are independently validated and over-long values rejected."""
    # 1. If DOM readback reports a value exceeding max_length, verification MUST fail
    bypassed_readback = {
        "found": True,
        "type": "input",
        "value": "ABCDEFGH",
        "max_length": 5,
        "is_invalid": False,
    }
    # It must NOT confirm
    assert not DOMDataMatcher.match(bypassed_readback, "ABCDEFGH")

    # 2. If requested value was "ABCDEFGH", but physical input clamped to "ABCDE" (max_length 5)
    clamped_readback = {
        "found": True,
        "type": "input",
        "value": "ABCDE",
        "max_length": 5,
        "is_invalid": False,
    }
    # WP-101: Clamped/truncated value does NOT verify against over-long requested string
    assert not DOMDataMatcher.match(clamped_readback, "ABCDEFGH")
    assert DOMDataMatcher.match(clamped_readback, "ABCDE")


def test_wpb_012_ssrf_protection_matrix():
    """WPB-012: Verify SSRF attacks across encodings, aliases, and IPv6 mappings are blocked."""
    bypasses = [
        "http://2852039166/latest/meta-data/",            # decimal 169.254.169.254
        "http://0xA9FEA9FE/latest/meta-data/",            # hex 169.254.169.254
        "http://0177.0.0.1/",                             # octal loopback
        "http://169.254.169.254.nip.io/latest/meta-data/",# DNS alias -> metadata IP
        "http://metadata.google.internal./x",             # trailing dot
        "http://[::ffff:169.254.169.254]/",               # IPv4-mapped IPv6
        "http://[fd00:ec2::254]/",                        # AWS IMDSv6
        "http://127.0.0.1:8901/",                         # plain loopback
        "http://10.0.0.84:8901/",                         # RFC-1918 private
    ]

    for url in bypasses:
        with pytest.raises(ValidationError):
            validate_safe_url(url)

    # Valid public URLs must still be allowed
    assert validate_safe_url("http://example.com/test") == "http://example.com/test"
    assert validate_safe_url("https://github.com") == "https://github.com"


def test_wpb_012_ssrf_internal_override():
    """WPB-012: Verify WEBPILOT_ALLOW_INTERNAL_URLS allows local lab while still blocking cloud metadata."""
    os.environ["WEBPILOT_ALLOW_INTERNAL_URLS"] = "1"
    try:
        # Loopback and private IP allowed when env var is active
        assert validate_safe_url("http://127.0.0.1:8901/") == "http://127.0.0.1:8901/"
        assert validate_safe_url("http://10.0.0.84:8901/") == "http://10.0.0.84:8901/"

        # Cloud metadata must STILL be blocked even with internal URLs allowed
        with pytest.raises(ValidationError):
            validate_safe_url("http://169.254.169.254/")
        with pytest.raises(ValidationError):
            validate_safe_url("http://0xA9FEA9FE/latest/meta-data/")
        with pytest.raises(ValidationError):
            validate_safe_url("http://[fd00:ec2::254]/")
    finally:
        os.environ.pop("WEBPILOT_ALLOW_INTERNAL_URLS", None)


def test_wpb_013_profile_cleanup_routine(tmp_path):
    """WPB-013: Verify temp profile cleanup routine correctly deletes orphaned directories."""
    import tempfile
    tmp_dir = tempfile.gettempdir()
    fake_profile = os.path.join(tmp_dir, "playwright_chromiumdev_profile-test12345")
    os.makedirs(fake_profile, exist_ok=True)
    with open(os.path.join(fake_profile, "test.txt"), "w") as f:
        f.write("test")

    assert os.path.exists(fake_profile)
    cleaned = LiveSessionManager.cleanup_temp_profiles(max_age_seconds=0)
    assert not os.path.exists(fake_profile)
    assert cleaned >= 1


def test_wpb_015_aria_radio_group_verification():
    """WPB-015: Verify ARIA custom radio group readback confirms state correctly."""
    radio_group_actual = {
        "found": True,
        "type": "radio_group",
        "value": "Pro",
        "is_invalid": False,
    }
    assert DOMDataMatcher.match(radio_group_actual, "Pro")
    assert not DOMDataMatcher.match(radio_group_actual, "Basic")
