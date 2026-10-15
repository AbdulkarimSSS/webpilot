"""Adversarial hypothesis verification tests (M1-M19, H4.1, H4.2).

Ensures complete truth barrier integrity, IPC isolation, process safety,
secret preservation, and structured error reporting.
"""

import json
import os
import sys
import unittest
from unittest.mock import MagicMock, patch

from common.paths import validate_safe_path
from common.secrets import parse_and_resolve_fill_args, resolve_secret_value
from core.exceptions import ValidationError
from core.models import ApplyExecutionResult
from mcp_tools import execute_inspect
from supervisor.client import SupervisorClient, _client_log
from supervisor.contracts import SupervisorActionResponse
from webpilot.client import WebPilot


class TestAdversarialHypotheses(unittest.TestCase):
    """Verifies remediation of adversarial defects."""

    def test_m1_unrelated_process_holding_port_not_killed(self):
        """M1: ensure_running() raises RuntimeError instead of killing an unrelated Python process."""
        client = SupervisorClient(base_url="http://127.0.0.1:9333")
        with patch.object(client, "is_running", return_value=False), \
             patch.object(client, "_find_pid_by_port", return_value=99999), \
             patch("subprocess.check_output", return_value="python3 -m http.server 9333"):
            with self.assertRaises(RuntimeError) as ctx:
                client.ensure_running()
            self.assertIn("occupied by an unrelated process", str(ctx.exception))

    def test_m3_m17_auth_401_does_not_kill_daemon(self):
        """M3 & M17: ensure_running() does not kill an active daemon on 401 Unauthorized."""
        client = SupervisorClient(base_url="http://127.0.0.1:9333")
        client._last_auth_error = True
        with patch.object(client, "is_running", return_value=False):
            with self.assertRaises(RuntimeError) as ctx:
                client.ensure_running()
            self.assertIn("HTTP 401 Unauthorized", str(ctx.exception))

    def test_m2_client_log_redirects_to_stderr_in_mcp_mode(self):
        """M2: _client_log writes to stderr when WEBPILOT_NO_STDIN is set."""
        with patch.dict(os.environ, {"WEBPILOT_NO_STDIN": "1"}):
            with patch("sys.stderr.write") as mock_stderr, patch("builtins.print") as mock_print:
                _client_log("[*] Testing stderr diversion")
                mock_stderr.assert_called_once_with("[*] Testing stderr diversion\n")
                mock_print.assert_not_called()

    def test_m8_literal_hyphen_not_treated_as_stdin(self):
        """M8: Literal '-' in form fields is preserved and not hijacked as @stdin."""
        val = resolve_secret_value("-")
        self.assertEqual(val, "-")

    def test_m8_unicode_escapes_not_mangled_in_field_values(self):
        """M8: Raw field values containing backslashes or \\u are not mangled."""
        pairs = parse_and_resolve_fill_args([r"file_path=C:\users\test\alpha", r"pass=sec\u1234ret"])
        self.assertEqual(pairs, [("file_path", r"C:\users\test\alpha"), ("pass", r"sec\u1234ret")])

    def test_m11_sensitive_paths_denylist(self):
        """M11: Access to ~/.webpilot, .aws, and /etc/passwd is rejected."""
        with self.assertRaises(ValidationError):
            validate_safe_path("~/.webpilot/supervisor.token")
        with self.assertRaises(ValidationError):
            validate_safe_path("/etc/passwd")
        with self.assertRaises(ValidationError):
            validate_safe_path("~/.aws/credentials")

    def test_m6_apply_execution_result_overall_success(self):
        """M6 & M9: ApplyExecutionResult.overall_success enforces strict honesty contract."""
        res_success = ApplyExecutionResult(
            confirmed_fields=[("A", "1")],
            unconfirmed_fields=[],
            failed_fields=[],
            validation_errors=[],
        )
        self.assertTrue(res_success.overall_success)

        res_failed = ApplyExecutionResult(
            confirmed_fields=[("A", "1")],
            unconfirmed_fields=[],
            failed_fields=[("B", "2")],
            validation_errors=[],
        )
        self.assertFalse(res_failed.overall_success)

        res_val_error = ApplyExecutionResult(
            confirmed_fields=[("A", "1")],
            unconfirmed_fields=[],
            failed_fields=[],
            validation_errors=["Validation check failure: timeout"],
        )
        self.assertFalse(res_val_error.overall_success)

    def test_m13_mcp_inspect_error_format(self):
        """M13: MCP execute_inspect returns structured JSON with success: False on failure."""
        mock_client = MagicMock()
        mock_client.execute.return_value = SupervisorActionResponse(
            success=False,
            action="inspect",
            message="Connection refused to browser",
        )
        out = execute_inspect(mock_client, url="https://example.com")
        parsed = json.loads(out)
        self.assertFalse(parsed["success"])
        self.assertEqual(parsed["status"], "error")
        self.assertIn("Connection refused", parsed["error"])

    def test_m14_sdk_eval_raises_on_failure_and_exit_closes(self):
        """M14: SDK eval raises RuntimeError on failure, close returns bool, __exit__ cleans up."""
        wp = WebPilot()
        wp.client = MagicMock()
        wp.client.execute.return_value = SupervisorActionResponse(
            success=False,
            action="eval",
            message="ReferenceError: foo is not defined",
        )
        with self.assertRaises(RuntimeError) as ctx:
            wp.eval("foo()")
        self.assertIn("JavaScript evaluation failed", str(ctx.exception))

        wp.client.restart_worker.return_value = SupervisorActionResponse(success=True, action="restart")
        self.assertTrue(wp.close())

        with patch.object(wp, "close") as mock_close:
            with wp as ctx_wp:
                self.assertIs(ctx_wp, wp)
            mock_close.assert_called_once()


    def test_wp009_whitespace_preserved_in_fill_args(self):
        """WP-009: Significant whitespace in fill values must be preserved."""
        from common.secrets import parse_and_resolve_fill_args
        res = parse_and_resolve_fill_args(["n=  spaces  "])
        self.assertEqual(res, [("n", "  spaces  ")])

    def test_wp004_empty_click_button_rejected(self):
        """WP-004: Empty button text returns error and does not click/submit."""
        from services.reactive_interaction_service import ReactiveInteractionService
        mock_page = MagicMock()
        mock_ctx = MagicMock()
        mock_insp = MagicMock()
        mock_val = MagicMock()
        svc = ReactiveInteractionService(mock_page, mock_ctx, mock_insp, mock_val)
        res = svc.click_button("")
        self.assertFalse(res["success"])
        self.assertIn("Empty button", res["message"])

        mock_client = MagicMock()
        from mcp_tools import execute_click_button
        mcp_res = json.loads(execute_click_button(mock_client, "   "))
        self.assertFalse(mcp_res["success"])
        self.assertEqual(mcp_res["status"], "error")
        mock_client.execute.assert_not_called()

    def test_wp010_empty_url_rejected(self):
        """WP-010: Explicit empty url returns error rather than inspecting/evaluating active page."""
        mock_client = MagicMock()
        mcp_res = json.loads(execute_inspect(mock_client, url=""))
        self.assertFalse(mcp_res["success"])
        self.assertEqual(mcp_res["status"], "error")
        self.assertIn("explicit empty URL", mcp_res["error"])
        mock_client.execute.assert_not_called()

    def test_wp003_eval_navigates_to_url(self):
        """WP-003: _handle_eval navigates when req.url is specified."""
        from supervisor.worker_process import OperationalWorker
        from supervisor.contracts import SupervisorActionRequest
        worker = OperationalWorker(headed=False)
        mock_coord = MagicMock()
        mock_coord.page.evaluate.return_value = "Test Title"
        mock_coord.page.url = "http://example.com/test"
        mock_coord.page.title.return_value = "Test Title"
        worker._ensure_session = MagicMock(return_value=mock_coord)

        req = SupervisorActionRequest(action="eval", script="document.title", url="http://example.com/test")
        resp = worker._handle_eval(req)
        self.assertTrue(resp.success)
        mock_coord.adapter.navigate.assert_called_once_with("http://example.com/test")

    def test_wp007_accept_downloads_enabled(self):
        """WP-007: BrowserContextEnvelopeBuilder sets accept_downloads=True."""
        from adapters.envelope_builder import BrowserContextEnvelopeBuilder
        builder = BrowserContextEnvelopeBuilder()
        envelope = builder.build_context_envelope()
        self.assertTrue(envelope.get("accept_downloads"))


if __name__ == "__main__":
    unittest.main()

