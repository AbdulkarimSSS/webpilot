"""Field value setting and DOM verification service."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple
from playwright.sync_api import Page

from adapters.dom_scripts import (
    PICKLIST_AUTO_SCROLL_SCRIPT,
    PROBE_FIELD_DOM_SCRIPT,
    SET_FIELD_DOM_SCRIPT,
    VERIFY_FIELD_DOM_SCRIPT,
)
from adapters.locator_fallbacks import PlaywrightLocatorFallback
from constants.timeouts import PAUSE_PICKLIST_CLOSE_MS
from services.dom_verifier import DOMDataMatcher
from services.target_descriptor import TargetDescriptorParser


class FieldInteractionService:
    """Sets form field values across standard and complex enterprise widgets and verifies DOM state."""

    def __init__(self, page: Page):
        self.page = page
        self.last_failure_reason: str = "No matching element found"

    def expand_dynamic_section(self, target_identifier: str, value: Any) -> Tuple[bool, Optional[str]]:
        """Handles dynamic repeating sections by finding and clicking 'Add' buttons to spawn missing inputs."""
        add_selectors = [
            '[id$="_addRowBtn"]',
            '[class*="addRowBtn" i]',
            '[class*="add-row" i]',
            '[class*="add_row" i]',
            'button:has-text("Add")',
            'button:has-text("+ Add")',
            'input[type="button"][value*="Add" i]',
            '[role="button"]:has-text("Add")',
            'button[aria-label*="Add" i]',
            'button[title*="Add" i]',
        ]
        orig_url = self.page.url
        for sel in add_selectors:
            try:
                add_btns = self.page.locator(sel)
                count = min(add_btns.count(), 3)
            except Exception:
                count = 0
            for b_idx in range(count):
                btn = add_btns.nth(b_idx)
                try:
                    btn_text = btn.inner_text().strip()
                    btn_id = (btn.get_attribute("id") or "").lower()
                    if "address" in btn_id or "address" in btn_text.lower():
                        continue
                    btn.click(timeout=1000)
                    self.page.wait_for_timeout(300)
                    if self.page.url != orig_url:
                        return False, None
                    if self.set_field(target_identifier, value):
                        return True, btn_text
                except Exception:
                    pass
        return False, None

    @staticmethod
    def parse_target_descriptor(target: str) -> Tuple[Optional[str], str, Optional[str]]:
        """Parses optional type hint prefix and hierarchy scoping from target string."""
        return TargetDescriptorParser.parse(target).to_tuple()

    @staticmethod
    def _escape_css_attr(val: str) -> str:
        """Escapes special characters in CSS attribute selectors."""
        return PlaywrightLocatorFallback.escape_css_attr(val)

    def _playwright_click_fallback(self, target: str, value: Any) -> bool:
        """Fallback setter using Playwright native locators (click / fill)."""
        return PlaywrightLocatorFallback.execute(self.page, target, value)

    def _match_actual_dom_data(self, actual: Any, expected: Any) -> bool:
        """Evaluates whether actual DOM readback matches expected value across control types."""
        return DOMDataMatcher.match(actual, expected)

    def set_field(
        self,
        target_identifier: str,
        value: Any,
        debug_lines: Optional[List[str]] = None,
        **kwargs: Any,
    ) -> bool:
        """Sets field value according to its widget type using JS manipulation or Playwright fallback."""
        type_hint, clean_target, scoped_parent = self.parse_target_descriptor(target_identifier)

        res = self.page.evaluate(SET_FIELD_DOM_SCRIPT, [clean_target, value, type_hint, scoped_parent])
        self.last_failure_reason = res.get("reason") or "No matching element found"
        if debug_lines is not None:
            debug_lines.append(f"    [debug] target='{clean_target}' (hint={type_hint}, scope={scoped_parent}), res={res}")

        # If scoped parent does not exist, fast fail immediately
        if not res.get("success") and res.get("reason") and "Scoped parent" in res.get("reason"):
            self.last_failure_reason = res.get("reason")
            if debug_lines is not None:
                debug_lines.append(f"    [!] Fast-fail: {res.get('reason')}")
            return False

        # Cascading dependent fields readiness check:
        # If element is missing or temporarily disabled/updating via parent reactive onChange/AJAX,
        # poll for up to 1200ms (150ms steps) to allow cascading DOM updates.
        if not res.get("success") and (
            "disabled" in str(res.get("reason")).lower()
            or res.get("reason") in ("No matching element found", "Element disabled or not interactable")
        ):
            for _ in range(8):
                self.page.wait_for_timeout(150)
                retry_res = self.page.evaluate(SET_FIELD_DOM_SCRIPT, [clean_target, value, type_hint, scoped_parent])
                if retry_res.get("success") or (retry_res.get("type") == "picklist" and retry_res.get("trigger_button")):
                    res = retry_res
                    self.last_failure_reason = res.get("reason") or ""
                    if debug_lines is not None:
                        debug_lines.append(f"    [debug] Cascading readiness resolved for '{clean_target}'")
                    break
                elif retry_res.get("reason"):
                    self.last_failure_reason = retry_res.get("reason")

        # If user explicitly requested a dropdown/picklist and element does not exist in DOM -> fast fail
        if type_hint in ("picklist", "select") and res.get("reason") == "No matching element found":
            self.last_failure_reason = f"Dropdown/Picklist '{clean_target}' not found in DOM"
            if debug_lines is not None:
                debug_lines.append(f"    [!] Fast-fail: Dropdown/Picklist '{clean_target}' not found in DOM")
            return False

        # Picklist: trigger button click + scoped auto-scrolling
        if res.get("type") == "picklist":
            inp_id = res.get("id")
            trig_id = res.get("trigger_button")
            # 1. First attempt: click trigger button and scroll/select
            if trig_id:
                try:
                    btn_loc = self.page.locator(f'[id="{trig_id}"]').first
                    is_vis = btn_loc.is_visible(timeout=1500)
                    if debug_lines is not None:
                        debug_lines.append(f"    [debug] trig_id='{trig_id}', is_visible={is_vis}")
                    if is_vis:
                        btn_loc.scroll_into_view_if_needed()
                        btn_loc.click(force=True)
                        self.page.wait_for_timeout(350)

                        pick_res = self.page.evaluate(PICKLIST_AUTO_SCROLL_SCRIPT, [inp_id, value])
                        if debug_lines is not None:
                            debug_lines.append(f"    [debug] pick_res={pick_res}")
                        if pick_res.get("success"):
                            self.page.wait_for_timeout(200)
                            return True
                        else:
                            self.page.keyboard.press("Escape")
                            self.page.wait_for_timeout(PAUSE_PICKLIST_CLOSE_MS)
                except Exception as exc:
                    if debug_lines is not None:
                        debug_lines.append(f"    [debug] Picklist click error: {exc}")

            # 2. Second attempt: type directly into input to trigger autocomplete filter
            if inp_id:
                try:
                    inp_loc = self.page.locator(f'[id="{inp_id}"]').first
                    inp_vis = inp_loc.is_visible(timeout=1500)
                    if debug_lines is not None:
                        debug_lines.append(f"    [debug] inp_id='{inp_id}', is_visible={inp_vis}")
                    if inp_vis:
                        inp_loc.scroll_into_view_if_needed()
                        inp_loc.click(force=True)
                        inp_loc.fill(str(value))
                        self.page.wait_for_timeout(200)
                        self.page.keyboard.press("Enter")
                        self.page.wait_for_timeout(200)

                        if self.verify_field_value(inp_id, value, settle_delay_ms=20):
                            if debug_lines is not None:
                                debug_lines.append(f"    [debug] Verified '{inp_id}' directly after fill & Enter")
                            return True

                        # Check if any matching option appeared in DOM
                        safe_val = self._escape_css_attr(str(value))
                        for opt_sel in [
                            f'[role="option"]:has-text("{safe_val}")',
                            f'[role="menuitem"]:has-text("{safe_val}")',
                            f'.globalMenuItem:has-text("{safe_val}")',
                            f'.picklistOption:has-text("{safe_val}")',
                            f'[class*="selectListOption"]:has-text("{safe_val}")',
                        ]:
                            try:
                                opt = self.page.locator(opt_sel)
                                if opt.count() > 0 and opt.first.is_visible(timeout=500):
                                    opt.first.click(force=True)
                                    self.page.wait_for_timeout(200)
                                    if debug_lines is not None:
                                        debug_lines.append(f"    [debug] Clicked matching option via selector: {opt_sel}")
                                    return True
                            except Exception:
                                pass

                        pick_res = self.page.evaluate(PICKLIST_AUTO_SCROLL_SCRIPT, [inp_id, value])
                        if debug_lines is not None:
                            debug_lines.append(f"    [debug] inp pick_res={pick_res}")
                        if pick_res.get("success"):
                            self.page.wait_for_timeout(200)
                            return True

                        if self.verify_field_value(inp_id, value, settle_delay_ms=20):
                            return True
                except Exception as exc:
                    if debug_lines is not None:
                        debug_lines.append(f"    [debug] Picklist input type error: {exc}")

            # Picklist failed after thorough probe -> fast fail, do not attempt unrelated click fallback
            self.last_failure_reason = f"Option '{value}' not found in picklist '{clean_target}'"
            if debug_lines is not None:
                debug_lines.append(f"    [!] Fast-fail: {self.last_failure_reason}")
            return False

        # Non-picklist JS success: verify whether the DOM actually accepted the value.
        # If an input has an isTrusted check or synthetic event rejection,
        # the JS write will be immediately wiped, so we fall through to Playwright native interaction.
        if res.get("success") and res.get("type") not in ("picklist",):
            if self.verify_field_value(clean_target, value, settle_delay_ms=20):
                self.last_failure_reason = ""
                return True

        # Fallback to Playwright native interaction
        fallback_res = self._playwright_click_fallback(clean_target, value)
        if fallback_res:
            self.last_failure_reason = ""
        return fallback_res

    def verify_field_value(self, target: str, expected: Any, settle_delay_ms: int = 50) -> bool:
        """Reads back current DOM value and confirms state, allowing framework settle window."""
        expected_str = str(expected).strip().lower() if expected is not None else ""
        try:
            actual = self.page.evaluate(VERIFY_FIELD_DOM_SCRIPT, [target, expected_str])
            if actual and actual.get("found"):
                if self._match_actual_dom_data(actual, expected):
                    return True

            # Shadow DOM fallback: check Playwright locator which pierces open Shadow DOM
            try:
                safe_t = self._escape_css_attr(target)
                for shadow_sel in [f'#{safe_t}', f'input[name="{safe_t}"]', f'textarea[name="{safe_t}"]']:
                    loc = self.page.locator(shadow_sel)
                    if loc.count() > 0:
                        v = loc.first.input_value()
                        if self._match_actual_dom_data(v, expected):
                            return True
            except Exception:
                pass

            # If first read was negative, allow a brief settle pause for async frameworks (React/Vue/Angular)
            if settle_delay_ms > 0:
                self.page.wait_for_timeout(settle_delay_ms)
                retry_actual = self.page.evaluate(VERIFY_FIELD_DOM_SCRIPT, [target, expected_str])
                if retry_actual and retry_actual.get("found"):
                    return self._match_actual_dom_data(retry_actual, expected)
            return False
        except Exception:
            return False

    def probe_field(
        self,
        target: str,
        include_options: bool = True,
        query: Optional[str] = None,
        include_html: bool = False,
    ) -> Optional[Dict[str, Any]]:
        """Probes a specific form field or picklist and retrieves deep diagnostic metadata."""
        try:
            return self.page.evaluate(
                PROBE_FIELD_DOM_SCRIPT,
                [target, include_options, query or "", include_html],
            )
        except Exception:
            return None
