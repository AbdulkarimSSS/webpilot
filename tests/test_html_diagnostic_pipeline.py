"""Comprehensive test suite for the Precision HTML Diagnostics Pipeline for `webpilot find --html`."""

import argparse
import io
import sys
import pytest
from bs4 import BeautifulSoup

from services.html_diagnostic_service import (
    HTMLDiagnosticService,
    DiagnosticSearchNotFoundError,
)
from cli_commands.find_cmd import find_cmd


# Realistic accordion section with 22 fields
ACCORDION_HTML = """
<div id="sec-2" class="accordion-section" data-section="compensation">
  <h2 class="accordion-header">Compensation & Benefits</h2>
  <div class="accordion-body">
    <div class="field-wrapper form-group" data-field="fld-1">
      <label for="cur_salary">Current Salary</label>
      <input id="cur_salary" name="current_salary" type="text" placeholder="e.g. 100,000" class="form-control" />
      <span class="help-text">Annual gross salary in USD</span>
    </div>
    <div class="field-wrapper form-group" data-field="fld-2">
      <label for="exp_salary">Expected Salary</label>
      <input id="exp_salary" name="expected_salary" type="text" class="form-control" />
    </div>
    <div class="field-wrapper form-group" data-field="fld-3">
      <label for="bonus">Annual Bonus</label>
      <input id="bonus" name="bonus" type="text" class="form-control" />
    </div>
    <div class="field-wrapper form-group" data-field="fld-4">
      <label for="equity">Equity Grant</label>
      <input id="equity" name="equity" type="text" class="form-control" />
    </div>
    <div class="field-wrapper form-group" data-field="fld-5">
      <label for="currency">Currency</label>
      <select id="currency" name="currency" class="form-control"><option>USD</option><option>EUR</option></select>
    </div>
    <div class="field-wrapper form-group" data-field="fld-6">
      <label for="relocation">Relocation Assistance</label>
      <input id="relocation" name="relocation" type="checkbox" />
    </div>
    <div class="field-wrapper form-group" data-field="fld-7"><label for="sign_on">Sign-on Bonus</label><input id="sign_on" name="sign_on"/></div>
    <div class="field-wrapper form-group" data-field="fld-8"><label for="health">Health Insurance</label><input id="health" name="health"/></div>
    <div class="field-wrapper form-group" data-field="fld-9"><label for="dental">Dental Insurance</label><input id="dental" name="dental"/></div>
    <div class="field-wrapper form-group" data-field="fld-10"><label for="vision">Vision Insurance</label><input id="vision" name="vision"/></div>
    <div class="field-wrapper form-group" data-field="fld-11"><label for="pension">Pension Plan</label><input id="pension" name="pension"/></div>
    <div class="field-wrapper form-group" data-field="fld-12"><label for="vacation">Paid Vacation Days</label><input id="vacation" name="vacation"/></div>
    <div class="field-wrapper form-group" data-field="fld-13"><label for="sick_leave">Sick Leave</label><input id="sick_leave" name="sick_leave"/></div>
    <div class="field-wrapper form-group" data-field="fld-14"><label for="parental_leave">Parental Leave</label><input id="parental_leave" name="parental_leave"/></div>
    <div class="field-wrapper form-group" data-field="fld-15"><label for="commute">Commuter Benefits</label><input id="commute" name="commute"/></div>
    <div class="field-wrapper form-group" data-field="fld-16"><label for="gym">Gym Stipend</label><input id="gym" name="gym"/></div>
    <div class="field-wrapper form-group" data-field="fld-17"><label for="education">Tuition Reimbursement</label><input id="education" name="education"/></div>
    <div class="field-wrapper form-group" data-field="fld-18"><label for="remote">Remote Work Allowance</label><input id="remote" name="remote"/></div>
    <div class="field-wrapper form-group" data-field="fld-19"><label for="phone">Phone Stipend</label><input id="phone" name="phone"/></div>
    <div class="field-wrapper form-group" data-field="fld-20"><label for="internet">Internet Stipend</label><input id="internet" name="internet"/></div>
    <div class="field-wrapper form-group" data-field="fld-21"><label for="stocks">Stock Purchase Plan</label><input id="stocks" name="stocks"/></div>
    <div class="field-wrapper form-group" data-field="fld-22"><label for="notes">Additional Compensation Notes</label><textarea id="notes" name="notes"></textarea></div>
  </div>
</div>
"""


