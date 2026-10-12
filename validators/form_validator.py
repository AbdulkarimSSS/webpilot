"""Form validation and error banner inspection."""

from typing import List
from playwright.sync_api import Page
from constants.selectors import SELECTOR_VALIDATION_ERRORS

class FormValidator:
    """Inspects the active DOM for validation notices, errors, and alerts."""

    def __init__(self, page: Page):
        self.page = page

    def get_validation_errors(self) -> List[str]:
        """Collects error alerts, validation messages, or red warning texts currently shown."""
        if self.page is None:
            return []

        def _do_eval():
            return self.page.evaluate("""(selector) => {
                const isVis = (el) => {
                    let cur = el;
                    while (cur && cur !== document.body) {
                        if (cur.hasAttribute && (cur.hasAttribute('hidden') || cur.getAttribute('aria-hidden') === 'true')) return false;
                        const st = window.getComputedStyle(cur);
                        if (st && (st.display === 'none' || st.visibility === 'hidden' || st.opacity === '0')) return false;
                        cur = cur.parentElement;
                    }
                    return true;
                };
                const isRealErrorText = (t) => {
                    const clean = t.replace(/[\\uE000-\\uF8FF]/g, '').trim();
                    if (!clean) return false;
                    const low = clean.toLowerCase();
                    if (low === 'loading...' || low === 'uploading...' || low.includes('successfully')) return false;
                    return true;
                };
                const errorNodes = Array.from(document.querySelectorAll(selector)).filter(isVis);
                const texts = errorNodes.map(e => (e.innerText || e.textContent || '').trim()).filter(isRealErrorText);

                // Also inspect visible lines starting with error keywords
                const bodyLines = (document.body.innerText || '').split('\\n').map(l => l.trim());
                const errLines = bodyLines.filter(l => (l.includes('is required') || l.includes('Please correct the errors')) && isRealErrorText(l));
                return Array.from(new Set([...texts, ...errLines]));
            }""", SELECTOR_VALIDATION_ERRORS)

        try:
            errors = _do_eval()
            return list(errors)
        except Exception as exc:
            err_str = str(exc).lower()
            if "execution context was destroyed" in err_str or "navigation" in err_str:
                try:
                    self.page.wait_for_load_state("domcontentloaded", timeout=4000)
                    return list(_do_eval())
                except Exception:
                    return []
            return []
