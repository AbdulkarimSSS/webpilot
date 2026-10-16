"""Tool execution implementations for WebPilot MCP Server."""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from common.paths import validate_safe_path, validate_safe_url
from common.secrets import parse_and_resolve_fill_args
from core.exceptions import ValidationError
from supervisor.client import SupervisorClient
from supervisor.contracts import SupervisorActionRequest


def _truncate_echo(val: Any, max_len: int = 150) -> Any:
    """Truncates deeply nested strings to prevent response bloat (WPB-005)."""
    if isinstance(val, str) and len(val) > max_len:
        return f"{val[:max_len]}... [truncated {len(val)} chars]"
    if isinstance(val, dict):
        return {k: _truncate_echo(v, max_len) for k, v in val.items()}
    if isinstance(val, list):
        return [_truncate_echo(x, max_len) for x in val]
    if isinstance(val, tuple):
        return tuple(_truncate_echo(x, max_len) for x in val)
    return val


def execute_inspect(
    client: SupervisorClient,
    url: Optional[str] = None,
    unpack_options: bool = False,
    screenshot_path: Optional[str] = None,
    tab_index: Optional[int] = None,
) -> str:
    if url is not None and not url.strip():
        return json.dumps(
            {
                "success": False,
                "status": "error",
                "error": "Validation error: explicit empty URL is invalid.",
                "message": "Validation error: explicit empty URL is invalid.",
            },
            indent=2,
            ensure_ascii=False,
        )

    if url:
        try:
            url = validate_safe_url(url)
        except ValidationError as exc:
            return json.dumps(
                {
                    "success": False,
                    "status": "error",
                    "error": f"Validation error: {exc}",
                    "message": f"Validation error: {exc}",
                },
                indent=2,
                ensure_ascii=False,
            )

    req = SupervisorActionRequest(
        action="inspect",
        url=url,
        unpack_options=unpack_options,
        screenshot_path=screenshot_path,
        tab_index=tab_index,
    )
    resp = client.execute(req)
    if not resp.success:
        return json.dumps(
            {
                "success": False,
                "status": "error",
                "error": resp.message,
                "message": f"Error inspecting page: {resp.message}",
            },
            indent=2,
            ensure_ascii=False,
        )

    output = {
        "success": True,
        "status": "success",
        "active_url": resp.active_url,
        "active_title": resp.active_title,
        "active_tab": resp.active_tab_index,
        "total_tabs": resp.total_tabs,
        "schema": resp.schema,
        "message": resp.message,
    }
    return json.dumps(output, indent=2, ensure_ascii=False)


def execute_fill_form(
    client: SupervisorClient,
    fields: Dict[str, Any],
    url: Optional[str] = None,
    submit: bool = False,
    cookies_path: Optional[str] = None,
    screenshot_path: Optional[str] = None,
    tab_index: Optional[int] = None,
) -> str:
    """Fills form fields via dictionary mapping with response bloat protection."""
    if url:
        try:
            url = validate_safe_url(url)
        except ValidationError as exc:
            return json.dumps(
                {
                    "success": False,
                    "status": "error",
                    "error": f"Validation error: {exc}",
                    "message": f"Validation error: {exc}",
                },
                indent=2,
                ensure_ascii=False,
            )

    fill_args = [f"{k}={v}" for k, v in fields.items()]
    resolved_pairs = parse_and_resolve_fill_args(fill_args)
    effective_fill = [f"{k}={v}" for k, v in resolved_pairs]

    req = SupervisorActionRequest(
        action="apply",
        url=url,
        fill_arguments=effective_fill,
        submit=submit,
        cookies_path=cookies_path,
        screenshot_path=screenshot_path,
        tab_index=tab_index,
    )
    resp = client.execute(req)

    # Truncate echoed fields and logs to avoid multi-megabyte response bloat (WPB-005)
    output = {
        "success": resp.success,
        "message": resp.message,
        "active_url": resp.active_url,
        "confirmed_fields": _truncate_echo(resp.confirmed_fields),
        "unconfirmed_fields": _truncate_echo(resp.unconfirmed_fields),
        "failed_fields": _truncate_echo(resp.failed_fields),
        "validation_errors": _truncate_echo(resp.validation_errors),
        "logs": _truncate_echo(resp.output_lines),
    }
    return json.dumps(output, indent=2, ensure_ascii=False)


