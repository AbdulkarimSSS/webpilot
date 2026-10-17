"""CLI command subpackage for WebPilot."""

from cli_commands.apply_cmd import apply_cmd
from cli_commands.common import get_base_url, get_supervisor_client
from cli_commands.config_cmd import config_cmd
from cli_commands.cookies_cmd import cookies_cmd
from cli_commands.css_cmd import css_cmd
from cli_commands.eval_cmd import eval_cmd
from cli_commands.find_cmd import find_cmd
from cli_commands.inspect_cmd import inspect_cmd
from cli_commands.read_cmd import read_cmd
from cli_commands.service_cmd import install_cmd, service_cmd, shell_cmd, skill_cmd
from cli_commands.tab_cmd import tab_cmd
from cli_commands.wait_cmd import wait_cmd

__all__ = [
    "get_base_url",
    "get_supervisor_client",
    "inspect_cmd",
    "apply_cmd",
    "read_cmd",
    "find_cmd",
    "eval_cmd",
    "css_cmd",
    "cookies_cmd",
    "tab_cmd",
    "service_cmd",
    "shell_cmd",
    "install_cmd",
    "skill_cmd",
    "config_cmd",
    "wait_cmd",
]
