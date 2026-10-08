"""Validation logic for form payloads and CLI inputs."""

from typing import Any, Dict, List, Tuple, Union
from core.exceptions import ValidationError

class PayloadValidator:
    """Validates candidate payloads and CLI key-value arguments."""

    @staticmethod
    def validate_key_value_pair(key: Any, val: Any) -> Tuple[str, Any]:
        """Validates that a field key is a non-empty string."""
        clean_key = str(key).strip()
        if not clean_key:
            raise ValidationError("Field key cannot be empty or whitespace")
        return clean_key, val

    @staticmethod
    def validate_payload_list(items: List[Tuple[str, Any]]) -> List[Tuple[str, Any]]:
        """Ensures all items in payload are valid (key, value) tuples."""
        validated = []
        for item in items:
            if not isinstance(item, (tuple, list)) or len(item) != 2:
                raise ValidationError(f"Invalid payload item structure: {item}")
            validated.append(PayloadValidator.validate_key_value_pair(item[0], item[1]))
        return validated
