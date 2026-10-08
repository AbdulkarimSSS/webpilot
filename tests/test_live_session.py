"""Integration test for LiveSessionManager and persistent CDP browser."""

import os
import subprocess
import sys
import time
import urllib.request
import pytest
from playwright.sync_api import sync_playwright

from adapters.live_session_manager import LiveSessionManager, DEFAULT_CDP_PORT


@pytest.mark.skipif(sys.platform != "win32", reason="WMI is only available on Windows")
def test_wmi_launch():
    """Verify _launch_wmi_process returns a real PID."""
    p = sync_playwright().start()
    exe = p.chromium.executable_path
    p.stop()
    cmd = f'"{exe}" --remote-debugging-port=9229 --headless=new --no-first-run'
    pid = LiveSessionManager._launch_wmi_process(cmd)
    assert pid is not None
    assert pid > 0
    # Clean up
    subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def test_persistent_session_lifecycle():
    """Verify persistent browser launches, accepts CDP connections, and remains alive after detach."""
    # 1. Clean up any existing session
    LiveSessionManager.terminate_session()

    p = sync_playwright().start()
    exe_path = p.chromium.executable_path

    # 2. Launch persistent browser
    pid, port = LiveSessionManager.launch_persistent_chrome(
        executable_path=exe_path,
        port=DEFAULT_CDP_PORT,
        headless=True,
        timeout_seconds=300,
    )
    assert pid is not None
    assert port == DEFAULT_CDP_PORT
    assert LiveSessionManager.is_cdp_port_active(port) is True

    # 3. Client 1 attaches, opens a tab, and detaches
    b1 = p.chromium.connect_over_cdp(f"http://127.0.0.1:{port}")
    assert b1.is_connected() is True
    ctx1 = b1.contexts[0]
    page1 = ctx1.new_page() if len(ctx1.pages) == 0 else ctx1.pages[0]
    page1.goto("https://example.com")
    assert "Example" in page1.title()

    # Detach Client 1
    b1.close()  # In Playwright CDP, browser.close() disconnects without killing the server
    p.stop()

    time.sleep(1)

    # 4. Verify browser process and port are STILL active
    assert LiveSessionManager.is_cdp_port_active(port) is True

    # 5. Client 2 attaches and sees the open page
    p2 = sync_playwright().start()
    b2 = p2.chromium.connect_over_cdp(f"http://127.0.0.1:{port}")
    ctx2 = b2.contexts[0]
    assert len(ctx2.pages) > 0
    non_blank = [pg for pg in ctx2.pages if "example.com" in pg.url]
    assert len(non_blank) > 0

    b2.close()
    p2.stop()

    # 6. Clean termination
    terminated = LiveSessionManager.terminate_session()
    assert terminated is True
    time.sleep(1)
    assert LiveSessionManager.is_cdp_port_active(port) is False
