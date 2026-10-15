"""Operational request handlers for Supervisor Worker Process.

Contains inspect, probe, and apply action execution routines extracted from OperationalWorker.
"""

from __future__ import annotations

import os
import sys
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

from builder import FormPayloadBuilder
from common.cookies import save_cookies
from common.text import decode_unicode_escapes
from services.field_interaction_service import FieldInteractionService
from services.form_application_pipeline import FormApplicationPipeline
from services.inspection_service import InspectionService
from services.page_lifecycle_service import PageLifecycleService
from services.reactive_interaction_service import ReactiveInteractionService
from supervisor.contracts import SupervisorActionRequest, SupervisorActionResponse
from validators.form_validator import FormValidator

if TYPE_CHECKING:
    from supervisor.worker_process import OperationalWorker


def _resolve(service_name: str, fallback_cls: Any) -> Any:
    """Resolves service class dynamically to support test monkeypatching on supervisor.worker_process."""
    wp_mod = sys.modules.get("supervisor.worker_process")
    if wp_mod and hasattr(wp_mod, service_name):
        return getattr(wp_mod, service_name)
    return fallback_cls


def handle_worker_inspect(
    worker: OperationalWorker,
    req: SupervisorActionRequest,
) -> SupervisorActionResponse:
    """Executes full page inspection inside worker session."""
    coord = worker._ensure_session(req)
    if req.tab_index is not None:
        page = coord.switch_to_tab(req.tab_index)
    else:
        page = coord.page
    if page is None:
        raise RuntimeError("Worker page is not available.")

    lines: List[str] = []
    if req.url:
        coord.adapter.navigate(req.url)
        page = coord.page
    elif getattr(req, "reload", False):
        lines.append(f"[*] Hard-reloading active page from server: {page.url}")
        page.reload(wait_until="load")
        for _ in range(10):
            if page.locator("input:not([type='hidden']), select, textarea, .rcmFormSection, [id*='expandAllSections']").count() > 0:
                break
            page.wait_for_timeout(250)
        worker.cached_schema = None

    # Landing portal transition if needed
    lifecycle_cls = _resolve("PageLifecycleService", PageLifecycleService)
    lifecycle_svc = lifecycle_cls(page, coord.context)
    if req.url and ("jobs." in page.url or page.locator("button.dropdown-toggle, .dialogApplyBtn").count() > 0):
        lifecycle_svc.bypass_job_landing_portal()
        page = coord.switch_to_latest_page()

    # Automatically wait for form readiness and expand all collapsed sections if requested
    do_expand = getattr(req, "auto_expand", True)
    if do_expand:
        try:
            lifecycle_svc.wait_for_form_ready(worker.settings.form_ready_timeout_ms)
            lifecycle_svc.expand_all_sections(worker.settings.expand_section_wait_ms)
        except Exception as exc:
            err_str = str(exc).lower()
            if "execution context was destroyed" in err_str or "navigation" in err_str:
                try:
                    page.wait_for_load_state("domcontentloaded", timeout=4000)
                    lifecycle_svc.expand_all_sections(worker.settings.expand_section_wait_ms)
                except Exception:
                    pass

    if worker.cached_url and worker.cached_url != page.url:
        worker.cached_schema = None
        worker.cached_url = None

    inspection_cls = _resolve("InspectionService", InspectionService)
    inspection_svc = inspection_cls(page)
    schema = inspection_svc.inspect(unpack_options=req.unpack_options)
    if worker.cached_schema and worker.cached_url == page.url and not getattr(req, "reload", False):
        schema = worker._merge_schemas(worker.cached_schema, schema)
    worker.cached_schema = schema
    worker.cached_url = page.url

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
        output_lines=lines,
    )


