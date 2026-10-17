"""Comprehensive unit and integration tests for WebPilot v2.7.3 features:
1. DNS-over-HTTPS (DoH) resolution & AdGuard defaults.
2. Console helpers injection for JavaScript eval ($ , $$, $x, $0, copy).
3. Network Traffic Manager (image blocking, pattern blocking, asset dump, HAR 1.2 export).
4. CLI argument parsing & persistent configuration flags.
"""

import json
import os
import tempfile
import pytest

from adapters.live_session_manager import LiveSessionManager
from adapters.network_interceptor import NetworkTrafficManager
from config.preferences import (
    load_preferences,
    save_preferences,
    apply_persistent_preferences,
)
from services.console_helpers import wrap_with_console_helpers, InvalidUserCodeError
from cli_parser import build_cli_parser


def test_doh_resolution_defaults():
    """Verify DoH resolution defaults to AdGuard DNS."""
    flags = LiveSessionManager.resolve_doh_args(enable_dns=True)
    assert "--enable-features=DnsOverHttps" in flags
    assert any(f.startswith("--dns-over-https-servers=") for f in flags)
    server_flag = [f for f in flags if f.startswith("--dns-over-https-servers=")][0]
    assert "https://dns.adguard.com/dns-query" in server_flag


def test_doh_resolution_disabled():
    """Verify --no-dns completely disables DoH flags."""
    flags = LiveSessionManager.resolve_doh_args(enable_dns=False)
    assert flags == []


def test_doh_resolution_custom_servers():
    """Verify custom comma and space separated DoH servers are correctly mapped."""
    custom = "https://dns.adguard.com/dns-query,https://adblock.doh.mullvad.net/dns-query"
    flags = LiveSessionManager.resolve_doh_args(enable_dns=True, custom_servers=custom)
    assert "--enable-features=DnsOverHttps" in flags
    server_flag = [f for f in flags if f.startswith("--dns-over-https-servers=")][0]
    # Chromium requires space-separated URLs in --dns-over-https-servers
    servers_val = server_flag.split("=", 1)[1]
    assert "https://dns.adguard.com/dns-query" in servers_val
    assert "https://adblock.doh.mullvad.net/dns-query" in servers_val
    assert " " in servers_val


def test_console_helpers_wrapping():
    """Verify wrap_with_console_helpers injects $, $$, $x, $0, and copy()."""
    code = "$('h1').innerText"
    wrapped = wrap_with_console_helpers(code)
    assert "const $ = (selector" in wrapped
    assert "const $$ = (selector" in wrapped
    assert "const $x = (xpath" in wrapped
    assert "const $0 =" in wrapped
    assert "const copy = (" in wrapped
    assert "$('h1').innerText" in wrapped
    assert wrapped.startswith("(() => {")
    assert wrapped.endswith("})()")


def test_console_helpers_empty_validation():
    """Verify invalid empty scripts raise InvalidUserCodeError."""
    with pytest.raises(InvalidUserCodeError):
        wrap_with_console_helpers("")
    with pytest.raises(InvalidUserCodeError):
        wrap_with_console_helpers("   ")
    with pytest.raises(InvalidUserCodeError):
        wrap_with_console_helpers(None)


def test_network_traffic_blocking_images():
    """Verify NetworkTrafficManager image blocking rules."""
    mgr = NetworkTrafficManager()
    mgr.configure_blocking(block_images=True)

    assert mgr.should_block_url("https://example.com/logo.png", "image") is True
    assert mgr.should_block_url("https://example.com/photo.jpg", "other") is True
    assert mgr.should_block_url("https://example.com/icon.svg?v=1", "other") is True
    assert mgr.should_block_url("https://example.com/api/user", "fetch") is False


def test_network_traffic_blocking_patterns():
    """Verify NetworkTrafficManager URL glob pattern blocking."""
    mgr = NetworkTrafficManager()
    mgr.configure_blocking(block_patterns=["*analytics*.js", "*/tracker/*"])

    assert mgr.should_block_url("https://cdn.example.com/google_analytics.js", "script") is True
    assert mgr.should_block_url("https://example.com/tracker/event", "xhr") is True
    assert mgr.should_block_url("https://example.com/app.js", "script") is False


