"""Reactive button clicking and state observation service."""

from __future__ import annotations

import time
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
        target = (button_text_or_purpose or "").strip()
        if not target:
            return {
                "success": False,
                "message": "Empty button text or target specified.",
                "redirected": False,
                "new_window": False,
                "modal_opened": False,
                "new_inputs_count": 0,
            }

        # 1. Baseline state
        pre_url = self.page.url
        pre_tabs_count = len(self.context.pages)
        try:
            baseline_counts = self.page.evaluate(
                f"() => [document.querySelectorAll('input, select, textarea').length, document.querySelectorAll('{SELECTOR_MODAL_DIALOGS}').length]"
            )
            pre_inputs_count, pre_modals_count = baseline_counts[0], baseline_counts[1]
        except Exception:
            pre_inputs_count, pre_modals_count = 0, 0

        clicked = False

        is_scoped = ">>" in target

        def _is_nav_exc(exc: Exception) -> bool:
            err = str(exc).lower()
            return "execution context was destroyed" in err or "navigation" in err or "navigating" in err

        # Strategy -1: Active Form Scoped Button Search (pierces Shadow DOM) (WP-001)
        if not is_scoped and not target.startswith("@"):
            try:
                if self.page.evaluate(CLICK_BUTTON_DOM_SCRIPT, target):
                    clicked = True
            except Exception as exc:
                if _is_nav_exc(exc):
                    clicked = True

        # Strategy 0: Arbitrary selector (css=..., xpath=..., //..., selector:...)
        clean_sel = target.strip()
        if clean_sel.startswith(("selector:", "selector=")):
            clean_sel = clean_sel.split(":", 1)[-1] if ":" in clean_sel else clean_sel.split("=", 1)[-1]
        if clean_sel.startswith(("css=", "css:", "xpath=", "xpath:", "//")):
            if clean_sel.startswith("css:"):
                clean_sel = clean_sel[4:]
            elif clean_sel.startswith("xpath:"):
                clean_sel = "xpath=" + clean_sel[6:]
            try:
                loc = self.page.locator(clean_sel)
                if loc.count() > 0 and loc.first.is_visible(timeout=400):
                    loc.first.scroll_into_view_if_needed()
                    try:
                        loc.first.click(timeout=1500)
                        clicked = True
                    except Exception as exc:
                        if _is_nav_exc(exc):
                            clicked = True
            except Exception as exc:
                if _is_nav_exc(exc):
                    clicked = True

        # Strategy A: LocalID (@btn-N) or Native ID ([id="..."])
        if not is_scoped and not clicked and target.startswith("@"):
            try:
                loc = self.page.locator(f'[data-wp-id="{target}"]')
                if loc.count() > 0 and loc.first.is_visible(timeout=400):
                    loc.first.scroll_into_view_if_needed()
                    try:
                        loc.first.click(timeout=1500)
                        clicked = True
                    except Exception as exc:
                        if _is_nav_exc(exc):
                            clicked = True
            except Exception as exc:
                if _is_nav_exc(exc):
                    clicked = True

        if not is_scoped and not clicked:
            clean_id = target.lstrip("#")
            try:
                for id_sel in (f'[id="{clean_id}"]', f"#{clean_id}"):
                    loc = self.page.locator(id_sel)
                    if loc.count() > 0 and loc.first.is_visible(timeout=400):
                        loc.first.scroll_into_view_if_needed()
                        try:
                            loc.first.click(timeout=1500)
                            clicked = True
                            break
                        except Exception as exc:
                            if _is_nav_exc(exc):
                                clicked = True
                                break
            except Exception as exc:
                if _is_nav_exc(exc):
                    clicked = True

        # Strategy B1: Exact Native Text / Role match first (prevents 'Save' matching 'Saved Applications')
        if not is_scoped and not clicked:
            try:
                for selector in [
                    f"button:text-is('{target}')",
                    f"a:text-is('{target}')",
                    f"[role='button']:text-is('{target}')",
                    f"button span:text-is('{target}')",
                    f"a span:text-is('{target}')",
                    f"input[type='submit'][value='{target}']",
                    f"input[type='button'][value='{target}']",
                ]:
                    cand = self.page.locator(selector)
                    cnt = cand.count()
                    if cnt == 1:
                        try:
                            cand.first.click(timeout=1000)
                            clicked = True
                            break
                        except Exception as exc:
                            if _is_nav_exc(exc):
                                clicked = True
                                break
                    elif cnt > 1:
                        # Multiple matches without scope: ambiguous target!
                        break
            except Exception as exc:
                if _is_nav_exc(exc):
                    clicked = True

        # Strategy B2: Substring Native Text / Role fallback
        if not is_scoped and not clicked:
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
                    cnt = cand.count()
                    if cnt == 1 and cand.first.is_visible(timeout=400):
                        cand.first.scroll_into_view_if_needed()
                        try:
                            cand.first.click(timeout=1500)
                            clicked = True
                            break
                        except Exception as exc:
                            if _is_nav_exc(exc):
                                clicked = True
                                break
                    elif cnt > 1:
                        # Multiple matches without scope: ambiguous target!
                        break
            except Exception as exc:
                if _is_nav_exc(exc):
                    clicked = True

        # Strategy B3: Semantic Submit / Synonym Match (WP-009)
        if not is_scoped and not clicked and target.lower().strip() in ("submit", "apply"):
            try:
                for selector in [
                    "button[type='submit']",
                    "input[type='submit']",
                    "form button:not([type='button']):not([type='reset'])",
                    "button:has-text('Register')",
                    "button:has-text('Save')",
                    "button:has-text('Continue')",
                    "button:has-text('Create Account')",
                    "button:has-text('Send')",
                    "button:has-text('Sign Up')",
                    "button:has-text('Confirm')",
                    "[role='button']:has-text('Register')",
                    "[role='button']:has-text('Save')",
                    "[role='button']:has-text('Continue')",
                ]:
                    cand = self.page.locator(selector)
                    if cand.count() > 0:
                        try:
                            cand.first.click(timeout=1000)
                            clicked = True
                            break
                        except Exception as exc:
                            if _is_nav_exc(exc):
                                clicked = True
                                break
            except Exception as exc:
                if _is_nav_exc(exc):
                    clicked = True

        # Strategy C: JavaScript fallback
        if not clicked:
            try:
                clicked = self.page.evaluate(CLICK_BUTTON_DOM_SCRIPT, target)
            except Exception as exc:
                err_str = str(exc).lower()
                if "execution context was destroyed" in err_str or "navigation" in err_str or "navigating" in err_str:
                    clicked = True
                else:
                    pass

        # Strategy D: Modal Dismiss / Escape fallback
        if not clicked:
            if target.lower().strip() == "escape":
                try:
                    self.page.keyboard.press("Escape")
                    clicked = True
                except Exception:
                    pass
            elif target.lower().strip() in ("close", "dismiss", "cancel"):
                try:
                    if self.dismiss_blocking_overlays():
                        clicked = True
                except Exception:
                    pass

        # Strategy E: Dismiss blocking modal/backdrop and retry
        if not clicked:
            if self.dismiss_blocking_overlays():
                try:
                    clicked = self.page.evaluate(CLICK_BUTTON_DOM_SCRIPT, target)
                except Exception as exc:
                    err_str = str(exc).lower()
                    if "execution context was destroyed" in err_str or "navigation" in err_str or "navigating" in err_str:
                        clicked = True
                    else:
                        pass

        # Strategy F: Frame Traversal fallback (WP-006)
        if not clicked and hasattr(self.page, "frames") and len(self.page.frames) > 1:
            for frame in self.page.frames[1:]:
                try:
                    f_clicked = frame.evaluate(CLICK_BUTTON_DOM_SCRIPT, target)
                    if f_clicked:
                        clicked = True
                        break
                    cand = frame.locator(
                        f"button:has-text('{target}'), a:has-text('{target}'), [role='button']:has-text('{target}'), input[value*='{target}']"
                    )
                    if cand.count() > 0:
                        cand.first.click(timeout=1000)
                        clicked = True
                        break
                except Exception as exc:
                    if _is_nav_exc(exc):
                        clicked = True
                        break

        if not clicked:
            return {"success": False, "target": target}

        # 2. Event-Driven Reactive Observation Loop (Mutation-First)
        # Check immediately for DOM mutations, modal appearance, URL redirects, or tab spawns.
        # Zero blocking on networkidle or page load states.
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
            "alerts": [],
        }

        # Initial micro-tick (50ms) to allow browser DOM event dispatch
        try:
            self.page.wait_for_timeout(50)
        except Exception:
            pass

        t_start = time.time()
        max_observation_seconds = 4.0

        loader_selectors = (
            "#loading:visible, .loading:visible, .spinner:visible, "
            ".busyIndicator:visible, .sapUiBusy:visible, [role='progressbar']:visible, [aria-busy='true']"
        )

        while time.time() - t_start < max_observation_seconds:
            # Check 1: New window / tab spawned
            try:
                pages_count = len(self.context.pages)
            except Exception:
                pages_count = pre_tabs_count

            if pages_count > pre_tabs_count:
                self.page = self.context.pages[-1]
                if self.on_active_page_change:
                    self.on_active_page_change(self.page)
                outcome["new_window"] = True
                try:
                    outcome["new_url"] = self.page.url
                    outcome["schema"] = self.inspection_service.inspect(unpack_options=False)
                except Exception:
                    pass
                return outcome

            # Check 2: URL redirect / route navigation
            try:
                post_url = self.page.url
            except Exception:
                post_url = pre_url

            if post_url != pre_url:
                outcome["redirected"] = True
                outcome["new_url"] = post_url
                try:
                    outcome["schema"] = self.inspection_service.inspect(unpack_options=False)
                except Exception:
                    pass
                return outcome

            # Check 3: Modal / dialog appearance (e.g. Easy Apply overlay)
            try:
                post_modals = self.page.locator(SELECTOR_MODAL_DIALOGS)
                if post_modals.count() > pre_modals_count:
                    outcome["modal_opened"] = True
                    try:
                        outcome["modal_text"] = post_modals.first.inner_text().strip()[:400]
                    except Exception:
                        pass
                    outcome["schema"] = self.inspection_service.inspect(unpack_options=False)
                    return outcome
            except Exception:
                pass

            # Check 4: Dynamic form inputs growth
            try:
                post_inputs_count = self.page.locator("input, select, textarea").count()
                if post_inputs_count > pre_inputs_count:
                    outcome["new_inputs_count"] = post_inputs_count - pre_inputs_count
                    outcome["schema"] = self.inspection_service.inspect(unpack_options=False)
                    return outcome
            except Exception:
                pass

            # Check 5: Validation errors / alerts appeared
            try:
                alerts = self.form_validator.get_validation_errors()
                if alerts:
                    outcome["alerts"] = alerts
                    return outcome
            except Exception:
                pass

            # Passive Spinner/Loader check: if page is actively displaying a loader, allow it to continue loading
            # without exiting prematurely, while still checking for DOM mutations on every 50ms tick
            try:
                is_busy = self.page.locator(loader_selectors).count() > 0
            except Exception:
                is_busy = False

            if not is_busy and (time.time() - t_start > 1.2):
                # If page is idle and no mutations occurred after initial stabilization window, exit cleanly
                break

            # Micro-wait 50ms before next check
            try:
                self.page.wait_for_timeout(50)
            except Exception:
                break

        # Fallback if no explicit mutation occurred within observation window
        try:
            outcome["alerts"] = self.form_validator.get_validation_errors()
        except Exception:
            outcome["alerts"] = []

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
