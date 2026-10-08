"""Context dataclasses for flow orchestration and lifecycle management."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
from config.settings import Settings
from core.models import ApplyExecutionResult, DeviceProfile


@dataclass
class SessionContext:
    """Encapsulates browser session configuration and runtime credentials."""
    settings: Settings
    device_profile: DeviceProfile
    headless: bool = True
    cookies_path: Optional[str] = None
    keep_alive: bool = False
    close_session: bool = False
    timeout_minutes: int = 30
    tab_index: Optional[int] = None


@dataclass
class InspectionRequestContext:
    """Encapsulates all parameters for a form inspection flow."""
    url: Optional[str] = None
    output_path: Optional[str] = None
    screenshot_path: Optional[str] = None
    cookies_path: Optional[str] = None
    unpack_options: bool = False
    headed: bool = False
    config_path: Optional[str] = None
    device_profile_path: Optional[str] = None
    env_file: Optional[str] = None
    keep_alive: bool = False
    close_session: bool = False
    list_tabs: bool = False
    tab_index: Optional[int] = None
    timeout_minutes: Optional[int] = 30


@dataclass
class ApplyRequestContext:
    """Encapsulates all parameters for an automated form filling and submission flow."""
    url: Optional[str] = None
    data_path: Optional[str] = None
    fill_arguments: List[str] = field(default_factory=list)
    press_buttons: List[str] = field(default_factory=list)
    upload_files: List[str] = field(default_factory=list)
    cookies_path: Optional[str] = None
    submit: bool = False
    screenshot_path: Optional[str] = None
    headed: bool = False
    config_path: Optional[str] = None
    device_profile_path: Optional[str] = None
    env_file: Optional[str] = None
    keep_alive: bool = False
    close_session: bool = False
    list_tabs: bool = False
    tab_index: Optional[int] = None
    timeout_minutes: Optional[int] = 30
    auto_inspect: bool = True


__all__ = [
    "SessionContext",
    "InspectionRequestContext",
    "ApplyRequestContext",
    "ApplyExecutionResult",
]
