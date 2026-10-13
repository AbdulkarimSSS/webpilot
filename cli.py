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
        css_cmd,
        eval_cmd,
        find_cmd,
        get_base_url,
        get_supervisor_client,
        inspect_cmd,
        install_cmd,
        service_cmd,
        shell_cmd,
        skill_cmd,
    )
except ImportError:
    try:
        from .cli_commands import (
            apply_cmd,
            css_cmd,
            eval_cmd,
            find_cmd,
            get_base_url,
            get_supervisor_client,
            inspect_cmd,
            install_cmd,
            service_cmd,
            shell_cmd,
            skill_cmd,
        )
    except Exception:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from cli_commands import (
            apply_cmd,
            css_cmd,
            eval_cmd,
            find_cmd,
            get_base_url,
            get_supervisor_client,
            inspect_cmd,
            install_cmd,
            service_cmd,
            shell_cmd,
            skill_cmd,
        )

DISPATCH_TABLE = {
    "inspect": inspect_cmd,
    "reload": inspect_cmd,
    "refresh": inspect_cmd,
    "apply": apply_cmd,
    "find": find_cmd,
    "probe": find_cmd,
    "eval": eval_cmd,
    "js": eval_cmd,
    "exec": eval_cmd,
    "css": css_cmd,
    "style": css_cmd,
    "service": service_cmd,
    "shell": shell_cmd,
    "install": install_cmd,
    "skill": skill_cmd,
}


def main(argv: Optional[List[str]] = None) -> None:
    """Main CLI entrypoint for WebPilot."""
    parser = build_cli_parser()
    args = parser.parse_args(argv)

    handler = DISPATCH_TABLE.get(args.command)
    if handler:
        handler(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
