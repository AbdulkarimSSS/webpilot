"""Authentication and portal navigation service."""

from __future__ import annotations

import json
from typing import Optional
from playwright.sync_api import BrowserContext, Page

from adapters.dom_scripts import (
    DETECT_LOGIN_PAGE_SCRIPT,
    INJECT_LOGIN_CREDENTIALS_SCRIPT,
    PORTAL_DROPDOWN_CLICK_SCRIPT,
    PORTAL_APPLY_CLICK_SCRIPT,
    CHECK_FORM_LOADING_SCRIPT,
    EXPAND_ALL_SECTIONS_SCRIPT,
)
from common.cookies import save_cookies
from constants.timeouts import (
    PAUSE_PORTAL_DROPDOWN_CLICK_MS,
    PAUSE_PORTAL_APPLY_CLICK_MS,
    PAUSE_LOGIN_STABILIZATION_MS,
    DEFAULT_FORM_READY_TIMEOUT_MS,
    DEFAULT_EXPAND_SECTION_WAIT_MS,
)


class AuthNavigationService:
    """Manages login detection, portal transitions, and form readiness state."""

    def __init__(self, page: Page, context: BrowserContext):
        self.page = page
        self.context = context

    def handle_login_if_needed(
        self,
        email: str,
        password: str,
        cookies_save_path: Optional[str] = None,
    ) -> bool:
        """Detects if page is a login/sign-in page and completes authentication."""
        try:
            self.page.wait_for_load_state("domcontentloaded", timeout=5000)
        except Exception:
            pass

        try:
            is_login = self.page.evaluate(DETECT_LOGIN_PAGE_SCRIPT)
        except Exception:
            self.page.wait_for_timeout(2000)
            try:
                is_login = self.page.evaluate(DETECT_LOGIN_PAGE_SCRIPT)
            except Exception:
                is_login = False

        if is_login:
            print("[*] Login page detected. Authenticating automatically...")
            self.page.evaluate(INJECT_LOGIN_CREDENTIALS_SCRIPT, [email, password])
            self.page.wait_for_timeout(1000)

            # Click Sign In / Submit button via native text locator
            for selector in ["button:has-text('sign in')", "[role='button']:has-text('sign in')", "input[type='submit']"]:
                loc = self.page.locator(selector)
                if loc.count() > 0 and loc.first.is_visible():
                    loc.first.click()
                    break

            self.page.wait_for_timeout(PAUSE_LOGIN_STABILIZATION_MS)
            print(f"[✓] Post-login URL: {self.page.url}")

            if cookies_save_path:
                try:
                    cookies = self.context.cookies()
                    save_cookies(cookies_save_path, cookies)
                    print(f"[✓] Fresh cookies saved to: {cookies_save_path}")
                except Exception as exc:
                    print(f"[!] Error saving cookies: {exc}")
            return True
        return False

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

            if len(self.context.pages) > 1:
                self.page = self.context.pages[-1]
                print(f"[*] Switched to active application window: {self.page.url}")
            return True
        return False

    def wait_for_form_ready(self, timeout_ms: int = DEFAULT_FORM_READY_TIMEOUT_MS) -> None:
        """Waits for form elements to be rendered in DOM, dismissing 'Loading...' state."""
        print("[*] Waiting for form components to render...")
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
        except Exception as exc:
            print(f"[!] Warning waiting for form: {exc}")

    def expand_all_sections(self, wait_ms: int = DEFAULT_EXPAND_SECTION_WAIT_MS) -> int:
        """Safely expands any collapsed form sections without toggling open ones."""
        opened = self.page.evaluate(EXPAND_ALL_SECTIONS_SCRIPT)
        if opened > 0:
            self.page.wait_for_timeout(wait_ms)
        return opened