def test_isolated_spine_pruning():
    """Verify searching for 'Salary' prunes unrelated siblings while preserving the spine and field container."""
    result = HTMLDiagnosticService.process_html_pipeline(
        raw_html=ACCORDION_HTML,
        search_query="Current Salary",
        pretty=True,
    )

    # Must preserve the spine down to the container
    assert "Current Salary" in result
    assert "cur_salary" in result
    assert "form-group" in result or "field-wrapper" in result
    assert "accordion-section" in result

    # Sibling field containers must be pruned
    assert "Annual Bonus" not in result
    assert "Equity Grant" not in result
    assert "Gym Stipend" not in result
    assert "Stock Purchase Plan" not in result
    assert "Additional Compensation Notes" not in result


def test_regex_search_query():
    """Verify regex patterns via 're:<pattern>' matching."""
    result = HTMLDiagnosticService.process_html_pipeline(
        raw_html=ACCORDION_HTML,
        search_query="re:^Annual.*Bonus",
        pretty=True,
    )

    assert "Annual Bonus" in result
    assert "bonus" in result
    assert "Current Salary" not in result
    assert "Gym Stipend" not in result


def test_attribute_matching():
    """Verify search matches inside placeholders, names, and data attributes."""
    result = HTMLDiagnosticService.process_html_pipeline(
        raw_html=ACCORDION_HTML,
        search_query="e.g. 100,000",
        pretty=True,
    )

    assert "Current Salary" in result
    assert "cur_salary" in result


def test_fail_fast_on_missing_target():
    """Verify DiagnosticSearchNotFoundError is raised when query is not found."""
    with pytest.raises(DiagnosticSearchNotFoundError) as exc_info:
        HTMLDiagnosticService.process_html_pipeline(
            raw_html=ACCORDION_HTML,
            search_query="NonExistentField12345",
        )
    assert "Search target 'NonExistentField12345' not found within element boundary" in str(exc_info.value)


def test_structural_tag_filter_include():
    """Verify --include retains whitelist tags and unwraps non-included ancestors."""
    sample_html = """
    <div class="field">
      <span>
        <label for="email">Work Email</label>
      </span>
      <input id="email" type="email" />
      <p class="description">We will never share your email.</p>
    </div>
    """
    result = HTMLDiagnosticService.process_html_pipeline(
        raw_html=sample_html,
        include_tags="div,label,input",
        pretty=False,
    )

    assert "<label" in result
    assert "<input" in result
    assert "<p" not in result
    assert "<span" not in result  # unwrapped


def test_structural_tag_filter_exclude_stubbing():
    """Verify --exclude strips noise and stubs SVG/script tags."""
    sample_html = """
    <div class="icon-field">
      <svg viewBox="0 0 100 100"><path d="M10 10 H 90 V 90 H 10 L 10 10"/></svg>
      <script>console.log("noisy tracking script");</script>
      <label>Username</label>
      <input name="user"/>
    </div>
    """
    result = HTMLDiagnosticService.process_html_pipeline(
        raw_html=sample_html,
        exclude_tags="svg,script",
        pretty=True,
    )

    assert "[SVG ICON]" in result
    assert "M10 10 H 90" not in result
    assert "[SCRIPT]" in result
    assert "noisy tracking script" not in result
    assert "Username" in result


