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
