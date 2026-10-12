"""Flow Orchestrator: coordinates multi-step inspection and form application workflows."""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional

from adapters.live_session_manager import LiveSessionManager
from builder import FormPayloadBuilder
from config.settings import get_settings, load_device_profile
from core.models import ApplyExecutionResult, InspectionResult
from orchestration.context import (
    ApplyRequestContext,
    InspectionRequestContext,
    SessionContext,
)
from orchestration.session_coordinator import SessionCoordinator
from services.page_lifecycle_service import PageLifecycleService
from services.field_interaction_service import FieldInteractionService
from services.form_application_pipeline import FormApplicationPipeline
from services.inspection_formatter_service import InspectionFormatterService
from services.inspection_service import InspectionService
from services.reactive_interaction_service import ReactiveInteractionService
from validators.form_validator import FormValidator


class FlowOrchestrator:
    """Enterprise flow orchestrator managing multi-step web automation pipelines."""

    @staticmethod
    def execute_inspection_flow(req: InspectionRequestContext) -> Dict[str, Any]:
        """Executes full multi-step inspection flow."""
        if req.close_session:
            terminated = LiveSessionManager.terminate_session()
            if terminated:
                print("[✓] Successfully terminated live browser session and killed process.")
            else:
                print("[*] No active live browser session was found to terminate.")
            return {}

        settings = get_settings(
            env_file=req.env_file,
            settings_json_path=req.config_path,
        )
        device_profile = load_device_profile(
            profile_path=req.device_profile_path,
            env_file=req.env_file,
        )
        headless = not req.headed if req.headed else settings.headless
        effective_cookies = req.cookies_path or settings.cookies_path

        session_ctx = SessionContext(
            settings=settings,
            device_profile=device_profile,
            headless=headless,
            cookies_path=effective_cookies,
            keep_alive=req.keep_alive or req.list_tabs,
            close_session=req.close_session,
            timeout_minutes=req.timeout_minutes or 30,
            tab_index=req.tab_index,
        )

        with SessionCoordinator(session_ctx) as coordinator:
            if req.list_tabs:
                tabs = coordinator.list_open_tabs()
                print("\n" + "═" * 70)
                print(" 📑 OPEN BROWSER TABS")
                print("═" * 70)
                if not tabs:
                    print(" [!] No open tabs detected in current session.")
                else:
                    for t in tabs:
                        active_mark = " [*ACTIVE*]" if t.get("is_active") else ""
                        print(f" • Tab #{t['index']}{active_mark}: '{t['title']}'\n   URL: {t['url']}")
                print("═" * 70 + "\n")
                return {"tabs": tabs}

            page = coordinator.page
            ctx = coordinator.context
            assert page is not None and ctx is not None

            if req.tab_index is not None:
                page = coordinator.switch_to_tab(req.tab_index)

            if req.url:
                print(f"[*] Starting engine and navigating to: {req.url}")
                coordinator.adapter.navigate(req.url)
            else:
                if page.url and page.url != "about:blank":
                    print(f"[*] Working on active page in existing browser session: {page.url}")
                else:
                    raise ValueError("Target URL (--url) is required when starting a new session without an active page.")

            lifecycle_svc = PageLifecycleService(page, ctx)

            # 1. Landing portal transition if applicable
            if "jobs." in page.url or page.locator("button.dropdown-toggle, .dialogApplyBtn").count() > 0:
                print("[*] Transitioning past landing portal...")
                lifecycle_svc.bypass_job_landing_portal()
                page = coordinator.switch_to_latest_page()

            # 2. Form readiness & section expansion
            lifecycle_svc.wait_for_form_ready(settings.form_ready_timeout_ms)
            lifecycle_svc.expand_all_sections(settings.expand_section_wait_ms)

            # 3. Inspect page schema
            print("[*] Inspecting page components and form schema...")
            inspection_svc = InspectionService(page)
            inspection_data = inspection_svc.inspect(unpack_options=req.unpack_options)

            # 4. Format & display summary
            summary = InspectionFormatterService.format_summary(inspection_data)
            print("\n" + summary)

            # 5. Persist schema & screenshot
            if req.output_path:
                with open(req.output_path, "w", encoding="utf-8") as f:
                    json.dump(inspection_data, f, indent=2, ensure_ascii=False)
                print(f"[✓] Full schema saved to: {req.output_path}")

            if req.screenshot_path:
                coordinator.adapter.capture_screenshot(req.screenshot_path, full_page=True)
                print(f"[✓] Screenshot saved to: {req.screenshot_path}")

            return inspection_data

    @staticmethod
    def execute_apply_flow(req: ApplyRequestContext) -> ApplyExecutionResult:
        """Executes full multi-step form filling, file uploading, and submission flow."""
        if req.close_session:
            terminated = LiveSessionManager.terminate_session()
            if terminated:
                print("[✓] Successfully terminated live browser session and killed process.")
            else:
                print("[*] No active live browser session was found to terminate.")
            return ApplyExecutionResult(
                confirmed_fields=[],
                unconfirmed_fields=[],
                failed_fields=[],
                final_url="",
                validation_errors=[],
                submitted=False,
            )

        settings = get_settings(
            env_file=req.env_file,
            settings_json_path=req.config_path,
        )
        device_profile = load_device_profile(
            profile_path=req.device_profile_path,
            env_file=req.env_file,
        )
        headless = not req.headed if req.headed else settings.headless
        effective_cookies = req.cookies_path or settings.cookies_path

        session_ctx = SessionContext(
            settings=settings,
            device_profile=device_profile,
            headless=headless,
            cookies_path=effective_cookies,
            keep_alive=req.keep_alive or req.list_tabs,
            close_session=req.close_session,
            timeout_minutes=req.timeout_minutes or 30,
            tab_index=req.tab_index,
        )

        with SessionCoordinator(session_ctx) as coordinator:
            if req.list_tabs:
                tabs = coordinator.list_open_tabs()
                print("\n" + "═" * 70)
                print(" 📑 OPEN BROWSER TABS")
                print("═" * 70)
                if not tabs:
                    print(" [!] No open tabs detected in current session.")
                else:
                    for t in tabs:
                        active_mark = " [*ACTIVE*]" if t.get("is_active") else ""
                        print(f" • Tab #{t['index']}{active_mark}: '{t['title']}'\n   URL: {t['url']}")
                print("═" * 70 + "\n")
                return ApplyExecutionResult(
                    confirmed_fields=[],
                    unconfirmed_fields=[],
                    failed_fields=[],
                    final_url=coordinator.page.url if coordinator.page else "",
                    validation_errors=[],
                    submitted=False,
                )

            page = coordinator.page
            ctx = coordinator.context
            assert page is not None and ctx is not None

            if req.tab_index is not None:
                page = coordinator.switch_to_tab(req.tab_index)

            if req.url:
                print(f"[*] Navigating to target URL: {req.url}")
                coordinator.adapter.navigate(req.url)
            else:
                if page.url and page.url != "about:blank":
                    print(f"[*] Working on active page in existing browser session: {page.url}")
                else:
                    raise ValueError("Target URL (--url) is required when starting a new session without an active page.")

            lifecycle_svc = PageLifecycleService(page, ctx)

            # 1. Landing portal bypass
            if req.url and ("jobs." in page.url or page.locator("button.dropdown-toggle, .dialogApplyBtn").count() > 0):
                print("[*] Bypassing landing page to active application...")
                lifecycle_svc.bypass_job_landing_portal()
                page = coordinator.switch_to_latest_page()

            print("[*] Current active URL:", page.url)

            # 2. Wait for form readiness & expand accordions
            lifecycle_svc.wait_for_form_ready(settings.form_ready_timeout_ms)
            print("[*] Ensuring all form sections are expanded...")
            try:
                lifecycle_svc.expand_all_sections(settings.expand_section_wait_ms)
            except Exception:
                pass

            # 3. Assemble fields to set
            fields_to_set = []
            if req.data_path:
                if os.path.isfile(req.data_path):
                    print(f"[*] Loading form payload from: {req.data_path}")
                    fields_to_set.extend(FormPayloadBuilder.load_from_file(req.data_path))
                else:
                    print(f"[!] Warning: Specified data file not found: {req.data_path}")

            if req.fill_arguments:
                fields_to_set.extend(FormPayloadBuilder.parse_cli_fill_arguments(req.fill_arguments))

            field_svc = FieldInteractionService(page)
            confirmed = []
            unconfirmed = []
            failed = []

            # 4. Populate fields dynamically using unified cascading pipeline
            if fields_to_set:
                fill_lines: List[str] = []
                confirmed, unconfirmed, failed = FormApplicationPipeline.execute_cascading_fill(
                    page=page,
                    field_svc=field_svc,
                    fields_to_set=fields_to_set,
                    cached_schema=None,
                    lines=fill_lines,
                )
                for l in fill_lines:
                    print(l)

            # 5. Handle document uploads
            if req.upload_files:
                upload_lines: List[str] = []
                FormApplicationPipeline.execute_uploads(page, req.upload_files, upload_lines)
                for l in upload_lines:
                    print(l)

            # 6. Handle custom button presses with reactive observation
            inspection_svc = InspectionService(page)
            validator = FormValidator(page)
            reactive_svc = ReactiveInteractionService(
                page=page,
                context=ctx,
                inspection_service=inspection_svc,
                form_validator=validator,
                on_active_page_change=lambda p: coordinator.switch_to_latest_page(),
            )

            if req.press_buttons:
                for btn in req.press_buttons:
                    print(f"\n[*] Pressing requested button: '{btn}'...")
                    res = reactive_svc.click_button(btn)
                    if not res.get("success"):
                        print(f"  [!] Failed to find or click button: '{btn}'")
                        continue
                    print(f"  [✓] Successfully clicked '{btn}'.")

                    page = coordinator.switch_to_latest_page()
                    coordinator.adapter.print_page_telemetry()

                    if res.get("new_window"):
                        print(f"\n[🌐 New Window / Tab Opened]: {res['new_url']}")
                        if req.auto_inspect and res.get("schema"):
                            print(InspectionFormatterService.format_summary(res["schema"]))
                    elif res.get("redirected"):
                        print(f"\n[🔀 Redirect / Navigation Detected]: {res['new_url']}")
                        if req.auto_inspect:
                            current_schema = inspection_svc.inspect(unpack_options=False)
                            print(InspectionFormatterService.format_summary(current_schema))
                    elif res.get("modal_opened"):
                        print(f"\n[🪟 New Modal / Dialog Appeared]:\n{res['modal_text']}")
                    elif res.get("new_inputs_count", 0) > 0:
                        print(f"\n[📋 Dynamic Form Expansion (+{res['new_inputs_count']} new inputs)]")

            # 7. Final Form Submission if requested
            submitted = False
            if req.submit:
                print("\n[*] Executing final form submission (submit=True)...")
                res = reactive_svc.click_button("apply")
                if not res.get("success"):
                    res = reactive_svc.click_button("submit")
                if res.get("success"):
                    submitted = True
                    print("  [✓] Form submitted successfully.")
                    page = coordinator.switch_to_latest_page()
                    coordinator.adapter.print_page_telemetry()
                else:
                    print("  [!] Submission button clicked or not found; moving to validation.")

            # 8. Post-submission screenshot
            confirmation_screenshot = None
            if req.screenshot_path:
                confirmation_screenshot = req.screenshot_path
                coordinator.adapter.capture_screenshot(req.screenshot_path, full_page=True)
                print(f"[✓] Form state captured: {req.screenshot_path}")

            # 9. Validation checks
            try:
                validation_errors = validator.get_validation_errors()
            except Exception:
                validation_errors = []

            if validation_errors:
                print("\n[!] Form Validation Notices / Field Errors:")
                for err in validation_errors:
                    print(f"    - {err}")
            else:
                print("\n[✓] Zero validation errors detected!")

            # 10. Auto-inspect form after submission/filling
            if req.auto_inspect:
                print("\n[*] Executing automatic post-interaction form inspection...")
                try:
                    schema = inspection_svc.inspect(unpack_options=False)
                    print(InspectionFormatterService.format_summary(schema))
                except Exception as exc:
                    print(f"[!] Warning during auto-inspection: {exc}")

            return ApplyExecutionResult(
                confirmed_fields=confirmed,
                unconfirmed_fields=unconfirmed,
                failed_fields=failed,
                final_url=page.url,
                validation_errors=validation_errors,
                submitted=submitted,
                confirmation_screenshot=confirmation_screenshot,
            )
