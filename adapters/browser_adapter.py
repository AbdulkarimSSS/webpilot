"""Playwright browser lifecycle and persistent live session adapter."""

from __future__ import annotations

import os
import subprocess
import sys
from typing import Any, Dict, List, Optional
from playwright.sync_api import sync_playwright, Browser, BrowserContext, Page, Playwright

from adapters.base import BrowserAdapterProtocol
from adapters.live_session_manager import (
    LiveSessionManager,
    DEFAULT_CDP_PORT,
    DEFAULT_INACTIVITY_TIMEOUT_SECONDS,
)
from adapters.envelope_builder import BrowserContextEnvelopeBuilder
from common.cookies import load_and_sanitize_cookies
from common.logging import log_event
from config.settings import Settings, get_settings, load_device_profile
from constants.timeouts import PAUSE_DOM_CONTENT_LOADED_MS
from core.exceptions import AutomationError, NavigationError
from core.models import DeviceProfile


class BrowserAdapter(BrowserAdapterProtocol):
    """Encapsulates Playwright Chromium browser and persistent CDP context lifecycle."""

    def __init__(
        self,
        headless: Optional[bool] = None,
        settings: Optional[Settings] = None,
        device_profile: Optional[DeviceProfile] = None,
        keep_alive: bool = False,
        close_session: bool = False,
        timeout_minutes: Optional[int] = None,
        tab_index: Optional[int] = None,
        strip_header: bool = False,
        session_name: Optional[str] = None,
    ):
        self.settings = settings or get_settings()
        self.device_profile = device_profile or load_device_profile()
        self.headless = headless if headless is not None else self.settings.headless
        self.keep_alive = keep_alive
        self.close_session = close_session
        self.timeout_minutes = timeout_minutes if timeout_minutes is not None else 30
        self.tab_index = tab_index
        self.strip_header: bool = strip_header or getattr(self.settings, "strip_header", False)
        self.session_name: Optional[str] = session_name
        self._last_printed_url: Optional[str] = None

        self._pw: Optional[Playwright] = None
        self.browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None
        self.browser_pid: Optional[int] = None
        self.cdp_port: Optional[int] = None
        self.is_persistent: bool = False

    @property
    def context(self) -> Optional[BrowserContext]:
        """Active BrowserContext."""
        return self._context

    @property
    def page(self) -> Optional[Page]:
        """Active Page instance."""
        return self._page

    @page.setter
    def page(self, p: Page) -> None:
        self._page = p
        if p:
            self._attach_default_dialog_handler(p)

    def _attach_default_dialog_handler(self, target_page: Page) -> None:
        """Handles browser modal dialogs (alert, confirm, prompt) preventing freeze and logging prompt text (WP-109)."""
        if not target_page:
            return

        def _on_dialog(d: Any) -> None:
            try:
                d_type = getattr(d, "type", "alert")
                d_msg = getattr(d, "message", "")
                d_def = getattr(d, "default_value", "")
                print(f"[*] Browser {d_type} dialog encountered: '{d_msg}' (default: '{d_def}')", flush=True)
                if hasattr(d, "accept"):
                    d.accept(prompt_text=d_def)
            except Exception:
                pass

        try:
            target_page.on("dialog", _on_dialog)
        except Exception:
            pass

    def print_browser_telemetry(self) -> None:
        """Prints a structured telemetry card for the browser process."""
        if self.strip_header:
            return
        pid_str = str(self.browser_pid) if self.browser_pid else "In-Process"
        port_str = f"127.0.0.1:{self.cdp_port}" if self.cdp_port else "Local Native"
        mode_str = "PERSISTENT (Live Session)" if self.is_persistent else "ISOLATED (Single-Run)"
        timeout_str = f"{self.timeout_minutes} mins" if self.timeout_minutes > 0 else "Infinite"

        print("\n" + "═" * 70)
        print(" 🌐 BROWSER PROCESS & ENGINE TELEMETRY")
        print("═" * 70)
        print(f" • Process ID (PID)  : {pid_str}")
        print(f" • Engine / Runtime  : Chromium (Headless: {self.headless})")
        print(f" • Viewport / Device : {self.device_profile.viewport_width}x{self.device_profile.viewport_height} ({self.device_profile.device_name})")
        print(f" • CDP Endpoint      : {port_str}")
        print(f" • Session Lifecycle : {mode_str} | Inactivity Timeout: {timeout_str}")
        print("═" * 70)

    def print_page_telemetry(self) -> None:
        """Prints a structured telemetry card for the current active page."""
        if not self._page or not self._context:
            return

        url = self._page.url or "about:blank"
        if self.strip_header:
            if url and url != self._last_printed_url and url != "about:blank":
                print(f"[*] URL: {url}")
                self._last_printed_url = url
            return

        self._last_printed_url = url
        active_idx = self.get_active_tab_index()
        total_tabs = len(self._context.pages)
        title = self._page.title() or "Untitled"

        print(" 📄 ACTIVE PAGE & TAB TELEMETRY")
        print("─" * 70)
        idx_str = f"#{active_idx}" if active_idx >= 0 else "N/A"
        print(f" • Active Tab Index  : {idx_str} (Total Open Tabs: {total_tabs})")
        print(f" • Page Title        : {title}")
        print(f" • Active URL        : {url}")
        print("═" * 70 + "\n")

    def get_active_tab_index(self) -> int:
        """Returns the index of the currently active page in context.pages."""
        from adapters.tab_manager import TabManager
        return TabManager.get_active_tab_index(self._context, self._page)

    def list_open_tabs(self) -> List[Dict[str, Any]]:
        """Returns a list of dictionaries describing all open tabs in the active browser."""
        from adapters.tab_manager import TabManager
        return TabManager.list_open_tabs(self._context, self._page)

    def switch_to_tab(self, index: int) -> Page:
        """Switches active page to the specified tab index."""
        if self._context is None:
            raise AutomationError("Browser context not initialized.")
        from adapters.tab_manager import TabManager
        self._page = TabManager.switch_to_tab(self._context, index)
        print(f"[*] Switched to Tab #{index}: '{self._page.title()}' ({self._page.url})")
        return self._page

    def create_new_tab(self, url: Optional[str] = None) -> Page:
        """Opens a new tab in BrowserContext, navigates to url if provided, and brings it to front."""
        if self._context is None:
            raise AutomationError("Browser context not initialized.")
        from adapters.tab_manager import TabManager
        self._page = TabManager.create_new_tab(self._context, url)
        return self._page

    def close_tab(self, index: Optional[int] = None) -> None:
        """Safely closes the target tab, ensuring at least one tab remains open."""
        if self._context is None:
            raise AutomationError("Browser context not initialized.")
        from adapters.tab_manager import TabManager
        self._page = TabManager.close_tab(self._context, index=index, active_page=self._page)

    def _ensure_browser_binaries(self) -> None:
        """Verifies Chromium is installed; if not, automatically downloads it or shows a clear error."""
        needs_install = False
        try:
            exec_path = self._pw.chromium.executable_path
            if not exec_path or not os.path.exists(exec_path):
                needs_install = True
        except Exception:
            needs_install = True

        if needs_install:
            print("\n" + "═" * 70)
            print(" 🚀 WEBPILOT | INITIAL BROWSER SETUP")
            print(" [*] Playwright Chromium binaries not found on this system.")
            print(" [*] Automatically downloading Chromium browser (one-time setup)...")
            print("═" * 70)
            try:
                cmd = [sys.executable, "-m", "playwright", "install", "chromium"]
                subprocess.run(cmd, check=True)
                print("[✓] Chromium installed successfully!")
            except Exception as exc:
                err_banner = (
                    "\n" + "═" * 70 + "\n"
                    " ❌ WEBPILOT ERROR: CHROMIUM BROWSER NOT INSTALLED\n"
                    " " + "═" * 35 + "\n"
                    " WebPilot requires Chromium to operate websites.\n"
                    " Automatic installation failed (offline or network restriction).\n\n"
                    " Please run the following command manually to install the browser:\n\n"
                    "     playwright install chromium\n"
                    "     or\n"
                    "     wp install\n\n"
                    f" Details: {exc}\n"
                    "═" * 70 + "\n"
                )
                print(err_banner, file=sys.stderr)
                raise RuntimeError("Chromium browser is not installed. Please run: wp install") from None

    def start(self, cookies_path: Optional[str] = None) -> None:
        """Starts browser context or connects to existing persistent live session."""
        if self.close_session:
            terminated = LiveSessionManager.terminate_session(self.session_name)
            if terminated:
                print(f"[✓] Successfully terminated live browser session '{self.session_name or 'default'}' and killed process.")
            else:
                print(f"[*] No active live browser session '{self.session_name or 'default'}' was found to terminate.")
            return

        self._pw = sync_playwright().start()
        self._ensure_browser_binaries()

        target_port = LiveSessionManager.get_session_cdp_port(self.session_name)
        existing_session = LiveSessionManager.load_session_state(self.session_name)
        should_use_persistent = self.keep_alive or (existing_session is not None)
        log_event("info", "Session check", {
            "session": self.session_name or "default",
            "existing": existing_session is not None,
            "port_active": LiveSessionManager.is_cdp_port_active(target_port),
        })

        if should_use_persistent:
            self.is_persistent = True
            timeout_sec = self.timeout_minutes * 60

            if existing_session and LiveSessionManager.is_cdp_port_active(existing_session.get("port", target_port)):
                # Connect to existing running browser
                self.cdp_port = existing_session.get("port", target_port)
                self.browser_pid = existing_session.get("pid")
                LiveSessionManager.touch_session(self.session_name)
            else:
                # Launch new persistent browser instance
                exec_path = self._pw.chromium.executable_path
                pid, port = LiveSessionManager.launch_persistent_chrome(
                    executable_path=exec_path,
                    port=target_port,
                    headless=self.headless,
                    viewport_width=self.device_profile.viewport_width,
                    viewport_height=self.device_profile.viewport_height,
                    user_agent=self.device_profile.user_agent,
                    timeout_seconds=timeout_sec,
                    session_name=self.session_name,
                )
                self.browser_pid = pid
                self.cdp_port = port

            # Connect via Playwright CDP
            self.browser = self._pw.chromium.connect_over_cdp(f"http://127.0.0.1:{self.cdp_port}")
            if len(self.browser.contexts) > 0:
                self._context = self.browser.contexts[0]
            else:
                builder = BrowserContextEnvelopeBuilder(
                    profile=self.device_profile,
                    settings=self.settings,
                )
                options = builder.build_context_envelope()
                self._context = self.browser.new_context(**options)

            # Determine active page
            if len(self._context.pages) > 0:
                if self.tab_index is not None and 0 <= self.tab_index < len(self._context.pages):
                    self._page = self._context.pages[self.tab_index]
                else:
                    non_blank = [
                        p for p in self._context.pages
                        if p.url and not p.url.startswith("chrome://") and p.url not in ("about:blank",)
                    ]
                    if non_blank:
                        self._page = non_blank[-1]
                    else:
                        self._page = self._context.pages[-1]
            else:
                self._page = self._context.new_page()

        else:
            # Isolated single-run execution
            self.is_persistent = False
            self.browser = self._pw.chromium.launch(
                headless=self.headless,
                args=["--disable-blink-features=AutomationControlled"],
            )
            try:
                from common.process_manager import get_process_manager
                children = get_process_manager().get_child_pids(os.getpid())
                if children:
                    self.browser_pid = children[0]
            except Exception:
                pass

            builder = BrowserContextEnvelopeBuilder(
                profile=self.device_profile,
                settings=self.settings,
            )
            options = builder.build_context_envelope()
            self._context = self.browser.new_context(**options)
            self._page = self._context.new_page()

        # Stealth evasions & Closed Shadow DOM hook (WP-007, WP-015)
        # Dialog handling
        if self._context:
            try:
                self._context.on("page", self._attach_default_dialog_handler)
                if self._page:
                    self._attach_default_dialog_handler(self._page)
            except Exception:
                pass
            try:
                self._context.add_init_script("""
                    // Standard window.chrome runtime stub
                    if (!window.chrome) {
                        window.chrome = { runtime: {} };
                    }
                """)
            except Exception:
                pass

        # Load cookies if requested
        effective_cookies = cookies_path or self.settings.cookies_path
        if effective_cookies and os.path.isfile(effective_cookies) and self._context:
            try:
                sanitized = load_and_sanitize_cookies(effective_cookies)
                self._context.add_cookies(sanitized)
                print(f"[*] Successfully loaded and sanitized {len(sanitized)} cookies.")
            except Exception as exc:
                print(f"[!] Warning loading cookies: {exc}")

        # Print initial telemetry
        self.print_browser_telemetry()
        self.print_page_telemetry()

    def stop(self) -> None:
        """Stops browser or cleanly detaches client while preserving live session."""
        if self.is_persistent and not self.close_session:
            # Cleanly detach Playwright client while preserving live session
            LiveSessionManager.touch_session(self.session_name)
            self.browser = None
            if self._pw:
                try:
                    self._pw.stop()
                except Exception:
                    pass
                self._pw = None
            self._context = None
            self._page = None
            print(f"[INFO] Browser session '{self.session_name or 'default'}' kept alive in background (PID: {self.browser_pid}, Port: {self.cdp_port}).")
            print(f"[INFO] You can run subsequent commands on this session using --tab or --keep-alive.")
        else:
            # Full termination
            if self.browser:
                try:
                    self.browser.close()
                except Exception:
                    pass
                self.browser = None
            if self._pw:
                try:
                    self._pw.stop()
                except Exception:
                    pass
                self._pw = None
            self._context = None
            self._page = None
            LiveSessionManager.terminate_session(self.session_name)
            # Clean leftover temp profiles (WPB-009)
            LiveSessionManager.cleanup_temp_profiles(max_age_seconds=0)

    def navigate(self, url: str, wait_timeout: Optional[int] = None) -> None:
        """Navigates to URL and waits for DOM content loaded with transient retry."""
        if self._page is None:
            raise AutomationError("Browser not started. Call start() first.")
        from common.paths import validate_safe_url
        url = validate_safe_url(url) or ""
        if self._page.url == url:
            print(f"[*] Page is already on target URL: {url}")
            self.print_page_telemetry()
            return
        timeout = wait_timeout if wait_timeout is not None else min(self.settings.default_timeout_ms, 20000)
        max_attempts = 2
        for attempt in range(1, max_attempts + 1):
            try:
                resp = self._page.goto(url, timeout=timeout, wait_until="domcontentloaded")
                if resp is not None and resp.status in (502, 503, 504) and attempt < max_attempts:
                    print(f"[*] Transient HTTP {resp.status} on '{url}'. Retrying in 500ms (attempt {attempt}/{max_attempts})...")
                    self._page.wait_for_timeout(500)
                    continue
                break
            except Exception as exc:
                err_msg = str(exc).lower()
                is_download = "download is starting" in err_msg or ("net::err_aborted" in err_msg and "download" in err_msg)
                if is_download:
                    print(f"[*] Detected download triggered by navigation to: {url}")
                    return
                # Do NOT retry hard timeouts on unroutable hosts (WPB-001)
                is_timeout = "timeout" in err_msg or "timed out" in err_msg
                if attempt < max_attempts and not is_timeout and any(x in err_msg for x in ("err_connection_reset", "err_network_changed")):
                    print(f"[*] Transient error navigating to '{url}': {exc}. Retrying in 500ms...")
                    self._page.wait_for_timeout(500)
                    continue
                fatal_indicators = (
                    "err_name_not_resolved",
                    "err_connection_refused",
                    "err_address_unreachable",
                    "err_connection_reset",
                    "err_invalid_url",
                    "cannot navigate to invalid url",
                    "net::err_",
                    "timeout",
                    "timed out",
                )
                if any(ind in err_msg for ind in fatal_indicators) or (
                    self._page.url in ("", "about:blank") and url not in ("", "about:blank")
                ):
                    raise NavigationError(f"Navigation to '{url}' failed: {exc}") from exc
                print(f"[!] Notice: Navigation event delayed by tracker/network: {exc}. Continuing with page state...")
                break
        self._page.wait_for_timeout(PAUSE_DOM_CONTENT_LOADED_MS)

        # Verify post-redirect target URL against SSRF / safe URL rules (WPB-012)
        final_url = self._page.url
        if final_url and final_url not in ("", "about:blank") and final_url != url:
            try:
                validate_safe_url(final_url)
            except Exception as exc:
                try:
                    self._page.goto("about:blank")
                except Exception:
                    pass
                raise NavigationError(f"Security restriction: redirected URL '{final_url}' violates safe URL policy: {exc}") from exc

        self.print_page_telemetry()


    def capture_screenshot(self, output_path: str, full_page: bool = False, allow_overwrite: bool = True) -> None:
        """Captures a screenshot to the specified disk path with overwrite validation."""
        if self._page is None:
            raise AutomationError("Browser not started.")
        from common.paths import validate_safe_path
        safe_path = validate_safe_path(output_path, for_write=True, allow_overwrite=allow_overwrite)
        os.makedirs(os.path.dirname(os.path.abspath(safe_path)), exist_ok=True)
        self._page.screenshot(path=safe_path, full_page=full_page)