def test_network_dump_and_har_export():
    """Verify asset dumping and HAR 1.2 exporting from captured traffic."""
    mgr = NetworkTrafficManager()
    mgr.sniff_active = True
    mgr.captured_traffic = [
        {
            "timestamp": "2026-10-17T20:00:00Z",
            "url": "https://example.com/scripts/vendor.js",
            "method": "GET",
            "resource_type": "script",
            "status": 200,
            "content_type": "application/javascript",
            "headers": {"content-type": "application/javascript"},
            "request_headers": {"accept": "*/*"},
            "post_data": None,
            "body": "console.log('vendor script loaded');",
        },
        {
            "timestamp": "2026-10-17T20:00:01Z",
            "url": "https://example.com/api/v1/user",
            "method": "GET",
            "resource_type": "fetch",
            "status": 200,
            "content_type": "application/json",
            "headers": {"content-type": "application/json"},
            "request_headers": {"accept": "application/json"},
            "post_data": None,
            "body": {"id": 123, "name": "Antigravity"},
        },
    ]

    with tempfile.TemporaryDirectory() as tmp_dir:
        # 1. Test dump JS assets
        js_dir = os.path.join(tmp_dir, "scripts")
        saved_js = mgr.dump_assets(output_dir=js_dir, types=["js"])
        assert len(saved_js) == 1
        assert saved_js[0].endswith(".js")
        with open(saved_js[0], "r", encoding="utf-8") as f:
            assert "vendor script loaded" in f.read()

        # 2. Test dump JSON API responses
        api_dir = os.path.join(tmp_dir, "api")
        saved_json = mgr.dump_assets(output_dir=api_dir, types=["json"], filter_pattern="/api/")
        assert len(saved_json) == 1
        assert saved_json[0].endswith(".json")
        with open(saved_json[0], "r", encoding="utf-8") as f:
            data = json.load(f)
            assert data["name"] == "Antigravity"

        # 3. Test HAR export
        har_file = os.path.join(tmp_dir, "test_session.har")
        export_path = mgr.export_har(har_file)
        assert os.path.isfile(export_path)
        with open(export_path, "r", encoding="utf-8") as f:
            har_data = json.load(f)
            assert har_data["log"]["version"] == "1.2"
            assert har_data["log"]["creator"]["name"] == "WebPilot Engine"
            assert len(har_data["log"]["entries"]) == 2
            assert har_data["log"]["entries"][0]["request"]["url"] == "https://example.com/scripts/vendor.js"
            assert har_data["log"]["entries"][1]["response"]["content"]["mimeType"] == "application/json"


def test_cli_parsing_new_commands():
    """Verify CLI parser parses sniff, dump, capture, block, and network subcommands."""
    parser = build_cli_parser()

    # sniff
    args = parser.parse_args(["sniff", "--types", "xhr,fetch", "--timeout", "5000"])
    assert args.command == "sniff"
    assert args.types == "xhr,fetch"
    assert args.timeout == 5000

    # dump
    args = parser.parse_args(["dump", "--types", "js", "-o", "./site_scripts/"])
    assert args.command == "dump"
    assert args.types == "js"
    assert args.output == "./site_scripts/"

    # capture
    args = parser.parse_args(["capture", "--filter", "/api/", "-o", "./api_data/"])
    assert args.command == "capture"
    assert args.filter_pattern == "/api/"
    assert args.output == "./api_data/"

    # block
    args = parser.parse_args(["block", "--pattern", "*analytics*.js", "--images"])
    assert args.command == "block"
    assert args.block_patterns == ["*analytics*.js"]
    assert args.images is True

    # network record
    args = parser.parse_args(["network", "record", "-o", "session.har"])
    assert args.command == "network"
    assert args.subaction == "record"
    assert args.output_path == "session.har"

    # inspect with --no-dns and --block-images
    args = parser.parse_args(["inspect", "--url", "https://example.com", "--no-dns", "--block-images"])
    assert args.command == "inspect"
    assert args.no_dns is True
    assert args.block_images is True
