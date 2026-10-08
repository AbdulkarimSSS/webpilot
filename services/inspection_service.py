"""Form schema inspection service."""

from __future__ import annotations

from typing import Any, Dict
from playwright.sync_api import Page
from adapters.dom_scripts import INSPECT_PAGE_DOM_SCRIPT, PROBE_PICKLIST_OPTIONS_SCRIPT

class InspectionService:
    """Inspects webpage DOM and produces structured form schema."""

    def __init__(self, page: Page):
        self.page = page

    def inspect(self, unpack_options: bool = True) -> Dict[str, Any]:
        """Deep inspection of the active page. Extracts form components, inputs, buttons, and uploads."""
        raw = self.page.evaluate(INSPECT_PAGE_DOM_SCRIPT)

        if unpack_options:
            print("[*] Probing picklist samples (unpack_options=True)...")
            for dd in raw.get("dropdowns", []):
                btn_id = dd.get("trigger_id")
                if btn_id and self.page.locator(f'[id="{btn_id}"]').count() > 0:
                    try:
                        btn_loc = self.page.locator(f'[id="{btn_id}"]').first
                        if btn_loc.is_visible():
                            btn_loc.click(force=True)
                            self.page.wait_for_timeout(300)
                            base_id = dd["id"].replace(":_input", "")
                            owns_id = f"{base_id}:_listSelect"
                            opts = self.page.evaluate(PROBE_PICKLIST_OPTIONS_SCRIPT, owns_id)
                            if opts:
                                dd["options_count"] = len(opts)
                                dd["sample_options"] = opts[:5]
                            self.page.keyboard.press("Escape")
                            self.page.wait_for_timeout(100)
                    except Exception:
                        pass

        return raw
