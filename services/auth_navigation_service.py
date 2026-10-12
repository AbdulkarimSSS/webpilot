"""Authentication and portal navigation service (backwards-compatibility facade)."""

from __future__ import annotations

from typing import Optional
from playwright.sync_api import BrowserContext, Page

from common.cookies import save_cookies
from constants.timeouts import PAUSE_LOGIN_STABILIZATION_MS
from services.page_lifecycle_service import PageLifecycleService


class AuthNavigationService(PageLifecycleService):
    """Backwards-compatibility facade inheriting from PageLifecycleService."""

    def __init__(self, page: Page, context: Optional[BrowserContext] = None):
        super().__init__(page, context)

    def handle_login_if_needed(
        self,
        email: str,
        password: str,
        cookies_save_path: Optional[str] = None,
    ) -> bool:
        """Legacy helper for authenticating basic login forms."""
        from adapters.dom_scripts import (
            DETECT_LOGIN_PAGE_SCRIPT,
            INJECT_LOGIN_CREDENTIALS_SCRIPT,
        )

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
            self.page.evaluate(INJECT_LOGIN_CREDENTIALS_SCRIPT, [email, password])
            self.page.wait_for_timeout(1000)

            for selector in [
                "button:has-text('sign in')",
                "[role='button']:has-text('sign in')",
                "input[type='submit']",
            ]:
                loc = self.page.locator(selector)
                if loc.count() > 0 and loc.first.is_visible():
                    loc.first.click()
                    break

            self.page.wait_for_timeout(PAUSE_LOGIN_STABILIZATION_MS)

            if cookies_save_path and self.context:
                try:
                    cookies = self.context.cookies()
                    save_cookies(cookies_save_path, cookies)
                except Exception:
                    pass
            return True
        return False
