"""Backwards compatibility shim for models."""

from core.models import (
    ProxyConfig,
    DeviceProfile,
    InputField,
    DropdownField,
    ChoiceGroup,
    FileUploadField,
    ActionButton,
    InspectionResult,
    FillSummary,
    ReactiveClickOutcome,
    ApplyExecutionResult,
)

__all__ = [
    "ProxyConfig",
    "DeviceProfile",
    "InputField",
    "DropdownField",
    "ChoiceGroup",
    "FileUploadField",
    "ActionButton",
    "InspectionResult",
    "FillSummary",
    "ReactiveClickOutcome",
    "ApplyExecutionResult",
]
