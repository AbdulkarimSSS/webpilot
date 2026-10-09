"""Unit and integration tests for Supervisor token security and HTTP authentication."""

import json
import os
import tempfile
import urllib.error
import urllib.request
import pytest
from http.server import HTTPServer
import threading

from supervisor.security import (
    generate_supervisor_token,
    save_supervisor_token,
    load_supervisor_token,
    remove_supervisor_token,
    validate_supervisor_token,
)
from supervisor.master_daemon import MasterSupervisor, create_supervisor_handler
from supervisor.client import SupervisorClient


def test_token_generation_and_validation():
    """Verify high entropy token generation and constant-time validation."""
    token = generate_supervisor_token()
    assert isinstance(token, str)
    assert len(token) == 64  # 32 bytes hex = 64 chars

    assert validate_supervisor_token(token, token) is True
    assert validate_supervisor_token(f"Bearer {token}", token) is True
    assert validate_supervisor_token("wrong-token", token) is False
    assert validate_supervisor_token(None, token) is False
    assert validate_supervisor_token("", token) is False


def test_token_file_save_and_load():
    """Verify saving token with strict permissions and loading it back."""
    with tempfile.TemporaryDirectory() as tmpdir:
        token_path = os.path.join(tmpdir, "test.token")
        token = generate_supervisor_token()

        saved_path = save_supervisor_token(token, path=token_path)
        assert os.path.isfile(saved_path)

        loaded = load_supervisor_token(path=token_path)
        assert loaded == token

        remove_supervisor_token(path=token_path)
        assert not os.path.isfile(token_path)


def test_supervisor_http_auth_enforcement():
    """Verify HTTP server rejects unauthenticated requests with 401 and accepts authorized ones."""
    test_token = "secret-test-token-12345"
    supervisor = MasterSupervisor(port=0, token=test_token)
    # Stop watchdog thread to keep test clean
    supervisor._is_running = False

    handler_cls = create_supervisor_handler(supervisor)
    server = HTTPServer(("127.0.0.1", 0), handler_cls)
    port = server.server_address[1]
    supervisor.port = port
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()

    try:
        # 1. Unauthenticated request -> Expect 401 Unauthorized
        req_unauth = urllib.request.Request(f"http://127.0.0.1:{port}/ping")
        with pytest.raises(urllib.error.HTTPError) as exc_info:
            urllib.request.urlopen(req_unauth, timeout=2)
        assert exc_info.value.code == 401

        # 2. Wrong token -> Expect 401 Unauthorized
        req_wrong = urllib.request.Request(
            f"http://127.0.0.1:{port}/ping",
            headers={"X-Supervisor-Token": "invalid-token"},
        )
        with pytest.raises(urllib.error.HTTPError) as exc_info:
            urllib.request.urlopen(req_wrong, timeout=2)
        assert exc_info.value.code == 401

        # 3. Non-ASCII token header -> Expect 401 Unauthorized (WP-005, must not raise 500)
        req_non_ascii = urllib.request.Request(
            f"http://127.0.0.1:{port}/ping",
            headers={"X-Supervisor-Token": "token\u1234".encode("utf-8")},
        )
        with pytest.raises(urllib.error.HTTPError) as exc_info:
            urllib.request.urlopen(req_non_ascii, timeout=2)
        assert exc_info.value.code == 401

        # 4. Valid token -> Expect 200 OK
        client_auth = SupervisorClient(base_url=f"http://127.0.0.1:{port}", token=test_token)
        assert client_auth.is_running() is True
        status = client_auth.get_status()
        assert status.get("supervisor_alive") is True
        assert status.get("supervisor_port") == port

    finally:
        server.shutdown()
        server.server_close()


def test_non_ascii_supervisor_token_validation():
    """Verify non-ASCII strings in validate_supervisor_token do not crash with TypeError (WP-005)."""
    assert validate_supervisor_token("token\u1234", "secret-token") is False
    assert validate_supervisor_token("secret-token", "token\u1234") is False
    assert validate_supervisor_token("token\u1234", "token\u1234") is True


def test_cli_token_argument_and_client_propagation():
    """Verify CLI --token flag parsing and propagation to SupervisorClient."""
    import argparse
    from cli import get_supervisor_client

    # 1. Custom token provided in args
    args_with_token = argparse.Namespace(host="127.0.0.1", port=9333, token="my-custom-token-xyz")
    client = get_supervisor_client(args_with_token)
    assert client.token == "my-custom-token-xyz"
    headers = client._get_headers()
    assert headers["X-Supervisor-Token"] == "my-custom-token-xyz"
    assert headers["Authorization"] == "Bearer my-custom-token-xyz"

    # 2. No token in args -> falls back to load_supervisor_token
    args_no_token = argparse.Namespace(host="127.0.0.1", port=9333, token=None)
    client_default = get_supervisor_client(args_no_token)
    assert client_default.base_url == "http://127.0.0.1:9333"
