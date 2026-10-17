"""WebPilot CLI Dispatcher.

Dispatches command-line arguments to focused subcommands in cli_commands.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import List, Optional

try:
    from cli_parser import build_cli_parser
except ImportError:
    try:
        from .cli_parser import build_cli_parser
    except Exception:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from cli_parser import build_cli_parser

try:
    from cli_commands import (
        apply_cmd,
        config_cmd,
        cookies_cmd,
        css_cmd,
        eval_cmd,
        find_cmd,
        get_base_url,
        get_supervisor_client,
        inspect_cmd,
        install_cmd,
        read_cmd,
        service_cmd,
        shell_cmd,
        skill_cmd,
        tab_cmd,
        wait_cmd,
        block_cmd,
        capture_cmd,
        dump_cmd,
        network_cmd,
        sniff_cmd,
    )
    from config.preferences import apply_persistent_preferences
except ImportError:
    try:
        from .cli_commands import (
            apply_cmd,
            config_cmd,
            cookies_cmd,
            css_cmd,
            eval_cmd,
            find_cmd,
            get_base_url,
            get_supervisor_client,
            inspect_cmd,
            install_cmd,
            read_cmd,
            service_cmd,
            shell_cmd,
            skill_cmd,
            tab_cmd,
            wait_cmd,
            block_cmd,
            capture_cmd,
            dump_cmd,
            network_cmd,
            sniff_cmd,
        )
        from .config.preferences import apply_persistent_preferences
    except Exception:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from cli_commands import (
            apply_cmd,
            config_cmd,
            cookies_cmd,
            css_cmd,
            eval_cmd,
            find_cmd,
            get_base_url,
            get_supervisor_client,
            inspect_cmd,
            install_cmd,
            read_cmd,
            service_cmd,
            shell_cmd,
            skill_cmd,
            tab_cmd,
            wait_cmd,
            block_cmd,
            capture_cmd,
            dump_cmd,
            network_cmd,
            sniff_cmd,
        )
        from config.preferences import apply_persistent_preferences


DISPATCH_TABLE = {
    "inspect": inspect_cmd,
    "reload": inspect_cmd,
    "refresh": inspect_cmd,
    "apply": apply_cmd,
    "read": read_cmd,
    "find": find_cmd,
    "probe": find_cmd,
    "eval": eval_cmd,
    "js": eval_cmd,
    "exec": eval_cmd,
    "css": css_cmd,
    "style": css_cmd,
    "cookies": cookies_cmd,
    "cookie": cookies_cmd,
    "tab": tab_cmd,
    "tabs": tab_cmd,
    "service": service_cmd,
    "shell": shell_cmd,
    "install": install_cmd,
    "skill": skill_cmd,
    "wait": wait_cmd,
    "wait_for": wait_cmd,
    "config": config_cmd,
    "pref": config_cmd,
    "prefs": config_cmd,
    "preference": config_cmd,
    "preferences": config_cmd,
    "sniff": sniff_cmd,
    "dump": dump_cmd,
    "capture": capture_cmd,
    "block": block_cmd,
    "network": network_cmd,
}


def main(argv: Optional[List[str]] = None) -> None:
    """Main CLI entrypoint for WebPilot."""
    parser = build_cli_parser()
    args = parser.parse_args(argv)

    if getattr(args, "command", None) not in ("config", "pref", "prefs", "preference", "preferences"):
        applied = apply_persistent_preferences(args)
        if applied and not getattr(args, "strip_header", False):
            print(f"[⚙️ Preferences] Persistent configuration active: {', '.join(applied)} (override with CLI flags or --no-persistent-config)", file=sys.stderr)

    handler = DISPATCH_TABLE.get(args.command)
    if handler:
        handler(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
