"""Regression tests for the WebPilot `find --html` pipeline (found while testing v2.6.5).

Run against the installed package:
    pytest test_html_diagnostics_v265.py -v

Run against a specific file (e.g. the original vs the fixed one):
    WP_SERVICE_FILE=/path/to/html_diagnostic_service.py pytest test_html_diagnostics_v265.py -v
"""

from __future__ import annotations

import importlib.util
import os
import re
import subprocess
import sys
import textwrap

import pytest
from bs4 import BeautifulSoup

SERVICE_FILE = os.environ.get("WP_SERVICE_FILE")

SF_HTML = """
<div class="rcmFormSection row" data-wp-id="@sec-2" id="170:section">
<h2 class="sectionTitle rcmFormSectionTitle" data-wp-id="@sec-2" id="170:headerLabel"><svg class="i"><path d="M0"/></svg>Personal Info</h2>
<div class="sectionContent rcmFormSectionContent" id="170:sectionContent" role="group">
<div class="layoutWrapper row rcmSectionComponent"><div class="leftColumn col-xs-12"><div class="row">
<div class="col-md-4"><div class="RCMFormField rcmFormElement">
<label class="rcmFormFieldLabel" for="57:_input" id="61:"><span aria-hidden="true" class="requiredField">*</span>Salutation</label>
<div class="fieldComponentInput" id="60:_fieldComponentInput"><span class="sfCascadingPicklist" id="56:"><div class="paginatedPicklistContainer"><div class="sr-only"><div role="status">One or more results available.</div></div><input aria-label="Salutation" data-wp-id="@drop-3" id="57:_input" role="combobox" type="text" value="Mr."/></div></span></div>
</div></div>
<div class="clearfix visible-xs"></div>
<div class="col-md-4"><div class="RCMFormField rcmFormElement">
<label class="rcmFormFieldLabel" for="63:_txtFld" id="65:">First Name</label>
<div class="fieldComponentInput" id="64:_fieldComponentInput"><div class="sfTextFieldCss" id="63:"><input data-wp-id="@fld-1" id="63:_txtFld" name="firstName" type="text" value="Abdulkarim"/></div></div>
</div></div>
<div class="clearfix visible-xs"></div>
<div class="col-md-4"><div class="RCMFormField rcmFormElement">
<label class="rcmFormFieldLabel" for="162:_txtFld" id="164:">Current Total Package Salary</label>
<div class="fieldComponentInput" id="163:_fieldComponentInput"><div class="sfTextFieldCss" id="162:"><input data-wp-id="@fld-13" id="162:_txtFld" name="custCurrentBasicSalary" type="text" value="7,000.00"/></div><div class="rcmValidationMsgArea displayNone" id="165:" role="alert"></div></div>
</div></div>
<div class="col-md-4"><div class="RCMFormField rcmFormElement">
<label class="rcmFormFieldLabel" for="170:_txtFld" id="171:">Notice Period</label>
<div class="fieldComponentInput"><div class="sfTextFieldCss"><input data-wp-id="@fld-14" name="notice" type="text" value="30"/></div></div>
</div></div>
</div></div></div></div></div>
"""


def _load_module():
    if SERVICE_FILE:
        spec = importlib.util.spec_from_file_location("wp_service_under_test", SERVICE_FILE)
        mod = importlib.util.module_from_spec(spec)
        sys.modules["wp_service_under_test"] = mod
        spec.loader.exec_module(mod)
        return mod
    import services.html_diagnostic_service as mod  # type: ignore
    return mod


@pytest.fixture()
def mod(tmp_path, monkeypatch):
    m = _load_module()
    S = m.HTMLDiagnosticService
    monkeypatch.setattr(S, "PRUNED_STORE_DIR", str(tmp_path))
    monkeypatch.setattr(S, "PRUNED_STORE_FILE", str(tmp_path / "pruned_nodes.json"))
    S.clear_pruned_store()
    yield m
    S.clear_pruned_store()


@pytest.fixture()
def S(mod):
    return mod.HTMLDiagnosticService


def run(S, html=SF_HTML, **kw):
    return S.process_html_pipeline(html, **kw)


_COMMENT = re.compile(r"<!--(.*?)-->", re.S)
_STUB = re.compile(r"\[(?:PRUNED|EXCLUDED): (@exc-\d+)(?:\.\.(@exc-\d+))?")


def stub_comments(out):
    """One entry per stub COMMENT (a collapsed range, or a comment with nested [EXCLUDED: ..] info, counts once)."""
    return [c for c in _COMMENT.findall(out) if _STUB.search(c)]


