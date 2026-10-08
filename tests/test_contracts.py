"""Tests for canonical wire-contract SSOT in constants.contracts."""

import pytest
from constants.contracts import (
    SCHEMA_KEYS,
    SCHEMA_KEY_TITLE,
    SCHEMA_KEY_URL,
    SCHEMA_KEY_SECTIONS,
    SCHEMA_KEY_INPUTS,
    SCHEMA_KEY_DROPDOWNS,
    SCHEMA_KEY_CHOICES,
    SCHEMA_KEY_FILE_UPLOADS,
    SCHEMA_KEY_ALREADY_UPLOADED,
    SCHEMA_KEY_BUTTONS,
    FIELD_KEY_ID,
    FIELD_KEY_LABEL,
    FIELD_KEY_TYPE,
    FIELD_KEY_REQUIRED,
    FIELD_KEY_VALUE,
    WIDGET_TYPE_TEXT,
    WIDGET_TYPE_SELECT,
    WIDGET_TYPE_RADIO,
    WIDGET_TYPE_BUTTON,
    OUTCOME_KEYS,
    OUTCOME_KEY_SUCCESS,
    OUTCOME_KEY_TARGET,
    OUTCOME_KEY_REDIRECTED,
    SUMMARY_KEYS,
    SUMMARY_KEY_CONFIRMED,
    SUMMARY_KEY_UNCONFIRMED,
    SUMMARY_KEY_FAILED,
)
from core.models import (
    InspectionResult,
    InputField,
    DropdownField,
    ChoiceGroup,
    FileUploadField,
    ActionButton,
    FillSummary,
    ReactiveClickOutcome,
    ApplyExecutionResult,
)


def test_inspection_result_matches_canonical_schema():
    """Verify InspectionResult serialization adheres strictly to canonical SCHEMA_KEYS."""
    result = InspectionResult(
        title="Job Application Form",
        url="https://example.com/apply",
        sections=["Personal", "Experience"],
        inputs=[InputField(id="full_name", label="Full Name", type=WIDGET_TYPE_TEXT, required=True, value="Alice")],
        dropdowns=[DropdownField(id="country", label="Country", type=WIDGET_TYPE_SELECT, required=True, value="US")],
        choices=[ChoiceGroup(question="Work Auth?", type=WIDGET_TYPE_RADIO, required=True, options=["Yes", "No"], selected="Yes")],
        file_uploads=[FileUploadField(id="cv", label="Resume", required=True)],
        already_uploaded_files=["previous_cv.pdf"],
        buttons=[ActionButton(id="submit_btn", text="Submit", action=WIDGET_TYPE_BUTTON)],
    )

    d = result.to_dict()
    assert set(d.keys()) == SCHEMA_KEYS
    assert d[SCHEMA_KEY_TITLE] == "Job Application Form"
    assert d[SCHEMA_KEY_URL] == "https://example.com/apply"
    assert len(d[SCHEMA_KEY_INPUTS]) == 1
    assert d[SCHEMA_KEY_INPUTS][0][FIELD_KEY_ID] == "full_name"
    assert d[SCHEMA_KEY_INPUTS][0][FIELD_KEY_LABEL] == "Full Name"
    assert d[SCHEMA_KEY_INPUTS][0][FIELD_KEY_REQUIRED] is True

    # Test round-trip reconstruction
    reconstructed = InspectionResult.from_dict(d)
    assert reconstructed.title == result.title
    assert len(reconstructed.inputs) == 1
    assert reconstructed.inputs[0].label == "Full Name"


def test_fill_summary_matches_canonical_keys():
    """Verify FillSummary serialization adheres strictly to SUMMARY_KEYS."""
    summary = FillSummary(
        confirmed=[("name", "Alice")],
        unconfirmed=[("phone", "phone_sample_val")],
        failed=[("missing_field", "xyz")],
    )

    d = summary.to_dict()
    assert set(d.keys()) == SUMMARY_KEYS
    assert ("name", "Alice") in d[SUMMARY_KEY_CONFIRMED]
    assert ("phone", "phone_sample_val") in d[SUMMARY_KEY_UNCONFIRMED]
    assert ("missing_field", "xyz") in d[SUMMARY_KEY_FAILED]


def test_reactive_outcome_matches_canonical_keys():
    """Verify ReactiveClickOutcome serialization adheres strictly to OUTCOME_KEYS."""
    outcome = ReactiveClickOutcome(
        success=True,
        target="Submit Button",
        redirected=True,
        new_window=False,
        new_url="https://example.com/confirmation",
        modal_opened=False,
        modal_text="",
        new_inputs_count=0,
        schema=None,
        alerts=["Application received"],
    )

    d = outcome.to_dict()
    assert set(d.keys()) == OUTCOME_KEYS
    assert d[OUTCOME_KEY_SUCCESS] is True
    assert d[OUTCOME_KEY_TARGET] == "Submit Button"
    assert d[OUTCOME_KEY_REDIRECTED] is True


def test_apply_execution_result_serialization():
    """Verify ApplyExecutionResult serialization structure."""
    exec_res = ApplyExecutionResult(
        confirmed_fields=[("first_name", "Alice")],
        unconfirmed_fields=[],
        failed_fields=[],
        final_url="https://example.com/success",
        validation_errors=[],
        submitted=True,
        confirmation_screenshot="/path/to/screenshot.png",
    )
    d = exec_res.to_dict()
    assert d["submitted"] is True
    assert d["final_url"] == "https://example.com/success"
    assert d["confirmed_fields"] == [("first_name", "Alice")]