def execute_click_button(
    client: SupervisorClient,
    button_text: str,
    screenshot_path: Optional[str] = None,
    cookies_path: Optional[str] = None,
    tab_index: Optional[int] = None,
) -> str:
    if not button_text or not button_text.strip():
        return json.dumps(
            {
                "success": False,
                "status": "error",
                "error": "Validation error: button_text cannot be empty.",
                "message": "Validation error: button_text cannot be empty.",
            },
            indent=2,
            ensure_ascii=False,
        )

    req = SupervisorActionRequest(
        action="apply",
        press_buttons=[button_text],
        screenshot_path=screenshot_path,
        cookies_path=cookies_path,
        tab_index=tab_index,
    )
    resp = client.execute(req)
    output = {
        "success": resp.success,
        "message": resp.message,
        "active_url": resp.active_url,
        "active_title": resp.active_title,
        "active_tab": resp.active_tab_index,
        "total_tabs": resp.total_tabs,
        "logs": _truncate_echo(resp.output_lines),
    }
    return json.dumps(output, indent=2, ensure_ascii=False)


def execute_upload_file(
    client: SupervisorClient,
    field_name: str,
    file_path: str,
    screenshot_path: Optional[str] = None,
) -> str:
    """Uploads a file or document to a file input."""
    try:
        validate_safe_path(file_path, for_write=False)
    except ValidationError as exc:
        return json.dumps(
            {
                "success": False,
                "status": "error",
                "error": f"Validation error: {exc}",
                "message": f"Validation error: {exc}",
            },
            indent=2,
            ensure_ascii=False,
        )

    upload_arg = f"{field_name}={file_path}"
    req = SupervisorActionRequest(
        action="apply",
        upload_files=[upload_arg],
        screenshot_path=screenshot_path,
    )
    resp = client.execute(req)
    return json.dumps(
        {
            "success": resp.success,
            "message": resp.message,
            "logs": _truncate_echo(resp.output_lines),
        },
        indent=2,
        ensure_ascii=False,
    )


def execute_screenshot(
    client: SupervisorClient,
    output_path: str = "screenshot.png",
) -> str:
    """Captures a visual screenshot of active page with overwrite protection."""
    if not output_path or not output_path.strip():
        return "Failed to capture screenshot: output_path cannot be empty."

    try:
        validate_safe_path(output_path, for_write=True, allow_overwrite=False)
    except ValidationError as exc:
        return f"Failed to capture screenshot: {exc}"

    req = SupervisorActionRequest(action="apply", screenshot_path=output_path)
    resp = client.execute(req)
    screenshot_error = next(
        (line for line in (resp.output_lines or []) if "Failed to capture screenshot" in line or "[!] Failed" in line),
        None,
    )
    if resp.success and not screenshot_error:
        return f"Screenshot successfully captured and saved to '{output_path}'."
    err = screenshot_error or resp.message
    return f"Failed to capture screenshot: {err}"


def execute_list_tabs(client: SupervisorClient) -> str:
    """Lists all open tabs in active session."""
    req = SupervisorActionRequest(action="list_tabs")
    resp = client.execute(req)
    return json.dumps(
        {
            "success": resp.success,
            "active_tab": resp.active_tab_index,
            "total_tabs": resp.total_tabs,
            "tabs": resp.tabs,
        },
        indent=2,
        ensure_ascii=False,
    )


def execute_switch_tab(client: SupervisorClient, tab_index: int) -> str:
    """Switches active focus to target tab index with structured message."""
    req = SupervisorActionRequest(action="switch_tab", tab_index=tab_index)
    resp = client.execute(req)
    msg = resp.message
    if not msg:
        msg = f"Switched to tab {resp.active_tab_index}" if resp.success else f"Failed to switch tab: index {tab_index} out of range"
    return json.dumps(
        {
            "success": resp.success,
            "active_tab_index": resp.active_tab_index,
            "active_url": resp.active_url,
            "active_title": resp.active_title,
            "message": msg,
        },
        indent=2,
        ensure_ascii=False,
    )