def stubs(out):
    """Every @exc ID referenced by the output; ranges like @exc-1..@exc-4 are expanded."""
    ids = []
    for c in stub_comments(out):
        m = _STUB.search(c)
        lo = int(m.group(1).split("-")[1])
        hi = int(m.group(2).split("-")[1]) if m.group(2) else lo
        ids.extend(f"@exc-{i}" for i in range(lo, hi + 1))
    return ids


# ---------------------------------------------------------------- 1. field container

@pytest.mark.parametrize("query", ["Salary", "custCurrentBasicSalary"])
def test_field_container_is_the_whole_form_field(S, query):
    """Container must be div.RCMFormField, not the <label> nor the small input wrapper."""
    root = BeautifulSoup(SF_HTML, "html.parser").find()
    leaf = S._find_matching_leaf(root, query)
    container = S._identify_field_container(leaf, root)
    assert "RCMFormField" in (container.get("class") or [])


@pytest.mark.parametrize(
    "kw",
    [
        {},
        {"include_tags": "div,label,input"},
        {"exclude_tags": "span"},
        {"include_tags": "div,label,input", "exclude_tags": "span"},
    ],
    ids=["search-only", "include", "exclude-span", "include+exclude"],
)
def test_search_keeps_target_input_and_label(S, kw):
    out = run(S, search_query="Salary", **kw)
    assert 'data-wp-id="@fld-13"' in out, "the searched field's input was pruned away"
    assert "Current Total Package Salary" in out


def test_search_does_not_leak_sibling_fields(S):
    out = run(S, search_query="Salary")
    assert "firstName" not in out and "Notice Period" not in out


# ---------------------------------------------------------------- 2. exclude is never silent

def test_exclude_leaves_stub_and_registers_node(S):
    out = run(S, exclude_tags="span")
    ids = stubs(out)
    assert ids, "exclude removed nodes without leaving any stub"
    assert 'data-wp-id="@drop-3"' not in out
    recovered = "".join(S.get_pruned_node(i)["raw_html"] for i in ids)
    assert 'data-wp-id="@drop-3"' in recovered, "the removed input must be retrievable by ID"


def test_exclude_nested_matches_produce_a_single_top_level_stub(S):
    html = '<form id="r"><div class="a"><div class="a"><input name="x"/></div></div></form>'
    out = run(S, html=html, exclude_tags="div")
    assert len(stub_comments(out)) == 1
    assert len(S._pruned_registry) == 1, "nested nodes inside a removed subtree must not be registered"


def test_exclude_beats_include_on_same_tag(S):
    html = '<form id="r"><div class="g"><input name="x"/></div></form>'
    out = run(S, html=html, include_tags="div,input", exclude_tags="div")
    assert "<input" not in out
    assert len(stub_comments(out)) == 1


def test_exclude_of_text_only_node_is_not_silent(S):
    """The '*' required-field marker lives in a text-only <span>: removing it must leave a stub."""
    out = run(S, exclude_tags="span")
    marker = [i for i in stubs(out) if "requiredField" in S.get_pruned_node(i)["raw_html"]]
    assert marker, "text-only excluded <span class=requiredField> vanished without a stub"


def test_repeated_query_does_not_grow_registry(S):
    run(S, search_query="Salary")
    n = len(S._pruned_registry)
    run(S, search_query="Salary")
    assert len(S._pruned_registry) == n


def test_noisy_tags_keep_inline_stub(S):
    out = run(S, exclude_tags="svg")
    assert "[SVG ICON]" in out and "<path" not in out


# ---------------------------------------------------------------- 3. stable @exc IDs

def test_same_node_gets_same_id_when_pruned_twice(S):
    first = stubs(run(S, search_query="Salary"))
    second = stubs(run(S, search_query="Salary"))
    assert first == second


_CHILD = textwrap.dedent(
    """
    import importlib.util, sys, json
    spec = importlib.util.spec_from_file_location("m", {path!r})
    m = importlib.util.module_from_spec(spec); sys.modules["m"] = m; spec.loader.exec_module(m)
    S = m.HTMLDiagnosticService
    html = open({html!r}, encoding="utf-8").read()
    mode = sys.argv[1]
    if mode == "run":
        out = S.process_html_pipeline(html, search_query=sys.argv[2])
        import re
        ids = []
        for a, b in re.findall(r"\\[(?:PRUNED|EXCLUDED): (@exc-\\d+)(?:\\.\\.(@exc-\\d+))?", out):
            lo = int(a.split("-")[1]); hi = int(b.split("-")[1]) if b else lo
            ids += [f"@exc-{{i}}" for i in range(lo, hi + 1)]
        print(json.dumps({{i: S.get_pruned_node(i)["raw_html"] for i in ids}}))
    else:
        n = S.get_pruned_node(sys.argv[2])
        print(json.dumps(n["raw_html"] if n else None))
    """
)


