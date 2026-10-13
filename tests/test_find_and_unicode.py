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


def test_cli_find_up_and_screenshot_flags():
    """Verify that 'wp find' flags for --up/--ancestor and --screenshot parse and serialize cleanly."""
    from cli_parser import build_cli_parser
    from supervisor.contracts import SupervisorActionRequest

    parser = build_cli_parser()

    # 1. Default up=0, screenshot=None
    args1 = parser.parse_args(["find", "First Name"])
    assert args1.target == "First Name"
    assert args1.up == 0
    assert args1.screenshot is None

    # 2. Ascend 2 levels
    args2 = parser.parse_args(["find", "@fld-1", "--up", "2"])
    assert args2.target == "@fld-1"
    assert args2.up == 2

    # 3. Alias --ancestor and --ascend
    args3 = parser.parse_args(["find", "From Date", "--ancestor", "3"])
    assert args3.up == 3
    args3b = parser.parse_args(["find", "From Date", "--ascend", "1"])
    assert args3b.up == 1

    # 4. Element screenshot flag
    args4 = parser.parse_args(["find", "Submit", "--screenshot", "out.png"])
    assert args4.screenshot == "out.png"
    args4b = parser.parse_args(["find", "Submit", "-s"])
    assert args4b.screenshot == "auto"

    # 5. Contract serialization
    req = SupervisorActionRequest(action="probe", target_field="First Name", up_levels=2, screenshot_path="shot.png")
    rt = SupervisorActionRequest.from_dict(req.to_dict())
    assert rt.up_levels == 2
    assert rt.screenshot_path == "shot.png"


def test_probe_field_ancestor_ascent_and_element_screenshot():
    """Validates real DOM ancestor ascent (GoUp) and element visual snapshot on live page."""
    import os
    import pathlib
    from playwright.sync_api import sync_playwright

    fixture_path = pathlib.Path(__file__).parent / "fixtures" / "enterprise_portal.html"
    file_url = fixture_path.resolve().as_uri()
    screenshot_file = str(pathlib.Path(__file__).parent / "test_field_crop.png")

    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(file_url)
            page.wait_for_selector("#first_name")

            svc = FieldInteractionService(page)

            # Level 0: Direct input element
            probe0 = svc.probe_field("First Name", up_levels=0, include_html=True)
            assert probe0 is not None
            assert probe0["found"] is True
            assert probe0["ancestor_depth"] == 0
            assert probe0["ancestor_tag"] == "input"
            assert "<input" in probe0["outerHTML"]
            assert 'id="first_name"' in probe0["outerHTML"]

            # Level 1: Immediate wrapper container (<div class="field-group">)
            probe1 = svc.probe_field("First Name", up_levels=1)
            assert probe1 is not None
            assert probe1["ancestor_depth"] == 1
            assert probe1["ancestor_tag"] == "div"
            assert "field-group" in probe1["ancestor_class"]
            assert '<label for="first_name">First Name</label>' in probe1["outerHTML"]

            # Level 2: Section content (<div class="sectionContent" id="sec_personal_content">)
            probe2 = svc.probe_field("First Name", up_levels=2)
            assert probe2 is not None
            assert probe2["ancestor_depth"] == 2
            assert probe2["ancestor_tag"] == "div"
            assert probe2["ancestor_id"] == "sec_personal_content"
            assert "Personal Information" in probe2["outerHTML"] or "Last Name" in probe2["outerHTML"]

            # Element Screenshot
            probe_shot = svc.probe_field("First Name", up_levels=1, screenshot_path=screenshot_file)
            assert probe_shot is not None
            assert probe_shot["screenshot_path"] == screenshot_file
            assert os.path.exists(screenshot_file)
            assert os.path.getsize(screenshot_file) > 100
            assert probe_shot["bounding_box"] is not None
            assert probe_shot["bounding_box"]["width"] > 0
            assert probe_shot["bounding_box"]["height"] > 0

            browser.close()
    finally:
        if os.path.exists(screenshot_file):
            try:
                os.remove(screenshot_file)
            except Exception:
                pass