def test_exclude_over_include_precedence():
    """Verify exclude takes precedence over include upon direct tag conflict and cleans container interiors."""
    sample_html = """
    <div class="container">
      <svg><circle cx="50" cy="50" r="40"/></svg>
      <label>Test</label>
      <p>Description paragraph</p>
    </div>
    """
    # 1. Direct tag conflict: If svg and p are in both include and exclude, exclude wins
    result = HTMLDiagnosticService.process_html_pipeline(
        raw_html=sample_html,
        include_tags="svg,label,p",
        exclude_tags="svg,p",
        pretty=False,
    )
    # svg is stubbed per STUBBED_TAGS, circle is gone
    assert "[SVG ICON]" in result
    assert "circle" not in result
    # p is completely decomposed
    assert "<p" not in result
    assert "Description paragraph" not in result
    # label is preserved
    assert "<label" in result
    assert "Test" in result

    # 2. Level 2: include retains containers while exclude purges interior noisy tags
    form_html = """
    <form id="login">
      <div class="field">
        <label>Username</label>
        <input type="text" />
        <svg class="icon"><path d="M0 0"/></svg>
        <script>track();</script>
      </div>
    </form>
    """
    res_form = HTMLDiagnosticService.process_html_pipeline(
        raw_html=form_html,
        include_tags="form,div,input,label",
        exclude_tags="svg,script",
        pretty=False,
    )
    assert "<label>Username</label>" in res_form
    assert "<input" in res_form
    assert "[SVG ICON]" in res_form
    assert "[SCRIPT]" in res_form
    assert "track();" not in res_form


def test_line_slicing_5_variants():
    """Verify 1-indexed line slicing semantics across all 5 variants."""
    lines_text = "\n".join([f"Line {i}" for i in range(1, 21)])

    # 1. Variant 1: Explicit range 5:15 (lines 5 through 15 inclusive)
    s1 = HTMLDiagnosticService.apply_line_slice(lines_text, "5:15")
    assert s1.splitlines() == [f"Line {i}" for i in range(5, 16)]

    # 2. Variant 2: Head as bare integer 10 (lines 1 through 10)
    s2 = HTMLDiagnosticService.apply_line_slice(lines_text, "10")
    assert s2.splitlines() == [f"Line {i}" for i in range(1, 11)]

    # 3. Variant 3: Head slice notation :15 (lines 1 through 15)
    s3 = HTMLDiagnosticService.apply_line_slice(lines_text, ":15")
    assert s3.splitlines() == [f"Line {i}" for i in range(1, 16)]

    # 4. Variant 4: Offset to end 15: (lines 15 through 20)
    s4 = HTMLDiagnosticService.apply_line_slice(lines_text, "15:")
    assert s4.splitlines() == [f"Line {i}" for i in range(15, 21)]

    # 5. Variant 5: Tail slice -5: (last 5 lines, lines 16 through 20)
    s5 = HTMLDiagnosticService.apply_line_slice(lines_text, "-5:")
    assert s5.splitlines() == [f"Line {i}" for i in range(16, 21)]


def test_line_slicing_target_anchored_window():
    """Verify target-anchored window preceding line X with banner when exceeding ceiling."""
    # Create 500 lines of 100 characters each (~50,000 characters total)
    large_lines = "\n".join([f"Line {i:03d} " + "x" * 90 for i in range(1, 501)])

    # Target line 500 with default ceiling 20,000 characters
    res = HTMLDiagnosticService.apply_line_slice(large_lines, ":500", max_chars=20000, show_all=False)

    # Must contain target line 500 at the end
    assert "Line 500" in res

    # Must contain the target-anchored window notification banner
    assert "[Note: Displaying target-anchored window preceding line 500" in res
    assert "Use --all to view from line 1]" in res

    # Line 1 must NOT be in the window because ceiling clamped the window backward
    assert "Line 001" not in res

    # Same target-anchored behavior with bare integer Variant 2
    res_bare = HTMLDiagnosticService.apply_line_slice(large_lines, "500", max_chars=20000, show_all=False)
    assert "[Note: Displaying target-anchored window preceding line 500" in res_bare
    assert "Line 500" in res_bare
    assert "Line 001" not in res_bare

    # Bypass with show_all=True: must contain Line 001 through Line 500 and NO banner
    res_all = HTMLDiagnosticService.apply_line_slice(large_lines, ":500", max_chars=20000, show_all=True)
    assert "Line 001" in res_all
    assert "Line 500" in res_all
    assert "[Note:" not in res_all


