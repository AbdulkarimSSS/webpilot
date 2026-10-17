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


def get_preference(key: str, default: Any = None) -> Any:
    """Gets a specific preference value."""
    prefs = load_preferences()
    return prefs.get(key, default)


def set_preference(key: str, value: Any) -> None:
    """Sets a specific preference value."""
    prefs = load_preferences()
    prefs[key] = value
    save_preferences(prefs)


def unset_preference(key: str) -> bool:
    """Removes a specific preference value."""
    prefs = load_preferences()
    if key in prefs:
        del prefs[key]
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

    prefs = load_preferences()
    if not prefs:
        return []

    applied_notices: list[str] = []

    # 1. strip_header preference
    if "strip_header" in prefs:
        # Check if user explicitly asked for header via --with-header or --no-strip-header
        if getattr(args, "with_header", False) or getattr(args, "no_strip_header", False):
            setattr(args, "strip_header", False)
        elif not hasattr(args, "strip_header") or getattr(args, "strip_header", None) is None:
            # If not explicitly set on CLI, inherit from preferences
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
                    # Merge sets additively
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

    # 5. default timeout preference
    if "timeout_minutes" in prefs and hasattr(args, "timeout_minutes"):
        current = getattr(args, "timeout_minutes", 30)
        if current == 30:  # standard default
            setattr(args, "timeout_minutes", int(prefs["timeout_minutes"]))
            applied_notices.append(f"timeout_minutes={prefs['timeout_minutes']}")

    return applied_notices
