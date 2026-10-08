"""Sequential form filling orchestration service."""

from __future__ import annotations

from typing import Any, Dict, List, Tuple
from playwright.sync_api import Page

from constants.selectors import SELECTOR_SECTION_BUTTON
from constants.timeouts import PAUSE_INPUT_SET_MS, PAUSE_RETRY_FALLBACK_MS
from services.field_interaction_service import FieldInteractionService


class FormFillerService:
    """Orchestrates section-by-section and global sequential form filling."""

    def __init__(self, page: Page, field_service: FieldInteractionService):
        self.page = page
        self.field_service = field_service

    def fill_form_sequential(self, field_mappings: List[Tuple[str, Any]]) -> Dict[str, List[Tuple[str, Any]]]:
        """Universal sequential form filler. Opens one section, fills matching fields, then advances."""
        results: Dict[str, List[Tuple[str, Any]]] = {
            "confirmed": [],
            "unconfirmed": [],
            "failed": [],
        }

        pending = list(field_mappings)
        section_count = self.page.locator(SELECTOR_SECTION_BUTTON).count()
        print(f"[*] Sequential fill: {len(pending)} fields across {section_count} sections.")

        def try_fill(key: str, val: Any) -> str:
            """Attempt fill + DOM verify. Returns 'confirmed', 'unconfirmed', or 'failed'."""
            success = self.field_service.set_field(key, val)
            if not success:
                return "failed"

            self.page.wait_for_timeout(PAUSE_INPUT_SET_MS)
            if self.field_service.verify_field_value(key, val):
                return "confirmed"

            # One retry via pure Playwright click
            self.page.wait_for_timeout(PAUSE_RETRY_FALLBACK_MS)
            self.field_service._playwright_click_fallback(key, val)
            self.page.wait_for_timeout(PAUSE_RETRY_FALLBACK_MS)
            if self.field_service.verify_field_value(key, val):
                return "confirmed"
            return "unconfirmed"

        # Pass 1: Section by section
        for sec_idx in range(section_count):
            if not pending:
                break

            sec_btn = self.page.locator(SELECTOR_SECTION_BUTTON).nth(sec_idx)
            try:
                sec_label = sec_btn.inner_text(timeout=800).strip()[:50]
            except Exception:
                sec_label = f"Section {sec_idx + 1}"

            try:
                is_collapsed = sec_btn.get_attribute("aria-expanded") == "false"
                if is_collapsed:
                    sec_btn.scroll_into_view_if_needed()
                    sec_btn.click(force=True)
                    self.page.wait_for_timeout(400)
                    print(f"  [▶] Opened: {sec_label}")
                else:
                    print(f"  [=] Already open: {sec_label}")
            except Exception:
                print(f"  [?] Could not check/open: {sec_label}")

            still_pending = []
            for key, val in pending:
                status = try_fill(key, val)
                if status == "confirmed":
                    results["confirmed"].append((key, val))
                    print(f"    [✓] {key!r} -> {val!r}")
                elif status == "unconfirmed":
                    still_pending.append((key, val))
                else:
                    still_pending.append((key, val))

            pending = still_pending

        # Pass 2: Global retry for unmatched fields
        if pending:
            print(f"\n[*] Pass 2: {len(pending)} field(s) not matched in any section — trying globally...")
            for key, val in pending:
                status = try_fill(key, val)
                if status == "confirmed":
                    results["confirmed"].append((key, val))
                    print(f"  [✓] {key!r} -> {val!r}")
                elif status == "unconfirmed":
                    results["unconfirmed"].append((key, val))
                    print(f"  [?] Not confirmed: {key!r} -> {val!r}")
                else:
                    results["failed"].append((key, val))
                    print(f"  [✗] Failed: {key!r} -> {val!r}")

        print(
            f"\n[*] Fill summary: ✓{len(results['confirmed'])} confirmed | "
            f"?{len(results['unconfirmed'])} unconfirmed | "
            f"✗{len(results['failed'])} failed"
        )
        return results
