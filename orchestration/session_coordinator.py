"""Session Coordinator: manages browser session lifecycle, cookie propagation, and window state."""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from playwright.sync_api import BrowserContext, Page

from adapters.browser_adapter import BrowserAdapter
from common.cookies import save_cookies
from common.logging import log_event
from core.exceptions import AutomationError
from orchestration.context import SessionContext


class SessionCoordinator:
    """Coordinates Playwright browser lifecycle, context persistence, and page state."""

    def __init__(self, session_ctx: SessionContext):
        self.session_ctx = session_ctx
        self.adapter = BrowserAdapter(
            headless=session_ctx.headless,
            settings=session_ctx.settings,
            device_profile=session_ctx.device_profile,
            keep_alive=session_ctx.keep_alive,
            close_session=session_ctx.close_session,
            timeout_minutes=session_ctx.timeout_minutes,
            tab_index=session_ctx.tab_index,
            strip_header=session_ctx.strip_header,
            session_name=getattr(session_ctx, "session_name", None),
            enable_dns=getattr(session_ctx, "enable_dns", True),
            doh_servers=getattr(session_ctx, "doh_servers", None),
            block_images=getattr(session_ctx, "block_images", False),
            block_patterns=getattr(session_ctx, "block_patterns", None),
        )

    @property
    def page(self) -> Optional[Page]:
        """Active Page handle."""
        return self.adapter.page

    @property
    def context(self) -> Optional[BrowserContext]:
        """Active BrowserContext handle."""
        return self.adapter.context

    def __enter__(self) -> "SessionCoordinator":
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()

    def start(self) -> None:
        """Starts browser context or connects to live persistent session."""
        log_event("info", "Starting browser session", {
            "headless": self.session_ctx.headless,
            "device": self.session_ctx.device_profile.device_name,
            "keep_alive": self.session_ctx.keep_alive,
        })
        self.adapter.start(cookies_path=self.session_ctx.cookies_path)

    def close(self) -> None:
        """Saves refreshed cookies and terminates or detaches browser session."""
        if self.context and self.session_ctx.cookies_path:
            try:
                cookies = self.context.cookies()
                save_cookies(self.session_ctx.cookies_path, cookies)
                log_event("info", "Persisted session cookies", {
                    "path": self.session_ctx.cookies_path,
                    "count": len(cookies),
                })
            except Exception as exc:
                log_event("warn", "Failed saving session cookies", {"error": str(exc)})

        self.adapter.stop()
        log_event("info", "Ended browser session turn", {})

    def list_open_tabs(self) -> List[Dict[str, Any]]:
        """Returns metadata for all open tabs."""
        return self.adapter.list_open_tabs()

    def switch_to_tab(self, index: int) -> Page:
        """Switches active page to specified tab index."""
        return self.adapter.switch_to_tab(index)

    def create_new_tab(self, url: Optional[str] = None, tab_timeout_minutes: Optional[int] = None) -> Page:
        """Opens a new tab, navigates to url if provided, and brings to front."""
        return self.adapter.create_new_tab(url, tab_timeout_minutes=tab_timeout_minutes)

    def set_tab_timeout(self, index: int, timeout_minutes: int) -> bool:
        """Sets inactivity timeout for a specific tab."""
        return self.adapter.set_tab_timeout(index, timeout_minutes)

    def close_tab(self, index: Optional[int] = None) -> None:
        """Safely closes the target tab, ensuring at least one tab remains open."""
        self.adapter.close_tab(index)

    def switch_to_latest_page(self) -> Page:
        """Synchronizes and returns the latest opened browser tab/window."""
        ctx = self.context
        if ctx is None:
            raise AutomationError("Browser context is not initialized.")
        if len(ctx.pages) > 0:
            latest = ctx.pages[-1]
            self.adapter.page = latest
            return latest
        if self.page is None:
            raise AutomationError("No active page available.")
        return self.page
