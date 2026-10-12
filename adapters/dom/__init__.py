"""DOM scripts package providing isolated, browser-evaluated JavaScript routines."""

from adapters.dom.inspection import (
    INSPECT_PAGE_DOM_SCRIPT,
    PROBE_PICKLIST_OPTIONS_SCRIPT,
)
from adapters.dom.lifecycle import (
    CHECK_FORM_LOADING_SCRIPT,
    EXPAND_ALL_SECTIONS_SCRIPT,
)
from adapters.dom.navigation import (
    PORTAL_APPLY_CLICK_SCRIPT,
    PORTAL_DROPDOWN_CLICK_SCRIPT,
)
from adapters.dom.picklist import PICKLIST_AUTO_SCROLL_SCRIPT
from adapters.dom.probe import PROBE_FIELD_DOM_SCRIPT
from adapters.dom.reactive import CLICK_BUTTON_DOM_SCRIPT
from adapters.dom.set_field import SET_FIELD_DOM_SCRIPT
from adapters.dom.verify import VERIFY_FIELD_DOM_SCRIPT

__all__ = [
    "PORTAL_DROPDOWN_CLICK_SCRIPT",
    "PORTAL_APPLY_CLICK_SCRIPT",
    "CHECK_FORM_LOADING_SCRIPT",
    "EXPAND_ALL_SECTIONS_SCRIPT",
    "INSPECT_PAGE_DOM_SCRIPT",
    "PROBE_PICKLIST_OPTIONS_SCRIPT",
    "SET_FIELD_DOM_SCRIPT",
    "PICKLIST_AUTO_SCROLL_SCRIPT",
    "VERIFY_FIELD_DOM_SCRIPT",
    "CLICK_BUTTON_DOM_SCRIPT",
    "PROBE_FIELD_DOM_SCRIPT",
]
