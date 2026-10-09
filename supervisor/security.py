"""Security and authentication management for Master Supervisor (Layer 1).

Generates, stores, and validates cryptographically secure access tokens.
Enforces strict user-only filesystem access permissions (POSIX 0600 / Windows ACLs)
to prevent unauthorized local processes from hijacking active browser sessions.
"""

from __future__ import annotations

import os
import secrets
import subprocess
import sys
from typing import Optional

DEFAULT_TOKEN_DIR: str = os.path.expanduser("~/.webpilot")
DEFAULT_TOKEN_FILE: str = os.path.join(DEFAULT_TOKEN_DIR, "supervisor.token")


def generate_supervisor_token() -> str:
    """Generates a high-entropy 256-bit hexadecimal security token."""
    return secrets.token_hex(32)


def get_token_file_path() -> str:
    """Returns the resolved supervisor token path."""
    return os.environ.get("WEBPILOT_SUPERVISOR_TOKEN_FILE") or DEFAULT_TOKEN_FILE


def save_supervisor_token(token: str, path: Optional[str] = None) -> str:
    """Persists token to disk with strict user-only file access permissions.

    POSIX: chmod 0600 (owner read/write only).
    Windows: icacls inheritance removal, granting explicit Full access solely to current user.
    """
    target_path = path or get_token_file_path()
    token_dir = os.path.dirname(target_path)
    if token_dir:
        os.makedirs(token_dir, exist_ok=True)

    if sys.platform != "win32":
        flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
        mode = 0o600
        fd = os.open(target_path, flags, mode)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(token.strip())
        try:
            os.chmod(target_path, 0o600)
        except Exception:
            pass
    else:
        # Windows write + ACL hardening
        with open(target_path, "w", encoding="utf-8") as f:
            f.write(token.strip())

        try:
            current_user = os.environ.get("USERNAME")
            if current_user:
                subprocess.run(
                    ["icacls", target_path, "/inheritance:r", "/grant:r", f"{current_user}:(F)"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=5,
                )
        except Exception:
            pass

    return target_path


def load_supervisor_token(path: Optional[str] = None) -> Optional[str]:
    """Retrieves token from environment override or secure token file."""
    # 1. Environment variable override (ideal for CI and containerized runners)
    env_token = os.environ.get("WEBPILOT_SUPERVISOR_TOKEN")
    if env_token:
        return env_token.strip()

    # 2. File lookup
    target_path = path or get_token_file_path()
    if os.path.isfile(target_path):
        try:
            with open(target_path, "r", encoding="utf-8") as f:
                token = f.read().strip()
                if token:
                    return token
        except Exception:
            return None
    return None


def remove_supervisor_token(path: Optional[str] = None) -> None:
    """Removes token file upon supervisor daemon teardown."""
    target_path = path or get_token_file_path()
    if os.path.isfile(target_path):
        try:
            os.remove(target_path)
        except Exception:
            pass


def validate_supervisor_token(provided_token: Optional[str], expected_token: str) -> bool:
    """Performs timing-attack-safe constant-time verification of the authentication token."""
    if not provided_token or not expected_token:
        return False
    # Clean bearer prefix if present
    clean_token = provided_token.strip()
    if clean_token.lower().startswith("bearer "):
        clean_token = clean_token[7:].strip()
    try:
        clean_bytes = clean_token.encode("utf-8")
        expected_bytes = expected_token.encode("utf-8")
        return secrets.compare_digest(clean_bytes, expected_bytes)
    except (TypeError, UnicodeEncodeError):
        return False

