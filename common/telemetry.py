"""Terminal telemetry formatting and visual banners."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from supervisor.contracts import SupervisorActionResponse


def print_telemetry_banner(resp: SupervisorActionResponse, strip_header: bool = False) -> None:
    """Renders real-time process tree telemetry across Layer 1, 2, and 3."""
    if strip_header:
        return
    if resp.browser_pid or resp.worker_pid or resp.active_url:
        print("\n" + "═" * 70)
        print(" 🚀 WEBPILOT | AUTONOMOUS BROWSER RUNTIME & SUPERVISOR TELEMETRY")
        print("═" * 70)
        if resp.worker_pid:
            print(f" • Layer 2 Worker PID   : {resp.worker_pid}")
        if resp.browser_pid:
            print(f" • Layer 3 Chromium PID : {resp.browser_pid}")
        if resp.active_tab_index is not None:
            print(f" • Active Tab Index     : Tab #{resp.active_tab_index} (Total: {resp.total_tabs})")
        if resp.active_title:
            print(f" • Active Page Title    : {resp.active_title}")
        if resp.active_url:
            print(f" • Active Page URL      : {resp.active_url}")
        print("═" * 70)
