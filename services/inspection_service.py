"""Form schema inspection service."""

from __future__ import annotations

from typing import Any, Dict
from playwright.sync_api import Page
from adapters.dom_scripts import INSPECT_PAGE_DOM_SCRIPT, PROBE_PICKLIST_OPTIONS_SCRIPT

class InspectionService:
    """Inspects webpage DOM and produces structured form schema."""

    def __init__(self, page: Page):
        self.page = page

    def inspect(self, unpack_options: bool = True, pua_mode: Optional[str] = None, auto_expand: bool = True) -> Dict[str, Any]:
        """Deep inspection of the active page. Extracts form components, inputs, buttons, and uploads."""
        if auto_expand:
            try:
                from services.page_lifecycle_service import PageLifecycleService
                PageLifecycleService(self.page).expand_all_sections()
            except Exception:
                pass

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

        # Traversal across child iframes (WP-006)
        if hasattr(self.page, "frames") and len(self.page.frames) > 1:
            for frame in self.page.frames[1:]:
                try:
                    frame_raw = frame.evaluate(INSPECT_PAGE_DOM_SCRIPT, dom_args)
                    if frame_raw:
                        for key in ("inputs", "buttons", "dropdowns", "choices", "file_uploads"):
                            if frame_raw.get(key):
                                raw.setdefault(key, []).extend(frame_raw[key])
                except Exception:
                    pass

        # Piercing closed shadow roots via Chrome DevTools Protocol (WP-007)
        try:
            cdp = self.page.context.new_cdp_session(self.page)
            doc = cdp.send("DOM.getDocument", {"depth": -1, "pierce": True})
            existing_ids = {str(inp.get("id")) for inp in raw.get("inputs", []) if inp.get("id")}
            existing_names = {str(inp.get("name")) for inp in raw.get("inputs", []) if inp.get("name")}

            def _extract_inputs_from_shadow(node):
                node_name = node.get("nodeName", "").lower()
                if node_name in ("input", "select", "textarea"):
                    attrs = node.get("attributes", [])
                    attr_dict = dict(zip(attrs[0::2], attrs[1::2]))
                    nid = attr_dict.get("id", "")
                    nname = attr_dict.get("name", "")
                    if (nid and nid not in existing_ids) or (nname and nname not in existing_names):
                        ntype = attr_dict.get("type", "text")
                        raw.setdefault("inputs", []).append({
                            "tag": node_name,
                            "id": nid,
                            "name": nname,
                            "type": ntype,
                            "value": attr_dict.get("value", ""),
                            "label": attr_dict.get("aria-label", "") or nname or nid,
                            "local_id": f"input_{len(raw.get('inputs', [])) + 1}",
                        })
                        if nid:
                            existing_ids.add(nid)
                        if nname:
                            existing_names.add(nname)
                for child in node.get("children", []):
                    _extract_inputs_from_shadow(child)

            def _find_shadow_roots(node):
                for sroot in node.get("shadowRoots", []):
                    _extract_inputs_from_shadow(sroot)
                for child in node.get("children", []):
                    _find_shadow_roots(child)

            _find_shadow_roots(doc.get("root", {}))
            cdp.detach()
        except Exception:
            pass

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
                            owns_id = dd.get("owns_id") or f"{base_id}:_listSelect"
                            opts = self.page.evaluate(PROBE_PICKLIST_OPTIONS_SCRIPT, owns_id)
                            if opts:
                                dd["options_count"] = len(opts)
                                dd["sample_options"] = opts[:5]
                            self.page.keyboard.press("Escape")
                            self.page.wait_for_timeout(100)
                    except Exception:
                        pass

        return raw
