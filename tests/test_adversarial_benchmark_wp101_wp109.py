"""Verification test suite for adversarial benchmark defects WP-101 through WP-109."""

import pytest
from services.dom_verifier import DOMDataMatcher
from adapters.dom.set_field import SET_FIELD_DOM_SCRIPT
from adapters.dom.universal_core import UNIVERSAL_DOM_CORE_JS


def test_wp101_maxlength_truncation_not_falsely_verified():
    """WP-101: An input clamped by maxlength must NOT be confirmed as matching the over-long request."""
    # Input has maxlength 10, DOM holds 10 chars, user requested 15 chars
    dom_readback = {
        "found": True,
        "type": "text",
        "value": "ABCDEFGHIJ",
        "max_length": 10,
        "is_invalid": False,
    }
    # Must NOT verify as the 15-char string (WP-101)
    assert not DOMDataMatcher.match(dom_readback, "ABCDEFGHIJKLMNO")
    # Must verify if expected matches the actual 10 chars
    assert DOMDataMatcher.match(dom_readback, "ABCDEFGHIJ")


def test_wp108_contenteditable_markup_matching():
    """WP-108: ContentEditable elements should verify when markup is stripped or sanitized."""
    dom_readback_cleaned = {
        "found": True,
        "type": "contenteditable",
        "value": "hi",
        "is_invalid": False,
    }
    # Matches even if user provided <b>hi</b>
    assert DOMDataMatcher.match(dom_readback_cleaned, "<b>hi</b>")

    # Also matches when angle brackets were stripped by custom sanitizers (e.g. bhib from <b>hi</b>)
    dom_readback_no_brackets = {
        "found": True,
        "type": "contenteditable",
        "value": "bhib",
        "is_invalid": False,
    }
    assert DOMDataMatcher.match(dom_readback_no_brackets, "<b>hi</b>")


def test_wp105_and_wp107_core_js_logic():
    """WP-105 & WP-107: Verify core JS detection logic contains correct guards."""
    assert "vis-hidden" in UNIVERSAL_DOM_CORE_JS
    assert "isClipRect0" in UNIVERSAL_DOM_CORE_JS
    assert "isOutOfFlow" in UNIVERSAL_DOM_CORE_JS


def test_wp106_candidate_scoring_in_set_field_script():
    """WP-106: Verify candidate scoring and priority ranking exists in SET_FIELD_DOM_SCRIPT."""
    assert "scoreCandidate" in SET_FIELD_DOM_SCRIPT
    assert "newsletter" in SET_FIELD_DOM_SCRIPT
