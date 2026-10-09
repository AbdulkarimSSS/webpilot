"""Tests for post-fill DOM verification, settle delays, pre-submit check, and honesty contract."""

import pytest
from unittest.mock import MagicMock
from services.field_interaction_service import FieldInteractionService
from supervisor.worker_process import OperationalWorker
from supervisor.contracts import SupervisorActionRequest


def test_field_interaction_service_matching_logic():
    """Verify FieldInteractionService._match_actual_dom_data across all control types."""
    svc = FieldInteractionService(page=MagicMock())

    # 1. Native <select>
    assert svc._match_actual_dom_data({"type": "select", "value": "CA", "text": "California"}, "California") is True
    assert svc._match_actual_dom_data({"type": "select", "value": "CA", "text": "California"}, "CA") is True
    assert svc._match_actual_dom_data({"type": "select", "value": "NY", "text": "New York"}, "California") is False

    # 2. Checkbox / Switch
    assert svc._match_actual_dom_data({"type": "checkbox", "checked": True}, True) is True
    assert svc._match_actual_dom_data({"type": "checkbox", "checked": True}, "yes") is True
    assert svc._match_actual_dom_data({"type": "checkbox", "checked": False}, True) is False
    assert svc._match_actual_dom_data({"type": "checkbox", "checked": False}, False) is True
    assert svc._match_actual_dom_data({"type": "checkbox", "checked": False}, "no") is True

    # 3. Radio & Radio group
    assert svc._match_actual_dom_data({"type": "radio", "checked": True, "value": "Option 1"}, "Option 1") is True
    assert svc._match_actual_dom_data({"type": "radio", "checked": False, "value": "Option 1"}, "Option 1") is False
    assert svc._match_actual_dom_data({"type": "radio_group", "value": "Full Time"}, "Full Time") is True
    assert svc._match_actual_dom_data({"type": "radio_group", "value": "Full Time"}, "Part Time") is False

    # 4. Custom Combobox / Picklist
    assert svc._match_actual_dom_data({"type": "picklist", "value": "SA", "selected_text": "Saudi Arabia"}, "Saudi Arabia") is True
    assert svc._match_actual_dom_data({"type": "picklist", "value": "SA", "selected_text": ""}, "SA") is True

    # 5. Text / Textarea with Phone / Number formatting normalization
    assert svc._match_actual_dom_data({"type": "input", "value": "John Doe"}, "John Doe") is True
    assert svc._match_actual_dom_data({"type": "input", "value": "(123) 456-7890"}, "1234567890") is True
    assert svc._match_actual_dom_data({"type": "input", "value": ""}, "John") is False


def test_pre_submit_barrier_catches_delayed_silent_revert(monkeypatch):
    """Verify that a delayed revert (e.g. S44) is caught by pre-submit verification pass."""
    worker = OperationalWorker()

    mock_coord = MagicMock()
    mock_coord.page.url = "https://example.com/form"
    mock_coord.page.title.return_value = "Test Form"
    mock_coord.page.is_closed.return_value = False
    mock_coord.page.locator.return_value.count.return_value = 0
    mock_coord.context.pages = [mock_coord.page]
    worker.coordinator = mock_coord
    monkeypatch.setattr(worker, "_ensure_session", lambda req: mock_coord)

    # State tracking: first_name is verified at fill time, but reverts before submit
    call_counts = {"first_name": 0}

    mock_field_svc = MagicMock()
    mock_field_svc.set_field.return_value = True

    def dynamic_verify(k, v, settle_delay_ms=50):
        if k == "first_name":
            call_counts["first_name"] += 1
            # First call is during initial fill (passes)
            # Second call is during pre-submit check (fails due to delayed revert like S44)
            if call_counts["first_name"] > 1:
                return False
        return True

    mock_field_svc.verify_field_value.side_effect = dynamic_verify

    mock_reactive = MagicMock()
    mock_reactive.click_button.return_value = {"success": True}

    monkeypatch.setattr("supervisor.worker_process.FieldInteractionService", lambda page: mock_field_svc)
    monkeypatch.setattr("supervisor.worker_process.AuthNavigationService", lambda p, c: MagicMock())
    monkeypatch.setattr("supervisor.worker_process.FormValidator", lambda p: MagicMock(get_validation_errors=lambda: []))
    monkeypatch.setattr("supervisor.worker_process.InspectionService", lambda p: MagicMock())
    monkeypatch.setattr("supervisor.worker_process.ReactiveInteractionService", lambda **kwargs: mock_reactive)

    req = SupervisorActionRequest(
        action="apply",
        url="https://example.com/form",
        fill_arguments=["first_name=Alice", "last_name=Smith"],
        press_buttons=["Submit"],
        auto_inspect=False,
    )

    resp = worker._handle_apply(req)

    # Both were initially set, but pre-submit check caught the reverted first_name
    assert resp.success is False
    assert resp.unconfirmed_fields == [("first_name", "Alice")]
    assert resp.confirmed_fields == [("last_name", "Smith")]
