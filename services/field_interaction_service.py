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
        _, clean_target, scoped_parent = self.parse_target_descriptor(target_identifier)
        # Strict repeating section selectors (WP-104: Never use bare generic "Add" without scoped container)
        add_selectors = [
            '[id$="_addRowBtn"]',
            '[class*="addRowBtn" i]',
            '[class*="add-row" i]',
            '[class*="add_row" i]',
            '[data-action*="add-row" i]',
            'button:has-text("+ Add Row")',
            'button:has-text("Add Row")',
            'button:has-text("Add Another")',
            'button:has-text("Add Entry")',
        ]
        # Only include generic Add buttons if scoped_parent is explicitly provided
        if scoped_parent:
            add_selectors.extend([
                'button:has-text("Add")',
                'button:has-text("+ Add")',
                'input[type="button"][value*="Add" i]',
                '[role="button"]:has-text("Add")',
            ])

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
                    # Only click Add if the enclosing section has 0 visible inputs or matches scoped_parent
                    should_click = btn.evaluate(
                        """(el, scope) => {
                            const sec = el.closest('.rcmFormSection, [class*="rcmFormSection"], fieldset, section, .form-section');
                            if (!sec) return false; // WP-104: Never click an Add button without an explicit section boundary
                            if (scope) {
                                return (sec.innerText || '').toLowerCase().includes(scope.toLowerCase());
                            }
                            const existingInputs = sec.querySelectorAll('input:not([type="hidden"]):not([type="button"]), select, textarea, .datePicker[id], [id$=":_datepicker"], ui5-date-picker-xweb-calendar-widget, ui5-date-picker');
                            return existingInputs.length === 0;
                        }""",
                        scoped_parent or "",
                    )
                    if not should_click:
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
        # Check child iframes if not found in top-level document (WP-006)
        if not res.get("success") and hasattr(self.page, "frames") and len(self.page.frames) > 1:
            for frame in self.page.frames[1:]:
                try:
                    f_res = frame.evaluate(SET_FIELD_DOM_SCRIPT, [clean_target, value, type_hint, scoped_parent])
                    if f_res.get("success"):
                        res = f_res
                        break
                except Exception:
                    pass

        self.last_failure_reason = res.get("reason") or "No matching element found"
        if debug_lines is not None:
            debug_lines.append(f"    [debug] target='{clean_target}' (hint={type_hint}, scope={scoped_parent}), res={res}")

        # If scoped parent does not exist, fast fail immediately
        if not res.get("success") and res.get("reason") and "Scoped parent" in res.get("reason"):
            self.last_failure_reason = res.get("reason")
            if debug_lines is not None:
                debug_lines.append(f"    [!] Fast-fail: {res.get('reason')}")
            return False

        # Honeypot / Hidden decoy protection: never attempt fallback on hidden decoys (WPB-007)
        if not res.get("success") and res.get("reason") in (
            "Field is hidden or collapsed in DOM",
            "Field is read-only",
        ):
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

                        pick_res = None
                        for poll_idx in range(16):
                            self.page.wait_for_timeout(150)
                            pick_res = self.page.evaluate(PICKLIST_AUTO_SCROLL_SCRIPT, [inp_id, value])
                            if pick_res.get("success"):
                                break
                            if pick_res.get("reason") not in ("list_not_ready",):
                                break

                        if debug_lines is not None:
                            debug_lines.append(f"    [debug] pick_res={pick_res}")

                        if pick_res and pick_res.get("success"):
                            try:
                                tagged_opt = self.page.locator('[data-wp-pick-target="1"]')
                                if tagged_opt.count() > 0 and tagged_opt.first.is_visible(timeout=200):
                                    tagged_opt.first.click(force=True)
                                    if debug_lines is not None:
                                        debug_lines.append("    [debug] Dispatched native Playwright click on [data-wp-pick-target='1']")
                            except Exception:
                                pass
                            self.page.evaluate(
                                "([id]) => { const el = document.getElementById(id); if (el) { el.blur(); el.dispatchEvent(new Event('blur', { bubbles: true })); } }",
                                [inp_id],
                            )
                            self.page.wait_for_timeout(200)
                            selected_text = pick_res.get("text")
                            check_val = selected_text if selected_text and not str(value).startswith("@opt-") else (selected_text or value)
                            if self.verify_field_value(inp_id, check_val, settle_delay_ms=100):
                                return True
                            if self.verify_field_value(inp_id, value, settle_delay_ms=100):
                                return True
                        else:
                            self.page.keyboard.press("Escape")
                            self.page.wait_for_timeout(PAUSE_PICKLIST_CLOSE_MS)
                except Exception as exc:
                    if debug_lines is not None:
                        debug_lines.append(f"    [debug] Picklist click error: {exc}")

            # 2. Second attempt: type directly into input to trigger autocomplete filter
            if inp_id and not str(value).startswith(("@opt-", "index:", "#")):
                try:
                    inp_loc = self.page.locator(f'[id="{inp_id}"]').first
                    inp_vis = inp_loc.is_visible(timeout=1500)
                    if debug_lines is not None:
                        debug_lines.append(f"    [debug] inp_id='{inp_id}', is_visible={inp_vis}")
                    if inp_vis:
                        inp_loc.scroll_into_view_if_needed()
                        inp_loc.click(force=True)
                        inp_loc.fill("")
                        inp_loc.press_sequentially(str(value), delay=25)

                        pick_res = None
                        for _ in range(14):
                            self.page.wait_for_timeout(150)
                            pick_res = self.page.evaluate(PICKLIST_AUTO_SCROLL_SCRIPT, [inp_id, value])
                            if pick_res.get("success"):
                                break
                            if pick_res.get("reason") not in ("list_not_ready",):
                                break

                        if debug_lines is not None:
                            debug_lines.append(f"    [debug] inp pick_res={pick_res}")

                        if pick_res and pick_res.get("success"):
                            try:
                                tagged_opt = self.page.locator('[data-wp-pick-target="1"]')
                                if tagged_opt.count() > 0 and tagged_opt.first.is_visible(timeout=200):
                                    tagged_opt.first.click(force=True)
                                    if debug_lines is not None:
                                        debug_lines.append("    [debug] Clicked filtered option via [data-wp-pick-target='1']")
                            except Exception:
                                pass

                            self.page.evaluate(
                                "([id]) => { const el = document.getElementById(id); if (el) { el.blur(); el.dispatchEvent(new Event('blur', { bubbles: true })); } }",
                                [inp_id],
                            )
                            self.page.wait_for_timeout(200)

                            selected_text = pick_res.get("text")
                            check_val = selected_text or value
                            if self.verify_field_value(inp_id, check_val, settle_delay_ms=100) or self.verify_field_value(inp_id, value, settle_delay_ms=100):
                                if debug_lines is not None:
                                    debug_lines.append(f"    [debug] Verified '{inp_id}' directly after fill & option click")
                                return True
                        else:
                            self.page.keyboard.press("Escape")
                            self.page.evaluate(
                                "([id]) => { const el = document.getElementById(id); if (el) { el.blur(); el.dispatchEvent(new Event('blur', { bubbles: true })); } }",
                                [inp_id],
                            )
                            self.page.wait_for_timeout(PAUSE_PICKLIST_CLOSE_MS)
                except Exception as exc:
                    if debug_lines is not None:
                        debug_lines.append(f"    [debug] Picklist input type error: {exc}")

            # Picklist failed after thorough probe -> fast fail, do not attempt unrelated click fallback
            self.last_failure_reason = f"Option '{value}' not found in picklist '{clean_target}'"
            if debug_lines is not None:
                debug_lines.append(f"    [!] Fast-fail: {self.last_failure_reason}")
            return False

        # Non-picklist JS success: verify whether the DOM actually accepted the value.
        if res.get("success") and res.get("type") not in ("picklist",):
            # For checkboxes and choices, dispatch native Playwright check/click to generate trusted CDP events (WP-103)
            if res.get("type") in ("checkbox", "choice", "radio", "switch"):
                field_id = res.get("id")
                if field_id:
                    try:
                        loc = self.page.locator(f'[id="{field_id}"]').first
                        if loc.count() > 0:
                            str_val = str(value).lower()
                            is_check = str_val in ("yes", "true", "1", "on", "checked")
                            if res.get("type") in ("checkbox", "switch"):
                                if is_check:
                                    if loc.is_checked():
                                        loc.uncheck(force=True, timeout=500)
                                    loc.check(force=True, timeout=1000)
                                else:
                                    if not loc.is_checked():
                                        loc.check(force=True, timeout=500)
                                    loc.uncheck(force=True, timeout=1000)
                            else:
                                loc.click(force=True, timeout=1000)
                            self.page.wait_for_timeout(100)
                    except Exception:
                        pass

            # Check for async typeahead suggestion container (e.g. S03, S24)
            try:
                has_sug = self.page.evaluate("() => !!document.querySelector('#sug, .sug, [role=\"listbox\"], .tt-menu, .autocomplete-suggestions')")
                if has_sug:
                    sug_loc = self.page.locator('#sug div, .sug div, [role="listbox"] [role="option"], .tt-suggestion, .autocomplete-suggestion').filter(has_text=str(value))
                    try:
                        sug_loc.first.wait_for(state="visible", timeout=3000)
                    except Exception:
                        pass
                    if sug_loc.count() > 0 and sug_loc.first.is_visible():
                        sug_loc.first.click(force=True)
                        self.page.wait_for_timeout(100)
                        if debug_lines is not None:
                            debug_lines.append(f"    [debug] Clicked typeahead suggestion for '{value}'")
            except Exception:
                pass

            # Allow async framework controlled-input re-render (React/Vue/Angular 250ms debounces, WP-102)
            if res.get("type") in ("input", "text", "textarea"):
                self.page.wait_for_timeout(260)
                try:
                    committed = self.page.evaluate("(id) => { const el = document.getElementById(id); return el ? el.value : null; }", res.get("id"))
                    if committed is not None:
                        res["value"] = committed
                except Exception:
                    pass

            verify_target = res.get("id") if (scoped_parent and res.get("id")) else clean_target
            if self.verify_field_value(verify_target, value, settle_delay_ms=20):
                self.last_failure_reason = ""
                return True
            if res.get("type") == "date":
                self.last_failure_reason = f"Invalid or rejected date value '{value}' for field '{clean_target}'"
                return False
            # If verify failed, record the verification mismatch instead of generic not found (WP-108)
            actual_dom = getattr(self, "last_dom_readback", None)
            dom_val = actual_dom.get("value") if isinstance(actual_dom, dict) else actual_dom
            self.last_failure_reason = f"Verification mismatch for '{clean_target}': DOM held '{dom_val}' (expected '{value}')"

        # Fallback to Playwright native interaction
        fallback_res = self._playwright_click_fallback(clean_target, value)
        if fallback_res:
            if self.verify_field_value(clean_target, value, settle_delay_ms=30):
                self.last_failure_reason = ""
                return True
            self.last_failure_reason = f"Value for '{clean_target}' did not verify after native interaction"
            return False
        return False

    def verify_field_value(self, target: str, expected: Any, settle_delay_ms: int = 50) -> bool:
        """Reads back current DOM value and confirms state, allowing framework settle window."""
        expected_str = str(expected).strip().lower() if expected is not None else ""
        try:
            actual = self.page.evaluate(VERIFY_FIELD_DOM_SCRIPT, [target, expected_str])
            if not actual or not actual.get("found"):
                if hasattr(self.page, "frames") and len(self.page.frames) > 1:
                    for frame in self.page.frames[1:]:
                        try:
                            f_act = frame.evaluate(VERIFY_FIELD_DOM_SCRIPT, [target, expected_str])
                            if f_act and f_act.get("found"):
                                actual = f_act
                                break
                        except Exception:
                            pass
            self.last_dom_readback = actual
            if actual and actual.get("found"):
                if self._match_actual_dom_data(actual, expected):
                    return True
            else:
                # Shadow DOM fallback: only when element was NOT found in light DOM
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
                self.last_dom_readback = retry_actual
                if retry_actual and retry_actual.get("found"):
                    return self._match_actual_dom_data(retry_actual, expected)
            return False
        except Exception:
            return False

    def probe_field(
        self,
        target: Optional[str] = None,
        include_options: bool = True,
        query: Optional[str] = None,
        include_html: bool = False,
        up_levels: int = 0,
        screenshot_path: Optional[str] = None,
        selector: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Probes a specific form field or picklist and retrieves deep diagnostic metadata."""
        effective_target = target or ""
        effective_selector = selector or ""
        try:
            details = self.page.evaluate(
                PROBE_FIELD_DOM_SCRIPT,
                [effective_target, include_options, query or "", include_html, up_levels, effective_selector],
            )
            if not details or not details.get("found"):
                if hasattr(self.page, "frames") and len(self.page.frames) > 1:
                    for frame in self.page.frames[1:]:
                        try:
                            f_details = frame.evaluate(
                                PROBE_FIELD_DOM_SCRIPT,
                                [effective_target, include_options, query or "", include_html, up_levels, effective_selector],
                            )
                            if f_details and f_details.get("found"):
                                frame_name = frame.name or "Sub-frame"
                                f_details["context_env"] = {
                                    "frame": f"Iframe ({frame_name})",
                                    "in_shadow_dom": f_details.get("context_env", {}).get("in_shadow_dom", False),
                                    "is_iframe": True,
                                }
                                details = f_details
                                break
                        except Exception:
                            pass

            if details and details.get("found"):
                # Interactive Picklist / AJAX Combobox / Select2 Typeahead Probe (WP-271)
                is_picklist_like = (
                    details.get("type") in ("picklist", "combobox", "select", "select2")
                    or bool(details.get("trigger_button"))
                    or bool(details.get("owns_id"))
                    or (include_options and not details.get("options"))
                )

                if include_options and is_picklist_like:
                    trig_id = details.get("trigger_button")
                    inp_id = details.get("id")
                    orig_val = details.get("value") or ""

                    # 1. Open picklist dropdown if not opened and options are empty (only when no query is provided)
                    if not query and not details.get("options") and trig_id and self.page.locator(f'[id="{trig_id}"]').count() > 0:
                        btn = self.page.locator(f'[id="{trig_id}"]').first
                        if btn.is_visible(timeout=500):
                            btn.scroll_into_view_if_needed()
                            btn.click(force=True)
                            for _ in range(10):
                                self.page.wait_for_timeout(150)
                                retry_details = self.page.evaluate(
                                    PROBE_FIELD_DOM_SCRIPT,
                                    [target, include_options, query or "", include_html, up_levels],
                                )
                                if retry_details and retry_details.get("options"):
                                    details = retry_details
                                    break
                            self.page.keyboard.press("Escape")
                            self.page.wait_for_timeout(100)

                    # 2. Interactive AJAX Typeahead Search (Siemens Select2, UI5, Comboboxes)
                    if query:
                        search_target_loc = None
                        search_candidates = [
                            ".select2-search__field",
                            "input.select2-input",
                            'input[role="searchbox"]',
                            'input[role="combobox"]',
                            'input[type="search"]',
                            f'[id="{inp_id}"]' if inp_id else None,
                            f'[data-wp-id="{target}"]' if target and target.startswith("@") else None,
                        ]
                        for cand in search_candidates:
                            if not cand:
                                continue
                            try:
                                loc = self.page.locator(cand)
                                if loc.count() > 0 and loc.first.is_visible(timeout=300):
                                    search_target_loc = loc.first
                                    break
                            except Exception:
                                pass

                        if not search_target_loc:
                            open_triggers = [
                                f'[id="{trig_id}"]' if trig_id else None,
                                f'[id="{inp_id}"]' if inp_id else None,
                                f'[data-wp-id="{target}"]' if target and target.startswith("@") else None,
                                ".select2-choice",
                                ".select2-selection",
                            ]
                            for trig in open_triggers:
                                if not trig:
                                    continue
                                try:
                                    tloc = self.page.locator(trig)
                                    if tloc.count() > 0 and tloc.first.is_visible(timeout=300):
                                        tloc.first.scroll_into_view_if_needed()
                                        tloc.first.click(force=True)
                                        self.page.wait_for_timeout(200)
                                        break
                                except Exception:
                                    pass

                            for cand in [".select2-search__field", "input.select2-input", 'input[role="searchbox"]', f'[id="{inp_id}"]']:
                                if not cand:
                                    continue
                                try:
                                    loc = self.page.locator(cand)
                                    if loc.count() > 0 and loc.first.is_visible(timeout=300):
                                        search_target_loc = loc.first
                                        break
                                except Exception:
                                    pass

                        if search_target_loc:
                            try:
                                search_target_loc.scroll_into_view_if_needed()
                                search_target_loc.click(force=True)
                                search_target_loc.fill("")
                                search_target_loc.press_sequentially(str(query), delay=35)
                                for _ in range(15):
                                    self.page.wait_for_timeout(150)
                                    ajax_opts = self.page.evaluate("""() => {
                                        const items = Array.from(document.querySelectorAll(
                                            '.select2-results__option, li.select2-result, [role="option"], .ui-menu-item, li[data-wp-option], .rcmpaginatedselectitem'
                                        ));
                                        return items.map((el, idx) => ({
                                            local_id: `@opt-${idx + 1}`,
                                            text: (el.innerText || el.textContent || '').trim(),
                                            value: el.getAttribute('data-id') || el.getAttribute('id') || el.getAttribute('data-value') || el.getAttribute('value') || (el.innerText || '').trim(),
                                            id: el.id || '',
                                        })).filter(o => o.text && !o.text.includes('Searching') && !o.text.includes('Loading'));
                                    }""")
                                    if ajax_opts:
                                        details["options"] = ajax_opts
                                        details["options_count"] = len(ajax_opts)
                                        break
                            except Exception:
                                pass
                            finally:
                                self.page.keyboard.press("Escape")
                                self.page.keyboard.press("Escape")
                                self.page.wait_for_timeout(100)

                # Capture element visual screenshot if requested
                if screenshot_path:
                    try:
                        probe_loc = self.page.locator('[data-wp-probe-target="1"]').first
                        if probe_loc.count() > 0:
                            probe_loc.scroll_into_view_if_needed()
                            resolved_path = screenshot_path
                            if resolved_path == "auto" or not resolved_path:
                                clean_id = (details.get("local_id") or details.get("id") or "element").replace("@", "").replace(":", "_")
                                resolved_path = f"element_{clean_id}.png"
                            probe_loc.screenshot(path=resolved_path)
                            details["screenshot_path"] = resolved_path
                    except Exception as exc:
                        details["screenshot_error"] = str(exc)
                    finally:
                        try:
                            self.page.evaluate("() => { document.querySelectorAll('[data-wp-probe-target]').forEach(n => n.removeAttribute('data-wp-probe-target')); }")
                        except Exception:
                            pass

            return details
        except Exception:
            return None

