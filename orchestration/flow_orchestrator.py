"""Flow Orchestrator: coordinates multi-step inspection and form application workflows."""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional

from builder import FormPayloadBuilder
from common.logging import log_event
from config.settings import get_settings, load_device_profile
from constants.timeouts import DEFAULT_SUBMIT_WAIT_MS
from core.models import ApplyExecutionResult, InspectionResult
from orchestration.context import (
    ApplyRequestContext,
    InspectionRequestContext,
    SessionContext,
)
from orchestration.session_coordinator import SessionCoordinator
from services.auth_navigation_service import AuthNavigationService
from services.field_interaction_service import FieldInteractionService
from services.inspection_formatter_service import InspectionFormatterService
from services.inspection_service import InspectionService
from services.reactive_interaction_service import ReactiveInteractionService
from adapters.live_session_manager import LiveSessionManager
from adapters.upload_adapter import UploadAdapter
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

            auth_svc = AuthNavigationService(page, ctx)

            # 1. Landing portal bypass if applicable
            if "jobs." in page.url or page.locator("button.dropdown-toggle, .dialogApplyBtn").count() > 0:
                print("[*] Transitioning past landing portal...")
                auth_svc.bypass_job_landing_portal()
                page = coordinator.switch_to_latest_page()

            # 2. Form readiness & section expansion
            auth_svc.wait_for_form_ready(settings.form_ready_timeout_ms)
            auth_svc.expand_all_sections(settings.expand_section_wait_ms)

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

            auth_svc = AuthNavigationService(page, ctx)

            # 1. Landing portal bypass
            if req.url and ("jobs." in page.url or page.locator("button.dropdown-toggle, .dialogApplyBtn").count() > 0):
                print("[*] Bypassing landing page to active application...")
                auth_svc.bypass_job_landing_portal()
                page = coordinator.switch_to_latest_page()

            print("[*] Current active URL:", page.url)

            # 2. Wait for form readiness & expand accordions
            auth_svc.wait_for_form_ready(settings.form_ready_timeout_ms)
            print("[*] Ensuring all form sections are expanded...")
            try:
                auth_svc.expand_all_sections(settings.expand_section_wait_ms)
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
            failed = []

            # 4. Populate fields dynamically
            if fields_to_set:
                print(f"\n[*] Populating {len(fields_to_set)} field(s)...")
                for key, val in fields_to_set:
                    success = field_svc.set_field(key, val)
                    if success:
                        confirmed.append((key, val))
                        print(f"  [✓] Set '{key}' -> '{val}'")
                    else:
                        failed.append((key, val))
                        print(f"  [~] Unmatched/Failed '{key}' -> '{val}'")
                print(f"[*] Fields summary: {len(confirmed)} set | {len(failed)} skipped.")

            # 5. Handle document uploads
            upload_adapter = UploadAdapter(page)
            if req.upload_files:
                for up in req.upload_files:
                    if "=" in up:
                        kw, path = up.split("=", 1)
                        kw, path = kw.strip(), path.strip()
                    else:
                        kw, path = "", up.strip()

                    if os.path.isfile(path):
                        print(f"[*] Uploading file '{path}' (Keyword: '{kw}')...")
                        upload_adapter.upload_document(path, kw)
                    else:
                        print(f"[!] Warning: Upload file not found: {path}")

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
                            schema = res.get("schema") or inspection_svc.inspect(unpack_options=False)
                            print(InspectionFormatterService.format_summary(schema))
                    elif res.get("modal_opened"):
                        print(f"\n[🪟 New Modal / Dialog Appeared]:\n{res['modal_text']}")
                        if req.auto_inspect and res.get("schema"):
                            print(InspectionFormatterService.format_summary(res["schema"]))
                    elif res.get("new_inputs_count", 0) > 0:
                        print(f"\n[📋 Dynamic Form Expansion (+{res['new_inputs_count']} new inputs detected)]")
                        if req.auto_inspect and res.get("schema"):
                            print(InspectionFormatterService.format_summary(res["schema"]))
                    else:
                        if req.auto_inspect:
                            print(f"\n[*] Auto-inspecting post-interaction state for: '{page.title()}' ({page.url})...")
                            post_inspection = inspection_svc.inspect(unpack_options=False)
                            print(InspectionFormatterService.format_summary(post_inspection))

                    if res.get("alerts"):
                        print("\n[📢 Page Notices / Alerts]:", res["alerts"])

            # 7. Screenshot state
            if req.screenshot_path:
                coordinator.adapter.capture_screenshot(req.screenshot_path, full_page=True)
                print(f"[✓] Form filled state captured: {req.screenshot_path}")

            # 8. Validation checks
            validation_errors = validator.get_validation_errors()
            if validation_errors:
                print("\n[!] Form Validation Notices:", validation_errors)
            else:
                print("\n[✓] Zero validation errors detected!")

            # 9. Final submission
            confirmation_screenshot = None
            if req.submit:
                print("\n[*] Executing final submission...")
                reactive_svc.click_button("apply")
                page.wait_for_timeout(settings.submission_wait_ms)

                post_errors = validator.get_validation_errors()
                if post_errors:
                    print("[!] Post-Submit Notices:", post_errors)
                else:
                    print("[✓] Application submitted successfully!")

                if req.screenshot_path:
                    confirmation_screenshot = "submission_final_confirmation.png"
                    coordinator.adapter.capture_screenshot(confirmation_screenshot, full_page=True)
                    print(f"[✓] Confirmation screenshot saved: {confirmation_screenshot}")

            return ApplyExecutionResult(
                confirmed_fields=confirmed,
                unconfirmed_fields=[],
                failed_fields=failed,
                final_url=page.url,
                validation_errors=validation_errors,
                submitted=req.submit,
                confirmation_screenshot=confirmation_screenshot,
            )
