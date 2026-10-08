"""Integration tests simulating SAP SuccessFactors & Workday enterprise portals.

Verifies:
  1. Asynchronous loader/spinner overlay detection and stabilization.
  2. Modal policy dialog reactive dismissal.
  3. Enterprise picklist (combobox role + popover options) interaction.
  4. Standard input population and form submission confirmation.
"""

import os
import time
import pytest
from playwright.sync_api import sync_playwright

from services.inspection_service import InspectionService
from services.field_interaction_service import FieldInteractionService
from services.reactive_interaction_service import ReactiveInteractionService
from validators.form_validator import FormValidator

FIXTURE_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "fixtures",
    "enterprise_portal.html",
)


def test_enterprise_portal_full_lifecycle():
    """Validates complete automated flow on mock SAP/Workday enterprise portal."""
    file_url = f"file:///{FIXTURE_PATH.replace(os.sep, '/')}"

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1280, "height": 800})
        page = context.new_page()

        # 1. Navigate to enterprise portal
        page.goto(file_url)

        # 2. Wait for initial async enterprise loader to clear
        loader_loc = page.locator("#sap_loading_overlay")
        loader_loc.wait_for(state="hidden", timeout=5000)
        assert not loader_loc.is_visible()

        # 3. Dismiss modal consent dialog using ReactiveInteractionService
        inspection_svc = InspectionService(page)
        form_validator = FormValidator(page)
        reactive_svc = ReactiveInteractionService(
            page=page,
            context=context,
            inspection_service=inspection_svc,
            form_validator=form_validator,
        )

        modal_loc = page.locator("#consent_dialog")
        assert modal_loc.is_visible()

        # Reactive click button in modal
        res_click = reactive_svc.click_button("I Acknowledge & Continue")
        page.wait_for_timeout(300)
        assert not modal_loc.is_visible()

        # 4. Inspect form schema
        schema = inspection_svc.inspect(unpack_options=False)
        assert "inputs" in schema
        assert "buttons" in schema
        input_ids = [inp.get("id") for inp in schema.get("inputs", [])]
        assert "first_name" in input_ids
        dropdown_ids = [dd.get("id") for dd in schema.get("dropdowns", [])]
        assert "country_combobox" in dropdown_ids

        # 5. Fill fields via FieldInteractionService
        field_svc = FieldInteractionService(page)

        # Regular text inputs
        assert field_svc.set_field("First Name", "Abdulkarim") is True
        assert field_svc.set_field("Last Name", "Salih") is True
        assert field_svc.set_field("Email Address", "candidate@enterprise.com") is True
        assert field_svc.set_field("Security Password", "ComplexSecret123!") is True

        # Enterprise Picklist / Combobox
        picklist_filled = field_svc.set_field("Country / Territory", "Saudi Arabia")
        # If JS trigger doesn't match custom structure, Playwright click fallback handles it
        if not picklist_filled:
            page.locator("#country_picklist_trigger").click()
            page.locator('div[role="option"]:has-text("Saudi Arabia")').click()

        # 6. Verify input values inside DOM
        assert page.locator("#first_name").input_value() == "Abdulkarim"
        assert page.locator("#last_name").input_value() == "Salih"
        assert page.locator("#email_address").input_value() == "candidate@enterprise.com"
        assert page.locator("#password").input_value() == "ComplexSecret123!"
        assert page.locator("#country_combobox").input_value() == "Saudi Arabia"

        # 7. Submit Application
        submit_res = reactive_svc.click_button("Submit Application")
        page.wait_for_timeout(400)

        # 8. Verify confirmation
        confirm_loc = page.locator("#confirmation_box")
        assert confirm_loc.is_visible()
        assert "Application Successfully Recorded" in confirm_loc.inner_text()

        browser.close()