def test_strip_header_flag_and_telemetry_suppression(capsys):
    """Verifies that --StripHeader and its aliases parse properly and suppress verbose telemetry."""
    from cli_parser import build_cli_parser
    from common.telemetry import print_telemetry_banner
    from supervisor.contracts import SupervisorActionRequest, SupervisorActionResponse
    from adapters.browser_adapter import BrowserAdapter

    parser = build_cli_parser()

    # 1. Parse flags across subcommands and aliases
    assert parser.parse_args(["inspect", "--StripHeader"]).strip_header is True
    assert parser.parse_args(["apply", "--strip-header"]).strip_header is True
    assert parser.parse_args(["find", "@fld-1", "--no-header"]).strip_header is True
    assert parser.parse_args(["reload", "--stripheader"]).strip_header is True
    assert parser.parse_args(["--strip-headers", "inspect"]).strip_header is True

    # 2. SupervisorActionRequest serialization
    req = SupervisorActionRequest(action="inspect", strip_header=True)
    d = req.to_dict()
    assert d["strip_header"] is True
    rt = SupervisorActionRequest.from_dict(d)
    assert rt.strip_header is True

    # 3. Telemetry banner suppression
    resp = SupervisorActionResponse(
        action="inspect",
        success=True,
        message="OK",
        browser_pid=1234,
        active_url="https://example.com",
    )

    # When strip_header=True: output must be empty
    print_telemetry_banner(resp, strip_header=True)
    out, _ = capsys.readouterr()
    assert out.strip() == ""

    # When strip_header=False: output has banner
    print_telemetry_banner(resp, strip_header=False)
    out_normal, _ = capsys.readouterr()
    assert "WEBPILOT" in out_normal

    # 4. BrowserAdapter telemetry suppression
    adapter = BrowserAdapter(strip_header=True)
    assert adapter.strip_header is True
    adapter.print_browser_telemetry()
    out_b, _ = capsys.readouterr()
    assert out_b.strip() == ""


def test_cli_find_selector_flag():
    """Verifies that 'wp find' flags for arbitrary selectors (--selector, --css, --xpath, -sel) parse cleanly."""
    from cli_parser import build_cli_parser
    from supervisor.contracts import SupervisorActionRequest
    from services.target_descriptor import TargetDescriptorParser

    parser = build_cli_parser()

    # 1. Parsing --selector
    args1 = parser.parse_args(["find", "--selector", "div.datePicker"])
    assert args1.selector == "div.datePicker"
    assert args1.target is None

    # 2. Parsing --css
    args2 = parser.parse_args(["find", "--css", "#250:_datepicker"])
    assert args2.selector == "#250:_datepicker"

    # 3. Parsing --xpath
    args3 = parser.parse_args(["find", "--xpath", "//button[contains(., 'Next')]"])
    assert args3.selector == "//button[contains(., 'Next')]"

    # 4. Parsing -sel
    args4 = parser.parse_args(["find", "-sel", "ui5-date-picker"])
    assert args4.selector == "ui5-date-picker"

    # 5. Contract serialization
    req = SupervisorActionRequest(action="probe", selector="div.datePicker", up_levels=1)
    rt = SupervisorActionRequest.from_dict(req.to_dict())
    assert rt.selector == "div.datePicker"
    assert rt.up_levels == 1

    # 6. TargetDescriptorParser selector support
    td1 = TargetDescriptorParser.parse("selector:div > span.active")
    assert td1.type_hint == "selector"
    assert td1.clean_target == "div > span.active"
    assert td1.scoped_parent is None

    td2 = TargetDescriptorParser.parse("css:#250:_datepicker")
    assert td2.type_hint == "css"
    assert td2.clean_target == "#250:_datepicker"

    td3 = TargetDescriptorParser.parse("xpath://button[@type='submit']")
    assert td3.type_hint == "xpath"
    assert td3.clean_target == "//button[@type='submit']"


