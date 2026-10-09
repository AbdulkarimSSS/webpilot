"""Data contracts for Master Supervisor, Worker Process, and CLI Client."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class SupervisorActionRequest:
    """Action payload sent from CLI or Shell to the Master Supervisor."""
    action: str  # 'apply', 'inspect', 'list_tabs', 'switch_tab', 'restart_worker', 'status', 'stop'
    url: Optional[str] = None
    data_path: Optional[str] = None
    fill_arguments: List[str] = field(default_factory=list)
    press_buttons: List[str] = field(default_factory=list)
    upload_files: List[str] = field(default_factory=list)
    cookies_path: Optional[str] = None
    submit: bool = False
    screenshot_path: Optional[str] = None
    tab_index: Optional[int] = None
    unpack_options: bool = False
    headed: bool = False
    auto_inspect: bool = True
    timeout_minutes: int = 30

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> SupervisorActionRequest:
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class SupervisorActionResponse:
    """Standardized response returned by Master Supervisor to CLI or Shell."""
    success: bool
    action: str
    message: str = ""
    browser_pid: Optional[int] = None
    worker_pid: Optional[int] = None
    active_tab_index: Optional[int] = None
    active_url: Optional[str] = None
    active_title: Optional[str] = None
    total_tabs: int = 0
    tabs: List[Dict[str, Any]] = field(default_factory=list)
    telemetry: Dict[str, Any] = field(default_factory=dict)
    schema: Optional[Dict[str, Any]] = None
    confirmed_fields: List[Any] = field(default_factory=list)
    unconfirmed_fields: List[Any] = field(default_factory=list)
    failed_fields: List[Any] = field(default_factory=list)
    validation_errors: List[str] = field(default_factory=list)
    reactive_event: Optional[Dict[str, Any]] = None
    output_lines: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> SupervisorActionResponse:
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})
