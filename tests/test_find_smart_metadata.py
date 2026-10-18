"""Unit and integration tests for WebPilot Intelligent Form Analyzer (find smart flags).

Tests:
1. Field constraints & rules (--rules)
2. Field validation & error state (--error)
3. Containment environment (--context)
4. Field dependencies (--deps)
5. Consolidated shortcut (--smart / --meta)
6. Zero-token overhead default (clean baseline without flags)
"""

import argparse
from io import StringIO
import sys
from unittest.mock import MagicMock, patch

from cli_parser import build_cli_parser
from cli_commands.find_cmd import find_cmd


def test_cli_parser_smart_find_flags():
    """Verify CLI parser parses all smart diagnostic flags."""
    parser = build_cli_parser()

    # Individual flags
    args = parser.parse_args(["find", "@inp-1", "--rules", "--error", "--context", "--deps"])
    assert args.command == "find"
    assert args.target == "@inp-1"
    assert args.show_rules is True
    assert args.show_error is True
    assert args.show_context is True
    assert args.show_deps is True
    assert args.show_smart is False

    # Consolidated flag
    args_smart = parser.parse_args(["find", "@inp-1", "--smart"])
    assert args_smart.show_smart is True


def test_find_cmd_clean_baseline_without_smart_flags():
    """Verify standard find output omits rules, errors, and context when flags are not passed."""
    mock_client = MagicMock()
    mock_resp = MagicMock()
    mock_resp.success = True
    mock_resp.field_details = {
        "found": True,
        "local_id": "@inp-1",
        "id": "phone_num",
        "label": "Phone Number",
        "type": "input",
        "value": "",
        "required": True,
        "disabled": False,
        "visible": True,
        "rules": {"max_length": 10, "pattern": "^[0-9]{10}$"},
        "error_state": {"has_error": True, "message": "Required field"},
        "context_env": {"frame": "Main Document", "in_shadow_dom": False},
    }
    mock_client.execute.return_value = mock_resp

    parser = build_cli_parser()
    args = parser.parse_args(["find", "@inp-1"])

    with patch("cli_commands.find_cmd.get_supervisor_client", return_value=mock_client):
        stdout_buf = StringIO()
        with patch.object(sys, "stdout", stdout_buf):
            find_cmd(args)
        output = stdout_buf.getvalue()

    # Standard fields must be present
    assert "• Label       : Phone Number" in output
    assert "• Required    : True" in output

    # Smart flags NOT passed -> must NOT be displayed
    assert "• Rules       :" not in output
    assert "• Error State :" not in output
    assert "• Context     :" not in output


def test_find_cmd_smart_flags_rendered():
    """Verify find output renders rules, error state, and context when flags are passed."""
    mock_client = MagicMock()
    mock_resp = MagicMock()
    mock_resp.success = True
    mock_resp.field_details = {
        "found": True,
        "local_id": "@inp-1",
        "id": "phone_num",
        "label": "Phone Number",
        "type": "input",
        "value": "123",
        "required": True,
        "disabled": False,
        "visible": True,
        "rules": {
            "max_length": 10,
            "min_length": 10,
            "pattern": "^[0-9]{10}$",
            "input_mode": "tel",
            "accept": None,
        },
        "error_state": {
            "has_error": True,
            "message": "Please enter a valid 10-digit mobile number",
        },
        "context_env": {
            "frame": "Iframe (#application-frame)",
            "in_shadow_dom": True,
            "is_iframe": True,
        },
        "dependency": {
            "is_dependent": True,
            "parent_label": "Country",
            "parent_id": "country_select",
            "parent_local_id": "@drop-1",
        },
    }
    mock_client.execute.return_value = mock_resp

    parser = build_cli_parser()
    args = parser.parse_args(["find", "@inp-1", "--smart"])

    with patch("cli_commands.find_cmd.get_supervisor_client", return_value=mock_client):
        stdout_buf = StringIO()
        with patch.object(sys, "stdout", stdout_buf):
            find_cmd(args)
        output = stdout_buf.getvalue()

    # Verify Rules line
    assert "• Rules       : Max: 10 chars | Min: 10 chars | Pattern: ^[0-9]{10}$ | Mode: tel" in output

    # Verify Error State line
    assert '• Error State : [!] INVALID -> "Please enter a valid 10-digit mobile number"' in output

    # Verify Linked Parent
    assert "• Linked Parent : [@drop-1] 'Country' (ID: country_select)" in output

    # Verify Context line
    assert "• Context     : Iframe (#application-frame) | Shadow DOM: True" in output


def test_find_cmd_displays_specific_input_type():
    """Verify find_cmd displays specific input_type if provided (e.g. input (tel))."""
    mock_client = MagicMock()
    mock_resp = MagicMock()
    mock_resp.success = True
    mock_resp.field_details = {
        "found": True,
        "local_id": "@inp-1",
        "id": "user_tel",
        "label": "Mobile",
        "type": "input",
        "input_type": "tel",
        "value": "",
        "required": False,
        "disabled": False,
        "visible": True,
    }
    mock_client.execute.return_value = mock_resp

    parser = build_cli_parser()
    args = parser.parse_args(["find", "@inp-1"])

    with patch("cli_commands.find_cmd.get_supervisor_client", return_value=mock_client):
        stdout_buf = StringIO()
        with patch.object(sys, "stdout", stdout_buf):
            find_cmd(args)
        output = stdout_buf.getvalue()

    assert "• Widget Type : input (tel)" in output


def test_inspect_cmd_summary_only_flag():
    """Verify inspect_cmd honors --summary-only by suppressing individual field lines."""
    from cli_commands.inspect_cmd import inspect_cmd

    mock_client = MagicMock()
    mock_resp = MagicMock()
    mock_resp.success = True
    mock_resp.output_lines = [
        "• [@inp-1] First Name (input)",
        "• [@inp-2] Last Name (input)",
    ]
    mock_resp.schema = {
        "url": "https://example.com/form",
        "inputs": [{"id": "fn"}, {"id": "ln"}],
        "dropdowns": [],
        "buttons": [],
        "uploads": [],
    }
    mock_client.execute.return_value = mock_resp

    parser = build_cli_parser()
    args = parser.parse_args(["inspect", "--summary-only"])

    with patch("cli_commands.inspect_cmd.get_supervisor_client", return_value=mock_client):
        stdout_buf = StringIO()
        with patch.object(sys, "stdout", stdout_buf):
            inspect_cmd(args)
        output = stdout_buf.getvalue()

    # Detailed lines suppressed
    assert "• [@inp-1] First Name" not in output
    # Summary included
    assert "FORM INSPECTION SUMMARY" in output
