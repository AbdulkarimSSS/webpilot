"""Reactive button clicking and state observation service."""

from __future__ import annotations

from typing import Any, Callable, Dict, Optional
from playwright.sync_api import BrowserContext, Page

from adapters.dom_scripts import CLICK_BUTTON_DOM_SCRIPT
from constants.selectors import SELECTOR_MODAL_DIALOGS
from constants.timeouts import PAUSE_REACTIVE_STABILIZE_MS
from services.inspection_service import InspectionService
from validators.form_validator import FormValidator


class ReactiveInteractionService:
    """Clicks buttons and actively tracks environmental mutations (tabs, routes, modals, fields)."""

    def __init__(
        self,
        page: Page,
        context: BrowserContext,
        inspection_service: InspectionService,
        form_validator: FormValidator,
        on_active_page_change: Optional[Callable[[Page], None]] = None,
    ):
        self.page = page
        self.context = context
        self.inspection_service = inspection_service
        self.form_validator = form_validator
        self.on_active_page_change = on_active_page_change

    def click_button(self, button_text_or_purpose: str) -> Dict[str, Any]:
        """Intelligently clicks a button/link and monitors reactive consequences."""
        target = button_text_or_purpose.strip()

        # 1. Baseline state
        pre_url = self.page.url
        pre_tabs_count = len(self.context.pages)
        pre_inputs_count = self.page.locator("input, select, textarea").count()
        pre_modals_count = self.page.locator(SELECTOR_MODAL_DIALOGS).count()

        clicked = False

        # Strategy A: Native ID
        clean_id = target.lstrip("#")
        try:
            loc = self.page.locator(f"#{clean_id}")
            if loc.count() > 0 and loc.first.is_visible(timeout=400):
                loc.first.click(timeout=1000)
                clicked = True
        except Exception:
            pass

        # Strategy B: Native Text / Role
        if not clicked:
            try:
                for selector in [
                    f"button:has-text('{target}')",
                    f"a:has-text('{target}')",
                    f"[role='button']:has-text('{target}')",
                    f"input[type='button'][value*='{target}']",
                    f"input[type='submit'][value*='{target}']",
                    f".modal-footer p:has-text('{target}')",
                    f"p:has-text('{target}')",
                    f"span:has-text('{target}')",
                ]:
                    cand = self.page.locator(selector)
                    if cand.count() > 0 and cand.first.is_visible(timeout=400):
                        cand.first.click(timeout=1000)
                        clicked = True
                        break
            except Exception:
                pass

        # Strategy C: JavaScript fallback
        if not clicked:
            clicked = self.page.evaluate(CLICK_BUTTON_DOM_SCRIPT, target)

        # Strategy D: Modal Dismiss / Escape fallback
        if not clicked and target.lower().strip() in ("close", "dismiss", "cancel", "escape"):
            try:
                self.page.keyboard.press("Escape")
                clicked = True
            except Exception:
                pass

        # Strategy E: Dismiss blocking modal/backdrop and retry
        if not clicked:
            if self.dismiss_blocking_overlays():
                clicked = self.page.evaluate(CLICK_BUTTON_DOM_SCRIPT, target)

        if not clicked:
            return {"success": False, "target": target}

        # 2. Wait for reactive stabilization and loading overlay dissolution
        self.page.wait_for_timeout(PAUSE_REACTIVE_STABILIZE_MS)
        try:
            self.page.wait_for_load_state("domcontentloaded", timeout=4000)
        except Exception:
            pass

        self._wait_for_loading_dissolution()

        # 3. Assess reactive changes
        outcome: Dict[str, Any] = {
            "success": True,
            "target": target,
            "redirected": False,
            "new_window": False,
            "new_url": None,
            "modal_opened": False,
            "modal_text": "",
            "new_inputs_count": 0,
            "schema": None,
            "alerts": self.form_validator.get_validation_errors(),
        }

        # Check for new window / tab
        if len(self.context.pages) > pre_tabs_count:
            self.page = self.context.pages[-1]
            if self.on_active_page_change:
                self.on_active_page_change(self.page)
            outcome["new_window"] = True
            outcome["new_url"] = self.page.url
            outcome["schema"] = self.inspection_service.inspect(unpack_options=False)
            return outcome

        # Check for URL redirect / client-side route change
        post_url = self.page.url
        if post_url != pre_url:
            outcome["redirected"] = True
            outcome["new_url"] = post_url
            outcome["schema"] = self.inspection_service.inspect(unpack_options=False)
            return outcome

        # Check for modal / dialog appearance
        post_modals = self.page.locator(SELECTOR_MODAL_DIALOGS)
        if post_modals.count() > pre_modals_count:
            outcome["modal_opened"] = True
            try:
                outcome["modal_text"] = post_modals.first.inner_text().strip()[:400]
            except Exception:
                pass
            outcome["schema"] = self.inspection_service.inspect(unpack_options=False)
            return outcome

        # Check for dynamic DOM form inputs growth
        post_inputs_count = self.page.locator("input, select, textarea").count()
        if post_inputs_count > pre_inputs_count:
            outcome["new_inputs_count"] = post_inputs_count - pre_inputs_count
            outcome["schema"] = self.inspection_service.inspect(unpack_options=False)
            return outcome

        return outcome

    def _wait_for_loading_dissolution(self, timeout_ms: int = 10000) -> None:
        """Detects if a blocking loader, spinner, or progress bar appeared and waits for its dissolution."""
        try:
            loader_selectors = [
                "#loading:visible",
                ".loading:visible",
                ".spinner:visible",
                ".busyIndicator:visible",
                ".sapUiBusy:visible",
                "[role='progressbar']:visible",
                "[aria-busy='true']",
            ]
            for sel in loader_selectors:
                loc = self.page.locator(sel)
                if loc.count() > 0 and loc.first.is_visible():
                    print(f"[*] Blocking loader detected ('{sel}'). Waiting for completion...")
                    try:
                        loc.first.wait_for(state="hidden", timeout=timeout_ms)
                        print("[✓] Loader completed and disappeared.")
                    except Exception:
                        pass
                    break
        except Exception:
            pass

    def dismiss_blocking_overlays(self) -> bool:
        """Dismisses cookie banners, popups, and modal dialogs that obscure the underlying form."""
        dismissed = False
        try:
            for sel in [
                "#cookie button",
                ".cookie-banner button",
                "[aria-label*='cookie' i] button",
                "button:has-text('Accept')",
                "button:has-text('Accept All')",
                "button:has-text('Agree')",
                "button:has-text('I agree')",
            ]:
                loc = self.page.locator(sel)
                if loc.count() > 0 and loc.first.is_visible(timeout=200):
                    loc.first.click()
                    dismissed = True
                    self.page.wait_for_timeout(200)
                    break
        except Exception:
            pass

        try:
            for sel in [
                "[role='dialog'] button:has-text('Close')",
                ".modal button:has-text('Close')",
                "#modal button:has-text('Close')",
                ".modal-close",
                "button[aria-label*='Close' i]",
            ]:
                loc = self.page.locator(sel)
                if loc.count() > 0 and loc.first.is_visible(timeout=200):
                    loc.first.click()
                    dismissed = True
                    self.page.wait_for_timeout(200)
                    break
        except Exception:
            pass

        try:
            if self.page.locator("[role='dialog']:visible, .bk:visible, #backdrop:visible").count() > 0:
                self.page.keyboard.press("Escape")
                dismissed = True
                self.page.wait_for_timeout(200)
        except Exception:
            pass

        return dismissed
