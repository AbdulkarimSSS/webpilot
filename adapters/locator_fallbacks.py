"""Native Playwright locator interaction strategies and fallback resolvers."""

from __future__ import annotations

from typing import Any
from playwright.sync_api import Page

from constants.timeouts import PAUSE_RETRY_FALLBACK_MS


class PlaywrightLocatorFallback:
    """Provides resilient Playwright native interaction fallbacks when JS manipulation cannot succeed."""

    @staticmethod
    def escape_css_attr(val: str) -> str:
        """Escapes special characters in CSS attribute selectors."""
        return str(val).replace("\\", "\\\\").replace('"', '\\"')

    @classmethod
    def execute(cls, page: Page, target: str, value: Any) -> bool:
        """Fallback setter using Playwright native locators (click / fill / select / check)."""
        strval = str(value)
        lower = target.lower().strip()
        safe_target = cls.escape_css_attr(target)
        safe_strval = cls.escape_css_attr(strval)

        # 000. Arbitrary Selector locator (css=..., xpath=..., //..., selector:...)
        clean_sel = target.strip()
        if clean_sel.startswith(("selector:", "selector=")):
            clean_sel = clean_sel.split(":", 1)[-1] if ":" in clean_sel else clean_sel.split("=", 1)[-1]
        if clean_sel.startswith(("css=", "css:", "xpath=", "xpath:", "//")):
            if clean_sel.startswith("css:"):
                clean_sel = clean_sel[4:]
            elif clean_sel.startswith("xpath:"):
                clean_sel = "xpath=" + clean_sel[6:]
            try:
                sel_loc = page.locator(clean_sel)
                if sel_loc.count() > 0 and sel_loc.first.is_visible(timeout=300):
                    first_el = sel_loc.first
                    tag = (first_el.evaluate("el => (el.tagName || '').toLowerCase()") or "")
                    if tag == "select":
                        first_el.select_option(strval)
                        return True
                    else:
                        first_el.focus()
                        try:
                            first_el.fill(strval)
                        except Exception:
                            first_el.press_sequentially(strval, delay=15)
                        first_el.dispatch_event("input")
                        first_el.dispatch_event("change")
                        return True
            except Exception:
                pass

        # 00. Direct LocalID (@fld-N, @drop-N, @opt-N) with Playwright (pierces open Shadow DOMs natively)
        if target.startswith("@"):
            try:
                wp_loc = page.locator(f'[data-wp-id="{safe_target}"]')
                if wp_loc.count() > 0 and wp_loc.first.is_visible(timeout=300):
                    first_el = wp_loc.first
                    tag = (first_el.evaluate("el => (el.tagName || '').toLowerCase()") or "")
                    role = (first_el.get_attribute("role") or "").lower()
                    if tag == "select":
                        first_el.select_option(strval)
                        return True
                    elif role == "switch" or (tag == "input" and (first_el.get_attribute("type") or "").lower() in ("checkbox", "radio")):
                        first_el.click()
                        return True
                    else:
                        first_el.focus()
                        try:
                            first_el.fill(strval)
                        except Exception:
                            first_el.press_sequentially(strval, delay=15)
                        first_el.dispatch_event("input")
                        first_el.dispatch_event("change")
                        return True
            except Exception:
                pass

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
                p_safe = cls.escape_css_attr(p)
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
