"""High-level Pythonic Client for WebPilot Engine.

Provides an ergonomic programmatic interface for AI agents, automation pipelines,
and Python scripts to inspect web pages, populate complex forms with physical truth
verification, probe DOM elements, and manage multi-tab browser sessions.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional, Union

from supervisor.client import SupervisorClient
from supervisor.contracts import SupervisorActionRequest, SupervisorActionResponse


class WebPilot:
    """Primary programmatic Python interface for WebPilot Engine.

    Usage:
        from webpilot import WebPilot

        wp = WebPilot()

        # 1. Inspect a page schema
        schema = wp.inspect("https://example.com/form")

        # 2. Fill fields and submit with 0.0% false success physical verification
        res = wp.apply(
            url="https://example.com/form",
            fields={"First Name": "Alice", "Email": "alice@example.com"},
            press="Submit"
        )
        print("Success:", res.success)
        print("Confirmed fields:", res.confirmed_fields)

        # 3. Probe an element
        probe = wp.find("Country", options=True)
    """

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 9333,
        token: Optional[str] = None,
        headed: bool = False,
        timeout_minutes: int = 30,
    ):
        self.base_url = f"http://{host}:{port}"
        self.client = SupervisorClient(base_url=self.base_url, token=token)
        self.headed = headed
        self.timeout_minutes = timeout_minutes

    def inspect(
        self,
        url: Optional[str] = None,
        unpack_options: bool = False,
        tab: Optional[int] = None,
        cookies: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Inspects page inputs, selects, buttons, and uploads.

        Returns the structured schema dictionary.
        """
        req = SupervisorActionRequest(
            action="inspect",
            url=url,
            unpack_options=unpack_options,
            tab_index=tab,
            cookies_path=cookies,
            headed=self.headed,
            timeout_minutes=self.timeout_minutes,
        )
        resp = self.client.execute(req)
        if not resp.success:
            raise RuntimeError(f"Inspection failed: {resp.message}")
        return resp.schema or {}

    def apply(
        self,
        url: Optional[str] = None,
        fields: Optional[Dict[str, Any]] = None,
        press: Optional[Union[str, List[str]]] = None,
        upload: Optional[Union[str, List[str]]] = None,
        submit: bool = False,
        data_path: Optional[str] = None,
        cookies: Optional[str] = None,
        tab: Optional[int] = None,
        auto_inspect: bool = True,
    ) -> SupervisorActionResponse:
        """Fills form fields, uploads files, clicks buttons, and verifies physical DOM state.

        Returns SupervisorActionResponse detailing confirmed, unconfirmed, and failed fields.
        """
        fill_args: List[str] = []
        if fields:
            from common.secrets import resolve_secret_value
            for k, v in fields.items():
                resolved_v = resolve_secret_value(v, prompt_label=str(k))
                fill_args.append(f"{k}={resolved_v}")

        press_args: List[str] = []
        if press:
            if isinstance(press, str):
                press_args.append(press)
            else:
                press_args.extend(press)

        upload_args: List[str] = []
        if upload:
            if isinstance(upload, str):
                upload_args.append(upload)
            else:
                upload_args.extend(upload)

        req = SupervisorActionRequest(
            action="apply",
            url=url,
            data_path=data_path,
            fill_arguments=fill_args,
            press_buttons=press_args,
            upload_files=upload_args,
            cookies_path=cookies,
            submit=submit,
            tab_index=tab,
            headed=self.headed,
            auto_inspect=auto_inspect,
            timeout_minutes=self.timeout_minutes,
        )
        return self.client.execute(req)

    def find(
        self,
        target: Optional[str] = None,
        url: Optional[str] = None,
        options: bool = True,
        query: Optional[str] = None,
        html: bool = False,
        up: int = 0,
        screenshot: Optional[str] = None,
        tab: Optional[int] = None,
        selector: Optional[str] = None,
    ) -> SupervisorActionResponse:
        """Probes a specific field/element and returns its options, attributes, ancestor HTML, or visual crop."""
        effective_target = target or selector or ""
        req = SupervisorActionRequest(
            action="probe",
            url=url,
            target_field=effective_target,
            selector=selector,
            include_options=options,
            include_html=html or (up > 0),
            up_levels=up,
            screenshot_path=screenshot,
            query=query,
            tab_index=tab,
            headed=self.headed,
            timeout_minutes=self.timeout_minutes,
        )
        return self.client.execute(req)

    def click(
        self,
        button_text: str,
        url: Optional[str] = None,
        tab: Optional[int] = None,
    ) -> SupervisorActionResponse:
        """Clicks a button or interactive element."""
        return self.apply(url=url, press=[button_text], tab=tab, auto_inspect=False)

    def eval(
        self,
        script: str,
        args: Optional[Any] = None,
        url: Optional[str] = None,
        tab: Optional[int] = None,
    ) -> Any:
        """Executes arbitrary JavaScript expression in the active page and returns result."""
        req = SupervisorActionRequest(
            action="eval",
            url=url,
            script=script,
            script_args=args,
            tab_index=tab,
            headed=self.headed,
            timeout_minutes=self.timeout_minutes,
        )
        resp = self.client.execute(req)
        if not resp.success:
            raise RuntimeError(f"JavaScript evaluation failed: {resp.message}")
        return (resp.reactive_event or {}).get("result")

    def js(self, script: str, **kwargs: Any) -> Any:
        """Alias for eval()."""
        return self.eval(script, **kwargs)

    def css(
        self,
        target_or_rules: str,
        selector: Optional[str] = None,
        prop: Optional[str] = None,
        url: Optional[str] = None,
        tab: Optional[int] = None,
    ) -> SupervisorActionResponse:
        """Injects custom CSS styles or inspects computed styles of an element."""
        req = SupervisorActionRequest(
            action="css",
            url=url,
            script=target_or_rules,
            selector=selector,
            query=prop,
            tab_index=tab,
            headed=self.headed,
            timeout_minutes=self.timeout_minutes,
        )
        return self.client.execute(req)

    def new_tab(self, url: Optional[str] = None) -> Dict[str, Any]:
        """Spawns a new browser tab in the active session, optionally navigating to url."""
        req = SupervisorActionRequest(action="new_tab", url=url)
        resp = self.client.execute(req)
        if not resp.success:
            raise RuntimeError(f"Failed to create new tab: {resp.message}")
        return {
            "index": resp.active_tab_index,
            "url": resp.active_url,
            "title": resp.active_title,
            "total_tabs": resp.total_tabs,
            "tabs": resp.tabs,
        }

    def close_tab(self, index: Optional[int] = None) -> bool:
        """Closes the tab at index (or active tab if omitted)."""
        req = SupervisorActionRequest(action="close_tab", tab_index=index)
        resp = self.client.execute(req)
        return bool(resp.success)

    def switch_tab(self, index: int) -> bool:
        """Switches the active tab context by 0-based index."""
        req = SupervisorActionRequest(action="switch_tab", tab_index=index)
        resp = self.client.execute(req)
        return bool(resp.success)

    def list_tabs(self) -> List[Dict[str, Any]]:
        """Returns list of open browser tabs in the active session."""
        req = SupervisorActionRequest(action="list_tabs")
        resp = self.client.execute(req)
        return resp.tabs

    def service_status(self) -> Dict[str, Any]:
        """Queries the status of Layer 1 Supervisor and Layer 2 Worker."""
        return self.client.get_status()

    def service_restart(self) -> bool:
        """Restarts the Layer 2 Worker process cleanly."""
        return self.client.restart_worker()

    def close(self) -> bool:
        """Terminates active browser session cleanly."""
        res = self.client.restart_worker()
        return bool(getattr(res, "success", res))

    def __enter__(self) -> WebPilot:
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()
