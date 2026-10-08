"""Cookie sanitization and persistence helpers for Playwright."""

import json
import os
from typing import Any, Dict, List, Optional
from core.exceptions import ValidationError

INVALID_COOKIE_KEYS = ("hostOnly", "session", "storeId", "id")
VALID_SAME_SITE_VALUES = ("Strict", "Lax", "None")

def sanitize_cookies(raw_cookies: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Sanitizes raw cookie objects ensuring full Playwright compatibility."""
    if not isinstance(raw_cookies, list):
        raise ValidationError(f"Expected list of cookies, got {type(raw_cookies).__name__}")

    sanitized: List[Dict[str, Any]] = []
    for c in raw_cookies:
        if not isinstance(c, dict):
            continue
        cookie = dict(c)
        same_site = str(cookie.get("sameSite", "")).capitalize()
        if same_site in VALID_SAME_SITE_VALUES:
            cookie["sameSite"] = same_site
        else:
            cookie.pop("sameSite", None)

        for key in INVALID_COOKIE_KEYS:
            cookie.pop(key, None)

        sanitized.append(cookie)

    return sanitized

def load_and_sanitize_cookies(filepath: str) -> List[Dict[str, Any]]:
    """Loads a JSON cookie file from disk and returns sanitized cookie dictionaries."""
    if not os.path.isfile(filepath):
        raise FileNotFoundError(f"Cookie file not found: {filepath}")

    with open(filepath, "r", encoding="utf-8") as f:
        raw_cookies = json.load(f)

    return sanitize_cookies(raw_cookies)

def save_cookies(filepath: str, cookies: List[Dict[str, Any]]) -> None:
    """Persists cookie objects to disk formatted cleanly."""
    os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(cookies, f, indent=2, ensure_ascii=False)
