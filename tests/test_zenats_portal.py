"""Test case for custom-styled choice elements and tabbed job portals (e.g. ZenATS, ZenHR)."""

import pytest
from playwright.sync_api import sync_playwright
from adapters.dom.inspection import INSPECT_PAGE_DOM_SCRIPT
from adapters.dom.lifecycle import EXPAND_ALL_SECTIONS_SCRIPT
from adapters.dom.set_field import SET_FIELD_DOM_SCRIPT

def test_zenats_custom_styled_radio_and_tab_revelation():
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page()
        try:
            html_content = """
            <html>
            <head>
                <style>
                    .hidden { display: none !important; }
                    .radio-button-component { display: none; }
                    .radio-button-label-component { display: inline-block; cursor: pointer; padding: 4px 8px; }
                </style>
            </head>
            <body>
                <div id="overview">
                    <h1>Draftsman / BIM Modeler</h1>
                    <p>Job summary text...</p>
                    <button class="overview-apply-btn zenhr-btn">Apply</button>
                    <a class="tab_link" href="/public_job/application">Application</a>
                </div>
                <div id="application" class="tab-item hidden">
                    <form id="new_candidate">
                        <div class="form-group">
                            <label class="required control-label" for="candidate_first_name">First Name</label>
                            <input type="text" id="candidate_first_name" name="candidate[first_name]" required="required" />
                        </div>
                        <div class="form-group">
                            <label class="required control-label" for="candidate_last_name">Last Name</label>
                            <input type="text" id="candidate_last_name" name="candidate[last_name]" required="required" />
                        </div>
                        <div class="form-group">
                            <label class="required control-label" for="candidate_email">Email</label>
                            <input type="email" id="candidate_email" name="candidate[email]" required="required" />
                        </div>
                        <div class="form-group">
                            <label class="required control-label" for="candidate_phone_number">Phone</label>
                            <input type="number" id="candidate_phone_number" name="candidate[phone_number]" required="required" />
                        </div>
                        <div class="form-group">
                            <label class="required control-label" for="status_89100">Nationality</label>
                            <div class="input-group">
                                <div class="radio-button-component-block">
                                    <input class="radio-button-component" id="questions_89100_choice_83613" required="required" type="radio" value="choice_83613" name="questions[89100]">
                                    <label class="radio-button-label-component" for="questions_89100_choice_83613">Saudi</label>
                                </div>
                                <div class="radio-button-component-block">
                                    <input class="radio-button-component" id="questions_89100_choice_83614" required="required" type="radio" value="choice_83614" name="questions[89100]">
                                    <label class="radio-button-label-component" for="questions_89100_choice_83614">Non - Saudi</label>
                                </div>
                            </div>
                        </div>
                        <div class="form-group">
                            <label class="required control-label" for="questions_89102">I Have experience in contracting and construction companies</label>
                            <div class="input-group">
                                <div class="radio-button-component-block">
                                    <input class="radio-button-component" id="questions_89102_yes" required="required" type="radio" value="yes" name="questions[89102]">
                                    <label class="radio-button-label-component" for="questions_89102_yes">Yes</label>
                                </div>
                                <div class="radio-button-component-block">
                                    <input class="radio-button-component" id="questions_89102_no" required="required" type="radio" value="no" name="questions[89102]">
                                    <label class="radio-button-label-component" for="questions_89102_no">No</label>
                                </div>
                            </div>
                        </div>
                        <div class="form-group">
                            <label class="control-label" for="candidate_resume">CV</label>
                            <input type="file" id="candidate_resume" name="candidate[resume]" required="required" />
                        </div>
                        <input type="submit" name="commit" value="Submit Application" />
                    </form>
                </div>
                <script>
                    document.querySelector('.overview-apply-btn').addEventListener('click', function() {
                        document.getElementById('overview').classList.add('hidden');
                        document.getElementById('application').classList.remove('hidden');
                    });
                </script>
            </body>
            </html>
            """
            page.set_content(html_content)

            # 1. Initially, #application is hidden. Test expand_all_sections reveals it.
            expanded = page.evaluate(EXPAND_ALL_SECTIONS_SCRIPT)
            assert expanded >= 1

            app_display = page.evaluate("() => window.getComputedStyle(document.getElementById('application')).display")
            assert app_display != "none"

            # 2. Inspect the form schema
            schema = page.evaluate(INSPECT_PAGE_DOM_SCRIPT, {"puaMode": "strip"})
            assert len(schema["inputs"]) >= 4
            assert any(inp["id"] == "candidate_first_name" for inp in schema["inputs"])
            assert any(inp["id"] == "candidate_last_name" for inp in schema["inputs"])
            assert any(inp["id"] == "candidate_email" for inp in schema["inputs"])
            assert any(inp["id"] == "candidate_phone_number" for inp in schema["inputs"])

            # 3. Verify choice groups extracted cleanly with human-readable labels
            assert len(schema["choices"]) == 2
            nat_group = next((c for c in schema["choices"] if "Nationality" in c["label"]), None)
            assert nat_group is not None
            assert "Saudi" in nat_group["options"]
            assert "Non - Saudi" in nat_group["options"]

            exp_group = next((c for c in schema["choices"] if "contracting and construction" in c["label"]), None)
            assert exp_group is not None
            assert "Yes" in exp_group["options"]
            assert "No" in exp_group["options"]

            # 4. Verify setting choice value sets checked and dispatches events
            res = page.evaluate(SET_FIELD_DOM_SCRIPT, ["Nationality", "Saudi", "choice", None])
            assert res["success"] is True

            saudi_checked = page.evaluate("() => document.getElementById('questions_89100_choice_83613').checked")
            assert saudi_checked is True

            res2 = page.evaluate(SET_FIELD_DOM_SCRIPT, ["contracting and construction", "Yes", "choice", None])
            assert res2["success"] is True

            yes_checked = page.evaluate("() => document.getElementById('questions_89102_yes').checked")
            assert yes_checked is True
        finally:
            browser.close()
