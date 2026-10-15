"""Browser tab enumeration, state tracking, and tab switching manager."""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from playwright.sync_api import BrowserContext, Page


class TabManager:
    """Manages browser tab enumeration, active tab tracking, and safe switching."""

    @staticmethod
    def get_active_tab_index(context: Optional[BrowserContext], active_page: Optional[Page]) -> int:
        """Returns the 0-based index of the currently active page in context.pages."""
        if not context or not active_page:
            return 0
        try:
            return context.pages.index(active_page)
        except ValueError:
            return 0

    @staticmethod
    def list_open_tabs(context: Optional[BrowserContext], active_page: Optional[Page]) -> List[Dict[str, Any]]:
        """Returns a list of dictionaries describing all open tabs in the browser context."""
        if not context:
            return []

        tabs_info = []
        for i, p in enumerate(context.pages):
            is_active = (p == active_page)
            tabs_info.append({
                "index": i,
                "title": p.title() or "Untitled",
                "url": p.url,
                "is_active": is_active,
            })
        return tabs_info

    @staticmethod
    def switch_to_tab(context: BrowserContext, index: int) -> Page:
        """Brings the tab at the specified index to front and returns it."""
        pages = context.pages
        if 0 <= index < len(pages):
            target_page = pages[index]
            target_page.bring_to_front()
            return target_page
        else:
            raise IndexError(f"Tab index #{index} out of range (Total open tabs: {len(pages)})")

    @staticmethod
    def create_new_tab(context: BrowserContext, url: Optional[str] = None) -> Page:
        """Opens a new tab in BrowserContext, navigates to url if provided, and brings it to front."""
        page = context.new_page()
        if url:
            page.goto(url)
        page.bring_to_front()
        return page

    @staticmethod
    def close_tab(context: BrowserContext, index: Optional[int] = None, active_page: Optional[Page] = None) -> Page:
        """Safely closes the target tab, ensuring at least one tab or an about:blank page remains open."""
        pages = context.pages
        if not pages:
            page = context.new_page()
            return page

        if index is not None:
            if 0 <= index < len(pages):
                target_page = pages[index]
            else:
                raise IndexError(f"Tab index #{index} out of range (Total open tabs: {len(pages)})")
        else:
            target_page = active_page if (active_page and active_page in pages) else pages[-1]

        # Ensure at least one tab or an about:blank page remains open
        if len(pages) <= 1:
            replacement = context.new_page()
            replacement.goto("about:blank")
            target_page.close()
            replacement.bring_to_front()
            return replacement

        target_page.close()
        remaining = context.pages
        new_active = remaining[-1]
        new_active.bring_to_front()
        return new_active