def test_line_slicing_forward_stream_clamping():
    """Verify Variant 4 (<X>:) and Variant 5 (-<X>:) clamp at character ceiling with truncation notice."""
    # 500 lines of 100 chars
    large_lines = "\n".join([f"Line {i:03d} " + "x" * 90 for i in range(1, 501)])

    # Variant 4: 20: -> streams forward until 20,000 chars, then truncates with warning notice
    res_v4 = HTMLDiagnosticService.apply_line_slice(large_lines, "20:", max_chars=20000, show_all=False)
    assert "Line 020" in res_v4
    assert "... [Truncated: showing first" in res_v4
    assert "Line 500" not in res_v4

    # Variant 5: -250: -> streams last 250 lines (~25,000 chars), clamped at 20,000
    res_v5 = HTMLDiagnosticService.apply_line_slice(large_lines, "-250:", max_chars=20000, show_all=False)
    assert "... [Truncated: showing first" in res_v5

    # Variant 1: Explicit range 20:300 is UNCONSTRAINED despite exceeding 20,000 chars
    res_v1 = HTMLDiagnosticService.apply_line_slice(large_lines, "20:300", max_chars=20000, show_all=False)
    assert "Line 020" in res_v1
    assert "Line 300" in res_v1
    assert "Truncated" not in res_v1


def test_char_slicing_differential_ceiling():
    """Verify Section 3 Differential Ceiling Rules for --chars."""
    # 100,000 characters payload
    large_payload = "A" * 100000

    # Variant 1 (<s>:<e>): UNCONSTRAINED
    s1 = HTMLDiagnosticService.apply_char_slice(large_payload, "0:50000", max_chars=20000)
    assert len(s1) == 50000
    assert "Truncated" not in s1

    # Variant 2 (<X>): UNCONSTRAINED [0, X]
    s2 = HTMLDiagnosticService.apply_char_slice(large_payload, "50000", max_chars=20000)
    assert len(s2) == 50000
    assert "Truncated" not in s2

    # Variant 3 (:<X>): UNCONSTRAINED [0, X]
    s3 = HTMLDiagnosticService.apply_char_slice(large_payload, ":50000", max_chars=20000)
    assert len(s3) == 50000
    assert "Truncated" not in s3

    # Variant 4 (<X>:): CLAMPED BY DEFAULT CEILING (20,000) + truncation notice
    s4 = HTMLDiagnosticService.apply_char_slice(large_payload, "1000:", max_chars=20000, show_all=False)
    assert "... [Truncated: showing first 20,000 of 99,000 characters" in s4
    assert s4.startswith("A" * 20000)

    # Variant 4 with show_all=True: unconstrained
    s4_all = HTMLDiagnosticService.apply_char_slice(large_payload, "1000:", max_chars=20000, show_all=True)
    assert len(s4_all) == 99000
    assert "Truncated" not in s4_all

    # Variant 5 (-<X>:): UNCONSTRAINED (exactly the last X characters)
    s5 = HTMLDiagnosticService.apply_char_slice(large_payload, "-50000:", max_chars=20000)
    assert len(s5) == 50000
    assert "Truncated" not in s5


def test_safety_guard_truncation():
    """Verify character ceiling truncation notice and --all bypass."""
    long_text = "A" * 1000
    guarded = HTMLDiagnosticService.apply_safety_guard(long_text, max_chars=100, show_all=False)
    assert len(guarded.splitlines()[0]) == 100
    assert "Truncated: showing first 100 of 1,000 characters" in guarded

    bypassed = HTMLDiagnosticService.apply_safety_guard(long_text, max_chars=100, show_all=True)
    assert len(bypassed) == 1000
    assert "Truncated" not in bypassed


