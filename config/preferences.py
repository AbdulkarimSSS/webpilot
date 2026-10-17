"""User persistent preferences and sticky configuration manager for WebPilot.

Manages ~/.webpilot/preferences.json, supporting sticky flags (e.g. strip_header=True,
exclude='svg,script,style') that auto-apply to CLI commands unless explicitly overridden.
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, Optional

CONFIG_DIR = os.path.expanduser("~/.webpilot")
PREFERENCES_FILE = os.path.join(CONFIG_DIR, "preferences.json")


def get_preferences_path() -> str:
    """Returns absolute path to the preferences file."""
    return PREFERENCES_FILE


def load_preferences() -> Dict[str, Any]:
    """Loads user preferences from disk."""
    if not os.path.isfile(PREFERENCES_FILE):
        return {}
    try:
        with open(PREFERENCES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_preferences(prefs: Dict[str, Any]) -> None:
    """Saves user preferences to disk securely."""
    try:
        os.makedirs(CONFIG_DIR, exist_ok=True)
    except Exception:
        pass
    with open(PREFERENCES_FILE, "w", encoding="utf-8") as f:
        json.dump(prefs, f, indent=2, ensure_ascii=False)


def normalize_config_key(key: str) -> str:
    """Normalizes configuration keys to lower snake_case (e.g. Strip-Header -> strip_header)."""
    return key.lower().replace("-", "_").strip()


def get_preference(key: str, default: Any = None) -> Any:
    """Gets a specific preference value with case-insensitive and hyphen-tolerant key lookup."""
    prefs = load_preferences()
    norm_key = normalize_config_key(key)
    # Direct match or scan normalized keys
    if norm_key in prefs:
        return prefs[norm_key]
    for k, v in prefs.items():
        if normalize_config_key(k) == norm_key:
            return v
    return default


def set_preference(key: str, value: Any) -> None:
    """Sets a specific preference value, standardizing key to normalized format."""
    prefs = load_preferences()
    norm_key = normalize_config_key(key)
    # Clean up any existing variant keys (e.g. Strip-Header vs strip_header)
    keys_to_remove = [k for k in prefs if normalize_config_key(k) == norm_key]
    for k in keys_to_remove:
        del prefs[k]
    prefs[norm_key] = value
    save_preferences(prefs)


def unset_preference(key: str) -> bool:
    """Removes a specific preference value with case-insensitive key lookup."""
    prefs = load_preferences()
    norm_key = normalize_config_key(key)
    keys_to_remove = [k for k in prefs if normalize_config_key(k) == norm_key]
    if keys_to_remove:
        for k in keys_to_remove:
            del prefs[k]
        save_preferences(prefs)
        return True
    return False


def clear_preferences() -> None:
    """Clears all stored preferences."""
    if os.path.isfile(PREFERENCES_FILE):
        try:
            os.remove(PREFERENCES_FILE)
        except Exception:
            pass


def apply_persistent_preferences(args: Any) -> list[str]:
    """Applies persistent preferences to argparse namespace if not explicitly overridden.

    Returns a list of human-readable notices explaining which preferences were applied.
    """
    if getattr(args, "no_persistent_config", False):
        return []

    raw_prefs = load_preferences()
    if not raw_prefs:
        return []

    # Map normalized keys to values
    prefs: Dict[str, Any] = {}
    for k, v in raw_prefs.items():
        prefs[normalize_config_key(k)] = v

    applied_notices: list[str] = []

    # 1. strip_header preference
    if "strip_header" in prefs:
        if getattr(args, "with_header", False) or getattr(args, "no_strip_header", False):
            setattr(args, "strip_header", False)
        elif not hasattr(args, "strip_header") or getattr(args, "strip_header", None) is None:
            pref_val = bool(prefs["strip_header"])
            setattr(args, "strip_header", pref_val)
            if pref_val:
                applied_notices.append(f"strip_header={pref_val}")

    # 2. exclude preference (additive merge)
    if "exclude" in prefs:
        if getattr(args, "no_exclude", False):
            setattr(args, "exclude", None)
        else:
            cli_exc = getattr(args, "exclude", None)
            pref_exc = str(prefs["exclude"]).strip()
            if pref_exc:
                if cli_exc:
                    cli_tags = [t.strip() for t in cli_exc.split(",") if t.strip()]
                    pref_tags = [t.strip() for t in pref_exc.split(",") if t.strip()]
                    merged = ",".join(sorted(set(pref_tags + cli_tags)))
                    setattr(args, "exclude", merged)
                    applied_notices.append(f"exclude='{merged}' (merged)")
                else:
                    setattr(args, "exclude", pref_exc)
                    applied_notices.append(f"exclude='{pref_exc}'")

    # 3. include preference (additive merge)
    if "include" in prefs:
        if getattr(args, "no_include", False):
            setattr(args, "include", None)
        else:
            cli_inc = getattr(args, "include", None)
            pref_inc = str(prefs["include"]).strip()
            if pref_inc:
                if cli_inc:
                    cli_tags = [t.strip() for t in cli_inc.split(",") if t.strip()]
                    pref_tags = [t.strip() for t in pref_inc.split(",") if t.strip()]
                    merged = ",".join(sorted(set(pref_tags + cli_tags)))
                    setattr(args, "include", merged)
                    applied_notices.append(f"include='{merged}' (merged)")
                else:
                    setattr(args, "include", pref_inc)
                    applied_notices.append(f"include='{pref_inc}'")

    # 4. default session preference
    if "session" in prefs and hasattr(args, "session") and not getattr(args, "session", None):
        setattr(args, "session", prefs["session"])
        applied_notices.append(f"session='{prefs['session']}'")

    # 5. default timeout preference (browser session inactivity)
    if "timeout_minutes" in prefs and hasattr(args, "timeout_minutes"):
        current = getattr(args, "timeout_minutes", 30)
        if current == 30:  # standard default
            setattr(args, "timeout_minutes", int(prefs["timeout_minutes"]))
            applied_notices.append(f"timeout_minutes={prefs['timeout_minutes']}")

    # 6. default tab_timeout preference (per-tab inactivity limit in minutes)
    if "tab_timeout" in prefs:
        tab_to_val = int(prefs["tab_timeout"])
        if hasattr(args, "tab_timeout") and getattr(args, "tab_timeout", None) in (None, 30):
            setattr(args, "tab_timeout", tab_to_val)
            applied_notices.append(f"tab_timeout={tab_to_val}m")
        elif not hasattr(args, "tab_timeout"):
            setattr(args, "tab_timeout", tab_to_val)

    # 7. default max_chars preference
    if "max_chars" in prefs and hasattr(args, "max_chars"):
        current_mc = getattr(args, "max_chars", 20000)
        if current_mc == 20000:
            mc_val = int(prefs["max_chars"])
            setattr(args, "max_chars", mc_val)
            applied_notices.append(f"max_chars={mc_val}")

    return applied_notices
