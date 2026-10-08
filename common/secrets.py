"""Secrets resolution and credential hygiene utilities.

Enables secure injection of sensitive form values without leaving plain-text
passwords in terminal history, process lists, or shell logfiles.
Supports:
  - @env:VARIABLE_NAME (reads secret from specified environment variable)
  - @stdin (reads securely from stdin/pipe without shell echo)
  - @file:FILE_PATH (reads secret from a local protected file)
"""

from __future__ import annotations

import getpass
import os
import sys
from typing import Any, Dict, List, Optional, Tuple, Union

from core.exceptions import ConfigurationError, ValidationError


def resolve_secret_value(value: Any, prompt_label: Optional[str] = None) -> Any:
    """Resolves secret references (@env:VAR, @stdin, @file:PATH) to actual string values."""
    if not isinstance(value, str):
        return value

    trimmed = value.strip()

    # 1. Environment Variable Reference (@env:VAR_NAME)
    if trimmed.startswith("@env:"):
        var_name = trimmed[5:].strip()
        if not var_name:
            raise ValidationError("Empty environment variable name specified in '@env:' reference.")
        env_val = os.environ.get(var_name)
        if env_val is None:
            raise ConfigurationError(
                f"Referenced environment variable '{var_name}' is not set. "
                f"Please define '{var_name}' before invoking WebPilot."
            )
        return env_val

    # 2. Standard Input Reference (@stdin or pure '-')
    if trimmed in ("@stdin", "-"):
        if sys.stdin.isatty():
            # Interactive terminal: prompt securely without terminal echo
            label = prompt_label or "secret value"
            try:
                entered = getpass.getpass(f"Enter {label}: ")
                return entered
            except Exception as exc:
                raise ValidationError(f"Failed to read secret from stdin: {exc}") from exc
        else:
            # Piped or redirected input: read single line from pipe
            line = sys.stdin.readline()
            return line.rstrip("\r\n")

    # 3. Secure File Reference (@file:PATH)
    if trimmed.startswith("@file:"):
        file_path = trimmed[6:].strip()
        if not os.path.isfile(file_path):
            raise ConfigurationError(f"Referenced secret file not found: {file_path}")
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return f.read().rstrip("\r\n")
        except Exception as exc:
            raise ConfigurationError(f"Failed to read secret file '{file_path}': {exc}") from exc

    return value


def resolve_payload_secrets(data: Any) -> Any:
    """Recursively resolves secret references in arbitrary dictionary or list structures."""
    if isinstance(data, dict):
        return {k: resolve_payload_secrets(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [resolve_payload_secrets(item) for item in data]
    elif isinstance(data, tuple) and len(data) == 2:
        return (data[0], resolve_secret_value(data[1], prompt_label=str(data[0])))
    elif isinstance(data, str):
        return resolve_secret_value(data)
    return data


def parse_and_resolve_fill_args(fill_args: Optional[List[str]]) -> List[Tuple[str, Any]]:
    """Parses list of CLI --fill arguments and resolves any @env, @stdin, or @file references.

    Also handles batch input from stdin if an argument is literally '-' or '@stdin'.
    """
    if not fill_args:
        return []

    results: List[Tuple[str, Any]] = []

    for item in fill_args:
        trimmed = item.strip()

        # Check for batch stdin ingestion
        if trimmed in ("-", "@stdin"):
            if not sys.stdin.isatty():
                # Read all lines from pipe: each line expected to be key=value
                for line in sys.stdin:
                    line_str = line.strip()
                    if line_str and "=" in line_str and not line_str.startswith("#"):
                        k, v = line_str.split("=", 1)
                        resolved_v = resolve_secret_value(v.strip(), prompt_label=k.strip())
                        results.append((k.strip(), resolved_v))
            continue

        if "=" not in trimmed:
            raise ValidationError(
                f"Invalid --fill argument format: '{item}'. "
                "Expected 'key=value', e.g. --fill 'username=john' or --fill 'password=@env:MY_PASS'"
            )

        k, v = trimmed.split("=", 1)
        key = k.strip()
        raw_val = v.strip()
        resolved_val = resolve_secret_value(raw_val, prompt_label=key)
        results.append((key, resolved_val))

    return results
