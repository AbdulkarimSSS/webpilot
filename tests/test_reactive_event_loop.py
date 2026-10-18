"""Tests for Event-Driven Reactive Interaction Service (Mutation-First).

Verifies that click_button detects modals, dynamic inputs, redirects, and alerts
instantaneously via micro-polling without any blocking calls to networkidle or load states.
"""

from unittest.mock import MagicMock
from services.reactive_interaction_service import ReactiveInteractionService


def test_click_button_modal_early_exit_without_network_wait():
    """Verify modal opening returns immediately and never invokes wait_for_load_state."""
    mock_page = MagicMock()
    mock_ctx = MagicMock()
    mock_insp = MagicMock()
    mock_val = MagicMock()

    mock_page.url = "https://example.com/job/123"
    mock_ctx.pages = [mock_page]

    # Pre-click evaluation counts: [0 inputs, 0 modals]
    mock_page.evaluate.side_effect = [
        [0, 0],   # baseline counts
        True,     # CLICK_BUTTON_DOM_SCRIPT returns True (clicked)
    ]

    # Mock locator for post-click modal detection
    mock_modal = MagicMock()
    mock_modal.count.return_value = 1  # 1 modal appeared
    mock_modal.first.inner_text.return_value = "Easy Apply to Tech Corp"
    mock_page.locator.return_value = mock_modal

    mock_insp.inspect.return_value = {"inputs": [{"id": "phone"}]}

    svc = ReactiveInteractionService(
        page=mock_page,
        context=mock_ctx,
        inspection_service=mock_insp,
        form_validator=mock_val,
    )

    res = svc.click_button("Easy Apply")

    assert res["success"] is True
    assert res["modal_opened"] is True
    assert "Easy Apply" in res["modal_text"]
    assert res["schema"] == {"inputs": [{"id": "phone"}]}

    # CRITICAL: wait_for_load_state must NEVER be called!
    mock_page.wait_for_load_state.assert_not_called()


def test_click_button_dynamic_inputs_detected():
    """Verify dynamic inputs expansion is detected and returned without network wait."""
    mock_page = MagicMock()
    mock_ctx = MagicMock()
    mock_insp = MagicMock()
    mock_val = MagicMock()

    mock_page.url = "https://example.com/form"
    mock_ctx.pages = [mock_page]

    # Pre-click evaluation counts: [2 inputs, 0 modals]
    mock_page.evaluate.side_effect = [
        [2, 0],   # baseline counts
        True,     # CLICK_BUTTON_DOM_SCRIPT returns True (clicked)
    ]

    # Locator calls:
    # First locator call is SELECTOR_MODAL_DIALOGS (count=0)
    # Second locator call is "input, select, textarea" (count=5 -> +3 new)
    mock_modals_loc = MagicMock()
    mock_modals_loc.count.return_value = 0

    mock_inputs_loc = MagicMock()
    mock_inputs_loc.count.return_value = 5

    def locator_side_effect(sel):
        if "modal" in sel or "dialog" in sel:
            return mock_modals_loc
        return mock_inputs_loc

    mock_page.locator.side_effect = locator_side_effect
    mock_insp.inspect.return_value = {"inputs": [1, 2, 3, 4, 5]}

    svc = ReactiveInteractionService(
        page=mock_page,
        context=mock_ctx,
        inspection_service=mock_insp,
        form_validator=mock_val,
    )

    res = svc.click_button("Add Experience")

    assert res["success"] is True
    assert res["new_inputs_count"] == 3
    mock_page.wait_for_load_state.assert_not_called()
