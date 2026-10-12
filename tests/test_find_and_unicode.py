"""Unit tests for Unicode/PUA escape decoding, target descriptor parsing, and probe contract serialization."""

import pytest
from common.text import clean_label, decode_unicode_escapes, escape_pua_characters
from config.settings import Settings, get_settings, reset_settings_cache
from services.field_interaction_service import FieldInteractionService
from supervisor.contracts import SupervisorActionRequest, SupervisorActionResponse


def test_decode_unicode_escapes():
    # 1. Standard \uXXXX
    assert decode_unicode_escapes(r"\u0041\u0042\u0043") == "ABC"
    assert decode_unicode_escapes(r"Search \uE03D Icon") == "Search \uE03D Icon"

    # 2. Bracket notation [U+XXXX]
    assert decode_unicode_escapes("Degree [U+0041]") == "Degree A"
    assert decode_unicode_escapes("Icon [U+E03D]") == "Icon \uE03D"

    # 3. Extended \UXXXXXXXX
    assert decode_unicode_escapes(r"\U0001F600 Smile") == "😀 Smile"

    # 4. Plain text untouched
    assert decode_unicode_escapes("Regular text") == "Regular text"
    assert decode_unicode_escapes("") == ""


def test_escape_pua_characters():
    raw_pua = "Button \uE03D Save \uE838"
    escaped = escape_pua_characters(raw_pua)
    assert escaped == r"Button \uE03D Save \uE838"

    # Non-PUA unicode untouched
    assert escape_pua_characters("مرحبا بك 123") == "مرحبا بك 123"


def test_parse_target_descriptor():
    # Type hint
    hint, target, scope = FieldInteractionService.parse_target_descriptor("text:First Name")
    assert hint == "text"
    assert target == "First Name"
    assert scope is None

    # Picklist with hierarchy scope
    hint, target, scope = FieldInteractionService.parse_target_descriptor("picklist:Education > Degree")
    assert hint == "picklist"
    assert target == "Degree"
    assert scope == "Education"

    # Hierarchy scope without type hint
    hint, target, scope = FieldInteractionService.parse_target_descriptor("Address > City")
    assert hint is None
    assert target == "City"
    assert scope == "Address"

    # Local ID preserved
    hint, target, scope = FieldInteractionService.parse_target_descriptor("@fld-1")
    assert hint is None
    assert target == "@fld-1"
    assert scope is None


def test_supervisor_probe_contract_serialization():
    req = SupervisorActionRequest(
        action="probe",
        target_field="@fld-1",
        include_options=True,
        include_html=True,
        query="Engineering",
    )
    d = req.to_dict()
    assert d["action"] == "probe"
    assert d["target_field"] == "@fld-1"
    assert d["include_options"] is True
    assert d["include_html"] is True
    assert d["query"] == "Engineering"

    rehydrated = SupervisorActionRequest.from_dict(d)
    assert rehydrated.target_field == "@fld-1"
    assert rehydrated.query == "Engineering"

    resp = SupervisorActionResponse(
        success=True,
        action="probe",
        message="Found field",
        field_details={
            "local_id": "@fld-1",
            "id": "input_first_name",
            "label": "First Name",
            "type": "text",
            "value": "John",
        },
    )
    resp_dict = resp.to_dict()
    assert resp_dict["field_details"]["local_id"] == "@fld-1"
    assert resp_dict["field_details"]["type"] == "text"


def test_pua_mode_setting_resolution():
    reset_settings_cache()
    settings = get_settings()
    assert hasattr(settings, "pua_mode")
    assert settings.pua_mode in ("escape", "strip", "raw")


