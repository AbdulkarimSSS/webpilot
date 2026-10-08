"""Typed exception hierarchy for Universal Web Applier."""

class UniversalApplierError(Exception):
    """Base exception for all universal web applier domain errors."""
    pass

class ConfigurationError(UniversalApplierError):
    """Raised when configuration values, files, or device profiles are missing or invalid."""
    pass

class ValidationError(UniversalApplierError):
    """Raised when input data, payloads, or schema validation fails."""
    pass

class AutomationError(UniversalApplierError):
    """Raised when web automation actions fail unexpectedly."""
    pass

class ElementNotFoundError(AutomationError):
    """Raised when an expected DOM element cannot be located."""
    pass

class InteractionTimeoutError(AutomationError):
    """Raised when an action or wait condition exceeds its deadline."""
    pass

class DocumentUploadError(AutomationError):
    """Raised when document attachment fails."""
    pass

class AuthenticationError(AutomationError):
    """Raised when login or credential submission fails."""
    pass