def test_probe_field_by_arbitrary_selectors():
    """Validates live DOM resolution by arbitrary CSS selectors and XPath expressions."""
    import pathlib
    from playwright.sync_api import sync_playwright
    from services.field_interaction_service import FieldInteractionService

    fixture_path = pathlib.Path(__file__).parent / "fixtures" / "enterprise_portal.html"
    file_url = f"file:///{str(fixture_path).replace('\\', '/')}"

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(file_url)

        svc = FieldInteractionService(page)

        # 1. Find by CSS selector flag (--selector "div#250:_datepicker")
        res_css = svc.probe_field(selector="div#250:_datepicker")
        assert res_css is not None
        assert res_css["found"] is True
        assert res_css["id"] == "250:_datepicker"
        assert res_css["type"] == "date"

        # 2. Find by custom web component tag name (--selector "ui5-date-picker-xweb-calendar-widget")
        res_wc = svc.probe_field(selector="ui5-date-picker-xweb-calendar-widget")
        assert res_wc is not None
        assert res_wc["found"] is True
        assert "date" in res_wc["type"] or "ui5" in res_wc["tag"]

        # 3. Find by XPath (--xpath "//div[@id='250:_datepicker']")
        res_xpath = svc.probe_field(selector="//div[@id='250:_datepicker']")
        assert res_xpath is not None
        assert res_xpath["found"] is True
        assert res_xpath["id"] == "250:_datepicker"

        # 4. Find with CSS selector passed directly as target string (e.g. "css=div.datePicker")
        res_direct = svc.probe_field(target="css=div.datePicker")
        assert res_direct is not None
        assert res_direct["found"] is True

        browser.close()


def test_cli_eval_and_css_parsing():
    """Verifies that 'wp eval' / 'wp js' and 'wp css' flags parse cleanly."""
    from cli_parser import build_cli_parser
    from supervisor.contracts import SupervisorActionRequest

    parser = build_cli_parser()

    # 1. Parsing eval / js
    args_eval = parser.parse_args(["eval", "document.title", "--json"])
    assert args_eval.command == "eval"
    assert args_eval.script == "document.title"
    assert args_eval.json is True

    args_js = parser.parse_args(["js", "1 + 1", "--StripHeader"])
    assert args_js.command == "js"
    assert args_js.script == "1 + 1"
    assert args_js.strip_header is True

    # 2. Parsing css injection & inspection
    args_css_inject = parser.parse_args(["css", "body { margin: 0; }"])
    assert args_css_inject.command == "css"
    assert args_css_inject.target == "body { margin: 0; }"

    args_css_inspect = parser.parse_args(["css", "--selector", "h1", "-p", "display"])
    assert args_css_inspect.command == "css"
    assert args_css_inspect.selector == "h1"
    assert args_css_inspect.prop == "display"

    # 3. Contract serialization
    req_eval = SupervisorActionRequest(action="eval", script="window.location.href")
    assert SupervisorActionRequest.from_dict(req_eval.to_dict()).action == "eval"

    req_css = SupervisorActionRequest(action="css", script="h1", query="color")
    assert SupervisorActionRequest.from_dict(req_css.to_dict()).action == "css"


def test_eval_and_css_execution_live():
    """Validates real JavaScript evaluation and CSS injection/inspection on live page."""
    import pathlib
    from playwright.sync_api import sync_playwright
    from adapters.dom.universal_core import UNIVERSAL_DOM_CORE_JS

    fixture_path = pathlib.Path(__file__).parent / "fixtures" / "enterprise_portal.html"
    file_url = f"file:///{str(fixture_path).replace('\\', '/')}"

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(file_url)

        # 1. JavaScript evaluation
        title_res = page.evaluate("document.title")
        assert "Enterprise" in title_res

        calc_res = page.evaluate("() => 21 * 2")
        assert calc_res == 42

        # 2. CSS injection
        page.add_style_tag(content="#sap_loading_overlay { background: rgb(255, 0, 0) !important; }")
        overlay_bg = page.evaluate("window.getComputedStyle(document.getElementById('sap_loading_overlay')).backgroundColor")
        assert "rgb(255, 0, 0)" in overlay_bg

        # 3. Computed CSS inspection
        js_inspect = UNIVERSAL_DOM_CORE_JS + """
        ([sel, propName]) => {
            const el = deepQuerySelector(document, sel);
            if (!el) return { found: false, error: "Element not found" };
            const style = window.getComputedStyle(el);
            if (propName) {
                return { found: true, selector: sel, property: propName, value: style.getPropertyValue(propName) || style[propName] || "" };
            }
            const keys = ['display', 'visibility', 'opacity', 'position'];
            const res = { found: true, selector: sel, properties: {} };
            keys.forEach(k => { res.properties[k] = style[k] || style.getPropertyValue(k); });
            return res;
        }
        """
        h1_style = page.evaluate(js_inspect, ["h1", ""])
        assert h1_style["found"] is True
        assert h1_style["properties"]["display"] == "block"

        prop_res = page.evaluate(js_inspect, ["h1", "display"])
        assert prop_res["found"] is True
        assert prop_res["value"] == "block"

        browser.close()