def execute_save_cookies(
    client: SupervisorClient,
    output_path: str = "session_cookies.json",
) -> str:
    """Exports current session cookies to JSON file with honesty enforcement."""
    if not output_path or not output_path.strip():
        return "Failed to save cookies: output_path cannot be empty."

    try:
        validate_safe_path(output_path, for_write=True)
    except ValidationError as exc:
        return f"Failed to save cookies: {exc}"

    req = SupervisorActionRequest(action="apply", cookies_path=output_path)
    resp = client.execute(req)
    cookie_error = next(
        (line for line in (resp.output_lines or []) if "Failed to save cookies" in line or "Warning saving cookies" in line),
        None,
    )
    if not resp.success or cookie_error:
        err = cookie_error or resp.message or "Failed to write cookie file."
        return f"Failed to save cookies: {err}"

    return f"Cookies saved successfully to '{output_path}'."


def execute_service_status(client: SupervisorClient) -> str:
    """Returns operational status and telemetry of supervisor."""
    is_alive = client.is_running()
    if not is_alive:
        return json.dumps(
            {
                "status": "stopped",
                "message": "Master Supervisor is not currently running. It will auto-spawn upon the next tool call.",
            },
            indent=2,
        )

    req = SupervisorActionRequest(action="list_tabs")
    resp = client.execute(req)
    return json.dumps(
        {
            "status": "active",
            "layer1_supervisor_url": client.base_url,
            "layer2_worker_pid": resp.worker_pid,
            "layer3_chromium_pid": resp.browser_pid,
            "active_tab_index": resp.active_tab_index,
            "total_tabs": resp.total_tabs,
            "active_url": resp.active_url,
            "active_title": resp.active_title,
        },
        indent=2,
        ensure_ascii=False,
    )


def execute_service_restart(client: SupervisorClient) -> str:
    """Restarts supervisor worker tier."""
    resp = client.restart_worker()
    return json.dumps(
        {
            "success": resp.success,
            "message": resp.message,
            "new_worker_pid": resp.worker_pid,
        },
        indent=2,
    )


def execute_read_page(
    client: SupervisorClient,
    url: Optional[str] = None,
    output_path: Optional[str] = None,
    tab_index: Optional[int] = None,
) -> str:
    """Extracts ultra-dense clean markdown content from active or target page via Trafilatura."""
    if url is not None and not url.strip():
        return json.dumps(
            {
                "success": False,
                "status": "error",
                "error": "Validation error: explicit empty URL is invalid.",
                "message": "Validation error: explicit empty URL is invalid.",
            },
            indent=2,
            ensure_ascii=False,
        )

    if url:
        try:
            url = validate_safe_url(url)
        except ValidationError as exc:
            return json.dumps(
                {
                    "success": False,
                    "status": "error",
                    "error": f"Validation error: {exc}",
                    "message": f"Validation error: {exc}",
                },
                indent=2,
                ensure_ascii=False,
            )

    if output_path:
        try:
            validate_safe_path(output_path, for_write=True)
        except ValidationError as exc:
            return json.dumps(
                {
                    "success": False,
                    "status": "error",
                    "error": f"Validation error: {exc}",
                    "message": f"Validation error: {exc}",
                },
                indent=2,
                ensure_ascii=False,
            )

    req = SupervisorActionRequest(
        action="read",
        url=url,
        output_path=output_path,
        tab_index=tab_index,
    )
    resp = client.execute(req)
    if not resp.success:
        return json.dumps(
            {
                "success": False,
                "status": "error",
                "error": resp.message,
                "message": f"Error reading page: {resp.message}",
            },
            indent=2,
            ensure_ascii=False,
        )

    output = {
        "success": True,
        "status": "success",
        "active_url": resp.active_url,
        "active_title": resp.active_title,
        "active_tab": resp.active_tab_index,
        "total_tabs": resp.total_tabs,
        "content": resp.content or "",
        "message": resp.message,
    }
    return json.dumps(output, indent=2, ensure_ascii=False)

