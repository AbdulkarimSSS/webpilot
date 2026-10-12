"""DOM readback verification and heuristic value normalization matcher."""

from __future__ import annotations

import re
from typing import Any


class DOMDataMatcher:
    """Evaluates whether actual DOM readback matches expected value across control types."""

    JUNK_VALUES = {
        "login/ view profile",
        "no selection",
        "select",
        "choose",
        "-- select --",
        "",
    }

    @classmethod
    def match(cls, actual: Any, expected: Any) -> bool:
        """Matches actual DOM readback against expected value."""
        if actual is None:
            return False

        expected_str = str(expected).strip().lower() if expected is not None else ""

        if isinstance(actual, dict):
            ctype = actual.get("type", "")

            # Checkbox / Toggle switch
            if ctype == "checkbox":
                is_checked = bool(actual.get("checked", False))
                if isinstance(expected, bool):
                    return is_checked is expected
                if expected_str in ("true", "yes", "1", "checked", "on"):
                    return is_checked is True
                if expected_str in ("false", "no", "0", "unchecked", "off"):
                    return is_checked is False
                return is_checked is True

            # Radio button
            if ctype == "radio":
                is_checked = bool(actual.get("checked", False))
                val = str(actual.get("value", "")).strip().lower()
                if is_checked:
                    if not expected_str or expected_str in ("true", "checked", "yes", "1"):
                        return True
                    return expected_str == val or expected_str in val or val in expected_str
                return False

            # Radio group
            if ctype == "radio_group":
                val = str(actual.get("value", "")).strip().lower()
                if not val or val in cls.JUNK_VALUES:
                    return False
                return expected_str in val or val in expected_str

            # Checkbox group (multiple checkboxes)
            if ctype == "checkbox_group":
                val = str(actual.get("value", "")).strip().lower()
                if not val:
                    return False
                if "," in expected_str or "," in val:
                    exp_parts = set(x.strip() for x in expected_str.split(",") if x.strip())
                    val_parts = set(x.strip() for x in val.split(",") if x.strip())
                    return exp_parts == val_parts or exp_parts.issubset(val_parts)
                return expected_str == val or expected_str in val

            # Native <select>
            if ctype == "select":
                val = str(actual.get("value", "")).strip().lower()
                text = str(actual.get("text", "")).strip().lower()
                if not val and not text:
                    return False
                if val in cls.JUNK_VALUES and text in cls.JUNK_VALUES:
                    return False
                # Comma-separated multi-select comparison
                if "," in expected_str or "," in val or "," in text:
                    exp_parts = set(x.strip() for x in expected_str.split(",") if x.strip())
                    val_parts = set(x.strip() for x in val.split(",") if x.strip())
                    text_parts = set(x.strip() for x in text.split(",") if x.strip())
                    if exp_parts and (
                        exp_parts == val_parts
                        or exp_parts == text_parts
                        or exp_parts.issubset(val_parts)
                        or exp_parts.issubset(text_parts)
                    ):
                        return True
                if expected_str == val or expected_str == text:
                    return True
                if expected_str and (
                    expected_str in text
                    or expected_str in val
                    or val in expected_str
                    or text in expected_str
                ):
                    return True
                if len(val) == 2 and len(expected_str) > 2 and (expected_str.startswith(val) or val in expected_str):
                    return True
                return False

            # Custom picklist / combobox
            if ctype == "picklist":
                val = str(actual.get("value", "")).strip().lower()
                sel_text = str(actual.get("selected_text", "")).strip().lower()
                target_str = sel_text if sel_text and sel_text not in cls.JUNK_VALUES else val
                if not target_str or target_str in cls.JUNK_VALUES:
                    return False
                if expected_str == target_str or expected_str in target_str or target_str in expected_str:
                    return True
                if len(target_str) == 2 and len(expected_str) > 2 and expected_str.startswith(target_str):
                    return True
                return False

            # Standard text / textarea
            val = str(actual.get("value", "")).strip()
            val_lower = val.lower()
            if not val:
                return expected_str == ""
            if expected_str == val_lower:
                return True
            # Whitespace normalized comparison
            if re.sub(r"\s+", " ", expected_str).strip() == re.sub(r"\s+", " ", val_lower).strip():
                return True
            # Phone / digits normalization
            digits_exp = re.sub(r"\D", "", expected_str)
            digits_val = re.sub(r"\D", "", val_lower)
            if digits_exp and digits_val and digits_exp == digits_val:
                return True
            # Currency / numeric normalization (e.g. "$1,234.56" vs "1234.56")
            clean_exp = re.sub(r"[^\d.]", "", expected_str)
            clean_val = re.sub(r"[^\d.]", "", val_lower)
            if clean_exp and clean_val and clean_exp == clean_val:
                return True
            return False

        # Fallback for plain string readback
        actual_lower = str(actual).strip().lower()
        if actual_lower in cls.JUNK_VALUES:
            return False
        if expected_str == actual_lower:
            return True
        if re.sub(r"\s+", " ", expected_str).strip() == re.sub(r"\s+", " ", actual_lower).strip():
            return True
        digits_exp = re.sub(r"\D", "", expected_str)
        digits_val = re.sub(r"\D", "", actual_lower)
        if digits_exp and digits_val and digits_exp == digits_val:
            return True
        clean_exp = re.sub(r"[^\d.]", "", expected_str)
        clean_val = re.sub(r"[^\d.]", "", actual_lower)
        if clean_exp and clean_val and clean_exp == clean_val:
            return True
        return False
