"""Inactivity watchdog timer for autonomous worker process resource management."""

from __future__ import annotations

import threading
import time
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from subprocess import Popen


class InactivityWatchdog:
    """Monitors worker process inactivity and terminates idle workers to free 100% of browser RAM."""

    def __init__(
        self,
        get_last_active_time: Callable[[], float],
        get_worker_process: Callable[[], Optional[Popen]],
        terminate_worker: Callable[[], None],
        timeout_seconds: int = 1800,
        interval_seconds: int = 15,
    ):
        self.get_last_active_time = get_last_active_time
        self.get_worker_process = get_worker_process
        self.terminate_worker = terminate_worker
        self.timeout_seconds = timeout_seconds
        self.interval_seconds = interval_seconds
        self._is_running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)

    def start(self) -> None:
        """Starts the background watchdog sentinel thread."""
        self._thread.start()

    def stop(self) -> None:
        """Stops the watchdog loop."""
        self._is_running = False

    def _loop(self) -> None:
        while self._is_running:
            try:
                time.sleep(self.interval_seconds)
                if not self._is_running:
                    break
                worker = self.get_worker_process()
                if worker and worker.poll() is None:
                    idle = time.time() - self.get_last_active_time()
                    if idle > self.timeout_seconds:
                        print(f"[*] Inactivity watchdog triggered ({idle:.0f}s idle). Terminating Worker to release RAM.")
                        self.terminate_worker()
            except Exception as exc:
                import logging
                logging.debug("InactivityWatchdog check suppressed error: %s", exc)
                time.sleep(self.interval_seconds)
