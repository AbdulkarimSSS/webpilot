"""Form schema inspection service."""

from __future__ import annotations

from typing import Any, Dict
from playwright.sync_api import Page
from adapters.dom_scripts import INSPECT_PAGE_DOM_SCRIPT, PROBE_PICKLIST_OPTIONS_SCRIPT

class InspectionService:
    """Inspects webpage DOM and produces structured form schema."""

    def __init__(self, page: Page):
        self.page = page

    def inspect(self, unpack_options: bool = True, pua_mode: Optional[str] = None) -> Dict[str, Any]:
        """Deep inspection of the active page. Extracts form components, inputs, buttons, and uploads."""
        try:
            from config.settings import get_settings
            effective_pua_mode = pua_mode or get_settings().pua_mode
        except Exception:
            effective_pua_mode = pua_mode or "escape"

        dom_args = {"puaMode": effective_pua_mode}
        try:
            raw = self.page.evaluate(INSPECT_PAGE_DOM_SCRIPT, dom_args)
        except Exception as exc:
            err_str = str(exc).lower()
            if "execution context was destroyed" in err_str or "navigation" in err_str:
                try:
                    self.page.wait_for_load_state("domcontentloaded", timeout=4000)
                    raw = self.page.evaluate(INSPECT_PAGE_DOM_SCRIPT, dom_args)
                except Exception:
                    raw = {
                        "title": self.page.title() if self.page else "",
                        "url": self.page.url if self.page else "",
                        "buttons": [], "dropdowns": [], "inputs": [], "choices": [],
                        "file_uploads": [], "sections": [], "already_uploaded_files": []
                    }
            else:
                raw = {
                    "title": self.page.title() if self.page else "",
                    "url": self.page.url if self.page else "",
                    "buttons": [], "dropdowns": [], "inputs": [], "choices": [],
                    "file_uploads": [], "sections": [], "already_uploaded_files": []
                }

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
