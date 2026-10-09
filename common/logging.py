"""Structured logging and sensitive data redaction utilities."""

import re
from typing import Any, Dict, List, Set, Union

SENSITIVE_KEY_PATTERNS: Set[str] = {
    "password",
    "secret",
    "token",
    "api_key",
    "apikey",
    "national_id",
    "iqama",
    "ssn",
    "credentials",
    "auth",
    "cookie",
}


def is_sensitive_key(key: Any) -> bool:
    """Returns True if key name matches known sensitive credential patterns."""
    k_lower = str(key).lower().strip()
    return any(p in k_lower for p in SENSITIVE_KEY_PATTERNS)


def redact_sensitive(data: Any) -> Any:
    """Recursively redacts sensitive keys and values from dictionaries, lists, or strings."""
    if isinstance(data, dict):
        redacted = {}
        for k, v in data.items():
            k_lower = str(k).lower().strip()
            if any(p in k_lower for p in SENSITIVE_KEY_PATTERNS):
                redacted[k] = "[REDACTED]"
            else:
                redacted[k] = redact_sensitive(v)
        return redacted

    if isinstance(data, list):
        return [redact_sensitive(item) for item in data]

    if isinstance(data, tuple):
        return tuple(redact_sensitive(item) for item in data)

    if isinstance(data, str):
        # Redact patterns resembling 9-10 digit national IDs (excluding all-zeros placeholders)
        masked = re.sub(r"\b(?!0{9,10}\b)[1-9]\d{8,9}\b", "[REDACTED_ID]", data)
        # Redact email addresses
        masked = re.sub(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+", "[REDACTED_EMAIL]", masked)
        return masked

    return data


def log_event(level: str, operation: str, context: Dict[str, Any]) -> None:
    """Prints a structured log line with sensitive fields automatically redacted."""
    safe_ctx = redact_sensitive(context)
    print(f"[{level.upper()}] {operation} | {safe_ctx}")
