"""Form readiness, dynamic section expansion, and portal lifecycle service."""

from __future__ import annotations

from typing import Tuple
from playwright.sync_api import BrowserContext, Page

from adapters.dom.lifecycle import (
    CHECK_FORM_LOADING_SCRIPT,
    EXPAND_ALL_SECTIONS_SCRIPT,
)
from adapters.dom.navigation import (
    PORTAL_APPLY_CLICK_SCRIPT,
    PORTAL_DROPDOWN_CLICK_SCRIPT,
)
from constants.timeouts import (
    DEFAULT_EXPAND_SECTION_WAIT_MS,
    DEFAULT_FORM_READY_TIMEOUT_MS,
    PAUSE_PORTAL_APPLY_CLICK_MS,
    PAUSE_PORTAL_DROPDOWN_CLICK_MS,
)


class PageLifecycleService:
    """Manages page DOM lifecycle, asynchronous form readiness, and accordion section expansion."""

    def __init__(self, page: Page, context: Optional[BrowserContext] = None):
        self.page = page
        self.context = context

    def wait_for_form_ready(self, timeout_ms: int = DEFAULT_FORM_READY_TIMEOUT_MS) -> None:
        """Waits for form elements to be rendered in DOM, dismissing 'Loading...' state."""
        try:
            self.page.wait_for_load_state("domcontentloaded", timeout=min(5000, timeout_ms))
        except Exception:
            pass

        try:
            is_loading = self.page.evaluate(CHECK_FORM_LOADING_SCRIPT)
            if is_loading:
                for _ in range(6):
                    self.page.wait_for_timeout(200)
                    if not self.page.evaluate(CHECK_FORM_LOADING_SCRIPT):
                        break
        except Exception:
            pass

    def expand_all_sections(self, wait_ms: int = DEFAULT_EXPAND_SECTION_WAIT_MS) -> int:
        """Safely expands any collapsed form sections without toggling open ones."""
        opened = self.page.evaluate(EXPAND_ALL_SECTIONS_SCRIPT)
        if opened > 0:
            self.page.wait_for_timeout(wait_ms)
        return opened

    def bypass_job_landing_portal(self) -> bool:
        """Clicks portal landing 'Apply Now' dropdowns/buttons to enter active ATS application."""
        dropdown_clicked = self.page.evaluate(PORTAL_DROPDOWN_CLICK_SCRIPT)
        if dropdown_clicked:
            self.page.wait_for_timeout(PAUSE_PORTAL_DROPDOWN_CLICK_MS)

        clicked_apply = self.page.evaluate(PORTAL_APPLY_CLICK_SCRIPT)
        if clicked_apply:
            self.page.wait_for_timeout(PAUSE_PORTAL_APPLY_CLICK_MS)

            # Check if an interim email getter prompt is shown (e.g. SuccessFactors social apply)
            try:
                email_inp = self.page.locator("input[name='email']:visible, input[type='email']:visible")
                if email_inp.count() > 0:
                    start_btn = self.page.locator("button.start:visible, button:has-text('Start'):visible")
                    if start_btn.count() > 0:
                        start_btn.first.click()
                        self.page.wait_for_timeout(PAUSE_PORTAL_APPLY_CLICK_MS)
            except Exception:
                pass

            if self.context and len(self.context.pages) > 1:
                self.page = self.context.pages[-1]
            return True
        return False
