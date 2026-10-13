"""Layer 2: Operational Worker Process.

Runs as a supervised subprocess of Master Supervisor (Layer 1).
Holds Playwright, Chromium browser, contexts, pages, and active session state.
Communicates via stdin/stdout JSON-RPC.
"""

from __future__ import annotations

import json
import os
import sys
from typing import Any, Dict, List, Optional, Tuple

# Ensure project root is on sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from config.settings import get_settings, load_device_profile
from orchestration.context import SessionContext
from orchestration.session_coordinator import SessionCoordinator
from services.field_interaction_service import FieldInteractionService
from services.form_application_pipeline import FormApplicationPipeline
from services.inspection_service import InspectionService
from services.page_lifecycle_service import PageLifecycleService
from services.reactive_interaction_service import ReactiveInteractionService
from services.schema_merger import SchemaMerger
from validators.form_validator import FormValidator
from supervisor.contracts import SupervisorActionRequest, SupervisorActionResponse
from supervisor.worker_handlers import (
    handle_worker_apply,
    handle_worker_inspect,
    handle_worker_probe,
)


class OperationalWorker:
    """Manages active Playwright runtime and executes form/browser automation tasks."""

    def __init__(self, headed: bool = False):
        self.settings = get_settings()
        self.headed = headed
        self.coordinator: Optional[SessionCoordinator] = None
        self.cached_schema: Optional[Dict[str, Any]] = None
        self.cached_url: Optional[str] = None

    def _merge_schemas(self, old_schema: Dict[str, Any], new_schema: Dict[str, Any]) -> Dict[str, Any]:
        """Performs a smart delta merge of two schemas from the same URL, preserving LocalIDs."""
        return SchemaMerger.merge(old_schema, new_schema)

    @staticmethod
    def _reverify_fields(
        field_svc: FieldInteractionService,
        confirmed: List[Tuple[str, Any]],
        unconfirmed: List[Tuple[str, Any]],
        lines: List[str],
        stage_name: str,
    ) -> List[Tuple[str, Any]]:
        """Re-verifies that previously confirmed fields have not been wiped or reverted."""
        return FormApplicationPipeline.reverify_fields(field_svc, confirmed, unconfirmed, lines, stage_name)

    def _ensure_session(self, req: SupervisorActionRequest) -> SessionCoordinator:
        """Initializes or returns active SessionCoordinator."""
        if (
            self.coordinator is None
            or self.coordinator.page is None
            or self.coordinator.page.is_closed()
        ):
            effective_cookies = req.cookies_path or self.settings.cookies_path
            session_ctx = SessionContext(
                settings=self.settings,
                device_profile=load_device_profile(),
                headless=not req.headed if req.headed else not self.headed,
                cookies_path=effective_cookies,
                keep_alive=False,
                close_session=False,
                timeout_minutes=req.timeout_minutes,
                tab_index=req.tab_index,
                strip_header=getattr(req, "strip_header", False),
            )
            self.coordinator = SessionCoordinator(session_ctx)
            self.coordinator.start()
        if self.coordinator and self.coordinator.adapter:
            self.coordinator.adapter.strip_header = getattr(req, "strip_header", False)
        return self.coordinator

    def handle_request(self, req: SupervisorActionRequest) -> SupervisorActionResponse:
        """Dispatches action to internal services and returns structured response."""
        action = req.action.lower().strip()

        try:
            if action in ("ping", "status"):
                return self._handle_status(req)

            elif action == "list_tabs":
                return self._handle_list_tabs(req)

            elif action == "switch_tab":
                return self._handle_switch_tab(req)

            elif action in ("inspect", "reload", "refresh"):
                if action in ("reload", "refresh"):
                    req.reload = True
                return self._handle_inspect(req)

            elif action in ("apply", "apply_reload"):
                if action == "apply_reload":
                    req.reload = True
                return self._handle_apply(req)

            elif action in ("probe", "find"):
                return self._handle_probe(req)

            elif action in ("eval", "js", "exec"):
                return self._handle_eval(req)

            elif action in ("css", "style"):
                return self._handle_css(req)

            elif action == "eval_py":
                return self._handle_eval_py(req)

            elif action in ("stop", "shutdown"):
                self.shutdown()
                return SupervisorActionResponse(
                    success=True,
                    action=action,
                    message="Operational Worker shut down cleanly.",
                )

            else:
                return SupervisorActionResponse(
                    success=False,
                    action=action,
                    message=f"Unknown action: '{action}'",
                )

        except Exception as exc:
            return SupervisorActionResponse(
                success=False,
                action=action,
                message=f"Error executing {action}: {exc}",
                output_lines=[f"[!] Worker exception: {exc}"],
            )

    def _handle_status(self, req: SupervisorActionRequest) -> SupervisorActionResponse:
        coord = self.coordinator
        if not coord or not coord.page:
            return SupervisorActionResponse(
                success=True,
                action="status",
                message="Worker is idle (no active browser yet).",
                worker_pid=os.getpid(),
                total_tabs=0,
            )

        adapter = coord.adapter
        return SupervisorActionResponse(
            success=True,
            action="status",
            message="Worker active with running browser.",
            browser_pid=adapter.browser_pid,
            worker_pid=os.getpid(),
            active_tab_index=adapter.get_active_tab_index(),
            active_url=coord.page.url if coord.page else "",
            active_title=coord.page.title() if coord.page else "",
            total_tabs=len(coord.context.pages) if coord.context else 0,
            tabs=adapter.list_open_tabs(),
        )

    def _handle_list_tabs(self, req: SupervisorActionRequest) -> SupervisorActionResponse:
        coord = self._ensure_session(req)
        adapter = coord.adapter
        tabs = adapter.list_open_tabs()
        return SupervisorActionResponse(
            success=True,
            action="list_tabs",
            message=f"Retrieved {len(tabs)} tabs.",
            browser_pid=adapter.browser_pid,
            worker_pid=os.getpid(),
            total_tabs=len(tabs),
            tabs=tabs,
            active_tab_index=adapter.get_active_tab_index(),
            active_url=coord.page.url if coord.page else "",
        )

    def _handle_switch_tab(self, req: SupervisorActionRequest) -> SupervisorActionResponse:
        coord = self._ensure_session(req)
        if req.tab_index is None:
            return SupervisorActionResponse(
                success=False,
                action="switch_tab",
                message="tab_index is required for switch_tab action.",
            )
        page = coord.switch_to_tab(req.tab_index)
        return SupervisorActionResponse(
            success=True,
            action="switch_tab",
            message=f"Switched to Tab #{req.tab_index}: '{page.title()}'",
            active_tab_index=req.tab_index,
            active_url=page.url,
            active_title=page.title(),
            total_tabs=len(coord.context.pages) if coord.context else 0,
        )

    def _handle_inspect(self, req: SupervisorActionRequest) -> SupervisorActionResponse:
        return handle_worker_inspect(self, req)

    def _handle_probe(self, req: SupervisorActionRequest) -> SupervisorActionResponse:
        return handle_worker_probe(self, req)

    def _handle_apply(self, req: SupervisorActionRequest) -> SupervisorActionResponse:
        return handle_worker_apply(self, req)

    def _handle_eval(self, req: SupervisorActionRequest) -> SupervisorActionResponse:
        coord = self._ensure_session(req)
        assert coord.page is not None
        try:
            res = coord.page.evaluate(req.script or "", req.script_args)
            return SupervisorActionResponse(
                success=True,
                action="eval",
                message="Evaluated successfully",
                reactive_event={"result": res},
                active_url=coord.page.url,
                active_title=coord.page.title(),
            )
        except Exception as exc:
            return SupervisorActionResponse(
                success=False,
                action="eval",
                message=str(exc),
                active_url=coord.page.url if coord.page else "",
                active_title=coord.page.title() if coord.page else "",
            )

    def _handle_eval_py(self, req: SupervisorActionRequest) -> SupervisorActionResponse:
        coord = self._ensure_session(req)
        assert coord.page is not None
        local_vars = {"page": coord.page, "context": coord.context, "coord": coord, "worker": self}
        try:
            exec(req.script or "", {}, local_vars)
            res = local_vars.get("result")
            return SupervisorActionResponse(
                success=True,
                action="eval_py",
                message="Python executed successfully",
                reactive_event={"result": res},
                active_url=coord.page.url,
                active_title=coord.page.title(),
            )
        except Exception as exc:
            import traceback
            tb = traceback.format_exc()
            return SupervisorActionResponse(
                success=False,
                action="eval_py",
                message=f"Error: {exc}\n{tb}",
                active_url=coord.page.url if coord.page else "",
                active_title=coord.page.title() if coord.page else "",
            )

    def _handle_css(self, req: SupervisorActionRequest) -> SupervisorActionResponse:
        coord = self._ensure_session(req)
        assert coord.page is not None
        if req.url:
            coord.adapter.navigate(req.url)
        css_content = (req.script or req.target_field or "").strip()
        selector = (req.selector or "").strip()
        prop_name = (req.query or "").strip()

        # Mode A: CSS Property Inspection or Modification on an element
        set_rules = str(req.script_args).strip() if req.script_args else ""
        if selector or (css_content and "{" not in css_content and ";" not in css_content):
            target_sel = selector or css_content
            try:
                from adapters.dom.universal_core import UNIVERSAL_DOM_CORE_JS
                js_inspect = UNIVERSAL_DOM_CORE_JS + """
                ([sel, propName, setRules]) => {
                    const el = deepQuerySelector(document, sel);
                    if (!el) return { found: false, error: "Element not found" };
                    if (setRules) {
                        el.style.cssText += ';' + setRules;
                        return { found: true, modified: true, selector: sel, set: setRules, style: el.style.cssText };
                    }
                    const style = window.getComputedStyle(el);
                    if (propName) {
                        return { found: true, selector: sel, property: propName, value: style.getPropertyValue(propName) || style[propName] || "" };
                    }
                    const keys = ['display', 'visibility', 'opacity', 'position', 'zIndex', 'pointerEvents', 'overflow', 'color', 'backgroundColor', 'width', 'height', 'top', 'left'];
                    const res = { found: true, selector: sel, properties: {} };
                    keys.forEach(k => { res.properties[k] = style[k] || style.getPropertyValue(k); });
                    return res;
                }
                """
                res = coord.page.evaluate(js_inspect, [target_sel, prop_name, set_rules])
                if not res.get("found"):
                    return SupervisorActionResponse(
                        success=False,
                        action="css",
                        message=f"Element not found for selector: '{target_sel}'",
                        active_url=coord.page.url,
                    )
                msg = f"Applied inline style on '{target_sel}': {set_rules}" if set_rules else f"Computed styles retrieved for '{target_sel}'"
                return SupervisorActionResponse(
                    success=True,
                    action="css",
                    message=msg,
                    reactive_event={"result": res},
                    active_url=coord.page.url,
                    active_title=coord.page.title(),
                )
            except Exception as exc:
                return SupervisorActionResponse(
                    success=False,
                    action="css",
                    message=f"Error inspecting CSS styles: {exc}",
                    active_url=coord.page.url,
                )

        # Mode B: CSS Injection
        try:
            coord.page.add_style_tag(content=css_content)
            return SupervisorActionResponse(
                success=True,
                action="css",
                message=f"Successfully injected CSS stylesheet ({len(css_content)} chars).",
                reactive_event={"injected": True, "length": len(css_content)},
                active_url=coord.page.url,
                active_title=coord.page.title(),
            )
        except Exception as exc:
            return SupervisorActionResponse(
                success=False,
                action="css",
                message=f"Failed to inject CSS: {exc}",
                active_url=coord.page.url,
            )

    def shutdown(self) -> None:
        """Terminates Playwright coordinator and all child browser tabs."""
        if self.coordinator:
            try:
                self.coordinator.close()
            except Exception:
                pass
            self.coordinator = None


def run_worker_loop():
    """Reads JSON requests from stdin, executes, writes JSON response to stdout."""
    rpc_out = sys.stdout
    # Redirect all print/logging to stderr to keep JSON-RPC channel strictly pure
    sys.stdout = sys.stderr

    worker = OperationalWorker(headed=False)

    while True:
        try:
            line = sys.stdin.readline()
            if not line:
                break

            line = line.strip()
            if not line:
                continue

            payload = json.loads(line)
            req = SupervisorActionRequest.from_dict(payload)
            resp = worker.handle_request(req)

            rpc_out.write(json.dumps(resp.to_dict()) + "\n")
            rpc_out.flush()

            if req.action.lower().strip() in ("stop", "shutdown"):
                break

        except Exception as exc:
            err_resp = SupervisorActionResponse(
                success=False,
                action="error",
                message=f"Worker loop fatal error: {exc}",
            )
            rpc_out.write(json.dumps(err_resp.to_dict()) + "\n")
            rpc_out.flush()


if __name__ == "__main__":
    run_worker_loop()
