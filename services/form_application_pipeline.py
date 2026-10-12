"""Multi-pass cascading form application pipeline and verification sentinels."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
from playwright.sync_api import BrowserContext, Page

from adapters.upload_adapter import UploadAdapter
from common.logging import is_sensitive_key
from services.field_interaction_service import FieldInteractionService
from services.inspection_service import InspectionService
from services.reactive_interaction_service import ReactiveInteractionService
from validators.form_validator import FormValidator


@dataclass
class FormPipelineResult:
    """Output metrics and state changes from executing form filling and submission."""
    confirmed: List[Tuple[str, Any]] = field(default_factory=list)
    unconfirmed: List[Tuple[str, Any]] = field(default_factory=list)
    failed: List[Tuple[str, Any]] = field(default_factory=list)
    press_failed: bool = False
    submit_failed: bool = False
    last_reactive_event: Optional[Dict[str, Any]] = None


class FormApplicationPipeline:
    """Orchestrates multi-pass cascading field resolution, upload triggers, and reactive actions."""

    @staticmethod
    def resolve_effective_key(key: str, cached_schema: Optional[Dict[str, Any]]) -> str:
        """Resolves target key to element LocalID from cached schema if available."""
        if key.startswith("@") or not cached_schema:
            return key

        key_lower = key.lower().strip()
        for cat in ("inputs", "dropdowns", "choices"):
            for item in cached_schema.get(cat, []):
                lbl = (item.get("label") or "").lower().strip()
                iid = (item.get("id") or "").lower().strip()
                if (lbl == key_lower or iid == key_lower) and item.get("local_id"):
                    return item["local_id"]
        return key

    @staticmethod
    def reverify_fields(
        field_svc: FieldInteractionService,
        confirmed: List[Tuple[str, Any]],
        unconfirmed: List[Tuple[str, Any]],
        lines: List[str],
        stage_name: str,
    ) -> List[Tuple[str, Any]]:
        """Re-verifies that previously confirmed fields have not been wiped or reverted."""
        still_confirmed = []
        for key, val in confirmed:
            display_val = "***REDACTED***" if is_sensitive_key(key) else str(val)
            if field_svc.verify_field_value(key, val):
                still_confirmed.append((key, val))
            else:
                unconfirmed.append((key, val))
                lines.append(f"  [!] {stage_name} detected cleared/reverted field: '{key}' -> '{display_val}'")
                lines.append(f"  [?] Set but unconfirmed '{key}' -> '{display_val}'")
        return still_confirmed

    @classmethod
    def execute_cascading_fill(
        cls,
        page: Page,
        field_svc: FieldInteractionService,
        fields_to_set: List[Tuple[str, Any]],
        cached_schema: Optional[Dict[str, Any]],
        lines: List[str],
    ) -> Tuple[List[Tuple[str, Any]], List[Tuple[str, Any]], List[Tuple[str, Any]]]:
        """Fills fields across multiple cascading passes allowing reactive dependency resolution."""
        confirmed: List[Tuple[str, Any]] = []
        unconfirmed: List[Tuple[str, Any]] = []
        failed: List[Tuple[str, Any]] = []

        if not fields_to_set:
            return confirmed, unconfirmed, failed

        lines.append(f"[*] Populating {len(fields_to_set)} field(s)...")

        remaining_queue = list(fields_to_set)
        pass_num = 1
        max_passes = min(len(fields_to_set) + 1, 5)

        while remaining_queue and pass_num <= max_passes:
            if pass_num > 1:
                lines.append(
                    f"[*] --- Cascading Pass #{pass_num}: Retrying {len(remaining_queue)} dependent/unresolved field(s) ---"
                )
            pass_succeeded = 0
            still_failing: List[Tuple[str, Any, str]] = []

            for key, val in remaining_queue:
                display_val = "***REDACTED***" if is_sensitive_key(key) else str(val)
                effective_key = cls.resolve_effective_key(key, cached_schema)

                try:
                    success = field_svc.set_field(effective_key, val, debug_lines=lines)
                except TypeError:
                    success = field_svc.set_field(effective_key, val)

                if not success and effective_key != key:
                    try:
                        success = field_svc.set_field(key, val, debug_lines=lines)
                    except TypeError:
                        success = field_svc.set_field(key, val)

                if not success:
                    try:
                        el_exists = page.evaluate(
                            "([k]) => !!(document.getElementById(k) || document.querySelector('[id=\"' + k + '\"]') || document.querySelector('label[for=\"' + k + '\"]'))",
                            [key],
                        )
                    except Exception:
                        el_exists = False

                    dyn_res = getattr(field_svc, "expand_dynamic_section", None) if not el_exists else None
                    if callable(dyn_res):
                        res = dyn_res(key, val)
                        if isinstance(res, tuple) and len(res) == 2:
                            success, btn_label = res
                        else:
                            success, btn_label = bool(res), None
                        if success and btn_label:
                            lines.append(f"  [+] Dynamically expanded section via '{btn_label}'")

                if success:
                    clean_key = getattr(field_svc, "parse_target_descriptor", lambda k: (None, k, None))(key)[1]
                    verified = field_svc.verify_field_value(clean_key, val)
                    if not verified and clean_key != key:
                        verified = field_svc.verify_field_value(key, val)
                    pass_tag = f" (Pass {pass_num})" if pass_num > 1 else ""
                    if verified:
                        confirmed.append((key, val))
                        lines.append(f"  [✓] Set & Verified '{key}' -> '{display_val}'{pass_tag}")
                    else:
                        unconfirmed.append((key, val))
                        lines.append(f"  [?] Set but unconfirmed '{key}' -> '{display_val}'{pass_tag}")
                    pass_succeeded += 1
                else:
                    reason = getattr(field_svc, "last_failure_reason", "No matching element found")
                    still_failing.append((key, val, reason))

            if pass_succeeded > 0 and still_failing:
                lines.append(
                    f"[*] Pass #{pass_num} resolved {pass_succeeded} field(s). Waiting for cascading reactive DOM updates..."
                )
                try:
                    page.wait_for_timeout(350)
                except Exception:
                    pass
                remaining_queue = [(k, v) for (k, v, r) in still_failing]
                pass_num += 1
            else:
                for k, v, reason in still_failing:
                    display_val = "***REDACTED***" if is_sensitive_key(k) else str(v)
                    failed.append((k, v))
                    lines.append(f"  [~] Failed '{k}' -> '{display_val}' | Reason: {reason}")
                break

        lines.append(
            f"[*] Fields summary: {len(confirmed)} confirmed | {len(unconfirmed)} unconfirmed | {len(failed)} skipped/failed."
        )
        return confirmed, unconfirmed, failed

    @classmethod
    def execute_uploads(
        cls,
        page: Page,
        upload_files: List[str],
        lines: List[str],
    ) -> None:
        """Executes file attachments via UploadAdapter."""
        if not upload_files:
            return

        upload_adapter = UploadAdapter(page)
        for up in upload_files:
            if "=" in up:
                kw, path = up.split("=", 1)
                kw, path = kw.strip(), path.strip()
            else:
                kw, path = "", up.strip()
            if os.path.isfile(path):
                lines.append(f"[*] Uploading '{path}' (Keyword: '{kw}')...")
                upload_adapter.upload_document(path, kw)
            else:
                lines.append(f"[!] Upload target file not found: '{path}'")
