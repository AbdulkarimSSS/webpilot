"""WebPilot Engine alias package redirecting to webpilot for dual-naming compatibility."""

from __future__ import annotations

import sys
from webpilot import (
    WebPilot,
    WebPilotEngine,
    UniversalFormEngine,
    FormPayloadBuilder,
    BrowserContextEnvelopeBuilder,
    SupervisorClient,
    SupervisorActionRequest,
    SupervisorActionResponse,
    Settings,
    get_settings,
    DeviceProfile,
    InspectionResult,
    InputField,
    DropdownField,
    ChoiceGroup,
    FileUploadField,
    ActionButton,
    __version__,
    __author__,
    __license__,
)

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
    "__version__",
]