def test_find_cmd_fail_fast_integration(monkeypatch, capsys):
    """Verify find_cmd fails fast with exit code 1 and error diagnostic on search miss."""
    class DummyClient:
        def execute(self, req):
            class Resp:
                success = True
                message = "OK"
                field_details = {
                    "found": True,
                    "label": "Compensation",
                    "local_id": "@sec-2",
                    "outerHTML": ACCORDION_HTML,
                }
            return Resp()

    import sys
    find_cmd_mod = sys.modules["cli_commands.find_cmd"]
    monkeypatch.setattr(find_cmd_mod, "get_supervisor_client", lambda args: DummyClient())

    args = argparse.Namespace(
        target="@sec-2",
        selector=None,
        standalone=False,
        url=None,
        cookies=None,
        tab=None,
        options=False,
        query=None,
        search="NonExistentTargetSalaryXYZ",
        html=True,
        up=0,
        screenshot=None,
        headed=False,
        timeout_minutes=30,
        strip_header=True,
        json=False,
        include=None,
        exclude=None,
        lines=None,
        chars=None,
        max_chars=20000,
        raw=False,
        all_options=False,
    )

    with pytest.raises(SystemExit) as exc_info:
        find_cmd(args)

    assert exc_info.value.code == 1
    captured = capsys.readouterr()
    err_out = captured.err or captured.out
    assert "Search target 'NonExistentTargetSalaryXYZ' not found within element boundary" in err_out


def test_find_cmd_successful_search_pipeline(monkeypatch, capsys):
    """Verify find_cmd successfully executes the full pipeline and prints pruned outerHTML."""
    class DummyClient:
        def execute(self, req):
            class Resp:
                success = True
                message = "OK"
                field_details = {
                    "found": True,
                    "label": "Compensation",
                    "local_id": "@sec-2",
                    "outerHTML": ACCORDION_HTML,
                }
            return Resp()

    import sys
    find_cmd_mod = sys.modules["cli_commands.find_cmd"]
    monkeypatch.setattr(find_cmd_mod, "get_supervisor_client", lambda args: DummyClient())

    args = argparse.Namespace(
        target="@sec-2",
        selector=None,
        standalone=False,
        url=None,
        cookies=None,
        tab=None,
        options=False,
        query=None,
        search="Current Salary",
        html=True,
        up=0,
        screenshot=None,
        headed=False,
        timeout_minutes=30,
        strip_header=True,
        json=False,
        include=None,
        exclude=None,
        lines="1:15",
        chars=None,
        max_chars=20000,
        raw=False,
        all_options=False,
    )

    find_cmd(args)
    captured = capsys.readouterr()
    assert "Outer HTML" in captured.out
    assert "Current Salary" in captured.out
    assert "Annual Bonus" not in captured.out


def test_sequential_lines_then_chars_pipeline():
    """Verify that --lines sets structural window and --chars acts as subsequent byte-budget trimmer."""
    # 50 lines of 100 characters each
    raw_lines = "\n".join([f"Line {i:02d}: " + "Z" * 90 for i in range(1, 51)])
    sample_html = f"<div>\n{raw_lines}\n</div>"

    # Step 1: Extract lines 10:30 only
    lines_only = HTMLDiagnosticService.process_html_pipeline(
        sample_html,
        lines_slice="10:30",
        pretty=False,
    )
    first_extracted_line = lines_only.splitlines()[0]
    assert len(lines_only) > 1500

    # Step 2: Combined --lines 10:30 --chars :1500
    combined = HTMLDiagnosticService.process_html_pipeline(
        sample_html,
        lines_slice="10:30",
        chars_slice=":1500",
        pretty=False,
    )

    # Must start with first line of extracted block (relative to lines window, NOT un-sliced document start)
    assert combined.startswith(first_extracted_line)
    # Must be exactly 1500 characters
    assert len(combined) == 1500
    # Must equal lines_only trimmed to 1500 characters
    assert combined == lines_only[:1500]


def test_sequential_target_anchored_lines_with_chars_trimmer():
    """Verify target-anchored banner is preserved when --chars trims the lines block."""
    large_lines = "\n".join([f"Line {i:03d}: " + "Y" * 90 for i in range(1, 501)])
    sample_html = f"<div>\n{large_lines}\n</div>"

    combined = HTMLDiagnosticService.process_html_pipeline(
        sample_html,
        lines_slice=":500",
        chars_slice=":500",
        pretty=False,
    )

    lines = combined.splitlines()
    assert lines[0].startswith("[Note: Displaying target-anchored window preceding line 500")
    # Content starts with line from the window
    assert "Line" in lines[1]


# Symmetrical Upper-Tier Pruning Tests

