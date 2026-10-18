"""HTTP request handling, authentication validation, and DNS rebinding protection."""

from __future__ import annotations

import json
import os
import threading
from http.server import BaseHTTPRequestHandler
from typing import TYPE_CHECKING, Any, Dict, Type

from supervisor.contracts import SupervisorActionRequest
from supervisor.security import validate_supervisor_token

if TYPE_CHECKING:
    from supervisor.master_daemon import MasterSupervisor


def create_supervisor_handler(supervisor: MasterSupervisor) -> Type[BaseHTTPRequestHandler]:
    """Factory creating an HTTP Request Handler bound to the supervisor instance."""

    class SupervisorHTTPHandler(BaseHTTPRequestHandler):
        def log_message(self, format, *args):
            # Suppress default stdout HTTP access logs
            return

        def _send_json(self, status_code: int, data: Dict[str, Any]):
            body = json.dumps(data, ensure_ascii=False).encode("utf-8")
            self.send_response(status_code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _check_host(self) -> bool:
            """Validates incoming Host header to protect against DNS rebinding attacks."""
            headers = getattr(self, "headers", None)
            host = headers.get("Host") if headers is not None else None
            if not host:
                if hasattr(self, "_send_json") and hasattr(self, "wfile"):
                    try:
                        self._send_json(
                            400,
                            {
                                "success": False,
                                "error": "Bad Request: Missing Host header.",
                            },
                        )
                    except Exception:
                        pass
                return False
            host_clean = host.split(":")[0].strip().lower()
            if host_clean in ("127.0.0.1", "localhost", "::1"):
                return True
            if hasattr(self, "_send_json") and hasattr(self, "wfile"):
                try:
                    self._send_json(
                        403,
                        {
                            "success": False,
                            "error": f"Forbidden: Host '{host}' is rejected by DNS rebinding defense.",
                        },
                    )
                except Exception:
                    pass
            return False

        def _authenticate(self) -> bool:
            """Validates incoming HTTP request against the supervisor's secure token."""
            if not self._check_host():
                return False

            header_token = self.headers.get("X-Supervisor-Token") or self.headers.get("Authorization")
            try:
                is_valid = validate_supervisor_token(header_token, supervisor.token)
            except Exception:
                is_valid = False

            if not is_valid:
                self._send_json(
                    401,
                    {
                        "success": False,
                        "error": "Unauthorized: Invalid or missing supervisor authentication token.",
                    },
                )
                return False
            return True

        def do_GET(self):
            if not self._authenticate():
                return

            if self.path == "/ping":
                self._send_json(200, {"status": "ok", "supervisor_pid": os.getpid()})
            elif self.path == "/status":
                status = supervisor.get_status()
                self._send_json(200, status)
            else:
                self._send_json(404, {"error": "Not Found"})

        def do_POST(self):
            if not self._authenticate():
                return

            MAX_BODY_BYTES = 10 * 1024 * 1024  # 10 MB limit
            try:
                content_length = int(self.headers.get("Content-Length", 0))
            except (ValueError, TypeError):
                self._send_json(400, {"error": "Invalid Content-Length header"})
                return

            if content_length < 0 or content_length > MAX_BODY_BYTES:
                self._send_json(413, {"error": f"Payload Too Large or invalid (max {MAX_BODY_BYTES} bytes)"})
                return

            raw_body = self.rfile.read(content_length).decode("utf-8") if content_length > 0 else "{}"

            try:
                data = json.loads(raw_body)
                if not isinstance(data, dict):
                    self._send_json(400, {"error": "Malformed JSON payload: body must be a JSON object"})
                    return
            except Exception as exc:
                self._send_json(400, {"error": f"Malformed JSON payload: {exc}"})
                return

            if self.path == "/execute":
                req = SupervisorActionRequest.from_dict(data)
                try:
                    res = supervisor.execute_action(req)
                except Exception as ex:
                    res = SupervisorActionResponse(
                        success=False,
                        action=req.action,
                        message=f"Supervisor execution failed: {ex}",
                    )
                self._send_json(200, res.to_dict())
            elif self.path == "/restart":
                res = supervisor.restart_worker()
                self._send_json(200, res.to_dict())
            elif self.path == "/stop":
                req = SupervisorActionRequest(action="stop")
                res = supervisor.execute_action(req)
                self._send_json(200, res.to_dict())
                # Schedule daemon shutdown in background thread
                threading.Thread(target=self.server.shutdown, daemon=True).start()
            else:
                self._send_json(404, {"error": "Not Found"})

    return SupervisorHTTPHandler
