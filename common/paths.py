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
    """Validates that a URL does not attempt Local File Inclusion (LFI) or cloud metadata SSRF.

    Protects against direct literals, decimal/hex/octal encodings, DNS aliases,
    IPv4-mapped IPv6, and link-local cloud metadata (AWS IMDSv4/v6, GCP, Azure, Oracle).
    """
    if url is None:
        return None
    raw = url.strip()
    if not raw:
        return ""

    if raw in ("about:blank", "chrome://newtab"):
        return raw

    import ipaddress
    import socket
    from urllib.parse import urlsplit

    split = urlsplit(raw)
    scheme = (split.scheme or "").lower()

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

    hostname = (split.hostname or "").strip().rstrip(".").lower()
    if not hostname:
        raise ValidationError("Security restriction: URL host cannot be empty.")

    # Explicit metadata domain denylist
    if hostname in ("metadata.google.internal", "metadata.internal", "instance-data"):
        raise ValidationError(
            f"Security restriction: access to cloud instance metadata at '{hostname}' is strictly prohibited."
        )

    allow_internal = os.environ.get("WEBPILOT_ALLOW_INTERNAL_URLS") == "1" or os.environ.get("WEBPILOT_ALLOW_LOCAL_URLS") == "1"

    # Cloud metadata networks (always blocked, even if WEBPILOT_ALLOW_INTERNAL_URLS=1)
    METADATA_NETWORKS = [
        ipaddress.ip_network("169.254.0.0/16"),       # IPv4 link-local & AWS/GCP/Azure/OCI IMDSv4
        ipaddress.ip_network("fd00:ec2::/32"),        # AWS IMDSv6
        ipaddress.ip_network("fe80::/10"),            # IPv6 link-local
    ]

    # Resolve IP addresses (handles decimal IP, hex IP, octal IP, DNS aliases like nip.io, IPv6)
    clean_host = hostname.strip("[]")
    addr_infos = []

    # Check integer/hex literal representation (e.g. 0xA9FEA9FE, 2852039166, 0x7f000001)
    try:
        val = int(clean_host, 0)
        if 0 <= val <= 0xFFFFFFFF:
            addr_infos.append((socket.AF_INET, None, None, None, (str(ipaddress.IPv4Address(val)), 0)))
    except (ValueError, TypeError):
        pass

    # Check dotted octal/hex/decimal (e.g. 0177.0.0.1, 127.0.0.1)
    if not addr_infos and "." in clean_host:
        parts = clean_host.split(".")
        if len(parts) == 4:
            try:
                b = [int(p, 0) for p in parts]
                if all(0 <= x <= 255 for x in b):
                    addr_infos.append((socket.AF_INET, None, None, None, (str(ipaddress.IPv4Address(bytes(b))), 0)))
            except (ValueError, TypeError):
                pass

    if not addr_infos:
        try:
            addr_infos = socket.getaddrinfo(clean_host, split.port or (443 if scheme == "https" else 80), proto=socket.IPPROTO_TCP)
        except socket.gaierror:
            try:
                addr = ipaddress.ip_address(clean_host)
                addr_infos = [(socket.AF_INET6 if addr.version == 6 else socket.AF_INET, None, None, None, (str(addr), 0))]
            except ValueError:
                if any(c.isdigit() for c in clean_host) and ("x" in clean_host.lower() or clean_host.replace(".", "").isdigit()):
                    raise ValidationError(f"Security restriction: invalid or malformed numeric host '{hostname}'.")
                return raw


    for addr_info in addr_infos:
        sock_addr = addr_info[4]
        ip_str = sock_addr[0]
        try:
            ip_obj = ipaddress.ip_address(ip_str)
        except ValueError:
            continue

        # Unwrap IPv4-mapped IPv6 (e.g. ::ffff:169.254.169.254)
        if isinstance(ip_obj, ipaddress.IPv6Address) and ip_obj.ipv4_mapped:
            ip_obj = ip_obj.ipv4_mapped

        # 1. Enforce strict cloud metadata block
        for meta_net in METADATA_NETWORKS:
            if ip_obj in meta_net:
                raise ValidationError(
                    f"Security restriction: access to cloud instance metadata / link-local address '{ip_obj}' is strictly prohibited."
                )

        # 2. Enforce private / loopback restriction unless explicitly allowed for testing
        if not allow_internal:
            if (
                ip_obj.is_loopback
                or ip_obj.is_private
                or ip_obj.is_reserved
                or ip_obj.is_multicast
                or ip_obj.is_unspecified
            ):
                raise ValidationError(
                    f"Security restriction: access to internal or private IP address '{ip_obj}' is blocked. Set WEBPILOT_ALLOW_INTERNAL_URLS=1 to permit local lab testing."
                )

    return raw


