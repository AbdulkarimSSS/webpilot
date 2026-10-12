"""Payload and protocol envelope builder module (Facade and Legacy Entrypoint).

Constructs browser context envelopes and form application payloads.
Enforces strict decoupling: NEVER injects hardcoded string literals or device
fallbacks. Reads strictly from passed models (DeviceProfile / Settings) or
verified values loaded from dedicated configuration files.
"""

from __future__ import annotations

import json
import os
import sys
from typing import Any, Dict, List, Optional, Tuple, Union

from adapters.envelope_builder import BrowserContextEnvelopeBuilder
from common.secrets import resolve_secret_value
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
        """Load field key-value pairs from an external JSON file or stdin ('-' or '@stdin')."""
        if filepath in ("-", "@stdin"):
            try:
                raw_data = json.load(sys.stdin)
            except Exception as exc:
                raise ValidationError(f"Invalid JSON read from standard input: {exc}") from exc
            return FormPayloadBuilder.normalize_payload(raw_data)

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
        """Normalizes dict or list structures into a clean list of (field, value) pairs and resolves secrets."""
        from common.secrets import resolve_secret_value

        fields: List[Tuple[str, Any]] = []

        if isinstance(raw_data, dict):
            for k, v in raw_data.items():
                if isinstance(v, dict):
                    # Nested section dictionary: {"Education": {"Degree": "Bachelor", "GPA": "4.5"}}
                    for sub_k, sub_v in v.items():
                        scoped_key = f"scope:{k}:{sub_k}"
                        fields.append((scoped_key, resolve_secret_value(sub_v, prompt_label=scoped_key)))
                elif isinstance(v, list) and all(isinstance(row, dict) for row in v):
                    # List of repeating rows in a section: {"Education": [{"Degree": "BSc"}, {"Degree": "MSc"}]}
                    for row_idx, row in enumerate(v, 1):
                        for sub_k, sub_v in row.items():
                            scoped_key = f"scope:{k}:{sub_k}"
                            fields.append((scoped_key, resolve_secret_value(sub_v, prompt_label=scoped_key)))
                else:
                    fields.append((str(k), resolve_secret_value(v, prompt_label=str(k))))
        elif isinstance(raw_data, list):
            for item in raw_data:
                if isinstance(item, (list, tuple)) and len(item) == 2:
                    fields.append((str(item[0]), resolve_secret_value(item[1], prompt_label=str(item[0]))))
                elif isinstance(item, dict) and ("key" in item or "target" in item or "field" in item or "name" in item) and "value" in item:
                    k = str(item.get("target") or item.get("key") or item.get("field") or item.get("name"))
                    scope = item.get("scope") or item.get("section")
                    if scope:
                        k = f"scope:{scope}:{k}"
                    fields.append((k, resolve_secret_value(item["value"], prompt_label=k)))
                else:
                    raise ValidationError(f"Unrecognized payload entry structure: {item}")
        else:
            raise ValidationError(f"Expected dict or list for payload, got {type(raw_data).__name__}")

        return fields

    @staticmethod
    def parse_cli_fill_arguments(fill_args: Optional[List[str]]) -> List[Tuple[str, Any]]:
        """Parses CLI --fill arguments into key-value pairs and resolves secrets (@env, @stdin, @file)."""
        from common.secrets import parse_and_resolve_fill_args
        return parse_and_resolve_fill_args(fill_args)

