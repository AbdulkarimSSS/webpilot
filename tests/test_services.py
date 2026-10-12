"""Tests for domain services and formatters."""

import pytest
from core.models import (
    InspectionResult,
    InputField,
    DropdownField,
    ChoiceGroup,
    FileUploadField,
    ActionButton,
)
from services.inspection_formatter_service import InspectionFormatterService
from validators.payload_validator import PayloadValidator
from common.text import clean_label, truncate_text
from common.cookies import sanitize_cookies
from common.retry import with_retry
from core.exceptions import ValidationError


def test_clean_label():
    assert clean_label("   * Full Name \u00a0\n ") == "Full Name"
    assert clean_label("***Email Address") == "Email Address"
    assert clean_label("") == ""


def test_truncate_text():
    assert truncate_text("Short text", 50) == "Short text"
    assert truncate_text("A very long sentence exceeding limit", 10) == "A very lon"


def test_sanitize_cookies():
    raw = [
        {"name": "session_id", "value": "123", "sameSite": "strict", "hostOnly": True, "id": 1},
        {"name": "tracking", "value": "xyz", "sameSite": "invalid_val", "storeId": "abc"},
    ]
    sanitized = sanitize_cookies(raw)
    assert len(sanitized) == 2
    assert sanitized[0]["sameSite"] == "Strict"
    assert "hostOnly" not in sanitized[0]
    assert "id" not in sanitized[0]
    assert "sameSite" not in sanitized[1]
    assert "storeId" not in sanitized[1]


def test_with_retry_success():
    calls = []
    def action():
        calls.append(1)
        if len(calls) < 2:
            raise ValueError("Temporary glitch")
        return "success"

    res = with_retry(action, max_attempts=3, initial_delay_sec=0.01)
    assert res == "success"
    assert len(calls) == 2


def test_with_retry_failure():
    def failing_action():
        raise KeyError("Persistent error")

    with pytest.raises(KeyError):
        with_retry(failing_action, max_attempts=2, initial_delay_sec=0.01)


def test_payload_validator():
    k, v = PayloadValidator.validate_key_value_pair(" First Name ", "John")
    assert k == "First Name"
    assert v == "John"

    with pytest.raises(ValidationError):
        PayloadValidator.validate_key_value_pair("   ", "Value")

    valid_list = PayloadValidator.validate_payload_list([("A", 1), ("B", 2)])
    assert valid_list == [("A", 1), ("B", 2)]


def test_inspection_formatter():
    data = {
        "title": "Application Page",
        "url": "https://example.com/apply",
        "sections": ["Personal Info", "Experience"],
        "inputs": [
            {"id": "name_inp", "label": "Full Name", "value": "Alice", "required": True},
        ],
        "dropdowns": [
            {"id": "country_dd", "label": "Country", "value": "USA", "required": True, "sample_options": ["USA", "Canada"]},
        ],
        "choices": [
            {"question": "Authorized to work?", "options": ["Yes", "No"], "selected": "Yes", "required": True},
        ],
        "file_uploads": [
            {"id": "resume_file", "label": "Resume", "required": True},
        ],
        "already_uploaded_files": ["resume_v1.pdf"],
        "buttons": [
            {"id": "submit_btn", "text": "Submit Application", "action": "submit"},
        ],
    }

    summary = InspectionFormatterService.format_summary(data)
    assert "=== FORM INSPECTION SUMMARY: 'Application Page' ===" in summary
    assert "Full Name" in summary
    assert "Country" in summary
    assert "Authorized to work?" in summary
    assert "Resume" in summary
    assert "resume_v1.pdf" in summary
    assert "SUBMIT" in summary


def test_target_descriptor_parsing():
    """Verify parse_target_descriptor extracts type hints, scope, and local_id."""
    from services.field_interaction_service import FieldInteractionService

    # 1. Type hint only
    hint, target, scope = FieldInteractionService.parse_target_descriptor("text:First Name")
    assert hint == "text"
    assert target == "First Name"
    assert scope is None

    # 2. Picklist with scope
    hint, target, scope = FieldInteractionService.parse_target_descriptor("picklist:Education Level > Degree")
    assert hint == "picklist"
    assert target == "Degree"
    assert scope == "Education Level"

    # 3. Local ID
    hint, target, scope = FieldInteractionService.parse_target_descriptor("@fld-1")
    assert hint is None
    assert target == "@fld-1"
    assert scope is None

    # 4. Scope without explicit type
    hint, target, scope = FieldInteractionService.parse_target_descriptor("Work History > Company")
    assert hint is None
    assert target == "Company"
    assert scope == "Work History"


def test_fill_arguments_with_hierarchy_and_types():
    """Verify parse_and_resolve_fill_args correctly parses 'Parent > Option' and type prefixes."""
    from common.secrets import parse_and_resolve_fill_args

    args = [
        "text:first_name=Alice",
        "Degree > Bachelors",
        "@drop-1=Saudi Arabia",
        "picklist:country=UAE",
    ]
    parsed = parse_and_resolve_fill_args(args)
    assert ("text:first_name", "Alice") in parsed
    assert ("picklist:Degree", "Bachelors") in parsed
    assert ("@drop-1", "Saudi Arabia") in parsed
    assert ("picklist:country", "UAE") in parsed


def test_inspection_formatter_with_local_ids():
    """Verify InspectionFormatterService outputs [local_id] for clear user targeting."""
    data = {
        "title": "Profile Form",
        "url": "https://example.com",
        "inputs": [{"id": "fn", "label": "First Name", "local_id": "@fld-1", "value": ""}],
        "dropdowns": [{"id": "deg", "label": "Degree", "local_id": "@drop-1", "value": ""}],
        "buttons": [{"id": "sub", "text": "Apply", "local_id": "@btn-1", "action": "submit"}],
    }
    summary = InspectionFormatterService.format_summary(data)
    assert "[@fld-1]" in summary
    assert "[@drop-1]" in summary
    assert "[@btn-1]" in summary
