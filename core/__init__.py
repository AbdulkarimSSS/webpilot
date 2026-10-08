"""Core package for universal web applier."""

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
)
from core.exceptions import (
    UniversalApplierError,
    ConfigurationError,
    ValidationError,
    AutomationError,
    ElementNotFoundError,
    InteractionTimeoutError,
    DocumentUploadError,
    AuthenticationError,
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
    "UniversalApplierError",
    "ConfigurationError",
    "ValidationError",
    "AutomationError",
    "ElementNotFoundError",
    "InteractionTimeoutError",
    "DocumentUploadError",
    "AuthenticationError",
]
