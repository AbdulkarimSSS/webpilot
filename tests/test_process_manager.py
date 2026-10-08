"""Unit tests for cross-platform ProcessManager abstraction."""

import os
import sys
import pytest
from common.process_manager import (
    BaseProcessManager,
    WindowsProcessManager,
    PosixProcessManager,
    get_process_manager,
    set_process_manager,
)


def test_get_process_manager_platform_type():
    """Verify get_process_manager returns the platform-appropriate manager."""
    mgr = get_process_manager()
    assert isinstance(mgr, BaseProcessManager)
    if sys.platform == "win32":
        assert isinstance(mgr, WindowsProcessManager)
    else:
        assert isinstance(mgr, PosixProcessManager)


def test_is_process_running_current_pid():
    """Verify is_process_running reports True for current active PID."""
    mgr = get_process_manager()
    assert mgr.is_process_running(os.getpid()) is True
    # Non-existent PID
    assert mgr.is_process_running(999999999) is False


def test_mock_process_manager_injection():
    """Verify custom ProcessManager can be injected for hermetic testing."""
    class MockProcessManager(BaseProcessManager):
        def launch_detached(self, cmd, cwd=None, env=None):
            return 4242

        def kill_process_tree(self, pid: int, force: bool = True) -> bool:
            return True

        def get_child_pids(self, parent_pid: int):
            return [1001, 1002]

        def is_process_running(self, pid: int) -> bool:
            return pid == 4242

    orig = get_process_manager()
    try:
        mock_mgr = MockProcessManager()
        set_process_manager(mock_mgr)
        assert get_process_manager() is mock_mgr
        assert get_process_manager().launch_detached("echo hi") == 4242
        assert get_process_manager().get_child_pids(1) == [1001, 1002]
        assert get_process_manager().kill_process_tree(4242) is True
    finally:
        set_process_manager(orig)
