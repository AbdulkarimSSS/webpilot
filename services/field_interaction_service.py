"""Field value setting and DOM verification service."""

from __future__ import annotations

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

        # Non-picklist JS success
        if res.get("success") and res.get("type") not in ("picklist",):
            return True

        # Fallback to Playwright native interaction
        return self._playwright_click_fallback(target_identifier, value)

    def _playwright_click_fallback(self, target: str, value: Any) -> bool:
        """Fallback setter using Playwright native locators (click / fill)."""
        page = self.page
        strval = str(value)
        lower = target.lower().strip()

        # 1. Picklist combobox by aria-label or title
        for loc in [
            page.locator(f'input[aria-label*="{target}"][role="combobox"]'),
            page.locator(f'input[title*="{target}"][role="combobox"]'),
        ]:
            try:
                if loc.count() > 0 and loc.first.is_visible(timeout=300):
                    loc.first.click()
                    page.wait_for_timeout(300)
                    for role_name in ["menuitem", "option", "listitem"]:
                        opt = page.get_by_role(role_name, name=strval, exact=False)  # type: ignore
                        if opt.count() > 0:
                            opt.first.click()
                            page.wait_for_timeout(PAUSE_RETRY_FALLBACK_MS)
                            return True
                    page.keyboard.press("Escape")
            except Exception:
                pass

        # 2. Native radio by ARIA role
        try:
            radio = page.get_by_role("radio", name=strval, exact=False)
            if radio.count() > 0:
                radio.first.click()
                return True
        except Exception:
            pass

        # 3. Custom ARIA radioLabel spans (SuccessFactors)
        for selector in [
            f'.radioLabel:text-is("{strval}")',
            f'.radioLabel:has-text("{strval}")',
        ]:
            try:
                spans = page.locator(selector)
                if spans.count() > 0:
                    spans.first.click()
                    return True
            except Exception:
                pass

        # 4. Text / Textarea via label
        try:
            field = page.get_by_label(lower, exact=False)
            if field.count() > 0 and field.first.is_visible(timeout=300):
                field.first.fill(strval)
                field.first.dispatch_event("change")
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

    def verify_field_value(self, target: str, expected: Any) -> bool:
        """Reads back current DOM value and checks if it matches expected."""
        expected_str = str(expected).strip().lower()
        junk = {"login/ view profile", "no selection", ""}

        try:
            actual = self.page.evaluate(VERIFY_FIELD_DOM_SCRIPT, [target, expected_str])
            if actual is None:
                return False
            actual_lower = str(actual).strip().lower()
            if actual_lower in junk:
                return False
            return expected_str in actual_lower
        except Exception:
            return False
