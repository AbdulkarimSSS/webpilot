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
    "/.config",
    "\\.config",
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
    "\\.bashrc",
    "/.bashrc",
    "\\.bash_profile",
    "/.bash_profile",
    "\\.profile",
    "/.profile",
    "\\.zshrc",
    "/.zshrc",
    "\\windows\\system32",
    "/windows/system32",
    "\\windows\\system32\\config",
)

SENSITIVE_PATTERNS = (
    "id_rsa",
    "id_ed25519",
    "id_ecdsa",
    "id_dsa",
    "authorized_keys",
    "known_hosts",
    "supervisor.token",
    ".env",
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


def validate_safe_path(
    path: str,
    for_write: bool = False,
    allow_overwrite: bool = True,
) -> str:
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
            or f"/{stripped_sensitive}" in norm_path.replace("\\", "/")
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

        if not allow_overwrite and os.path.exists(clean_path):
            raise ValidationError(
                f"Security restriction: file '{path}' already exists; overwrite is not permitted."
            )

    return clean_path


def validate_safe_url(url: str | None) -> str | None:
    """Validates that a URL does not attempt Local File Inclusion (LFI) or cloud metadata SSRF."""
    if url is None:
        return None
    raw = url.strip()
    if not raw:
        return ""

    if raw in ("about:blank", "chrome://newtab"):
        return raw

    from urllib.parse import urlparse

    parsed = urlparse(raw)
    scheme = (parsed.scheme or "").lower()

    if scheme == "file":
        if os.environ.get("WEBPILOT_ALLOW_FILE_URLS") == "1":
            return raw
        raise ValidationError(
            "Security restriction: 'file://' scheme is disabled to prevent local file inclusion. Set WEBPILOT_ALLOW_FILE_URLS=1 to permit local testing."
        )

    if scheme in ("data", "javascript", "blob", "vbscript"):
        raise ValidationError(
            f"Security restriction: scheme '{scheme}:' is strictly prohibited."
        )

    if scheme not in ("http", "https"):
        raise ValidationError(
            f"Security restriction: scheme '{scheme}:' is not supported. Only http and https URLs are allowed."
        )

    hostname = (parsed.hostname or "").lower()
    if hostname in ("169.254.169.254", "metadata.google.internal", "metadata.internal"):
        raise ValidationError(
            f"Security restriction: access to cloud instance metadata at '{hostname}' is strictly prohibited."
        )

    return raw