UPPER_TIER_HTML = """
<div id="page-root" class="application-root">
  <header class="main-header">
    <h1 class="header-title">Application Dashboard</h1>
    <svg class="header-icon"><path d="M0 0"/></svg>
    <script>console.log("analytics tracking");</script>
    <button id="help-btn">Help</button>
  </header>
  <div class="sidebar-nav">
    <ul><li>Dashboard</li><li>Settings</li></ul>
  </div>
  <main class="page-body">
    <div class="section-toolbar">
      <h2 class="section-heading">Personal Details</h2>
      <button class="btn-refresh">Refresh</button>
    </div>
    <div class="unrelated-section">
      <p>System status notices</p>
    </div>
    <div class="form-container">
      <div class="field-group form-group" data-field="fld-1">
        <label for="full_name">Full Name</label>
        <input id="full_name" name="name" type="text" />
      </div>
      <div class="field-group form-group" data-field="fld-2">
        <label for="user_email">Email Address</label>
        <input id="user_email" name="email" type="email" />
      </div>
      <div class="field-group form-group" data-field="fld-3">
        <label for="user_phone">Phone Number</label>
        <input id="user_phone" name="phone" type="tel" />
      </div>
    </div>
  </main>
</div>
"""


def test_upper_include_spares_ancestral_uncles():
    """Verify --upper-include spares whitelisted upper-tier elements while other uncles and fields are pruned."""
    # 1. Default: without upper-include, all upper uncles (header, sidebar, toolbar) are pruned
    default_res = HTMLDiagnosticService.process_html_pipeline(
        UPPER_TIER_HTML,
        search_query="Email Address",
        pretty=True,
    )
    assert "Email Address" in default_res
    assert "user_email" in default_res
    assert "main-header" not in default_res
    assert "sidebar-nav" not in default_res
    assert "section-toolbar" not in default_res
    assert "unrelated-section" not in default_res
    assert "Full Name" not in default_res
    assert "Phone Number" not in default_res

    # 2. With --upper-include "header,.section-toolbar", spared elements are retained
    spared_res = HTMLDiagnosticService.process_html_pipeline(
        UPPER_TIER_HTML,
        search_query="Email Address",
        upper_include="header,.section-toolbar",
        pretty=True,
    )
    assert "Email Address" in spared_res
    assert "main-header" in spared_res
    assert "Application Dashboard" in spared_res
    assert "section-toolbar" in spared_res
    assert "Personal Details" in spared_res
    # Un-whitelisted upper uncles and lower siblings must remain pruned
    assert "sidebar-nav" not in spared_res
    assert "unrelated-section" not in spared_res
    assert "Full Name" not in spared_res
    assert "Phone Number" not in spared_res


def test_upper_exclude_prunes_inside_spared_elements():
    """Verify --upper-exclude purges child elements (e.g. svg, script) exclusively inside spared upper elements."""
    res = HTMLDiagnosticService.process_html_pipeline(
        UPPER_TIER_HTML,
        search_query="Email Address",
        upper_include="header",
        upper_exclude="svg,script",
        pretty=True,
    )
    # Header is spared
    assert "main-header" in res
    assert "Application Dashboard" in res
    assert "help-btn" in res

    # Svg and script inside header are purged / stubbed
    assert "analytics tracking" not in res
    assert "M0 0" not in res
    assert "[SVG ICON]" in res
    assert "[SCRIPT]" in res


def test_upper_exclude_graceful_noop():
    """Verify --upper-exclude operates as a graceful no-op if --upper-include is omitted or tags are absent."""
    # When --upper-include is omitted, upper_exclude has nothing to act on and produces no error
    res_no_include = HTMLDiagnosticService.process_html_pipeline(
        UPPER_TIER_HTML,
        search_query="Email Address",
        upper_exclude="svg,script",
        pretty=True,
    )
    assert "Email Address" in res_no_include
    assert "main-header" not in res_no_include

    # When upper_exclude specifies non-existent tags, it is a clean no-op
    res_unmatched = HTMLDiagnosticService.process_html_pipeline(
        UPPER_TIER_HTML,
        search_query="Email Address",
        upper_include="header",
        upper_exclude="video,canvas,.nonexistent-class",
        pretty=True,
    )
    assert "main-header" in res_unmatched
    assert "Application Dashboard" in res_unmatched


