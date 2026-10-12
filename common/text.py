"""Text processing and string normalization utilities."""

import re

def clean_label(text: str) -> str:
    """Strips unicode whitespace, tabs, newlines, and leading asterisks/spaces."""
    if not text:
        return ""
    # Replace non-breaking spaces and line breaks with single space
    cleaned = re.sub(r"[\u00a0\r\n\t]+", " ", str(text))
    # Strip leading whitespace and asterisks commonly used in required indicators
    cleaned = re.sub(r"^[\s\*]+", "", cleaned)
    return cleaned.strip()

def truncate_text(text: str, max_length: int = 80) -> str:
    """Truncates text safely with boundary check."""
    if not text or len(text) <= max_length:
        return text or ""
    return text[:max_length].strip()


def decode_unicode_escapes(text: str) -> str:
    """Decodes standard unicode escape sequences (\\uXXXX, \\UXXXXXXXX, [U+XXXX]) into real characters."""
    if not text:
        return ""
    # 1. Standard \\uXXXX
    res = re.sub(r"\\u([0-9a-fA-F]{4})", lambda m: chr(int(m.group(1), 16)), str(text))
    # 2. Extended \\UXXXXXXXX
    res = re.sub(r"\\U([0-9a-fA-F]{8})", lambda m: chr(int(m.group(1), 16)), res)
    # 3. Bracket notation [U+XXXX] or [u+XXXX]
    res = re.sub(r"\[[Uu]\+([0-9a-fA-F]{4,6})\]", lambda m: chr(int(m.group(1), 16)), res)
    return res


def escape_pua_characters(text: str) -> str:
    """Replaces Private Use Area (PUA) code points (U+E000-U+F8FF) with readable escape sequences (\\uXXXX)."""
    if not text:
        return ""
    return re.sub(r"[\uE000-\uF8FF]", lambda m: f"\\u{ord(m.group(0)):04X}", str(text))
