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

from builder import FormPayloadBuilder
from common.cookies import save_cookies
from common.text import decode_unicode_escapes
from config.settings import get_settings, load_device_profile
from orchestration.context import SessionContext
from orchestration.session_coordinator import SessionCoordinator
from services.auth_navigation_service import AuthNavigationService
from services.field_interaction_service import FieldInteractionService
from services.form_application_pipeline import FormApplicationPipeline
from services.inspection_service import InspectionService
from services.reactive_interaction_service import ReactiveInteractionService
from services.schema_merger import SchemaMerger
from supervisor.contracts import SupervisorActionRequest, SupervisorActionResponse
from validators.form_validator import FormValidator


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
            )
            self.coordinator = SessionCoordinator(session_ctx)
            self.coordinator.start()
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

            elif action == "inspect":
                return self._handle_inspect(req)

            elif action == "apply":
                return self._handle_apply(req)

            elif action in ("probe", "find"):
                return self._handle_probe(req)

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
        coord = self._ensure_session(req)
        page = coord.page
        assert page is not None

        if req.url:
            coord.adapter.navigate(req.url)
            page = coord.page

        # Landing portal transition if needed
        auth_svc = AuthNavigationService(page, coord.context)
        if req.url and ("jobs." in page.url or page.locator("button.dropdown-toggle, .dialogApplyBtn").count() > 0):
            auth_svc.bypass_job_landing_portal()
            page = coord.switch_to_latest_page()

        # Automatically wait for form readiness and expand all collapsed sections
        try:
            auth_svc.wait_for_form_ready(self.settings.form_ready_timeout_ms)
            auth_svc.expand_all_sections(self.settings.expand_section_wait_ms)
        except Exception as exc:
            err_str = str(exc).lower()
            if "execution context was destroyed" in err_str or "navigation" in err_str:
                try:
                    page.wait_for_load_state("domcontentloaded", timeout=4000)
                    auth_svc.expand_all_sections(self.settings.expand_section_wait_ms)
                except Exception:
                    pass

        if self.cached_url and self.cached_url != page.url:
            self.cached_schema = None
            self.cached_url = None

        inspection_svc = InspectionService(page)
        schema = inspection_svc.inspect(unpack_options=req.unpack_options)
        if self.cached_schema and self.cached_url == page.url:
            schema = self._merge_schemas(self.cached_schema, schema)
        self.cached_schema = schema
        self.cached_url = page.url

        if req.screenshot_path:
            coord.adapter.capture_screenshot(req.screenshot_path, full_page=True)

        return SupervisorActionResponse(
            success=True,
            action="inspect",
            message=f"Inspected page: '{page.title()}'",
            browser_pid=coord.adapter.browser_pid,
            worker_pid=os.getpid(),
            active_tab_index=coord.adapter.get_active_tab_index(),
            active_url=page.url,
            active_title=page.title(),
            total_tabs=len(coord.context.pages) if coord.context else 0,
            schema=schema,
        )

    def _handle_probe(self, req: SupervisorActionRequest) -> SupervisorActionResponse:
        coord = self._ensure_session(req)
        page = coord.page
        assert page is not None

        if req.url:
            coord.adapter.navigate(req.url)
            page = coord.page

        target = req.target_field or ""
        if not target:
            return SupervisorActionResponse(
                success=False,
                action="probe",
                message="Missing target field to probe.",
            )

        if target.startswith("@"):
            try:
                has_stamp = page.evaluate("([t]) => !!document.querySelector('[data-wp-id=\"' + t + '\"]')", [target])
                if not has_stamp:
                    InspectionService(page).inspect()
            except Exception:
                pass

        interaction_svc = FieldInteractionService(page)
        decoded_target = decode_unicode_escapes(target)
        decoded_query = decode_unicode_escapes(req.query or "")
        details = interaction_svc.probe_field(
            target=decoded_target,
            include_options=req.include_options,
            query=decoded_query,
            include_html=req.include_html,
        )

        if not details or not details.get("found"):
            return SupervisorActionResponse(
                success=False,
                action="probe",
                message=f"Field not found: '{target}'",
                active_tab_index=coord.adapter.get_active_tab_index(),
                active_url=page.url,
                active_title=page.title(),
            )

        return SupervisorActionResponse(
            success=True,
            action="probe",
            message=f"Found element '{details.get('local_id') or details.get('id') or target}': {details.get('label')}",
            active_tab_index=coord.adapter.get_active_tab_index(),
            active_url=page.url,
            active_title=page.title(),
            field_details=details,
        )

    def _handle_apply(self, req: SupervisorActionRequest) -> SupervisorActionResponse:
        coord = self._ensure_session(req)
        page = coord.page
        ctx = coord.context
        assert page is not None and ctx is not None

        lines: List[str] = []

        if req.tab_index is not None:
            page = coord.switch_to_tab(req.tab_index)

        if req.url:
            lines.append(f"[*] Navigating to target URL: {req.url}")
            coord.adapter.navigate(req.url)
            page = coord.page
        else:
            if page.url and page.url != "about:blank":
                lines.append(f"[*] Working on active page in existing session: {page.url}")
            else:
                return SupervisorActionResponse(
                    success=False,
                    action="apply",
                    message="Target URL (--url) is required when starting a new session without an active page.",
                )

        auth_svc = AuthNavigationService(page, ctx)

        # 1. Landing portal bypass
        if req.url and ("jobs." in page.url or page.locator("button.dropdown-toggle, .dialogApplyBtn").count() > 0):
            lines.append("[*] Bypassing landing page to active application...")
            auth_svc.bypass_job_landing_portal()
            page = coord.switch_to_latest_page()

        # 2. Wait for form readiness & expand accordions
        auth_svc.wait_for_form_ready(self.settings.form_ready_timeout_ms)
        lines.append("[*] Ensuring all form sections are expanded...")
        try:
            auth_svc.expand_all_sections(self.settings.expand_section_wait_ms)
        except Exception:
            pass

        # 3. Assemble fields to set
        fields_to_set = []
        if req.data_path and os.path.isfile(req.data_path):
            fields_to_set.extend(FormPayloadBuilder.load_from_file(req.data_path))
        if req.fill_arguments:
            fields_to_set.extend(FormPayloadBuilder.parse_cli_fill_arguments(req.fill_arguments))

        field_svc = FieldInteractionService(page)
        confirmed: List[Tuple[str, Any]] = []
        unconfirmed: List[Tuple[str, Any]] = []
        failed: List[Tuple[str, Any]] = []

        if fields_to_set:
            confirmed, unconfirmed, failed = FormApplicationPipeline.execute_cascading_fill(
                page=page,
                field_svc=field_svc,
                fields_to_set=fields_to_set,
                cached_schema=self.cached_schema,
                lines=lines,
            )

        # 4. Handle uploads
        if req.upload_files:
            FormApplicationPipeline.execute_uploads(page, req.upload_files, lines)

        # 5. Pre-submit verification barrier
        if confirmed and (req.press_buttons or req.submit):
            confirmed = self._reverify_fields(field_svc, confirmed, unconfirmed, lines, "Pre-submit check")

        # 6. Handle buttons with reactive observation
        inspection_svc = InspectionService(page)
        validator = FormValidator(page)
        reactive_svc = ReactiveInteractionService(
            page=page,
            context=ctx,
            inspection_service=inspection_svc,
            form_validator=validator,
            on_active_page_change=lambda p: coord.switch_to_latest_page(),
        )

        last_reactive_event: Optional[Dict[str, Any]] = None
        press_failed = False
        if req.press_buttons:
            for btn in req.press_buttons:
                lines.append(f"[*] Pressing button: '{btn}'...")
                res = reactive_svc.click_button(btn)
                if not res.get("success"):
                    lines.append(f"  [!] Failed to find or click button: '{btn}'")
                    press_failed = True
                    continue
                lines.append(f"  [✓] Successfully clicked '{btn}'.")
                page = coord.switch_to_latest_page()
                last_reactive_event = res

                if res.get("new_window"):
                    lines.append(f"\n[🌐 New Window / Tab Opened]: {res['new_url']}")
                elif res.get("redirected"):
                    lines.append(f"\n[🔀 Redirect / Navigation Detected]: {res['new_url']}")
                elif res.get("modal_opened"):
                    lines.append(f"\n[🪟 New Modal / Dialog Appeared]:\n{res['modal_text']}")
                elif res.get("new_inputs_count", 0) > 0:
                    lines.append(f"\n[📋 Dynamic Form Expansion (+{res['new_inputs_count']} new inputs)]")

        # 7. Final form submission if requested
        submit_failed = False
        if req.submit:
            lines.append("[*] Executing final form submission (submit=True)...")
            res = reactive_svc.click_button("apply")
            if not res.get("success"):
                res = reactive_svc.click_button("submit")
            if res.get("success"):
                lines.append("  [✓] Form submitted successfully.")
                page = coord.switch_to_latest_page()
                last_reactive_event = res
            else:
                lines.append("  [!] Submission button clicked or not found; moving to validation.")
                submit_failed = True

        # Post-interaction verification pass
        has_navigated = False
        if last_reactive_event and (last_reactive_event.get("redirected") or last_reactive_event.get("new_window")):
            has_navigated = True

        if confirmed and (req.press_buttons or req.submit) and not has_navigated:
            try:
                confirmed = self._reverify_fields(field_svc, confirmed, unconfirmed, lines, "Post-interaction check")
            except Exception as exc:
                err_str = str(exc).lower()
                if "execution context was destroyed" in err_str or "navigation" in err_str:
                    lines.append("  [*] Navigation in progress; skipping post-interaction check on previous form.")
                else:
                    lines.append(f"  [!] Post-interaction check notice: {exc}")

        # 8. Capture screenshot if requested
        if req.screenshot_path:
            coord.adapter.capture_screenshot(req.screenshot_path, full_page=True)
            lines.append(f"[✓] Form state captured: {req.screenshot_path}")

        # 9. Save refreshed cookies if requested
        if req.cookies_path and ctx:
            try:
                cookies = ctx.cookies()
                save_cookies(req.cookies_path, cookies)
                lines.append(f"[✓] Persisted {len(cookies)} cookies to: {req.cookies_path}")
            except Exception as exc:
                lines.append(f"[!] Warning saving cookies: {exc}")

        # 10. Validation checks
        try:
            validation_errors = validator.get_validation_errors()
        except Exception:
            validation_errors = []

        if validation_errors:
            lines.append(f"[!] Validation Notices: {validation_errors}")
        else:
            lines.append("[✓] Zero validation errors detected!")

        schema = None
        if req.auto_inspect:
            try:
                schema = inspection_svc.inspect(unpack_options=False)
            except Exception:
                schema = None

        # Honesty contract: success requires zero failed fields, zero unconfirmed fields, and all requested button presses succeeding
        overall_success = (len(failed) == 0 and len(unconfirmed) == 0 and not press_failed and not submit_failed)
        if press_failed:
            action_msg = "Form action completed but one or more requested button presses failed."
        elif submit_failed:
            action_msg = "Form action completed but submission button click failed."
        elif overall_success:
            action_msg = "Form action executed successfully."
        else:
            action_msg = "Form completed with unconfirmed or failed fields."

        return SupervisorActionResponse(
            success=overall_success,
            action="apply",
            message=action_msg,
            browser_pid=coord.adapter.browser_pid,
            worker_pid=os.getpid(),
            active_tab_index=coord.adapter.get_active_tab_index(),
            active_url=page.url,
            active_title=page.title(),
            total_tabs=len(ctx.pages) if ctx else 0,
            tabs=coord.adapter.list_open_tabs(),
            confirmed_fields=confirmed,
            unconfirmed_fields=unconfirmed,
            failed_fields=failed,
            validation_errors=validation_errors,
            schema=schema,
            reactive_event=last_reactive_event,
            output_lines=lines,
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

    worker = OperationalWorker()
    for raw_line in sys.stdin:
        line = raw_line.strip()
        if not line:
            continue
        try:
            data = json.loads(line)
            req = SupervisorActionRequest.from_dict(data)
            res = worker.handle_request(req)
            out = json.dumps(res.to_dict(), ensure_ascii=False)
            rpc_out.write(out + "\n")
            rpc_out.flush()
            if req.action in ("stop", "shutdown"):
                break
        except Exception as exc:
            err_res = SupervisorActionResponse(
                success=False,
                action="unknown",
                message=f"Fatal worker parse error: {exc}",
            )
            rpc_out.write(json.dumps(err_res.to_dict(), ensure_ascii=False) + "\n")
            rpc_out.flush()


if __name__ == "__main__":
    run_worker_loop()
