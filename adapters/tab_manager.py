import time
from typing import Any, Dict, List, Optional
from playwright.sync_api import BrowserContext, Page


class TabTelemetry:
    """Stores lifecycle timestamps and metadata for a specific Playwright Page."""
    def __init__(self, page_id: int, timeout_minutes: int = 30):
        self.page_id = page_id
        self.created_at = time.time()
        self.last_activity = time.time()
        self.state = "IDLE"  # IDLE, LOADING, READY
        self.loading_started: Optional[float] = None
        self.tab_timeout_minutes = timeout_minutes

    def mark_loading(self) -> None:
        self.state = "LOADING"
        self.loading_started = time.time()
        self.last_activity = time.time()

    def mark_idle(self) -> None:
        self.state = "IDLE"
        self.loading_started = None
        self.last_activity = time.time()

    def touch(self) -> None:
        self.last_activity = time.time()


class TabManager:
    """Manages browser tab enumeration, active tab tracking, safe switching, and inactivity reaping."""

    # Page id (id(page)) -> TabTelemetry
    _telemetry_registry: Dict[int, TabTelemetry] = {}
    DEFAULT_TAB_TIMEOUT_MINUTES: int = 30

    @classmethod
    def get_or_create_telemetry(cls, page: Page, timeout_minutes: Optional[int] = None) -> TabTelemetry:
        """Retrieves or registers lifecycle telemetry for a Page."""
        pid = id(page)
        if pid not in cls._telemetry_registry:
            to_val = timeout_minutes if timeout_minutes is not None else cls.DEFAULT_TAB_TIMEOUT_MINUTES
            telem = TabTelemetry(pid, timeout_minutes=to_val)
            cls._telemetry_registry[pid] = telem
            cls._attach_page_listeners(page, telem)
        elif timeout_minutes is not None:
            cls._telemetry_registry[pid].tab_timeout_minutes = timeout_minutes
        return cls._telemetry_registry[pid]

    @classmethod
    def _attach_page_listeners(cls, page: Page, telem: TabTelemetry) -> None:
        """Hooks page navigation and lifecycle events to update telemetry in real time."""
        try:
            def on_load(_: Page) -> None:
                telem.mark_idle()

            def on_domcontentloaded(_: Page) -> None:
                telem.mark_idle()

            def on_framenavigated(_: Any) -> None:
                telem.touch()

            def on_close(_: Page) -> None:
                cls._telemetry_registry.pop(id(page), None)

            if hasattr(page, "on"):
                page.on("load", on_load)
                page.on("domcontentloaded", on_domcontentloaded)
                page.on("framenavigated", on_framenavigated)
                page.on("close", on_close)
        except Exception:
            pass

    @classmethod
    def format_duration(cls, seconds: float) -> str:
        """Formats duration into human-readable shorthand (e.g. 15s, 4m 12s, 1h 20m)."""
        secs = max(0, int(seconds))
        if secs < 60:
            return f"{secs}s ago"
        mins = secs // 60
        rem_secs = secs % 60
        if mins < 60:
            return f"{mins}m {rem_secs}s ago" if rem_secs > 0 else f"{mins}m ago"
        hrs = mins // 60
        rem_mins = mins % 60
        return f"{hrs}h {rem_mins}m ago" if rem_mins > 0 else f"{hrs}h ago"

    @staticmethod
    def get_active_tab_index(context: Optional[BrowserContext], active_page: Optional[Page]) -> int:
        """Returns the 0-based index of the currently active page in context.pages, or -1 if unknown."""
        if not context or not active_page:
            return -1
        try:
            return context.pages.index(active_page)
        except (ValueError, Exception):
            return -1

    @classmethod
    def list_open_tabs(cls, context: Optional[BrowserContext], active_page: Optional[Page]) -> List[Dict[str, Any]]:
        """Returns a list of dictionaries describing all open tabs in the browser context with rich telemetry."""
        if not context:
            return []

        # First, reap any inactive tabs that exceeded their timeout
        cls.reap_inactive_tabs(context, active_page=active_page)

        now = time.time()
        tabs_info = []
        for i, p in enumerate(context.pages):
            try:
                if hasattr(p, "is_closed") and p.is_closed():
                    continue
                title = p.title() or "Untitled"
                url = p.url
                is_active = (p == active_page)
                telem = cls.get_or_create_telemetry(p)

                # Evaluate live state
                open_since_sec = now - telem.created_at
                last_act_sec = now - telem.last_activity
                state_desc = telem.state
                if telem.state == "LOADING" and telem.loading_started:
                    load_sec = int(now - telem.loading_started)
                    state_desc = f"LOADING (loading since {load_sec}s)"

                tabs_info.append({
                    "index": i,
                    "title": title,
                    "url": url,
                    "is_active": is_active,
                    "state": state_desc,
                    "open_since": cls.format_duration(open_since_sec),
                    "open_since_seconds": int(open_since_sec),
                    "last_activity": cls.format_duration(last_act_sec),
                    "last_activity_seconds": int(last_act_sec),
                    "tab_timeout_minutes": telem.tab_timeout_minutes,
                })
            except Exception:
                continue
        return tabs_info

    @classmethod
    def reap_inactive_tabs(
        cls,
        context: Optional[BrowserContext],
        active_page: Optional[Page] = None,
    ) -> List[int]:
        """Automatically closes background tabs that exceeded their inactivity tab_timeout.

        Guarantees that at least one tab or an about:blank tab remains open so the browser doesn't die.
        """
        if not context or len(context.pages) <= 1:
            return []

        now = time.time()
        reaped_indices: List[int] = []
        pages = list(context.pages)
        for i, p in enumerate(pages):
            try:
                if p == active_page:
                    continue  # Never reap the actively focused page
                if hasattr(p, "is_closed") and p.is_closed():
                    continue
                telem = cls.get_or_create_telemetry(p)
                timeout_sec = telem.tab_timeout_minutes * 60
                if timeout_sec > 0 and (now - telem.last_activity) > timeout_sec:
                    # Tab exceeded timeout
                    if len(context.pages) > 1:
                        p.close()
                        cls._telemetry_registry.pop(id(p), None)
                        reaped_indices.append(i)
            except Exception:
                continue

        return reaped_indices

    @classmethod
    def set_tab_timeout(cls, context: BrowserContext, index: int, timeout_minutes: int) -> bool:
        """Sets a custom inactivity timeout in minutes for a specific tab."""
        pages = context.pages
        if 0 <= index < len(pages):
            p = pages[index]
            telem = cls.get_or_create_telemetry(p)
            telem.tab_timeout_minutes = max(0, timeout_minutes)
            return True
        return False

    @staticmethod
    def switch_to_tab(context: BrowserContext, index: int) -> Page:
        """Brings the tab at the specified index to front and returns it."""
        pages = context.pages
        if 0 <= index < len(pages):
            target_page = pages[index]
            target_page.bring_to_front()
            # Touch activity
            TabManager.get_or_create_telemetry(target_page).touch()
            return target_page
        else:
            raise IndexError(f"Tab index #{index} out of range (Total open tabs: {len(pages)})")

    @classmethod
    def create_new_tab(
        cls,
        context: BrowserContext,
        url: Optional[str] = None,
        tab_timeout_minutes: Optional[int] = None,
    ) -> Page:
        """Opens a new tab in BrowserContext, navigates to url if provided, and brings it to front."""
        page = context.new_page()
        telem = cls.get_or_create_telemetry(page, timeout_minutes=tab_timeout_minutes)
        if url:
            telem.mark_loading()
            try:
                page.goto(url)
            finally:
                telem.mark_idle()
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

        TabManager._telemetry_registry.pop(id(target_page), None)

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