def _service_path():
    return SERVICE_FILE or sys.modules[_load_module().__name__].__file__


def test_ids_stay_valid_across_processes(tmp_path):
    html_file = tmp_path / "page.html"
    html_file.write_text(SF_HTML, encoding="utf-8")
    script = tmp_path / "child.py"
    script.write_text(_CHILD.format(path=_service_path(), html=str(html_file)), encoding="utf-8")
    env = {**os.environ, "HOME": str(tmp_path)}

    def call(*args):
        r = subprocess.run([sys.executable, str(script), *args], env=env, capture_output=True, text=True)
        assert r.returncode == 0, r.stderr
        import json
        return json.loads(r.stdout.strip().splitlines()[-1])

    before = call("run", "Salary")                 # process 1: IDs handed to the "agent"
    call("run", "First Name")                      # process 2: a different query
    for exc_id, html in before.items():            # process 3: the agent uses an old ID
        assert call("get", exc_id) == html, f"{exc_id} now points at different content"


# ---------------------------------------------------------------- 4. upper tier

def test_upper_include_h2_spares_the_title(S):
    out = run(S, search_query="First Name", upper_include="h2")
    assert "Personal Info" in out


@pytest.mark.parametrize("token", ["label", "input"])
def test_upper_include_does_not_spare_uncles_that_merely_contain_the_tag(S, token):
    out = run(S, search_query="First Name", upper_include=token)
    for other in ("Salutation", "Salary", "Notice Period"):
        assert other not in out, f"--upper-include {token} leaked {other!r}"


def test_upper_exclude_cleans_inside_spared_element(S):
    out = run(S, search_query="First Name", upper_include="h2", upper_exclude="svg")
    assert "[SVG ICON]" in out and "<path" not in out


# ---------------------------------------------------------------- 5. slicing and limits

def _big(S, **kw):
    html = "<root>" + "".join(f"<p>{'x' * 60}</p>" for _ in range(800)) + "</root>"
    return S.process_html_pipeline(html, **kw)


def test_banner_is_isolated_from_chars_slice(S):
    out = _big(S, lines_slice="2000", chars_slice="0:50")
    banner, body = out.split("\n", 1)
    assert banner.startswith("[Note:") and "target-anchored" in banner
    assert len(body) == 50


def test_no_banner_for_explicit_range(S):
    out = _big(S, lines_slice="5:15", chars_slice="0:30")
    assert not out.startswith("[Note") and len(out) == 30


def test_all_beats_max_chars(S):
    out = _big(S, lines_slice="2000", show_all=True, max_chars=100)
    assert len(out.splitlines()) == 2000


def test_max_chars_zero_disables_ceiling(S):
    assert "Truncated" not in _big(S, max_chars=0)


def test_default_ceiling_truncates(S):
    assert "Truncated" in _big(S)


def test_negative_max_chars_is_rejected(mod, S):
    with pytest.raises(mod.DiagnosticInputError):
        _big(S, max_chars=-5)


def test_invalid_regex_is_a_clean_error(mod, S):
    with pytest.raises(mod.DiagnosticInputError):
        run(S, search_query="re:(")


@pytest.mark.parametrize("kw", [{"lines_slice": "abc"}, {"chars_slice": "x:y"}])
def test_invalid_slice_is_rejected(mod, S, kw):
    with pytest.raises(mod.DiagnosticInputError):
        _big(S, **kw)


def test_search_not_found_raises(mod, S):
    with pytest.raises(mod.DiagnosticSearchNotFoundError):
        run(S, search_query="zzz-nope")
    with pytest.raises(mod.DiagnosticSearchNotFoundError):
        run(S, search_query="راتب")


def test_collapsed_range_exposes_every_pruned_id(S):
    """A collapsed stub must let the agent reach EVERY node it swallowed (ranges break when IDs are shared/non-contiguous)."""
    out = run(S, search_query="Salary")
    exposed = set(stubs(out))
    swallowed = {k for k, m in S._pruned_registry.items() if 'data-wp-id="@fld-1"' in m["raw_html"]}
    assert swallowed, "fixture sanity: First Name field should have been pruned"
    assert swallowed <= exposed, f"{swallowed - exposed} pruned but unreachable from the stub text"
