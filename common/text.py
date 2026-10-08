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
