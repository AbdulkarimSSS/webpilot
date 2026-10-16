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
    "/etc/gshadow",
    "/etc/security",
    "/etc/pam.d",
    "\\.netrc",
    "/.netrc",
    "\\.git-credentials",
    "/.git-credentials",
    "\\.bash_history",
    "/.bash_history",
    "\\.zsh_history",
    "/.zsh_history",
    "\\windows\\system32",
    "/windows/system32",
    "\\windows\\system32\\config",
)

SENSITIVE_PATTERNS = (
    "id_rsa",
    "id_ed25519",
    "id_ecdsa",
    "id_dsa",
    "supervisor.token",
)

SYSTEM_WRITE_ROOTS = (
    "/etc",
    "/usr",
    "/bin",
    "/sbin",
    "/lib",
    "/lib64",
    "/boot",
    "/dev",
    "/proc",
    "/sys",
    "c:\\windows",
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

    base_name = os.path.basename(norm_path)
    for pattern in SENSITIVE_PATTERNS:
        if pattern in base_name:
            raise ValidationError(
                f"Security restriction: access to protected key/token '{path}' is strictly prohibited."
            )

    if for_write:
        for sys_root in SYSTEM_WRITE_ROOTS:
            if norm_path == sys_root or norm_path.startswith(sys_root + os.sep) or norm_path.startswith(sys_root + "/"):
                raise ValidationError(
                    f"Security restriction: writing into system directory '{path}' is strictly prohibited."
                )

    return clean_path
