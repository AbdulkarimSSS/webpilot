"""Filesystem safety and path confinement utilities."""

from __future__ import annotations

import os
import sys
from core.exceptions import ValidationError

SENSITIVE_TARGETS = (
    "/.ssh",
    "\\.ssh",
    "/.aws",
    "\\.aws",
    "/.gnupg",
    "\\.gnupg",
    "/.webpilot",
    "\\.webpilot",
    "/etc/shadow",
    "/etc/passwd",
    "/etc/sudoers",
    "/etc/master.passwd",
    "\\windows\\system32",
    "/windows/system32",
    "\\windows\\system32\\config",
)


def validate_safe_path(path: str, for_write: bool = False) -> str:
    """Validates that a path does not target sensitive credential stores or protected system roots."""
    if not path or not path.strip():
        raise ValidationError("Empty file path specified.")

    clean_path = os.path.abspath(os.path.expanduser(path.strip()))
    norm_path = os.path.normpath(clean_path).lower()

    for sensitive in SENSITIVE_TARGETS:
        norm_sensitive = os.path.normpath(sensitive).lower()
        stripped_sensitive = os.path.normpath(sensitive.strip("/\\")).lower()
        if (
            norm_sensitive in norm_path
            or norm_path.endswith(stripped_sensitive)
            or f"{os.sep}{stripped_sensitive}" in norm_path
        ):
            raise ValidationError(
                f"Security restriction: access to protected or sensitive path '{path}' is strictly prohibited."
            )

    return clean_path
