"""WebPilot Engine: Autonomous Multi-Tier Browser Automation Engine & AI Agent Web Runtime."""

from __future__ import annotations

__version__ = "2.6.9"
__author__ = "Abdulkarim Salih & WebPilot Core Team"

__license__ = "MIT"

# Programmatic Python Client Facade
from webpilot.client import WebPilot

# CLI Commands
from cli_commands.tab_cmd import tab_cmd

# Core Engine & Builder Facades
from engine import UniversalFormEngine
from builder import BrowserContextEnvelopeBuilder, FormPayloadBuilder

# Supervisor Client & Contracts
from supervisor.client import SupervisorClient
from supervisor.contracts import SupervisorActionRequest, SupervisorActionResponse

# Models & Settings
from config.settings import Settings, get_settings
from core.models import (
    DeviceProfile,
    InspectionResult,
    InputField,
    DropdownField,
    ChoiceGroup,
    FileUploadField,
    ActionButton,
)

# Aliases for idiomatic naming
WebPilotEngine = UniversalFormEngine

__all__ = [
    "WebPilot",
    "WebPilotEngine",
    "UniversalFormEngine",
    "FormPayloadBuilder",
    "BrowserContextEnvelopeBuilder",
    "SupervisorClient",
    "SupervisorActionRequest",
    "SupervisorActionResponse",
    "Settings",
    "get_settings",
    "DeviceProfile",
    "InspectionResult",
    "InputField",
    "DropdownField",
    "ChoiceGroup",
    "FileUploadField",
    "ActionButton",
    "tab_cmd",
    "__version__",
]