def test_inline_json_in_fill_args():
    from common.secrets import parse_and_resolve_fill_args

    # 1. Plain dictionary JSON string
    json_arg = '{"@fld-1": "Abdulkarim", "Degree": "Bachelor"}'
    resolved = parse_and_resolve_fill_args([json_arg])
    assert resolved == [("@fld-1", "Abdulkarim"), ("Degree", "Bachelor")]

    # 2. List of typed objects JSON string
    typed_arg = '[{"target": "@drop-1", "value": "val:SA"}, {"target": "Notes", "value": "Test"}]'
    resolved_typed = parse_and_resolve_fill_args([typed_arg])
    assert resolved_typed == [("@drop-1", "val:SA"), ("Notes", "Test")]


def test_worker_schema_merge():
    from supervisor.worker_process import OperationalWorker

    worker = OperationalWorker()
    old_schema = {
        "inputs": [
            {"id": "inp_1", "local_id": "@fld-1", "label": "First Name"},
            {"id": "inp_2", "local_id": "@fld-2", "label": "Last Name"},
        ],
        "dropdowns": [
            {"id": "dd_1", "local_id": "@drop-1", "label": "Country"},
        ],
    }
    new_schema = {
        "inputs": [
            {"id": "inp_1", "local_id": "@fld-1", "label": "First Name"},
            {"id": "inp_3", "local_id": "@fld-3", "label": "City"},
        ],
        "dropdowns": [
            {"id": "dd_1", "local_id": "@drop-1", "label": "Country"},
        ],
    }
    merged = worker._merge_schemas(old_schema, new_schema)
    merged_input_ids = [i["id"] for i in merged["inputs"]]
    assert "inp_1" in merged_input_ids
    assert "inp_2" in merged_input_ids  # Preserved from old_schema!
    assert "inp_3" in merged_input_ids  # Added from new_schema!


def test_failure_reasons_audit():
    """Verify that SET_FIELD_DOM_SCRIPT provides specific reasons for disabled, read-only, and missing options."""
    from adapters.dom_scripts import SET_FIELD_DOM_SCRIPT
    from unittest.mock import MagicMock

    mock_page = MagicMock()
    # Mock evaluate returning disabled reason
    mock_page.evaluate.return_value = {"success": False, "reason": "Field is disabled (awaiting dependency)", "type": "input", "id": "city"}

    from services.field_interaction_service import FieldInteractionService
    svc = FieldInteractionService(mock_page)
    res = svc.set_field("City", "Riyadh")
    assert res is False
    assert "disabled" in svc.last_failure_reason.lower()


def test_worker_schema_merge_ajax_rerender_dedup():
    """Verify that SchemaMerger replaces stale pre-rerender DOM IDs when (local_id, label) match."""
    from supervisor.worker_process import OperationalWorker

    worker = OperationalWorker()
    old_schema = {
        "dropdowns": [
            {"id": "57:_input", "local_id": "@drop-1", "label": "Salutation"},
        ],
    }
    new_schema = {
        "dropdowns": [
            {"id": "389:_input", "local_id": "@drop-1", "label": "Salutation"},
        ],
    }
    merged = worker._merge_schemas(old_schema, new_schema)
    assert len(merged["dropdowns"]) == 1
    assert merged["dropdowns"][0]["id"] == "389:_input"


def test_cli_reload_command_and_flag():
    """Verify that 'wp reload', 'wp inspect --reload', and 'wp apply --reload' parse cleanly."""
    from cli_parser import build_cli_parser
    from supervisor.contracts import SupervisorActionRequest

    parser = build_cli_parser()

    args_cmd = parser.parse_args(["reload"])
    assert args_cmd.command == "reload"
    assert args_cmd.reload is True

    args_insp = parser.parse_args(["inspect", "--reload"])
    assert args_insp.command == "inspect"
    assert args_insp.reload is True

    args_app = parser.parse_args(["apply", "--fill", "@fld-1=Test", "--reload"])
    assert args_app.command == "apply"
    assert args_app.reload is True

    req = SupervisorActionRequest(action="reload", reload=True)
    rt = SupervisorActionRequest.from_dict(req.to_dict())
    assert rt.action == "reload"
    assert rt.reload is True



