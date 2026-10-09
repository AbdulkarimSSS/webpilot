"""Timing and delay constants for browser actions and stabilization."""

from typing import Final

# Default timeouts in milliseconds
DEFAULT_NAV_TIMEOUT_MS: Final[int] = 45000
DEFAULT_FORM_READY_TIMEOUT_MS: Final[int] = 10000
DEFAULT_SUBMIT_WAIT_MS: Final[int] = 8000
DEFAULT_EXPAND_SECTION_WAIT_MS: Final[int] = 800

# Granular stabilization pauses in milliseconds
PAUSE_DOM_CONTENT_LOADED_MS: Final[int] = 250
PAUSE_PORTAL_DROPDOWN_CLICK_MS: Final[int] = 300
PAUSE_PORTAL_APPLY_CLICK_MS: Final[int] = 1500
PAUSE_LOGIN_STABILIZATION_MS: Final[int] = 1500
PAUSE_INPUT_SET_MS: Final[int] = 50
PAUSE_RETRY_FALLBACK_MS: Final[int] = 100
PAUSE_PICKLIST_EXPAND_MS: Final[int] = 150
PAUSE_PICKLIST_SCROLL_STEP_MS: Final[int] = 150
PAUSE_PICKLIST_CLOSE_MS: Final[int] = 50
PAUSE_UPLOAD_DIRECT_MS: Final[int] = 500
PAUSE_UPLOAD_CHOOSER_MS: Final[int] = 500
PAUSE_REACTIVE_STABILIZE_MS: Final[int] = 300
PAUSE_MICRO_WAIT_MS: Final[int] = 50
PAUSE_MODAL_DISMISS_MS: Final[int] = 100
