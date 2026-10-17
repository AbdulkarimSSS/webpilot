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
    handle_worker_read,
)


def _sanitize_eval_result(val: Any, seen: Optional[set] = None, depth: int = 0) -> Any:
    """Sanitizes eval results to prevent infinite recursion on circular objects."""
    if depth > 15:
        return "[Max Depth]"
    if seen is None:
        seen = set()
    if val is None or isinstance(val, (int, float, bool, str)):
        return val
    val_id = id(val)
    if val_id in seen:
        return "[Circular]"
    seen.add(val_id)
    try:
        if isinstance(val, dict):
            return {str(k): _sanitize_eval_result(v, seen, depth + 1) for k, v in val.items()}
        elif isinstance(val, (list, tuple, set)):
            return [_sanitize_eval_result(item, seen, depth + 1) for item in val]
        elif hasattr(val, "__dict__"):
            return _sanitize_eval_result(val.__dict__, seen, depth + 1)
        else:
            return str(val)
    except (RecursionError, Exception):
        return "[Unserializable]"
    finally:
        seen.discard(val_id)


class OperationalWorker:
    """Manages active Playwright runtime and executes form/browser automation tasks."""

    def __init__(self, headed: bool = False):
        self.settings = get_settings()
        self.headed = headed
        self.coordinators: Dict[str, SessionCoordinator] = {}
        self.coordinator: Optional[SessionCoordinator] = None
        self.cached_schema: Optional[Dict[str, Any]] = None
        self.cached_url: Optional[str] = None

    def _merge_schemas(self, old_schema: Dict[str, Any], new_schema: Dict[str, Any]) -> Dict[str, Any]:
        """Performs a smart delta merge of two schemas from the same URL, preserving LocalIDs."""
        return SchemaMerger.merge(old_schema, new_schema)

    def _reverify_fields(
        self,
        field_svc: FieldInteractionService,
        confirmed: List[Tuple[str, Any]],
        unconfirmed: List[Tuple[str, Any]],
        lines: List[str],
        stage_name: str,
    ) -> List[Tuple[str, Any]]:
        """Re-verifies that previously confirmed fields have not been wiped or reverted."""
        return FormApplicationPipeline.reverify_fields(
            field_svc, confirmed, unconfirmed, lines, stage_name, cached_schema=self.cached_schema
        )

    def _ensure_session(self, req: SupervisorActionRequest) -> SessionCoordinator:
        """Initializes or returns active SessionCoordinator for the requested session."""
        session_name = getattr(req, "session_name", None) or "default"
        coord = self.coordinators.get(session_name)
        if (
            coord is None
            or coord.page is None
            or coord.page.is_closed()
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
                session_name=req.session_name,
            )
            coord = SessionCoordinator(session_ctx)
            coord.start()
            self.coordinators[session_name] = coord

        self.coordinator = coord
        if coord and coord.adapter:
            coord.adapter.strip_header = getattr(req, "strip_header", False)
        return coord

    def handle_request(self, req: SupervisorActionRequest) -> SupervisorActionResponse:
        """Dispatches action to internal services and returns structured response."""
        action = req.action.lower().strip()

        try:
            if action in ("ping", "status"):
                return self._handle_status(req)

            elif action in ("list_tabs", "tab_list", "tabs"):
                return self._handle_list_tabs(req)

            elif action in ("switch_tab", "tab_switch"):
                return self._handle_switch_tab(req)

            elif action in ("new_tab", "tab_new", "open_tab"):
                return self._handle_new_tab(req)

            elif action in ("close_tab", "tab_close"):
                return self._handle_close_tab(req)

            elif action in ("set_tab_timeout", "tab_timeout", "set_timeout"):
                return self._handle_set_tab_timeout(req)

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

            elif action in ("read", "clean_read", "content"):
                return self._handle_read(req)

            elif action in ("eval", "js", "exec"):
                return self._handle_eval(req)

            elif action in ("css", "style"):
                return self._handle_css(req)

            elif action in ("cookies", "cookie", "get_cookies", "dump_cookies", "export_cookies"):
                return self._handle_cookies(req)

            elif action in ("wait", "wait_for"):
                return self._handle_wait(req)

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

    def _handle_new_tab(self, req: SupervisorActionRequest) -> SupervisorActionResponse:
        coord = self._ensure_session(req)
        page = coord.create_new_tab(req.url, tab_timeout_minutes=req.tab_timeout)
        adapter = coord.adapter
        tabs = adapter.list_open_tabs()
        active_idx = adapter.get_active_tab_index()
        return SupervisorActionResponse(
            success=True,
            action="new_tab",
            message=f"Opened new tab #{active_idx}: '{page.title()}' ({page.url})",
            browser_pid=adapter.browser_pid,
            worker_pid=os.getpid(),
            active_tab_index=active_idx,
            active_url=page.url,
            active_title=page.title(),
            total_tabs=len(tabs),
            tabs=tabs,
        )

    def _handle_set_tab_timeout(self, req: SupervisorActionRequest) -> SupervisorActionResponse:
        coord = self._ensure_session(req)
        idx = req.tab_index if req.tab_index is not None else coord.adapter.get_active_tab_index()
        to_min = req.tab_timeout if req.tab_timeout is not None else 30
        ok = coord.set_tab_timeout(idx, to_min)
        if ok:
            return SupervisorActionResponse(
                success=True,
                action="set_tab_timeout",
                message=f"Set inactivity timeout for Tab #{idx} to {to_min} minutes.",
                active_tab_index=idx,
                tabs=coord.adapter.list_open_tabs(),
            )
        else:
            return SupervisorActionResponse(
                success=False,
                action="set_tab_timeout",
                message=f"Failed to set timeout for Tab #{idx}: index out of range.",
            )

    def _handle_close_tab(self, req: SupervisorActionRequest) -> SupervisorActionResponse:
        coord = self._ensure_session(req)
        target_idx = req.tab_index
        coord.close_tab(target_idx)
        adapter = coord.adapter
        tabs = adapter.list_open_tabs()
        active_idx = adapter.get_active_tab_index()
        page = coord.page
        return SupervisorActionResponse(
            success=True,
            action="close_tab",
            message=f"Closed tab{' #' + str(target_idx) if target_idx is not None else ''}. Active is now Tab #{active_idx}.",
            browser_pid=adapter.browser_pid,
            worker_pid=os.getpid(),
            active_tab_index=active_idx,
            active_url=page.url if page else "",
            active_title=page.title() if page else "",
            total_tabs=len(tabs),
            tabs=tabs,
        )

    def _handle_inspect(self, req: SupervisorActionRequest) -> SupervisorActionResponse:
        return handle_worker_inspect(self, req)

    def _handle_probe(self, req: SupervisorActionRequest) -> SupervisorActionResponse:
        return handle_worker_probe(self, req)

    def _handle_apply(self, req: SupervisorActionRequest) -> SupervisorActionResponse:
        return handle_worker_apply(self, req)

    def _handle_read(self, req: SupervisorActionRequest) -> SupervisorActionResponse:
        return handle_worker_read(self, req)

    def _handle_eval(self, req: SupervisorActionRequest) -> SupervisorActionResponse:
        coord = self._ensure_session(req)
        if coord.page is None:
            raise RuntimeError("Worker page is not available.")
        if req.url is not None and not req.url.strip():
            return SupervisorActionResponse(
                success=False,
                action="eval",
                message="Explicit empty URL is invalid.",
                browser_pid=coord.adapter.browser_pid,
                worker_pid=os.getpid(),
                active_url=coord.page.url,
                active_title=coord.page.title(),
            )
        if req.url:
            coord.adapter.navigate(req.url)
        safe_eval_wrapper = """async ([code, args]) => {
            let raw;
            try {
                const fn = new Function('args', 'return (' + code + ')');
                raw = fn(args);
            } catch (e) {
                const fn2 = new Function('args', code);
                raw = fn2(args);
            }
            if (typeof raw === 'function') {
                try {
                    raw = raw(args);
                } catch (e) {}
            }
            if (raw && typeof raw.then === 'function') {
                try {
                    raw = await raw;
                } catch (e) {
                    throw e;
                }
            }
            if (typeof raw === 'function') {
                try {
                    raw = raw(args);
                } catch (e) {}
            }
            if (raw && typeof raw.then === 'function') {
                try {
                    raw = await raw;
                } catch (e) {
                    throw e;
                }
            }
            const seen = new Set();
            function sanitize(val, depth) {
                if (depth > 10) return '[Max Depth]';
                if (val === null || val === undefined) return val;
                if (typeof val === 'function') return '[Function ' + (val.name || 'anonymous') + ']';
                if (typeof val === 'object') {
                    if (typeof Window !== 'undefined' && val instanceof Window) return '[Window]';
                    if (typeof Document !== 'undefined' && val instanceof Document) return '[Document]';
                    if (typeof Node !== 'undefined' && val instanceof Node) return '[' + (val.nodeName || 'Node') + ']';
                    if (seen.has(val)) return '[Circular]';
                    seen.add(val);
                    if (Array.isArray(val)) {
                        return val.map(item => sanitize(item, depth + 1));
                    }
                    const out = {};
                    for (const k in val) {
                        if (Object.prototype.hasOwnProperty.call(val, k)) {
                            try {
                                out[k] = sanitize(val[k], depth + 1);
                            } catch (err) {
                                out[k] = '[Unserializable]';
                            }
                        }
                    }
                    return out;
                }
                return val;
            }
            return sanitize(raw, 0);
        }"""
        try:
            try:
                res = coord.page.evaluate(safe_eval_wrapper, [req.script or "", req.script_args])
            except Exception:
                res = coord.page.evaluate(req.script or "", req.script_args)
            sanitized_res = _sanitize_eval_result(res)
            return SupervisorActionResponse(
                success=True,
                action="eval",
                message="Evaluated successfully",
                reactive_event={"result": sanitized_res},
                active_url=coord.page.url,
                active_title=coord.page.title(),
            )
        except RecursionError:
            return SupervisorActionResponse(
                success=False,
                action="eval",
                message="Evaluation resulted in maximum recursion depth exceeded (circular DOM reference)",
                active_url=coord.page.url if coord.page else "",
                active_title=coord.page.title() if coord.page else "",
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
        if coord.page is None:
            raise RuntimeError("Worker page is not available.")
        if os.environ.get("WEBPILOT_ENABLE_EVAL_PY") != "1":
            return SupervisorActionResponse(
                success=False,
                action="eval_py",
                message="Security restriction: eval_py action is disabled by default. Set environment variable WEBPILOT_ENABLE_EVAL_PY=1 to enable.",
                active_url=coord.page.url if coord.page else "",
                active_title=coord.page.title() if coord.page else "",
            )
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
        if coord.page is None:
            raise RuntimeError("Worker page is not available.")
        if req.url is not None and not req.url.strip():
            return SupervisorActionResponse(
                success=False,
                action="css",
                message="Explicit empty URL is invalid.",
                browser_pid=coord.adapter.browser_pid,
                worker_pid=os.getpid(),
                active_url=coord.page.url,
                active_title=coord.page.title(),
            )
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

    def _handle_cookies(self, req: SupervisorActionRequest) -> SupervisorActionResponse:
        coord = self._ensure_session(req)
        ctx = coord.context
        if ctx is None:
            raise RuntimeError("Browser context is not available.")
        if req.url is not None and not req.url.strip():
            return SupervisorActionResponse(
                success=False,
                action="cookies",
                message="Explicit empty URL is invalid.",
                browser_pid=coord.adapter.browser_pid,
                worker_pid=os.getpid(),
            )
        if req.url:
            coord.adapter.navigate(req.url)

        urls_filter = None
        if req.target_field or req.query:
            target = (req.target_field or req.query or "").strip()
            if target.startswith("http://") or target.startswith("https://"):
                urls_filter = [target]
        elif coord.page and coord.page.url and coord.page.url not in ("about:blank", ""):
            # If domain or target not explicitly given, still export all context cookies or filter by active URL if desired
            pass

        cookies = ctx.cookies(urls_filter) if urls_filter else ctx.cookies()

        # If domain filter string given (e.g. "example.com")
        domain_query = (req.target_field or req.query or "").strip().lower()
        if domain_query and not (domain_query.startswith("http://") or domain_query.startswith("https://")):
            cookies = [c for c in cookies if domain_query in str(c.get("domain", "")).lower() or domain_query in str(c.get("name", "")).lower()]

        from common.cookies import save_cookies
        output_path = req.output_path or req.cookies_path
        if output_path:
            save_cookies(output_path, cookies)
            msg = f"Successfully exported {len(cookies)} cookies to: {output_path}"
        else:
            msg = f"Retrieved {len(cookies)} cookies from browser session."

        return SupervisorActionResponse(
            success=True,
            action="cookies",
            message=msg,
            cookies=cookies,
            browser_pid=coord.adapter.browser_pid,
            worker_pid=os.getpid(),
            active_url=coord.page.url if coord.page else "",
            active_title=coord.page.title() if coord.page else "",
        )

    def _handle_wait(self, req: SupervisorActionRequest) -> SupervisorActionResponse:
        """Explicitly waits for an element selector, network idle, or timeout."""
        coord = self._ensure_session(req)
        if req.tab_index is not None:
            coord.switch_to_tab(req.tab_index)
        page = coord.page
        if not page:
            raise RuntimeError("Worker page is not available.")

        lines: List[str] = []
        timeout_ms = getattr(req, "wait_timeout", 10000) or 10000
        state = getattr(req, "wait_state", "visible") or "visible"

        if req.url:
            lines.append(f"[*] Navigating to: {req.url}")
            coord.adapter.navigate(req.url)
            page = coord.page

        if getattr(req, "network_idle", False):
            lines.append(f"[*] Waiting for network idle (timeout: {timeout_ms}ms)...")
            try:
                page.wait_for_load_state("networkidle", timeout=timeout_ms)
                lines.append("[✓] Network idle state reached.")
            except Exception as exc:
                return SupervisorActionResponse(
                    success=False,
                    action="wait",
                    message=f"Timeout waiting for network idle: {exc}",
                    browser_pid=coord.adapter.browser_pid,
                    worker_pid=os.getpid(),
                    active_tab_index=coord.adapter.get_active_tab_index(),
                    active_url=page.url,
                    active_title=page.title(),
                    output_lines=lines + [f"[!] Network idle error: {exc}"],
                )

        if req.selector:
            lines.append(f"[*] Waiting for selector '{req.selector}' to reach state '{state}' (timeout: {timeout_ms}ms)...")
            try:
                page.wait_for_selector(req.selector, state=state, timeout=timeout_ms)
                lines.append(f"[✓] Element '{req.selector}' reached state '{state}'.")
            except Exception as exc:
                return SupervisorActionResponse(
                    success=False,
                    action="wait",
                    message=f"Timeout waiting for selector '{req.selector}' to reach state '{state}': {exc}",
                    browser_pid=coord.adapter.browser_pid,
                    worker_pid=os.getpid(),
                    active_tab_index=coord.adapter.get_active_tab_index(),
                    active_url=page.url,
                    active_title=page.title(),
                    output_lines=lines + [f"[!] Wait error: {exc}"],
                )

        target_desc = req.selector or ("networkidle" if getattr(req, "network_idle", False) else "condition")
        return SupervisorActionResponse(
            success=True,
            action="wait",
            message=f"Successfully waited for {target_desc}.",
            browser_pid=coord.adapter.browser_pid,
            worker_pid=os.getpid(),
            active_tab_index=coord.adapter.get_active_tab_index(),
            active_url=page.url,
            active_title=page.title(),
            total_tabs=len(coord.context.pages) if coord.context else 1,
            tabs=coord.adapter.list_open_tabs(),
            output_lines=lines,
        )

    def shutdown(self) -> None:
        """Terminates all Playwright coordinators and all child browser tabs."""
        for c in list(self.coordinators.values()):
            try:
                c.close()
            except Exception:
                pass
        self.coordinators.clear()
        if self.coordinator:
            try:
                self.coordinator.close()
            except Exception:
                pass
            self.coordinator = None


def run_worker_loop():
    """Reads JSON requests from stdin, executes, writes JSON response to stdout."""
    os.environ["WEBPILOT_WORKER_PROCESS"] = "1"
    rpc_out = sys.stdout
    # Redirect all print/logging to stderr to keep JSON-RPC channel strictly pure
    sys.stdout = sys.stderr

    import signal
    worker = OperationalWorker(headed=False)

    def _sig_handler(signum, frame):
        try:
            worker.shutdown()
            from adapters.live_session_manager import LiveSessionManager
            LiveSessionManager.cleanup_temp_profiles(max_age_seconds=0)
        except Exception:
            pass
        sys.exit(0)

    try:
        signal.signal(signal.SIGINT, _sig_handler)
        if hasattr(signal, "SIGTERM"):
            signal.signal(signal.SIGTERM, _sig_handler)
    except Exception:
        pass

    try:
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

                try:
                    out_payload = json.dumps(resp.to_dict())
                except RecursionError:
                    resp.reactive_event = {"result": "[Circular]"}
                    out_payload = json.dumps(resp.to_dict())

                rpc_out.write(out_payload + "\n")
                rpc_out.flush()

                if req.action.lower().strip() in ("stop", "shutdown"):
                    break

            except RecursionError:
                err_resp = SupervisorActionResponse(
                    success=False,
                    action="error",
                    message="Worker loop fatal error: maximum recursion depth exceeded",
                )
                rpc_out.write(json.dumps(err_resp.to_dict()) + "\n")
                rpc_out.flush()
            except Exception as exc:
                err_resp = SupervisorActionResponse(
                    success=False,
                    action="error",
                    message=f"Worker loop fatal error: {exc}",
                )
                rpc_out.write(json.dumps(err_resp.to_dict()) + "\n")
                rpc_out.flush()
    finally:
        try:
            worker.shutdown()
        except Exception:
            pass
        try:
            from adapters.live_session_manager import LiveSessionManager
            LiveSessionManager.cleanup_temp_profiles(max_age_seconds=0)
        except Exception:
            pass


if __name__ == "__main__":
    run_worker_loop()