def test_upper_and_lower_tier_independence():
    """Verify lower-tier --include and --exclude do NOT prune or corrupt spared upper-tier elements."""
    res = HTMLDiagnosticService.process_html_pipeline(
        UPPER_TIER_HTML,
        search_query="Email Address",
        upper_include="header",
        include_tags="label,input",  # Lower tier whitelist does NOT include 'header', 'h1', or 'button'
        pretty=True,
    )
    # Spared upper tier must NOT be destroyed by lower-tier whitelist
    assert "main-header" in res
    assert "Application Dashboard" in res
    assert "help-btn" in res

    # Lower tier field container only retains whitelisted tags
    assert "user_email" in res
    assert "Email Address" in res


def test_pruned_nodes_indexing_and_placeholders():
    """Verify pruned sibling branches are indexed with @exc-N and replaced by comments."""
    HTMLDiagnosticService.clear_pruned_store()
    res = HTMLDiagnosticService.process_html_pipeline(
        ACCORDION_HTML,
        search_query="Current Salary",
        pretty=True,
    )
    # Target field is retained
    assert "Current Salary" in res
    assert "cur_salary" in res

    # Pruned siblings are replaced with clean comments containing @exc-N IDs
    assert "<!-- [PRUNED: @exc-1" in res
    assert "<!-- [PRUNED: @exc-2" in res

    # Sibling fields are indexed in pruned registry
    node1 = HTMLDiagnosticService.get_pruned_node("@exc-1")
    assert node1 is not None
    assert node1["exc_id"] == "@exc-1"
    assert node1["chars"] > 0
    assert node1["lines"] > 0
    assert "Expected Salary" in node1["raw_html"]


def test_pruned_node_info_query():
    """Verify --info formatting returns concise, structured metadata for @exc-N nodes."""
    HTMLDiagnosticService.clear_pruned_store()
    HTMLDiagnosticService.process_html_pipeline(
        ACCORDION_HTML,
        search_query="Current Salary",
        include_tags="input,label,select",
        pretty=True,
    )

    node = HTMLDiagnosticService.get_pruned_node("@exc-1")
    assert node is not None
    info_text = HTMLDiagnosticService.format_pruned_info(node)

    assert "@exc-1" in info_text
    assert "chars:" in info_text
    assert "lines:" in info_text
    assert "depth:" in info_text
    assert "inner elements:" in info_text
    assert "input" in info_text
    assert "label" in info_text


def test_robust_banner_tuple_isolation():
    """Verify banner tuple isolation ensures --chars does NOT clip or count banner characters."""
    # 500 lines of 100 characters each
    large_lines = "\n".join([f"Line {i:03d}: " + "Z" * 90 for i in range(1, 501)])
    sample_html = f"<div>\n{large_lines}\n</div>"

    # Slicing line :500 anchors target window backwards and generates a banner
    # Chars 0:50 must slice EXACTLY 50 characters of the body, leaving the banner intact
    res = HTMLDiagnosticService.process_html_pipeline(
        sample_html,
        lines_slice=":500",
        chars_slice="0:50",
        pretty=False,
    )

    lines = res.splitlines()
    assert lines[0].startswith("[Note: Displaying target-anchored window preceding line 500")
    # Body starts immediately on line 1 and has exactly 50 characters
    body_part = "\n".join(lines[1:])
    assert len(body_part) == 50


def test_max_chars_negative_rejection_and_zero_bypass():
    """Verify --max-chars 0 bypasses truncation ceiling and negative values are rejected."""
    long_text = "B" * 50000

    # max_chars = 0 -> completely unconstrained (bypasses default 20,000 ceiling)
    unconstrained = HTMLDiagnosticService.apply_safety_guard(long_text, max_chars=0, show_all=False)
    assert len(unconstrained) == 50000
    assert "Truncated" not in unconstrained

    # find_cmd rejects negative --max-chars
    args = argparse.Namespace(
        target="@sec-1",
        selector=None,
        search=None,
        upper_include=None,
        upper_exclude=None,
        max_chars=-100,
        html=True,
    )
    with pytest.raises(SystemExit) as exc_info:
        find_cmd(args)
    assert exc_info.value.code == 1


