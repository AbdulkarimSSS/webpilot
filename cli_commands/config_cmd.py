"""CLI command handler for 'webpilot config' / 'wp config'."""

from __future__ import annotations

import argparse
import json
import sys

from config.preferences import (
    clear_preferences,
    get_preferences_path,
    load_preferences,
    set_preference,
    unset_preference,
)


def config_cmd(args: argparse.Namespace) -> None:
    """Manages persistent WebPilot user preferences and sticky flags."""
    action = getattr(args, "config_action", None) or "list"
    action = action.lower().strip()

    if action == "list":
        prefs = load_preferences()
        if getattr(args, "json", False):
            print(json.dumps(prefs, indent=2, ensure_ascii=False))
            return

        print("\n" + "═" * 70)
        print(" ⚙️ WEBPILOT PERSISTENT PREFERENCES & STICKY FLAGS")
        print("═" * 70)
        print(f" Config file: {get_preferences_path()}")
        print("─" * 70)
        if not prefs:
            print(" No persistent preferences configured (using standard factory defaults).")
            print("\n Tips:")
            print("   wp config set strip_header true     # Always suppress headers to save tokens")
            print("   wp config set exclude svg,script     # Always prune svg and script tags from HTML")
            print("   wp config set session main           # Default to named session 'main'")
        else:
            for k, v in prefs.items():
                print(f" • {k:<18} = {repr(v)}")
        print("═" * 70 + "\n")

    elif action == "set":
        key = getattr(args, "key", None)
        value = getattr(args, "value", None)
        if not key or value is None:
            print("[!] Error: 'wp config set <key> <value>' requires both key and value.", file=sys.stderr)
            sys.exit(1)

        # Parse boolean or integer strings nicely
        low_val = str(value).lower()
        if low_val in ("true", "1", "yes", "on"):
            parsed_val = True
        elif low_val in ("false", "0", "no", "off"):
            parsed_val = False
        else:
            try:
                parsed_val = int(value)
            except ValueError:
                parsed_val = value

        set_preference(key, parsed_val)
        print(f"[✓] Successfully set persistent preference: {key} = {repr(parsed_val)}")

    elif action in ("unset", "remove", "delete"):
        key = getattr(args, "key", None)
        if not key:
            print("[!] Error: 'wp config unset <key>' requires a key name.", file=sys.stderr)
            sys.exit(1)
        if unset_preference(key):
            print(f"[✓] Removed persistent preference: '{key}'")
        else:
            print(f"[*] Preference '{key}' was not set.")

    elif action in ("clear", "reset"):
        clear_preferences()
        print("[✓] Cleared all persistent user preferences (reset to defaults).")

    else:
        print(f"[!] Unknown config action: '{action}'", file=sys.stderr)
        sys.exit(1)
