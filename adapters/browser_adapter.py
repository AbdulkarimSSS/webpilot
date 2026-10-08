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
    ):
        self.settings = settings or get_settings()
        self.device_profile = device_profile or load_device_profile()
        self.headless = headless if headless is not None else self.settings.headless
        self.keep_alive = keep_alive
        self.close_session = close_session
        self.timeout_minutes = timeout_minutes if timeout_minutes is not None else 30
        self.tab_index = tab_index

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

    def print_browser_telemetry(self) -> None:
        """Prints a structured telemetry card for the browser process."""
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

        active_idx = self.get_active_tab_index()
        total_tabs = len(self._context.pages)
        title = self._page.title() or "Untitled"
        url = self._page.url or "about:blank"

        print(" 📄 ACTIVE PAGE & TAB TELEMETRY")
        print("─" * 70)
        print(f" • Active Tab Index  : #{active_idx} (Total Open Tabs: {total_tabs})")
        print(f" • Page Title        : {title}")
        print(f" • Active URL        : {url}")
        print("═" * 70 + "\n")

    def get_active_tab_index(self) -> int:
        """Returns the index of the currently active page in context.pages."""
        if not self._context or not self._page:
            return 0
        try:
            return self._context.pages.index(self._page)
        except ValueError:
            return 0

    def list_open_tabs(self) -> List[Dict[str, Any]]:
        """Returns a list of dictionaries describing all open tabs in the active browser."""
        if not self._context:
            return []

        tabs_info = []
        for i, p in enumerate(self._context.pages):
            is_active = (p == self._page)
            tabs_info.append({
                "index": i,
                "title": p.title() or "Untitled",
                "url": p.url,
                "is_active": is_active,
            })
        return tabs_info

    def switch_to_tab(self, index: int) -> Page:
        """Switches active page to the specified tab index."""
        assert self._context is not None, "Browser context not initialized."
        pages = self._context.pages
        if 0 <= index < len(pages):
            self._page = pages[index]
            self._page.bring_to_front()
            print(f"[*] Switched to Tab #{index}: '{self._page.title()}' ({self._page.url})")
            return self._page
        else:
            raise IndexError(f"Tab index #{index} out of range (Total open tabs: {len(pages)})")

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
            terminated = LiveSessionManager.terminate_session()
            if terminated:
                print("[✓] Successfully terminated live browser session and killed process.")
            else:
                print("[*] No active live browser session was found to terminate.")
            return

        self._pw = sync_playwright().start()
        self._ensure_browser_binaries()

        existing_session = LiveSessionManager.load_session_state()
        should_use_persistent = self.keep_alive or (existing_session is not None)
        log_event("info", "Session check", {
            "existing": existing_session is not None,
            "port_active": LiveSessionManager.is_cdp_port_active(DEFAULT_CDP_PORT),
        })

        if should_use_persistent:
            self.is_persistent = True
            timeout_sec = self.timeout_minutes * 60

            if existing_session and LiveSessionManager.is_cdp_port_active(existing_session.get("port", DEFAULT_CDP_PORT)):
                # Connect to existing running browser
                self.cdp_port = existing_session.get("port", DEFAULT_CDP_PORT)
                self.browser_pid = existing_session.get("pid")
                LiveSessionManager.touch_session()
            else:
                # Launch new persistent browser instance
                exec_path = self._pw.chromium.executable_path
                pid, port = LiveSessionManager.launch_persistent_chrome(
                    executable_path=exec_path,
                    port=DEFAULT_CDP_PORT,
                    headless=self.headless,
                    viewport_width=self.device_profile.viewport_width,
                    viewport_height=self.device_profile.viewport_height,
                    user_agent=self.device_profile.user_agent,
                    timeout_seconds=timeout_sec,
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
                if sys.platform == "win32":
                    ps_c = f'(Get-CimInstance Win32_Process | Where-Object {{ $_.ParentProcessId -eq {os.getpid()} }}).ProcessId | Select-Object -First 1'
                    out = subprocess.check_output(["powershell", "-NoProfile", "-Command", ps_c], text=True).strip()
                    if out.isdigit():
                        self.browser_pid = int(out)
                else:
                    out = subprocess.check_output(["pgrep", "-P", str(os.getpid())], text=True).strip().split()
                    if out and out[0].isdigit():
                        self.browser_pid = int(out[0])
            except Exception:
                pass

            builder = BrowserContextEnvelopeBuilder(
                profile=self.device_profile,
                settings=self.settings,
            )
            options = builder.build_context_envelope()
            self._context = self.browser.new_context(**options)
            self._page = self._context.new_page()

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
            LiveSessionManager.touch_session()
            self.browser = None
            if self._pw:
                try:
                    self._pw.stop()
                except Exception:
                    pass
                self._pw = None
            self._context = None
            self._page = None
            print(f"[INFO] Browser kept alive in background (PID: {self.browser_pid}, Port: {self.cdp_port}).")
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
            LiveSessionManager.terminate_session()

    def navigate(self, url: str, wait_timeout: Optional[int] = None) -> None:
        """Navigates to URL and waits for DOM content loaded."""
        assert self._page is not None, "Browser not started. Call start() first."
        if self._page.url == url:
            print(f"[*] Page is already on target URL: {url}")
            self.print_page_telemetry()
            return
        timeout = wait_timeout if wait_timeout is not None else self.settings.default_timeout_ms
        try:
            self._page.goto(url, timeout=timeout, wait_until="domcontentloaded")
        except Exception as exc:
            print(f"[!] Notice: Navigation event delayed by tracker/network: {exc}. Continuing with page state...")
        self._page.wait_for_timeout(PAUSE_DOM_CONTENT_LOADED_MS)
        self.print_page_telemetry()

    def capture_screenshot(self, output_path: str, full_page: bool = False) -> None:
        """Captures a screenshot to the specified disk path."""
        assert self._page is not None, "Browser not started."
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        self._page.screenshot(path=output_path, full_page=full_page)