def test_upper_controls_without_search_notice(capsys):
    """Verify informative notice is output on stderr when --upper-* is passed without --search."""
    HTMLDiagnosticService.clear_pruned_store()
    # Register dummy @exc-1 so find_cmd terminates cleanly without launching Playwright/supervisor
    HTMLDiagnosticService._pruned_registry["@exc-1"] = {
        "exc_id": "@exc-1",
        "tag": "div",
        "dom_id": None,
        "classes": [],
        "selector_desc": "div",
        "raw_html": "<div>Test</div>",
        "chars": 15,
        "lines": 1,
        "depth": 1,
        "element_counts": {},
        "field_types": {},
        "matching_include": 0,
    }

    args = argparse.Namespace(
        target="@exc-1",
        selector=None,
        search=None,
        upper_include="header",
        upper_exclude="svg",
        max_chars=20000,
        html=True,
        raw=False,
        info=True,
        json=False,
        all_options=False,
        options=False,
        query=None,
        include=None,
        exclude=None,
        lines=None,
        chars=None,
        up=0,
        screenshot=None,
    )
    find_cmd(args)
    captured = capsys.readouterr()
    assert "[i] Notice: --upper-* controls require --search/-q to establish an ancestral spine (ignored)." in captured.err


def test_find_cmd_pruned_node_info_and_html(capsys):
    """Verify find_cmd directly serves @exc-N nodes via --info and --html."""
    HTMLDiagnosticService.clear_pruned_store()
    HTMLDiagnosticService._pruned_registry["@exc-1"] = {
        "exc_id": "@exc-1",
        "tag": "div",
        "dom_id": "salary-box",
        "classes": ["form-group", "field-wrapper"],
        "selector_desc": "div.form-group.field-wrapper#salary-box",
        "raw_html": '<div id="salary-box" class="form-group"><label>Bonus</label><input name="bonus" type="number"/></div>',
        "chars": 86,
        "lines": 1,
        "depth": 2,
        "element_counts": {"label": 1, "input": 1},
        "field_types": {"number": 1},
        "matching_include": 1,
    }

    # 1. Inspect metadata via --info
    args_info = argparse.Namespace(
        target="@exc-1",
        selector=None,
        search=None,
        upper_include=None,
        upper_exclude=None,
        max_chars=20000,
        html=False,
        raw=False,
        info=True,
        json=False,
        all_options=False,
        options=False,
        query=None,
        include=None,
        exclude=None,
        lines=None,
        chars=None,
        up=0,
        screenshot=None,
    )
    find_cmd(args_info)
    captured_info = capsys.readouterr()
    assert "WEBPILOT PRUNED NODE METADATA | @exc-1" in captured_info.out
    assert "depth: 2 levels" in captured_info.out
    assert "number: 1" in captured_info.out

    # 2. Retrieve outerHTML via --html
    args_html = argparse.Namespace(
        target="@exc-1",
        selector=None,
        search=None,
        upper_include=None,
        upper_exclude=None,
        max_chars=20000,
        html=True,
        raw=False,
        info=False,
        json=False,
        all_options=False,
        options=False,
        query=None,
        include=None,
        exclude=None,
        lines=None,
        chars=None,
        up=0,
        screenshot=None,
    )
    find_cmd(args_html)
    captured_html = capsys.readouterr()
    assert "Outer HTML:" in captured_html.out
    assert '<input name="bonus" type="number"/>' in captured_html.out

    # 3. Missing @exc-999 exits with error 1
    args_missing = argparse.Namespace(
        target="@exc-999",
        selector=None,
        search=None,
        upper_include=None,
        upper_exclude=None,
        max_chars=20000,
        html=False,
        raw=False,
        info=True,
        json=False,
        all_options=False,
        options=False,
        query=None,
        include=None,
        exclude=None,
        lines=None,
        chars=None,
        up=0,
        screenshot=None,
    )
    with pytest.raises(SystemExit) as exc_err:
        find_cmd(args_missing)
    assert exc_err.value.code == 1