def handle_worker_probe(
    worker: OperationalWorker,
    req: SupervisorActionRequest,
) -> SupervisorActionResponse:
    """Probes a specific field or element in the live DOM."""
    coord = worker._ensure_session(req)
    page = coord.page
    if page is None:
        raise RuntimeError("Worker page is not available.")

    if req.url:
        coord.adapter.navigate(req.url)
        page = coord.page

    target = req.selector or req.target_field or ""
    if not target:
        return SupervisorActionResponse(
            success=False,
            action="probe",
            message="Missing target field or selector to probe.",
        )

    if target.startswith("@"):
        try:
            has_stamp = page.evaluate("([t]) => !!document.querySelector('[data-wp-id=\"' + t + '\"]')", [target])
            if not has_stamp:
                inspection_cls = _resolve("InspectionService", InspectionService)
                inspection_cls(page).inspect()
        except Exception:
            pass

    field_cls = _resolve("FieldInteractionService", FieldInteractionService)
    interaction_svc = field_cls(page)
    decoded_target = decode_unicode_escapes(target)
    decoded_query = decode_unicode_escapes(req.query or "")
    details = interaction_svc.probe_field(
        target=decoded_target,
        include_options=req.include_options,
        query=decoded_query,
        include_html=req.include_html or (getattr(req, "up_levels", 0) > 0),
        up_levels=getattr(req, "up_levels", 0),
        screenshot_path=req.screenshot_path,
        selector=req.selector,
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


def handle_worker_apply(
    worker: OperationalWorker,
    req: SupervisorActionRequest,
) -> SupervisorActionResponse:
    """Executes full form population and submission lifecycle."""
    coord = worker._ensure_session(req)
    page = coord.page
    ctx = coord.context
    if page is None or ctx is None:
        raise RuntimeError("Worker page or context is not available.")

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

    lifecycle_cls = _resolve("PageLifecycleService", PageLifecycleService)
    lifecycle_svc = lifecycle_cls(page, ctx)

    # 1. Landing portal bypass
    if req.url and ("jobs." in page.url or page.locator("button.dropdown-toggle, .dialogApplyBtn").count() > 0):
        lines.append("[*] Bypassing landing page to active application...")
        lifecycle_svc.bypass_job_landing_portal()
        page = coord.switch_to_latest_page()

    # 2. Wait for form readiness & expand accordions
    lifecycle_svc.wait_for_form_ready(worker.settings.form_ready_timeout_ms)
    lines.append("[*] Ensuring all form sections are expanded...")
    try:
        lifecycle_svc.expand_all_sections(worker.settings.expand_section_wait_ms)
    except Exception:
        pass

    # 3. Assemble fields to set
    fields_to_set = []
    failed: List[Tuple[str, Any]] = []
    if req.data_path:
        if os.path.isfile(req.data_path):
            fields_to_set.extend(FormPayloadBuilder.load_from_file(req.data_path))
        else:
            lines.append(f"[!] Data payload file not found: '{req.data_path}'")
            failed.append(("@data_file", req.data_path))
    if req.fill_arguments:
        fields_to_set.extend(FormPayloadBuilder.parse_cli_fill_arguments(req.fill_arguments))

    field_cls = _resolve("FieldInteractionService", FieldInteractionService)
    field_svc = field_cls(page)
    confirmed: List[Tuple[str, Any]] = []
    unconfirmed: List[Tuple[str, Any]] = []

    if fields_to_set:
        c, u, f = FormApplicationPipeline.execute_cascading_fill(
            page=page,
            field_svc=field_svc,
            fields_to_set=fields_to_set,
            cached_schema=worker.cached_schema,
            lines=lines,
        )
        confirmed.extend(c)
        unconfirmed.extend(u)
        failed.extend(f)

    # 4. Handle uploads
    upload_failed = False
    if req.upload_files:
        upload_ok = FormApplicationPipeline.execute_uploads(page, req.upload_files, lines)
        if not upload_ok:
            upload_failed = True

    # 5. Pre-submit verification barrier (if uploads or intervening actions occurred)
    if confirmed and req.upload_files and (req.press_buttons or req.submit):
        confirmed = worker._reverify_fields(field_svc, confirmed, unconfirmed, lines, "Pre-submit check")

    # 6. Handle buttons with reactive observation
    inspection_cls = _resolve("InspectionService", InspectionService)
    inspection_svc = inspection_cls(page)
    validator_cls = _resolve("FormValidator", FormValidator)
    validator = validator_cls(page)
    reactive_cls = _resolve("ReactiveInteractionService", ReactiveInteractionService)
    reactive_svc = reactive_cls(
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
        if not res.get("success"):
            for kw in ("register", "save", "continue", "create account", "send", "confirm"):
                res = reactive_svc.click_button(kw)
                if res.get("success"):
                    break
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
            confirmed = worker._reverify_fields(field_svc, confirmed, unconfirmed, lines, "Post-interaction check")
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
        if validation_errors:
            lines.append(f"[!] Validation Notices: {validation_errors}")
        else:
            lines.append("[✓] Zero validation errors detected!")
    except Exception as exc:
        lines.append(f"  [!] Notice during form validation check: {exc}")
        validation_errors = []

    if getattr(req, "reload", False):
        if (validation_errors or failed or unconfirmed) and (req.press_buttons or req.submit):
            lines.append("[!] Skipping post-action reload because failed/unconfirmed fields or validation errors are present (preserving filled state).")
        else:
            try:
                lines.append(f"[*] Hard-reloading active page from server: {page.url}")
                page.reload(wait_until="load")
                for _ in range(10):
                    if page.locator("input:not([type='hidden']), select, textarea, .rcmFormSection, [id*='expandAllSections']").count() > 0:
                        break
                    page.wait_for_timeout(250)
                worker.cached_schema = None
                lifecycle_svc.wait_for_form_ready(worker.settings.form_ready_timeout_ms)
                lifecycle_svc.expand_all_sections(worker.settings.expand_section_wait_ms)
            except Exception as exc:
                lines.append(f"[!] Warning during page reload: {exc}")

    schema = None
    if req.auto_inspect:
        try:
            if (has_navigated or req.press_buttons or req.submit) and not getattr(req, "reload", False):
                lifecycle_svc.wait_for_form_ready(worker.settings.form_ready_timeout_ms)
                lifecycle_svc.expand_all_sections(worker.settings.expand_section_wait_ms)
            schema = inspection_svc.inspect(unpack_options=False)
            if schema:
                worker.cached_schema = schema
                worker.cached_url = page.url
        except Exception:
            schema = None


    # Honesty contract: success requires zero failed fields, zero unconfirmed fields, zero validation errors, and all requested button presses and uploads succeeding
    overall_success = (
        len(failed) == 0
        and len(unconfirmed) == 0
        and not press_failed
        and not submit_failed
        and not upload_failed
        and len(validation_errors) == 0
    )
    if press_failed:
        action_msg = "Form action completed but one or more requested button presses failed."
    elif submit_failed:
        action_msg = "Form action completed but submission button click failed."
    elif upload_failed:
        action_msg = "Form action completed but one or more file uploads failed."
    elif len(validation_errors) > 0:
        action_msg = f"Form action completed but {len(validation_errors)} validation error(s) detected: {validation_errors[0]}"
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
