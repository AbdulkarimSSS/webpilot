"""Tool execution implementations for WebPilot MCP Server."""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from common.secrets import parse_and_resolve_fill_args
from supervisor.client import SupervisorClient
from supervisor.contracts import SupervisorActionRequest


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
    """Fills form fields via dictionary mapping."""
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
    output = {
        "success": resp.success,
        "message": resp.message,
        "active_url": resp.active_url,
        "confirmed_fields": resp.confirmed_fields,
        "unconfirmed_fields": resp.unconfirmed_fields,
        "failed_fields": resp.failed_fields,
        "validation_errors": resp.validation_errors,
        "logs": resp.output_lines,
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
        "logs": resp.output_lines,
    }
    return json.dumps(output, indent=2, ensure_ascii=False)


def execute_upload_file(
    client: SupervisorClient,
    field_name: str,
    file_path: str,
    screenshot_path: Optional[str] = None,
) -> str:
    """Uploads a file or document to a file input."""
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
            "logs": resp.output_lines,
        },
        indent=2,
        ensure_ascii=False,
    )


def execute_screenshot(
    client: SupervisorClient,
    output_path: str = "screenshot.png",
) -> str:
    """Captures a visual screenshot of active page."""
    req = SupervisorActionRequest(action="apply", screenshot_path=output_path)
    resp = client.execute(req)
    if resp.success:
        return f"Screenshot successfully captured and saved to '{output_path}'."
    return f"Failed to capture screenshot: {resp.message}"


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
    """Switches active focus to target tab index."""
    req = SupervisorActionRequest(action="switch_tab", tab_index=tab_index)
    resp = client.execute(req)
    return json.dumps(
        {
            "success": resp.success,
            "active_tab_index": resp.active_tab_index,
            "active_url": resp.active_url,
            "active_title": resp.active_title,
        },
        indent=2,
        ensure_ascii=False,
    )


def execute_save_cookies(
    client: SupervisorClient,
    output_path: str = "session_cookies.json",
) -> str:
    """Exports current session cookies to JSON file."""
    req = SupervisorActionRequest(action="apply", cookies_path=output_path)
    resp = client.execute(req)
    if resp.success:
        return f"Cookies saved successfully to '{output_path}'."
    return f"Failed to save cookies: {resp.message}"


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
