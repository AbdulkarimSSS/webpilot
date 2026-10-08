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
    supervisor = MasterSupervisor(port=9444, token=test_token)
    # Stop watchdog thread to keep test clean
    supervisor._is_running = False

    handler_cls = create_supervisor_handler(supervisor)
    server = HTTPServer(("127.0.0.1", 9444), handler_cls)
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()

    try:
        # 1. Unauthenticated request -> Expect 401 Unauthorized
        req_unauth = urllib.request.Request("http://127.0.0.1:9444/ping")
        with pytest.raises(urllib.error.HTTPError) as exc_info:
            urllib.request.urlopen(req_unauth, timeout=2)
        assert exc_info.value.code == 401

        # 2. Wrong token -> Expect 401 Unauthorized
        req_wrong = urllib.request.Request(
            "http://127.0.0.1:9444/ping",
            headers={"X-Supervisor-Token": "invalid-token"},
        )
        with pytest.raises(urllib.error.HTTPError) as exc_info:
            urllib.request.urlopen(req_wrong, timeout=2)
        assert exc_info.value.code == 401

        # 3. Valid token -> Expect 200 OK
        client_auth = SupervisorClient(base_url="http://127.0.0.1:9444", token=test_token)
        assert client_auth.is_running() is True
        status = client_auth.get_status()
        assert status.get("supervisor_alive") is True
        assert status.get("supervisor_port") == 9444

    finally:
        server.shutdown()
        server.server_close()
