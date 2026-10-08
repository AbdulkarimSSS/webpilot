"""Payload and protocol envelope builder module (Facade and Legacy Entrypoint).

Constructs browser context envelopes and form application payloads.
Enforces strict decoupling: NEVER injects hardcoded string literals or device
fallbacks. Reads strictly from passed models (DeviceProfile / Settings) or
verified values loaded from dedicated configuration files.
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional, Tuple, Union

from adapters.envelope_builder import BrowserContextEnvelopeBuilder
from core.exceptions import ConfigurationError, ValidationError
from core.models import DeviceProfile, ProxyConfig
from config.settings import (
    Settings,
    get_settings,
    load_device_profile,
    DEFAULT_DEVICE_PROFILE_JSON,
)

__all__ = ["BrowserContextEnvelopeBuilder", "FormPayloadBuilder"]


class FormPayloadBuilder:
    """Builds and validates form field application payloads.

    Loads mappings from file, dictionaries, or key-value pairs without
    injecting hardcoded personal identity strings or sensitive fallbacks.
    """

    @staticmethod
    def load_from_file(filepath: str) -> List[Tuple[str, Any]]:
        """Load field key-value pairs from an external JSON file."""
        if not os.path.isfile(filepath):
            raise ConfigurationError(f"Form payload data file not found: {filepath}")

        try:
            with open(filepath, "r", encoding="utf-8") as f:
                raw_data = json.load(f)
        except Exception as exc:
            raise ValidationError(f"Invalid JSON in form payload file {filepath}: {exc}") from exc

        return FormPayloadBuilder.normalize_payload(raw_data)

    @staticmethod
    def normalize_payload(raw_data: Union[Dict[str, Any], List[Any]]) -> List[Tuple[str, Any]]:
        """Normalizes dict or list structures into a clean list of (field, value) pairs."""
        fields: List[Tuple[str, Any]] = []

        if isinstance(raw_data, dict):
            for k, v in raw_data.items():
                fields.append((str(k), v))
        elif isinstance(raw_data, list):
            for item in raw_data:
                if isinstance(item, (list, tuple)) and len(item) == 2:
                    fields.append((str(item[0]), item[1]))
                elif isinstance(item, dict) and "key" in item and "value" in item:
                    fields.append((str(item["key"]), item["value"]))
                else:
                    raise ValidationError(f"Unrecognized payload entry structure: {item}")
        else:
            raise ValidationError(f"Expected dict or list for payload, got {type(raw_data).__name__}")

        return fields

    @staticmethod
    def parse_cli_fill_arguments(fill_args: Optional[List[str]]) -> List[Tuple[str, str]]:
        """Parses CLI --fill 'key=value' arguments into key-value pairs."""
        if not fill_args:
            return []

        parsed: List[Tuple[str, str]] = []
        for item in fill_args:
            if "=" in item:
                k, v = item.split("=", 1)
                parsed.append((k.strip(), v.strip()))
            else:
                raise ValidationError(f"Invalid fill argument format: '{item}' (Expected 'key=value')")
        return parsed
