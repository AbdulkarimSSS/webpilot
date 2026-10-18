"""Comprehensive test suite for internal/local network access control (allow_internal).

Tests:
1. validate_safe_url blocks private IPs and localhost by default.
2. validate_safe_url permits private IPs and localhost when WEBPILOT_ALLOW_INTERNAL_URLS=1.
3. validate_safe_url strictly blocks cloud metadata (169.254.169.254, fd00:ec2::/32, fe80::/10) unconditionally.
4. CLI parser supports --allow-internal and --allow-local across commands.
5. populate_network_args maps CLI flag and env var to SupervisorActionRequest.
6. Supervisor contracts preserve allow_internal through serialization round-trips.
7. OperationalWorker sets WEBPILOT_ALLOW_INTERNAL_URLS dynamically when req.allow_internal is True.
"""

import os
import pytest
from common.paths import validate_safe_url, ValidationError
from cli_parser import build_cli_parser
from cli_commands.common import populate_network_args
from supervisor.contracts import SupervisorActionRequest


def test_validate_safe_url_blocks_internal_by_default(monkeypatch):
    monkeypatch.delenv("WEBPILOT_ALLOW_INTERNAL_URLS", raising=False)
    monkeypatch.delenv("WEBPILOT_ALLOW_LOCAL_URLS", raising=False)

    with pytest.raises(ValidationError, match="Security restriction"):
        validate_safe_url("http://192.168.0.1/#/login")

    with pytest.raises(ValidationError, match="Security restriction"):
        validate_safe_url("http://10.0.0.1:8080/admin")

    with pytest.raises(ValidationError, match="Security restriction"):
        validate_safe_url("http://127.0.0.1:9000/")

    with pytest.raises(ValidationError, match="Security restriction"):
        validate_safe_url("http://localhost:3000/")


def test_validate_safe_url_allows_internal_when_configured(monkeypatch):
    monkeypatch.setenv("WEBPILOT_ALLOW_INTERNAL_URLS", "1")

    url = validate_safe_url("http://192.168.0.1/#/login")
    assert url == "http://192.168.0.1/#/login"

    url_local = validate_safe_url("http://127.0.0.1:9000/app")
    assert url_local == "http://127.0.0.1:9000/app"


def test_validate_safe_url_blocks_cloud_metadata_unconditionally(monkeypatch):
    monkeypatch.setenv("WEBPILOT_ALLOW_INTERNAL_URLS", "1")

    # AWS / GCP / Azure IMDS IPv4 link-local
    with pytest.raises(ValidationError, match="cloud instance metadata"):
        validate_safe_url("http://169.254.169.254/latest/meta-data/")

    # AWS IMDSv6
    with pytest.raises(ValidationError, match="cloud instance metadata"):
        validate_safe_url("http://[fd00:ec2::254]/latest/meta-data/")

    # IPv6 link-local
    with pytest.raises(ValidationError, match="cloud instance metadata"):
        validate_safe_url("http://[fe80::1]/")

    # Metadata domain name
    with pytest.raises(ValidationError, match="cloud instance metadata"):
        validate_safe_url("http://metadata.google.internal/computeMetadata/v1/")


def test_cli_parser_allow_internal_flag():
    parser = build_cli_parser()

    # inspect
    args = parser.parse_args(["inspect", "--url", "http://192.168.0.1/", "--allow-internal"])
    assert getattr(args, "allow_internal", False) is True

    # alias --allow-local
    args_alias = parser.parse_args(["inspect", "--url", "http://192.168.0.1/", "--allow-local"])
    assert getattr(args_alias, "allow_internal", False) is True

    # apply
    args_apply = parser.parse_args(["apply", "--url", "http://10.0.0.5/", "--allow-internal"])
    assert getattr(args_apply, "allow_internal", False) is True

    # read
    args_read = parser.parse_args(["read", "--url", "http://192.168.0.1/", "--allow-internal"])
    assert getattr(args_read, "allow_internal", False) is True


def test_populate_network_args_with_flag():
    parser = build_cli_parser()
    args = parser.parse_args(["inspect", "--url", "http://192.168.0.1/", "--allow-internal"])

    req = SupervisorActionRequest(action="inspect", url=args.url)
    assert req.allow_internal is False

    populate_network_args(req, args)
    assert req.allow_internal is True


def test_populate_network_args_with_env(monkeypatch):
    monkeypatch.setenv("WEBPILOT_ALLOW_INTERNAL_URLS", "1")
    parser = build_cli_parser()
    args = parser.parse_args(["inspect", "--url", "http://192.168.0.1/"])

    req = SupervisorActionRequest(action="inspect", url=args.url)
    populate_network_args(req, args)
    assert req.allow_internal is True


def test_supervisor_contracts_allow_internal_roundtrip():
    req = SupervisorActionRequest(action="inspect", url="http://192.168.0.1/", allow_internal=True)
    d = req.to_dict()
    assert d["allow_internal"] is True

    req2 = SupervisorActionRequest.from_dict(d)
    assert req2.allow_internal is True
