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
    def _boundary_match(cls, expected: str, actual_val: str) -> bool:
        """Matches expected value against actual string using whole token/word boundaries to prevent false positives."""
        if not expected or not actual_val:
            return False
        if expected == actual_val:
            return True
        pattern = r"(?:^|[\s,;/\-_\(\)])" + re.escape(expected) + r"(?:$|[\s,;/\-_\(\)])"
        return bool(re.search(pattern, actual_val))

    @classmethod
    def match(cls, actual: Any, expected: Any) -> bool:
        """Matches actual DOM readback against expected value."""
        if actual is None:
            return False

        expected_raw = str(expected).strip() if expected is not None else ""
        raw_lower = expected_raw.lower()
        is_regex = False
        regex_pattern = ""

        if raw_lower.startswith("regex:"):
            is_regex = True
            regex_pattern = expected_raw[6:].strip()
            expected_str = regex_pattern.lower()
        elif raw_lower.startswith("re:"):
            is_regex = True
            regex_pattern = expected_raw[3:].strip()
            expected_str = regex_pattern.lower()
        elif raw_lower.startswith("text:"):
            expected_raw = expected_raw[5:].strip()
            expected_str = expected_raw.lower()
        elif raw_lower.startswith("val:"):
            expected_raw = expected_raw[4:].strip()
            expected_str = expected_raw.lower()
        else:
            expected_str = raw_lower

        def _test_regex(val_str: Any) -> bool:
            if not is_regex or val_str is None:
                return False
            try:
                return bool(re.search(regex_pattern, str(val_str), re.IGNORECASE))
            except Exception:
                return False

        if isinstance(actual, dict):
            if actual.get("is_invalid") is True:
                return False
            ctype = actual.get("type", "")

            # Checkbox / Toggle switch
            if ctype == "checkbox":
                is_checked = bool(actual.get("checked", False))
                if is_regex:
                    return _test_regex("true" if is_checked else "false")
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
                    if is_regex:
                        return _test_regex(actual.get("value", ""))
                    if not expected_str or expected_str in ("true", "checked", "yes", "1"):
                        return True
                    return cls._boundary_match(expected_str, val)
                return False

            # Radio group
            if ctype == "radio_group":
                val = str(actual.get("value", "")).strip().lower()
                if not val or val in cls.JUNK_VALUES:
                    return False
                if is_regex:
                    return _test_regex(actual.get("value", ""))
                return cls._boundary_match(expected_str, val)

            # Checkbox group (multiple checkboxes)
            if ctype == "checkbox_group":
                val = str(actual.get("value", "")).strip().lower()
                if not val:
                    return False
                if is_regex:
                    return _test_regex(actual.get("value", ""))
                if "," in expected_str or "," in val:
                    exp_parts = set(x.strip() for x in expected_str.split(",") if x.strip())
                    val_parts = set(x.strip() for x in val.split(",") if x.strip())
                    return exp_parts == val_parts or exp_parts.issubset(val_parts)
                return cls._boundary_match(expected_str, val)

            # Native <select>
            if ctype == "select":
                val = str(actual.get("value", "")).strip().lower()
                text = str(actual.get("text", "")).strip().lower()
                if not val and not text:
                    return False
                if val in cls.JUNK_VALUES and text in cls.JUNK_VALUES:
                    return False
                if is_regex:
                    return _test_regex(actual.get("value", "")) or _test_regex(actual.get("text", ""))
                if expected_str.startswith("index:"):
                    sel_idx = actual.get("selected_index")
                    if sel_idx is not None and str(sel_idx) == expected_str.split(":", 1)[1].strip():
                        return True
                    return False
                if expected_str.startswith(("@opt-", "#")):
                    sel_opt_id = str(actual.get("selected_option_id", "")).lower()
                    clean_exp = expected_str.lstrip("#@").lower()
                    if sel_opt_id and (sel_opt_id == clean_exp or clean_exp in sel_opt_id):
                        return True
                    if val == clean_exp or val == expected_str:
                        return True
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
                if expected_str and (cls._boundary_match(expected_str, text) or cls._boundary_match(expected_str, val)):
                    return True
                return False

            # Custom picklist / combobox
            if ctype == "picklist":
                val = str(actual.get("value", "")).strip().lower()
                sel_text = str(actual.get("selected_text", "")).strip().lower()
                target_str = sel_text if sel_text and sel_text not in cls.JUNK_VALUES else val
                if not target_str or target_str in cls.JUNK_VALUES:
                    return False
                if is_regex:
                    return _test_regex(actual.get("selected_text", "")) or _test_regex(actual.get("value", ""))
                if expected_str.startswith("index:"):
                    sel_idx = actual.get("selected_index")
                    if sel_idx is not None and str(sel_idx) == expected_str.split(":", 1)[1].strip():
                        return True
                    return False
                if expected_str.startswith(("@opt-", "#")):
                    sel_opt_id = str(actual.get("selected_option_id", "")).lower()
                    clean_exp = expected_str.lstrip("#@").lower()
                    if sel_opt_id:
                        return sel_opt_id == clean_exp or clean_exp in sel_opt_id
                    if target_str == clean_exp or target_str == expected_str:
                        return True
                    opt_match = re.match(r"^@?opt-(\d+)$", expected_str)
                    if opt_match:
                        opt_idx = int(opt_match.group(1))
                        sel_idx = actual.get("selected_index")
                        if sel_idx is not None:
                            try:
                                s_idx = int(sel_idx)
                                return s_idx == opt_idx or s_idx == (opt_idx - 1)
                            except (ValueError, TypeError):
                                pass
                        if target_str and target_str not in cls.JUNK_VALUES:
                            return True
                    return False
                if cls._boundary_match(expected_str, target_str):
                    return True
                return False

            # Standard text / textarea / date
            val = str(actual.get("value", "")).strip()
            val_lower = val.lower()
            if is_regex:
                return _test_regex(val)
            if not val:
                return expected_str == ""
            if expected_str == val_lower:
                return True
            # Date normalization: YYYY-MM-DD <-> DD/MM/YYYY
            iso_exp = re.match(r"^(\d{4})-(\d{1,2})-(\d{1,2})$", expected_str)
            slash_val = re.match(r"^(\d{1,2})/(\d{1,2})/(\d{4})$", val_lower)
            if iso_exp and slash_val:
                if (
                    int(iso_exp.group(1)) == int(slash_val.group(3))
                    and int(iso_exp.group(2)) == int(slash_val.group(2))
                    and int(iso_exp.group(3)) == int(slash_val.group(1))
                ):
                    return True
            slash_exp = re.match(r"^(\d{1,2})/(\d{1,2})/(\d{4})$", expected_str)
            if slash_exp and slash_val:
                if (
                    int(slash_exp.group(1)) == int(slash_val.group(1))
                    and int(slash_exp.group(2)) == int(slash_val.group(2))
                    and int(slash_exp.group(3)) == int(slash_val.group(3))
                ):
                    return True
            # Whitespace normalized comparison
            if re.sub(r"\s+", " ", expected_str).strip() == re.sub(r"\s+", " ", val_lower).strip():
                return True
            # Phone / digits normalization (strictly restricted to tel fields or pure phone/numeric formats)
            is_tel = actual.get("type") in ("tel", "phone") or any(
                k in str(actual.get(attr, "")).lower()
                for attr in ("name", "id", "aria_label", "label")
                for k in ("phone", "tel", "mobile")
            )
            is_pure_numeric = bool(re.match(r"^[\d\s\(\)\-\+\.]+$", expected_str)) and bool(re.match(r"^[\d\s\(\)\-\+\.]+$", val_lower))
            if is_tel or is_pure_numeric:
                digits_exp = re.sub(r"\D", "", expected_str)
                digits_val = re.sub(r"\D", "", val_lower)
                if digits_exp and digits_val and digits_exp == digits_val:
                    return True
            # Currency / numeric normalization (e.g. "$1,234.56" vs "1234.56")
            is_currency_or_num = bool(re.match(r"^[\$\€\£\¥\d\s\(\)\-\+\.,]+$", expected_str)) and bool(re.match(r"^[\$\€\£\¥\d\s\(\)\-\+\.,]+$", val_lower))
            if is_currency_or_num:
                clean_exp = re.sub(r"[^\d.]", "", expected_str)
                clean_val = re.sub(r"[^\d.]", "", val_lower)
                if clean_exp and clean_val and clean_exp == clean_val:
                    return True
            return False

        # Fallback for plain string readback
        actual_str = str(actual).strip()
        actual_lower = actual_str.lower()
        if actual_lower in cls.JUNK_VALUES:
            return False
        if is_regex:
            return _test_regex(actual_str)
        if expected_str == actual_lower:
            return True
        if re.sub(r"\s+", " ", expected_str).strip() == re.sub(r"\s+", " ", actual_lower).strip():
            return True
        is_pure_numeric_fb = bool(re.match(r"^[\d\s\(\)\-\+\.]+$", expected_str)) and bool(re.match(r"^[\d\s\(\)\-\+\.]+$", actual_lower))
        if is_pure_numeric_fb:
            digits_exp = re.sub(r"\D", "", expected_str)
            digits_val = re.sub(r"\D", "", actual_lower)
            if digits_exp and digits_val and digits_exp == digits_val:
                return True
            clean_exp = re.sub(r"[^\d.]", "", expected_str)
            clean_val = re.sub(r"[^\d.]", "", actual_lower)
            if clean_exp and clean_val and clean_exp == clean_val:
                return True
        return False
