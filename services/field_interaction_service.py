"""Field value setting and DOM verification service."""

from __future__ import annotations

import re
from typing import Any
from playwright.sync_api import Page

from adapters.dom_scripts import (
    SET_FIELD_DOM_SCRIPT,
    PICKLIST_AUTO_SCROLL_SCRIPT,
    VERIFY_FIELD_DOM_SCRIPT,
)
from constants.timeouts import (
    PAUSE_INPUT_SET_MS,
    PAUSE_RETRY_FALLBACK_MS,
    PAUSE_PICKLIST_EXPAND_MS,
    PAUSE_PICKLIST_CLOSE_MS,
)


class FieldInteractionService:
    """Sets form field values across standard and complex enterprise widgets and verifies DOM state."""

    def __init__(self, page: Page):
        self.page = page

    def set_field(self, target_identifier: str, value: Any) -> bool:
        """Sets field value according to its widget type using JS manipulation or Playwright fallback."""
        res = self.page.evaluate(SET_FIELD_DOM_SCRIPT, [target_identifier, value])

        # Picklist: trigger button click + scoped auto-scrolling
        if res.get("type") == "picklist" and res.get("trigger_button"):
            try:
                btn_loc = self.page.locator(f'[id="{res["trigger_button"]}"]').first
                if btn_loc.is_visible(timeout=1500):
                    btn_loc.scroll_into_view_if_needed()
                    btn_loc.click(force=True)
                    self.page.wait_for_timeout(PAUSE_PICKLIST_EXPAND_MS)

                    pick_res = self.page.evaluate(PICKLIST_AUTO_SCROLL_SCRIPT, [res["id"], value])

                    if pick_res.get("success"):
                        self.page.wait_for_timeout(300)
                        return True
                    else:
                        self.page.keyboard.press("Escape")
                        self.page.wait_for_timeout(PAUSE_PICKLIST_CLOSE_MS)
            except Exception as exc:
                print(f"    [!] Picklist click error: {exc}")

        # Non-picklist JS success: verify whether the DOM actually accepted the value.
        # If an input has an isTrusted check or synthetic event rejection (e.g. S33),
        # the JS write will be immediately wiped, so we fall through to Playwright native interaction.
        if res.get("success") and res.get("type") not in ("picklist",):
            if self.verify_field_value(target_identifier, value, settle_delay_ms=20):
                return True

        # Fallback to Playwright native interaction
        return self._playwright_click_fallback(target_identifier, value)

    @staticmethod
    def _escape_css_attr(val: str) -> str:
        """Escapes special characters in CSS attribute selectors."""
        return str(val).replace("\\", "\\\\").replace('"', '\\"')

    def _playwright_click_fallback(self, target: str, value: Any) -> bool:
        """Fallback setter using Playwright native locators (click / fill)."""
        page = self.page
        strval = str(value)
        lower = target.lower().strip()
        safe_target = self._escape_css_attr(target)
        safe_strval = self._escape_css_attr(strval)

        # 0a. Native <select> (single or multi-select)
        try:
            for sel_css in [f'select#{safe_target}', f'select[name="{safe_target}"]']:
                s_loc = page.locator(sel_css)
                if s_loc.count() > 0 and s_loc.first.is_visible(timeout=300):
                    if s_loc.first.get_attribute("multiple") is not None:
                        parts = [x.strip() for x in strval.split(",") if x.strip()]
                        s_loc.first.select_option(parts)
                        return True
                    else:
                        s_loc.first.select_option(strval)
                        return True
        except Exception:
            pass

        # 0b. Checkbox group with comma-separated values (e.g. "AI,Security")
        if "," in strval:
            parts = [x.strip() for x in strval.split(",") if x.strip()]
            checked_any = False
            for p in parts:
                p_safe = self._escape_css_attr(p)
                for cb_sel in [
                    f'input[name="{safe_target}"][value="{p_safe}"]',
                    f'input[type="checkbox"][name="{safe_target}"][value="{p_safe}"]',
                    f'input[type="checkbox"][value="{p_safe}"]',
                ]:
                    try:
                        cb = page.locator(cb_sel)
                        if cb.count() > 0:
                            cb.first.check()
                            checked_any = True
                            break
                    except Exception:
                        pass
            if checked_any:
                return True

        # 0c. Direct element ID or Name locator with Playwright (pierces Shadow DOM)
        for sel in [f'#{safe_target}', f'input[name="{safe_target}"]', f'textarea[name="{safe_target}"]']:
            try:
                loc = page.locator(sel)
                if loc.count() > 0 and loc.first.is_visible(timeout=300):
                    loc.first.focus()
                    loc.first.fill(strval)
                    loc.first.dispatch_event("input")
                    loc.first.dispatch_event("change")
                    return True
            except Exception:
                pass

        # 1. Picklist combobox by aria-label, title, id, name, or placeholder
        for loc in [
            page.locator(f'input[aria-label*="{safe_target}"][role="combobox"]'),
            page.locator(f'input[title*="{safe_target}"][role="combobox"]'),
            page.locator(f'input[id*="{safe_target}"][role="combobox"]'),
            page.locator(f'input[name*="{safe_target}"][role="combobox"]'),
            page.locator(f'input#{safe_target}[role="combobox"]'),
            page.locator(f'#{safe_target}-input[role="combobox"]'),
        ]:
            try:
                if loc.count() > 0 and loc.first.is_visible(timeout=300):
                    loc.first.click()
                    loc.first.fill(strval)
                    page.wait_for_timeout(300)
                    for role_name in ["option", "menuitem", "listitem"]:
                        opt = page.locator(f'[role="{role_name}"]:has-text("{safe_strval}")')
                        if opt.count() > 0:
                            opt.first.click()
                            page.wait_for_timeout(PAUSE_RETRY_FALLBACK_MS)
                            return True
                    page.keyboard.press("Escape")
            except Exception:
                pass

        # 2. Native radio scoped to target radio group
        try:
            scoped_radio = page.locator(f'input[type="radio"][name="{safe_target}"][value="{safe_strval}"]').first
            if scoped_radio.count() > 0:
                scoped_radio.click()
                return True
        except Exception:
            pass

        # 3. Custom ARIA radioLabel spans (SuccessFactors)
        for selector in [
            f'.radioLabel:text-is("{safe_strval}")',
            f'.radioLabel:has-text("{safe_strval}")',
        ]:
            try:
                spans = page.locator(selector)
                if spans.count() > 0:
                    spans.first.click()
                    return True
            except Exception:
                pass

        # 4. Text / Textarea via label (strictly avoid clicking checkboxes or switches)
        try:
            field = page.get_by_label(lower, exact=False)
            if field.count() > 0 and field.first.is_visible(timeout=300):
                field_type = (field.first.get_attribute("type") or "").lower()
                field_role = (field.first.get_attribute("role") or "").lower()
                if field_type not in ("checkbox", "radio") and field_role not in ("checkbox", "switch"):
                    field.first.fill(strval)
                    field.first.dispatch_event("input")
                    field.first.dispatch_event("change")
                    # If this input is a combobox, select the option that appeared
                    if field_role == "combobox":
                        page.wait_for_timeout(200)
                        for role_name in ["option", "menuitem", "listitem"]:
                            opt = page.locator(f'[role="{role_name}"]:has-text("{safe_strval}")')
                            if opt.count() > 0:
                                opt.first.click()
                                page.wait_for_timeout(PAUSE_RETRY_FALLBACK_MS)
                                break
                    return True
        except Exception:
            pass

        # 5. Text via placeholder
        try:
            field = page.get_by_placeholder(lower, exact=False)
            if field.count() > 0 and field.first.is_visible(timeout=300):
                field.first.fill(strval)
                field.first.dispatch_event("change")
                return True
        except Exception:
            pass

        # 6. Username / Email generic heuristic
        if lower in ("username", "user", "email", "login", "user name", "email address"):
            for sel in [
                'input[type="email"]',
                'input[name*="user" i]',
                'input[id*="user" i]',
                'input[name*="email" i]',
                'input[id*="email" i]',
                'input[autocomplete="username"]',
                'input[autocomplete="email"]',
            ]:
                try:
                    f = page.locator(sel)
                    if f.count() > 0 and f.first.is_visible(timeout=300):
                        f.first.fill(strval)
                        f.first.dispatch_event("input")
                        f.first.dispatch_event("change")
                        return True
                except Exception:
                    pass

        # 7. Password generic heuristic
        if lower in ("password", "pass", "pwd", "user password"):
            try:
                f = page.locator('input[type="password"]')
                if f.count() > 0 and f.first.is_visible(timeout=300):
                    f.first.fill(strval)
                    f.first.dispatch_event("input")
                    f.first.dispatch_event("change")
                    return True
            except Exception:
                pass

        return False

    def _match_actual_dom_data(self, actual: Any, expected: Any) -> bool:
        """Evaluates whether actual DOM readback matches expected value across control types."""
        if actual is None:
            return False

        expected_str = str(expected).strip().lower() if expected is not None else ""
        junk = {"login/ view profile", "no selection", "select", "choose", "-- select --", ""}

        if isinstance(actual, dict):
            ctype = actual.get("type", "")

            # Checkbox / Toggle switch
            if ctype == "checkbox":
                is_checked = bool(actual.get("checked", False))
                if isinstance(expected, bool):
                    return is_checked is expected
                if expected_str in ("true", "yes", "1", "checked", "on"):
                    return is_checked is True
                if expected_str in ("false", "no", "0", "unchecked", "off"):
                    return is_checked is False
                return is_checked is True

            # Radio button
            if ctype == "radio":
                is_checked = bool(actual.get("checked", False))
                val = str(actual.get("value", "")).strip().lower()
                if is_checked:
                    if not expected_str or expected_str in ("true", "checked", "yes", "1"):
                        return True
                    return expected_str == val or expected_str in val or val in expected_str
                return False

            # Radio group
            if ctype == "radio_group":
                val = str(actual.get("value", "")).strip().lower()
                if not val or val in junk:
                    return False
                return expected_str in val or val in expected_str

            # Checkbox group (multiple checkboxes)
            if ctype == "checkbox_group":
                val = str(actual.get("value", "")).strip().lower()
                if not val:
                    return False
                if "," in expected_str or "," in val:
                    exp_parts = set(x.strip() for x in expected_str.split(",") if x.strip())
                    val_parts = set(x.strip() for x in val.split(",") if x.strip())
                    return exp_parts == val_parts or exp_parts.issubset(val_parts)
                return expected_str == val or expected_str in val

            # Native <select>
            if ctype == "select":
                val = str(actual.get("value", "")).strip().lower()
                text = str(actual.get("text", "")).strip().lower()
                if not val and not text:
                    return False
                if val in junk and text in junk:
                    return False
                # Comma-separated multi-select comparison
                if "," in expected_str or "," in val or "," in text:
                    exp_parts = set(x.strip() for x in expected_str.split(",") if x.strip())
                    val_parts = set(x.strip() for x in val.split(",") if x.strip())
                    text_parts = set(x.strip() for x in text.split(",") if x.strip())
                    if exp_parts and (exp_parts == val_parts or exp_parts == text_parts or exp_parts.issubset(val_parts) or exp_parts.issubset(text_parts)):
                        return True
                if expected_str == val or expected_str == text:
                    return True
                if expected_str and (expected_str in text or expected_str in val or val in expected_str or text in expected_str):
                    return True
                if len(val) == 2 and len(expected_str) > 2 and (expected_str.startswith(val) or val in expected_str):
                    return True
                return False

            # Custom picklist / combobox
            if ctype == "picklist":
                val = str(actual.get("value", "")).strip().lower()
                sel_text = str(actual.get("selected_text", "")).strip().lower()
                target_str = sel_text if sel_text and sel_text not in junk else val
                if not target_str or target_str in junk:
                    return False
                if expected_str == target_str or expected_str in target_str or target_str in expected_str:
                    return True
                if len(target_str) == 2 and len(expected_str) > 2 and expected_str.startswith(target_str):
                    return True
                return False

            # Standard text / textarea
            val = str(actual.get("value", "")).strip()
            val_lower = val.lower()
            if not val:
                return expected_str == ""
            if expected_str == val_lower:
                return True
            # Whitespace normalized comparison
            if re.sub(r"\s+", " ", expected_str).strip() == re.sub(r"\s+", " ", val_lower).strip():
                return True
            # Phone / digits normalization
            digits_exp = re.sub(r"\D", "", expected_str)
            digits_val = re.sub(r"\D", "", val_lower)
            if digits_exp and digits_val and digits_exp == digits_val:
                return True
            # Currency / numeric normalization (e.g. "$1,234.56" vs "1234.56")
            clean_exp = re.sub(r"[^\d.]", "", expected_str)
            clean_val = re.sub(r"[^\d.]", "", val_lower)
            if clean_exp and clean_val and clean_exp == clean_val:
                return True
            return False

        # Fallback for plain string readback
        actual_lower = str(actual).strip().lower()
        if actual_lower in junk:
            return False
        if expected_str == actual_lower:
            return True
        if re.sub(r"\s+", " ", expected_str).strip() == re.sub(r"\s+", " ", actual_lower).strip():
            return True
        digits_exp = re.sub(r"\D", "", expected_str)
        digits_val = re.sub(r"\D", "", actual_lower)
        if digits_exp and digits_val and digits_exp == digits_val:
            return True
        clean_exp = re.sub(r"[^\d.]", "", expected_str)
        clean_val = re.sub(r"[^\d.]", "", actual_lower)
        if clean_exp and clean_val and clean_exp == clean_val:
            return True
        return False

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
