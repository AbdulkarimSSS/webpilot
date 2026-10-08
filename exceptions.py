"""Backwards compatibility shim for exceptions."""

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
    "UniversalApplierError",
    "ConfigurationError",
    "ValidationError",
    "AutomationError",
    "ElementNotFoundError",
    "InteractionTimeoutError",
    "DocumentUploadError",
    "AuthenticationError",
]
