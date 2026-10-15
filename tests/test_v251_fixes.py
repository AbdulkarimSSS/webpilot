"""Comprehensive tests for v2.5.1 bug fixes and native tab management."""

import pytest
from unittest.mock import MagicMock
from playwright.sync_api import sync_playwright

from services.dom_verifier import DOMDataMatcher
from adapters.tab_manager import TabManager
from supervisor.worker_process import _sanitize_eval_result, OperationalWorker
from supervisor.contracts import SupervisorActionRequest, SupervisorActionResponse


# ---------------------------------------------------------------------------
# Test 1: DOMDataMatcher Prefix Stripping & Regex Evaluation (Bug 4)
# ---------------------------------------------------------------------------
def test_dom_data_matcher_prefix_stripping_and_regex():
    # 1. Standard text with text: and val: prefixes
    assert DOMDataMatcher.match({"value": "Male", "type": "text"}, "text:Male")
    assert DOMDataMatcher.match({"value": "male", "type": "text"}, "val:Male")
    assert DOMDataMatcher.match("Male", "text:Male")

    # 2. Regex matching on picklist
    actual_picklist = {
        "type": "picklist",
        "value": "SA",
        "selected_text": "Saudi Arabia",
    }
    assert DOMDataMatcher.match(actual_picklist, "re:^Saudi\\s+Arabia$")
    assert DOMDataMatcher.match(actual_picklist, "regex:^saudi")
    assert not DOMDataMatcher.match(actual_picklist, "re:^Emirates$")

    # 3. Regex matching on select
    actual_select = {
        "type": "select",
        "value": "US",
        "text": "United States of America",
    }
    assert DOMDataMatcher.match(actual_select, "re:^United\\s+States")
    assert DOMDataMatcher.match(actual_select, "regex:america$")
    assert DOMDataMatcher.match(actual_select, "val:US")

    # 4. Regex matching on standard input
    actual_input = {
        "type": "text",
        "value": "Software Engineer",
    }
    assert DOMDataMatcher.match(actual_input, "re:software\\s+engineer")
    assert DOMDataMatcher.match(actual_input, "regex:^soft.*")
    assert not DOMDataMatcher.match(actual_input, "regex:^hardware")


# ---------------------------------------------------------------------------
# Test 2: Sanitization of Circular / Infinite Recursion Eval Result (Bug 6)
# ---------------------------------------------------------------------------
def test_sanitize_eval_result_circular_objects():
    # Direct self-referencing dict
    cyclic = {"name": "root"}
    cyclic["self"] = cyclic

    sanitized = _sanitize_eval_result(cyclic)
    assert sanitized["name"] == "root"
    assert sanitized["self"] == "[Circular]"

    # Nested deep circular list
    l1 = [1, 2]
    l1.append(l1)
    sanitized_l = _sanitize_eval_result(l1)
    assert sanitized_l[0] == 1
    assert sanitized_l[2] == "[Circular]"


# ---------------------------------------------------------------------------
# Test 3: TabManager create_new_tab and safe close_tab
# ---------------------------------------------------------------------------
def test_tab_manager_lifecycle():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context()

        # Initial state: 0 pages
        assert len(ctx.pages) == 0

        # Create new tab
        p1 = TabManager.create_new_tab(ctx, "about:blank")
        assert len(ctx.pages) == 1
        assert ctx.pages[0] == p1

        # Create second tab
        p2 = TabManager.create_new_tab(ctx, "about:blank")
        assert len(ctx.pages) == 2

        # Enumerate tabs
        tabs = TabManager.list_open_tabs(ctx, active_page=p2)
        assert len(tabs) == 2
        assert tabs[0]["index"] == 0
        assert tabs[1]["index"] == 1
        assert tabs[1]["is_active"] is True

        # Switch tab
        switched = TabManager.switch_to_tab(ctx, 0)
        assert switched == p1

        # Close specific tab (Tab 0)
        new_active = TabManager.close_tab(ctx, index=0)
        assert len(ctx.pages) == 1
        assert new_active == p2

        # Close the last remaining tab -> should spawn about:blank so context never crashes
        survivor = TabManager.close_tab(ctx)
        assert len(ctx.pages) == 1
        assert survivor.url == "about:blank"

        browser.close()


# ---------------------------------------------------------------------------
# Test 4: Inspection of Scrolled Element (Bug 1) and Colon IDs (Bug 2)
# ---------------------------------------------------------------------------
def test_dom_honeypot_scrolled_offsets_and_colon_ids():
    from adapters.dom_scripts import INSPECT_PAGE_DOM_SCRIPT

    html = """
    <!DOCTYPE html>
    <html>
    <head><title>Colon & Scrolled Test</title></head>
    <body style="height: 3000px; padding-top: 1000px;">
        <!-- Top Section with colon IDs -->
        <div id="57:_container">
            <label for="57:first_name">SAP Colon Input</label>
            <input type="text" id="57:first_name" name="57:first_name" value="Top Value" />
        </div>

        <div style="margin-top: 1500px;" id="bottom_section">
            <label for="250:_select">Cascading Picklist</label>
            <select id="250:_select" data-parent="57:first_name">
                <option value="1">Option 1</option>
            </select>
        </div>
    </body>
    </html>
    """

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.set_content(html)

        # Scroll to bottom so top section gets negative viewport coordinates (rect.bottom < 0)
        page.evaluate("window.scrollTo(0, 2000)")

        # Evaluate inspect DOM script
        data = page.evaluate(INSPECT_PAGE_DOM_SCRIPT, {"puaMode": "strip"})

        # Verify that top input with colon ID was NOT pruned as a honeypot
        inputs = data.get("inputs", [])
        assert any(inp["id"] == "57:first_name" for inp in inputs), "Scrolled input was falsely pruned as honeypot!"

        # Verify cascading parent resolution with colon IDs did not throw DOMException
        dropdowns = data.get("dropdowns", [])
        target_drop = next((d for d in dropdowns if d["id"] == "250:_select"), None)
        assert target_drop is not None
        dep = target_drop.get("dependency")
        assert dep is not None and dep.get("is_dependent") is True
        assert dep.get("parent_id") == "57:first_name"

        browser.close()


# ---------------------------------------------------------------------------
# Test 5: handle_worker_inspect honors tab_index (Bug 5)
# ---------------------------------------------------------------------------
def test_handle_worker_inspect_honors_tab_index():
    from supervisor.worker_handlers import handle_worker_inspect

    worker = MagicMock()
    coord = MagicMock()
    page0 = MagicMock()
    page0.url = "https://tab0.local"
    page1 = MagicMock()
    page1.url = "https://tab1.local"

    worker._ensure_session.return_value = coord
    coord.page = page0
    coord.switch_to_tab.return_value = page1

    # Request with tab_index=1
    req = SupervisorActionRequest(action="inspect", tab_index=1)
    
    # Mocking inspection service
    with pytest.MonkeyPatch.context() as mp:
        mock_svc = MagicMock()
        mock_svc.return_value.inspect.return_value.to_dict.return_value = {"title": "Tab 1 Title", "url": "https://tab1.local"}
        mp.setattr("supervisor.worker_handlers.InspectionService", mock_svc)
        mp.setattr("services.inspection_formatter_service.InspectionFormatterService.format_summary", lambda d: "summary")

        resp = handle_worker_inspect(worker, req)

    coord.switch_to_tab.assert_called_once_with(1)
    assert resp.success is True
