"""Unit tests for secrets resolution (@env:VAR, @stdin, @file:PATH, and stdin JSON)."""

import io
import os
import tempfile
import pytest
from core.exceptions import ConfigurationError, ValidationError
from common.secrets import (
    resolve_secret_value,
    parse_and_resolve_fill_args,
    resolve_payload_secrets,
)
from builder import FormPayloadBuilder


def test_resolve_env_variable(monkeypatch):
    """Verify @env:VAR resolution from environment variables."""
    monkeypatch.setenv("TEST_APP_PASSWORD", "SuperSecret123!")
    resolved = resolve_secret_value("@env:TEST_APP_PASSWORD")
    assert resolved == "SuperSecret123!"

    # Missing env variable raises ConfigurationError
    with pytest.raises(ConfigurationError):
        resolve_secret_value("@env:NON_EXISTENT_VAR_xyz987")


def test_resolve_file_secret():
    """Verify @file:PATH resolution from local files."""
    with tempfile.NamedTemporaryFile("w+", delete=False, encoding="utf-8") as tmp:
        tmp.write("secret-file-content\n")
        tmp_path = tmp.name

    try:
        resolved = resolve_secret_value(f"@file:{tmp_path}")
        assert resolved == "secret-file-content"

        # Non-existent file raises ConfigurationError
        with pytest.raises(ConfigurationError):
            resolve_secret_value("@file:/non/existent/path.txt")
    finally:
        if os.path.isfile(tmp_path):
            os.remove(tmp_path)


def test_resolve_stdin_piped(monkeypatch):
    """Verify @stdin reads cleanly from standard input stream."""
    monkeypatch.setattr("sys.stdin", io.StringIO("piped-secret-value\n"))
    monkeypatch.setattr("sys.stdin.isatty", lambda: False)

    resolved = resolve_secret_value("@stdin")
    assert resolved == "piped-secret-value"


def test_parse_and_resolve_fill_args(monkeypatch):
    """Verify parse_and_resolve_fill_args correctly resolves mix of plain and secret args."""
    monkeypatch.setenv("LOGIN_PASS", "SecurePassword999")
    args = [
        "username=john_doe",
        "password=@env:LOGIN_PASS",
        "company=Acme Corp",
    ]
    parsed = parse_and_resolve_fill_args(args)
    assert parsed == [
        ("username", "john_doe"),
        ("password", "SecurePassword999"),
        ("company", "Acme Corp"),
    ]


def test_form_payload_builder_json_secrets(monkeypatch):
    """Verify FormPayloadBuilder.normalize_payload resolves @env secrets in dict/list payloads."""
    monkeypatch.setenv("DB_TOKEN", "db-token-abc")
    raw_payload = {
        "service": "postgres",
        "token": "@env:DB_TOKEN",
        "port": 5432,
    }
    normalized = FormPayloadBuilder.normalize_payload(raw_payload)
    mapping = dict(normalized)
    assert mapping["service"] == "postgres"
    assert mapping["token"] == "db-token-abc"
    assert mapping["port"] == 5432


def test_form_payload_builder_stdin_json(monkeypatch):
    """Verify FormPayloadBuilder.load_from_file('-') reads JSON from stdin."""
    json_content = '{"field1": "val1", "field2": "val2"}'
    monkeypatch.setattr("sys.stdin", io.StringIO(json_content))

    payload = FormPayloadBuilder.load_from_file("-")
    assert payload == [("field1", "val1"), ("field2", "val2")]
